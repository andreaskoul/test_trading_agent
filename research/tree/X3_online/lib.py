"""Branch X3 (within-year updating): shared causal building blocks.

Rebuilt target (protocol ruling): for row d, Y[d] = sum of D["e"] over sessions d+2 .. d+6, demeaned across eligible
names. It is used for a prediction at row t only when d + 6 <= t ("closed"). D["y5"] is never used for fitting; it is
only read on rows <= the first train_end to check that the rebuilt target matches it (check_target).

Every model is score[t] = X[t] @ b(cut), with b computed from per-session sufficient statistics of sessions d <= cut:
  online : cut = t - 6          (every closed window)
  yearly : cut = train_end      (the control: same model, fitted once a year)
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.dirname(HERE))

LAG = 6            # a window of row d closes at row d + 6
_ST = {}


def rebuilt_target(D):
    """(T, N): sum of e over d+2..d+6, demeaned across eligible names of row d; NaN where the window is incomplete."""
    e = D["e"].astype(np.float64)
    T = e.shape[0]
    Y = np.full(e.shape, np.nan)
    acc = np.zeros((T - LAG, e.shape[1]))
    for k in range(2, LAG + 1):
        acc += e[k:T - LAG + k]
    Y[:T - LAG] = acc
    Y = np.where(D["elig"], Y, np.nan)
    with np.errstate(all="ignore"):
        Y = Y - np.nanmean(Y, 1, keepdims=True)
    return Y


def check_target(D, te):
    """Correlation of the rebuilt target with y5 on rows <= te (training rows only)."""
    Y = rebuilt_target(D)[:te + 1]
    y = D["y5"][:te + 1].astype(np.float64)
    m = np.isfinite(Y) & np.isfinite(y) & D["elig"][:te + 1]
    return float(np.corrcoef(Y[m], y[m])[0, 1]), int(m.sum()), int((np.isfinite(y) & D["elig"][:te + 1]).sum())


def _rz(a):
    """Row-wise rank, standardised; NaN stays NaN."""
    r = pd.DataFrame(a).rank(axis=1).to_numpy()
    with np.errstate(all="ignore"):
        return (r - np.nanmean(r, 1, keepdims=True)) / np.nanstd(r, 1, keepdims=True)


def design(D, kind):
    if kind == "Z5":
        X = D["Z"].astype(np.float64)
        ok = D["elig"] & np.isfinite(X).all(2)
        return np.where(ok[:, :, None], X, 0.0).astype(np.float32), ok
    if kind == "C32":                                   # branch C's 24 characteristics + 8 state interactions
        import importlib.util
        spec = importlib.util.spec_from_file_location("c_model", os.path.join(os.path.dirname(HERE), "C_features", "model.py"))
        cm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cm)
        return cm._design(D)
    raise ValueError(kind)


def stats(D, kind="Z5", lam=0.1):
    """Per-session statistics of the rebuilt, rank-standardised target on X. Row d of c/bfm/ic depends on e up to d+6."""
    key = (id(D["e"]), kind, lam)
    if key in _ST:
        return _ST[key]
    X, ok = design(D, kind)
    y = _rz(np.where(ok, rebuilt_target(D), np.nan))
    m = np.isfinite(y)
    n = m.sum(1).astype(np.float64)
    Xm = X * m[:, :, None]
    y0 = np.where(m, y, 0.0).astype(np.float32)
    A = np.einsum("tnk,tnj->tkj", Xm, Xm, optimize=True).astype(np.float64)
    c = np.einsum("tnk,tn->tk", Xm, y0, optimize=True).astype(np.float64)
    good = n >= 50
    nn = np.where(good, n, 1.0)
    A, c = A / nn[:, None, None], c / nn[:, None]
    K = X.shape[2]
    bfm = np.zeros((len(n), K))
    for d in np.where(good)[0]:
        bfm[d] = np.linalg.solve(A[d] + lam * np.trace(A[d]) / K * np.eye(K), c[d])
    # single-column rank ICs (correlation of the column's rank with the target rank)
    ic = np.zeros((len(n), K))
    for j in range(K):
        xr = _rz(np.where(m, X[:, :, j], np.nan))
        with np.errstate(all="ignore"):
            ic[:, j] = np.nan_to_num(np.nanmean(xr * y, 1))
    ic[~good] = 0.0
    out = dict(X=X, ok=ok, A=A, c=c, bfm=bfm, ic=ic, good=good, K=K)
    _ST[key] = out
    return out


def weights(days, cut, window, hl=None, roll=None):
    w = np.ones(len(days))
    if window == "ew":
        w = 0.5 ** ((cut - days) / hl)
    elif window == "roll":
        w = (days > cut - roll).astype(float)
    return w


def coef(st, cut, mode, window="exp", hl=None, roll=None, lam=0.1, eta=None, step=1):
    """Coefficient vector from sessions d <= cut (every `step`-th session counted back from cut)."""
    days = np.where(st["good"][:cut + 1])[0]
    if step > 1:
        days = days[(cut - days) % step == 0]
    w = weights(days, cut, window, hl, roll)
    K = st["K"]
    if w.sum() <= 0:
        return np.zeros(K)
    w = w / w.sum()
    if mode == "pool":
        Aw = np.einsum("d,dij->ij", w, st["A"][days])
        return np.linalg.solve(Aw + lam * np.trace(Aw) / K * np.eye(K), w @ st["c"][days])
    if mode == "fm":
        return w @ st["bfm"][days]
    if mode == "ict":                                   # characteristic timing: weight = trailing mean IC
        return w @ st["ic"][days]
    if mode == "ict_t":                                 # trailing IC t-statistic
        mu = w @ st["ic"][days]
        sd = np.sqrt(np.maximum(w @ (st["ic"][days] - mu) ** 2, 1e-12))
        return mu / sd
    if mode == "hedge":                                 # exponential weights over 2K signed single-column experts
        cum = (weights(days, cut, window, hl, roll)[:, None] * st["ic"][days]).sum(0) / 5.0   # per-week units
        g = np.concatenate([cum, -cum]) * eta
        p = np.exp(g - g.max())
        p = p / p.sum()
        return p[:K] - p[K:]
    raise ValueError(mode)


def make(kind="Z5", online=True, mode="pool", lag=0, **kw):
    """lag: extra sessions of staleness for the online version (diagnostic): cut = t - 6 - lag."""
    lam = kw.get("lam", 0.1)

    def fit_predict(D, train_end, pred_rows, seed=0):
        st = stats(D, kind, lam if mode == "fm" else 0.1)
        rows = np.asarray(pred_rows)
        if online:
            B = np.array([coef(st, int(t) - LAG - lag, mode, **kw) for t in rows])
        else:
            B = np.tile(coef(st, int(train_end), mode, **kw), (len(rows), 1))
        p = np.einsum("rnk,rk->rn", st["X"][rows].astype(np.float64), B)
        return np.where(st["ok"][rows], p, np.nan)

    return fit_predict
