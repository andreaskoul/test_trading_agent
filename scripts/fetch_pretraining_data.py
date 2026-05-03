"""Fetch pre-training historical OHLCV from Stooq for backtest windows (Phase R).

Why a dedicated fetcher? yfinance hourly bars are capped at ~730 days
from today, which no longer reaches before training-start (2023-07-17).
Stooq.com publishes free CSV downloads of continuous-future gold (gc.f)
back to ~2007 at hourly resolution — no signup, no API key. This script
turns that into a parquet drop-in for the existing build_features
pipeline.

Usage::

    python scripts/fetch_pretraining_data.py
    python scripts/fetch_pretraining_data.py --source file --file-path /tmp/my.parquet
    python scripts/fetch_pretraining_data.py --asset GC=F --interval 60m

Output: ``data/raw/gold_pretraining.parquet`` with the same columns as
``data/raw/gold.parquet`` (open/high/low/close/volume, UTC DatetimeIndex).
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
import urllib.request

import pandas as pd

from _bootstrap import path, setup

log = logging.getLogger("fetch_pretraining_data")


# Stooq's continuous-future symbol map. Lowercase, suffixed with .f
# (futures continuous). See https://stooq.com/q/?s=gc.f
_STOOQ_SYMBOLS = {
    "GC=F": "gc.f",
    "SI=F": "si.f",
    "CL=F": "cl.f",
    "GLD": "gld.us",
}

_STOOQ_INTERVAL = {"60m": "h", "1h": "h", "1d": "d"}


def _stooq_url(symbol: str, interval: str) -> str:
    stq_sym = _STOOQ_SYMBOLS.get(symbol)
    if stq_sym is None:
        raise ValueError(
            f"no Stooq mapping for {symbol!r}; add it to _STOOQ_SYMBOLS"
        )
    stq_int = _STOOQ_INTERVAL.get(interval, "h")
    return f"https://stooq.com/q/d/l/?s={stq_sym}&i={stq_int}"


def _fetch_stooq(symbol: str, interval: str, timeout: float = 30.0) -> pd.DataFrame:
    """Download the full available history for ``symbol`` from Stooq.

    Stooq returns a CSV with header ``Date,Time,Open,High,Low,Close,Volume``
    for hourly bars (Time column is HH:MM:SS UTC) and ``Date,Open,High,
    Low,Close,Volume`` for daily. We coerce both to the standard layout.
    """
    url = _stooq_url(symbol, interval)
    log.info("fetching %s (%s) from Stooq: %s", symbol, interval, url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    if not body.strip():
        raise RuntimeError("Stooq returned an empty response (rate-limited?)")
    if body.startswith("No data") or "<html" in body[:200].lower():
        raise RuntimeError(f"Stooq returned non-CSV response: {body[:200]!r}")
    df = pd.read_csv(io.StringIO(body))
    # Normalise to standard columns + UTC DatetimeIndex.
    if "Time" in df.columns:
        ts = pd.to_datetime(df["Date"] + " " + df["Time"], utc=True)
    else:
        ts = pd.to_datetime(df["Date"], utc=True)
    df.index = ts
    keep = {"Open": "open", "High": "high", "Low": "low",
             "Close": "close", "Volume": "volume"}
    df = df.rename(columns=keep)[list(keep.values())]
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def _load_from_file(file_path: str) -> pd.DataFrame:
    """Load OHLCV from a user-supplied parquet/CSV. Same normalisation."""
    if file_path.endswith(".parquet"):
        df = pd.read_parquet(file_path)
    else:
        df = pd.read_csv(file_path)
    # Find a timestamp column or assume the index is one.
    if not isinstance(df.index, pd.DatetimeIndex):
        for col in ("ts", "timestamp", "datetime", "date", "Date"):
            if col in df.columns:
                df.index = pd.to_datetime(df[col], utc=True)
                df = df.drop(columns=[col])
                break
        else:
            raise ValueError(
                f"{file_path}: no datetime index or recognised timestamp column"
            )
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.columns = [c.lower() for c in df.columns]
    needed = ["open", "high", "low", "close", "volume"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"{file_path}: missing columns {missing}")
    return df[needed].sort_index()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", default="GC=F")
    parser.add_argument("--interval", default="60m")
    parser.add_argument("--source", default="stooq", choices=["stooq", "file"])
    parser.add_argument("--file-path", default="",
                        help="parquet or CSV when --source=file")
    parser.add_argument("--out", default="data/raw/gold_pretraining.parquet")
    args = parser.parse_args()

    cfg = setup()

    if args.source == "stooq":
        try:
            df = _fetch_stooq(args.asset, args.interval)
        except Exception as exc:
            log.error("Stooq fetch failed: %s", exc)
            return 2
    else:
        if not args.file_path:
            log.error("--source file requires --file-path")
            return 2
        try:
            df = _load_from_file(args.file_path)
        except Exception as exc:
            log.error("file load failed: %s", exc)
            return 2

    if len(df) == 0:
        log.error("0 rows after parsing")
        return 2

    out_path = path(cfg, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_parquet(out_path)
    log.info("wrote %s: %d bars (%s -> %s)",
             out_path, len(df), df.index[0].isoformat(), df.index[-1].isoformat())
    return 0


if __name__ == "__main__":
    sys.exit(main())
