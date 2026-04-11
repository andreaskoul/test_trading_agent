"""Gold OHLCV loader.

Primary source is real Micro Gold Futures (MGC) 60-minute OHLCV published on
GitHub (domzack/mgc-ohlcv-data) — the sandbox allows raw.githubusercontent.com
but blocks Yahoo/Stooq/Tiingo/Alphavantage/FRED. We optionally try yfinance as
a secondary path for users running outside the sandbox, and fall back to a
synthetic GBM+GARCH series only if every network source fails.
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class LoadResult:
    df: pd.DataFrame
    source: str  # "github:MGC_60m", "yfinance:GC=F", "synthetic", ...


REQUIRED_COLS = ["open", "high", "low", "close", "volume"]

MGC_60M_URL = (
    "https://raw.githubusercontent.com/domzack/mgc-ohlcv-data/"
    "master/aggregated/continuous/ohlcv_MGC_60m_continuous.csv"
)


def _standardise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: c.lower() for c in df.columns})
    # yfinance sometimes returns "adj close" which we drop.
    df = df[[c for c in df.columns if c in REQUIRED_COLS]]
    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = np.nan
    df = df[REQUIRED_COLS].copy()
    df.index = pd.to_datetime(df.index, utc=True)
    df = df[~df.index.duplicated(keep="first")].sort_index()
    df = df.dropna(subset=["close"])
    return df


def _try_github_mgc() -> Optional[pd.DataFrame]:
    """Fetch real Micro Gold Futures 60-min OHLCV from GitHub.

    This endpoint is on raw.githubusercontent.com, which is reachable from the
    sandbox egress allow-list (whereas Yahoo/Stooq/etc. are not). The CSV
    covers 2023-01 onward with ~20k hourly bars.
    """
    try:
        import urllib.request

        log.info("fetching real MGC 60m OHLCV from %s", MGC_60M_URL)
        with urllib.request.urlopen(MGC_60M_URL, timeout=60) as r:
            payload = r.read()
    except Exception as exc:
        log.warning("github MGC download failed: %s", exc)
        return None

    try:
        df = pd.read_csv(io.BytesIO(payload))
    except Exception as exc:
        log.warning("MGC CSV parse failed: %s", exc)
        return None

    if "timestamp" not in df.columns:
        return None
    df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return _standardise(df)


def _try_yfinance(symbol: str, start: str, end: str, interval: str) -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf  # local import so tests without yfinance still run
    except Exception as exc:  # pragma: no cover
        log.warning("yfinance import failed: %s", exc)
        return None
    try:
        raw = yf.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if raw is None or len(raw) == 0:
            return None
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        return _standardise(raw)
    except Exception as exc:  # network errors, symbol not found, etc.
        log.warning("yfinance download failed for %s: %s", symbol, exc)
        return None


def _synthetic(n: int = 5000, seed: int = 7) -> pd.DataFrame:
    """GBM + GARCH(1,1)-like volatility clustering, calibrated to gold-ish stats."""
    rng = np.random.default_rng(seed)
    mu = 0.0002
    omega, alpha, beta = 1e-6, 0.08, 0.90
    sigma2 = np.full(n, 1e-4)
    eps = rng.standard_normal(n)
    for t in range(1, n):
        sigma2[t] = omega + alpha * (eps[t - 1] ** 2) * sigma2[t - 1] + beta * sigma2[t - 1]
    sigma = np.sqrt(sigma2)
    rets = mu + sigma * eps
    close = 1500.0 * np.exp(np.cumsum(rets))
    noise = rng.normal(0, 0.0015, size=(n, 4))
    open_ = close * (1 + noise[:, 0])
    high = np.maximum.reduce([close, open_, close * (1 + np.abs(noise[:, 1]))])
    low = np.minimum.reduce([close, open_, close * (1 - np.abs(noise[:, 2]))])
    volume = np.abs(rng.normal(1e5, 2e4, size=n)).astype(np.int64)
    idx = pd.date_range("2005-01-03", periods=n, freq="B", tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def load_gold(
    symbol: str,
    fallback_symbols: List[str],
    start: str,
    end: str,
    interval: str = "1d",
    cache_path: Optional[str] = None,
    force_synthetic: bool = False,
) -> LoadResult:
    """Load OHLCV gold data with primary -> fallbacks -> synthetic."""
    if cache_path and os.path.exists(cache_path) and not force_synthetic:
        log.info("loading cached OHLCV from %s", cache_path)
        df = pd.read_parquet(cache_path)
        source = str(df.attrs.get("source", "cache"))
        return LoadResult(df=df, source=source)

    if not force_synthetic:
        # Primary: real MGC 60m OHLCV from GitHub (sandbox-reachable).
        df = _try_github_mgc()
        if df is not None and len(df) > 500:
            df.attrs["source"] = "github:MGC_60m"
            if cache_path:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                df.to_parquet(cache_path)
            return LoadResult(df=df, source="github:MGC_60m")

        # Secondary: yfinance (useful outside the sandbox).
        for sym in [symbol, *fallback_symbols]:
            log.info("trying yfinance symbol %s", sym)
            df = _try_yfinance(sym, start, end, interval)
            if df is not None and len(df) > 500:
                df.attrs["source"] = f"yfinance:{sym}"
                if cache_path:
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    df.to_parquet(cache_path)
                return LoadResult(df=df, source=f"yfinance:{sym}")

    log.warning("falling back to synthetic OHLCV (network failed or forced)")
    df = _synthetic(n=5000)
    df.attrs["source"] = "synthetic"
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        df.to_parquet(cache_path)
    return LoadResult(df=df, source="synthetic")
