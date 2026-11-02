"""What hard news earns at the fund's speed: a precision estimate (reports/research/PREREG_hard_news.md).

    python3 research/p8/hard_news.py count     # event counts and the weights only (no returns)
    python3 research/p8/hard_news.py check     # structure only: rows, complete windows, a sample (no y statistic)
    python3 research/p8/hard_news.py run       # ONCE -> reports/research/p8/HARD_NEWS.{lock,json,md}

Everything here is fixed by the pre-registration: cells, d, the fund's entry, horizons, placebo, errors, weights and the
decision rule. Nothing is chosen on outcomes.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import family_e as FE                                            # noqa: E402
import family_e_soft as FS                                       # noqa: E402
import inference as I                                            # noqa: E402
import prices as PX                                              # noqa: E402
import residuals as RS                                           # noqa: E402

A, B = pd.Timestamp("2016-01-01"), pd.Timestamp("2025-12-31")
H_ALL, H_PRIMARY = (5, 10, 15, 20), 10
H_L, H_R = 4.0, 10.0                                             # bp, DESIGN_RULES.md rule 1
LOCK = os.path.join(PX.OUT, "HARD_NEWS.lock")
ET = "America/New_York"
EARN_NEWS = {"earnings", "guidance"}


def y_all(R, t, i_entry, i_beta):
    """Residual sums over the first H sessions after the entry close, for every H in H_ALL (NaN if incomplete); beta
    fixed before i_beta, as family_e.resid_sum, estimated once."""
    b = RS.betas(R, t, i_beta)
    out = {}
    for h in H_ALL:
        if b is None or i_entry + h >= len(R.index):
            out[h] = np.nan
            continue
        w = R.iloc[i_entry + 1: i_entry + h + 1]
        e = w[t] - b[0] * w["SPY"]
        out[h] = float(e.sum()) if e.notna().all() else np.nan
    return out


def row(R, t, i0, info_et, cell, src, industry, t0):
    if t not in R:
        return None
    d = np.sign(FE.day0(R, t, i0))
    ent = FE.fund_entry(info_et, R.index)
    if not d or not np.isfinite(d) or ent is None:
        return None
    ys = y_all(R, t, R.index.get_loc(ent), i0 - 1)
    return {"cell": cell, "src": src, "ticker": t, "t0": R.index[i0], "entry": ent, "d": int(d), "industry": industry,
            **{f"y{h}": d * ys[h] for h in H_ALL}}


_MONTHS = {}


def placebo(R, t, i0, excl, rng, cell, src, industry, lag_min=0.0):
    """Same name, a session drawn at random from the same calendar month, >= 5 sessions from the name's events."""
    key = (id(R), R.index[i0].to_period("M"))
    if key not in _MONTHS:
        m = R.index[i0].to_period("M")
        _MONTHS[key] = [i for i, s in enumerate(R.index) if s.to_period("M") == m]
    cand = [i for i in _MONTHS[key] if all(abs(i - j) >= 5 for j in excl)]
    if not cand:
        return None
    i = int(rng.choice(cand))
    info = pd.Timestamp(R.index[i].date()) + pd.Timedelta(hours=12) + pd.Timedelta(minutes=lag_min)
    r = row(R, t, i, info, cell, src, industry, R.index[i])
    return r and {**r, "placebo": True}


