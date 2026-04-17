"""Pretrain an xLSTM-lite encoder per CPCV training fold.

Shared encoder: when multiple assets are configured, each encoder group
is pretrained on **concatenated** features from all assets so the encoder
learns universal temporal patterns (volatility clustering, trend momentum,
mean-reversion) across instruments.
"""

from __future__ import annotations

import argparse
import logging
import os

import numpy as np
import pandas as pd

from _bootstrap import setup, path

from src.data.config_utils import parse_asset_configs
from src.data.features import feature_columns
from src.training.pretrain_encoder import PretrainConfig, pretrain_fold, save_encoder
from src.validation.cpcv import CombinatorialPurgedKFold, _group_bounds, _purge_train, _embargo


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="Use a reduced training budget")
    args = ap.parse_args()

    log = logging.getLogger("pretrain")
    cfg = setup()

    assets = parse_asset_configs(cfg)

    # Load per-asset features and labels
    asset_features: list[pd.DataFrame] = []
    asset_labels: list[pd.DataFrame] = []
    for asset in assets:
        feats = pd.read_parquet(path(cfg, asset.features_path))
        labels = pd.read_parquet(path(cfg, asset.labels_path))
        labels["t1"] = pd.to_datetime(labels["t1"], utc=True)
        asset_features.append(feats)
        asset_labels.append(labels)
        log.info("[%s] loaded %d bars", asset.symbol, len(feats))

    # Use the first asset to determine feature columns (all assets share
    # the same feature set since build_features is asset-agnostic).
    feat_cols = feature_columns(asset_features[0])
    log.info("feature columns: %d", len(feat_cols))

    n_splits = cfg["cpcv"]["n_splits"]
    embargo_pct = cfg["cpcv"]["embargo_pct"]

    epochs = cfg["encoder"]["pretrain_epochs"]
    if args.fast:
        epochs = max(1, epochs // 2)

    pcfg = PretrainConfig(
        seq_len=cfg["features"]["seq_len"],
        hidden_size=cfg["encoder"]["hidden_size"],
        n_slstm=cfg["encoder"]["n_slstm"],
        n_mlstm=cfg["encoder"]["n_mlstm"],
        dropout=cfg["encoder"]["dropout"],
        softcap=cfg["encoder"]["softcap"],
        focal_gamma=cfg["encoder"]["focal_gamma"],
        lr=cfg["encoder"]["pretrain_lr"],
        epochs=epochs,
        batch_size=cfg["encoder"]["pretrain_batch"],
        device="cpu",
        vib=bool(cfg["encoder"].get("vib", False)),
        vib_beta=float(cfg["encoder"].get("vib_beta", 1e-3)),
        tft=bool(cfg["encoder"].get("tft", False)),
        tft_heads=int(cfg["encoder"].get("tft_heads", 4)),
    )

    artefacts = path(cfg, cfg["artefact_dir"], "encoders")
    os.makedirs(artefacts, exist_ok=True)

    # Pretrain one encoder per CPCV group. For each group g, the training
    # set is all bars NOT in group g (with purge+embargo), concatenated
    # across all assets.
    for g in range(n_splits):
        all_train_feats: list[np.ndarray] = []
        all_train_labels: list[np.ndarray] = []
        all_val_feats: list[np.ndarray] = []
        all_val_labels: list[np.ndarray] = []

        for a_idx, (feats, labels) in enumerate(zip(asset_features, asset_labels)):
            n = len(feats)
            groups = _group_bounds(n, n_splits)
            lo, hi = groups[g]
            test_idx = np.arange(lo, hi)
            train_candidates = np.setdiff1d(np.arange(n), test_idx)

            t1_series = pd.Series(labels["t1"].values, index=feats.index)
            tr = _purge_train(train_candidates, test_idx, t1_series)
            tr = _embargo(tr, [(lo, hi)], int(embargo_pct * n), n)

            val_size = int(len(tr) * 0.1)
            val_idx = tr[-val_size:]
            train_idx = tr[:-val_size]

            all_train_feats.append(feats[feat_cols].to_numpy(dtype=np.float32)[train_idx])
            all_train_labels.append(labels["label_multi"].to_numpy()[train_idx])
            all_val_feats.append(feats[feat_cols].to_numpy(dtype=np.float32)[val_idx])
            all_val_labels.append(labels["label_multi"].to_numpy()[val_idx])

            log.info(
                "group %d asset %d (%s): train=%d val=%d",
                g, a_idx, assets[a_idx].symbol, len(train_idx), len(val_idx),
            )

        # Concatenate across all assets for shared encoder training
        combined_train_feats = np.concatenate(all_train_feats, axis=0)
        combined_train_labels = np.concatenate(all_train_labels, axis=0)
        combined_val_feats = np.concatenate(all_val_feats, axis=0)
        combined_val_labels = np.concatenate(all_val_labels, axis=0)

        # Build a synthetic DataFrame + labels for pretrain_fold
        # (pretrain_fold expects DataFrame for feature extraction)
        train_idx_combined = np.arange(len(combined_train_feats))
        val_idx_combined = np.arange(
            len(combined_train_feats),
            len(combined_train_feats) + len(combined_val_feats),
        )

        all_feats_arr = np.concatenate([combined_train_feats, combined_val_feats], axis=0)
        all_labels_arr = np.concatenate([combined_train_labels, combined_val_labels], axis=0)

        # Create a temporary DataFrame with the right columns
        combined_df = pd.DataFrame(all_feats_arr, columns=feat_cols)
        combined_labels_df = pd.DataFrame({"label_multi": all_labels_arr})

        log.info(
            "group %d: total train=%d val=%d (across %d assets)",
            g, len(train_idx_combined), len(val_idx_combined), len(assets),
        )

        model = pretrain_fold(
            features=combined_df,
            feature_cols=feat_cols,
            labels=combined_labels_df,
            train_idx=train_idx_combined,
            val_idx=val_idx_combined,
            cfg=pcfg,
        )
        out = os.path.join(artefacts, f"encoder_group{g}.pt")
        save_encoder(model, out)
        log.info("saved encoder -> %s", out)


if __name__ == "__main__":
    main()
