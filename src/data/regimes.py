"""HMM regime model for T2.1 (regime-conditioned policy).

Per the plan's Tier 2 recommendation (see Bauman 2024, PMLR 233), we fit a
3-state Gaussian HMM on `(log_return, realised_vol)` over the training
window of each CPCV encoder group, then emit the 3-dim posterior
P(state | observation) for every bar. At PPO rollout time this posterior
is concatenated to the 128-dim xLSTM embedding so the observation becomes
131-dim, turning the monolithic policy into an implicit mixture of
regime-specific sub-policies.

Key design choices:
- **Fit on train bars only.** The HMM is unsupervised but it still captures
  information about the training window's volatility regimes, so we never
  feed it test bars during fit. Inference on the test block is safe
  because HMM is a filter, not a classifier against test labels.
- **3 states** (calm / trending / volatile) matches the Hudson & Thames
  regime tutorial and the Bauman 2024 setup. We start the covariance as
  "full" to allow correlation between log-return and vol.
- **No BIC sweep** in this first cut - the plan explicitly asks for 3
  states fixed. If Tier 2 needs tuning we can add it later.

The posterior is cached per encoder group at
``artefacts/regimes/hmm_group{N}.pkl`` so subsequent evaluate / finetune
runs reuse the same fit.
"""

from __future__ import annotations

import logging
import os
import pickle
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

try:
    from hmmlearn.hmm import GaussianHMM
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "HMM regime module requires hmmlearn; install with `pip install hmmlearn`"
    ) from exc


log = logging.getLogger(__name__)


@dataclass
class HMMRegimeConfig:
    n_states: int = 3
    covariance_type: str = "full"
    n_iter: int = 100
    tol: float = 1e-3
    vol_window: int = 20
    random_state: int = 0


def _build_hmm_features(close: np.ndarray, vol_window: int) -> np.ndarray:
    """Build the 2D (log_return, realised_vol) feature matrix.

    Uses a rolling std of log returns to approximate realised volatility.
    The first ``vol_window`` bars are padded by back-filling so the array
    has the same length as ``close``.
    """
    close = np.asarray(close, dtype=np.float64)
    log_ret = np.zeros_like(close)
    log_ret[1:] = np.log(close[1:] / np.maximum(close[:-1], 1e-12))
    rv = (
        pd.Series(log_ret)
        .rolling(vol_window, min_periods=1)
        .std(ddof=0)
        .bfill()
        .fillna(0.0)
        .to_numpy()
    )
    feats = np.column_stack([log_ret, rv]).astype(np.float64)
    # Replace any residual NaN / inf so hmmlearn does not crash.
    feats = np.nan_to_num(feats, nan=0.0, posinf=0.0, neginf=0.0)
    return feats


class HMMRegimeModel:
    """Thin wrapper around ``hmmlearn.GaussianHMM`` with persistence."""

    def __init__(self, cfg: Optional[HMMRegimeConfig] = None):
        self.cfg = cfg or HMMRegimeConfig()
        self._hmm: Optional[GaussianHMM] = None

    def fit(self, close: np.ndarray, train_idx: np.ndarray) -> "HMMRegimeModel":
        feats = _build_hmm_features(close, self.cfg.vol_window)
        train_idx = np.asarray(train_idx, dtype=np.int64)
        if len(train_idx) == 0:
            raise ValueError("train_idx is empty")
        X_train = feats[train_idx]
        self._hmm = GaussianHMM(
            n_components=self.cfg.n_states,
            covariance_type=self.cfg.covariance_type,
            n_iter=self.cfg.n_iter,
            tol=self.cfg.tol,
            random_state=self.cfg.random_state,
        )
        self._hmm.fit(X_train)
        return self

    def posterior(self, close: np.ndarray) -> np.ndarray:
        """Compute P(state | x) for every bar. Shape: (n_bars, n_states)."""
        if self._hmm is None:
            raise RuntimeError("HMMRegimeModel.fit must be called first")
        feats = _build_hmm_features(close, self.cfg.vol_window)
        post = self._hmm.predict_proba(feats)
        return post.astype(np.float32)

    # ------------------------------------------------------------------
    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"cfg": self.cfg, "hmm": self._hmm}, f)

    @classmethod
    def load(cls, path: str) -> "HMMRegimeModel":
        with open(path, "rb") as f:
            payload = pickle.load(f)
        obj = cls(payload["cfg"])
        obj._hmm = payload["hmm"]
        return obj

    @property
    def n_states(self) -> int:
        return int(self.cfg.n_states)


def fit_or_load_regime(
    close: np.ndarray,
    train_idx: np.ndarray,
    cache_path: str,
    cfg: Optional[HMMRegimeConfig] = None,
) -> tuple[HMMRegimeModel, np.ndarray]:
    """Fit or load a per-group HMM and return (model, full-bar posterior).

    ``close`` is the full-dataset close series; ``train_idx`` is the
    train-only slice used to fit the HMM. The returned posterior is
    computed on ALL bars so the trading env can index it by global bar
    position.
    """
    if os.path.exists(cache_path):
        log.info("loading cached HMM from %s", cache_path)
        model = HMMRegimeModel.load(cache_path)
    else:
        log.info(
            "fitting %d-state GaussianHMM on %d train bars",
            (cfg or HMMRegimeConfig()).n_states,
            len(train_idx),
        )
        model = HMMRegimeModel(cfg).fit(close, train_idx)
        model.save(cache_path)
    post = model.posterior(close)
    return model, post
