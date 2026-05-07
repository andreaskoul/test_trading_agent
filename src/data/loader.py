"""Multi-asset OHLCV loader.

Supports any symbol via yfinance with synthetic GBM+GARCH fallback.
Real Micro Gold Futures (MGC) 60-minute OHLCV from GitHub
(domzack/mgc-ohlcv-data) is the primary source for gold; the sandbox
allows raw.githubusercontent.com but blocks Yahoo/Stooq/Tiingo etc.

Historical pre-training gold spot data (2012-2022) is available in
data/raw/gold_xauusd_h1.parquet (ejtraderLabs/historical-data on GitHub).
Use scripts/fetch_free_data.py to regenerate all free-source parquets.

For other assets the priority is:
  1. Cached parquet (if exists)
  2. Known GitHub CSV sources (currently MGC only)
  3. FRED direct CSV (VIX, 10Y yield, DXY, S&P 500 — no API key needed)
  4. FMP (Financial Modeling Prep) REST API — set FMP_API_KEY env var
  5. yfinance
  6. Synthetic GBM+GARCH calibrated to the symbol's typical dynamics
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

# GitHub-hosted macro series reachable in restricted-network environments.
# These are curated open-data repos; updated infrequently but real data.
# VIX: daily OHLCV back to 1990 (datasets/finance-vix)
# ^GSPC: monthly close back to 1871 (datasets/s-and-p-500) — forward-filled
# ^TNX:  monthly rate back to 1953 (datasets/bond-yields-us-10y) — forward-filled
KNOWN_GITHUB_MACRO: Dict[str, str] = {
    "^VIX":  "https://raw.githubusercontent.com/datasets/finance-vix/main/data/vix-daily.csv",
    "^GSPC": "https://raw.githubusercontent.com/datasets/s-and-p-500/master/data/data.csv",
    "^TNX":  "https://raw.githubusercontent.com/datasets/bond-yields-us-10y/master/data/monthly.csv",
}

# FRED direct CSV downloads (no API key required, always current).
# Format: observation_date,<SERIES_ID>  — missing values encoded as '.'
# Preferred over the GitHub monthly CSVs above because they are daily and
# updated to T-1.  data/raw/macro_*.parquet are pre-seeded by
# scripts/fetch_free_data.py so these URLs are only hit when the cache is
# absent or force_refresh=True.
KNOWN_FRED_MACRO: Dict[str, str] = {
    "^VIX":  "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS",
    "^TNX":  "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
    "DX=F":  "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS",
    "^GSPC": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500",
}

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


def _try_github_macro(symbol: str) -> Optional[pd.DataFrame]:
    """Fetch a macro series from a known GitHub open-data CSV.

    Handles three formats:
    - ^VIX  : DATE(MM/DD/YYYY), OPEN, HIGH, LOW, CLOSE — daily
    - ^GSPC : Date(YYYY-MM-DD), SP500 — monthly, forward-filled to daily
    - ^TNX  : Date(YYYY-MM-DD), Rate  — monthly, forward-filled to daily
    """
    url = KNOWN_GITHUB_MACRO.get(symbol)
    if url is None:
        return None
    try:
        import urllib.request
        log.info("fetching macro %s from github: %s", symbol, url)
        with urllib.request.urlopen(url, timeout=30) as r:
            payload = r.read()
        df = pd.read_csv(io.BytesIO(payload))
    except Exception as exc:
        log.warning("github macro fetch failed for %s: %s", symbol, exc)
        return None

    try:
        if symbol == "^VIX":
            # DATE format: MM/DD/YYYY
            df.columns = [c.strip().lower() for c in df.columns]
            df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y", utc=True)
            df = df.set_index("date").sort_index()
            # Has open/high/low/close already
            return _standardise(df)

        elif symbol == "^GSPC":
            # Date: YYYY-MM-DD, SP500 column = monthly close
            df["date"] = pd.to_datetime(df["Date"], utc=True)
            df = df.rename(columns={"SP500": "close"}).set_index("date").sort_index()
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df = df[["close"]].dropna()
            # Forward-fill monthly to business-day daily
            daily_idx = pd.date_range(df.index[0], df.index[-1], freq="B", tz="UTC")
            df = df.reindex(daily_idx, method="ffill")
            df["open"] = df["close"]
            df["high"] = df["close"]
            df["low"]  = df["close"]
            df["volume"] = 0
            return _standardise(df)

        elif symbol == "^TNX":
            # Date: YYYY-MM-DD, Rate column = monthly 10Y yield
            df["date"] = pd.to_datetime(df["Date"], utc=True)
            df = df.rename(columns={"Rate": "close"}).set_index("date").sort_index()
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df = df[["close"]].dropna()
            daily_idx = pd.date_range(df.index[0], df.index[-1], freq="B", tz="UTC")
            df = df.reindex(daily_idx, method="ffill")
            df["open"] = df["close"]
            df["high"] = df["close"]
            df["low"]  = df["close"]
            df["volume"] = 0
            return _standardise(df)

    except Exception as exc:
        log.warning("github macro parse failed for %s: %s", symbol, exc)
    return None


def _try_fred_macro(symbol: str) -> Optional[pd.DataFrame]:
    """Fetch a macro series from FRED's direct CSV endpoint (no API key).

    FRED CSV format: two columns — observation_date, <SERIES_ID>.
    Missing observations are encoded as '.' and dropped.
    Returns a daily OHLCV frame where open=high=low=close=value, volume=0.
    """
    url = KNOWN_FRED_MACRO.get(symbol)
    if url is None:
        return None
    try:
        import urllib.request
        log.info("fetching macro %s from FRED: %s", symbol, url)
        with urllib.request.urlopen(url, timeout=30) as r:
            payload = r.read()
        df = pd.read_csv(io.BytesIO(payload), na_values=".")
        df.columns = ["date", "close"]
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df = df.set_index("date").sort_index()
        df = df.dropna(subset=["close"])
        df["open"] = df["close"]
        df["high"] = df["close"]
        df["low"]  = df["close"]
        df["volume"] = 0.0
        return _standardise(df)
    except Exception as exc:
        log.warning("FRED macro fetch failed for %s: %s", symbol, exc)
    return None


# ---------------------------------------------------------------------------
# FMP symbol mapping: Yahoo-style tickers → FMP-style tickers
# FMP uses the same Yahoo symbols for most indices, but a few differ.
# ---------------------------------------------------------------------------
_FMP_SYMBOL_MAP: Dict[str, str] = {
    "DX=F":   "DX-Y.NYB",   # Dollar index continuous -> FMP ticker
    "^VIX":   "^VIX",
    "^TNX":   "^TNX",
    "^GSPC":  "^GSPC",
    "GC=F":   "GCUSD",      # Gold spot on FMP; futures use GC
    "SI=F":   "SIUSD",
}

# FMP base URL
_FMP_BASE = "https://financialmodelingprep.com/api/v3"


def _try_fmp(
    symbol: str,
    start: str,
    end: str,
    interval: str = "1d",
    api_key: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """Fetch OHLCV from Financial Modeling Prep REST API.

    Only daily bars are reliably available for macro indices on FMP's
    free tier.  Intraday intervals are silently skipped so the caller
    falls through to the next source.

    Set FMP_API_KEY in the environment or pass api_key explicitly.
    """
    key = api_key or os.environ.get("FMP_API_KEY", "")
    if not key:
        return None

    # FMP free tier supports daily historical data; skip intraday.
    if interval not in ("1d", "daily"):
        return None

    fmp_sym = _FMP_SYMBOL_MAP.get(symbol, symbol)
    # URL-encode ^ prefix
    fmp_sym_enc = fmp_sym.replace("^", "%5E")
    url = (
        f"{_FMP_BASE}/historical-price-full/{fmp_sym_enc}"
        f"?from={start}&to={end}&apikey={key}"
    )
    try:
        import urllib.request
        import json as _json
        log.info("FMP fetch: %s -> %s", symbol, url.split("apikey=")[0] + "apikey=***")
        with urllib.request.urlopen(url, timeout=30) as r:
            payload = _json.loads(r.read())
    except Exception as exc:
        log.warning("FMP request failed for %s: %s", symbol, exc)
        return None

    historical = payload.get("historical") or payload.get("historicalStockList", [])
    if not historical:
        log.warning("FMP returned empty historical for %s", symbol)
        return None

    # historical is a list of dicts, newest-first
    try:
        df = pd.DataFrame(historical)
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df = df.set_index("date").sort_index()
        # FMP returns camelCase: adjClose etc — standardise() lowercases
        df = df.rename(columns={"adjClose": "adj_close"})
        return _standardise(df)
    except Exception as exc:
        log.warning("FMP parse failed for %s: %s", symbol, exc)
        return None


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
    fmp_api_key: Optional[str] = None,
) -> LoadResult:
    """Load OHLCV: cache → GitHub → FMP → yfinance → synthetic.

    FMP is used when FMP_API_KEY is set in the environment or fmp_api_key
    is passed explicitly.  It is the preferred source for macro series
    (DXY, VIX, TNX, SPX) because yfinance is blocked in some environments.
    """
    if fallback_symbols is None:
        fallback_symbols = []

    if cache_path and os.path.exists(cache_path) and not force_synthetic:
        log.info("loading cached OHLCV from %s", cache_path)
        df = pd.read_parquet(cache_path)
        source = str(df.attrs.get("source", "cache"))
        return LoadResult(df=df, source=source)

    if not force_synthetic:
        # 1. Known GitHub CSV sources (currently MGC 60m only)
        github_url = KNOWN_GITHUB_SOURCES.get(symbol)
        if github_url and interval.lower() in ("60m", "1h"):
            df = _try_github_csv(github_url)
            if df is not None and len(df) > 500:
                df.attrs["source"] = f"github:{symbol}"
                if cache_path:
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    df.to_parquet(cache_path)
                return LoadResult(df=df, source=f"github:{symbol}")

        # 2a. FRED direct CSV (daily, always current, no API key)
        df = _try_fred_macro(symbol)
        if df is not None and len(df) > 100:
            df.attrs["source"] = f"fred:{symbol}"
            if cache_path:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                df.to_parquet(cache_path)
            return LoadResult(df=df, source=f"fred:{symbol}")

        # 2b. GitHub open-data macro CSVs (VIX daily, SPX/TNX monthly ffill)
        df = _try_github_macro(symbol)
        if df is not None and len(df) > 100:
            df.attrs["source"] = f"github_macro:{symbol}"
            if cache_path:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                df.to_parquet(cache_path)
            return LoadResult(df=df, source=f"github_macro:{symbol}")

        # 3. FMP REST API (daily only; requires FMP_API_KEY)
        df = _try_fmp(symbol, start, end, interval, api_key=fmp_api_key)
        if df is not None and len(df) > 100:
            df.attrs["source"] = f"fmp:{symbol}"
            if cache_path:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                df.to_parquet(cache_path)
            return LoadResult(df=df, source=f"fmp:{symbol}")

        # 3. yfinance: try primary symbol then fallbacks
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


def fetch_macro_series(
    symbols: List[str],
    start: str = "2005-01-01",
    end: str = "2025-12-31",
    interval: str = "1d",
    cache_dir: str = "data/raw",
    fmp_api_key: Optional[str] = None,
    force_refresh: bool = False,
) -> Dict[str, pd.DataFrame]:
    """Fetch exogenous macro series (daily) used as auxiliary features.

    Resolution order: cached parquet → FMP (if FMP_API_KEY set) →
    yfinance → synthetic.  Pass fmp_api_key or set FMP_API_KEY env var.
    Set force_refresh=True to bypass the cache and re-fetch from source.
    """
    if not symbols:
        return {}
    key = fmp_api_key or os.environ.get("FMP_API_KEY", "") or None
    out: Dict[str, pd.DataFrame] = {}
    os.makedirs(cache_dir, exist_ok=True)
    for sym in symbols:
        safe = sym.replace("=", "").replace("^", "").replace(".", "_").replace("/", "_")
        cache_path = os.path.join(cache_dir, f"macro_{safe}.parquet")
        if force_refresh and os.path.exists(cache_path):
            os.remove(cache_path)
        res = load_ohlcv(
            symbol=sym,
            start=start,
            end=end,
            interval=interval,
            cache_path=cache_path,
            fmp_api_key=key,
        )
        df = res.df
        df.attrs["source"] = res.source
        out[sym] = df
        log.info("macro %s: %d bars, source=%s", sym, len(df), res.source)
    return out
