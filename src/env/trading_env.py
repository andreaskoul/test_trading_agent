"""Gymnasium trading environment with Triple Barrier exits.

Key design choices:
  * Action space is {HOLD, BUY, SELL} - there is no explicit CLOSE. The
    environment owns exit logic via a Triple Barrier once a position is
    open, exactly as in the Amertume architecture.
  * While a position is live the agent's action is ignored and a reward
    of 0 is returned until a barrier fires. This prevents the agent from
    churning and matches the conservative TB philosophy.
  * Reward on barrier fire is a simple shaped signal: +2 on upper (TP),
    -1 on lower (SL), sign(pnl) on timeout. Transaction costs (in bps)
    are deducted from the returned reward on every entry/exit pair.
  * The observation can be either the raw rolling feature window
    (B, seq_len, n_features) or a pre-encoded 128-dim embedding if you
    pass a frozen encoder.

The env also exposes an env.set_regime(volatility_max_q) method so the
training loop can implement a curriculum: calm -> mixed -> full volatility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces


HOLD, BUY, SELL = 0, 1, 2


@dataclass
class EnvConfig:
    seq_len: int = 32
    rr_upper: float = 2.0
    rr_lower: float = 1.0
    horizon: int = 20
    spread_bps: float = 2.0
    reward_tp: float = 2.0
    reward_sl: float = -1.0


class TradingEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        features: pd.DataFrame,
        feature_cols: list[str],
        cfg: EnvConfig,
        allowed_idx: Optional[np.ndarray] = None,
        seed: int = 0,
    ):
        super().__init__()
        self.features = features.reset_index(drop=True)
        self.feature_cols = list(feature_cols)
        self.cfg = cfg
        self.n = len(self.features)
        self.rng = np.random.default_rng(seed)

        self._feat_mat = self.features[self.feature_cols].to_numpy(dtype=np.float32)
        self._close = self.features["close"].to_numpy(dtype=np.float64)
        self._atr = self.features["atr"].to_numpy(dtype=np.float64)

        # Per-bar realized vol quantile for curriculum filtering.
        rv = pd.Series(self._atr / self._close).rolling(20, min_periods=1).mean()
        self._vol_quantile = rv.rank(pct=True).to_numpy()

        # Starting indices must leave room for seq_len behind and horizon ahead
        lo = cfg.seq_len
        hi = self.n - cfg.horizon - 1
        base = np.arange(lo, hi)
        if allowed_idx is not None:
            base = np.intersect1d(base, allowed_idx)
        self._base_starts = base
        self._volatility_max_q = 1.0
        self._update_start_pool()

        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(
            low=-10.0,
            high=10.0,
            shape=(cfg.seq_len, len(self.feature_cols)),
            dtype=np.float32,
        )

        self._pos = 0  # 0 flat, 1 long, -1 short
        self._entry_i = -1
        self._entry_price = 0.0
        self._barrier_upper = 0.0
        self._barrier_lower = 0.0
        self._step_i = 0
        self._episode_trades: list[float] = []

    # ------------------------------------------------------------------
    # curriculum
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
    # gym API
    # ------------------------------------------------------------------
    def reset(self, *, seed: int | None = None, options=None):  # type: ignore[override]
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self._step_i = int(self.rng.choice(self._start_pool))
        self._pos = 0
        self._entry_i = -1
        self._episode_trades = []
        return self._obs(), {}

    def step(self, action: int):  # type: ignore[override]
        cfg = self.cfg
        reward = 0.0
        terminated = False
        truncated = False
        info: dict = {}

        if self._pos == 0:
            if action == BUY:
                self._open_position(+1)
            elif action == SELL:
                self._open_position(-1)
            # HOLD: no-op
            self._step_i += 1
        else:
            # Advance until barrier fires or horizon expires
            reward, fired, ret = self._check_barrier()
            if fired:
                self._episode_trades.append(ret)
                info["trade_return"] = ret
                self._pos = 0
            self._step_i += 1

        if self._step_i >= self.n - 1:
            terminated = True
        return self._obs(), float(reward), bool(terminated), bool(truncated), info

    # ------------------------------------------------------------------
    def _obs(self) -> np.ndarray:
        end = self._step_i + 1
        start = end - self.cfg.seq_len
        if start < 0:
            start = 0
        window = self._feat_mat[start:end]
        if window.shape[0] < self.cfg.seq_len:
            pad = np.zeros((self.cfg.seq_len - window.shape[0], window.shape[1]), dtype=np.float32)
            window = np.concatenate([pad, window], axis=0)
        return window.astype(np.float32)

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
            ret -= 2 * cfg.spread_bps / 1e4  # entry + exit
            return cfg.reward_tp + self._cost_penalty(), True, float(ret)
        if hit_sl:
            ret = pos * (self._barrier_lower / self._entry_price - 1)
            ret -= 2 * cfg.spread_bps / 1e4
            return cfg.reward_sl + self._cost_penalty(), True, float(ret)
        if horizon_exceeded:
            raw_ret = pos * (price / self._entry_price - 1)
            raw_ret -= 2 * cfg.spread_bps / 1e4
            shaped = float(np.sign(raw_ret)) * 0.5
            return shaped, True, float(raw_ret)
        return 0.0, False, 0.0

    def _cost_penalty(self) -> float:
        return -2 * self.cfg.spread_bps / 1e4
