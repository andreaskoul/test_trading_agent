"""Branch E best configuration (E13): state-kernel ridge with a momentum-off-in-panic rule. Self-contained.

score[t] = Z[t] @ b(t), where
  * b(t) is a ridge fit on the Thursdays <= train_end (target: cross-sectional rank of y5, standardised), with each
    past week weighted by a Gaussian kernel on the distance between its market state and the state at t;
    state = (market 252-session return, log 21-session market volatility, 63-session average-correlation proxy),
    standardised with rows <= train_end only;
  * the momentum coefficient is set to zero when the market's 252-session return is negative and its 21-session
    volatility is above the 67th percentile of rows <= train_end.
Deterministic: the seed is ignored. Characteristic order: momentum 12-1, 1-month reversal, 1-week reversal,
low volatility, 52-week high.
"""
import numpy as np
import pandas as pd

H, LAM, VOL_Q, MOM = 1.0, 0.1, 0.67, 0


def _states(D):
    """(T, 3): trend252, log vol21, corr63. Row t uses returns up to and including row t."""
    rm = pd.Series(D["rm"].astype(np.float64))
    r = np.where(D["elig"], D["r"], np.nan).astype(np.float64)
    with np.errstate(all="ignore"):
        mean_var = pd.DataFrame(r).rolling(63, min_periods=40).var().mean(1)
        ew = pd.Series(np.nanmean(r, 1))
    return np.c_[rm.rolling(252).sum(), np.log(rm.rolling(21).std()), ew.rolling(63).var() / mean_var]


def _rank_z(y):
    r = pd.Series(y).rank().to_numpy()
    return (r - r.mean()) / r.std()


def fit_predict(D, train_end, pred_rows, seed=0):
    S = D["S"]
    idx = np.arange(len(S))
    raw = _states(D)
    mu, sd = np.nanmean(raw[:train_end + 1], 0), np.nanstd(raw[:train_end + 1], 0)
    Zs = np.clip((raw - mu) / sd, -3, 3)
    tr, A, c = [], [], []
    for t in np.where((S.weekday == 3) & (idx <= train_end) & (idx >= 260))[0]:
        m = np.isfinite(D["y5"][t]) & D["elig"][t] & np.isfinite(D["Z"][t]).all(1)
        if m.sum() < 50 or not np.isfinite(Zs[t]).all():
            continue
        X, y = D["Z"][t][m].astype(np.float64), _rank_z(D["y5"][t][m].astype(np.float64))
        tr.append(t); A.append(X.T @ X / len(y)); c.append(X.T @ y / len(y))
    tr, A, c = np.array(tr), np.array(A), np.array(c)
    thr = np.nanquantile(raw[:train_end + 1, 1], VOL_Q)
    B = []
    for t in pred_rows:
        w = np.exp(-((Zs[tr] - Zs[t]) ** 2).sum(1) / (2 * H * H * Zs.shape[1]))
        w = w / w.sum()
        b = np.linalg.solve(np.einsum("w,wij->ij", w, A) + LAM * np.eye(A.shape[1]), w @ c)
        if raw[t, 0] < 0 and raw[t, 1] > thr:
            b[MOM] = 0.0
        B.append(b)
    return np.einsum("rnk,rk->rn", D["Z"][pred_rows].astype(np.float64), np.array(B))
