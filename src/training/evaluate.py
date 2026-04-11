"""End-to-end evaluation of a trained PPO policy on a CPCV test block."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from stable_baselines3 import PPO

from ..env.embedding_env import EmbeddingTradingEnv
from ..env.trading_env import EnvConfig, BUY, SELL, HOLD
from ..models.precompute import precompute_embeddings
from ..models.xlstm_lite import XLSTMLite
from ..validation.metrics import compute_metrics, PerformanceMetrics

log = logging.getLogger(__name__)


@dataclass
class EvalResult:
    trade_returns: np.ndarray
    equity: np.ndarray
    metrics: PerformanceMetrics
    n_trades: int


def build_precomputed(
    features: pd.DataFrame,
    feature_cols: list[str],
    encoder: XLSTMLite,
    seq_len: int,
) -> dict:
    feats = features[feature_cols].to_numpy(dtype=np.float32)
    embeddings = precompute_embeddings(encoder, feats, seq_len=seq_len)
    close = features["close"].to_numpy(dtype=np.float64)
    atr = features["atr"].to_numpy(dtype=np.float64)
    rv = pd.Series(atr / close).rolling(20, min_periods=1).mean()
    vol_quantile = rv.rank(pct=True).to_numpy()
    return dict(close=close, atr=atr, embeddings=embeddings, vol_quantile=vol_quantile)


def _policy_action(model: PPO, obs: np.ndarray) -> int:
    action, _ = model.predict(obs, deterministic=True)
    return int(action)


def rollout_policy(
    model: PPO,
    precomputed: dict,
    env_cfg: EnvConfig,
    test_idx: np.ndarray,
) -> EvalResult:
    """Walk the test block deterministically and collect trade returns."""
    env = EmbeddingTradingEnv(
        close=precomputed["close"],
        atr=precomputed["atr"],
        embeddings=precomputed["embeddings"],
        vol_quantile=precomputed["vol_quantile"],
        cfg=env_cfg,
        allowed_idx=test_idx,
        seed=0,
    )

    trades: list[float] = []
    env._step_i = int(test_idx[0])
    env._pos = 0
    end = int(test_idx[-1])

    step = 0
    max_steps = end - env._step_i + 1
    while env._step_i < end and step < max_steps:
        obs = env._obs()
        if env._pos == 0:
            a = _policy_action(model, obs)
        else:
            a = HOLD
        _, _, terminated, _, info = env.step(a)
        if "trade_return" in info:
            trades.append(info["trade_return"])
        if terminated:
            break
        step += 1

    trade_returns = np.array(trades, dtype=float)
    if len(trade_returns) == 0:
        equity = np.array([1.0])
    else:
        equity = np.concatenate([[1.0], np.cumprod(1 + trade_returns)])
    metrics = compute_metrics(trade_returns)
    return EvalResult(
        trade_returns=trade_returns,
        equity=equity,
        metrics=metrics,
        n_trades=len(trade_returns),
    )


def rollout_with_cost(
    model: PPO,
    precomputed: dict,
    env_cfg: EnvConfig,
    test_idx: np.ndarray,
    spread_bps: float,
) -> EvalResult:
    cfg = EnvConfig(
        seq_len=env_cfg.seq_len,
        rr_upper=env_cfg.rr_upper,
        rr_lower=env_cfg.rr_lower,
        horizon=env_cfg.horizon,
        spread_bps=spread_bps,
        reward_tp=env_cfg.reward_tp,
        reward_sl=env_cfg.reward_sl,
    )
    return rollout_policy(model, precomputed, cfg, test_idx)
