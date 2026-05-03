"""Fetch a long historical OHLCV corpus for the trading agent (Phase S).

Extends ``scripts/fetch_pretraining_data.py`` to handle:

  * Configurable date range (default 2016-01-01 → today).
  * Both the trading asset (60m gold) and macro series (daily VIX/GSPC/TNX).
  * Stooq as primary source for hourly gold; yfinance fallback for macros
    (and as a sanity check on daily gold if Stooq disappoints).

Designed to run from a GitHub Actions runner (sandbox can't reach Stooq;
runner's IP space typically can). On success it writes parquets to
``data/raw/`` ready to be picked up by ``scripts/01_build_data.py``
after a config update — see ``docs/retraining.md`` for the post-fetch
flow.

Usage::

    python scripts/fetch_historical_data.py \\
        --start 2016-01-01 --interval 60m \\
        --asset GC=F --macros VIX,GSPC,TNX

Output:
  * data/raw/gold_60m_historical.parquet  (Stooq if 60m, yfinance fallback)
  * data/raw/macro_VIX.parquet, macro_GSPC.parquet, macro_TNX.parquet
    (overwrites — longer history is strictly better)
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
import urllib.request
from datetime import datetime, timezone

import pandas as pd

from _bootstrap import path, setup

# Reuse the Stooq helpers from the Phase R fetcher (DRY).
from fetch_pretraining_data import (   # noqa: E402  (script-style import)
    _STOOQ_SYMBOLS,
    _STOOQ_INTERVAL,
    _load_from_file,
)

log = logging.getLogger("fetch_historical_data")


def _stooq_url(symbol: str, interval: str,
                start: str = "", end: str = "") -> str:
    """Stooq URL with optional date range. Format: YYYYMMDD."""
    stq_sym = _STOOQ_SYMBOLS.get(symbol)
    if stq_sym is None:
        raise ValueError(f"no Stooq mapping for {symbol!r}; add it to _STOOQ_SYMBOLS")
    stq_int = _STOOQ_INTERVAL.get(interval, "h")
    url = f"https://stooq.com/q/d/l/?s={stq_sym}&i={stq_int}"
    if start:
        url += f"&d1={start.replace('-', '')}"
    if end:
        url += f"&d2={end.replace('-', '')}"
    return url


def _fetch_stooq(
    symbol: str, interval: str, start: str = "", end: str = "",
    timeout: float = 60.0,
) -> pd.DataFrame:
    """Download a date-bounded OHLCV slice from Stooq."""
    url = _stooq_url(symbol, interval, start=start, end=end)
    log.info("fetching %s (%s) from Stooq [%s -> %s]", symbol, interval, start, end)
    log.debug("url: %s", url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    if not body.strip():
        raise RuntimeError("Stooq returned an empty response (rate-limited?)")
    if body.startswith("No data") or "<html" in body[:200].lower():
        raise RuntimeError(f"Stooq non-CSV response: {body[:200]!r}")
    df = pd.read_csv(io.StringIO(body))
    if "Time" in df.columns:
        ts = pd.to_datetime(df["Date"] + " " + df["Time"], utc=True)
    else:
        ts = pd.to_datetime(df["Date"], utc=True)
    df.index = ts
    cols = {"Open": "open", "High": "high", "Low": "low",
             "Close": "close", "Volume": "volume"}
    df = df.rename(columns=cols)[list(cols.values())]
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def _fetch_yfinance(
    symbol: str, start: str, end: str, interval: str,
) -> pd.DataFrame:
    """Yahoo Finance fallback. Required for macros (Stooq doesn't have ^VIX
    in a stable format) and as a backup when Stooq fails for the asset."""
    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError("yfinance not installed")
    log.info("fetching %s (%s) from yfinance [%s -> %s]", symbol, interval, start, end)
    raw = yf.download(symbol, start=start, end=end, interval=interval,
                      progress=False, auto_adjust=False, threads=False)
    if raw is None or len(raw) == 0:
        raise RuntimeError(f"yfinance returned empty for {symbol}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.rename(columns={"Open": "open", "High": "high", "Low": "low",
                                "Close": "close", "Volume": "volume"})
    keep = [c for c in ("open", "high", "low", "close", "volume") if c in raw.columns]
    raw = raw[keep].copy()
    if not isinstance(raw.index, pd.DatetimeIndex):
        raw.index = pd.to_datetime(raw.index, utc=True)
    elif raw.index.tz is None:
        raw.index = raw.index.tz_localize("UTC")
    else:
        raw.index = raw.index.tz_convert("UTC")
    raw = raw.sort_index()
    raw = raw[~raw.index.duplicated(keep="last")]
    return raw


def _slice(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Trim to [start, end] (both inclusive)."""
    if start:
        df = df[df.index >= pd.Timestamp(start, tz="UTC")]
    if end:
        df = df[df.index <= pd.Timestamp(end, tz="UTC")]
    return df


