"""Block bootstrap CIs and Monte-Carlo permutation tests for trade returns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .deflated_sr import sharpe_ratio


@dataclass
class BootstrapCI:
    point: float
    lo: float
    hi: float
    samples: int


def _moving_block_bootstrap(
    returns: np.ndarray, block: int, rng: np.random.Generator
) -> np.ndarray:
    n = len(returns)
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, max(n - block + 1, 1), size=n_blocks)
    sample = np.concatenate([returns[s : s + block] for s in starts])
    return sample[:n]


def block_bootstrap_sharpe(
    returns: np.ndarray,
    block: int = 20,
    n_resamples: int = 2000,
    periods_per_year: float = 252.0,
    seed: int = 42,
) -> BootstrapCI:
    rng = np.random.default_rng(seed)
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    if len(returns) < block:
        return BootstrapCI(point=0.0, lo=0.0, hi=0.0, samples=0)
    srs = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        sample = _moving_block_bootstrap(returns, block, rng)
        srs[i] = sharpe_ratio(sample, periods_per_year)
    lo, hi = np.percentile(srs, [2.5, 97.5])
    return BootstrapCI(
        point=sharpe_ratio(returns, periods_per_year),
        lo=float(lo),
        hi=float(hi),
        samples=n_resamples,
    )


def permutation_pvalue_sharpe(
    returns: np.ndarray,
    n_resamples: int = 1000,
    periods_per_year: float = 252.0,
    seed: int = 123,
) -> float:
    """One-sided p-value: P(shuffled SR >= observed SR).

    This tests the null that the *sequence* of returns carries no edge -
    the identity of returns is preserved, only the order is shuffled.
    """
    rng = np.random.default_rng(seed)
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    if len(returns) < 3:
        return 1.0
    observed = sharpe_ratio(returns, periods_per_year)
    ge = 0
    pool = returns.copy()
    for _ in range(n_resamples):
        rng.shuffle(pool)
        if sharpe_ratio(pool, periods_per_year) >= observed:
            ge += 1
    return (ge + 1) / (n_resamples + 1)
