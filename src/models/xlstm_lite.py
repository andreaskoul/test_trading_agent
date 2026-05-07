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
    """Stabilised scalar-memory LSTM block with exponential gating.

    The recurrent U(h) connection is intentionally removed so all T gate
    vectors can be computed in a single batched matmul and the linear
    recurrences c_t / n_t solved with torch.cumsum — O(1) GPU kernels
    instead of T serial dispatches.

    U is kept in __init__ (unused) so checkpoints trained with the old
    sequential forward still load without errors.
    """

    def __init__(self, dim: int, softcap: float = 15.0, dropout: float = 0.0):
        super().__init__()
        self.dim = dim
        self.softcap = softcap
        self.norm = RMSNorm(dim)
        self.W = nn.Linear(dim, dim * 4, bias=True)
        self.U = nn.Linear(dim, dim * 4, bias=False)  # kept for ckpt compat
        self.out_proj = nn.Linear(dim, dim, bias=True)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # (B, T, D)
        B, T, D = x.shape
        x_n = self.norm(x)

        # One batched matmul for all T timesteps — (B, T, 4D).
        gates = self.W(x_n)
        i_raw, f_raw, z_raw, o_raw = gates.chunk(4, dim=-1)

        i = _softcap_exp(i_raw, self.softcap)   # (B, T, D)
        f = _softcap_exp(f_raw, self.softcap)
        o = torch.sigmoid(o_raw)
        z = torch.tanh(z_raw)

        # Parallel scan for the two coupled linear recurrences:
        #   c_t = f_t * c_{t-1} + i_t * z_t,  c_0 = 0
        #   n_t = f_t * n_{t-1} + i_t,          n_0 = 1
        #
        # Closed form via the cumulative forget product F_t = ∏_{k≤t} f_k:
        #   c_t = F_t · cumsum(i·z / F, dim=1)[t]
        #   n_t = F_t · (1 + cumsum(i / F, dim=1)[t])
        #
        # log_F is clamped to ≤8 (exp(8)≈2981) to stay in float32 range.
        log_F = torch.cumsum(
            torch.log(f.clamp(min=1e-10)), dim=1
        ).clamp(max=8.0)                              # (B, T, D)
        F     = log_F.exp()
        inv_F = 1.0 / F.clamp(min=1e-10)

        c = (F * torch.cumsum(i * z * inv_F, dim=1)).clamp(-1e4, 1e4)
        n = (F * (1.0 + torch.cumsum(i * inv_F, dim=1))).clamp(min=1e-6)

        h = o * (c / n)                               # (B, T, D)
        return x + self.dropout(self.out_proj(h))


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
        H, Dh = self.n_heads, self.head_dim
        x_n = self.norm(x)

        # All projections in parallel — (B, T, H, Dh).
        q = self.q_proj(x_n).view(B, T, H, Dh)
        k = self.k_proj(x_n).view(B, T, H, Dh)
        v = self.v_proj(x_n).view(B, T, H, Dh)
        gates = self.gate_proj(x_n).view(B, T, H, Dh * 2)
        i_raw, f_raw = gates.chunk(2, dim=-1)
        i_gate = _softcap_exp(i_raw, self.softcap)   # (B, T, H, Dh)
        f_gate = _softcap_exp(f_raw, self.softcap)

        # Scalar gate per head: mean over Dh — (B, T, H, 1).
        i_s = i_gate.mean(dim=-1, keepdim=True)
        f_s = f_gate.mean(dim=-1, keepdim=True)

        # Parallel scan for two coupled linear recurrences (no Python loop):
        #   C_t = f_t·C_{t-1} + i_t·(v_t⊗k_t),   C_0 = 0  ∈ R^(Dh×Dh)
        #   n_t = f_t·n_{t-1} + i_t·k_t,           n_0 = 1  ∈ R^Dh
        #
        # With cumulative forget F_t = ∏_{k≤t} f_k (scalar per head):
        #   C_t = F_t · cumsum(i_s·outer / F, dim=1)[t]
        #   n_t = F_t · (1 + cumsum(i_s·k / F, dim=1)[t])
        log_F = torch.cumsum(
            torch.log(f_s.clamp(min=1e-10)), dim=1
        ).clamp(max=8.0)                              # (B, T, H, 1)
        F     = log_F.exp()                           # (B, T, H, 1)
        inv_F = 1.0 / F.clamp(min=1e-10)             # (B, T, H, 1)

        # n: (B, T, H, Dh)
        n = (F * (1.0 + torch.cumsum(
            i_s * k * inv_F, dim=1
        ))).clamp(-1e4, 1e4)

        # outer: (B, T, H, Dh, Dh) — outer product v⊗k for every timestep.
        outer = torch.einsum("bthd,bthe->bthde", v, k)

        # C: (B, T, H, Dh, Dh)
        C = (F.unsqueeze(-1) * torch.cumsum(
            i_s.unsqueeze(-1) * outer * inv_F.unsqueeze(-1), dim=1
        )).clamp(-1e4, 1e4)

        # Query read: h_t = C_t q_t / max(|n_t^T q_t|, ε)
        num   = torch.einsum("bthde,bthe->bthd", C, q)   # (B, T, H, Dh)
        denom = (n * q).sum(dim=-1, keepdim=True).abs().clamp(min=1e-6)
        y = (num / denom).reshape(B, T, D)

        return x + self.dropout(self.out_proj(y))


