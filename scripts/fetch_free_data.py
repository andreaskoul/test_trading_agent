"""Download free historical data and save to data/raw/.

Sources
-------
Gold spot hourly 2012-2022  ejtraderLabs/historical-data (GitHub raw CSV)
VIX daily 1990-present      FRED VIXCLS
10Y Treasury daily 1962-now FRED DGS10
DXY (broad) daily 2006-now  FRED DTWEXBGS
S&P 500 daily 2016-now      FRED SP500

Run
---
    python scripts/fetch_free_data.py [--out-dir data/raw]
"""

from __future__ import annotations

import argparse
import io
import logging
import urllib.request
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source URLs
# ---------------------------------------------------------------------------
XAUUSD_H1_URL = (
    "https://raw.githubusercontent.com/ejtraderLabs/historical-data/"
    "main/XAUUSD/XAUUSDh1.csv"
)

FRED_SERIES = {
    "macro_VIX.parquet":  ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS",  "VIXCLS"),
    "macro_TNX.parquet":  ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",   "DGS10"),
    "macro_DXF.parquet":  ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS","DTWEXBGS"),
    "macro_GSPC.parquet": ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500",   "SP500"),
}


def _fetch(url: str, timeout: int = 60) -> bytes:
    log.info("fetching %s", url)
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


# ---------------------------------------------------------------------------
# Gold hourly
# ---------------------------------------------------------------------------
def fetch_gold_hourly(out_dir: Path) -> None:
    """Download ejtraderLabs XAUUSD H1 and save as gold_xauusd_h1.parquet.

    Prices in the source are scaled ×100 (MetaTrader fractional-pips format).
    Dividing by 100 gives USD/oz, matching the existing gc_60m.parquet scale.
    Date range: 2012-05-17 → 2022-03-04 (~57 k bars).
    """
    payload = _fetch(XAUUSD_H1_URL)
    df = pd.read_csv(io.BytesIO(payload))
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={"date": "timestamp", "tick_volume": "volume"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    # Undo MetaTrader ×100 price scaling
    for col in ("open", "high", "low", "close"):
        df[col] = df[col] / 100.0

    df.index.name = "date"
    out = out_dir / "gold_xauusd_h1.parquet"
    df.to_parquet(out)
    log.info("saved %s  (%d rows, %s → %s)",
             out, len(df), df.index[0].date(), df.index[-1].date())


# ---------------------------------------------------------------------------
# FRED macro series
# ---------------------------------------------------------------------------
def fetch_fred_series(out_dir: Path) -> None:
    """Download four FRED series and save as OHLCV parquets.

    FRED CSV format: observation_date,<SERIES_ID>
    Missing values are encoded as '.' and dropped.
    """
    for filename, (url, series_id) in FRED_SERIES.items():
        try:
            payload = _fetch(url)
            df = pd.read_csv(io.BytesIO(payload), na_values=".")
            df.columns = ["date", "close"]
            df["date"] = pd.to_datetime(df["date"], utc=True)
            df = df.set_index("date").sort_index()
            df = df.dropna(subset=["close"])
            df["open"] = df["close"]
            df["high"] = df["close"]
            df["low"]  = df["close"]
            df["volume"] = 0.0
            df = df[["open", "high", "low", "close", "volume"]]
            out = out_dir / filename
            df.to_parquet(out)
            log.info("saved %s  (%d rows, %s → %s, series=%s)",
                     out, len(df), df.index[0].date(), df.index[-1].date(), series_id)
        except Exception as exc:
            log.error("failed to fetch %s (%s): %s", filename, series_id, exc)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch free historical data")
    parser.add_argument("--out-dir", default="data/raw", help="output directory")
    parser.add_argument("--gold-only", action="store_true", help="only fetch gold hourly")
    parser.add_argument("--macro-only", action="store_true", help="only fetch macro series")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.macro_only:
        fetch_gold_hourly(out_dir)
    if not args.gold_only:
        fetch_fred_series(out_dir)


if __name__ == "__main__":
    main()