def earnings_and_8k(R, gi):
    E = pd.read_parquet(os.path.join(PX.CACHE, "events.parquet"))
    E = E[E["universe"] == "sp500"].copy()
    E["et"] = FE.live_202_time(E)
    E = E[E["et"].notna()].copy()
    S = R.index
    E["t0"] = E["et"].map(lambda x: FE.t0_info(pd.Timestamp(x), S))
    E = E[E["t0"].notna() & (E["t0"] >= A) & (E["t0"] <= B)].copy()
    E["i0"] = E["t0"].map(S.get_loc)
    Hd = FE.first_per_window(FE.filing_events("hard", R).query("t0 >= @A and t0 <= @B"), 5)
    ev_idx = {}
    for t, i in list(zip(E["ticker"], E["i0"])) + list(zip(Hd["ticker"], Hd["i0"])):
        ev_idx.setdefault(t, []).append(int(i))
    rng = np.random.default_rng(0)
    rows, plac = [], []
    for r in E.sort_values(["ticker", "t0"]).itertuples():
        ind = (gi.get(r.ticker) or {}).get("industry_code", "NA")
        x = row(R, r.ticker, int(r.i0), pd.Timestamp(r.et), "E", "8-K 2.02", ind, r.t0)
        if x:
            rows.append(x)
            p = placebo(R, r.ticker, int(r.i0), ev_idx.get(r.ticker, []), rng, "E", "8-K 2.02", ind)
            if p:
                plac.append(p)
    for r in Hd.sort_values(["ticker", "t0"]).itertuples():
        ind = (gi.get(r.ticker) or {}).get("industry_code", "NA")
        x = row(R, r.ticker, int(r.i0), pd.Timestamp(r.accepted_et), "O", "8-K hard items", ind, r.t0)
        if x:
            rows.append(x)
            p = placebo(R, r.ticker, int(r.i0), ev_idx.get(r.ticker, []), rng, "O", "8-K hard items", ind)
            if p:
                plac.append(p)
    return rows, plac


def finnhub(gi, L_min):
    Rs = FS.returns_soft()
    S = FS.shocks(Rs.index)
    lab = {(x["ticker"], x["session"]): x for x in map(json.loads, open(FS.LABELS)) if x["status"] == "ok"}
    rel = FS.releases_202()
    rng = np.random.default_rng(1)
    rows, plac = [], []
    lo, hi = pd.Timestamp("2025-11-01"), pd.Timestamp("2026-10-31")
    shock_idx = {}
    for r in S.itertuples():
        if r.session in Rs.index:
            shock_idx.setdefault(r.ticker, []).append(Rs.index.get_loc(r.session))
    for t, accs in rel.items():
        for a in accs:
            s = FS.session_of(pd.Timestamp(a), Rs.index)
            if s is not None:
                shock_idx.setdefault(t, []).append(Rs.index.get_loc(s))
    for r in S.sort_values(["ticker", "session"]).itertuples():
        x = lab.get((r.ticker, str(r.session.date())))
        if not x or not (lo <= r.session <= hi) or r.ticker not in Rs:
            continue
        o = x["out"]
        if o["event_type"] in EARN_NEWS:
            cell = "earnings news"
        elif o["hard"] or o["event_type"] == "capital_return":
            cell = "O"
        else:
            continue
        ind = (gi.get(r.ticker) or {}).get("industry_code", "NA")
        i0 = Rs.index.get_loc(r.session)
        y = row(Rs, r.ticker, i0, pd.Timestamp(r.first_et) + pd.Timedelta(minutes=L_min), cell, "Finnhub", ind, r.session)
        if y:
            rows.append(y)
            p = placebo(Rs, r.ticker, i0, shock_idx.get(r.ticker, []), rng, cell, "Finnhub", ind, L_min)
            if p:
                plac.append(p)
    return rows, plac


def weights():
    """w_E: share of the live desk's hard views typed earnings or guidance, labelled cohorts from 2026-10-28 on."""
    g = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True, cwd=PX.ROOT).stdout
    g("fetch", "-q", "origin", "fund-data")
    paths = sorted(p for p in g("ls-tree", "-r", "--name-only", "origin/fund-data", "fund_state/live").split()
                   if p.endswith("/lifecycle.json") and len(p.split("/")) == 4 and p.split("/")[-2][:2] == "20"
                   and p.split("/")[-2] >= "2026-10-28")                  # dated cohort folders only
    nE = nO = 0
    for p in paths:
        for v in json.loads(g("show", f"origin/fund-data:{p}")).get("names", {}).values():
            o = v.get("out") or {}
            if v.get("status") != "ok" or not (o.get("hard") or o.get("event_type") in ("earnings", "guidance", "capital_return")):
                continue
            nE, nO = nE + (o.get("event_type") in EARN_NEWS), nO + (o.get("event_type") not in EARN_NEWS)
    return nE / (nE + nO), {"cohorts": [p.split("/")[-2] for p in paths], "n_E": nE, "n_O": nO}


