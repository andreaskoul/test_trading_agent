"""Multi-asset OHLCV loader.

Supports any symbol via yfinance with synthetic GBM+GARCH fallback.
Real Micro Gold Futures (MGC) 60-minute OHLCV from GitHub
(domzack/mgc-ohlcv-data) is the primary source for gold; the sandbox
allows raw.githubusercontent.com but blocks Yahoo/Stooq/Tiingo etc.

For other assets the priority is:
  1. Cached parquet (if exists)
  2. Known GitHub CSV sources (currently MGC only)
  3. yfinance
  4. Synthetic GBM+GARCH calibrated to the symbol's typical dynamics
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class LoadResult:
    df: pd.DataFrame
    source: str  # "github:MGC_60m", "yfinance:GC=F", "synthetic", ...


REQUIRED_COLS = ["open", "high", "low", "close", "volume"]

# ---------------------------------------------------------------------------
# Known GitHub CSV sources (sandbox-reachable)
# ---------------------------------------------------------------------------
KNOWN_GITHUB_SOURCES: Dict[str, str] = {
    "GC=F": (
        "https://raw.githubusercontent.com/domzack/mgc-ohlcv-data/"
        "master/aggregated/continuous/ohlcv_MGC_60m_continuous.csv"
    ),
}

# Keep old constant for backward compat
MGC_60M_URL = KNOWN_GITHUB_SOURCES["GC=F"]

# ---------------------------------------------------------------------------
# Synthetic profiles: (start_price, mu, omega, alpha, beta)
# ---------------------------------------------------------------------------
_SYNTHETIC_PROFILES: Dict[str, Tuple[float, float, float, float, float]] = {
    "GC=F":      (1500.0, 0.0002,  1e-6, 0.08, 0.90),
    "SI=F":      (25.0,   0.0002,  1e-6, 0.09, 0.89),
    "CL=F":      (80.0,   0.0003,  2e-6, 0.10, 0.88),
    "EURUSD=X":  (1.08,   0.00003, 5e-7, 0.05, 0.92),
    "GBPUSD=X":  (1.27,   0.00003, 5e-7, 0.06, 0.91),
}

# Default profile (gold-calibrated) for unknown symbols
_DEFAULT_PROFILE = (1500.0, 0.0002, 1e-6, 0.08, 0.90)


def _synthetic_profile(symbol: str) -> Tuple[float, float, float, float, float]:
    """Return (start_price, mu, omega, alpha, beta) for a symbol."""
    profile = _SYNTHETIC_PROFILES.get(symbol)
    if profile is not None:
        return profile
    # Try partial match (e.g. "GLD" matches gold profile)
    sym_up = symbol.upper()
    if any(k in sym_up for k in ("GC", "GOLD", "GLD", "XAU")):
        return _SYNTHETIC_PROFILES["GC=F"]
    if any(k in sym_up for k in ("SI", "SLV", "SILVER")):
        return _SYNTHETIC_PROFILES["SI=F"]
    if any(k in sym_up for k in ("CL", "OIL", "CRUDE", "WTI")):
        return _SYNTHETIC_PROFILES["CL=F"]
    if any(k in sym_up for k in ("EUR",)):
        return _SYNTHETIC_PROFILES["EURUSD=X"]
    if any(k in sym_up for k in ("GBP",)):
        return _SYNTHETIC_PROFILES["GBPUSD=X"]
    log.warning("no synthetic profile for %s; using gold defaults", symbol)
    return _DEFAULT_PROFILE


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


def _try_github_csv(url: str) -> Optional[pd.DataFrame]:
    """Fetch OHLCV from a known GitHub CSV URL."""
    try:
        import urllib.request
        log.info("fetching OHLCV from %s", url)
        with urllib.request.urlopen(url, timeout=60) as r:
            payload = r.read()
    except Exception as exc:
        log.warning("github download failed: %s", exc)
        return None
    try:
        df = pd.read_csv(io.BytesIO(payload))
    except Exception as exc:
        log.warning("CSV parse failed: %s", exc)
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
        import yfinance as yf
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
    except Exception as exc:
        log.warning("yfinance download failed for %s: %s", symbol, exc)
        return None


def _synthetic(
    n: int = 5000,
    seed: int = 7,
    start_price: Optional[float] = None,
    mu: Optional[float] = None,
    garch_params: Optional[Tuple[float, float, float]] = None,
) -> pd.DataFrame:
    """GBM + GARCH(1,1)-like volatility clustering.

    Parameters are optional; defaults are gold-calibrated for backward
    compatibility.
    """
    rng = np.random.default_rng(seed)
    _mu = mu if mu is not None else 0.0002
    if garch_params is not None:
        omega, alpha, beta = garch_params
    else:
        omega, alpha, beta = 1e-6, 0.08, 0.90
    _price = start_price if start_price is not None else 1500.0

    sigma2 = np.full(n, 1e-4)
    eps = rng.standard_normal(n)
    for t in range(1, n):
        sigma2[t] = omega + alpha * (eps[t - 1] ** 2) * sigma2[t - 1] + beta * sigma2[t - 1]
    sigma = np.sqrt(sigma2)
    rets = _mu + sigma * eps
    close = _price * np.exp(np.cumsum(rets))
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


def load_ohlcv(
    symbol: str,
    fallback_symbols: Optional[List[str]] = None,
    start: str = "2005-01-01",
    end: str = "2025-12-31",
    interval: str = "1d",
    cache_path: Optional[str] = None,
    force_synthetic: bool = False,
) -> LoadResult:
    """Load OHLCV data for any symbol: cache -> GitHub -> yfinance -> synthetic."""
    if fallback_symbols is None:
        fallback_symbols = []

    if cache_path and os.path.exists(cache_path) and not force_synthetic:
        log.info("loading cached OHLCV from %s", cache_path)
        df = pd.read_parquet(cache_path)
        source = str(df.attrs.get("source", "cache"))
        return LoadResult(df=df, source=source)

    if not force_synthetic:
        # Try known GitHub CSV sources for this symbol. Current mirror
        # (domzack/mgc-ohlcv-data) only hosts 60m bars, so skip it when the
        # caller asks for a different interval -- otherwise we'd silently
        # serve 60m data under a 15m label.
        github_url = KNOWN_GITHUB_SOURCES.get(symbol)
        if github_url and interval.lower() in ("60m", "1h"):
            df = _try_github_csv(github_url)
            if df is not None and len(df) > 500:
                df.attrs["source"] = f"github:{symbol}"
                if cache_path:
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    df.to_parquet(cache_path)
                return LoadResult(df=df, source=f"github:{symbol}")

        # yfinance: try primary symbol then fallbacks
        for sym in [symbol, *fallback_symbols]:
            log.info("trying yfinance symbol %s", sym)
            df = _try_yfinance(sym, start, end, interval)
            if df is not None and len(df) > 500:
                df.attrs["source"] = f"yfinance:{sym}"
                if cache_path:
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    df.to_parquet(cache_path)
                return LoadResult(df=df, source=f"yfinance:{sym}")

    # Synthetic fallback, calibrated to this symbol's typical dynamics
    log.warning("falling back to synthetic OHLCV for %s", symbol)
    price, mu, omega, alpha, beta = _synthetic_profile(symbol)
    df = _synthetic(
        n=5000, seed=hash(symbol) % (2**31),
        start_price=price, mu=mu, garch_params=(omega, alpha, beta),
    )
    df.attrs["source"] = f"synthetic:{symbol}"
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        df.to_parquet(cache_path)
    return LoadResult(df=df, source=f"synthetic:{symbol}")


# Backward-compatible alias
load_gold = load_ohlcv
