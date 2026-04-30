"""Live statistical-confidence helpers for the cockpit.

The validation module already exposes the heavy machinery (DSR, block
bootstrap, PSR) in offline form. This module wraps them in a thin
``LiveStats`` class with a small ring-buffer cache so the cockpit can
poll cheaply per WebSocket tick without recomputing on every call.

Why a cache?
  ``bootstrap_pvalue_sharpe`` runs 2000 block resamples per call. Even
  with a 60-trade window that's ~0.3-0.6s on commodity CPU. The cockpit
  fires WebSocket ticks every bar, but stats only change on closed
  trades — so we keep the result keyed by ``len(returns)`` and
  invalidate when a new trade arrives.

Public API
----------
``LiveStats(annualisation_factor, bootstrap_block, bootstrap_resamples)``
``.compute(returns) -> dict`` — returns the structured payload for
``GET /api/paper/stats`` and the WebSocket ``stats`` channel.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .bootstrap import block_bootstrap_sharpe, bootstrap_pvalue_sharpe
from .deflated_sr import (
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
    sharpe_ratio,
)


@dataclass
class LiveStatsResult:
    """Structured result; serialise to JSON via ``asdict``."""

    n_trades: int
    sharpe: float
    dsr: float                  # Deflated Sharpe (Bailey & Lopez de Prado)
    psr_vs_zero: float          # P(true SR > 0)
    boot_p: float               # Block-bootstrap p-value vs H0: E[r] <= 0
    boot_lo: float              # 2.5th-percentile Sharpe under bootstrap
    boot_hi: float              # 97.5th-percentile Sharpe under bootstrap
    ann_factor: float

    def to_dict(self) -> dict:
        return {
            "n_trades": int(self.n_trades),
            "sharpe": float(self.sharpe),
            "dsr": float(self.dsr),
            "psr_vs_zero": float(self.psr_vs_zero),
            "boot_p": float(self.boot_p),
            "boot_lo": float(self.boot_lo),
            "boot_hi": float(self.boot_hi),
            "ann_factor": float(self.ann_factor),
        }


def _empty(n: int, ann: float) -> LiveStatsResult:
    return LiveStatsResult(
        n_trades=n, sharpe=0.0, dsr=0.5, psr_vs_zero=0.5,
        boot_p=1.0, boot_lo=0.0, boot_hi=0.0, ann_factor=ann,
    )


class LiveStats:
    """Compute and cache live statistical-confidence metrics.

    The cache is a 1-slot LRU keyed by ``(n_trades, last_return_hash)``.
    Two consecutive calls with the same returns array return the cached
    result; any change invalidates and recomputes.
    """

    def __init__(
        self,
        annualisation_factor: float = 252.0,
        bootstrap_block: int = 20,
        bootstrap_resamples: int = 2000,
        n_trials_for_dsr: int = 36,
    ) -> None:
        self.ann = float(annualisation_factor)
        self.block = int(bootstrap_block)
        self.resamples = int(bootstrap_resamples)
        self.n_trials = int(n_trials_for_dsr)
        self._cache_key: Optional[tuple[int, float]] = None
        self._cache_val: Optional[LiveStatsResult] = None

    def compute(self, returns) -> LiveStatsResult:
        arr = np.asarray(returns, dtype=float)
        arr = arr[np.isfinite(arr)]
        n = len(arr)
        # Cache key is (n, last_value); cheap and stable across appends.
        last = float(arr[-1]) if n else 0.0
        key = (n, last)
        if self._cache_key == key and self._cache_val is not None:
            return self._cache_val

        if n < max(self.block, 4):
            self._cache_key = key
            self._cache_val = _empty(n, self.ann)
            return self._cache_val

        sr = sharpe_ratio(arr, self.ann)
        dsr_res = deflated_sharpe_ratio(arr, n_trials=self.n_trials,
                                         periods_per_year=self.ann)
        psr0 = probabilistic_sharpe_ratio(arr, sr_benchmark=0.0,
                                          periods_per_year=self.ann)
        ci = block_bootstrap_sharpe(arr, block=self.block,
                                    n_resamples=self.resamples,
                                    periods_per_year=self.ann)
        p = bootstrap_pvalue_sharpe(arr, block=self.block,
                                    n_resamples=self.resamples,
                                    periods_per_year=self.ann)

        result = LiveStatsResult(
            n_trades=n,
            sharpe=float(sr) if math.isfinite(sr) else 0.0,
            dsr=float(dsr_res.deflated_sharpe),
            psr_vs_zero=float(psr0),
            boot_p=float(p),
            boot_lo=float(ci.lo),
            boot_hi=float(ci.hi),
            ann_factor=self.ann,
        )
        self._cache_key = key
        self._cache_val = result
        return result
