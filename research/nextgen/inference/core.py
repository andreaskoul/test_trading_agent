"""Pure research-only inferential safeguards. No market data or backtest IO.

A percentile circular-block CI is a diagnostic, NOT Ledoit-Wolf studentized
bootstrap and NOT a formal production hypothesis test. Samples must not have
been selected by inspecting the same evaluation dates.
"""
import numpy as np


def _returns(values, name, n=None):
    r = np.asarray(values, dtype=float)
    if r.ndim != 1 or r.size < 52 or not np.all(np.isfinite(r)):
        raise ValueError(f"{name} needs >=52 finite aligned fractional returns")
    if n is not None and len(r) != n:
        raise ValueError("unmatched sample lengths")
    if np.any(r <= -1):
        raise ValueError("bankruptcy or invalid NAV; cannot compute continuous strategy Sharpe")
    return r


def _sharpe(excess, annualisation):
    std = np.std(excess, ddof=1)
    if not np.isfinite(std) or std <= 1e-14:
        raise ValueError("excess return variance is zero or degenerate")
    return np.sqrt(annualisation) * np.mean(excess) / std


def _circular_indices(n, block_length, rng):
    starts = rng.integers(0, n, size=(n + block_length - 1) // block_length)
    idx = (starts[:, None] + np.arange(block_length)[None, :]) % n
    return idx.reshape(-1)[:n]


def paired_sharpe_block_ci(candidate, control, cash, *, block_length=8,
                           draws=1000, seed=0, confidence=0.95,
                           periods_per_year=52):
    """Paired circular moving-block percentile CI for excess-Sharpe *difference*.

    Resamples shared indices on candidate, control, and cash simultaneously.
    CI is exploratory; dependent data and small samples impair coverage.
    Does not adjust for strategy selection or provide a p-value.
    """
    a = _returns(candidate, "candidate")
    b = _returns(control, "control", len(a))
    c = _returns(cash, "cash", len(a))
    n = len(a)
    if (isinstance(block_length, bool) or not isinstance(block_length, int)
        or block_length < 1 or block_length * 4 > n):
        raise ValueError("block_length must permit >=4 blocks")
    if isinstance(draws, bool) or not isinstance(draws, int) or draws < 200:
        raise ValueError("draws must be integer >=200")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if not np.isfinite(confidence) or not 0 < confidence < 1:
        raise ValueError("confidence must be strictly between 0 and 1")
    if not np.isfinite(periods_per_year) or periods_per_year <= 0:
        raise ValueError("invalid annualisation")
    obs = float(_sharpe(a-c, periods_per_year)-_sharpe(b-c, periods_per_year))
    rng = np.random.default_rng(seed)
    boot = np.empty(draws, dtype=float)
    for j in range(draws):
        idx = _circular_indices(n, block_length, rng)
        boot[j] = _sharpe((a-c)[idx], periods_per_year)-_sharpe((b-c)[idx], periods_per_year)
    q = (1-confidence)/2
    lo, hi = np.quantile(boot,[q,1-q])
    return {"difference":obs, "lower":float(lo), "upper":float(hi),
            "block_length":block_length, "bootstrap_draws":draws,
            "confidence":confidence, "observations":n, "seed":seed,
            "method":"paired circular moving-block percentile (exploratory)"}


def holm_adjust(p_values):
    """Holm step-down FWER correction, valid for any dependence IF inputs are valid p-values.

    The array must represent a fully pre-registered testing family. Excluding
    previously tried ideas invalidates claims of family-wise error control.
    """
    p = np.asarray(p_values, dtype=float)
    if p.ndim != 1 or len(p)==0 or not np.isfinite(p).all() or ((p<0)|(p>1)).any():
        raise ValueError("nonempty vector of p-values in [0,1] required")
    n = len(p)
    order = np.argsort(p,kind="stable")
    sorted_adj = np.maximum.accumulate(np.minimum(1.0,(n - np.arange(n))*p[order]))
    out = np.empty_like(sorted_adj)
    out[order] = sorted_adj
    return out
