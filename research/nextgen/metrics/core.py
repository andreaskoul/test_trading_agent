"""Independent net-NAV evaluation primitives (research only).

Inputs are aligned fractional simple period returns. No model/backtest execution.
"""
from math import erf, sqrt
import numpy as np


def _series(values, name, minimum=2):
    a = np.asarray(values, dtype=float)
    if a.ndim != 1 or a.size < minimum or not np.isfinite(a).all():
        raise ValueError(f"{name}: expected finite 1D series of length >= {minimum}")
    return a


def excess_sharpe(returns, risk_free, periods_per_year=52):
    """Annualised excess-return Sharpe (NOT the historical raw-return ratio)."""
    a = _series(returns, "returns", 3)
    b = _series(risk_free, "risk_free", 3)
    if a.size != b.size or not np.isfinite(periods_per_year) or periods_per_year <= 0:
        raise ValueError("returns and cash must align and K must be positive")
    d = a - b
    sd = d.std(ddof=1)
    if sd == 0:
        raise ValueError("zero excess return volatility")
    return float(np.sqrt(periods_per_year) * d.mean()/sd)


def compound_return(returns):
    r = _series(returns, "returns", 1)
    if (r <= -1).any():
        raise ValueError("invalid or bankrupt NAV")
    return float(np.expm1(np.log1p(r).sum()))


def max_drawdown(returns):
    r = _series(returns, "returns", 1)
    if (r <= -1).any():
        raise ValueError("invalid or bankrupt NAV")
    nav = np.r_[1.0, np.cumprod(1 + r)]
    return float((nav / np.maximum.accumulate(nav) - 1).min())


def ledger_residual(net, core_gross, book_gross, funding_cost, trading_cost,
                    other_cost=None, tolerance=1e-10):
    """Assert net = core + book - funding - trading - other in NAV units."""
    net = _series(net, "net", 1)
    comps = [_series(v, "ledger component", 1) for v in
             (core_gross, book_gross, funding_cost, trading_cost)]
    other = np.zeros_like(net) if other_cost is None else _series(other_cost,"other",1)
    if not np.isfinite(tolerance) or tolerance < 0 or any(len(v) != len(net) for v in comps+[other]):
        raise ValueError("unaligned ledger or invalid tolerance")
    error = float(np.max(np.abs(net - (comps[0]+comps[1]-comps[2]-comps[3]-other))))
    if error > tolerance:
        raise ValueError(f"NAV reconciliation failed: {error} > {tolerance}")
    return error


def paired_hac_mean_test(differences, lags=4):
    """NW one-sided mean-difference test, NOT a Sharpe-difference test."""
    d = _series(differences, "paired difference", 4)
    n = len(d)
    if not isinstance(lags, int) or lags < 0 or lags >= n:
        raise ValueError("invalid HAC lags")
    centered = d - d.mean()
    v = float(centered @ centered / n)
    for j in range(1, lags+1):
        v += 2 * (1-j/(lags+1)) * float(centered[j:] @ centered[:-j] / n)
    if v <= 0:
        raise ValueError("nonpositive long-run variance")
    se = sqrt(v/n)
    z = float(d.mean()/se)
    return {"n": n, "mean_difference": float(d.mean()), "hac_se": se,
            "z": z, "one_sided_p": 0.5*(1-erf(z/sqrt(2)))}
