"""H1 sympathy reversal (PREREG_thesis_tree.md §4; operational definition: Amendment 5 C).

    python research/p8/h1.py build      # -> .cache/p8/h1_rows.parquet (all years; no statistic)
    python research/p8/h1.py fit        # fit-sample statistic (2012-2021), descriptive, + placebo (shuffled peers)

For a report of firm i at t0_i: early peers P_i = same-GICS-sub-industry firms with t0_p in the same calendar
quarter and t0_p <= t0_i - 3 sessions. S_i = mean over p of sum_{s=t0_p-1}^{t0_p+1} e_{i,s} (i's own residual
return around its peers' reports). Target CAR_i = sum_{s=t0_i-1}^{t0_i+1} e_{i,s}. Registered sign: negative
(early-to-late sympathy over-reacts and reverses; Thomas & Zhang 2008). Betas for i: the §1 window ending 21
sessions before the earliest day used (min over the peers' t0_p - 1 and t0_i - 1).
Placebo (registered, expected null): peers drawn at random from other sub-industries of the same season, same count.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import events as EV                                              # noqa: E402
import inference as I                                            # noqa: E402
import prices as PX                                              # noqa: E402
import residuals as RS                                           # noqa: E402

ROWS = os.path.join(PX.CACHE, "h1_rows.parquet")


def resid(R, t, idx_from, idx_to, beta_at):
    """Daily e of name t over positions idx_from..idx_to, betas ending 21 sessions before position beta_at."""
    b = RS.betas(R, t, beta_at)
    if b is None:
        return None
    bm, bs, etf, g = b
    w = R.iloc[idx_from: idx_to + 1]
    e = w[t] - bm * w["SPY"]
    if etf:
        e = e - bs * (w[etf] - g * w["SPY"])
    return e


def build(placebo_seed=None):
    R = RS.returns()
    E = pd.read_parquet(EV.OUT).dropna(subset=["sub", "industry", "sector"])
    pos = {d: i for i, d in enumerate(R.index)}
    E = E[E["t0"].isin(pos)].copy()
    E["ti"] = E["t0"].map(pos)
    rng = np.random.default_rng(placebo_seed) if placebo_seed is not None else None
    rows = []
    for season, gs in E.groupby("season"):
        for r in gs.itertuples():
            if r.ticker not in R.columns:
                continue
            if rng is None:
                P = gs[(gs["sub"] == r.sub) & (gs["ti"] <= r.ti - 3) & (gs["cik"] != r.cik)]
            else:
                pool = gs[(gs["sub"] != r.sub) & (gs["ti"] <= r.ti - 3) & (gs["cik"] != r.cik)]
                n = len(gs[(gs["sub"] == r.sub) & (gs["ti"] <= r.ti - 3) & (gs["cik"] != r.cik)])
                if n == 0 or len(pool) < n:
                    continue
                P = pool.iloc[rng.choice(len(pool), n, replace=False)]
            if not len(P):
                continue
            lo = int(min(P["ti"].min() - 1, r.ti - 1))
            if r.ti + 1 >= len(R):
                continue
            e = resid(R, r.ticker, lo, r.ti + 1, lo)
            if e is None:
                continue
            ev = e.values
            off = lambda k: k - lo
            s_parts = [ev[off(p - 1): off(p + 1) + 1].sum() for p in P["ti"]]
            car = ev[off(r.ti - 1): off(r.ti + 1) + 1]
            if not np.isfinite(car).all() or not np.isfinite(s_parts).all():
                continue
            rows.append({"cik": r.cik, "ticker": r.ticker, "universe": r.universe, "t0": r.t0, "season": season,
                         "sector": r.sector, "industry": r.industry, "n_peers": len(P),
                         "S": float(np.mean(s_parts)), "CAR": float(car.sum())})
    return pd.DataFrame(rows)


def stat(D, B=9999):
    """Registered test on D: beta of CAR on S, season x sector FE, industry clusters, sign -; stability halves and
    the net tercile spread are computed by the family runner on validation."""
    return I.event_test(D["CAR"], D["S"], D["season"] + "|" + D["sector"], D["industry"], direction=-1, B=B)


def spread(D, cost=0.002):
    """Per season: terciles of the direction-signed signal (-S), mean CAR top minus bottom, minus 20 bp; averaged."""
    out = []
    for _, g in D.groupby("season"):
        if len(g) < 30:
            continue
        q = pd.qcut((-g["S"]).rank(method="first"), 3, labels=False)
        out.append(g["CAR"][q == 2].mean() - g["CAR"][q == 0].mean() - cost)
    return float(np.mean(out))


if __name__ == "__main__":
    if sys.argv[1] == "build":
        D = build()
        D.to_parquet(ROWS)
        D["year"] = D["t0"].dt.year
        print(D.groupby(["year", "universe"]).size().unstack().to_string())
        print(f"rows {len(D):,}; median peers {D['n_peers'].median():.0f}")
    elif sys.argv[1] == "fit":
        D = pd.read_parquet(ROWS)
        F = D[(D["t0"] >= "2012-01-01") & (D["t0"] <= "2021-12-31")]
        for u in ("sp500", "sp400"):
            x = F[F["universe"] == u]
            o = stat(x)
            print(f"H1 fit 2012-21 {u}: n {o['n']:,}, beta {o['beta']:+.4f}, t {o['t']:+.2f}, p_wild {o['p_wild']:.4f}, "
                  f"p_ri {o['p_ri']:.4f}, clusters {o['clusters']}; net tercile spread {spread(x) * 1e4:+.1f} bp")
        Pl = build(placebo_seed=1)
        Pl = Pl[(Pl["t0"] >= "2012-01-01") & (Pl["t0"] <= "2021-12-31")]
        for u in ("sp500", "sp400"):
            o = stat(Pl[Pl["universe"] == u])
            print(f"H1 placebo (random other-sub-industry peers) {u}: beta {o['beta']:+.4f}, t {o['t']:+.2f}, p {o['p']:.4f}")
