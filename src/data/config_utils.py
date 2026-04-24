"""Multi-asset configuration helpers.

Provides backward-compatible parsing of the config YAML so that
existing single-asset configs (``data.symbol``) still work, while new
multi-asset configs (``data.assets``) are supported natively.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Frequency-adaptive scaling
# ---------------------------------------------------------------------------
# Base assumptions: all "base" params (warmup_bars, zscore_window, horizon)
# are calibrated for daily bars.  When the bar frequency changes, multiply
# by this factor so the effective lookback in *calendar time* stays constant.

_FREQ_MULTIPLIERS = {
    "1d": 1.0,
    "4h": 1.625,     # ~6.5h trading day / 4h
    "240m": 1.625,
    "1h": 6.5,       # 6.5 hourly bars per trading day
    "60m": 6.5,
    "30m": 13.0,
    "15m": 26.0,
    "5m": 78.0,
    "1m": 390.0,
}


def freq_multiplier(interval: str) -> float:
    """Return the bar-count multiplier for a given frequency relative to daily."""
    m = _FREQ_MULTIPLIERS.get(interval.lower())
    if m is not None:
        return m
    log.warning("unknown interval %r, assuming daily (multiplier=1.0)", interval)
    return 1.0


def scale_param(base_value: int, interval: str) -> int:
    """Scale an integer parameter (warmup, horizon, etc.) by freq multiplier."""
    return max(1, int(math.ceil(base_value * freq_multiplier(interval))))


# ---------------------------------------------------------------------------
# Asset config dataclass
# ---------------------------------------------------------------------------

@dataclass
class AssetConfig:
    symbol: str
    fallback_symbols: List[str] = field(default_factory=list)
    interval: str = "1d"
    raw_path: str = ""
    features_path: str = ""
    labels_path: str = ""


def parse_asset_configs(cfg: dict) -> List[AssetConfig]:
    """Extract a list of ``AssetConfig`` from the top-level config dict.

    Supports two formats:

    **New format** (multi-asset)::

        data:
          assets:
            - symbol: "GC=F"
              ...
            - symbol: "SI=F"
              ...

    **Legacy format** (single-asset, backward-compatible)::

        data:
          symbol: "GC=F"
          raw_path: "data/raw/gold.parquet"
          features_path: "data/processed/features.parquet"
          labels_path: "data/processed/labels.parquet"
    """
    data = cfg.get("data", {})
    assets_raw = data.get("assets")

    if assets_raw:
        out: list[AssetConfig] = []
        for a in assets_raw:
            out.append(AssetConfig(
                symbol=a["symbol"],
                fallback_symbols=a.get("fallback_symbols", []),
                interval=a.get("interval", data.get("interval", "1d")),
                raw_path=a.get("raw_path", ""),
                features_path=a.get("features_path", ""),
                labels_path=a.get("labels_path", ""),
            ))
        return out

    # Legacy single-asset fallback
    if "symbol" in data:
        return [AssetConfig(
            symbol=data["symbol"],
            fallback_symbols=data.get("fallback_symbols", []),
            interval=data.get("interval", "1d"),
            raw_path=data.get("raw_path", ""),
            features_path=data.get("features_path", ""),
            labels_path=data.get("labels_path", ""),
        )]

    return []
