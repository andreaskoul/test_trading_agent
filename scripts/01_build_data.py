"""Download OHLCV, engineer features, and compute Triple Barrier labels."""

from __future__ import annotations

import logging
import os

import pandas as pd

from _bootstrap import setup, path

from src.data.loader import load_gold
from src.data.features import build_features, feature_columns
from src.data.triple_barrier import TBConfig, label_triple_barrier


def main() -> None:
    log = logging.getLogger("build_data")
    cfg = setup()

    raw_cache = path(cfg, cfg["data"]["raw_path"])
    features_path = path(cfg, cfg["data"]["features_path"])
    labels_path = path(cfg, cfg["data"]["labels_path"])

    result = load_gold(
        symbol=cfg["data"]["symbol"],
        fallback_symbols=cfg["data"]["fallback_symbols"],
        start=cfg["data"]["start"],
        end=cfg["data"]["end"],
        interval=cfg["data"]["interval"],
        cache_path=raw_cache,
    )
    log.info("loaded %d bars from %s", len(result.df), result.source)

    feats = build_features(
        result.df,
        warmup_bars=cfg["features"]["warmup_bars"],
        zscore_window=cfg["features"]["zscore_window"],
    )
    log.info("features: %d bars x %d cols", len(feats), feats.shape[1])

    tb_cfg = TBConfig(
        horizon=cfg["triple_barrier"]["horizon"],
        rr_upper=cfg["triple_barrier"]["rr_upper"],
        rr_lower=cfg["triple_barrier"]["rr_lower"],
    )
    labels = label_triple_barrier(feats, tb_cfg)
    log.info(
        "labels: +1=%d 0=%d -1=%d",
        int((labels["label_multi"] == 1).sum()),
        int((labels["label_multi"] == 0).sum()),
        int((labels["label_multi"] == -1).sum()),
    )

    os.makedirs(os.path.dirname(features_path), exist_ok=True)
    os.makedirs(os.path.dirname(labels_path), exist_ok=True)
    feats.to_parquet(features_path)
    # parquet can't serialise arbitrary object dtype timestamps directly;
    # convert `t1` to int64 nanoseconds for safe round-tripping.
    labels_out = labels.copy()
    labels_out["t1"] = labels_out["t1"].astype("int64")
    labels_out.to_parquet(labels_path)
    log.info("wrote features -> %s and labels -> %s", features_path, labels_path)


if __name__ == "__main__":
    main()