class TFTAttentionHead(nn.Module):
    """TFT-style global aggregator on top of the xLSTM sequence output.

    Applies a learned-query multi-head attention over the full (B, T, D)
    sequence, producing a (B, D) summary. This captures which past timesteps
    most influenced the prediction (interpretable attention weights) while
    letting the xLSTM act as the local temporal encoder. Loosely after Lim et
    al. 2020 — minus the quantile head + covariate VSN which don't apply here.
    """

    def __init__(self, dim: int, n_heads: int = 4, dropout: float = 0.0):
        super().__init__()
        self.attn = nn.MultiheadAttention(
            dim, n_heads, dropout=dropout, batch_first=True,
        )
        self.query = nn.Parameter(torch.randn(1, 1, dim) * 0.02)
        self.norm = RMSNorm(dim)

    def forward(self, seq: torch.Tensor) -> torch.Tensor:  # (B, T, D) -> (B, D)
        q = self.query.expand(seq.size(0), -1, -1)
        out, _ = self.attn(q, seq, seq, need_weights=False)
        return self.norm(out.squeeze(1))


@dataclass
class XLSTMConfig:
    input_dim: int
    hidden_size: int = 128
    n_slstm: int = 2
    n_mlstm: int = 2
    dropout: float = 0.3
    softcap: float = 15.0
    n_classes: int = 3  # {-1, 0, +1} -> indices 0/1/2
    vib: bool = False          # Variational Information Bottleneck head
    vib_beta: float = 1e-3     # KL weight on I(Z; X) term
    tft: bool = False          # TFT-style attention aggregator over sequence
    tft_heads: int = 4
    multitask: bool = False    # add volatility-regression + meta-label aux heads
    meta_classes: int = 2      # binary sign-of-forward-return meta-label head


class XLSTMLite(nn.Module):
    def __init__(self, cfg: XLSTMConfig):
        super().__init__()
        self.cfg = cfg
        self.input_proj = nn.Linear(cfg.input_dim, cfg.hidden_size)
        blocks: list[nn.Module] = []
        for i in range(max(cfg.n_slstm, cfg.n_mlstm)):
            if i < cfg.n_slstm:
                blocks.append(SLSTMBlock(cfg.hidden_size, cfg.softcap, cfg.dropout))
            if i < cfg.n_mlstm:
                blocks.append(MLSTMBlock(cfg.hidden_size, cfg.softcap, cfg.dropout))
        self.blocks = nn.ModuleList(blocks)
        self.out_norm = RMSNorm(cfg.hidden_size)
        if cfg.tft:
            self.tft_head = TFTAttentionHead(
                cfg.hidden_size, n_heads=cfg.tft_heads, dropout=cfg.dropout,
            )
        if cfg.vib:
            self.mu_head = nn.Linear(cfg.hidden_size, cfg.hidden_size)
            self.logsigma_head = nn.Linear(cfg.hidden_size, cfg.hidden_size)
        self.cls_head = nn.Linear(cfg.hidden_size, cfg.n_classes)
        if cfg.multitask:
            # Auxiliary heads share the deterministic encoder backbone.
            # Volatility head: scalar regression on forward realised-vol.
            # Meta head: binary "trade worked" sign classification.
            self.vol_head = nn.Linear(cfg.hidden_size, 1)
            self.meta_head = nn.Linear(cfg.hidden_size, cfg.meta_classes)

    def _backbone(self, x: torch.Tensor) -> torch.Tensor:
        h = self.input_proj(x)
        for block in self.blocks:
            h = block(h)
        if self.cfg.tft:
            return self.tft_head(h)
        return self.out_norm(h[:, -1])

    def encode_params(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """VIB posterior: (mu, logsigma). Errors if VIB is disabled."""
        if not self.cfg.vib:
            raise RuntimeError("encode_params requires cfg.vib=True")
        h = self._backbone(x)
        mu = self.mu_head(h)
        logsigma = self.logsigma_head(h).clamp(min=-8.0, max=4.0)
        return mu, logsigma

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """(B, T, F) -> (B, hidden_size) deterministic embedding.

        With VIB enabled this is the posterior mean mu, which is what we use
        at inference and by PPO (no sampling at deployment).
        """
        if self.cfg.vib:
            mu, _ = self.encode_params(x)
            return mu
        return self._backbone(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Classification logits. Training-time sampling lives in the loss."""
        return self.cls_head(self.encode(x))

    def forward_multi(
        self, x: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Multi-task forward: (cls_logits, vol_pred, meta_logits).

        Uses the deterministic backbone (not the VIB sample) for the auxiliary
        heads — they're regularisers, not production heads, so we don't want
        the KL noise feeding into their gradients.
        """
        if not self.cfg.multitask:
            raise RuntimeError("forward_multi requires cfg.multitask=True")
        h = self._backbone(x)
        cls_logits = self.cls_head(h)
        vol_pred = self.vol_head(h).squeeze(-1)
        meta_logits = self.meta_head(h)
        return cls_logits, vol_pred, meta_logits


def vib_reparameterize(mu: torch.Tensor, logsigma: torch.Tensor) -> torch.Tensor:
    """Sample z = mu + sigma * eps, eps ~ N(0, I). Gradient flows through mu and logsigma."""
    sigma = logsigma.clamp(-8.0, 4.0).exp()
    eps = torch.randn_like(mu)
    return mu + sigma * eps


def vib_kl(mu: torch.Tensor, logsigma: torch.Tensor) -> torch.Tensor:
    """KL(N(mu, sigma^2) || N(0, I)) averaged over the batch, summed over dims."""
    ls = logsigma.clamp(-8.0, 4.0)
    # Clamp the exponent separately to prevent exp() overflow on MPS/float32.
    kl = -0.5 * (1.0 + 2.0 * ls - mu.pow(2) - (2.0 * ls).clamp(max=8.0).exp())
    return kl.sum(dim=-1).mean()


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
