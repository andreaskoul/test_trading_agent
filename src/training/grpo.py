"""GRPO (Group Relative Policy Optimization) — critic-free policy gradient.

DeepSeek introduced GRPO for RLHF on sparse rewards: instead of a learned
critic, the baseline is the mean return over a "group" of trajectory samples
from the same initial state, and the advantage is the group z-score. This
removes the value-function learning dynamics that often destabilize PPO on
noisy financial rewards.

We adapt GRPO to single-stream trading rollouts:

  * Collect ``group_size * rollout_per_trajectory`` steps total by running
    ``group_size`` restarts of the env from the same calm-frac curriculum.
  * For each trajectory compute per-step discounted returns G_t.
  * Advantage is the within-group z-score: A_t = (G_t - mean_G) / std_G.
  * Policy update is PPO-style clipped log-ratio without a value loss.

The class exposes the subset of SB3's API used by ``scripts/03_train_ppo.py``
(``learn``, ``predict``, ``save``, ``load``, ``set_env``), so the manifest
loader and evaluation rollouts see it as just another algorithm choice.
"""

from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from io import BytesIO

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from gymnasium import Env

# `torch.save(...); torch.load(...)` round-trip uses a pickle protocol, but we
# wrap it in a zip so SB3's `.zip` extension convention keeps working for the
# manifest paths.


class _MLPPolicy(nn.Module):
    """Discrete policy head: obs -> action logits. No value head (GRPO)."""

    def __init__(self, obs_dim: int, n_actions: int, hidden: tuple[int, ...] = (128, 64)):
        super().__init__()
        layers: list[nn.Module] = []
        prev = obs_dim
        for h in hidden:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.Tanh())
            prev = h
        layers.append(nn.Linear(prev, n_actions))
        self.net = nn.Sequential(*layers)

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.net(obs)


@dataclass
class GRPOConfig:
    total_timesteps: int
    group_size: int = 4
    steps_per_trajectory: int = 256
    gamma: float = 0.99
    clip_range: float = 0.2
    ent_coef: float = 0.01
    learning_rate: float = 3e-4
    n_epochs: int = 4
    batch_size: int = 256
    hidden: tuple[int, ...] = (128, 64)
    seed: int = 0


