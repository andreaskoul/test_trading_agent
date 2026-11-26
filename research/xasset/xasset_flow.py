"""Statistical machinery for the cross-asset information-flow family (PREREG_XASSET.md Amendment 2 = LIT_FLOW.md §7).

Array-level functions only: no file is read here. The hypotheses H1-H6 themselves (which series, which window) are
separate functions in xasset_read.py and run over the read's guarded panel; the gate-time items (frozen H5
bandwidth, the §5.4 failure control) are in xasset_checks.py; the synthetic validation and power simulation are in
xasset_flow_prep.py. Choices the specification leaves open: IMPLEMENTATION_NOTES.md part E.
"""
import math

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import linprog

SEED, DRAWS, MEAN_BLOCK = 20261125, 10000, 12
OOS_START = pd.Timestamp("1980-01-01")
FAMILY_LEVEL = 0.10
REJECT_R2 = 0.0025                 # rejected if the 90 % upper bound of the implied R2 < 0.25 %
PRIOR_R2 = 0.005                   # out-of-window prior R2 ~ 0.5 %
WILD_L = 12                        # wild-bootstrap dependence parameter (weeks); implementation choice
TAU = 0.10
N_PROGRAMME_BASE = 40              # programme count before the family (the 0.10/40 of the xasset power arithmetic)
# "registered": the Amendment 2 null (joint stationary blocks of same-month residual and innovation). "decoupled" is a
# SYNTHETIC-ONLY comparison (u = c v + w; v and w in independent blocks), never used by the read.
NULL_SCHEME = "registered"
TRADING_DAYS = 252


# ===================================================================================== resampling
def stationary_idx(T, draws, rng, mean_block=MEAN_BLOCK):
    p = 1.0 / mean_block
    new = rng.random((draws, T)) < p
    starts = rng.integers(0, T, size=(draws, T))
    idx = np.empty((draws, T), dtype=np.int64)
    idx[:, 0] = starts[:, 0]
    for t in range(1, T):
        idx[:, t] = np.where(new[:, t], starts[:, t], (idx[:, t - 1] + 1) % T)
    return idx


# ===================================================================================== linear Granger (H1-H4)
def _partial(Z, A):
    Q, _ = np.linalg.qr(Z)
    return A - Q @ (Q.T @ A)


def slope_t(y, x, Z):
    """OLS slope and conventional t of x in y ~ [Z, x]; y, x may be (T,) or (T, D) (one column per draw)."""
    yt, xt = _partial(Z, np.asarray(y, float)), _partial(Z, np.asarray(x, float))
    sxx = (xt * xt).sum(0)
    b = (xt * yt).sum(0) / sxx
    e = yt - xt * b
    dof = len(Z) - Z.shape[1] - 1
    se = np.sqrt((e * e).sum(0) / dof / sxx)
    return b, se, b / se


