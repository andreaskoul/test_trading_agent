"""Branch N2: FINRA daily short volume on top of the frozen MASTER 5-day scores.

All features are causal: rolling windows over sessions ending at row t. Cross-sectional ranks use row t only.
Orientation: every feature is signed so that the registered prior (more shorting -> lower return) means higher = better.
"""
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "3")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "3")
os.environ.setdefault("MKL_NUM_THREADS", "3")

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import harness  # noqa: E402

FEATS = ["f2", "f5", "f60", "dratio", "abn", "abnshort", "abntotal"]
_CACHE = {}


def raw(D):
    """Signed raw short-volume features, sessions x names (float64)."""
    if "raw" in _CACHE:
        return _CACHE["raw"]
    E = harness.load_extra("finra")
    sh = pd.DataFrame(E["short"].astype(np.float64))
    to = pd.DataFrame(E["total"].astype(np.float64))
    ok = np.isfinite(sh) & np.isfinite(to) & (to > 0)
    sh, to = sh.where(ok), to.where(ok)

    def rs(x, n):
        return x.rolling(n, min_periods=max(2, int(0.8 * n))).sum()

    ratio = {n: rs(sh, n) / rs(to, n) for n in (5, 20, 60, 252)}
    daily = sh / to
    F = {
        "f2": -ratio[20],                                  # the validated F2 (minus the 20-session ratio)
        "f5": -ratio[5],
        "f60": -ratio[60],
        "dratio": -(ratio[5] - ratio[60]),                 # recent rise in shorting
        "abn": -(ratio[20] - ratio[252]) / daily.rolling(252, min_periods=200).std(),  # vs its own year
        "abnshort": -np.log(rs(sh, 20) / 20 / (rs(sh, 252) / 252)),   # short volume vs its own history
        "abntotal": -np.log(rs(to, 20) / 20 / (rs(to, 252) / 252)),   # total volume vs its own history (proxy: no shares outstanding)
    }
    F = {k: v.replace([np.inf, -np.inf], np.nan).to_numpy() for k, v in F.items()}
    _CACHE["raw"] = F
    return F


def xrank(a, mask=None):
    """Cross-sectional percentile rank per row, centred to [-0.5, 0.5]; NaN kept."""
    a = np.where(mask, a, np.nan) if mask is not None else a
    return pd.DataFrame(a).rank(axis=1, pct=True).to_numpy() - 0.5


def ranked(D):
    if "ranked" in _CACHE:
        return _CACHE["ranked"]
    F = raw(D)
    R = {k: xrank(v, D["elig"]) for k, v in F.items()}
    R["master"] = xrank(D["master_h5_ref"].astype(np.float64), D["elig"])
    _CACHE["ranked"] = R
    return R


def target_rank(D, rows):
    y = D["y5"][rows].astype(np.float64)
    return xrank(y, D["elig"][rows])


def train_rows(D, te, need_master=True):
    S = D["S"]
    tr = np.where((S.weekday == 3) & (np.arange(len(S)) <= te))[0]
    if need_master:
        R = ranked(D)
        tr = tr[np.isfinite(R["master"][tr]).sum(1) > 50]
    return tr


def design(D, rows, feats, fill=True):
    """Stack [master rank, features] for rows; missing short features filled with 0 (neutral rank) if fill."""
    R = ranked(D)
    X = [R["master"][rows]] + [R[f][rows] for f in feats]
    X = np.stack(X, -1)
    if fill:
        X[..., 1:] = np.where(np.isfinite(X[..., 1:]), X[..., 1:], 0.0)
    return X


def fama_macbeth(D, tr, feats):
    """Per-week OLS of the rank target on [master, feats]; returns mean coefs and their t."""
    X = design(D, tr, feats)
    Y = target_rank(D, tr)
    B = []
    for i in range(len(tr)):
        m = np.isfinite(X[i]).all(1) & np.isfinite(Y[i])
        if m.sum() < 50:
            continue
        Xi = np.column_stack([np.ones(m.sum()), X[i][m]])
        b = np.linalg.lstsq(Xi, Y[i][m], rcond=None)[0][1:]
        B.append(b)
    B = np.array(B)
    return B.mean(0), B.mean(0) / B.std(0, ddof=1) * np.sqrt(len(B))


def feature_ic(D, tr, f):
    R = ranked(D)
    Y = target_rank(D, tr)
    ics = []
    for i, t in enumerate(tr):
        x = R[f][t]
        m = np.isfinite(x) & np.isfinite(Y[i])
        if m.sum() < 50:
            continue
        ics.append(np.corrcoef(x[m], Y[i][m])[0, 1])
    ics = np.array(ics)
    return float(ics.mean()), float(ics.mean() / ics.std(ddof=1) * np.sqrt(len(ics))), len(ics)


def combine(D, rows, w_master, feats, w_feats):
    """Linear combination of ranks; NaN where MASTER has no score (same names as the base)."""
    X = design(D, rows, feats)
    out = w_master * X[..., 0] + sum(w * X[..., j + 1] for j, w in enumerate(w_feats))
    return np.where(np.isfinite(X[..., 0]), out, np.nan)
