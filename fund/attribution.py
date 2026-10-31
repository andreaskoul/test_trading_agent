"""Decision ledger: what followed each decision (reporting only; nothing reads it for a decision).

    python fund/attribution.py        # -> performance/attribution.json and attribution.md

Every decision of the lifecycle book (lifecycle/state.json events) and of the shadow control, plus the cohort names
the book did not enter (counterfactual rows), gets the beta-adjusted ("residual") return of the stock after the
decision's close, at h = 1, 5, 10 and 20 sessions:

    y_h = side x sum over the h sessions after the decision of (r - beta x r_SPY)

* side is the position's direction (+1 long, -1 short). For an entry or an increase, y > 0 means the added exposure
  earned. For an exit, a reduction or a horizon close, y > 0 means the stock kept moving the position's way after we
  left (the exit cost money). For a name not entered, y > 0 means the entry would have earned.
* beta is the cohort's hedge beta (screen.json), as the book uses. Returns come from lifecycle/returns.csv (frozen
  at first use), so the report never revises a recorded day.
* Event class follows PREREG_family_E.md rule A:
  * hard: earnings, guidance or capital return, or the desk's `hard` label;
  * soft: product launch, partnership, leadership, macro read-through, M&A rumour or other, without `hard`;
  * other: everything else.
* Statistics by book x action x class x h:
  * n counts complete windows only;
  * mean and median are in bp;
  * t is CR1, clustered by the decision's calendar week, since decisions in one week share market moves.
  * The rank IC is the Spearman correlation per cohort between the desk's signed weight and y over all cohort names.

This is evidence for the next protocol's design under the per-event rule, read with its sample size. It is not a test.
"""

import glob
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MODE, STATE                                    # noqa: E402

H = (1, 5, 10, 20)
HARD = {"earnings", "guidance", "capital_return"}
SOFT = {"product_launch", "partnership", "leadership", "macro_readthrough", "mna_rumour", "other"}
SKIP = {"hedge", "no_live_run"}
ADD = {"entry", "news_increase"}


def event_class(out):
    t, hard = (out or {}).get("event_type"), (out or {}).get("hard")
    if t in HARD or hard is True:
        return "hard"
    return "soft" if t in SOFT else "other"


def forward(R, day, t, h, beta=1.0):
    """Sum over the h sessions after `day` of r_t - beta x r_SPY (R: daily returns, dates x tickers, with SPY);
    NaN if the window is not complete."""
    if t not in R or "SPY" not in R:
        return np.nan
    after = R.index[R.index > pd.Timestamp(day)]
    if len(after) < h:
        return np.nan
    v = (R[t] - float(beta) * R["SPY"]).reindex(after[:h])
    return float(v.sum()) if v.notna().all() else np.nan


def cohort_info(base):
    """{as-of: {"names": lifecycle.json names, "w": fund weights, "beta": hedge betas, "entry_day": ...}}."""
    out = {}
    for wd in sorted(glob.glob(os.path.join(base, "20*"))):
        lp, bp, sp = (os.path.join(wd, f) for f in ("lifecycle.json", "book.json", "screen.json"))
        if not (os.path.exists(lp) and os.path.exists(bp)):
            continue
        L, B = json.load(open(lp)), json.load(open(bp))
        if L.get("status") != "ok":
            continue
        beta = {}
        if os.path.exists(sp):
            S = pd.DataFrame(json.load(open(sp))["rows"]).set_index("ticker")
            beta = (S["beta_hedge"] if "beta_hedge" in S else S["beta60"]).fillna(1.0).to_dict()
        out[os.path.basename(wd)] = {"names": L.get("names", {}), "w": (B.get("books") or {}).get("fund", {}),
                                     "beta": beta, "entry_day": L.get("entry_day")}
    return out


def rows_of(events, coh, E, book):
    rows = []
    for e in events:
        if e.get("action") in SKIP or "|" not in str(e.get("id")):
            continue
        a, t = e["id"].split("|", 1)
        side = int(np.sign(e["to"] if e["action"] in ADD else e["from"])) or 0
        if not side:
            continue
        c = coh.get(a, {})
        r = {"book": book, "day": e["day"], "cohort": a, "ticker": t, "action": e["action"], "side": side,
             "class": event_class((c.get("names", {}).get(t) or {}).get("out")), "notional": abs(e["to"] - e["from"])}
        r.update({f"y{h}": side * forward(E, e["day"], t, h, c.get("beta", {}).get(t, 1.0)) for h in H})
        rows.append(r)
    return rows


def not_entered(coh, events, E):
    """Cohort names with a desk weight that never got an entry event (stale, priced in, capacity or other)."""
    entered = {(e["id"].split("|", 1)[0], e["ticker"]) for e in events if e.get("action") == "entry" and "|" in str(e.get("id"))}
    rows = []
    for a, c in coh.items():
        if not c.get("entry_day"):
            continue
        for t, w in c["w"].items():
            if t == "SPY" or not w or (a, t) in entered:
                continue
            n = c["names"].get(t) or {}
            r = {"book": "not_entered", "day": c["entry_day"], "cohort": a, "ticker": t,
                 "action": "stale" if n.get("stale") else "not_entered", "side": int(np.sign(w)),
                 "class": event_class(n.get("out")), "notional": 0.0}
            r.update({f"y{h}": int(np.sign(w)) * forward(E, c["entry_day"], t, h, c["beta"].get(t, 1.0)) for h in H})
            rows.append(r)
    return rows


