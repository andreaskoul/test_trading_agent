"""Monthly residual returns e_{i,m} for the P8 monthly tests (H3a, H5, H2): the sum of daily §1 residuals over the
sessions of calendar month m, with betas from the 252 sessions ending 21 sessions before the month's first session
(Welch-winsorised, shrunk 1/3 toward 1; sector residual when the SPDR ETF covers >= 200 of those sessions, else
market-only and flagged; Amendment 4 D4). Vectorised per month across names; identical to residuals.betas on a
single name (checked in __main__).

    python research/p8/monthly.py     # -> .cache/p8/monthly_e.parquet (month x ticker), monthly_kind.parquet
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices as PX                                              # noqa: E402
import residuals as RS                                           # noqa: E402

OUT = os.path.join(PX.CACHE, "monthly_e.parquet")
KIND = os.path.join(PX.CACHE, "monthly_kind.parquet")


def _cov_cols(Y, x):
    """Column-wise cov(Y[:, j], x) / var(x) over rows where both are finite (x a vector)."""
    M = np.isfinite(Y) & np.isfinite(x)[:, None]
    n = M.sum(0)
    xm = np.where(M, x[:, None], 0.0)
    ym = np.where(M, Y, 0.0)
    mx, my = xm.sum(0) / np.maximum(n, 1), ym.sum(0) / np.maximum(n, 1)
    cxy = ((xm - mx) * (ym - my) * M).sum(0) / np.maximum(n - 1, 1)
    vx = (((xm - mx) ** 2) * M).sum(0) / np.maximum(n - 1, 1)
    return cxy / vx, n


def build():
    R = RS.returns()
    sect = RS.SECTOR_ETF
    names = [c for c in R.columns if c not in RS.ETF.values() and c != "SPY"]
    days = R.index
    months = pd.period_range(days[0].to_period("M"), days[-1].to_period("M"), freq="M")
    E, K = {}, {}
    for m in months:
        sess = np.where(days.to_period("M") == m)[0]
        if not len(sess):
            continue
        i0 = sess[0]
        lo, hi = i0 - 21 - 252, i0 - 21
        if lo < 0:
            continue
        W = R.iloc[lo:hi]
        rm = W["SPY"].values
        Y = W[names].values
        l_, h_ = np.minimum(-2 * rm, 4 * rm)[:, None], np.maximum(-2 * rm, 4 * rm)[:, None]
        Yw = np.clip(Y, l_, h_)
        bm_raw, n = _cov_cols(Yw, rm)
        bm = 2 / 3 * bm_raw + 1 / 3
        bm[n < 200] = np.nan
        Mo = R.iloc[sess]
        em = Mo[names].values - bm[None, :] * Mo["SPY"].values[:, None]
        kind = np.array(["market_only"] * len(names), dtype=object)
        for etf in set(v for v in sect.values() if v):
            if etf not in R or W.index[0] < RS.ETF_START.get(etf, pd.Timestamp("1990-01-01")):
                continue
            rs = W[etf].values
            if np.isfinite(rs).sum() < 200:
                continue
            cols = [j for j, t in enumerate(names) if sect.get(t) == etf]
            if not cols:
                continue
            ok = np.isfinite(rs) & np.isfinite(rm)
            g = np.cov(rs[ok], rm[ok])[0, 1] / np.var(rm[ok], ddof=1)
            rres = rs - g * rm
            resid_y = Yw[:, cols] - bm_raw[cols][None, :] * rm[:, None]
            bs_raw, ns = _cov_cols(resid_y, rres)
            bs = 2 / 3 * bs_raw + 1 / 3
            bs[ns < 200] = 0.0
            em[:, cols] -= bs[None, :] * (Mo[etf].values - g * Mo["SPY"].values)[:, None]
            kind[cols] = np.where(ns >= 200, "sector", "market_only")
        full = np.isfinite(em).sum(0) >= 0.8 * len(sess)
        E[m] = pd.Series(np.where(full, np.nansum(em, 0), np.nan), index=names)
        K[m] = pd.Series(kind, index=names)
    Em, Km = pd.DataFrame(E).T, pd.DataFrame(K).T
    Em.index, Km.index = Em.index.astype(str), Km.index.astype(str)
    return Em, Km


if __name__ == "__main__":
    Em, Km = build()
    Em.to_parquet(OUT)
    Km.to_parquet(KIND)
    # cross-check against the single-name path (residuals.betas + daily e summed) on three names and months
    R = RS.returns()
    for t, m in (("AAPL", "2019-03"), ("JPM", "2014-07"), ("XOM", "2023-11")):
        sess = np.where(R.index.to_period("M") == pd.Period(m))[0]
        b = RS.betas(R, t, sess[0])
        bm, bs, etf, g = b
        w = R.iloc[sess]
        e = w[t] - bm * w["SPY"] - (bs * (w[etf] - g * w["SPY"]) if etf else 0)
        print(f"{t} {m}: vectorised {Em.loc[m, t]:+.6f} vs single-name {e.sum():+.6f}")
    print(f"months {len(Em)}, names {Em.shape[1]}, sector share {(Km == 'sector').values.mean():.1%}")
