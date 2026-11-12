"""Phase 2 read for the methods finalists (PREREG phase 2, Amendment 2): one panel with the S&P 500 names of the
phase-1 panel and the current S&P 400 members, every field built by the same code as research/quant_trials/
sp500_test.build on the combined cross-section. Coordinating session only.

    from panel400 import build
    D, is400 = build()        # is400: bool per column, the names scored in the read

S&P 400 prices: Alpaca adjusted daily closes (.cache/p8/alpaca_bars.parquet), 2016-2025, the 390 current members in
the P8 events file. Survivorship: current members only. A current S&P 400 name already in the S&P 500 panel is not
scored (it was in the phase-1 holdout universe). S&P 400 names are eligible from their first close.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
QT = os.path.join(os.path.dirname(ROOT), "quant-tf")
sys.path.insert(0, os.path.join(QT, "research", "quant_trials"))
P8 = os.path.join(ROOT, ".cache", "p8")


def build():
    import sp500_test as T
    px5 = pd.read_parquet(T.PX)
    px5.index = pd.to_datetime(px5.index).tz_localize(None).normalize()
    spy = px5.pop("SPY")
    S = px5.index
    mem = T.membership().reindex(S, method="ffill")
    names5 = list(px5.columns)
    ev = pd.read_parquet(os.path.join(P8, "events.parquet"), columns=["ticker", "universe"])
    s400 = sorted(set(ev[ev.universe == "sp400"].ticker) - set(names5))
    b = pd.read_parquet(os.path.join(P8, "alpaca_bars.parquet"), columns=["date", "ticker", "close"])
    b = b[b.ticker.isin(s400)]
    px4 = b.pivot(index="date", columns="ticker", values="close").reindex(S)
    px4 = px4.loc[:, px4.notna().sum() > 300]
    names4 = list(px4.columns)
    px = pd.concat([px5, px4], axis=1)
    names = names5 + names4
    elig5 = np.array([[t in s for t in names5] for s in mem.values])
    elig4 = px4.notna().to_numpy() & (S >= pd.Timestamp("2016-01-01"))[:, None]
    elig = np.concatenate([elig5, elig4], 1)
    # ---- from here the same construction as sp500_test.build, on the combined cross-section
    close = px.values
    lp = np.log(px)
    r = px.pct_change(fill_method=None).values
    rm = spy.pct_change().values
    sig = {"mom12_1": (lp.shift(20) - lp.shift(252)).values, "rev1m": -(lp - lp.shift(20)).values,
           "rev1w": -(lp - lp.shift(5)).values,
           "lowvol": -np.log(px).diff().rolling(60, min_periods=50).std().values,
           "high52": (px / px.rolling(252, min_periods=200).max()).values}
    spec = json.load(open(os.path.join(QT, "artefacts", "llm", "ridge_stocks.json")))
    Z = np.stack([sig[c] for c in spec["features"]], -1)
    Z[~elig] = np.nan
    with np.errstate(all="ignore"):
        Z = (Z - np.nanmean(Z, 1, keepdims=True)) / np.nanstd(Z, 1, keepdims=True)
    lo, hi = np.minimum(-2 * rm, 4 * rm)[:, None], np.maximum(-2 * rm, 4 * rm)[:, None]
    w = pd.DataFrame(np.clip(r, lo, hi), index=S)
    m = pd.Series(rm, index=S)
    beta = (2 / 3) * w.rolling(252, min_periods=200).cov(m).div(m.rolling(252, min_periods=200).var(), axis=0) \
        .fillna(1.0).values + 1 / 3
    cr = np.vstack([np.zeros((1, r.shape[1])), np.cumsum(np.nan_to_num(r), 0)])
    cm = np.concatenate([[0], np.cumsum(np.nan_to_num(rm))])
    h = 5
    y = np.full(r.shape, np.nan)
    for d in range(len(S) - 1 - h):
        a, bb = d + 2, d + 2 + h
        y[d] = (cr[bb] - cr[a]) - beta[d] * (cm[bb] - cm[a])
    valid = np.isfinite(close)
    ok = np.zeros_like(valid)
    ok[: len(S) - 1 - h] = valid[1 + h:] & valid[: len(S) - 1 - h]
    y[~(ok & elig)] = np.nan
    with np.errstate(all="ignore"):
        y = y - np.nanmean(y, 1, keepdims=True)
    e = r - np.vstack([np.full((1, r.shape[1]), np.nan), beta[:-1]]) * rm[:, None]
    D = {"S": S, "names": names, "Z": Z.astype(np.float32), "y5": y.astype(np.float32), "elig": elig,
         "e": e.astype(np.float32), "spy": spy.values, "rm": rm.astype(np.float32), "r": r.astype(np.float32),
         "beta": beta.astype(np.float32), "valid": valid}
    is400 = np.array([False] * len(names5) + [True] * len(names4))
    return D, is400


if __name__ == "__main__":
    D, is400 = build()
    S = D["S"]
    print("names: S&P 500 panel", int((~is400).sum()), "| S&P 400 scored", int(is400.sum()))
    th = (S.weekday == 3) & (S.year >= 2019)
    print("S&P 400 names with a y5 per Thursday 2019-2025: mean", float(np.isfinite(D["y5"][th][:, is400]).sum(1).mean()))
