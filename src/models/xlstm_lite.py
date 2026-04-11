"""xLSTM-lite encoder (self-contained, no external ``xlstm`` dependency).

Implements the key ideas from Beck et al. (2024, arXiv:2405.04517):
  * sLSTM: scalar memory cell with exponential input/forget gates stabilised
    by a running "soft cap" on the exponent.
  * mLSTM: matrix memory with a covariance-style outer product update and
    similar exponential gating.

This is a deliberately compact re-implementation - it trades a few modelling
niceties (block-diagonal residual streams, conv skip, expanded head mixer)
for clarity and easy CPU training.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F


class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(dim))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rms = x.pow(2).mean(dim=-1, keepdim=True).add(self.eps).sqrt()
        return self.weight * (x / rms)


def _softcap_exp(x: torch.Tensor, cap: float) -> torch.Tensor:
    """Soft-capped exponential: stable near the boundary used by xLSTM."""
    capped = cap * torch.tanh(x / cap)
    return torch.exp(capped)


class SLSTMBlock(nn.Module):
    """Stabilised scalar-memory LSTM block with exponential gating."""

    def __init__(self, dim: int, softcap: float = 15.0, dropout: float = 0.0):
        super().__init__()
        self.dim = dim
        self.softcap = softcap
        self.norm = RMSNorm(dim)
        self.W = nn.Linear(dim, dim * 4, bias=True)
        self.U = nn.Linear(dim, dim * 4, bias=False)
        self.out_proj = nn.Linear(dim, dim, bias=True)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # (B, T, D)
        B, T, D = x.shape
        x_n = self.norm(x)
        h = torch.zeros(B, D, device=x.device, dtype=x.dtype)
        c = torch.zeros(B, D, device=x.device, dtype=x.dtype)
        n = torch.ones(B, D, device=x.device, dtype=x.dtype)  # normalizer state
        outs = []
        for t in range(T):
            gates = self.W(x_n[:, t]) + self.U(h)
            i_raw, f_raw, z, o_raw = gates.chunk(4, dim=-1)
            i = _softcap_exp(i_raw, self.softcap)
            f = _softcap_exp(f_raw, self.softcap)
            o = torch.sigmoid(o_raw)
            z = torch.tanh(z)
            c = f * c + i * z
            n = f * n + i
            h = o * (c / n.clamp(min=1e-6))
            outs.append(h)
        y = torch.stack(outs, dim=1)
        return x + self.dropout(self.out_proj(y))


class MLSTMBlock(nn.Module):
    """Matrix-memory LSTM block with covariance update + exponential gating."""

    def __init__(self, dim: int, softcap: float = 15.0, dropout: float = 0.0, head_dim: int = 16):
        super().__init__()
        assert dim % head_dim == 0, "dim must be divisible by head_dim"
        self.dim = dim
        self.head_dim = head_dim
        self.n_heads = dim // head_dim
        self.softcap = softcap
        self.norm = RMSNorm(dim)
        self.q_proj = nn.Linear(dim, dim, bias=True)
        self.k_proj = nn.Linear(dim, dim, bias=True)
        self.v_proj = nn.Linear(dim, dim, bias=True)
        self.gate_proj = nn.Linear(dim, dim * 2, bias=True)  # i_gate, f_gate
        self.out_proj = nn.Linear(dim, dim, bias=True)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # (B, T, D)
        B, T, D = x.shape
        x_n = self.norm(x)
        q = self.q_proj(x_n).view(B, T, self.n_heads, self.head_dim)
        k = self.k_proj(x_n).view(B, T, self.n_heads, self.head_dim)
        v = self.v_proj(x_n).view(B, T, self.n_heads, self.head_dim)
        gates = self.gate_proj(x_n).view(B, T, self.n_heads, self.head_dim * 2)
        i_raw, f_raw = gates.chunk(2, dim=-1)
        i_gate = _softcap_exp(i_raw, self.softcap)  # (B, T, H, Dh)
        f_gate = _softcap_exp(f_raw, self.softcap)

        # Matrix memory per head: C in R^(Dh, Dh), n in R^(Dh,)
        C = torch.zeros(B, self.n_heads, self.head_dim, self.head_dim, device=x.device, dtype=x.dtype)
        n = torch.ones(B, self.n_heads, self.head_dim, device=x.device, dtype=x.dtype)
        outs = []
        for t in range(T):
            q_t = q[:, t]          # (B, H, Dh)
            k_t = k[:, t]
            v_t = v[:, t]
            i_t = i_gate[:, t].mean(dim=-1, keepdim=True)  # scalar-ish per head
            f_t = f_gate[:, t].mean(dim=-1, keepdim=True)
            # Update covariance memory: C <- f * C + i * v k^T
            outer = torch.einsum("bhi,bhj->bhij", v_t, k_t)
            C = f_t.unsqueeze(-1) * C + i_t.unsqueeze(-1) * outer
            n = f_t * n + i_t * k_t
            # Query: h = C q / max(|n^T q|, eps)
            num = torch.einsum("bhij,bhj->bhi", C, q_t)
            denom = (n * q_t).sum(dim=-1, keepdim=True).abs().clamp(min=1e-6)
            outs.append(num / denom)
        y = torch.stack(outs, dim=1).reshape(B, T, D)
        return x + self.dropout(self.out_proj(y))


@dataclass
class XLSTMConfig:
    input_dim: int
    hidden_size: int = 128
    n_slstm: int = 2
    n_mlstm: int = 2
    dropout: float = 0.3
    softcap: float = 15.0
    n_classes: int = 3  # {-1, 0, +1} -> indices 0/1/2


class XLSTMLite(nn.Module):
    def __init__(self, cfg: XLSTMConfig):
        super().__init__()
        self.cfg = cfg
        self.input_proj = nn.Linear(cfg.input_dim, cfg.hidden_size)
        blocks: list[nn.Module] = []
        # Interleave sLSTM and mLSTM blocks
        for i in range(max(cfg.n_slstm, cfg.n_mlstm)):
            if i < cfg.n_slstm:
                blocks.append(SLSTMBlock(cfg.hidden_size, cfg.softcap, cfg.dropout))
            if i < cfg.n_mlstm:
                blocks.append(MLSTMBlock(cfg.hidden_size, cfg.softcap, cfg.dropout))
        self.blocks = nn.ModuleList(blocks)
        self.out_norm = RMSNorm(cfg.hidden_size)
        self.cls_head = nn.Linear(cfg.hidden_size, cfg.n_classes)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """(B, T, F) -> (B, hidden_size) final-timestep embedding."""
        h = self.input_proj(x)
        for block in self.blocks:
            h = block(h)
        h = self.out_norm(h[:, -1])
        return h

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # classification logits
        return self.cls_head(self.encode(x))


class FocalLoss(nn.Module):
    """Multi-class focal loss with optional per-class alpha weights."""

    def __init__(self, gamma: float = 2.0, alpha: torch.Tensor | None = None):
        super().__init__()
        self.gamma = gamma
        if alpha is not None:
            self.register_buffer("alpha", alpha)
        else:
            self.alpha = None

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        logp = F.log_softmax(logits, dim=-1)
        p = logp.exp()
        target_logp = logp.gather(1, targets.unsqueeze(1)).squeeze(1)
        target_p = p.gather(1, targets.unsqueeze(1)).squeeze(1)
        focal = ((1 - target_p) ** self.gamma) * (-target_logp)
        if self.alpha is not None:
            a = self.alpha.to(logits.device)[targets]
            focal = a * focal
        return focal.mean()
