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

Two further tables (added 2026-11-02; measurement only):
* **Agreement.** For each entry and each name not entered: does the desk's side match the sign of the stock's residual
  move on the news session? The session is B1's release session where recorded, else Amendment 8's news session. Rule
  A needed this share. Break-even needs (2a - 1) x mu >= cost, where a is the share and mu the follow-through.
  Reported as k/n with a Wilson 95% interval.
* **Holding-period segments.** Each lot's residual return per session held, side x (r - beta x r_SPY), per unit of
  position, by session after entry: 1-3, 4-15 and 16+. Earnings reaction sessions are split out where one falls
  inside a holding. They come from the cohort's earnings calendar, which the desk records from the 2026-10-28 cohort
  on, so earlier lots are never flagged. "before entry" is the move from the cohort's as-of close to the entry close: it is not
  P&L, it is what moved before we traded.

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
from lifecycle_rules import soft_view                             # noqa: E402

H = (1, 5, 10, 20)
HARD = {"earnings", "guidance", "capital_return"}
SOFT = {"product_launch", "partnership", "leadership", "macro_readthrough", "mna_rumour", "other"}
SKIP = {"hedge", "no_live_run"}
ADD = {"entry", "news_increase"}
SEG = ((1, 3, "1-3"), (4, 15, "4-15"), (16, 10 ** 6, "16+"))


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


def news_move(c, t, E):
    """(session, residual move) of ticker t on its news session: B1's release session if the desk recorded one, else
    Amendment 8's news session, else the desk's first-report date (as rule A's applicability count); the first trading
    session on or after it. (None, NaN) if unknown."""
    n = (c.get("names") or {}).get(t) or {}
    s = ((n.get("release") or {}).get("session") or (n.get("inputs") or {}).get("news_session")
         or (n.get("out") or {}).get("first_reported"))          # cohorts before Amendment 8: the first report date
    if not s or t not in E or "SPY" not in E:
        return None, np.nan
    d = E.index[E.index >= pd.Timestamp(s)]
    if not len(d):
        return None, np.nan
    v = E.at[d[0], t] - float(c.get("beta", {}).get(t, 1.0)) * E.at[d[0], "SPY"]
    return str(d[0].date()), (float(v) if np.isfinite(v) else np.nan)


def agree_fields(c, t, side, E):
    s0, mv = news_move(c, t, E)
    return {"news_session": s0, "news_move": mv,
            "agree": None if not np.isfinite(mv) or mv == 0 else int(np.sign(mv) == side)}


def reaction_session(info, sessions):
    """The session that first trades on the firm's next report in the cohort's earnings calendar (as
    lifecycle.catalyst_session: before the open or time unknown -> that day; after the close -> the next session)."""
    cal = (info.get("inputs") or {}).get("catalyst")
    if not cal:
        return None
    d, tm = pd.Timestamp(cal[0]), (cal[1] if len(cal) > 1 else "") or ""
    x = [s for s in sessions if s > d or (s == d and tm in ("bmo", "dmh", ""))]
    return x[0] if x else None


def segments(events, coh, E, book):
    """Per lot: one row per session held (side x residual return, per unit of position) and one 'before entry' row."""
    by = {}
    for e in events:
        if "|" in str(e.get("id")) and e.get("action") not in SKIP:
            by.setdefault(e["id"], []).append(e)
    S, rows = E.index, []
    for lid, ev in by.items():
        ent = next((e for e in ev if e["action"] == "entry"), None)
        a, t = lid.split("|", 1)
        if ent is None or t not in E or "SPY" not in E or not np.sign(ent["to"]):
            continue
        side, c = int(np.sign(ent["to"])), coh.get(a, {})
        beta = float(c.get("beta", {}).get(t, 1.0))
        res = (E[t] - beta * E["SPY"]) * side
        d0 = pd.Timestamp(ent["day"])
        shut = [pd.Timestamp(e["day"]) for e in ev if e is not ent and pd.Timestamp(e["day"]) >= d0 and abs(e["to"]) < 1e-9]
        end = min(shut) if shut else S[-1]
        er = reaction_session((c.get("names") or {}).get(t) or {}, S)
        for k, d in enumerate(S[(S > d0) & (S <= end)], 1):
            if np.isfinite(res.get(d, np.nan)):
                rows.append({"book": book, "id": lid, "ticker": t, "day": str(d.date()), "k": k, "side": side,
                             "seg": next(g for lo, hi, g in SEG if lo <= k <= hi),
                             "earnings": bool(er is not None and d == er), "y": float(res[d])})
        pre = res[(S > pd.Timestamp(a)) & (S <= d0)]
        if len(pre) and pre.notna().all():
            rows.append({"book": book, "id": lid, "ticker": t, "day": str(d0.date()), "k": 0, "side": side,
                         "seg": "before entry", "earnings": False, "y": float(pre.sum())})
    return rows


def wilson(k, n, z=1.96):
    if not n:
        return None, None
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return float(c - h), float(c + h)


def agreement(D):
    out = []
    if not len(D) or "agree" not in D:
        return out
    for key, g in D[D["agree"].notna()].groupby(["book", "action", "class"]):
        k, n = int(g["agree"].sum()), int(len(g))
        lo, hi = wilson(k, n)
        out.append({"book": key[0], "action": key[1], "class": key[2], "agree": k, "n": n, "share": k / n, "lo95": lo, "hi95": hi})
    return out


