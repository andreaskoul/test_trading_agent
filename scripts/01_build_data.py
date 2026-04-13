"""Download OHLCV, engineer features, and compute Triple Barrier labels.

Supports multi-asset configs: loops over ``data.assets`` and builds
per-asset feature/label parquets.
"""

from __future__ import annotations

import logging
import os

import pandas as pd

from _bootstrap import setup, path

from src.data.config_utils import parse_asset_configs, scale_param
from src.data.loader import load_ohlcv
from src.data.features import build_features, feature_columns
from src.data.triple_barrier import TBConfig, label_triple_barrier


def main() -> None:
    log = logging.getLogger("build_data")
    cfg = setup()

    assets = parse_asset_configs(cfg)
    if not assets:
        raise RuntimeError("no assets defined in config (need data.assets or data.symbol)")

    for asset in assets:
        log.info("=== building data for %s ===", asset.symbol)

        raw_cache = path(cfg, asset.raw_path)
        features_path = path(cfg, asset.features_path)
        labels_path = path(cfg, asset.labels_path)

        result = load_ohlcv(
            symbol=asset.symbol,
            fallback_symbols=asset.fallback_symbols,
            start=cfg["data"]["start"],
            end=cfg["data"]["end"],
            interval=asset.interval,
            cache_path=raw_cache,
        )
        log.info("[%s] loaded %d bars from %s", asset.symbol, len(result.df), result.source)

        # Frequency-adaptive parameter scaling
        warmup = scale_param(cfg["features"]["warmup_bars"], asset.interval)
        zscore_win = scale_param(cfg["features"]["zscore_window"], asset.interval)
        horizon = scale_param(cfg["triple_barrier"]["horizon"], asset.interval)

        feats = build_features(
            result.df,
            warmup_bars=warmup,
            zscore_window=zscore_win,
        )
        log.info("[%s] features: %d bars x %d cols", asset.symbol, len(feats), feats.shape[1])

        tb_cfg = TBConfig(
            horizon=horizon,
            rr_upper=cfg["triple_barrier"]["rr_upper"],
            rr_lower=cfg["triple_barrier"]["rr_lower"],
        )
        labels = label_triple_barrier(feats, tb_cfg)
        log.info(
            "[%s] labels: +1=%d 0=%d -1=%d",
            asset.symbol,
            int((labels["label_multi"] == 1).sum()),
            int((labels["label_multi"] == 0).sum()),
            int((labels["label_multi"] == -1).sum()),
        )

        os.makedirs(os.path.dirname(features_path), exist_ok=True)
        os.makedirs(os.path.dirname(labels_path), exist_ok=True)
        feats.to_parquet(features_path)
        labels_out = labels.copy()
        labels_out["t1"] = labels_out["t1"].astype("int64")
        labels_out.to_parquet(labels_path)
        log.info("[%s] wrote features -> %s and labels -> %s", asset.symbol, features_path, labels_path)

    log.info("data build complete for %d assets", len(assets))


if __name__ == "__main__":
    main()
