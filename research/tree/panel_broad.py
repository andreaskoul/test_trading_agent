"""Layer 3 read panel (PREREG Layer 3, Amendment 1): the S&P 500 panel plus the broad survivorship-free universe.
Coordinating session only.

    from panel_broad import build
    D, isb = build()          # isb: bool per column, the broad names (scored); eligibility per session in D["elig"]

Eligibility of a broad name at session t (point in time): close above $5, at least 252 sessions of history, and among
the 1,500 such names with the highest 63-session mean dollar volume. Excluded throughout: the S&P 500 panel names and
the S&P 400 names already read (panel400). Every other field: panel400.build's construction on the combined panel.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
BROAD = os.path.join(ROOT, ".cache", "tree", "broad")
TOP, MIN_PX, HIST, DV_WIN = 1500, 5.0, 252, 63


def broad_prices(exclude, S):
    b = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(os.path.join(BROAD, "chunks", "*.parquet")))])
    b = b[~b.ticker.isin(exclude)]
    b["date"] = pd.to_datetime(b["date"])
    close = b.pivot_table(index="date", columns="ticker", values="close").reindex(S)
    vol = b.pivot_table(index="date", columns="ticker", values="volume").reindex(S)
    return close, vol


def eligibility(close, vol):
    dv = (close * vol).rolling(DV_WIN, min_periods=DV_WIN).mean()
    hist = close.notna().cumsum()
    ok = (close > MIN_PX) & (hist >= HIST) & dv.notna()
    rank = dv.where(ok).rank(axis=1, ascending=False)
    return (rank <= TOP).to_numpy()


def build():
    import panel400 as P4
    import sp500_test as T
    D4, is4 = P4.build()
    px5 = pd.read_parquet(T.PX)
    px5.index = pd.to_datetime(px5.index).tz_localize(None).normalize()
    spy = px5.pop("SPY")
    S = px5.index
    names5 = list(px5.columns)
    read400 = [n for n, f in zip(D4["names"], is4) if f]
    close, vol = broad_prices(set(names5) | set(read400) | {"SPY"}, S)
    elig_b = eligibility(close, vol)
    keep = elig_b.any(0)
    close, elig_b = close.loc[:, keep], elig_b[:, keep]
    namesb = list(close.columns)
    mem = T.membership().reindex(S, method="ffill")
    elig5 = np.array([[t in s for t in names5] for s in mem.values])
    px = pd.concat([px5, close], axis=1)
    elig = np.concatenate([elig5, elig_b], 1)
    D = P4.fields(px, spy, elig) if hasattr(P4, "fields") else None
    if D is None:
        raise SystemExit("panel400.fields is required (refactor of panel400.build into fields(px, spy, elig))")
    D["names"] = names5 + namesb
    isb = np.array([False] * len(names5) + [True] * len(namesb))
    return D, isb


if __name__ == "__main__":
    D, isb = build()
    S = D["S"]
    th = (S.weekday == 3) & (S.year >= 2017)
    nb = (D["elig"][th][:, isb]).sum(1)
    meta = json.load(open(os.path.join(BROAD, "symbols.json")))["meta"]
    print(json.dumps({"broad_names_ever_eligible": int(isb.sum()), "eligible_per_Thursday_2017_2025_mean": float(nb.mean()),
                      "min": int(nb.min()), "max": int(nb.max()), "symbols_meta": meta}))