def est(D, h):
    """Mean (bp) and SE: the largest of CR1 week, CR1 industry and two-way variances (inference._two_way)."""
    y = D[f"y{h}"].to_numpy(float) * 1e4
    ok = np.isfinite(y)
    y, D = y[ok], D[ok]
    if len(y) < 30:
        return {"n": int(len(y)), "mean": float(np.mean(y)) if len(y) else None, "se": None}
    gw = I._codes(pd.to_datetime(D["t0"]).dt.strftime("%G-%V").to_numpy())
    gi = I._codes(D["industry"].astype(str).to_numpy())
    m = float(y.mean())
    t, _ = I._two_way(y, gw, gi, 0.0, 1)
    se = abs(m / t) if t else float(np.std(y) / np.sqrt(len(y)))
    return {"n": int(len(y)), "mean": m, "se": float(se), "lo": m - 1.96 * se, "hi": m + 1.96 * se}


def pooled(cells, w):
    """Inverse-variance pooling within a cell's sources."""
    xs = [c for c in cells if c and c.get("se")]
    if not xs:
        return None
    iv = np.array([1 / c["se"] ** 2 for c in xs])
    m = float(np.dot(iv, [c["mean"] for c in xs]) / iv.sum())
    se = float(1 / np.sqrt(iv.sum()))
    return {"n": int(sum(c["n"] for c in xs)), "mean": m, "se": se, "lo": m - 1.96 * se, "hi": m + 1.96 * se}


def combine(e, o, w):
    m = w * e["mean"] + (1 - w) * o["mean"]
    se = float(np.sqrt((w * e["se"]) ** 2 + ((1 - w) * o["se"]) ** 2))
    return {"mean": m, "se": se, "lo": m - 1.96 * se, "hi": m + 1.96 * se}


def count():
    gi = FE.gics_of()
    w, wi = weights()
    print(f"w_E = {w:.3f} from {wi}")
    return w


def build():
    L_min = json.load(open(os.path.join(PX.OUT, "E_SOFT_READ.json")))["lag_min"]
    gi = FE.gics_of()
    w, wi = weights()
    R = FE.returns_2016()
    r1, p1 = earnings_and_8k(R, gi)
    r2, p2 = finnhub(gi, L_min)
    return pd.DataFrame(r1 + r2), pd.DataFrame(p1 + p2), w, wi, L_min


def check():
    """Structure only: rows and missing-window shares per cell and horizon, and 12 random Finnhub rows without any y.
    No mean, sum or sign of y is printed."""
    X, P, w, wi, L_min = build()
    print(f"w_E {w:.3f} {wi}; L {L_min:.0f} min")
    for nm, D in (("events", X), ("placebo", P)):
        for (c, src), g in D.groupby(["cell", "src"]):
            print(nm, c, src, "rows", len(g), "| complete windows", {h: int(g[f"y{h}"].notna().sum()) for h in H_ALL},
                  "| weeks", pd.to_datetime(g["t0"]).dt.strftime("%G-%V").nunique(), "| industries NA",
                  int((g["industry"].astype(str) == "NA").sum()))
    F = X[X.src == "Finnhub"].sample(min(12, int((X.src == "Finnhub").sum())), random_state=0)
    print(F[["cell", "ticker", "t0", "entry"]].to_string())


