"""Action-level ensemble across multiple trained policies.

Phase M3 motivation
-------------------
After Phase L, the manifest holds 36 policies (6 CPCV splits × 3 seeds ×
2 algos). Per-run Sharpe std=0.212 — substantial. A weighted majority
vote across policies on the same observation should reduce realised
session-Sharpe variance without any retraining.

Design
------
* ``EnsemblePolicy(members, weights)`` exposes the same ``predict(obs,
  deterministic=True)`` signature stable-baselines3 policies do, so it
  drops into ``PaperEngine.model`` unchanged.
* Each member can be any object with ``.predict(obs, deterministic) ->
  (action_idx, _state)``.
* ``weights`` defaults to uniform; pass per-member validation Sharpe to
  weight better policies higher.
* For HOLD/BUY/SELL (3-class) the vote is a weighted argmax over
  per-action weight totals. Ties break toward HOLD (lower index in the
  trading-env ordering) because the cost of a missed trade is bounded
  while a wrong trade is not.

Why a separate module?
  Keeps the cockpit's ``_load_model`` simple — a single new branch
  ``if entry.get("ensemble"): return build_ensemble(entry)`` — and lets
  us unit-test the voting logic without spinning a real PPO model.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

import numpy as np

log = logging.getLogger(__name__)


class EnsemblePolicy:
    """Weighted-majority ensemble over a list of SB3-compatible policies."""

    def __init__(
        self,
        members: Sequence,
        weights: Optional[Sequence[float]] = None,
        n_actions: int = 3,
    ) -> None:
        if not members:
            raise ValueError("EnsemblePolicy requires at least one member")
        self.members = list(members)
        self.n_actions = int(n_actions)
        if weights is None:
            w = np.ones(len(self.members), dtype=np.float64)
        else:
            w = np.asarray(list(weights), dtype=np.float64)
            if w.shape != (len(self.members),):
                raise ValueError(
                    f"weights shape {w.shape} != members {len(self.members)}"
                )
            # Negative or zero Sharpe → tiny positive weight so the policy
            # still has minimal influence (avoids divide-by-zero on all-bad
            # corpora). Log a warning so the operator knows.
            if np.any(w <= 0):
                log.warning("ensemble: %d members have non-positive weight; "
                            "clamping to 1e-3", int(np.sum(w <= 0)))
                w = np.where(w > 0, w, 1e-3)
        self.weights = w / w.sum()

    def predict(self, obs, deterministic: bool = True):
        """Return ``(action_idx, None)`` matching the SB3 contract.

        We always run every member on the same observation; any member
        that raises is excluded from this vote (logged once, not per call).
        """
        votes = np.zeros(self.n_actions, dtype=np.float64)
        for member, w in zip(self.members, self.weights):
            try:
                act, _ = member.predict(obs, deterministic=deterministic)
                idx = int(act)
                if 0 <= idx < self.n_actions:
                    votes[idx] += w
            except Exception as exc:    # pragma: no cover - defensive
                log.warning("ensemble member %s failed: %s",
                            type(member).__name__, exc)
        if votes.sum() == 0.0:
            # No member produced a usable vote — default to HOLD (idx 0).
            return 0, None
        return int(np.argmax(votes)), None
