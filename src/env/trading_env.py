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


def env_config_from_yaml(cfg: dict) -> "EnvConfig":
    """Build an EnvConfig from the parsed YAML config.

    Centralising this means the 4 script entry points stay in sync on the
    reward-shaping knobs (T1.2 / T1.3). Missing keys fall back to
    ``EnvConfig`` defaults, so old YAMLs stay compatible.
    """
    env = cfg.get("env", {})
    tb = cfg.get("triple_barrier", {})
    return EnvConfig(
        seq_len=env.get("seq_len", 32),
        rr_upper=tb.get("rr_upper", 2.0),
        rr_lower=tb.get("rr_lower", 1.0),
        horizon=tb.get("horizon", 20),
        spread_bps=env.get("spread_bps", 2.0),
        reward_tp=env.get("reward_tp", 2.0),
        reward_sl=env.get("reward_sl", -1.0),
        reward_mode=env.get("reward_mode", "shaped"),
        reward_return_scale=env.get("reward_return_scale", 100.0),
        reward_cost_lambda=env.get("reward_cost_lambda", 0.0),
        reward_dsr_eta=env.get("reward_dsr_eta", 0.01),
        reward_dsr_scale=env.get("reward_dsr_scale", 1.0),
        min_flat_bars=env.get("min_flat_bars", 0),
    )


@dataclass
class EnvConfig:
    seq_len: int = 32
    rr_upper: float = 2.0
    rr_lower: float = 1.0
    horizon: int = 20
    spread_bps: float = 2.0
    reward_tp: float = 2.0
    reward_sl: float = -1.0
    # --- Tier 1 reward-shaping knobs ---
    # reward_mode:
    #   "shaped"     -> legacy: ±reward_tp/reward_sl fixed signal (backward compat).
    #   "return"     -> return-proportional: scale*(ret - lambda*roundtrip_cost).
    #                   Directly attacks the cost cliff identified in the eval
    #                   report (T1.2).
    #   "diff_sharpe"-> Moody & Saffell (1998) differential Sharpe increment
    #                   on each trade fire (T1.3). Complements "return" mode
    #                   by making risk-adjusted return the optimisation target.
    reward_mode: str = "shaped"
    # Scale the realised return into reward units. 100 keeps rewards roughly
    # in [-2, +2] given ~1% per-trade returns.
    reward_return_scale: float = 100.0
    # Extra turnover penalty on top of realised spread cost. 0 disables; set
    # e.g. 3.0 to penalise the agent 3x actual per-round-trip cost.
    reward_cost_lambda: float = 0.0
    # EWMA rate for differential Sharpe moments. Smaller = slower adaptation.
    reward_dsr_eta: float = 0.01
    # Scale factor on the differential Sharpe increment.
    reward_dsr_scale: float = 1.0
    # Minimum flat bars enforced after a trade closes, before a new entry is
    # allowed. 0 disables. A small cooldown (1-3 bars) kills flip-flop
    # turnover without the over-suppression iter-2's cost_lambda=4 caused.
    min_flat_bars: int = 0


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
        # Differential-Sharpe running moments (Moody & Saffell 1998).
        self._dsr_A = 0.0
        self._dsr_B = 1e-8

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
        self._flat_until = -1
        self._episode_trades = []
        self._dsr_A = 0.0
        self._dsr_B = 1e-8
        return self._obs(), {}

    def step(self, action: int):  # type: ignore[override]
        cfg = self.cfg
        reward = 0.0
        terminated = False
        truncated = False
        info: dict = {}

        if self._pos == 0:
            # Cooldown: after a trade exits, block new entries for
            # cfg.min_flat_bars steps. Forces HOLD regardless of action.
            if self._step_i >= self._flat_until:
                if action == BUY:
                    self._open_position(+1)
                elif action == SELL:
                    self._open_position(-1)
            # HOLD (or cooldown): no-op
            self._step_i += 1
        else:
            # Advance until barrier fires or horizon expires
            reward, fired, ret = self._check_barrier()
            if fired:
                self._episode_trades.append(ret)
                info["trade_return"] = ret
                self._pos = 0
                self._flat_until = self._step_i + cfg.min_flat_bars + 1
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
    # reward shaping
    # ------------------------------------------------------------------
    def _compute_reward(self, ret: float, barrier: str) -> float:
        """Convert a realised trade return into a PPO reward.

        ``ret`` is the actual fractional PnL of the trade (spread already
        deducted once). ``barrier`` is "tp", "sl" or "timeout" and is only
        used by the legacy shaped mode to preserve backward compatibility.
        """
        cfg = self.cfg
        mode = getattr(cfg, "reward_mode", "shaped")
        if mode == "shaped":
            # Legacy path: fixed ±shaped signal plus tiny cost penalty.
            cost_pen = -2 * cfg.spread_bps / 1e4
            if barrier == "tp":
                return float(cfg.reward_tp + cost_pen)
            if barrier == "sl":
                return float(cfg.reward_sl + cost_pen)
            return float(np.sign(ret)) * 0.5
        if mode == "return":
            # Return-proportional with optional extra turnover penalty.
            # lambda=0 means reward == return_scale*ret (already net of spread).
            extra_cost = cfg.reward_cost_lambda * 2 * cfg.spread_bps / 1e4
            return float(cfg.reward_return_scale * (ret - extra_cost))
        if mode == "diff_sharpe":
            # Moody & Saffell differential Sharpe increment (NeurIPS 1998).
            # Uses EWMA first/second moments; returns the change in the
            # running Sharpe estimate attributable to this single trade.
            A = self._dsr_A
            B = self._dsr_B
            delta_a = ret - A
            delta_b = ret * ret - B
            var = B - A * A
            if var > 1e-12:
                denom = var ** 1.5
                d = (B * delta_a - 0.5 * A * delta_b) / denom
            else:
                # Cold start before variance is well defined.
                d = ret
            self._dsr_A = A + cfg.reward_dsr_eta * delta_a
            self._dsr_B = B + cfg.reward_dsr_eta * delta_b
            # Penalty on turnover is still useful so the agent doesn't just
            # hunt DSR by trading more.
            extra_cost = cfg.reward_cost_lambda * 2 * cfg.spread_bps / 1e4
            return float(cfg.reward_dsr_scale * d - cfg.reward_return_scale * extra_cost)
        raise ValueError(f"unknown reward_mode: {mode!r}")
