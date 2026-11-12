"""Branch M5: peer graph on 10-K text neighbours. Shared pieces.

* Graph: harness.load_extra("peers"); year y's graph is used for every session of calendar year y (2009 sessions and
  names without a vector: no neighbours, self only). An edge j -> k is live at row t only if k is usable at row t
  (eligible with finite features), so nothing from a later row or an ineligible name enters.
* Features: the five harness characteristics Z (NaN -> 0) and branch C's 24 price characteristics (read-only import
  of C_features/lib.py), cross-sectional ranks over eligible names. All causal (windows ending at row t).
* Peer features: cosine-weighted mean of the neighbours' ranked features at row t, re-ranked across names; gap = own
  rank minus peer mean, re-ranked. Names without live neighbours get 0 (the cross-sectional middle).
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
sys.path.insert(0, TREE)

import importlib.util  # noqa: E402

import harness  # noqa: E402

_spec = importlib.util.spec_from_file_location("c_features_lib", os.path.join(TREE, "C_features", "lib.py"))
clib = importlib.util.module_from_spec(_spec)   # branch C's lib, read-only
_spec.loader.exec_module(clib)

_CACHE = {}


def graph(D):
    """Per row: (nbr (N,10) int, w (N,10) float) indices for the row's calendar year, or None before 2010."""
    if "graph" in _CACHE:
        return _CACHE["graph"]
    P = harness.load_extra("peers")
    yr = np.asarray(D["S"].year)
    G = {}
    for a, y in enumerate(P["years"]):
        nb = P["neighbours"][a].astype(np.int64)
        w = np.where(nb >= 0, np.maximum(P["cosine"][a], 0.0), 0.0).astype(np.float32)
        nb = np.where(nb >= 0, nb, np.arange(nb.shape[0])[:, None])     # pad to self with weight 0
        G[int(y)] = (nb, w)
    out = (yr, G)
    _CACHE["graph"] = out
    return out


def edges(D, rows, ok, uniform=False):
    """For each row in rows: neighbour indices (R,N,10) and live weights (R,N,10) (0 for dead edges)."""
    yr, G = graph(D)
    N = ok.shape[1]
    NB = np.repeat(np.arange(N)[None, :, None], 10, 2).repeat(len(rows), 0)
    W = np.zeros((len(rows), N, 10), np.float32)
    for i, t in enumerate(rows):
        g = G.get(int(yr[t]))
        if g is None:
            continue
        nb, w = g
        live = ok[t][nb] & ok[t][:, None]
        NB[i] = nb
        W[i] = np.where(live, 1.0 if uniform else w, 0.0)
    return NB, W


def rerank(a, ok):
    a = np.where(ok, a, np.nan)
    u = pd.DataFrame(a).rank(axis=1).to_numpy()
    n = np.sum(np.isfinite(a), 1, keepdims=True)
    u = ((u - 0.5) / np.maximum(n, 1) - 0.5) * np.sqrt(12.0)
    return np.where(np.isfinite(u), u, 0.0).astype(np.float32)


def base_design(D, which):
    """which: 'Z5' or 'C24'. Returns X (T,N,K) float32 ranked, NaN -> 0, and ok (T,N)."""
    key = ("base", which)
    if key in _CACHE:
        return _CACHE[key]
    if which == "C24":
        X, ok = clib.design(D, clib.GROUPS["all"], "rank")
    else:
        Z = D["Z"]
        ok = D["elig"] & np.isfinite(Z).all(2)
        X = np.stack([rerank(Z[:, :, k], ok) for k in range(Z.shape[2])], 2)
    _CACHE[key] = (X, ok)
    return X, ok


def peer_design(D, which, cols=None, gap=True, uniform=False):
    """Peer means (and gaps) of base features `cols` (indices into the base design), re-ranked per row.
    Returns P (T,N,k) float32 and has (T,N) bool (name had at least one live neighbour)."""
    key = ("peer", which, tuple(cols) if cols is not None else None, gap, uniform)
    if key in _CACHE:
        return _CACHE[key]
    X, ok = base_design(D, which)
    cols = list(range(X.shape[2])) if cols is None else list(cols)
    T, N = ok.shape
    PM = np.zeros((T, N, len(cols)), np.float32)
    has = np.zeros((T, N), bool)
    for t0 in range(0, T, 256):
        rows = np.arange(t0, min(T, t0 + 256))
        NB, W = edges(D, rows, ok, uniform)
        Xs = X[rows][:, :, cols]                                     # (R,N,k)
        sw = W.sum(2)                                                # (R,N)
        acc = np.zeros((len(rows), N, len(cols)), np.float32)
        for j in range(10):
            idx = NB[:, :, j]                                        # (R,N)
            acc += W[:, :, j, None] * np.take_along_axis(Xs, idx[..., None].repeat(len(cols), 2), 1)
        PM[rows] = np.where(sw[..., None] > 0, acc / np.maximum(sw, 1e-12)[..., None], np.nan)
        has[rows] = sw > 0
    feats = []
    for k in range(len(cols)):
        pm = PM[:, :, k]
        feats.append(rerank(pm, ok & has))
        if gap:
            feats.append(rerank(X[:, :, cols[k]] - pm, ok & has))
    out = (np.stack(feats, 2), has)
    _CACHE[key] = out
    return out


def ridge(Xfn, lam=0.1, fm=True, thursdays_only=False):
    """Ridge candidate on an arbitrary design Xfn(D) -> (X, ok); per-day standardised target (branch C's)."""
    cache = {}

    def fit_predict(D, te, rows, seed):
        X, ok = Xfn(D)
        if te not in cache:
            y = clib.target(D, te)
            m = np.isfinite(y) & ok[: te + 1]
            K = X.shape[2]
            Xm = X[: te + 1] * m[:, :, None]
            A = np.einsum("tnk,tnj->tkj", Xm, Xm, optimize=True).astype(np.float64)
            c = np.einsum("tnk,tn->tk", Xm, np.where(m, y, 0.0).astype(np.float32), optimize=True).astype(np.float64)
            n = m.sum(1).astype(np.float64)
            tr = np.einsum("tkk->t", A) / np.maximum(n, 1)
            days = np.where((n >= 50) & (tr > 0.25 * K * 0.5))[0]   # skip days whose design is mostly empty (no graph)
            if thursdays_only:
                days = days[D["S"][days].weekday == 3]
            if fm:
                bs = [np.linalg.solve(A[d] / n[d] + lam * np.trace(A[d] / n[d]) / K * np.eye(K), c[d] / n[d]) for d in days]
                b = np.mean(bs, 0)
            else:
                Aw, cw = A[days].sum(0) / n[days].sum(), c[days].sum(0) / n[days].sum()
                b = np.linalg.solve(Aw + lam * np.trace(Aw) / K * np.eye(K), cw)
            cache[te] = b
        p = X[rows].astype(np.float64) @ cache[te]
        return np.where(ok[rows], p, np.nan)

    fit_predict.cache = cache
    return fit_predict


def ranked_target(D, te, rows, ok):
    y = np.where(ok[rows], D["y5"][rows], np.nan)
    return rerank(y, np.isfinite(y)), np.isfinite(y)
