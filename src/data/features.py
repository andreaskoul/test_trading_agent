"""Stationary feature engineering for the trading agent.

All features are causal (no look-ahead). We drop the first `warmup_bars`
rows after transformation so the rolling z-score and indicators have fully
populated windows.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def _atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()


def _tema(series: pd.Series, span: int) -> pd.Series:
    e1 = _ema(series, span)
    e2 = _ema(e1, span)
    e3 = _ema(e2, span)
    return 3 * e1 - 3 * e2 + e3


def _rolling_z(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std(ddof=0)
    return (series - mean) / (std.replace(0, np.nan))


def _hawkes_intensity(magnitude: pd.Series, beta: float) -> pd.Series:
    """Causal Hawkes-process intensity with an exponential kernel.

    Recursion lambda_t = exp(-beta) * lambda_{t-1} + magnitude_{t-1}. The
    shift(1) is what makes this strictly causal: bar t's feature only reflects
    shocks up to and including bar t-1. Implementation uses pandas EWM (alpha =
    1 - exp(-beta)) which returns the EWMA; scale by 1/alpha to recover the
    EWM sum that the Hawkes recursion produces.
    """
    decay = float(np.exp(-beta))
    alpha = 1.0 - decay
    ewma = magnitude.shift(1).ewm(alpha=alpha, adjust=False).mean()
    return ewma / alpha


def _macro_symbol_slug(sym: str) -> str:
    """Column-safe prefix for a macro ticker (e.g. '^VIX' -> 'vix')."""
    return (
        sym.replace("=", "").replace("^", "").replace(".", "_").replace("/", "_")
        .replace("-", "_").lower()
    )


def build_features(
    df: pd.DataFrame,
    warmup_bars: int = 252,
    zscore_window: int = 252,
    macro_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> pd.DataFrame:
    """Return a feature DataFrame aligned to `df.index` with a `close` passthrough."""
    out = pd.DataFrame(index=df.index)
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float).replace(0, np.nan)

    # Log returns
    log_ret = np.log(close).diff()
    out["ret_1"] = log_ret
    out["ret_5"] = log_ret.rolling(5).sum()
    out["ret_20"] = log_ret.rolling(20).sum()

    # ATR and normalised range
    atr = _atr(df, window=14)
    out["atr_rel"] = atr / close
    out["hl_range"] = ((high - low) / atr).replace([np.inf, -np.inf], np.nan)

    # EMAs expressed as distance to close normalised by ATR
    for span in (10, 30, 100):
        ema = _ema(close, span)
        out[f"ema_{span}_dist"] = ((close - ema) / atr).replace([np.inf, -np.inf], np.nan)

    # TEMA-based MACD
    tema_fast = _tema(close, 12)
    tema_slow = _tema(close, 26)
    macd = tema_fast - tema_slow
    signal = _ema(macd, 9)
    out["tema_macd"] = (macd / atr).replace([np.inf, -np.inf], np.nan)
    out["tema_macd_hist"] = ((macd - signal) / atr).replace([np.inf, -np.inf], np.nan)

    # Realised volatility (rolling) and skew
    out["rv_20"] = log_ret.rolling(20).std(ddof=0)
    out["rv_60"] = log_ret.rolling(60).std(ddof=0)
    out["skew_20"] = log_ret.rolling(20).skew()

    # Volume z-score (log volume)
    log_vol = np.log(volume)
    out["vol_z"] = _rolling_z(log_vol, zscore_window)

    # Hawkes-process intensity on |log-return| at three decay scales. Models
    # volatility / event clustering (trade bursts around COMEX opens, macro
    # prints). Three widely separated betas capture fast, session, and
    # multi-session clustering; the rolling-z loop below strips the drift.
    ret_mag = log_ret.abs().fillna(0.0)
    out["hawkes_fast"] = _hawkes_intensity(ret_mag, beta=1.0)
    out["hawkes_med"] = _hawkes_intensity(ret_mag, beta=0.1)
    out["hawkes_slow"] = _hawkes_intensity(ret_mag, beta=0.02)

    # Price z-score (useful for regime awareness even though non-stationary)
    out["close_z"] = _rolling_z(close, zscore_window)

    # Passthrough price columns the env needs
    out["close"] = close
    out["atr"] = atr

    # Rolling z-score normalise numeric features (excluding passthroughs)
    feat_cols = [c for c in out.columns if c not in ("close", "atr")]
    for col in feat_cols:
        out[col] = _rolling_z(out[col], zscore_window)

    # Intraday seasonality -- cyclic encoding of UTC hour and day-of-week.
    # Added AFTER the z-score loop so the sin/cos signal survives intact.
    # MGC trades ~23h/day so the hour-of-day feature captures London open
    # (~07:00 UTC), NY RTH open (~13:30), London PM fix (~14:00), COMEX
    # close (~17:00) without the model having to rediscover them from
    # lagged returns.
    if isinstance(out.index, pd.DatetimeIndex):
        hour = out.index.hour + out.index.minute / 60.0
        dow = out.index.dayofweek.to_numpy(dtype=float)
        out["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
        out["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
        out["dow_sin"] = np.sin(2 * np.pi * dow / 7.0)
        out["dow_cos"] = np.cos(2 * np.pi * dow / 7.0)
    else:
        # Non-datetime index (tests, synthetic): fill zeros so schema is stable.
        for col in ("hour_sin", "hour_cos", "dow_sin", "dow_cos"):
            out[col] = 0.0

    # Macro exogenous features (Phase G / iter-6). DeepTrader-style state
    # augmentation: daily macros (DXY, ^TNX, ^VIX, ^GSPC) re-sampled to bar
    # freq via forward-fill. We encode as 5- and 20-day log-returns (roughly
    # stationary) rather than raw levels, and z-score using the same warmup
    # window as the endogenous features.
    if macro_data and isinstance(out.index, pd.DatetimeIndex):
        for sym, mdf in macro_data.items():
            if mdf is None or mdf.empty or "close" not in mdf.columns:
                continue
            slug = _macro_symbol_slug(sym)
            mclose = mdf["close"].astype(float).sort_index()
            mlog = np.log(mclose.replace(0, np.nan)).dropna()
            chg5 = mlog.diff(5)
            chg20 = mlog.diff(20)
            out[f"{slug}_chg5"] = chg5.reindex(out.index, method="ffill")
            out[f"{slug}_chg20"] = chg20.reindex(out.index, method="ffill")
        macro_cols = [c for c in out.columns if c.endswith("_chg5") or c.endswith("_chg20")]
        for col in macro_cols:
            out[col] = _rolling_z(out[col].astype(float), zscore_window)

    # Drop warmup rows to guarantee everything is populated
    out = out.iloc[warmup_bars:]
    out = out.dropna()
    return out


def feature_columns(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns if c not in ("close", "atr")]
