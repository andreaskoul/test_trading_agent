"""PPO training loop with curriculum + seeds + CPCV paths.

Uses precomputed encoder embeddings (see src.models.precompute) so the
PPO rollout does NOT pay the per-step encoder cost.

T2.2 also supports algorithm-diverse training: ``algorithm`` may be one of
``"ppo"``, ``"a2c"``, or ``"recurrent_ppo"`` (sb3-contrib). Recurrent PPO
uses an LSTM head on top of our embedding obs and tends to capture
short-horizon temporal structure that a vanilla MLP misses.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import torch
from stable_baselines3 import A2C, PPO
from stable_baselines3.common.vec_env import DummyVecEnv

from ..env.embedding_env import EmbeddingTradingEnv
from ..env.trading_env import EnvConfig
from ..models.precompute import precompute_embeddings
from ..models.xlstm_lite import XLSTMLite

try:
    from sb3_contrib import RecurrentPPO
except ImportError:  # pragma: no cover
    RecurrentPPO = None  # type: ignore[assignment]

log = logging.getLogger(__name__)


@dataclass
class PPORunConfig:
    total_timesteps: int
    n_steps: int
    batch_size: int
    gae_lambda: float
    gamma: float
    ent_coef: float
    clip_range: float
    learning_rate: float
    curriculum: dict
    # T2.2: which RL algorithm to instantiate. Defaults to vanilla PPO so
    # existing call sites stay backward-compatible.
    algorithm: str = "ppo"


def _make_env(
    close: np.ndarray,
    atr: np.ndarray,
    embeddings: np.ndarray,
    vol_quantile: np.ndarray,
    env_cfg: EnvConfig,
    train_idx: np.ndarray,
    seed: int,
    regime_posterior: np.ndarray | None = None,
):
    def thunk():
        return EmbeddingTradingEnv(
            close=close,
            atr=atr,
            embeddings=embeddings,
            vol_quantile=vol_quantile,
            cfg=env_cfg,
            allowed_idx=train_idx,
            seed=seed,
            regime_posterior=regime_posterior,
        )
    return thunk


def train_ppo_run(
    features: pd.DataFrame,
    feature_cols: list[str],
    env_cfg: EnvConfig,
    encoder: XLSTMLite,
    train_idx: np.ndarray,
    run_cfg: PPORunConfig,
    seed: int,
    save_path: str,
    precomputed: dict | None = None,
) -> PPO:
    """Train one PPO run.

    `precomputed` lets callers reuse an already-built embedding matrix
    across many seeds for the same path. Expected keys: close, atr,
    embeddings, vol_quantile.
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    if precomputed is None:
        feats = features[feature_cols].to_numpy(dtype=np.float32)
        embeddings = precompute_embeddings(encoder, feats, seq_len=env_cfg.seq_len)
        close = features["close"].to_numpy(dtype=np.float64)
        atr = features["atr"].to_numpy(dtype=np.float64)
        rv = pd.Series(atr / close).rolling(20, min_periods=1).mean()
        vol_quantile = rv.rank(pct=True).to_numpy()
        precomputed = dict(close=close, atr=atr, embeddings=embeddings, vol_quantile=vol_quantile)

    venv = DummyVecEnv([
        _make_env(
            precomputed["close"],
            precomputed["atr"],
            precomputed["embeddings"],
            precomputed["vol_quantile"],
            env_cfg,
            train_idx,
            seed,
            regime_posterior=precomputed.get("regime_posterior"),
        )
    ])

    algo = (run_cfg.algorithm or "ppo").lower()
    if algo == "ppo":
        model = PPO(
            policy="MlpPolicy",
            env=venv,
            n_steps=run_cfg.n_steps,
            batch_size=run_cfg.batch_size,
            gae_lambda=run_cfg.gae_lambda,
            gamma=run_cfg.gamma,
            ent_coef=run_cfg.ent_coef,
            clip_range=run_cfg.clip_range,
            learning_rate=run_cfg.learning_rate,
            policy_kwargs=dict(net_arch=dict(pi=[128, 64], vf=[128, 64])),
            verbose=0,
            seed=seed,
            device="cpu",
        )
    elif algo == "a2c":
        # A2C does not take batch_size or clip_range; it uses n_steps as the
        # rollout size and updates after each rollout. Use a smaller n_steps
        # for higher update frequency, which is the standard A2C recipe.
        model = A2C(
            policy="MlpPolicy",
            env=venv,
            n_steps=max(8, run_cfg.n_steps // 8),
            gae_lambda=run_cfg.gae_lambda,
            gamma=run_cfg.gamma,
            ent_coef=run_cfg.ent_coef,
            learning_rate=run_cfg.learning_rate,
            policy_kwargs=dict(net_arch=dict(pi=[128, 64], vf=[128, 64])),
            verbose=0,
            seed=seed,
            device="cpu",
        )
    elif algo in ("recurrent_ppo", "rppo"):
        if RecurrentPPO is None:
            raise RuntimeError("recurrent_ppo requires sb3-contrib; pip install sb3-contrib")
        model = RecurrentPPO(
            policy="MlpLstmPolicy",
            env=venv,
            n_steps=run_cfg.n_steps,
            batch_size=run_cfg.batch_size,
            gae_lambda=run_cfg.gae_lambda,
            gamma=run_cfg.gamma,
            ent_coef=run_cfg.ent_coef,
            clip_range=run_cfg.clip_range,
            learning_rate=run_cfg.learning_rate,
            policy_kwargs=dict(
                net_arch=dict(pi=[64], vf=[64]),
                lstm_hidden_size=64,
                n_lstm_layers=1,
            ),
            verbose=0,
            seed=seed,
            device="cpu",
        )
    else:
        raise ValueError(f"unknown algorithm: {run_cfg.algorithm!r}")

    curriculum = run_cfg.curriculum
    calm_steps = int(run_cfg.total_timesteps * curriculum.get("calm_frac", 0.3))
    mixed_steps = int(run_cfg.total_timesteps * curriculum.get("mixed_frac", 0.3))
    full_steps = run_cfg.total_timesteps - calm_steps - mixed_steps

    stage_plan = [
        (0.33, calm_steps, "calm"),
        (0.66, mixed_steps, "mixed"),
        (1.00, full_steps, "full"),
    ]

    total_done = 0
    for q, steps, tag in stage_plan:
        if steps <= 0:
            continue
        venv.env_method("set_regime", q)
        log.info("seed=%d stage=%s q<=%.2f steps=%d", seed, tag, q, steps)
        model.learn(total_timesteps=steps, reset_num_timesteps=False, progress_bar=False)
        total_done += steps

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    model.save(save_path)
    venv.close()
    return model
