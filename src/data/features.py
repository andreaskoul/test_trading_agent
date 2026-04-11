"""Stationary feature engineering for the trading agent.

All features are causal (no look-ahead). We drop the first `warmup_bars`
rows after transformation so the rolling z-score and indicators have fully
populated windows.
"""

from __future__ import annotations

from typing import List

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


def build_features(
    df: pd.DataFrame,
    warmup_bars: int = 252,
    zscore_window: int = 252,
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

    # Price z-score (useful for regime awareness even though non-stationary)
    out["close_z"] = _rolling_z(close, zscore_window)

    # Passthrough price columns the env needs
    out["close"] = close
    out["atr"] = atr

    # Rolling z-score normalise numeric features (excluding passthroughs)
    feat_cols = [c for c in out.columns if c not in ("close", "atr")]
    for col in feat_cols:
        out[col] = _rolling_z(out[col], zscore_window)

    # Drop warmup rows to guarantee everything is populated
    out = out.iloc[warmup_bars:]
    out = out.dropna()
    return out


def feature_columns(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns if c not in ("close", "atr")]