def seg_stats(G):
    """Mean residual per lot-session (bp) by book x segment, x side, x earnings session; CR1 t by week (>= 5 weeks)."""
    out = []
    if not len(G):
        return out
    G = G.assign(week=pd.to_datetime(G["day"]).dt.strftime("%G-W%V"),
                 side_=np.where(G["side"] > 0, "long", "short"), earn=np.where(G["earnings"], "earnings", "other"))
    has_e = G.groupby(["book", "seg"])["earnings"].transform("any")      # split only where an earnings session exists
    for keys in (["book", "seg"], ["book", "seg", "side_"], ["book", "seg", "earn"]):
        for key, g in (G[has_e] if keys[-1] == "earn" else G).groupby(keys):
            y = g["y"] * 1e4
            m, W = y.mean(), g["week"].nunique()
            sc = (y - m).groupby(g["week"]).sum()
            se = np.sqrt(W / (W - 1) * (sc ** 2).sum()) / len(y) if W >= 5 else np.nan
            out.append({**dict(zip(["book", "seg", "split"], list(key) + [None] * (3 - len(key)))), "by": keys[-1] if len(keys) == 3 else "all",
                        "n": int(len(y)), "lots": int(g["id"].nunique()), "weeks": int(W), "mean_bp": float(m),
                        "t": float(m / se) if se and se > 0 else None})
    return out


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
        if e["action"] == "entry":
            r.update(agree_fields(c, t, side, E))
        rows.append(r)
    return rows


def not_entered(coh, events, E):
    """Cohort names with a desk weight that never got an entry event (stale, priced in, a soft view under 7B A3,
    capacity or other)."""
    entered = {(e["id"].split("|", 1)[0], e["ticker"]) for e in events if e.get("action") == "entry" and "|" in str(e.get("id"))}
    rows = []
    for a, c in coh.items():
        if not c.get("entry_day"):
            continue
        for t, w in c["w"].items():
            if t == "SPY" or not w or (a, t) in entered:
                continue
            n = c["names"].get(t) or {}
            a3 = soft_view(n, pd.Timestamp(c["entry_day"]))       # 7B A3: a soft view the live book did not act on
            r = {"book": "not_entered", "day": c["entry_day"], "cohort": a, "ticker": t,
                 "action": "stale" if n.get("stale") else ("a3_soft" if a3 else "not_entered"), "side": int(np.sign(w)),
                 "class": event_class(n.get("out")), "notional": 0.0}
            r.update({f"y{h}": int(np.sign(w)) * forward(E, c["entry_day"], t, h, c["beta"].get(t, 1.0)) for h in H})
            r.update(agree_fields(c, t, int(np.sign(w)), E))
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
    segs = segments(live.get("events", []), coh, E, "live")
    cp = os.path.join(LC, "control", "state.json")
    if os.path.exists(cp):
        cev = json.load(open(cp)).get("events", [])
        rows += rows_of(cev, coh, E, "control")
        segs += segments(cev, coh, E, "control")
    D = pd.DataFrame(rows)
    ic = {h: rank_ic(coh, E, h) for h in (5, 10)}
    return {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rows": rows, "stats": stats(D),
            "agreement": agreement(D), "segments": seg_stats(pd.DataFrame(segs)),
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
    A = pd.DataFrame(rep.get("agreement", []))
    if len(A):
        L += ["## Does the desk's side match the news-day move?", "",
              "Share of names whose side equals the sign of the residual move on the news session. Break-even for a "
              "follow-through trade: (2a - 1) x mu >= the round-trip cost.", "",
              "| book | decision | news | agree / n | share | 95% interval |", "|---|---|---|---:|---:|---|"]
        L += [f"| {r.book} | {r.action} | {r['class']} | {r.agree}/{r.n} | {r.share:.0%} | {r.lo95:.0%}-{r.hi95:.0%} |"
              for _, r in A.sort_values(["book", "action", "class"]).iterrows()]
        L.append("")
    G = pd.DataFrame(rep.get("segments", []))
    if len(G):
        L += ["## Where the result comes from: residual return per session held", "",
              "Per unit of position, side x (r - beta x r_SPY), bp per lot-session. 'before entry' is one value per lot: "
              "the move from the as-of close to the entry close (not P&L). Earnings sessions are split out only where one fell "
              "inside a holding (calendar recorded from the 2026-10-28 cohort).", "",
              "| book | segment | split | lot-sessions | lots | weeks | mean bp | t |", "|---|---|---|---:|---:|---:|---:|---:|"]
        order = {"before entry": 0, "1-3": 1, "4-15": 2, "16+": 3}
        G = G.assign(o=G["seg"].map(order)).sort_values(["book", "o", "by", "split"], na_position="first")
        L += [f"| {r.book} | {r.seg} | {'all' if pd.isna(r.split) else r.split} | {r.n} | {r.lots} | {r.weeks} | {r.mean_bp:+.1f} | "
              f"{'' if r.t is None or pd.isna(r.t) else f'{r.t:+.2f}'} |" for _, r in G.iterrows()]
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
