"""Triple-barrier trade execution shared by the training envs and PaperEngine.

One implementation, so training, backtest and live can't drift apart.

fill_model="bracket" (default)
    Signal on the close of bar i. Entry at open[i+1]: an hourly job sees the
    closed bar and acts on the next one. TP/SL are resting orders at
    entry +/- rr * atr[i], checked against each bar's high/low from bar i+1.
    If both are touched in the same bar the stop is assumed first (we cannot
    see the intrabar path). A gap through a level fills at the open. The
    position times out at close[i + horizon].

fill_model="close"  (legacy, reproduces the pre-fix numbers)
    Entry at close[i]; barriers checked on the close only but filled at the
    barrier price. A stop is booked at its level after the close has gone
    through it (on average ~21 bp past it on 60m gold) and intrabar wicks
    are ignored. Under this rule random entries are profitable after costs.
"""

from __future__ import annotations

import numpy as np

FILL_MODELS = ("bracket", "close")


def require_ohlc(fill_model: str, open_, high, low) -> None:
    if fill_model not in FILL_MODELS:
        raise ValueError(f"unknown fill_model {fill_model!r}; expected one of {FILL_MODELS}")
    if fill_model == "bracket" and (open_ is None or high is None or low is None):
        raise ValueError(
            "fill_model='bracket' needs open/high/low arrays. Rebuild features "
            "(build_features now passes OHLC through) or set fill_model='close' "
            "to reproduce legacy results."
        )


def open_trade(i: int, direction: int, close, atr, open_, rr_upper: float, rr_lower: float,
               fill_model: str) -> tuple[float, float, float] | None:
    """Return (entry_price, take_profit, stop) for a signal on bar i, or None
    if there is no next bar to enter on."""
    if fill_model == "bracket":
        if i + 1 >= len(open_):
            return None
        entry = float(open_[i + 1])
    else:
        entry = float(close[i])
    a = max(float(atr[i]), 1e-8)
    return entry, entry + direction * rr_upper * a, entry - direction * rr_lower * a


def check_exit(j: int, signal_i: int, direction: int, tp: float, sl: float, horizon: int,
               open_, high, low, close, fill_model: str) -> tuple[str, float] | None:
    """Evaluate bar j (> signal_i) for an open trade. Return (barrier, fill)
    or None if the trade stays open."""
    d = direction
    if fill_model == "bracket":
        first = j == signal_i + 1          # entry happened at this bar's open
        if (d > 0 and low[j] <= sl) or (d < 0 and high[j] >= sl):
            gap = not first and d * (open_[j] - sl) <= 0
            return "sl", float(open_[j]) if gap else sl
        if (d > 0 and high[j] >= tp) or (d < 0 and low[j] <= tp):
            gap = not first and d * (open_[j] - tp) >= 0
            return "tp", float(open_[j]) if gap else tp
    else:
        c = close[j]
        if d * (c - tp) >= 0:
            return "tp", tp
        if d * (sl - c) >= 0:
            return "sl", sl
    if j - signal_i >= horizon:
        return "timeout", float(close[j])
    return None


def as_array(x):
    return None if x is None else np.asarray(x, dtype=np.float64)
