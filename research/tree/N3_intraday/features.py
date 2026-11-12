"""N3 intraday features. Feature at row t uses sessions t-k+1..t only (the session t is complete before the entry at
the next close). NaN where fewer than 80% of the window's sessions have data."""
import os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import harness as h


def _roll(x, k, fn="sum"):
    df = pd.DataFrame(x)
    cnt = df.notna().rolling(k, min_periods=1).sum()
    if fn == "sum":
        v = df.rolling(k, min_periods=1).sum()          # NaN-skipping sum
        v = v * k / cnt                                   # scale up partial windows
    elif fn == "std":
        v = df.rolling(k, min_periods=int(0.8 * k)).std()
    elif fn == "mean":
        v = df.rolling(k, min_periods=1).mean()
    v[cnt < 0.8 * k] = np.nan
    return v.to_numpy()


def build(D=None, R=None):
    D = D or h.load()
    R = h.load_extra("intraday")["R"] if R is None else R
    R = R.astype(np.float64)
    on = R[:, 0, :]
    ok = np.isfinite(R).all(1)
    on = np.where(ok, on, np.nan)
    bars = np.where(ok[:, None, :], R[:, 1:, :], np.nan)
    idr = bars.sum(1)
    idr[~ok] = np.nan
    last = bars[:, -1, :]
    F = {}
    for k in (5, 21, 63):
        F[f"on{k}"] = _roll(on, k)
        F[f"id{k}"] = _roll(idr, k)
    F["on21_minus_id21"] = F["on21"] - F["id21"]
    F["last30_5"] = _roll(last, 5)                                       # last half-hour return, 5 sessions
    absb = np.abs(bars)
    F["last30_share21"] = _roll(np.abs(last), 21) / _roll(np.where(ok, absb.sum(1), np.nan), 21)
    sd_id = _roll(idr, 21, "std")
    sd_on = _roll(on, 21, "std")
    F["logvol_id_over_on21"] = np.log(sd_id / sd_on)
    # tug of war frequency (Akbas et al. 2022, from memory): share of days with ON<0 & ID>0 minus ON>0 & ID<0
    tow = np.where(ok, ((on < 0) & (idr > 0)).astype(float) - ((on > 0) & (idr < 0)).astype(float), np.nan)
    F["tow_freq21"] = _roll(tow, 21, "mean")
    return F


def rank_rows(x):
    """Cross-sectional percentile rank minus 0.5 (NaN kept)."""
    return pd.DataFrame(x).rank(axis=1, pct=True).to_numpy() - 0.5
