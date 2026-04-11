"""Deflated & Probabilistic Sharpe Ratios (Bailey & Lopez de Prado 2014).

All functions operate on 1-D arrays of per-period returns (already in the
correct units - e.g. daily returns if you want an annualisation factor of
252).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.stats import norm, skew, kurtosis


@dataclass
class DSRResult:
    sharpe: float
    deflated_sharpe: float          # Φ-value: P(SR > SR0 | non-normal adj.)
    psr_vs_zero: float              # Probability observed SR > 0
    expected_max_sr: float          # Expected max SR over N trials under null
    n_obs: int
    n_trials: int
    skew: float
    kurt_excess: float
    min_trl: Optional[float] = None  # Minimum Track Record Length at 95%


EULER_MASCHERONI = 0.5772156649015329


def _annualised(sr: float, periods_per_year: float) -> float:
    return sr * math.sqrt(periods_per_year)


def sharpe_ratio(returns: np.ndarray, periods_per_year: float = 252.0) -> float:
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    if len(returns) < 2 or returns.std(ddof=1) == 0:
        return 0.0
    return float(_annualised(returns.mean() / returns.std(ddof=1), periods_per_year))


def probabilistic_sharpe_ratio(
    returns: np.ndarray,
    sr_benchmark: float = 0.0,
    periods_per_year: float = 252.0,
) -> float:
    """PSR: P(true SR > sr_benchmark) given sample stats incl. skew/kurt."""
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    n = len(returns)
    if n < 4:
        return 0.5
    # Non-annualised SR
    sr_hat = returns.mean() / returns.std(ddof=1) if returns.std(ddof=1) > 0 else 0.0
    # Benchmark in the same (non-annualised) units
    sr_bm = sr_benchmark / math.sqrt(periods_per_year)
    sk = float(skew(returns, bias=False))
    kt = float(kurtosis(returns, fisher=False, bias=False))  # "raw" kurt (3 = normal)
    denom = math.sqrt(max(1e-12, 1 - sk * sr_hat + ((kt - 1) / 4.0) * sr_hat ** 2))
    z = (sr_hat - sr_bm) * math.sqrt(max(n - 1, 1)) / denom
    return float(norm.cdf(z))


def expected_max_sr(n_trials: int, var_trials: float = 1.0) -> float:
    """Approximation to E[max SR_i] for N i.i.d. trials under SR ~ N(0, var)."""
    n = max(int(n_trials), 1)
    if n == 1:
        return 0.0
    # Bailey & Lopez de Prado (2014) Eq. 9 approximation
    inv_n = 1.0 / n
    sr0 = math.sqrt(var_trials) * (
        (1 - EULER_MASCHERONI) * norm.ppf(1 - inv_n)
        + EULER_MASCHERONI * norm.ppf(1 - inv_n * math.exp(-1))
    )
    return float(sr0)


def deflated_sharpe_ratio(
    returns: np.ndarray,
    n_trials: int,
    periods_per_year: float = 252.0,
    var_trials: Optional[float] = None,
) -> DSRResult:
    """Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio.

    Reports Φ-value = P(observed SR is > E[max SR] under null of no skill).
    """
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    n = len(returns)
    ann_sr = sharpe_ratio(returns, periods_per_year)
    if n < 4:
        return DSRResult(
            sharpe=ann_sr,
            deflated_sharpe=0.5,
            psr_vs_zero=probabilistic_sharpe_ratio(returns, 0.0, periods_per_year),
            expected_max_sr=0.0,
            n_obs=n,
            n_trials=n_trials,
            skew=0.0,
            kurt_excess=0.0,
        )

    # Variance of SRs across trials - default to Var(SR under null) ≈ 1/n
    if var_trials is None:
        var_trials = 1.0  # in non-annualised SR units

    sr0_non_ann = expected_max_sr(n_trials, var_trials=var_trials / max(n - 1, 1))
    sr0 = _annualised(sr0_non_ann, periods_per_year)

    # DSR = PSR with the benchmark set to the null expected max
    dsr = probabilistic_sharpe_ratio(returns, sr_benchmark=sr0, periods_per_year=periods_per_year)
    psr0 = probabilistic_sharpe_ratio(returns, sr_benchmark=0.0, periods_per_year=periods_per_year)
    sk = float(skew(returns, bias=False))
    kt_ex = float(kurtosis(returns, fisher=True, bias=False))

    # Minimum Track Record Length at 95% vs 0
    denom_trl = max(ann_sr - 0.0, 1e-9) ** 2
    trl = 1 + (1 - sk * ann_sr / math.sqrt(periods_per_year) + (kt_ex / 4.0) * (ann_sr / math.sqrt(periods_per_year)) ** 2) * (norm.ppf(0.95) ** 2) / denom_trl
    min_trl = float(trl) if ann_sr > 0 else float("inf")

    return DSRResult(
        sharpe=ann_sr,
        deflated_sharpe=dsr,
        psr_vs_zero=psr0,
        expected_max_sr=sr0,
        n_obs=n,
        n_trials=n_trials,
        skew=sk,
        kurt_excess=kt_ex,
        min_trl=min_trl,
    )