def mean_granger(y, Z, innov, build_x, sign, draws=DRAWS, seed=SEED, dates=None, nonneg_forecast=True):
    """Restricted-model residual bootstrap for one predictor.
    y (T,): target month s = t+1; Z (T, k) incl. constant; innov (P+T+1, q): the predictor's own innovations by month,
    row P+r = month t_r (the predictor's date for y[r]); row P+r+1 = month s_r (the target month); the first P+1 rows
    are kept fixed. build_x(innov[:P+T]) -> x (T,). sign: +1 / -1 (one-sided).
    Null: y* = restricted fit + u*, where the pairs (u_s, v_s) of restricted residual and predictor innovation OF THE
    SAME MONTH s are resampled jointly in stationary blocks (contemporaneous correlation and persistence kept), and x*
    is rebuilt from the resampled innovations: x*_r uses v*_{r-1}, v*_{r-2}, ... ."""
    T = len(y)
    P = len(innov) - T - 1
    x = build_x(innov[:P + T])
    b, se, t = slope_t(y, x, Z)
    br, *_ = np.linalg.lstsq(Z, y, rcond=None)
    u = y - Z @ br
    v = innov[P + 1:P + 1 + T]
    pre = innov[:P + 1]
    rng = np.random.default_rng(seed)
    idx = stationary_idx(T, draws, rng)
    if NULL_SCHEME == "registered":
        ustar = u[idx].T
    else:
        idx2 = stationary_idx(T, draws, rng)
        if getattr(build_x, "indices", False):
            ustar = u[idx2].T
        else:
            c, *_ = np.linalg.lstsq(v, u, rcond=None)
            w = u - v @ c
            ustar = (v[idx] @ c).T + w[idx2].T
    ystar = (Z @ br)[:, None] + ustar                                 # (T, D)
    xs = np.empty((T, draws))
    for d in range(draws):
        xs[:, d] = build_x(np.concatenate([pre, v[idx[d][:T - 1]]]))
    _, _, ts = slope_t(ystar, xs, Z)
    p = float(np.mean(sign * ts >= sign * t))
    xt = _partial(Z, x)
    vx, vy = float(np.var(xt)), float(np.var(y))
    r2 = float(b ** 2 * vx / vy)
    up = max(0.0, sign * b + 1.6449 * se)
    out = {"T": int(T), "beta": float(b), "se": float(se), "t": float(t), "p_one_sided": p, "draws": int(draws),
           "implied_R2": r2, "implied_R2_90pct_upper": float(up ** 2 * vx / vy), "expected_sign": int(sign),
           "std_beta": float(b * math.sqrt(vx / vy)), "std_beta_se": float(se * math.sqrt(vx / vy))}
    if dates is not None:
        out["oos"] = oos_r2(y, Z, x, dates, sign, nonneg_forecast)
    return out


