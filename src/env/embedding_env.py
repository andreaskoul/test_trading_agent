"""A lighter Gymnasium env that operates on precomputed xLSTM embeddings.

The full TradingEnv feeds raw (seq_len, n_features) windows through the
encoder on every step. That is too slow on CPU for PPO. EmbeddingTradingEnv
instead consumes a precomputed (n_bars, hidden_size) embedding matrix -
one 128-dim vector per bar - and exposes only that vector as the
observation. The encoder therefore runs exactly once per bar at dataset
build time, not per PPO step.

All the trading semantics (Triple Barrier exits, action space, rewards,
curriculum) are identical to TradingEnv.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

from .trading_env import EnvConfig, HOLD, BUY, SELL


class EmbeddingTradingEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        close: np.ndarray,
        atr: np.ndarray,
        embeddings: np.ndarray,   # (n_bars, hidden_size)
        vol_quantile: np.ndarray, # (n_bars,)
        cfg: EnvConfig,
        allowed_idx: Optional[np.ndarray] = None,
        seed: int = 0,
        regime_posterior: Optional[np.ndarray] = None,  # (n_bars, n_states)
    ):
        super().__init__()
        self._close = np.asarray(close, dtype=np.float64)
        self._atr = np.asarray(atr, dtype=np.float64)
        self._emb = np.asarray(embeddings, dtype=np.float32)
        self._vol_quantile = np.asarray(vol_quantile, dtype=np.float64)
        # T2.1 regime conditioning: optional per-bar HMM posterior.
        if regime_posterior is not None:
            self._regime = np.asarray(regime_posterior, dtype=np.float32)
            if self._regime.ndim != 2 or len(self._regime) != len(self._close):
                raise ValueError(
                    f"regime_posterior must be (n_bars, n_states); got {self._regime.shape}"
                )
        else:
            self._regime = None
        self.cfg = cfg
        self.n = len(self._close)
        self.rng = np.random.default_rng(seed)

        lo = cfg.seq_len
        hi = self.n - cfg.horizon - 1
        base = np.arange(lo, hi)
        if allowed_idx is not None:
            base = np.intersect1d(base, allowed_idx)
        self._base_starts = base
        self._volatility_max_q = 1.0
        self._update_start_pool()

        self.action_space = spaces.Discrete(3)
        obs_dim = self._emb.shape[1]
        if self._regime is not None:
            obs_dim += self._regime.shape[1]
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(obs_dim,),
            dtype=np.float32,
        )

        self._pos = 0
        self._entry_i = -1
        self._entry_price = 0.0
        self._barrier_upper = 0.0
        self._barrier_lower = 0.0
        self._step_i = 0
        self._episode_trades: list[float] = []
        # Differential-Sharpe running moments (Moody & Saffell 1998).
        self._dsr_A = 0.0
        self._dsr_B = 1e-8

    # ------------------------------------------------------------------
    def set_regime(self, volatility_max_q: float) -> None:
        self._volatility_max_q = max(0.05, min(volatility_max_q, 1.0))
        self._update_start_pool()

    def _update_start_pool(self) -> None:
        mask = self._vol_quantile[self._base_starts] <= self._volatility_max_q
        self._start_pool = self._base_starts[mask]
        if len(self._start_pool) == 0:
            self._start_pool = self._base_starts

    # ------------------------------------------------------------------
    def reset(self, *, seed: int | None = None, options=None):  # type: ignore[override]
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self._step_i = int(self.rng.choice(self._start_pool))
        self._pos = 0
        self._entry_i = -1
        self._flat_until = -1
        self._episode_trades = []
        self._dsr_A = 0.0
        self._dsr_B = 1e-8
        return self._obs(), {}

    def step(self, action: int):  # type: ignore[override]
        reward = 0.0
        terminated = False
        truncated = False
        info: dict = {}

        if self._pos == 0:
            if self._step_i >= self._flat_until:
                if action == BUY:
                    self._open_position(+1)
                elif action == SELL:
                    self._open_position(-1)
            self._step_i += 1
        else:
            reward, fired, ret = self._check_barrier()
            if fired:
                self._episode_trades.append(ret)
                info["trade_return"] = ret
                self._pos = 0
                self._flat_until = self._step_i + self.cfg.min_flat_bars + 1
            self._step_i += 1

        if self._step_i >= self.n - 1:
            terminated = True
        return self._obs(), float(reward), bool(terminated), bool(truncated), info

    # ------------------------------------------------------------------
    def _obs(self) -> np.ndarray:
        i = min(self._step_i, self.n - 1)
        emb = self._emb[i].astype(np.float32)
        if self._regime is None:
            return emb
        return np.concatenate([emb, self._regime[i]]).astype(np.float32)

    def _open_position(self, direction: int) -> None:
        self._pos = direction
        self._entry_i = self._step_i
        self._entry_price = self._close[self._step_i]
        atr_now = max(self._atr[self._step_i], 1e-8)
        if direction == +1:
            self._barrier_upper = self._entry_price + self.cfg.rr_upper * atr_now
            self._barrier_lower = self._entry_price - self.cfg.rr_lower * atr_now
        else:
            self._barrier_upper = self._entry_price - self.cfg.rr_upper * atr_now
            self._barrier_lower = self._entry_price + self.cfg.rr_lower * atr_now

    def _check_barrier(self) -> tuple[float, bool, float]:
        cfg = self.cfg
        i = self._step_i
        price = self._close[i]
        horizon_exceeded = (i - self._entry_i) >= cfg.horizon
        pos = self._pos

        hit_tp = False
        hit_sl = False
        if pos == +1:
            hit_tp = price >= self._barrier_upper
            hit_sl = price <= self._barrier_lower
        elif pos == -1:
            hit_tp = price <= self._barrier_upper
            hit_sl = price >= self._barrier_lower

        if hit_tp:
            ret = pos * (self._barrier_upper / self._entry_price - 1)
            ret -= 2 * cfg.spread_bps / 1e4
            return self._compute_reward(float(ret), "tp"), True, float(ret)
        if hit_sl:
            ret = pos * (self._barrier_lower / self._entry_price - 1)
            ret -= 2 * cfg.spread_bps / 1e4
            return self._compute_reward(float(ret), "sl"), True, float(ret)
        if horizon_exceeded:
            raw_ret = pos * (price / self._entry_price - 1)
            raw_ret -= 2 * cfg.spread_bps / 1e4
            return self._compute_reward(float(raw_ret), "timeout"), True, float(raw_ret)
        return 0.0, False, 0.0

    # ------------------------------------------------------------------
    # reward shaping (mirrors TradingEnv._compute_reward)
    # ------------------------------------------------------------------
    def _compute_reward(self, ret: float, barrier: str) -> float:
        cfg = self.cfg
        mode = getattr(cfg, "reward_mode", "shaped")
        if mode == "shaped":
            cost_pen = -2 * cfg.spread_bps / 1e4
            if barrier == "tp":
                return float(cfg.reward_tp + cost_pen)
            if barrier == "sl":
                return float(cfg.reward_sl + cost_pen)
            return float(np.sign(ret)) * 0.5
        if mode == "return":
            extra_cost = cfg.reward_cost_lambda * 2 * cfg.spread_bps / 1e4
            return float(cfg.reward_return_scale * (ret - extra_cost))
        if mode == "diff_sharpe":
            A = self._dsr_A
            B = self._dsr_B
            delta_a = ret - A
            delta_b = ret * ret - B
            var = B - A * A
            if var > 1e-12:
                denom = var ** 1.5
                d = (B * delta_a - 0.5 * A * delta_b) / denom
            else:
                d = ret
            self._dsr_A = A + cfg.reward_dsr_eta * delta_a
            self._dsr_B = B + cfg.reward_dsr_eta * delta_b
            extra_cost = cfg.reward_cost_lambda * 2 * cfg.spread_bps / 1e4
            return float(cfg.reward_dsr_scale * d - cfg.reward_return_scale * extra_cost)
        raise ValueError(f"unknown reward_mode: {mode!r}")