def _fetch_asset(
    symbol: str, interval: str, start: str, end: str, source: str,
) -> pd.DataFrame:
    """Fetch the trading asset's OHLCV. ``source=auto`` tries Stooq for 60m,
    falls back to yfinance on failure."""
    errors: list[str] = []
    if source in ("auto", "stooq"):
        try:
            df = _fetch_stooq(symbol, interval, start=start, end=end)
            if len(df) > 0:
                return _slice(df, start, end)
            errors.append("stooq: 0 rows")
        except Exception as exc:
            errors.append(f"stooq: {exc}")
    if source in ("auto", "yfinance"):
        try:
            df = _fetch_yfinance(symbol, start=start, end=end, interval=interval)
            return _slice(df, start, end)
        except Exception as exc:
            errors.append(f"yfinance: {exc}")
    raise RuntimeError(f"all sources failed for {symbol}: {errors}")


def _fetch_macro(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Daily macro from yfinance. Stooq has these but in a less consistent
    format; yfinance daily history is reliable back decades."""
    return _fetch_yfinance(symbol, start=start, end=end, interval="1d")


def _safe_filename(symbol: str) -> str:
    return symbol.replace("=", "").replace("^", "").replace(".", "_").replace("/", "_")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", default="GC=F")
    parser.add_argument("--interval", default="60m")
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default="",
                        help="empty = today (UTC)")
    parser.add_argument("--macros", default="VIX,GSPC,TNX",
                        help="comma-separated yfinance symbols WITHOUT ^ prefix")
    parser.add_argument("--source", default="auto",
                        choices=["auto", "stooq", "yfinance", "file"])
    parser.add_argument("--file-path", default="",
                        help="parquet/CSV when --source=file (asset only)")
    parser.add_argument("--out-dir", default="data/raw")
    parser.add_argument("--name-suffix", default="_historical",
                        help="appended to the asset filename to avoid clobbering "
                             "the existing gc_60m.parquet")
    args = parser.parse_args()

    cfg = setup()
    out_dir = path(cfg, args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    if not args.end:
        args.end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log.info("range: %s -> %s | source=%s | interval=%s",
             args.start, args.end, args.source, args.interval)

    # ---- asset ----
    if args.source == "file":
        if not args.file_path:
            log.error("--source file requires --file-path")
            return 2
        try:
            asset_df = _slice(_load_from_file(args.file_path), args.start, args.end)
        except Exception as exc:
            log.error("file load failed: %s", exc)
            return 2
    else:
        try:
            asset_df = _fetch_asset(args.asset, args.interval,
                                      args.start, args.end, args.source)
        except Exception as exc:
            log.error("asset fetch failed: %s", exc)
            return 2

    if len(asset_df) == 0:
        log.error("asset DataFrame is empty after fetch+slice")
        return 2

    # Filename: gc_60m_historical.parquet (default) or stooq-style.
    asset_safe = _safe_filename(args.asset).lower()
    asset_name = f"{asset_safe}_{args.interval}{args.name_suffix}.parquet"
    asset_out = os.path.join(out_dir, asset_name)
    asset_df.to_parquet(asset_out)
    log.info("wrote %s: %d bars [%s -> %s]",
             asset_out, len(asset_df),
             asset_df.index[0].isoformat(), asset_df.index[-1].isoformat())

    # ---- macros ----
    macro_list = [s.strip() for s in args.macros.split(",") if s.strip()]
    n_macro_ok = 0
    for sym in macro_list:
        # yfinance uses ^VIX / ^GSPC / ^TNX. User passes bare symbols; we
        # add the caret. Pass-through anything that already has it.
        ysym = sym if sym.startswith("^") else f"^{sym}"
        try:
            mdf = _fetch_macro(ysym, args.start, args.end)
        except Exception as exc:
            log.warning("macro %s failed: %s", sym, exc)
            continue
        macro_out = os.path.join(out_dir, f"macro_{_safe_filename(ysym)}.parquet")
        mdf.to_parquet(macro_out)
        log.info("wrote %s: %d bars [%s -> %s]",
                 macro_out, len(mdf),
                 mdf.index[0].isoformat(), mdf.index[-1].isoformat())
        n_macro_ok += 1

    log.info("done: 1 asset + %d/%d macros written to %s",
             n_macro_ok, len(macro_list), out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
