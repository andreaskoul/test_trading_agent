"""Finetune the best PPO policy with a lower learning rate on full data."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv

from ..env.trading_env import EnvConfig
from ..models.xlstm_lite import XLSTMLite
from .train_ppo import _make_env

log = logging.getLogger(__name__)


@dataclass
class FinetuneConfig:
    timesteps: int
    lr: float
    ent_coef: float


def finetune_policy(
    precomputed: dict,
    env_cfg: EnvConfig,
    train_idx: np.ndarray,
    base_policy_path: str,
    cfg: FinetuneConfig,
    save_path: str,
    seed: int = 42,
) -> PPO:
    venv = DummyVecEnv([
        _make_env(
            precomputed["close"],
            precomputed["atr"],
            precomputed["embeddings"],
            precomputed["vol_quantile"],
            env_cfg,
            train_idx,
            seed,
        )
    ])
    model = PPO.load(base_policy_path, env=venv, device="cpu")
    model.learning_rate = cfg.lr
    model.ent_coef = cfg.ent_coef

    venv.env_method("set_regime", 1.0)
    model.learn(total_timesteps=cfg.timesteps, reset_num_timesteps=False, progress_bar=False)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    model.save(save_path)
    venv.close()
    return model
