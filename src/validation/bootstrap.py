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
    Element-wise shuffle; anti-conservative when returns have
    autocorrelation (use block_permutation_pvalue_sharpe in that case).
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


def bootstrap_pvalue_sharpe(
    returns: np.ndarray,
    block: int = 20,
    n_resamples: int = 2000,
    periods_per_year: float = 252.0,
    seed: int = 7,
) -> float:
    """Block-bootstrap p-value: P(SR <= 0 | observed sample).

    The PROPER replacement for permutation_pvalue_sharpe for edge
    detection. Sharpe ratio is permutation-invariant (mean and std are
    order-independent), so the classical permutation test is degenerate
    — it reports p ≈ 1 trivially because every shuffle produces the
    same SR (up to floating-point precision, where ties count as >=).

    Instead, we use a block bootstrap (which DOES change the sample by
    drawing with replacement). Under the null H0: E[r] <= 0, we centre
    the returns to enforce H0, block-bootstrap-resample, and compute
    the fraction of resampled SRs >= observed SR. This is the Politis
    & Romano (1994) stationary-bootstrap hypothesis test adapted for a
    Sharpe statistic.

    Low p-value (e.g. < 0.05) = strong evidence that the observed edge
    is not attributable to the centred-sample null.
    """
    rng = np.random.default_rng(seed)
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    n = len(returns)
    if n < block or returns.std(ddof=1) == 0:
        return 1.0
    observed = sharpe_ratio(returns, periods_per_year)
    if observed <= 0:
        return 1.0
    # Centre to impose H0: mean return is zero
    centred = returns - returns.mean()
    ge = 0
    for _ in range(n_resamples):
        sample = _moving_block_bootstrap(centred, block, rng)
        if sharpe_ratio(sample, periods_per_year) >= observed:
            ge += 1
    return (ge + 1) / (n_resamples + 1)


def acf_lag1(returns: np.ndarray) -> float:
    """Lag-1 autocorrelation of trade returns.

    Diagnostic for the permutation test: if |ACF(1)| > 0.05 the returns
    have sequential dependence and element-wise shuffle is
    anti-conservative; block_permutation_pvalue_sharpe should be used
    instead. Returns 0.0 for degenerate inputs.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 3:
        return 0.0
    r_dm = r - r.mean()
    denom = float(np.dot(r_dm, r_dm))
    if denom < 1e-14:
        return 0.0
    return float(np.dot(r_dm[:-1], r_dm[1:]) / denom)


def block_permutation_pvalue_sharpe(
    returns: np.ndarray,
    block_size: int = 8,
    n_resamples: int = 1000,
    periods_per_year: float = 252.0,
    seed: int = 123,
) -> float:
    """One-sided p-value: P(block-permuted SR >= observed SR).

    Permutes contiguous BLOCKS of trades rather than individual trades,
    preserving within-block serial correlation. Appropriate when
    |ACF(1)| > 0.05, which is typical under momentum / trend-following
    strategies (macro-regime clustering of wins and losses).

    block_size=8 ≈ 1 trading day at ~8 trades/day on 60m MGC.
    Mirrors _moving_block_bootstrap() but permutes (no replacement), so
    the marginal distribution of individual returns is preserved
    exactly.
    """
    rng = np.random.default_rng(seed)
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    n = len(returns)
    if n < block_size:
        return 1.0
    observed = sharpe_ratio(returns, periods_per_year)
    # Pre-slice blocks ONCE outside the loop. With 55k trades and
    # block_size=8 -> 6875 blocks; 1000 resamples -> 6.9M slice ops if
    # done inside the loop. Pre-slicing is ~100x faster.
    block_starts = list(range(0, n, block_size))
    blocks = [returns[s : s + block_size] for s in block_starts]
    n_blocks = len(blocks)
    idx = np.arange(n_blocks, dtype=np.intp)
    ge = 0
    for _ in range(n_resamples):
        rng.shuffle(idx)
        permuted = np.concatenate([blocks[i] for i in idx])
        if sharpe_ratio(permuted, periods_per_year) >= observed:
            ge += 1
    return (ge + 1) / (n_resamples + 1)
