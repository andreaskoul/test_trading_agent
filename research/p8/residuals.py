"""P8 residual returns (PREREG_thesis_tree.md §1; Amendment 4 D1, D3, D4).

e = r - b_m r_SPY - b_s r~_sector, where r~_sector is the SPDR sector ETF return residualised on SPY over the same
window. Betas use 252 daily returns ending 21 sessions before the window, with each stock return clipped to lie
between -2x and 4x SPY's that day (Welch 2022, as fund/screen.py), and both are shrunk 1/3 toward 1 (§1).
Before XLRE (2015-10-08) and XLC (2018-06-19), and for names without a current GICS sector, e is market-only
and flagged (Amendment 4, D4).

Returns: Alpaca SIP (adjusted) from 2016-01-04; yfinance (auto-adjusted) before, flagged as survivorship-biased.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices as PX                                              # noqa: E402

ETF = {"Materials": "XLB", "Communication Services": "XLC", "Energy": "XLE", "Financials": "XLF",
       "Industrials": "XLI", "Information Technology": "XLK", "Consumer Staples": "XLP", "Real Estate": "XLRE",
       "Utilities": "XLU", "Health Care": "XLV", "Consumer Discretionary": "XLY"}
ETF_START = {"XLRE": pd.Timestamp("2015-10-08"), "XLC": pd.Timestamp("2018-06-19")}
SPLICE = pd.Timestamp("2016-01-04")
WIN, GAP = 252, 21


def returns():
    """Daily simple returns, Alpaca from SPLICE, yfinance before (first Alpaca return is SPLICE's own)."""
    A = PX.panel().sort_index()
    Y = pd.read_parquet(os.path.join(PX.CACHE, "yf_sp500_close.parquet")).sort_index()
    ra = A.pct_change(fill_method=None)
    ry = Y.pct_change(fill_method=None)
    ra = ra[ra.index > SPLICE]
    ry = ry[ry.index <= SPLICE]
    R = pd.concat([ry, ra]).sort_index()
    R = R[~R.index.duplicated(keep="last")]
    # data-quality rule (fixed before reading any result): a daily |return| > 75% in this universe is a bad print or
    # a mis-adjusted corporate action (CPWR, JXG: several > 150% days), set to missing; the count is reported
    global N_BAD
    bad = R.drop(columns=[c for c in ETF.values() if c in R] + ["SPY"]).abs() > 0.75
    N_BAD = int(bad.values.sum())
    R = R.mask(bad.reindex(columns=R.columns, fill_value=False))
    return R


N_BAD = 0


def sectors():
    s = {}
    for f in ("sp500_current.csv", "sp400_current.csv"):
        d = pd.read_csv(os.path.join(PX.ROOT, "data", "raw", "stocks", f))
        s.update(dict(zip(d["Symbol"], d["GICS Sector"])))
    return s


def betas(R, t, start_idx):
    """Betas for name t from the 252 returns ending GAP sessions before position start_idx in R's index.
    Returns (b_m, b_s, etf or None)."""
    lo, hi = start_idx - GAP - WIN, start_idx - GAP
    if lo < 0:
        return None
    w = R.iloc[lo:hi]
    rm = w["SPY"]
    y = w[t]
    ok = y.notna() & rm.notna()
    if ok.sum() < 200:
        return None
    lo_, hi_ = np.minimum(-2 * rm, 4 * rm), np.maximum(-2 * rm, 4 * rm)
    yw = y.clip(lower=lo_, upper=hi_)[ok]
    rmo = rm[ok]
    bm = float(np.cov(yw, rmo)[0, 1] / rmo.var())
    etf = SECTOR_ETF.get(t)
    bs = 0.0
    okk = ok & w[etf].notna() if etf and etf in w else ok & False
    # the sector residual needs the ETF over (nearly) the whole window: before 2016 the cache has no ETF prices,
    # and a handful of overlapping days gave sector betas of ~1e13 (2016-02-09 events) before this rule
    if etf and w.index[0] >= ETF_START.get(etf, pd.Timestamp("1990-01-01")) and okk.sum() >= 200:
        rs = w[etf]
        g = float(np.cov(rs[okk], rm[okk])[0, 1] / rm[okk].var())
        rres = (rs - g * rm)[okk]                            # sector return orthogonal to SPY in the window
        resid_y = (y.clip(lower=lo_, upper=hi_) - bm * rm)[okk]
        bs = float(np.cov(resid_y, rres)[0, 1] / rres.var())
        bs = (2 / 3) * bs + 1 / 3
    else:
        etf = None
    bm = (2 / 3) * bm + 1 / 3
    return bm, bs, etf, (g if etf else 0.0)


SECTOR_ETF = {t: ETF.get(s) for t, s in sectors().items()}


def residual_path(R, t, t0_idx, pre=1, post=121):
    """e for name t over sessions t0-pre .. t0+post (inclusive) with betas fixed before the window."""
    b = betas(R, t, t0_idx - pre)
    if b is None:
        return None, None
    bm, bs, etf, g = b
    w = R.iloc[t0_idx - pre: t0_idx + post + 1]
    e = w[t] - bm * w["SPY"]
    if etf:
        e = e - bs * (w[etf] - g * w["SPY"])
    return e.values, ("sector" if etf else "market_only")
