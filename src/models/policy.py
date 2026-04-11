"""Stable-Baselines3 features extractor that wraps a frozen xLSTM-lite encoder.

The feature extractor receives the raw (seq_len, n_features) observation
and returns the 128-dim embedding produced by the frozen encoder's
`encode()` method. Gradients do not flow into the encoder - this is the
decoupled-representation training regime advocated by Stooke et al. 2021.
"""

from __future__ import annotations

import gymnasium as gym
import torch
import torch.nn as nn
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor

from .xlstm_lite import XLSTMLite


class XLSTMFeaturesExtractor(BaseFeaturesExtractor):
    def __init__(self, observation_space: gym.spaces.Box, encoder: XLSTMLite):
        features_dim = encoder.cfg.hidden_size
        super().__init__(observation_space, features_dim=features_dim)
        self.encoder = encoder
        # Freeze encoder parameters
        for p in self.encoder.parameters():
            p.requires_grad = False
        self.encoder.eval()

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            emb = self.encoder.encode(observations)
        return emb.float()


def build_policy_kwargs(encoder: XLSTMLite) -> dict:
    return dict(
        features_extractor_class=XLSTMFeaturesExtractor,
        features_extractor_kwargs=dict(encoder=encoder),
        net_arch=dict(pi=[128, 64], vf=[128, 64]),
    )