def stats(D):
    out = []
    if not len(D):
        return out
    D = D.assign(week=pd.to_datetime(D["day"]).dt.strftime("%G-W%V"))
    for key, g in D.groupby(["book", "action", "class"]):
        for h in H:
            y = g[f"y{h}"].dropna() * 1e4
            if not len(y):
                continue
            w = g.loc[y.index, "week"]
            m = y.mean()
            G = w.nunique()
            sc = (y - m).groupby(w).sum()
            se = np.sqrt(G / (G - 1) * (sc ** 2).sum()) / len(y) if G >= 5 else np.nan   # no t below 5 weeks
            out.append({"book": key[0], "action": key[1], "class": key[2], "h": h, "n": int(len(y)), "weeks": int(G),
                        "mean_bp": float(m), "median_bp": float(y.median()), "t": float(m / se) if se and se > 0 else None,
                        "hit": float((y > 0).mean())})
    return out


def rank_ic(coh, E, h):
    ics = {}
    for a, c in coh.items():
        if not c.get("entry_day"):
            continue
        pairs = [(w, forward(E, c["entry_day"], t, h, c["beta"].get(t, 1.0))) for t, w in c["w"].items() if t != "SPY" and w]
        pairs = [(w, y) for w, y in pairs if np.isfinite(y)]
        if len(pairs) >= 8:
            x, y = zip(*pairs)
            ics[a] = float(pd.Series(x).rank().corr(pd.Series(y).rank()))
    return ics


def build(base):
    LC = os.path.join(base, "lifecycle")
    R = pd.read_csv(os.path.join(LC, "returns.csv"), parse_dates=["date"]).pivot_table(index="date", columns="ticker", values="ret")
    coh = cohort_info(base)
    E = R                                               # residuals are taken per row, with that cohort's hedge beta
    live = json.load(open(os.path.join(LC, "state.json")))
    rows = rows_of(live.get("events", []), coh, E, "live") + not_entered(coh, live.get("events", []), E)
    cp = os.path.join(LC, "control", "state.json")
    if os.path.exists(cp):
        rows += rows_of(json.load(open(cp)).get("events", []), coh, E, "control")
    D = pd.DataFrame(rows)
    ic = {h: rank_ic(coh, E, h) for h in (5, 10)}
    return {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rows": rows, "stats": stats(D),
            "rank_ic": {str(h): {"by_cohort": v, "mean": float(np.mean(list(v.values()))) if v else None, "cohorts": len(v)}
                        for h, v in ic.items()}}


def markdown(rep):
    S = pd.DataFrame(rep["stats"])
    L = ["# Decision ledger: what followed each decision", "",
         f"Updated {rep['updated']}. Reporting only. y = the position side x the stock's residual return after the decision's "
         "close; for exits, y > 0 means the stock kept moving the position's way after we left. t is clustered by week. "
         "Small samples: read n before the mean.", ""]
    if len(S):
        for h in (5, 10):
            s = S[S.h == h].sort_values(["book", "action", "class"])
            L += [f"## {h} sessions after the decision", "", "| book | decision | news | n | weeks | mean bp | median bp | t | share > 0 |",
                  "|---|---|---|---:|---:|---:|---:|---:|---:|"]
            L += [f"| {r.book} | {r.action} | {r['class']} | {r.n} | {r.weeks} | {r.mean_bp:+.0f} | {r.median_bp:+.0f} | "
                  f"{'' if r.t is None or pd.isna(r.t) else f'{r.t:+.2f}'} | {r.hit:.0%} |" for _, r in s.iterrows()]
            L.append("")
    for h, v in rep["rank_ic"].items():
        m = "n/a" if v["mean"] is None else f"{v['mean']:+.3f}"
        L.append(f"Rank IC of the desk's weights vs the next {h} sessions' residual return: mean {m} over {v['cohorts']} cohorts.")
    return "\n".join(L) + "\n"


def clean(v):                                       # NaN -> null: browsers and strict JSON reject NaN
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [clean(x) for x in v]
    return None if isinstance(v, float) and not np.isfinite(v) else v


def main():
    base = os.path.join(STATE, MODE)
    rep = build(base)
    out = os.path.join(base, "performance")
    os.makedirs(out, exist_ok=True)
    json.dump(clean(rep), open(os.path.join(out, "attribution.json"), "w"), indent=0, default=str, allow_nan=False)
    open(os.path.join(out, "attribution.md"), "w").write(markdown(rep))
    print(f"decision ledger: {len(rep['rows'])} rows, {len(rep['stats'])} cells")


if __name__ == "__main__":
    main()
