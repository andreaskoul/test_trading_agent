"""H3b inventory bullwhip (PREREG_thesis_tree.md §4; operational definition: Amendment 5 C).

    python research/p8/h3b.py build    # -> .cache/p8/h3b_rows.parquet (all years; no statistic)
    python research/p8/h3b.py fit      # fit-sample statistic (2012-2021), descriptive, + placebo

For a report of firm i (stage k of a chain, k in S0..S3) at t0_i: partners = the firms of stage k+1 of the same
chain in i's universe (as H3a). For each partner, its latest quarter whose inventory/sales ratio was first filed
on or before the session before t0_i, and the quarter 4 earlier (end date 365 +- 20 days before). Partner value:
-(ratio_q - ratio_q-4); weight: the partner's revenue in quarter q. Signal for the membership: the revenue-weighted
mean over >= 3 partners. A firm in several chains: its signal is the mean over its memberships (one row per
report). Target: SUE_i at t0_i (primary); SUE at the next report (registered secondary); CAR at t0_i for the
economic spread. Registered sign: positive (downstream inventory builds -> upstream misses).
Placebo: stage labels shuffled within each chain (as H3a), seed 1.
Descriptive robustness: partner ratios winsorised at the fit-sample 1st/99th percentiles.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edgar as ED                                               # noqa: E402
import events as EV                                              # noqa: E402
import h1 as H1                                                  # noqa: E402
import h3a as H3A                                                # noqa: E402
import inference as I                                            # noqa: E402
import prices as PX                                              # noqa: E402
import residuals as RS                                           # noqa: E402

ROWS = os.path.join(PX.CACHE, "h3b_rows.parquet")
STAGES = H3A.STAGES


def partner_values(X, cik, asof):
    """-(ratio_q - ratio_q-4) and revenue_q for the latest quarter first filed on or before `asof`."""
    g = X.get(cik)
    if g is None:
        return None
    known = g[g["filed"] <= asof]
    if not len(known):
        return None
    q = known.iloc[-1]
    prior = known[(q["end"] - known["end"]).dt.days.between(345, 385)]
    if not len(prior):
        return None
    return -(q["ratio"] - prior.iloc[-1]["ratio"]), q["rev"]


def build(shuffle_seed=None, winsor=None):
    import json
    E = pd.read_parquet(EV.OUT).dropna(subset=["sub", "industry", "sector"])
    R = RS.returns()
    pos = {d: i for i, d in enumerate(R.index)}
    C = json.load(open(os.path.join(ED.CACHE, "ciks.json")))
    t2c = {t: x["cik"] for t, x in C.items() if x["cik"]}
    Xa = pd.read_parquet(os.path.join(ED.CACHE, "inv_sales.parquet")).sort_values(["cik", "end"])
    if winsor is not None:
        Xa["ratio"] = Xa["ratio"].clip(*winsor)
    X = {c: g for c, g in Xa.groupby("cik")}
    M = H3A.memberships(shuffle_seed)
    mem_of = {t: g[["chain", "stage"]].values.tolist() for t, g in M.groupby("ticker")}
    sp400 = set(pd.read_csv(os.path.join(PX.ROOT, "data", "raw", "stocks", "sp400_current.csv"))["Symbol"])
    msess = PX.members(R.index)
    nxt_sue = E.sort_values("t0").groupby("cik")["sue"].shift(-1)
    rows = []
    for r, nsue in zip(E.itertuples(), nxt_sue):
        if r.ticker not in mem_of or r.t0 not in pos or not np.isfinite(r.sue):
            continue
        i0 = pos[r.t0]
        asof = R.index[i0 - 1]
        m500 = set(msess.loc[r.t0]) if r.t0 in msess.index else set()
        uni_of = lambda t: "sp500" if t in m500 else ("sp400" if t in sp400 else None)
        sigs = []
        for ch, st in mem_of[r.ticker]:
            k = STAGES.index(st)
            if k > 3:
                continue
            partners = M[(M["chain"] == ch) & (M["stage"] == STAGES[k + 1]) & (M["ticker"] != r.ticker)]["ticker"]
            vals = [partner_values(X, t2c.get(t), asof) for t in partners if uni_of(t) == r.universe]
            vals = [v for v in vals if v is not None and v[1] > 0 and np.isfinite(v[0])]
            if len(vals) >= 3:
                w = np.array([v[1] for v in vals])
                sigs.append(float(np.sum(w * np.array([v[0] for v in vals])) / w.sum()))
        if not sigs:
            continue
        e = H1.resid(R, r.ticker, i0 - 1, min(i0 + 1, len(R) - 1), i0 - 1) if r.ticker in R else None
        car = float(e.sum()) if e is not None and np.isfinite(e.values).all() and len(e) == 3 else np.nan
        rows.append({"cik": r.cik, "ticker": r.ticker, "universe": r.universe, "t0": r.t0, "season": r.season,
                     "sector": r.sector, "industry": r.industry, "signal": float(np.mean(sigs)), "sue": r.sue,
                     "sue_next": nsue, "car": car, "memberships": len(sigs)})
    return pd.DataFrame(rows)


def stat(D, target="sue", B=9999):
    x = D.dropna(subset=[target])
    return I.event_test(x[target], x["signal"], x["season"] + "|" + x["sector"], x["industry"], direction=1, B=B)


def spread(D, cost=0.002):
    out = []
    for _, g in D.dropna(subset=["car"]).groupby("season"):
        if len(g) < 30:
            continue
        q = pd.qcut(g["signal"].rank(method="first"), 3, labels=False)
        out.append(g["car"][q == 2].mean() - g["car"][q == 0].mean() - cost)
    return float(np.mean(out))


if __name__ == "__main__":
    fit = lambda D: D[(D["t0"] >= "2012-01-01") & (D["t0"] <= "2021-12-31")]
    if sys.argv[1] == "build":
        D = build()
        D.to_parquet(ROWS)
        D["year"] = D["t0"].dt.year
        print(D.groupby(["year", "universe"]).size().unstack().to_string())
        print(f"rows {len(D):,}; firms {D['ticker'].nunique()}")
    elif sys.argv[1] == "fit":
        F = fit(pd.read_parquet(ROWS))
        for u in ("sp500", "sp400"):
            x = F[F["universe"] == u]
            o, o2 = stat(x), stat(x, "sue_next", B=1999)
            print(f"H3b fit {u}: n {o['n']:,}, beta {o['beta']:+.4f}, t {o['t']:+.2f}, p_wild {o['p_wild']:.4f}, "
                  f"p_ri {o['p_ri']:.4f}; secondary (next SUE) t {o2['t']:+.2f}; net tercile CAR spread {spread(x) * 1e4:+.1f} bp")
        Xa = pd.read_parquet(os.path.join(ED.CACHE, "inv_sales.parquet"))
        fx = Xa[(Xa["end"] >= "2011-01-01") & (Xa["end"] <= "2021-12-31")]["ratio"]
        W = fit(build(winsor=(fx.quantile(.01), fx.quantile(.99))))
        P = fit(build(shuffle_seed=1))
        for u in ("sp500", "sp400"):
            ow, op = stat(W[W["universe"] == u], B=1999), stat(P[P["universe"] == u], B=1999)
            print(f"  {u}: winsorised ratios t {ow['t']:+.2f}; placebo (shuffled stages) t {op['t']:+.2f}, p {op['p']:.4f}")
