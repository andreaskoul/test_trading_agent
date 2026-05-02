"""Meta-labeling classifier for trade filtering (Lopez de Prado, AFML Ch. 3).

Implements a secondary classifier (M2 in AFML's terminology) that, given the
features observed at the moment a base PPO policy decides to enter a trade,
predicts whether that trade will be profitable after costs. At inference,
the meta-model produces a probability; actions below a chosen threshold are
gated to HOLD, raising precision at the cost of recall.

This attacks the "cost cliff" failure mode documented in the current
evaluation report: the base policy has a real gross edge (permutation
p=0.001) but turnover is too high for the per-trade edge. Filtering out
low-confidence trades lifts realised Sharpe even if total return drops.

Design notes:
- Out-of-fold training per CPCV split: the meta-model used to gate trades
  from split s is trained on trades from splits != s. This prevents the
  meta-model from seeing its own test distribution.
- Features are the 128-dim encoder embedding at the entry bar, concatenated
  with the side (+1 long, -1 short) and the realised volatility quantile.
  No position history or recent PnL is used, to keep gating deterministic
  and replayable.
- Labels are binary: 1 if trade_return > 0, else 0. We use binary rather
  than sign because the barrier exits already bake the TB magnitude into
  `trade_return`; the classifier only needs to predict profitability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    from sklearn.ensemble import HistGradientBoostingClassifier
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "meta_label requires scikit-learn; install with `pip install scikit-learn`"
    ) from exc


def build_trade_features(
    embedding: np.ndarray, direction: int, vol_q: float
) -> np.ndarray:
    """Pack (embedding, direction, vol_q) into a single flat feature row."""
    emb = np.asarray(embedding, dtype=np.float32).reshape(-1)
    return np.concatenate(
        [emb, np.array([float(direction), float(vol_q)], dtype=np.float32)]
    )


@dataclass
class MetaLabelConfig:
    max_iter: int = 200
    max_depth: int = 6
    learning_rate: float = 0.05
    min_samples_leaf: int = 20
    l2_regularization: float = 1.0


class MetaLabelModel:
    """Thin wrapper around sklearn's HistGradientBoostingClassifier.

    Saves/loads use joblib to keep compatibility with the rest of the repo.
    """

    def __init__(self, cfg: Optional[MetaLabelConfig] = None):
        self.cfg = cfg or MetaLabelConfig()
        self._clf: Optional[HistGradientBoostingClassifier] = None
        # Base rate of positive trades in the training set; used as a
        # fallback prediction if the classifier cannot be fit (e.g. because
        # training labels are degenerate - all wins or all losses).
        self._base_rate: float = 0.5

    def fit(self, X: np.ndarray, y: np.ndarray) -> "MetaLabelModel":
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=np.int64)
        if len(X) == 0:
            self._clf = None
            self._base_rate = 0.5
            return self
        self._base_rate = float(np.mean(y)) if len(y) else 0.5
        if len(np.unique(y)) < 2:
            # Degenerate labels - every trade the same class. Skip fit;
            # predict_proba will return the constant base rate.
            self._clf = None
            return self
        self._clf = HistGradientBoostingClassifier(
            max_iter=self.cfg.max_iter,
            max_depth=self.cfg.max_depth,
            learning_rate=self.cfg.learning_rate,
            min_samples_leaf=self.cfg.min_samples_leaf,
            l2_regularization=self.cfg.l2_regularization,
            random_state=0,
        )
        self._clf.fit(X, y)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return probability of profit (class 1) for each row in X."""
        X = np.asarray(X, dtype=np.float32)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        if self._clf is None:
            return np.full(X.shape[0], self._base_rate, dtype=np.float32)
        probs = self._clf.predict_proba(X)
        # predict_proba is (n, 2) with column 1 = positive class
        return probs[:, 1].astype(np.float32)

    @property
    def base_rate(self) -> float:
        return self._base_rate


# ---------------------------------------------------------------------------
# Phase L: LightGBM meta-stack with monotone constraints
# ---------------------------------------------------------------------------

class LightGBMMetaModel:
    """LightGBM meta-labeler with monotone constraints on the side/vol_q.

    Design rationale
    ----------------
    The vanilla ``MetaLabelModel`` (HistGradientBoostingClassifier) makes no
    structural assumptions about features. For the *side* (+1 long / -1 short)
    and *vol_q* features that get concatenated to the encoder embedding, that
    is wasteful: economic priors say profitability is **monotone** in those
    inputs (a higher confidence "long" should not raise the probability of a
    profitable short, and very low or very high vol-quantile bars are
    consistently more cost-sensitive). LightGBM exposes per-feature
    ``monotone_constraints`` that bake these priors into the splits.

    Falls back to the base ``MetaLabelModel`` if ``lightgbm`` is unavailable
    so the import never blocks the rest of the repo.

    Feature layout (must match ``build_trade_features``):
      ``[embedding (E dims), direction (1), vol_q (1)]``
    Default constraint vector is therefore ``[0]*E + [+1, +1]`` which forbids
    direction- or vol-q-driven splits from working *against* a positive-label
    monotone relationship. Set ``vol_q_monotone=-1`` if your prior is the
    opposite (likelier-profitable in low-vol bars).
    """

    def __init__(
        self,
        cfg: Optional[MetaLabelConfig] = None,
        embedding_dim: Optional[int] = None,
        direction_monotone: int = +1,
        vol_q_monotone: int = +1,
    ) -> None:
        self.cfg = cfg or MetaLabelConfig()
        self.embedding_dim = embedding_dim
        self.direction_monotone = int(direction_monotone)
        self.vol_q_monotone = int(vol_q_monotone)
        self._model = None
        self._fallback: Optional[MetaLabelModel] = None
        self._base_rate: float = 0.5

    def _build_constraints(self, n_features: int) -> list[int]:
        emb_dim = self.embedding_dim if self.embedding_dim is not None else n_features - 2
        emb_dim = max(0, min(emb_dim, n_features - 2))
        return [0] * emb_dim + [self.direction_monotone, self.vol_q_monotone] + \
               [0] * (n_features - emb_dim - 2)

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LightGBMMetaModel":
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=np.int64)
        if len(X) == 0 or len(np.unique(y)) < 2:
            self._fallback = MetaLabelModel(self.cfg).fit(X, y)
            self._base_rate = self._fallback.base_rate
            return self
        self._base_rate = float(np.mean(y))

        try:
            import lightgbm as lgb
        except ImportError:
            # No LightGBM installed → use the existing HistGradientBoosting
            # fallback so callers don't need to special-case the deployment env.
            self._fallback = MetaLabelModel(self.cfg).fit(X, y)
            return self

        constraints = self._build_constraints(X.shape[1])
        self._model = lgb.LGBMClassifier(
            n_estimators=self.cfg.max_iter,
            max_depth=self.cfg.max_depth,
            learning_rate=self.cfg.learning_rate,
            min_child_samples=self.cfg.min_samples_leaf,
            reg_lambda=self.cfg.l2_regularization,
            monotone_constraints=constraints,
            random_state=0,
            verbosity=-1,
        )
        self._model.fit(X, y)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=np.float32)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        if self._fallback is not None:
            return self._fallback.predict_proba(X)
        if self._model is None:
            return np.full(X.shape[0], self._base_rate, dtype=np.float32)
        probs = self._model.predict_proba(X)
        return probs[:, 1].astype(np.float32)

    @property
    def base_rate(self) -> float:
        return self._base_rate
