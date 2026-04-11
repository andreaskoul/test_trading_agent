"""Triple Barrier labelling a la Lopez de Prado (AFML Ch. 3).

Labels each bar's forward window with the first barrier touched:
  +1 if upper (take-profit) hits first
  -1 if lower (stop-loss)   hits first
   0 if the vertical (timeout) barrier hits first

The `t1` timestamp of the first touch is exposed so that CPCV can purge
training samples whose labels leak into the test window.

Two label sets are produced:
  * long side  (upper = +rr_upper * ATR, lower = -rr_lower * ATR)
  * short side (upper = +rr_lower * ATR, lower = -rr_upper * ATR) - i.e. R/R flipped

For the encoder we combine them into a 3-class label:
  +1 = either direction produced a win
   0 = timeout / ambiguous
  -1 = both directions produced a loss (chop/trap)

This is an intentionally conservative multi-class signal designed for
representation learning, not for direct trade execution.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class TBConfig:
    horizon: int = 20
    rr_upper: float = 2.0
    rr_lower: float = 1.0


def _barrier_touches(
    close: np.ndarray,
    atr: np.ndarray,
    horizon: int,
    rr_upper: float,
    rr_lower: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorised-ish TB for a long trade.

    Returns (label, first_touch_offset, realised_return_at_touch) per bar.
    For bars where `bar + horizon >= n` we return 0 / horizon (unlabelled).
    """
    n = len(close)
    label = np.zeros(n, dtype=np.int8)
    t1_off = np.full(n, horizon, dtype=np.int32)
    ret = np.zeros(n, dtype=np.float64)

    for i in range(n):
        end = i + horizon
        if end >= n:
            label[i] = 0
            t1_off[i] = n - 1 - i
            ret[i] = (close[min(end, n - 1)] / close[i]) - 1.0
            continue
        upper = close[i] + rr_upper * atr[i]
        lower = close[i] - rr_lower * atr[i]
        window = close[i + 1 : end + 1]
        up_hit = np.where(window >= upper)[0]
        dn_hit = np.where(window <= lower)[0]
        up_idx = up_hit[0] if len(up_hit) else horizon + 1
        dn_idx = dn_hit[0] if len(dn_hit) else horizon + 1
        if up_idx == dn_idx == horizon + 1:
            label[i] = 0
            t1_off[i] = horizon
            ret[i] = (close[end] / close[i]) - 1.0
        elif up_idx < dn_idx:
            label[i] = 1
            t1_off[i] = up_idx + 1
            ret[i] = rr_upper * atr[i] / close[i]
        else:
            label[i] = -1
            t1_off[i] = dn_idx + 1
            ret[i] = -rr_lower * atr[i] / close[i]
    return label, t1_off, ret


def label_triple_barrier(
    features: pd.DataFrame,
    cfg: TBConfig,
) -> pd.DataFrame:
    """Return a DataFrame with columns [label_long, label_short, label_multi, t1].

    `t1` is the timestamp of the first barrier touch, required by CPCV
    purging. `label_multi` is the combined multi-class encoder target:
      +1 long side won, -1 long side lost, 0 otherwise.
    """
    close = features["close"].to_numpy(dtype=np.float64)
    atr = features["atr"].to_numpy(dtype=np.float64)
    idx = features.index

    long_lab, long_off, long_ret = _barrier_touches(close, atr, cfg.horizon, cfg.rr_upper, cfg.rr_lower)
    short_lab, short_off, _short_ret = _barrier_touches(close, atr, cfg.horizon, cfg.rr_lower, cfg.rr_upper)
    short_lab = -short_lab  # flip so +1 means "short won"

    t1_idx = np.minimum(np.arange(len(close)) + long_off, len(close) - 1)
    t1_ts = idx[t1_idx]

    out = pd.DataFrame(
        {
            "label_long": long_lab,
            "label_short": short_lab,
            "long_ret": long_ret,
            "t1": t1_ts,
        },
        index=idx,
    )
    # multi-class: both long-loss and short-loss => -1; either win => +1; else 0
    multi = np.zeros(len(close), dtype=np.int8)
    multi[(long_lab == 1) | (short_lab == 1)] = 1
    multi[(long_lab == -1) & (short_lab == -1)] = -1
    out["label_multi"] = multi
    return out
