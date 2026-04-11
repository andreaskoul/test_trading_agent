"""Precompute xLSTM encoder embeddings for every bar.

Given an (N, F) feature matrix and a sequence length T, build the
(N, T, F) rolling window tensor and return an (N, hidden_size) embedding
matrix. Bars whose window is incomplete (i < T - 1) are padded with zeros
on the left.

This runs the encoder once per bar - a lot faster than running it on
every PPO step.
"""

from __future__ import annotations

import numpy as np
import torch

from .xlstm_lite import XLSTMLite


def build_rolling_windows(feats: np.ndarray, seq_len: int) -> np.ndarray:
    n, f = feats.shape
    out = np.zeros((n, seq_len, f), dtype=np.float32)
    for i in range(n):
        start = max(0, i - seq_len + 1)
        window = feats[start : i + 1]
        pad_len = seq_len - window.shape[0]
        if pad_len > 0:
            out[i, :pad_len] = 0.0
            out[i, pad_len:] = window
        else:
            out[i] = window
    return out


def precompute_embeddings(
    encoder: XLSTMLite,
    feats: np.ndarray,
    seq_len: int,
    batch_size: int = 256,
    device: str = "cpu",
) -> np.ndarray:
    encoder.eval()
    encoder.to(device)
    windows = build_rolling_windows(feats, seq_len)
    n = windows.shape[0]
    out = np.zeros((n, encoder.cfg.hidden_size), dtype=np.float32)
    with torch.no_grad():
        for start in range(0, n, batch_size):
            end = min(n, start + batch_size)
            batch = torch.from_numpy(windows[start:end]).to(device)
            emb = encoder.encode(batch)
            out[start:end] = emb.cpu().numpy()
    return out
