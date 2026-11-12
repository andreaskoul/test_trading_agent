"""Branch E (regime-adaptive models): shared, causal building blocks.

Characteristic order (checked empirically): 0 momentum 12-1, 1 one-month reversal, 2 one-week reversal,
3 low volatility, 4 52-week high.

Every model here is  score[t] = Z[t] @ b(t)  with b a 5-vector that depends on the market state at t and on the
weekly sufficient statistics (A_w = Z'Z/n, c_w = Z'y/n) of the Thursdays w <= train_end. Targets after train_end are
never touched (the harness blanks them; we also restrict to rows <= train_end explicitly).
"""
import numpy as np
import pandas as pd

STATE_NAMES = ["trend21", "trend63", "trend252", "vol21", "volchg", "disp21", "corr63"]


def states(D):
    """Daily market-state matrix (T, 7). Row t uses returns up to and including row t only."""
    rm = pd.Series(D["rm"].astype(np.float64))
    r = np.where(D["elig"], D["r"], np.nan).astype(np.float64)
    with np.errstate(all="ignore"):
        disp = pd.Series(np.nanstd(r, 1))
        mean_var = pd.DataFrame(r).rolling(63, min_periods=40).var().mean(1)
        ew = pd.Series(np.nanmean(r, 1))
    vol21 = rm.rolling(21).std()
    vol252 = rm.rolling(252).std()
    S = pd.DataFrame({
        "trend21": rm.rolling(21).sum(), "trend63": rm.rolling(63).sum(), "trend252": rm.rolling(252).sum(),
        "vol21": np.log(vol21), "volchg": np.log(vol21 / vol252),
        "disp21": np.log(disp.rolling(21).mean()),
        "corr63": ew.rolling(63).var() / mean_var,        # about the average pairwise correlation
    })[STATE_NAMES]
    return S.to_numpy()


def zstates(D, te):
    """States standardised with the mean and std of rows <= te (no later row enters the scaling), clipped at 3."""
    S = states(D)
    mu, sd = np.nanmean(S[:te + 1], 0), np.nanstd(S[:te + 1], 0)
    return np.clip((S - mu) / sd, -3, 3), S


def rank_z(y):
    r = pd.Series(y).rank().to_numpy()
    return (r - r.mean()) / r.std()


def weekly_stats(D, te, every=None):
    """Thursdays w <= te with a finite state: rows, A (W,5,5), c (W,5), single-characteristic rank ICs (W,5)."""
    S = D["S"]
    idx = np.arange(len(S))
    tr = np.where((S.weekday == 3) & (idx <= te) & (idx >= 260))[0] if every is None else np.arange(260, te + 1, every)
    rows, A, c, ic = [], [], [], []
    for t in tr:
        m = np.isfinite(D["y5"][t]) & D["elig"][t] & np.isfinite(D["Z"][t]).all(1)
        if m.sum() < 50:
            continue
        X = D["Z"][t][m].astype(np.float64)
        y = rank_z(D["y5"][t][m].astype(np.float64))
        n = len(y)
        rows.append(t); A.append(X.T @ X / n); c.append(X.T @ y / n)
        ic.append([np.corrcoef(rank_z(X[:, j]), y)[0, 1] for j in range(X.shape[1])])
    return np.array(rows), np.array(A), np.array(c), np.array(ic)


def wsolve(A, c, w, lam):
    """Weighted ridge on the weekly statistics: b = (sum w A + lam I)^-1 sum w c, w normalised to sum 1."""
    w = w / w.sum()
    return np.linalg.solve(np.einsum("w,wij->ij", w, A) + lam * np.eye(A.shape[1]), w @ c)


def apply(D, rows, B):
    """Scores Z[rows] @ B[i]; NaN where a characteristic is missing."""
    return np.einsum("rnk,rk->rn", D["Z"][rows].astype(np.float64), B)
