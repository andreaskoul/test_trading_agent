"""Pretrain the xLSTM-lite encoder on Triple Barrier labels with Focal Loss.

Runs per CPCV training fold so the encoder used at evaluation time has
*not* seen the test block.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

from ..models.xlstm_lite import FocalLoss, XLSTMConfig, XLSTMLite

log = logging.getLogger(__name__)


@dataclass
class PretrainConfig:
    seq_len: int
    hidden_size: int
    n_slstm: int
    n_mlstm: int
    dropout: float
    softcap: float
    focal_gamma: float
    lr: float
    epochs: int
    batch_size: int
    device: str = "cpu"


class WindowDataset(Dataset):
    def __init__(self, feats: np.ndarray, labels: np.ndarray, seq_len: int, idx: np.ndarray):
        self.feats = feats.astype(np.float32)
        self.labels = labels.astype(np.int64)  # already mapped to 0/1/2
        self.seq_len = seq_len
        # drop indices that can't produce a full window
        self.idx = idx[idx >= seq_len - 1]

    def __len__(self) -> int:
        return len(self.idx)

    def __getitem__(self, i: int):
        row = self.idx[i]
        start = row - self.seq_len + 1
        window = self.feats[start : row + 1]
        return torch.from_numpy(window), torch.tensor(self.labels[row])


def _map_labels(multi: np.ndarray) -> np.ndarray:
    """Map {-1, 0, +1} to {0, 1, 2}."""
    out = np.empty_like(multi, dtype=np.int64)
    out[multi == -1] = 0
    out[multi == 0] = 1
    out[multi == 1] = 2
    return out


def pretrain_fold(
    features: pd.DataFrame,
    feature_cols: list[str],
    labels: pd.DataFrame,
    train_idx: np.ndarray,
    val_idx: np.ndarray,
    cfg: PretrainConfig,
) -> XLSTMLite:
    device = torch.device(cfg.device)
    feats = features[feature_cols].to_numpy()
    y = _map_labels(labels["label_multi"].to_numpy())

    model_cfg = XLSTMConfig(
        input_dim=len(feature_cols),
        hidden_size=cfg.hidden_size,
        n_slstm=cfg.n_slstm,
        n_mlstm=cfg.n_mlstm,
        dropout=cfg.dropout,
        softcap=cfg.softcap,
        n_classes=3,
    )
    model = XLSTMLite(model_cfg).to(device)

    # Class-balanced alpha (inverse frequency, clipped)
    counts = np.bincount(y[train_idx], minlength=3).astype(np.float32)
    counts = np.where(counts == 0, 1.0, counts)
    alpha = (counts.sum() / (3 * counts)).clip(0.1, 5.0)
    loss_fn = FocalLoss(gamma=cfg.focal_gamma, alpha=torch.tensor(alpha, dtype=torch.float32))

    train_ds = WindowDataset(feats, y, cfg.seq_len, train_idx)
    val_ds = WindowDataset(feats, y, cfg.seq_len, val_idx)
    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size, shuffle=False)

    optim = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    best_val = float("inf")
    best_state = None

    for epoch in range(cfg.epochs):
        model.train()
        tr_loss = 0.0
        tr_n = 0
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            optim.zero_grad()
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optim.step()
            tr_loss += float(loss) * len(xb)
            tr_n += len(xb)

        model.eval()
        val_loss = 0.0
        val_n = 0
        correct = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device)
                yb = yb.to(device)
                logits = model(xb)
                loss = loss_fn(logits, yb)
                val_loss += float(loss) * len(xb)
                val_n += len(xb)
                correct += int((logits.argmax(dim=-1) == yb).sum())
        tr_avg = tr_loss / max(tr_n, 1)
        val_avg = val_loss / max(val_n, 1)
        val_acc = correct / max(val_n, 1)
        log.info(
            "epoch %d train_loss=%.4f val_loss=%.4f val_acc=%.3f", epoch, tr_avg, val_avg, val_acc
        )
        if val_avg < best_val:
            best_val = val_avg
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    return model


def save_encoder(model: XLSTMLite, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "config": model.cfg.__dict__,
        },
        path,
    )


def load_encoder(path: str, device: str = "cpu") -> XLSTMLite:
    ckpt = torch.load(path, map_location=device, weights_only=False)
    cfg = XLSTMConfig(**ckpt["config"])
    model = XLSTMLite(cfg).to(device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    return model
