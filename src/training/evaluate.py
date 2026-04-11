"""End-to-end evaluation of a trained PPO policy on a CPCV test block."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from stable_baselines3 import PPO

from ..env.embedding_env import EmbeddingTradingEnv
from ..env.trading_env import EnvConfig, BUY, SELL, HOLD
from ..models.meta_label import MetaLabelModel, build_trade_features
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
    # Optional per-trade trace used by the meta-labeling layer (T1.1).
    # Each row is the feature vector observed at trade *entry*, aligned with
    # trade_returns. Empty when the caller didn't ask for tracing.
    trade_features: Optional[np.ndarray] = None
    trade_directions: Optional[np.ndarray] = None


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
    meta_model: Optional[MetaLabelModel] = None,
    meta_threshold: float = 0.5,
    trace_entries: bool = False,
) -> EvalResult:
    """Walk the test block deterministically and collect trade returns.

    Parameters
    ----------
    meta_model:
        Optional meta-labeler (T1.1). When supplied, BUY/SELL actions are
        only permitted if the meta-model's P(profit) is >= ``meta_threshold``.
        Otherwise the action is forced to HOLD.
    trace_entries:
        When True, the result also exposes the per-trade entry features and
        directions so a meta-labeler can be trained on them.
    """
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
    entry_feats: list[np.ndarray] = []
    entry_dirs: list[int] = []
    pending_entry: Optional[tuple[np.ndarray, int]] = None
    env._step_i = int(test_idx[0])
    env._pos = 0
    end = int(test_idx[-1])

    step = 0
    max_steps = end - env._step_i + 1
    while env._step_i < end and step < max_steps:
        obs = env._obs()
        if env._pos == 0:
            a = _policy_action(model, obs)
            if a != HOLD:
                direction = +1 if a == BUY else -1
                feats = build_trade_features(
                    obs, direction, float(precomputed["vol_quantile"][env._step_i])
                )
                if meta_model is not None:
                    p_profit = float(meta_model.predict_proba(feats)[0])
                    if p_profit < meta_threshold:
                        a = HOLD
                        pending_entry = None
                    else:
                        pending_entry = (feats, direction)
                else:
                    pending_entry = (feats, direction)
            else:
                pending_entry = None
        else:
            a = HOLD
        _, _, terminated, _, info = env.step(a)
        if "trade_return" in info:
            # Invariant: a trade can only fire after we previously sent
            # BUY/SELL, and the BUY/SELL path always sets pending_entry.
            if pending_entry is None:
                # Should not happen, but keep the sizes aligned defensively
                # by using a zero feature vector + direction 0.
                emb_dim = precomputed["embeddings"].shape[1]
                pending_entry = (
                    np.zeros(emb_dim + 2, dtype=np.float32),
                    0,
                )
            trades.append(info["trade_return"])
            entry_feats.append(pending_entry[0])
            entry_dirs.append(pending_entry[1])
            pending_entry = None
        if terminated:
            break
        step += 1

    trade_returns = np.array(trades, dtype=float)
    if len(trade_returns) == 0:
        equity = np.array([1.0])
    else:
        equity = np.concatenate([[1.0], np.cumprod(1 + trade_returns)])
    metrics = compute_metrics(trade_returns)
    trade_features = np.stack(entry_feats) if trace_entries and entry_feats else None
    trade_directions = (
        np.array(entry_dirs, dtype=np.int8) if trace_entries and entry_dirs else None
    )
    return EvalResult(
        trade_returns=trade_returns,
        equity=equity,
        metrics=metrics,
        n_trades=len(trade_returns),
        trade_features=trade_features,
        trade_directions=trade_directions,
    )


def rollout_with_cost(
    model: PPO,
    precomputed: dict,
    env_cfg: EnvConfig,
    test_idx: np.ndarray,
    spread_bps: float,
) -> EvalResult:
    # Copy all fields, override only the spread. Using dataclass.replace so
    # any new reward-shaping knobs (reward_mode, dsr_*, cost_lambda) added
    # to EnvConfig propagate automatically.
    from dataclasses import replace

    cfg = replace(env_cfg, spread_bps=spread_bps)
    return rollout_policy(model, precomputed, cfg, test_idx)