def oos_r2(y, Z, x, dates, sign, nonneg=True, start=OOS_START):
    """Recursive out-of-sample R2 against the restricted model, Campbell-Thompson restrictions: the predictor's
    forecast is replaced by the restricted one when its slope has the wrong sign; forecasts truncated at 0 (equity
    premium targets). Reported by decade; not decisive."""
    dates = pd.DatetimeIndex(dates)
    X = np.column_stack([Z, x])
    fr, fu, rows = [], [], []
    for i in np.flatnonzero(dates >= start):
        if i < 24:
            continue
        br, *_ = np.linalg.lstsq(Z[:i], y[:i], rcond=None)
        bu, *_ = np.linalg.lstsq(X[:i], y[:i], rcond=None)
        r, u = float(Z[i] @ br), float(X[i] @ bu)
        if sign * bu[-1] < 0:
            u = r
        if nonneg:
            r, u = max(r, 0.0), max(u, 0.0)
        fr.append(r), fu.append(u), rows.append(i)
    if not rows:
        return {"months": 0}
    rows = np.array(rows)
    e_r, e_u = y[rows] - np.array(fr), y[rows] - np.array(fu)
    res = {"months": int(len(rows)), "R2_oos": float(1 - (e_u @ e_u) / (e_r @ e_r)), "by_decade": {}}
    dec = (dates[rows].year // 10) * 10
    for d in sorted(set(dec)):
        k = dec == d
        res["by_decade"][f"{d}s"] = float(1 - (e_u[k] @ e_u[k]) / (e_r[k] @ e_r[k]))
    return res


# ===================================================================================== quantile Granger (H6)
def qreg(y, X, tau=TAU):
    n, k = X.shape
    c = np.r_[np.zeros(k), tau * np.ones(n), (1 - tau) * np.ones(n)]
    A = np.hstack([X, np.eye(n), -np.eye(n)])
    bounds = [(None, None)] * k + [(0, None)] * (2 * n)
    r = linprog(c, A_eq=A, b_eq=y, bounds=bounds, method="highs")
    if r.status != 0:
        raise RuntimeError(f"quantile regression failed: {r.message}")
    return r.x[:k]


def rank_score(y, Zr, Xc, tau=TAU, br=None):
    """Rank-score statistic for H0: the slopes of Xc are 0 in the tau-quantile regression of y on [Zr, Xc]."""
    if br is None:
        br = qreg(y, Zr, tau)
    u = y - Zr @ br
    a = tau - (u < -1e-12)
    Xt = _partial(Zr, Xc)
    n = len(y)
    S = Xt.T @ a / math.sqrt(n)
    return float(S @ np.linalg.solve(Xt.T @ Xt / n, S) / (tau * (1 - tau))), br


def quantile_granger(y, Zr, Xc_ext, draws=DRAWS, seed=SEED, tau=TAU, dates=None):
    """Restricted quantile model bootstrap. Xc_ext (T+1, q): the one-month predictor returns, row r = month t_r, row
    r+1 = the target month s_r. The pairs (u_s, x_s) of the same month are resampled jointly in stationary blocks;
    y* = restricted fit + u*; x*_r = the resampled x of row r-1 (x*_0 fixed); refit; rank-score statistic."""
    T = len(y)
    Xc = Xc_ext[:T]
    st, br = rank_score(y, Zr, Xc, tau)
    u = y - Zr @ br
    v = Xc_ext[1:T + 1]
    rng = np.random.default_rng(seed)
    idx = stationary_idx(T, draws, rng)
    fit = Zr @ br
    if NULL_SCHEME != "registered":
        idx2 = stationary_idx(T, draws, rng)
        c, *_ = np.linalg.lstsq(v, u, rcond=None)
        w = u - v @ c
    sims = np.empty(draws)
    for d in range(draws):
        ix = idx[d]
        xs = np.vstack([Xc_ext[:1], v[ix[:T - 1]]])
        us = u[ix] if NULL_SCHEME == "registered" else v[ix] @ c + w[idx2[d]]
        sims[d], _ = rank_score(fit + us, Zr, xs, tau)
    p = float(np.mean(sims >= st))
    bu = qreg(y, np.column_stack([Zr, Xc]), tau)
    out = {"T": int(T), "tau": tau, "rank_score": st, "df": int(Xc.shape[1]), "p": p,
           "p_asymptotic_chi2": float(stats.chi2.sf(st, Xc.shape[1])), "draws": int(draws),
           "slopes": [float(v_) for v_ in bu[Zr.shape[1]:]]}
    if dates is not None:
        out["oos_check_loss_skill"] = oos_quantile(y, Zr, Xc, dates, tau)
    return out


def _check(e, tau):
    return np.sum(e * (tau - (e < 0)))


def oos_quantile(y, Zr, Xc, dates, tau=TAU, start=OOS_START):
    dates = pd.DatetimeIndex(dates)
    X = np.column_stack([Zr, Xc])
    er, eu, rows = [], [], []
    for i in np.flatnonzero(dates >= start):
        if i < 36:
            continue
        br, bu = qreg(y[:i], Zr[:i], tau), qreg(y[:i], X[:i], tau)
        er.append(y[i] - Zr[i] @ br), eu.append(y[i] - X[i] @ bu), rows.append(i)
    if not rows:
        return {"months": 0}
    er, eu = np.array(er), np.array(eu)
    return {"months": len(rows), "skill": float(1 - _check(eu, tau) / _check(er, tau)),
            "note": "1 - check loss (unrestricted) / check loss (restricted); recursive from 1980-01; reported only"}


# ===================================================================================== HSIC with the wild bootstrap (H5)
def sqdist(A):
    A = np.atleast_2d(A.T).T if A.ndim == 1 else A
    s = (A * A).sum(1)
    return np.maximum(s[:, None] + s[None, :] - 2 * A @ A.T, 0.0)


def median_heuristic(A):
    D = np.sqrt(sqdist(A))
    iu = np.triu_indices(len(D), 1)
    return float(np.median(D[iu]))


def _centred_gram(A, sigma):
    K = np.exp(-sqdist(A) / (2 * sigma ** 2))
    n = len(K)
    H = np.eye(n) - 1.0 / n
    return H @ K @ H


def hsic_wild(e, X, sig_e, sig_x, draws=DRAWS, seed=SEED, l=WILD_L):
    """n * HSIC_b(e, X) with Gaussian kernels on standardised inputs, and its wild-bootstrap null for dependent data
    (Chwialkowski-Sejdinovic-Gretton: W_t = exp(-1/l) W_{t-1} + sqrt(1 - exp(-2/l)) N(0,1), centred)."""
    e = (e - e.mean()) / e.std()
    X = (X - X.mean(0)) / X.std(0)
    M = _centred_gram(e[:, None], sig_e) * _centred_gram(X, sig_x)
    n = len(e)
    stat = float(M.sum() / n)
    rng = np.random.default_rng(seed)
    a = math.exp(-1.0 / l)
    sims = np.empty(draws)
    for d0 in range(0, draws, 1000):
        D = min(1000, draws - d0)
        eps = rng.standard_normal((D, n))
        W = np.empty((D, n))
        W[:, 0] = eps[:, 0]
        for t in range(1, n):
            W[:, t] = a * W[:, t - 1] + math.sqrt(1 - a * a) * eps[:, t]
        W -= W.mean(1, keepdims=True)
        sims[d0:d0 + D] = ((W @ M) * W).sum(1) / n
    return {"T": int(n), "nHSIC": stat, "p": float(np.mean(sims >= stat)), "draws": int(draws), "wild_l": l,
            "bandwidths": [sig_e, sig_x]}


# ===================================================================================== absorption-ratio state (H4)
def absorption_ratio(R, window=TRADING_DAYS):
    """Largest-eigenvalue share of the correlation matrix of the trailing `window` daily returns (R: days x 5)."""
    R = np.asarray(R, float)
    n, k = R.shape
    c1 = np.vstack([np.zeros(k), np.cumsum(R, 0)])
    c2 = np.vstack([np.zeros((k, k))[None], np.cumsum(R[:, :, None] * R[:, None, :], 0)])
    s1 = c1[window:] - c1[:-window]
    s2 = c2[window:] - c2[:-window]
    m = s1 / window
    cov = s2 / window - m[:, :, None] * m[:, None, :]
    sd = np.sqrt(np.clip(np.einsum("tii->ti", cov), 1e-18, None))
    corr = cov / (sd[:, :, None] * sd[:, None, :])
    ev = np.linalg.eigvalsh(corr)
    ar = np.full(n, np.nan)
    ar[window - 1:] = ev[:, -1] / k
    return ar


def spike_series(ar, short=15, long=TRADING_DAYS):
    a = pd.Series(ar)
    d = (a.rolling(short).mean() - a.rolling(long).mean()) / a.rolling(long).std()
    return (d >= 1.0).astype(float).where(d.notna()).values


# ===================================================================================== family
def holm(pvals):
    """Holm step-down adjusted p-values over the evaluable set."""
    keys = [k for k, v in pvals.items() if v is not None]
    ps = np.array([pvals[k] for k in keys])
    order = np.argsort(ps)
    m = len(ps)
    adj, run = {}, 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (m - r) * ps[i]))
        adj[keys[i]] = float(run)
    return adj