class GRPO:
    """Minimal critic-free policy-gradient trainer with group-relative baseline."""

    def __init__(self, env, cfg: GRPOConfig, device: str = "cpu"):
        self.cfg = cfg
        self.device = torch.device(device)
        self.env = env
        obs_space = env.observation_space
        act_space = env.action_space
        self.obs_dim = int(np.prod(obs_space.shape))
        self.n_actions = int(act_space.n)
        self.policy = _MLPPolicy(self.obs_dim, self.n_actions, cfg.hidden).to(self.device)
        self.optim = torch.optim.Adam(self.policy.parameters(), lr=cfg.learning_rate)
        self._rng = np.random.default_rng(cfg.seed)
        torch.manual_seed(cfg.seed)

    # ---- minimal SB3-ish API ---------------------------------------------
    def set_env(self, env) -> None:
        self.env = env

    @torch.no_grad()
    def predict(self, obs, state=None, deterministic: bool = True):
        """Return (action, state). Mirrors SB3's signature for rollout reuse."""
        x = torch.as_tensor(obs, dtype=torch.float32, device=self.device)
        if x.dim() == 1:
            x = x.unsqueeze(0)
            squeeze = True
        else:
            squeeze = False
        logits = self.policy(x)
        if deterministic:
            act = logits.argmax(dim=-1)
        else:
            dist = torch.distributions.Categorical(logits=logits)
            act = dist.sample()
        a = act.cpu().numpy()
        if squeeze:
            a = a[0]
        return a, state

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        buffer = BytesIO()
        torch.save(
            {
                "state_dict": self.policy.state_dict(),
                "cfg": self.cfg.__dict__,
                "obs_dim": self.obs_dim,
                "n_actions": self.n_actions,
            },
            buffer,
        )
        buffer.seek(0)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("grpo.pt", buffer.read())

    @classmethod
    def load(cls, path: str, env=None, device: str = "cpu"):
        with zipfile.ZipFile(path, "r") as zf:
            raw = zf.read("grpo.pt")
        ckpt = torch.load(BytesIO(raw), map_location=device, weights_only=False)
        cfg = GRPOConfig(**ckpt["cfg"])
        inst = cls.__new__(cls)
        inst.cfg = cfg
        inst.device = torch.device(device)
        inst.env = env
        inst.obs_dim = ckpt["obs_dim"]
        inst.n_actions = ckpt["n_actions"]
        inst.policy = _MLPPolicy(inst.obs_dim, inst.n_actions, cfg.hidden).to(inst.device)
        inst.policy.load_state_dict(ckpt["state_dict"])
        inst.policy.eval()
        inst.optim = torch.optim.Adam(inst.policy.parameters(), lr=cfg.learning_rate)
        inst._rng = np.random.default_rng(cfg.seed)
        return inst

    # ---- training --------------------------------------------------------
    def _collect_group(self) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Run ``group_size`` trajectories and return (obs, act, logp_old, adv).

        Advantage is the within-group z-score of per-step discounted returns.
        """
        all_obs: list[np.ndarray] = []
        all_acts: list[np.ndarray] = []
        all_logp: list[np.ndarray] = []
        all_returns: list[np.ndarray] = []

        def _flat(o):
            arr = np.asarray(o, dtype=np.float32)
            return arr.reshape(-1)

        for _ in range(self.cfg.group_size):
            obs_buf = np.zeros((self.cfg.steps_per_trajectory, self.obs_dim), dtype=np.float32)
            act_buf = np.zeros(self.cfg.steps_per_trajectory, dtype=np.int64)
            logp_buf = np.zeros(self.cfg.steps_per_trajectory, dtype=np.float32)
            rew_buf = np.zeros(self.cfg.steps_per_trajectory, dtype=np.float32)

            o, _ = self.env.reset(seed=int(self._rng.integers(0, 1 << 31)))
            for t in range(self.cfg.steps_per_trajectory):
                o_flat = _flat(o)
                with torch.no_grad():
                    x = torch.from_numpy(o_flat).unsqueeze(0).to(self.device)
                    logits = self.policy(x)
                    dist = torch.distributions.Categorical(logits=logits)
                    a = dist.sample()
                    lp = dist.log_prob(a)
                act = int(a.item())
                obs_buf[t] = o_flat
                act_buf[t] = act
                logp_buf[t] = float(lp.item())
                o, r, term, trunc, _info = self.env.step(act)
                rew_buf[t] = float(r)
                if term or trunc:
                    o, _ = self.env.reset(seed=int(self._rng.integers(0, 1 << 31)))

            # Discounted returns per trajectory
            ret = np.zeros_like(rew_buf)
            running = 0.0
            for t in range(self.cfg.steps_per_trajectory - 1, -1, -1):
                running = rew_buf[t] + self.cfg.gamma * running
                ret[t] = running
            all_obs.append(obs_buf)
            all_acts.append(act_buf)
            all_logp.append(logp_buf)
            all_returns.append(ret)

        obs = np.concatenate(all_obs, axis=0)
        acts = np.concatenate(all_acts, axis=0)
        logp_old = np.concatenate(all_logp, axis=0)
        returns = np.concatenate(all_returns, axis=0)

        # Group-relative z-score advantage. This is the GRPO signature — no
        # critic, baseline is the group mean, scale is the group std.
        adv = (returns - returns.mean()) / (returns.std() + 1e-6)

        return (
            torch.from_numpy(obs).to(self.device),
            torch.from_numpy(acts).to(self.device),
            torch.from_numpy(logp_old).to(self.device),
            torch.from_numpy(adv.astype(np.float32)).to(self.device),
        )

    def _update(
        self,
        obs: torch.Tensor,
        acts: torch.Tensor,
        logp_old: torch.Tensor,
        adv: torch.Tensor,
    ) -> None:
        n = obs.shape[0]
        for _ in range(self.cfg.n_epochs):
            idx = torch.randperm(n, device=self.device)
            for start in range(0, n, self.cfg.batch_size):
                b = idx[start : start + self.cfg.batch_size]
                logits = self.policy(obs[b])
                dist = torch.distributions.Categorical(logits=logits)
                logp = dist.log_prob(acts[b])
                ratio = (logp - logp_old[b]).exp()
                a_b = adv[b]
                surr1 = ratio * a_b
                surr2 = ratio.clamp(1 - self.cfg.clip_range, 1 + self.cfg.clip_range) * a_b
                policy_loss = -torch.min(surr1, surr2).mean()
                entropy = dist.entropy().mean()
                loss = policy_loss - self.cfg.ent_coef * entropy
                self.optim.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.policy.parameters(), 1.0)
                self.optim.step()

    def learn(
        self,
        total_timesteps: int,
        progress_bar: bool = False,
        reset_num_timesteps: bool = True,
        callback=None,
        log_interval: int | None = None,
        tb_log_name: str = "GRPO",
    ) -> "GRPO":
        # SB3-shaped signature so train_ppo.py can call GRPO interchangeably
        # with PPO/A2C/RecurrentPPO. We don't use the SB3 logger or callbacks.
        del progress_bar, reset_num_timesteps, callback, log_interval, tb_log_name
        steps_per_batch = self.cfg.group_size * self.cfg.steps_per_trajectory
        n_batches = max(1, total_timesteps // steps_per_batch)
        for _ in range(n_batches):
            obs, acts, logp_old, adv = self._collect_group()
            self._update(obs, acts, logp_old, adv)
        return self
