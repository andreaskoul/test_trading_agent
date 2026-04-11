"""Pretrain an xLSTM-lite encoder per CPCV training fold."""

from __future__ import annotations

import argparse
import logging
import os

import numpy as np
import pandas as pd

from _bootstrap import setup, path

from src.data.features import feature_columns
from src.training.pretrain_encoder import PretrainConfig, pretrain_fold, save_encoder
from src.validation.cpcv import CombinatorialPurgedKFold


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="Use a reduced training budget")
    args = ap.parse_args()

    log = logging.getLogger("pretrain")
    cfg = setup()

    features = pd.read_parquet(path(cfg, cfg["data"]["features_path"]))
    labels = pd.read_parquet(path(cfg, cfg["data"]["labels_path"]))
    labels["t1"] = pd.to_datetime(labels["t1"], utc=True)

    feat_cols = feature_columns(features)
    log.info("features %s x %d", features.shape, len(feat_cols))

    cpcv = CombinatorialPurgedKFold(
        n_splits=cfg["cpcv"]["n_splits"],
        n_test_splits=cfg["cpcv"]["n_test_splits"],
        embargo_pct=cfg["cpcv"]["embargo_pct"],
    )
    t1_series = pd.Series(labels["t1"].values, index=features.index)

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
    )

    # One encoder per CPCV split. For the MVR scope we only actually need
    # one encoder per backtest-path, but it is simpler to key by split and
    # let the training loop pick the matching one via a stable hash.
    artefacts = path(cfg, cfg["artefact_dir"], "encoders")
    os.makedirs(artefacts, exist_ok=True)

    splits = list(cpcv.split(t1_series))
    log.info("CPCV produced %d splits", len(splits))

    # Pretrain only the first N_splits encoders (one per group combination
    # would be wasteful and slow). We produce n_splits encoders where the
    # training set for encoder i = all bars not in group i.
    n_splits = cfg["cpcv"]["n_splits"]
    n = len(features)
    from src.validation.cpcv import _group_bounds
    groups = _group_bounds(n, n_splits)

    for g in range(n_splits):
        lo, hi = groups[g]
        test_idx = np.arange(lo, hi)
        train_candidates = np.setdiff1d(np.arange(n), test_idx)
        # apply purge
        from src.validation.cpcv import _purge_train, _embargo
        tr = _purge_train(train_candidates, test_idx, t1_series)
        tr = _embargo(tr, [(lo, hi)], int(cfg["cpcv"]["embargo_pct"] * n), n)
        val_size = int(len(tr) * 0.1)
        val_idx = tr[-val_size:]
        train_idx = tr[:-val_size]
        log.info("group %d: train=%d val=%d test=%d", g, len(train_idx), len(val_idx), len(test_idx))
        model = pretrain_fold(
            features=features,
            feature_cols=feat_cols,
            labels=labels,
            train_idx=train_idx,
            val_idx=val_idx,
            cfg=pcfg,
        )
        out = os.path.join(artefacts, f"encoder_group{g}.pt")
        save_encoder(model, out)
        log.info("saved encoder -> %s", out)


if __name__ == "__main__":
    main()
