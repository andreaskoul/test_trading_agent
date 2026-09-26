"""Build training and OOS feature/label parquets for the extended corpus.

Training set : data/raw/gold_xauusd_h1.parquet  2012-05-17 → 2022-03-04
OOS set      : data/raw/gc_60m.parquet           2023-01-02 → 2026-03-24

Outputs (all in data/processed/):
  features_gc_extended.parquet         training features  (~42 k bars after warmup)
  labels_gc_extended.parquet           training labels
  features_gc_extended_holdout.parquet OOS features        (~18 k bars after warmup)
  labels_gc_extended_holdout.parquet   OOS labels

Run:
    python scripts/build_extended_data.py [--force-macro-refresh]

The script is self-contained: it does NOT require TRADING_PROFILE to be set.
After running, set TRADING_PROFILE=extended to use the extended corpus in
all downstream scripts (03_train_ppo.py, 04_evaluate.py, 04b_holdout_eval.py).
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
import urllib.request

import numpy as np
import pandas as pd

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.data.config_utils import scale_param
from src.data.features import PASSTHROUGH, build_features, feature_columns
from src.data.feature_selection import mi_filter
from src.data.triple_barrier import TBConfig, label_triple_barrier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_extended")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RAW_DIR  = os.path.join(_REPO_ROOT, "data", "raw")
PROC_DIR = os.path.join(_REPO_ROOT, "data", "processed")

TRAIN_RAW  = os.path.join(RAW_DIR, "gold_xauusd_h1.parquet")   # 2012-2022 spot
OOS_RAW    = os.path.join(RAW_DIR, "gc_60m.parquet")            # 2023-2026 futures

TRAIN_FEATS  = os.path.join(PROC_DIR, "features_gc_extended.parquet")
TRAIN_LABELS = os.path.join(PROC_DIR, "labels_gc_extended.parquet")
OOS_FEATS    = os.path.join(PROC_DIR, "features_gc_extended_holdout.parquet")
OOS_LABELS   = os.path.join(PROC_DIR, "labels_gc_extended_holdout.parquet")

# ---------------------------------------------------------------------------
# Feature / label parameters (mirrors aggressive.yaml at 60m)
# ---------------------------------------------------------------------------
INTERVAL    = "60m"
WARMUP      = scale_param(252, INTERVAL)   # ~1638 bars
ZSCORE_WIN  = scale_param(252, INTERVAL)
HORIZON     = scale_param(4,   INTERVAL)
ATR_WINDOW  = scale_param(4,   INTERVAL)
MI_THRESHOLD = 0.003

TB_CFG = TBConfig(horizon=HORIZON, rr_upper=1.5, rr_lower=0.75)

# ---------------------------------------------------------------------------
# Macro series loading
# ---------------------------------------------------------------------------
# FRED direct CSV — covers the full 2012-2026 window.
_FRED = {
    "^VIX":  "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS",
    "^TNX":  "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
    "DX=F":  "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS",
}

# GitHub monthly S&P 500 (back to 1871) for pre-2016 coverage.
_GSPC_GITHUB = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500/master/data/data.csv"
)
# FRED daily S&P 500 (2016-present) for recent high-resolution data.
_GSPC_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500"


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def _load_fred_series(url: str) -> pd.Series:
    """Return a UTC-indexed daily float Series from a 2-column FRED CSV."""
    df = pd.read_csv(io.BytesIO(_fetch(url)), na_values=".")
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.set_index("date").sort_index().dropna()
    return df["value"]


def _build_macro(force_refresh: bool) -> dict[str, pd.DataFrame]:
    """Load all 4 macro series as OHLCV DataFrames keyed by symbol.

    ^GSPC combines GitHub monthly (pre-2016) + FRED daily (2016+) so the
    feature builder has coverage across the full 2012-2026 window.
    """
    macro: dict[str, pd.DataFrame] = {}
    cache_paths = {
        "^VIX":  os.path.join(RAW_DIR, "macro_VIX.parquet"),
        "^TNX":  os.path.join(RAW_DIR, "macro_TNX.parquet"),
        "DX=F":  os.path.join(RAW_DIR, "macro_DXF.parquet"),
        "^GSPC": os.path.join(RAW_DIR, "macro_GSPC.parquet"),
    }

    def _to_ohlcv(s: pd.Series) -> pd.DataFrame:
        df = s.rename("close").to_frame()
        df["open"] = df["close"]
        df["high"] = df["close"]
        df["low"]  = df["close"]
        df["volume"] = 0.0
        return df[["open", "high", "low", "close", "volume"]]

    # VIX, TNX, DXY — FRED covers full window, use cache unless force_refresh.
    for sym, url in _FRED.items():
        cpath = cache_paths[sym]
        if not force_refresh and os.path.exists(cpath):
            log.info("macro %s: loading from cache %s", sym, cpath)
            macro[sym] = pd.read_parquet(cpath)
        else:
            log.info("macro %s: fetching from FRED", sym)
            try:
                s = _load_fred_series(url)
                macro[sym] = _to_ohlcv(s)
                macro[sym].to_parquet(cpath)
                log.info("macro %s: %d rows %s → %s",
                         sym, len(s), s.index[0].date(), s.index[-1].date())
            except Exception as exc:
                log.warning("macro %s: FRED fetch failed (%s), using cache", sym, exc)
                if os.path.exists(cpath):
                    macro[sym] = pd.read_parquet(cpath)

    # ^GSPC: daily closes from Yahoo. The previous cache spliced the GitHub
    # s-and-p-500 *monthly average* (stamped on the 1st, forward-filled) in
    # front of FRED SP500: for 2012-2015 every bar saw the average of the
    # month it was in, i.e. up to a month of look-ahead. FRED SP500 only
    # covers the last 10 years, so Yahoo is the daily source for the span.
    gspc_path = cache_paths["^GSPC"]
    cached = pd.read_parquet(gspc_path) if os.path.exists(gspc_path) else None
    daily_ok = (cached is not None and len(cached) > 0 and
                cached.loc["2013-01-02":"2013-01-31", "close"].nunique() > 5)
    if force_refresh or not daily_ok:
        import yfinance as yf
        raw = yf.download("^GSPC", start="2005-01-01", interval="1d",
                          progress=False, auto_adjust=False, threads=False)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        s_ = raw["Close"].dropna()
        s_.index = pd.to_datetime(s_.index, utc=True)
        macro["^GSPC"] = _to_ohlcv(s_)
        macro["^GSPC"].to_parquet(gspc_path)
        log.info("macro ^GSPC: %d daily rows from Yahoo %s -> %s", len(s_),
                 s_.index[0].date(), s_.index[-1].date())
    else:
        macro["^GSPC"] = cached

    return macro


# ---------------------------------------------------------------------------
# Feature + label building
# ---------------------------------------------------------------------------
def _build_features_labels(
    raw: pd.DataFrame,
    macro: dict[str, pd.DataFrame],
    name: str,
    kept_cols_override: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    log.info("[%s] building features (%d raw bars)…", name, len(raw))
    feats = build_features(raw, warmup_bars=WARMUP, zscore_window=ZSCORE_WIN,
                           macro_data=macro or None)
    log.info("[%s] features before MI: %d bars × %d cols", name, len(feats), feats.shape[1])

    if kept_cols_override is not None:
        # Use the same columns as training — do NOT re-run MI on OOS data.
        available = [c for c in kept_cols_override if c in feats.columns]
        missing = [c for c in kept_cols_override if c not in feats.columns]
        if missing:
            log.warning("[%s] %d training cols absent from OOS features: %s", name, len(missing), missing)
        feats = feats[available]
        log.info("[%s] applied training feature set: %d cols", name, len(available))
    else:
        # MI prune (same threshold as aggressive.yaml)
        drop_cols = [c for c in PASSTHROUGH if c in feats.columns]
        y_mi = label_triple_barrier(feats, TB_CFG)["label_multi"].to_numpy().astype(int) + 1
        kept, _ = mi_filter(
            feats.drop(columns=drop_cols, errors="ignore"),
            y_mi,
            threshold=MI_THRESHOLD,
        )
        kept_cols = list(dict.fromkeys(list(kept) + drop_cols))
        dropped = [c for c in feats.columns if c not in kept_cols]
        if dropped:
            log.info("[%s] MI pruned %d cols: %s", name, len(dropped), dropped)
        feats = feats[kept_cols]

    labels = label_triple_barrier(feats, TB_CFG)
    labels["t1"] = labels["t1"].astype("int64")
    log.info("[%s] labels: +1=%d  0=%d  -1=%d",
             name,
             int((labels["label_multi"] == 1).sum()),
             int((labels["label_multi"] == 0).sum()),
             int((labels["label_multi"] == -1).sum()))
    return feats, labels


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------
def _print_summary(
    train_feats: pd.DataFrame, train_labels: pd.DataFrame,
    oos_feats: pd.DataFrame,   oos_labels: pd.DataFrame,
) -> None:
    sep = "=" * 64
    print(sep)
    print("EXTENDED CORPUS BUILD SUMMARY")
    print(sep)

    def _stats(feats: pd.DataFrame, labels: pd.DataFrame, tag: str) -> None:
        rets = feats["close"].pct_change().dropna()
        n = len(feats)
        n_trades = int((labels["label_multi"] != 0).sum())
        n_long   = int((labels["label_multi"] == 1).sum())
        n_short  = int((labels["label_multi"] == -1).sum())
        n_flat   = int((labels["label_multi"] == 0).sum())
        years = (feats.index[-1] - feats.index[0]).days / 365.25
        print(f"\n{tag}")
        print(f"  Date range : {feats.index[0].date()} → {feats.index[-1].date()}")
        print(f"  Bars       : {n:,}  (~{years:.1f} years)")
        print(f"  Features   : {feats.shape[1]} cols")
        print(f"  Labels     : long={n_long}  short={n_short}  flat={n_flat}  "
              f"signal_rate={n_trades/n:.1%}")
        ann_vol = rets.std() * np.sqrt(6_240)   # ~6240 hourly bars/year
        print(f"  Ann. vol   : {ann_vol:.1%}")

    _stats(train_feats, train_labels, "TRAINING (2012-2022, XAUUSD spot)")
    _stats(oos_feats,   oos_labels,   "OOS      (2023-2026, GC=F futures)")
    print(f"\n  Train/OOS bar ratio : {len(train_feats) / max(len(oos_feats), 1):.1f}×")
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Build extended training + OOS datasets")
    parser.add_argument("--force-macro-refresh", action="store_true",
                        help="re-fetch all macro series from source even if cached")
    parser.add_argument("--reselect", action="store_true",
                        help="re-run MI feature selection instead of keeping the current schema")
    args = parser.parse_args()

    os.makedirs(PROC_DIR, exist_ok=True)

    # 1. Macro series (shared between train and OOS)
    macro = _build_macro(force_refresh=args.force_macro_refresh)

    # 2. Training set — XAUUSD spot hourly 2012-2022
    log.info("loading training raw: %s", TRAIN_RAW)
    train_raw = pd.read_parquet(TRAIN_RAW)
    # Keep the column set the encoders/policies were trained on unless asked
    # to re-run MI selection (MI on the old, leaky macros picked this set).
    schema = None
    if not args.reselect and os.path.exists(TRAIN_FEATS):
        from src.data.features import feature_columns as _fc
        schema = _fc(pd.read_parquet(TRAIN_FEATS)) + list(PASSTHROUGH)
        log.info("keeping existing %d-feature schema", len(schema) - len(PASSTHROUGH))
    train_feats, train_labels = _build_features_labels(train_raw, macro, "TRAIN",
                                                       kept_cols_override=schema)
    train_feats.to_parquet(TRAIN_FEATS)
    train_labels.to_parquet(TRAIN_LABELS)
    log.info("wrote %s  (%d bars)", TRAIN_FEATS, len(train_feats))
    log.info("wrote %s  (%d bars)", TRAIN_LABELS, len(train_labels))

    # 3. OOS set — GC=F 60m 2023-2026 (full, no further split)
    # Use the exact feature columns selected for training to avoid dimension mismatch.
    from src.data.features import feature_columns as _feat_cols
    train_kept = list(train_feats.columns)
    log.info("loading OOS raw: %s", OOS_RAW)
    oos_raw = pd.read_parquet(OOS_RAW)
    oos_feats, oos_labels = _build_features_labels(oos_raw, macro, "OOS",
                                                   kept_cols_override=train_kept)
    oos_feats.to_parquet(OOS_FEATS)
    oos_labels.to_parquet(OOS_LABELS)
    log.info("wrote %s  (%d bars)", OOS_FEATS, len(oos_feats))
    log.info("wrote %s  (%d bars)", OOS_LABELS, len(oos_labels))

    # 4. Summary
    _print_summary(train_feats, train_labels, oos_feats, oos_labels)


if __name__ == "__main__":
    main()
