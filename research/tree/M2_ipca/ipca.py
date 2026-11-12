"""Branch M2: Instrumented PCA (Kelly, Pruitt and Su 2019), implemented from the paper (no package).

    x_{i,t+1} = Z_{i,t} Gamma_a + Z_{i,t} Gamma_b f_{t+1} + e

Z: cross-sectional ranks of characteristics in [-0.5, 0.5] over eligible names (missing -> 0, the middle), plus a
constant. x: the 5-session hedged return y5 on Thursdays ("weekly", non-overlapping) or the next-but-one daily hedged
return e[t+2] ("daily"; same entry convention as y5). Estimated by alternating least squares on the managed-portfolio
moments W_t = Z_t'Z_t / n_t, X_t = Z_t'x_t / n_t (each period weighted equally).

Prediction for row t: restricted  s = Z_t Gamma_b lambda,  unrestricted  s = Z_t (Gamma_a + Gamma_b lambda),
lambda = mean of the estimated factors over the training periods.

K selection ("auto"): inside each training set only. The last min(2 years, 1/3) of training periods are held out, the
model is fitted on the rest, and K maximises the out-of-sample predictive R^2 (Kelly-Pruitt-Su definition,
1 - sum (x - Z gamma)^2 / sum x^2). Never by validation-year IC.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

_RANKZ = {}


def rank_chars(D, chars):
    key = (id(D["r"]), chars)
    if key in _RANKZ:
        return _RANKZ[key]
    elig = D["elig"]
    if chars == "Z5":
        A = [D["Z"][:, :, k].astype(np.float64) for k in range(D["Z"].shape[2])]
    else:
        from C_features import lib                               # read-only import
        F = lib.raw_features(D)
        feats = lib.GROUPS["all"][:]
        A = [F[f] for f in feats]
        if chars == "C32":
            st = lib.market_state(D)
            inter = [("rev5", "mvol"), ("erev5", "mvol"), ("rev21", "mvol"), ("erev21", "mvol"), ("rev1", "mvol"),
                     ("mom252", "mvol"), ("rev5", "mret"), ("mom252", "mret")]
    cols = []
    for a in A:
        a = np.where(elig & np.isfinite(a), a, np.nan)
        u = pd.DataFrame(a).rank(axis=1).to_numpy()
        n = np.sum(np.isfinite(a), 1, keepdims=True)
        cols.append(np.where(np.isfinite(u), (u - 0.5) / np.maximum(n, 1) - 0.5, 0.0))
    if chars == "C32":
        idx = {f: i for i, f in enumerate(feats)}
        cols += [cols[idx[f]] * st[s][:, None] for f, s in inter]
    Z = np.stack(cols + [np.ones_like(cols[0])], 2)              # constant last
    _RANKZ[key] = Z
    return Z


def moments(D, Z, te, freq, xnorm=False):
    """Per-period W_t, X_t, sum x^2 / n, n for training periods (rows t <= te with >= 50 names)."""
    S = D["S"]
    T = len(S)
    if freq == "weekly":
        rows = np.where((S.weekday == 3) & (np.arange(T) <= te))[0]
        Y = D["y5"]
    else:
        rows = np.arange(0, te + 1)
        Y = np.full(D["e"].shape, np.nan)
        Y[:-2] = D["e"][2:]
    Ws, Xs, ss, used = [], [], [], []
    for t in rows:
        x = Y[t].astype(np.float64)
        m = D["elig"][t] & np.isfinite(x) & (np.abs(Z[t, :, :-1]).sum(1) > 0)
        n = m.sum()
        if n < 50 or ((np.abs(Z[t, :, :-1]) > 0) & m[:, None]).sum(0).min() < 50:   # warm-up: a characteristic missing
            continue
        z, x = Z[t][m], x[m]
        if xnorm:
            x = np.clip((x - x.mean()) / (x.std() + 1e-12), -3, 3)
        Ws.append(z.T @ z / n)
        Xs.append(z.T @ x / n)
        ss.append(x @ x / n)
        used.append(t)
    return np.array(Ws), np.array(Xs), np.array(ss), np.array(used)


def als(W, X, K, alpha, lam=0.0, iters=300, tol=1e-7):
    """IPCA alternating least squares. Returns Gb (L,K), Ga (L,) or zeros, F (T,K)."""
    T, L, _ = W.shape
    M = X.T @ X / T                                             # second moment of managed portfolios
    ev, V = np.linalg.eigh(M)
    Gb = V[:, ::-1][:, :K].copy()
    Ga = np.zeros(L)
    for it in range(iters):
        # factor step
        R = X - W @ Ga if alpha else X
        A = np.einsum("lk,tlm,mj->tkj", Gb, W, Gb)
        b = np.einsum("lk,tl->tk", Gb, R)
        F = np.linalg.solve(A + 1e-10 * np.eye(K), b[:, :, None])[:, :, 0]
        # Gamma step
        Ft = np.hstack([np.ones((T, 1)), F]) if alpha else F
        Kf = Ft.shape[1]
        FF = np.einsum("tk,tj->tkj", Ft, Ft)
        big = (W.reshape(T, L * L).T @ FF.reshape(T, Kf * Kf)).reshape(L, L, Kf, Kf).transpose(0, 2, 1, 3).reshape(L * Kf, L * Kf)
        rhs = np.einsum("tl,tk->lk", X, Ft).reshape(-1)
        big = big / T
        rhs = rhs / T
        reg = lam * np.trace(big) / (L * Kf) * np.eye(L * Kf)
        G = np.linalg.solve(big + reg, rhs).reshape(L, Kf)
        Ga_new = G[:, 0] if alpha else np.zeros(L)
        Gb_new = G[:, 1:] if alpha else G
        # normalisation: Gb orthonormal, factors orthogonal by descending variance, Ga orthogonal to Gb, mean f >= 0
        Q, Rr = np.linalg.qr(Gb_new)
        F2 = F @ Rr.T
        ev, U = np.linalg.eigh(F2.T @ F2 / T)
        U = U[:, ::-1]
        Gb_new, F2 = Q @ U, F2 @ U
        if alpha:
            proj = Gb_new.T @ Ga_new
            Ga_new = Ga_new - Gb_new @ proj
            F2 = F2 + proj
        sg = np.sign(F2.mean(0)); sg[sg == 0] = 1
        Gb_new, F2 = Gb_new * sg, F2 * sg
        d = max(np.abs(Gb_new - Gb).max(), np.abs(Ga_new - Ga).max())
        Gb, Ga, F = Gb_new, Ga_new, F2
        if d < tol:
            break
    # final factors given final Gamma
    R = X - W @ Ga if alpha else X
    A = np.einsum("lk,tlm,mj->tkj", Gb, W, Gb)
    b = np.einsum("lk,tl->tk", Gb, R)
    F = np.linalg.solve(A + 1e-10 * np.eye(K), b[:, :, None])[:, :, 0]
    return Gb, Ga, F, it + 1


def r2(W, X, ss, gamma):
    """Predictive R^2 of a fixed loading vector gamma over periods (sum over periods of per-name means)."""
    res = ss - 2 * X @ gamma + np.einsum("l,tlm,m->t", gamma, W, gamma)
    return 1 - res.sum() / ss.sum()


def total_r2(W, X, ss, Gb, Ga):
    R = X - W @ Ga
    A = np.einsum("lk,tlm,mj->tkj", Gb, W, Gb)
    b = np.einsum("lk,tl->tk", Gb, R)
    F = np.linalg.solve(A + 1e-10 * np.eye(Gb.shape[1]), b[:, :, None])[:, :, 0]
    fit = W @ Ga + np.einsum("tlm,mk,tk->tl", W, Gb, F)          # Z'Z(Ga + Gb f)/n
    g = Ga[None] + F @ Gb.T                                     # per-period loading
    res = ss - 2 * (X * g).sum(1) + np.einsum("tl,tlm,tm->t", g, W, g)
    return 1 - res.sum() / ss.sum()


def make(chars="Z5", freq="weekly", K="auto", Ks=(1, 3, 5), lam=0.0, xnorm=False, log=None, tag=""):
    """Returns two fit_predict functions sharing one fit per training set: (restricted, unrestricted)."""
    cache = {}

    def fit(D, te):
        k = (id(D["r"]), te)
        if k in cache:
            return cache[k]
        Z = rank_chars(D, chars)
        W, X, ss, used = moments(D, Z, te, freq, xnorm)
        Tn = len(used)
        sel = {}
        for alpha in (False, True):
            if K == "auto":
                nh = min(int(round(Tn / 3)), 104 if freq == "weekly" else 504)
                a, h = slice(0, Tn - nh), slice(Tn - nh, Tn)
                rr = {}
                for kk in Ks:
                    Gb, Ga, F, _ = als(W[a], X[a], kk, alpha, lam)
                    g = Ga + Gb @ F.mean(0)
                    rr[kk] = {"pred_r2": float(r2(W[h], X[h], ss[h], g)), "total_r2": float(total_r2(W[h], X[h], ss[h], Gb, Ga))}
                kb = max(Ks, key=lambda q: rr[q]["pred_r2"])
                sel[alpha] = (kb, rr)
            else:
                sel[alpha] = (K, {})
        out = {}
        for alpha in (False, True):
            Gb, Ga, F, it = als(W, X, sel[alpha][0], alpha, lam)
            out[alpha] = Ga + Gb @ F.mean(0)
            if log:
                with open(log, "a") as f:
                    f.write(json.dumps({"tag": tag, "te": int(te), "date": str(D["S"][te].date()), "alpha": alpha,
                                        "K": int(sel[alpha][0]), "inner": {str(q): v for q, v in sel[alpha][1].items()},
                                        "iters": int(it), "periods": int(Tn),
                                        "in_sample_total_r2": float(total_r2(W, X, ss, Gb, Ga)),
                                        "in_sample_pred_r2": float(r2(W, X, ss, out[alpha])),
                                        "lambda": F.mean(0).tolist(), "lambda_t": (F.mean(0) / (F.std(0) + 1e-18) * np.sqrt(len(F))).tolist(),
                                        "alpha_norm": float(np.linalg.norm(Ga))}) + "\n")
        cache[k] = (Z, out)
        return cache[k]

    def mk(alpha):
        def fit_predict(D, te, rows, seed):
            Z, out = fit(D, te)
            p = Z[rows] @ out[alpha]
            return np.where(D["elig"][rows], p, np.nan)
        return fit_predict

    return mk(False), mk(True)
