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

from ..models.xlstm_lite import (
    FocalLoss,
    XLSTMConfig,
    XLSTMLite,
    vib_kl,
    vib_reparameterize,
)

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
    vib: bool = False
    vib_beta: float = 1e-3
    tft: bool = False
    tft_heads: int = 4
    multitask: bool = False
    vol_weight: float = 0.3
    meta_weight: float = 0.2


class WindowDataset(Dataset):
    def __init__(
        self,
        feats: np.ndarray,
        labels: np.ndarray,
        seq_len: int,
        idx: np.ndarray,
        vol_targets: np.ndarray | None = None,
        meta_targets: np.ndarray | None = None,
    ):
        self.feats = feats.astype(np.float32)
        self.labels = labels.astype(np.int64)  # already mapped to 0/1/2
        self.seq_len = seq_len
        # drop indices that can't produce a full window
        self.idx = idx[idx >= seq_len - 1]
        self.vol_targets = (
            vol_targets.astype(np.float32) if vol_targets is not None else None
        )
        self.meta_targets = (
            meta_targets.astype(np.int64) if meta_targets is not None else None
        )

    def __len__(self) -> int:
        return len(self.idx)

    def __getitem__(self, i: int):
        row = self.idx[i]
        start = row - self.seq_len + 1
        window = self.feats[start : row + 1]
        if self.vol_targets is None or self.meta_targets is None:
            return torch.from_numpy(window), torch.tensor(self.labels[row])
        return (
            torch.from_numpy(window),
            torch.tensor(self.labels[row]),
            torch.tensor(self.vol_targets[row]),
            torch.tensor(self.meta_targets[row]),
        )


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

    # Auxiliary multi-task targets (Phase G). We z-score the volatility
    # regression target per-fold on train rows so loss scales are comparable
    # to the cross-entropy task loss.
    vol_targets = None
    meta_targets = None
    if cfg.multitask:
        if "ret_fwd_std" in labels.columns and "ret_fwd" in labels.columns:
            vol_raw = labels["ret_fwd_std"].to_numpy(dtype=np.float64)
            ret_fwd = labels["ret_fwd"].to_numpy(dtype=np.float64)
            train_mask = np.zeros(len(vol_raw), dtype=bool)
            train_mask[train_idx] = True
            mu = float(np.nanmean(vol_raw[train_mask])) if train_mask.any() else 0.0
            sd = float(np.nanstd(vol_raw[train_mask])) if train_mask.any() else 1.0
            vol_targets = (vol_raw - mu) / (sd if sd > 1e-8 else 1.0)
            meta_targets = (ret_fwd > 0).astype(np.int64)
        else:
            log.warning("multitask requested but labels lack ret_fwd/ret_fwd_std; disabling")

    model_cfg = XLSTMConfig(
        input_dim=len(feature_cols),
        hidden_size=cfg.hidden_size,
        n_slstm=cfg.n_slstm,
        n_mlstm=cfg.n_mlstm,
        dropout=cfg.dropout,
        softcap=cfg.softcap,
        n_classes=3,
        vib=cfg.vib,
        vib_beta=cfg.vib_beta,
        tft=cfg.tft,
        tft_heads=cfg.tft_heads,
        multitask=cfg.multitask and vol_targets is not None,
        meta_classes=2,
    )
    model = XLSTMLite(model_cfg).to(device)

    # Class-balanced alpha (inverse frequency, clipped)
    counts = np.bincount(y[train_idx], minlength=3).astype(np.float32)
    counts = np.where(counts == 0, 1.0, counts)
    alpha = (counts.sum() / (3 * counts)).clip(0.1, 5.0)
    loss_fn = FocalLoss(gamma=cfg.focal_gamma, alpha=torch.tensor(alpha, dtype=torch.float32))

    train_ds = WindowDataset(
        feats, y, cfg.seq_len, train_idx,
        vol_targets=vol_targets, meta_targets=meta_targets,
    )
    val_ds = WindowDataset(
        feats, y, cfg.seq_len, val_idx,
        vol_targets=vol_targets, meta_targets=meta_targets,
    )
    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size, shuffle=False)

    optim = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    best_val = float("inf")
    best_state = None

    def _step_logits(xb: torch.Tensor, *, stochastic: bool) -> tuple[torch.Tensor, torch.Tensor]:
        """Return (logits, kl). kl is zero when VIB is disabled."""
        if not cfg.vib:
            return model(xb), torch.zeros((), device=xb.device)
        mu, logsigma = model.encode_params(xb)
        z = vib_reparameterize(mu, logsigma) if stochastic else mu
        logits = model.cls_head(z)
        kl = vib_kl(mu, logsigma)
        return logits, kl

    use_multitask = model.cfg.multitask
    for epoch in range(cfg.epochs):
        model.train()
        tr_loss = 0.0
        tr_kl = 0.0
        tr_aux = 0.0
        tr_n = 0
        for batch in train_loader:
            if use_multitask:
                xb, yb, vb, mb = batch
                vb = vb.to(device)
                mb = mb.to(device)
            else:
                xb, yb = batch
            xb = xb.to(device)
            yb = yb.to(device)
            optim.zero_grad()
            logits, kl = _step_logits(xb, stochastic=True)
            task_loss = loss_fn(logits, yb)
            loss = task_loss + cfg.vib_beta * kl
            aux_val = 0.0
            if use_multitask:
                _, vol_pred, meta_logits = model.forward_multi(xb)
                vol_loss = torch.nn.functional.mse_loss(vol_pred, vb)
                meta_loss = torch.nn.functional.cross_entropy(meta_logits, mb)
                aux = cfg.vol_weight * vol_loss + cfg.meta_weight * meta_loss
                loss = loss + aux
                aux_val = float(aux.detach())
            if not torch.isfinite(loss):
                log.warning("epoch %d: non-finite loss, skipping batch", epoch)
                optim.zero_grad()
                continue
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            optim.step()
            tr_loss += float(task_loss.detach()) * len(xb)
            tr_kl += float(kl.detach()) * len(xb)
            tr_aux += aux_val * len(xb)
            tr_n += len(xb)

        model.eval()
        val_loss = 0.0
        val_n = 0
        correct = 0
        with torch.no_grad():
            for batch in val_loader:
                if use_multitask:
                    xb, yb, _vb, _mb = batch
                else:
                    xb, yb = batch
                xb = xb.to(device)
                yb = yb.to(device)
                logits, _ = _step_logits(xb, stochastic=False)
                loss = loss_fn(logits, yb)
                val_loss += float(loss) * len(xb)
                val_n += len(xb)
                correct += int((logits.argmax(dim=-1) == yb).sum())
        tr_avg = tr_loss / max(tr_n, 1)
        tr_kl_avg = tr_kl / max(tr_n, 1)
        tr_aux_avg = tr_aux / max(tr_n, 1)
        val_avg = val_loss / max(val_n, 1)
        val_acc = correct / max(val_n, 1)
        log.info(
            "epoch %d train_loss=%.4f kl=%.4f aux=%.4f val_loss=%.4f val_acc=%.3f",
            epoch, tr_avg, tr_kl_avg, tr_aux_avg, val_avg, val_acc,
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
