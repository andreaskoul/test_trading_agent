"""Risk-field research (PREREG.md §8): consequences for weekly decile books on the bar universe.

P1: hedge with the best beta vs the fund's beta (B0). P2: inverse-forecast-volatility weights within each leg vs equal
weights. Books: 12-1 momentum and 1-week reversal deciles, entered at close t+1, held to close t+6, 5 bp per unit of
one-sided turnover.
"""
import numpy as np

import risk as K

COST = 5e-4


def scores(D, t):
    r = D.r
    ok = D.stock & np.isfinite(r[t - 251:t + 1]).sum(0).astype(bool) & (np.isfinite(r[t - 251:t + 1]).sum(0) >= 240)
    lr = np.where(np.isfinite(r), r, 0.0)
    mom = lr[t - 251:t - 20].sum(0)
    rev = -lr[t - 4:t + 1].sum(0)
    return {"MOM": np.where(ok, mom, np.nan), "REV": np.where(ok, rev, np.nan)}


def legs(score, inv_vol=None):
    m = np.isfinite(score) & (np.isfinite(inv_vol) if inv_vol is not None else True)
    w = np.zeros(score.shape)
    if m.sum() < 50:
        return w
    q = np.nanquantile(score[m], [0.1, 0.9])
    for side, sel in ((0.5, m & (score >= q[1])), (-0.5, m & (score <= q[0]))):
        x = np.ones(sel.sum()) if inv_vol is None else inv_vol[sel]
        w[sel] = side * x / x.sum()
    return w


def run(D, beta_best, sig_best, period):
    """Weekly book returns per book under: B0-hedged equal weight (base), best-beta-hedged equal weight (P1), and
    best-beta-hedged inverse-vol weight (P2). beta_best, sig_best: T x N forecasts (NaN where missing)."""
    import beta as BT
    Bt = BT.build(D)
    thu = np.where(Bt["thu"] & K.origins(D, 6, period))[0]
    out = {k: {"base": [], "p1": [], "p2_eq": [], "p2_iv": [], "date": []} for k in ("MOM", "REV")}
    prev = {}
    for t in thu:
        if t < 260:
            continue
        R = np.expm1(np.where(np.isfinite(D.r[t + 2:t + 7]), D.r[t + 2:t + 7], 0.0).sum(0))
        Rm = R[D.si]
        have = np.isfinite(D.r[t + 1]) & np.isfinite(Bt["B0"][t]) & np.isfinite(beta_best[t]) & np.isfinite(sig_best[t])
        for k, sc in scores(D, t).items():
            sc = np.where(have, sc, np.nan)
            we = legs(sc)
            wi = legs(sc, 1 / sig_best[t])
            h0 = -float((we * np.nan_to_num(Bt["B0"][t])).sum())
            h1 = -float((we * np.nan_to_num(beta_best[t])).sum())
            hi = -float((wi * np.nan_to_num(beta_best[t])).sum())
            res = {}
            for nm, (w, hs) in {"base": (we, h0), "p1": (we, h1), "p2_eq": (we, h1), "p2_iv": (wi, hi)}.items():
                g = float((w * R).sum() + hs * Rm)
                pw = prev.get((k, nm))
                to = 1.0 if pw is None else float(np.abs(w - pw[0]).sum() + abs(hs - pw[1]))
                prev[(k, nm)] = (w, hs)
                res[nm] = g - COST * to
            for nm, v in res.items():
                out[k][nm].append(v)
            out[k]["date"].append(D.S[t])
    return {k: {nm: np.array(v) for nm, v in d.items()} for k, d in out.items()}


def jkm(a, b):
    """Jobson-Korkie test with Memmel's correction for SR(a) - SR(b), per-period Sharpe ratios."""
    T = len(a)
    sa, sb = a.mean() / a.std(ddof=1), b.mean() / b.std(ddof=1)
    rho = np.corrcoef(a, b)[0, 1]
    theta = (2 * (1 - rho) + 0.5 * (sa ** 2 + sb ** 2 - 2 * sa * sb * rho ** 2)) / T
    return float((sa - sb) * np.sqrt(52)), float((sa - sb) / np.sqrt(theta))


def p_stats(res):
    d = np.mean([res[k]["base"] ** 2 - res[k]["p1"] ** 2 for k in res], 0)
    m, t, n = K.nw_t(d, 5)
    var = {k: {"sd_base_pct_wk": float(res[k]["base"].std() * 100), "sd_p1_pct_wk": float(res[k]["p1"].std() * 100)}
           for k in res}
    a = np.mean([res[k]["p2_iv"] for k in res], 0)
    b = np.mean([res[k]["p2_eq"] for k in res], 0)
    dsr, z = jkm(a, b)
    sh = lambda x: float(x.mean() / x.std(ddof=1) * np.sqrt(52))
    return {"P1": {"gain": m, "t": t, "weeks": n, "books": var},
            "P2": {"sharpe_diff": dsr, "t": z, "sharpe_iv": sh(a), "sharpe_eq": sh(b),
                   "net_pct_yr_iv": float((np.prod(1 + a) ** (52 / len(a)) - 1) * 100),
                   "net_pct_yr_eq": float((np.prod(1 + b) ** (52 / len(b)) - 1) * 100)}}