def run():
    if os.path.exists(LOCK):
        raise SystemExit(f"{LOCK} exists: the estimate has been made")
    X, P, w, wi, L_min = build()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=PX.ROOT).stdout.strip()
    open(LOCK, "w").write(f"{datetime.now(timezone.utc).isoformat()} commit {commit}\n")   # before any statistic
    res = {"lock": open(LOCK).read().strip(), "w_E": w, "weights_from": wi, "L_min": L_min, "by_h": {}}
    for h in H_ALL:
        cE, cP = est(X[X.cell == "E"], h), est(P[P.cell == "E"], h)
        o8, oF = est(X[(X.cell == "O") & (X.src != "Finnhub")], h), est(X[(X.cell == "O") & (X.src == "Finnhub")], h)
        cO = pooled([o8, oF], None)
        pO = pooled([est(P[(P.cell == "O") & (P.src != "Finnhub")], h), est(P[(P.cell == "O") & (P.src == "Finnhub")], h)], None)
        pool = combine(cE, cO, w) if cE.get("se") and cO else None
        ppool = combine(cP, pO, w) if cP.get("se") and pO else None
        diff = ({"mean": pool["mean"] - ppool["mean"], "se": float(np.hypot(pool["se"], ppool["se"]))} if pool and ppool else None)
        if diff:
            diff.update(lo=diff["mean"] - 1.96 * diff["se"], hi=diff["mean"] + 1.96 * diff["se"])
        side = {c: {s: est(X[(X.cell == c) & (X.d == s)], h) for s in (1, -1)} for c in ("E", "O")}
        res["by_h"][h] = {"E": cE, "E_placebo": cP, "O_8k": o8, "O_finnhub": oF, "O": cO, "O_placebo": pO,
                          "earnings_news": est(X[X.cell == "earnings news"], h), "pooled": pool, "pooled_placebo": ppool,
                          "event_minus_placebo": diff, "side": side}
    res["tail_E_16_20"] = est(X[X.cell == "E"].assign(y99=lambda d: d["y20"] - d["y15"]), 99)   # sessions 16-20
    pr = res["by_h"][H_PRIMARY]["pooled"]
    dif = res["by_h"][H_PRIMARY]["event_minus_placebo"]
    if pr["hi"] < H_L:
        dec = "LIMIT"
    elif pr["lo"] > H_R and dif and dif["lo"] > 0:
        dec = "PROPOSE"
    else:
        dec = "MEASURE"
    tl = res["tail_E_16_20"]
    res["decision"] = dec
    res["tail_rule"] = "propose a 15-session cap" if tl and tl.get("se") and tl["hi"] < 0 else "no change"
    json.dump(res, open(os.path.join(PX.OUT, "HARD_NEWS.json"), "w"), indent=1, default=str)
    write_md(res)
    X.to_parquet(os.path.join(PX.CACHE, "hard_news_rows.parquet"))
    P.to_parquet(os.path.join(PX.CACHE, "hard_news_placebo.parquet"))


def fmt(c):
    if not c or c.get("mean") is None:
        return "n/a"
    s = f"{c['mean']:+.1f}"
    return s + (f" [{c['lo']:+.1f}, {c['hi']:+.1f}]" if c.get("se") else "") + (f" (n {c['n']})" if "n" in c else "")


def write_md(res):
    L = ["# What hard news earns at the fund's speed (precision estimate, run once)", "",
         f"Lock: {res['lock']}. Pre-registration: `reports/research/PREREG_hard_news.md`. bp per event, y = d x residual "
         f"sum after the fund's entry close; [95% interval]. w_E = {res['w_E']:.2f} ({res['weights_from']['n_E']} earnings/guidance vs "
         f"{res['weights_from']['n_O']} other hard views). Hurdles: h_L {H_L:.0f} bp, h_R {H_R:.0f} bp.", "",
         "| H | E: earnings releases | E placebo | O: 8-K hard items | O: Finnhub hard | O pooled | pooled (w) | pooled placebo | event − placebo | Finnhub earnings news |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for h, r in res["by_h"].items():
        L.append(f"| {h} | {fmt(r['E'])} | {fmt(r['E_placebo'])} | {fmt(r['O_8k'])} | {fmt(r['O_finnhub'])} | {fmt(r['O'])} | "
                 f"{fmt(r['pooled'])} | {fmt(r['pooled_placebo'])} | {fmt(r['event_minus_placebo'])} | {fmt(r['earnings_news'])} |")
    L += ["", "**By side (d), H = 10:** " + "; ".join(
        f"{c} {'up' if s == '1' or s == 1 else 'down'} {fmt(v)}" for c, x in res["by_h"][H_PRIMARY]["side"].items() for s, v in x.items()),
          f"**E tail, sessions 16–20:** {fmt(res['tail_E_16_20'])} → {res['tail_rule']}.", "",
          f"**Decision (primary, pooled H = 10): {res['decision']}.**"]
    open(os.path.join(PX.OUT, "HARD_NEWS.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"count": count, "check": check, "run": run}[sys.argv[1]]()