def verdict(holm_p, oos_r2, r2_upper):
    if holm_p is not None and holm_p <= FAMILY_LEVEL and (oos_r2 is None or oos_r2 > 0):
        return "supported"
    if r2_upper is not None and r2_upper < REJECT_R2:
        return "rejected"
    return "inconclusive"


def posterior_r2(std_beta, se, sign):
    """Normal-normal shrinkage of the standardised slope b (R2 = b^2) towards the prior b0 = sign x sqrt(0.5 %),
    prior sd = |b0| (implementation choice)."""
    b0 = sign * math.sqrt(PRIOR_R2)
    s0 = abs(b0)
    prec = 1 / s0 ** 2 + 1 / se ** 2
    m = (b0 / s0 ** 2 + std_beta / se ** 2) / prec
    return {"prior_R2": PRIOR_R2, "posterior_std_beta": m, "posterior_sd": math.sqrt(1 / prec),
            "posterior_R2": m ** 2 if sign * m > 0 else 0.0}


# ===================================================================================== diagnostics (outside the family)
def forbes_rigobon(eq, comp, crisis):
    """Correlation of equity with a composite in crisis months vs the rest, and the Forbes-Rigobon adjusted crisis
    correlation rho* = rho / sqrt(1 + delta (1 - rho^2)), delta = var_crisis(equity) / var_rest(equity) - 1."""
    j = pd.concat([eq.rename("e"), comp.rename("c"), crisis.rename("k")], axis=1).dropna()
    h, l = j[j.k > 0], j[j.k == 0]
    if len(h) < 6 or len(l) < 6:
        return {"months_crisis": int(len(h))}
    rh, rl = float(h.e.corr(h.c)), float(l.e.corr(l.c))
    delta = float(h.e.var() / l.e.var() - 1)
    return {"months_crisis": int(len(h)), "months_rest": int(len(l)), "rho_rest": rl, "rho_crisis": rh,
            "delta": delta, "rho_crisis_adjusted": rh / math.sqrt(1 + delta * (1 - rh ** 2))}


def var1(Y):
    Y = np.asarray(Y, float)
    X = np.column_stack([np.ones(len(Y) - 1), Y[:-1]])
    B, *_ = np.linalg.lstsq(X, Y[1:], rcond=None)
    E = Y[1:] - X @ B
    return B[1:].T, E.T @ E / (len(E) - X.shape[1])


def diebold_yilmaz(Y, names, H=10):
    """Generalised FEVD spillover from a VAR(1) (Diebold-Yilmaz 2012), horizon H days: total and directional."""
    A, S = var1(Y)
    k = len(names)
    Psi = [np.eye(k)]
    for _ in range(1, H):
        Psi.append(A @ Psi[-1])
    num = sum((P @ S) ** 2 for P in Psi) / np.diag(S)[None, :]
    den = sum(np.diag(P @ S @ P.T) for P in Psi)[:, None]
    th = num / den
    th = th / th.sum(1, keepdims=True)
    off = th - np.diag(np.diag(th))
    return {"total_pct": float(100 * off.sum() / k),
            "from_others_pct": {n: float(100 * off[i].sum()) for i, n in enumerate(names)},
            "to_others_pct": {n: float(100 * off[:, i].sum()) for i, n in enumerate(names)},
            "net_pct": {n: float(100 * (off[:, i].sum() - off[i].sum())) for i, n in enumerate(names)}}


def barunik_krehlik(Y, names, bands=((1, 5), (5, 20), (20, None)), M=512):
    """Frequency-domain connectedness (Barunik-Krehlik 2018) from a VAR(1): bands in days (period)."""
    A, S = var1(Y)
    k = len(names)
    w = np.pi * np.arange(1, M + 1) / M
    f = np.empty((M, k, k))
    g = np.empty((M, k))
    for i, om in enumerate(w):
        Pw = np.linalg.inv(np.eye(k) - A * np.exp(-1j * om))
        PS = Pw @ S
        full = (PS @ Pw.conj().T).real
        g[i] = np.diag(full)
        f[i] = (np.abs(PS) ** 2) / np.diag(S)[None, :] / np.diag(full)[:, None]
    Gam = g / g.sum(0, keepdims=True)
    th_all = (Gam[:, :, None] * f).sum(0)
    norm = th_all.sum(1, keepdims=True)
    out = {}
    period = 2 * np.pi / w
    for lo, hi in bands:
        sel = (period >= lo) & ((period < hi) if hi else True)
        th = (Gam[sel][:, :, None] * f[sel]).sum(0) / norm
        off = th - np.diag(np.diag(th))
        out[f"{lo}-{hi or 'inf'}d"] = {"total_pct": float(100 * off.sum() / k),
                                       "equity_from_others_pct": float(100 * off[0].sum()),
                                       "equity_to_others_pct": float(100 * off[:, 0].sum())}
    return out
