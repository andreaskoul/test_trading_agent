"""Layer 6 T2 (research/tree/PREREG.md, "Layer 6"): latent regimes with state-dependent means.

Gaussian HMM (full covariance, own EM; hmmlearn/statsmodels not installed, nothing pip-installed) and a two-regime
Markov-switching regression, both with expanding-window refits every 13 weeks, 20 random starts, and the Hamilton
FILTER only for the trading signal.

Timing (strict "known at t"): week k has decision session t_k (Thursday close) and book return b_k held from
close(t_k+1) to close(t_{k+1}+1) (construct/L4 simulator periods). Observation y_j is aligned to period j and uses data
through session c_j = t_{j+1}+1 only. At decision k only observations with c_j <= t_k are used (normally j <= k-2), and
the state forecast for period k is p_{j_last} A^(k - j_last).
"""
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
COST, GROSS = 5e-4, 0.6
REFIT, STARTS, BURN = 13, 20, 104
MIN_STD_OBS = 13            # expanding mean/sd need at least this many observations
COV_FLOOR = 1e-3            # on standardised data
MAX_IT, TOL = 500, 1e-6


# ---------------------------------------------------------------- weekly series from a panel
def periods(S, years):
    """Same Thursday periods as strategies.periods (construct / L4 simulator)."""
    th = np.where((S.weekday == 3) & (S.year >= min(years)) & (S.year <= max(years)))[0]
    out = []
    for k in range(len(th) - 1):
        t, t2 = th[k], th[k + 1]
        if t2 + 2 > len(S):
            break
        out.append((t, t2))
    return out


def weekly_states(d, score, book, years):
    """Per period j: decision row t_j, known-at row c_j = t_{j+1}+1, and the raw 5-vector inputs + IC13 regressor.

    book: DataFrame from the L4 simulator (index = S[t_j]) with column 'book'.
    """
    S, r, rm, elig = d["S"], d["r"], d["rm"], d["elig"]
    per = periods(S, years)
    assert len(per) == len(book), (len(per), len(book))
    t_ = np.array([p[0] for p in per])
    c_ = np.array([p[1] + 1 for p in per])
    assert (S[t_] == book.index).all()
    lm = np.concatenate([[0], np.cumsum(np.log1p(np.nan_to_num(rm)))])
    spy_ret = np.array([np.expm1(lm[c + 1] - lm[t + 2]) for t, c in zip(t_, c_)])   # close(t+1) -> close(c)
    rmz = np.nan_to_num(rm)
    rv21 = np.array([np.log(np.std(rmz[c - 20: c + 1], ddof=1) * math.sqrt(252)) for c in c_])
    lr = np.vstack([np.zeros((1, r.shape[1])), np.cumsum(np.log1p(np.nan_to_num(r)), 0)])
    disp = []
    for c in c_:
        r5 = np.expm1(lr[c + 1] - lr[c - 4])
        m = elig[c] & np.isfinite(r[c - 4: c + 1]).all(0)
        disp.append(float(np.std(r5[m], ddof=1)))
    disp = np.array(disp)
    # realised weekly IC of the score at t_j: Spearman with y5[t_j] (returns sessions t_j+2..t_j+6, realised at t_j+6)
    ic = np.full(len(t_), np.nan)
    for j, t in enumerate(t_):
        m = np.isfinite(score[t]) & np.isfinite(d["y5"][t]) & elig[t]
        if m.sum() >= 50:
            ic[j] = pd.Series(score[t][m]).corr(pd.Series(d["y5"][t][m]), method="spearman")
    ic_real = t_ + 6

    def ic13(cut):
        v = ic[(ic_real <= cut) & np.isfinite(ic)]
        return float(v[-13:].mean()) if len(v) >= 13 else np.nan
    ic13_obs = np.array([ic13(c) for c in c_])      # IC13 known at c_j (component of y_j)
    ic13_dec = np.array([ic13(t) for t in t_])      # IC13 known at decision t_j (MSR regressor)
    b = book["book"].to_numpy().astype(float)
    b[~np.isfinite(b)] = np.nan
    b[np.array([np.isfinite(score[t]).sum() < 30 for t in t_])] = np.nan     # no book that week
    return pd.DataFrame({"t": t_, "c": c_, "b": b, "spy": spy_ret, "lrv21": rv21, "disp": disp, "ic": ic,
                         "ic13": ic13_obs, "ic13_dec": ic13_dec}, index=book.index)


def expanding_z(x, min_obs=MIN_STD_OBS):
    """z_j = (x_j - mean(x_1..x_j)) / sd(x_1..x_j), over finite values; nan before min_obs observations."""
    s = pd.Series(x)
    m = s.expanding(min_periods=min_obs).mean()
    sd = s.expanding(min_periods=min_obs).std(ddof=1)
    return ((s - m) / sd).to_numpy(), m.to_numpy(), sd.to_numpy()


# ---------------------------------------------------------------- Gaussian HMM, full covariance
def _logpdf(Y, mu, cov):
    T, D = Y.shape
    K = len(mu)
    out = np.empty((T, K))
    for k in range(K):
        L = np.linalg.cholesky(cov[k])
        z = np.linalg.solve(L, (Y - mu[k]).T)
        out[:, k] = -0.5 * (z * z).sum(0) - np.log(np.diag(L)).sum() - 0.5 * D * math.log(2 * math.pi)
    return out


def _fwd(logB, A, p0):
    T, K = logB.shape
    mx = logB.max(1, keepdims=True)
    B = np.exp(logB - mx)
    al = np.empty((T, K))
    c = np.empty(T)
    a = p0 * B[0]
    c[0] = a.sum()
    al[0] = a / c[0]
    for t in range(1, T):
        a = (al[t - 1] @ A) * B[t]
        c[t] = a.sum()
        al[t] = a / c[t]
    return al, c, B, float(np.log(c).sum() + mx.sum())


def _bwd(B, A, c):
    T, K = B.shape
    be = np.empty((T, K))
    be[-1] = 1.0
    for t in range(T - 2, -1, -1):
        be[t] = A @ (B[t + 1] * be[t + 1]) / c[t + 1]
    return be


def hmm_fit_one(Y, K, rng):
    T, D = Y.shape
    mu = Y[rng.choice(T, K, replace=False)] + 0.1 * rng.standard_normal((K, D))
    C0 = np.cov(Y.T) + COV_FLOOR * np.eye(D)
    cov = np.array([C0.copy() for _ in range(K)])
    A = 0.7 * np.eye(K) + 0.3 * rng.dirichlet(np.ones(K), K)
    p0 = np.full(K, 1.0 / K)
    ll_old = -np.inf
    for it in range(MAX_IT):
        logB = _logpdf(Y, mu, cov)
        al, c, B, ll = _fwd(logB, A, p0)
        be = _bwd(B, A, c)
        g = al * be
        g /= g.sum(1, keepdims=True)
        xi = (al[:-1, :, None] * A[None] * (B[1:] * be[1:])[:, None, :]) / c[1:, None, None]
        p0 = g[0] + 1e-12
        p0 /= p0.sum()
        A = xi.sum(0) + 1e-12
        A /= A.sum(1, keepdims=True)
        w = g.sum(0) + 1e-12
        mu = (g.T @ Y) / w[:, None]
        for k in range(K):
            Z = Y - mu[k]
            cov[k] = (g[:, k, None] * Z).T @ Z / w[k] + COV_FLOOR * np.eye(D)
        if abs(ll - ll_old) < TOL * max(1.0, abs(ll)):
            ll_old = ll
            break
        ll_old = ll
    # final log-likelihood at the final parameters
    ll = _fwd(_logpdf(Y, mu, cov), A, p0)[3]
    return {"mu": mu, "cov": cov, "A": A, "p0": p0, "ll": ll, "iters": it + 1}


def hmm_fit(Y, K, seed):
    rng = np.random.default_rng(seed)
    best = None
    lls = []
    for s in range(STARTS):
        try:
            f = hmm_fit_one(Y, K, rng)
        except np.linalg.LinAlgError:
            lls.append(None)
            continue
        lls.append(f["ll"])
        if best is None or f["ll"] > best["ll"]:
            best = f
    o = np.argsort(best["mu"][:, 0])                   # label states by their mean of b (ascending)
    best = {"mu": best["mu"][o], "cov": best["cov"][o], "A": best["A"][np.ix_(o, o)], "p0": best["p0"][o],
            "ll": best["ll"], "iters": best["iters"]}
    T, D = Y.shape
    npar = (K - 1) + K * (K - 1) + K * D + K * D * (D + 1) // 2
    best["bic"] = -2 * best["ll"] + npar * math.log(T)
    best["n_params"], best["T"] = npar, T
    best["start_lls"] = lls
    return best


def hmm_filter(Y, f):
    """Hamilton filter p_t = P(s_t | y_1..y_t) (no smoothing)."""
    al = _fwd(_logpdf(Y, f["mu"], f["cov"]), f["A"], f["p0"])[0]
    return al


# ---------------------------------------------------------------- two-regime Markov-switching regression
def _msr_logB(y, x, c, beta, sig2):
    mu = c[None] + beta[None] * x[:, None]
    return -0.5 * (np.log(2 * math.pi * sig2[None]) + (y[:, None] - mu) ** 2 / sig2[None])


def msr_fit_one(y, x, rng, K=2):
    T = len(y)
    X = np.column_stack([np.ones(T), x])
    v = np.var(y)
    coef0 = np.linalg.lstsq(X, y, rcond=None)[0]
    c = coef0[0] + np.sqrt(v) * rng.standard_normal(K) * 0.5
    beta = coef0[1] + np.std(y) * rng.standard_normal(K) * 0.5
    sig2 = v * rng.uniform(0.3, 2.0, K)
    A = 0.7 * np.eye(K) + 0.3 * rng.dirichlet(np.ones(K), K)
    p0 = np.full(K, 1.0 / K)
    floor = 1e-4 * v
    ll_old = -np.inf
    for it in range(MAX_IT):
        al, cc, B, ll = _fwd(_msr_logB(y, x, c, beta, sig2), A, p0)
        be = _bwd(B, A, cc)
        g = al * be
        g /= g.sum(1, keepdims=True)
        xi = (al[:-1, :, None] * A[None] * (B[1:] * be[1:])[:, None, :]) / cc[1:, None, None]
        p0 = g[0] + 1e-12
        p0 /= p0.sum()
        A = xi.sum(0) + 1e-12
        A /= A.sum(1, keepdims=True)
        for k in range(K):
            w = g[:, k] + 1e-12
            XtW = X.T * w
            cf = np.linalg.solve(XtW @ X + 1e-12 * np.eye(2), XtW @ y)
            c[k], beta[k] = cf
            sig2[k] = max(float((w * (y - X @ cf) ** 2).sum() / w.sum()), floor)
        if abs(ll - ll_old) < TOL * max(1.0, abs(ll)):
            break
        ll_old = ll
    ll = _fwd(_msr_logB(y, x, c, beta, sig2), A, p0)[3]
    return {"c": c.copy(), "beta": beta.copy(), "sig2": sig2.copy(), "A": A, "p0": p0, "ll": ll, "iters": it + 1}


def msr_fit(y, x, seed, K=2):
    rng = np.random.default_rng(seed)
    best, lls = None, []
    for s in range(STARTS):
        f = msr_fit_one(y, x, rng, K)
        lls.append(f["ll"])
        if np.isfinite(f["ll"]) and (best is None or f["ll"] > best["ll"]):
            best = f
    # label by the regime mean of b at the sample-mean regressor
    mb = best["c"] + best["beta"] * float(np.mean(x))
    o = np.argsort(mb)
    best = {k: (v[o] if k in ("c", "beta", "sig2", "p0") else v) for k, v in best.items()}
    best["A"] = best["A"][np.ix_(o, o)]
    T = len(y)
    npar = (K - 1) + K * (K - 1) + 3 * K
    best["bic"] = -2 * best["ll"] + npar * math.log(T)
    best["n_params"], best["T"], best["start_lls"] = npar, T, lls
    return best


def msr_filter(y, x, f):
    return _fwd(_msr_logB(y, x, f["c"], f["beta"], f["sig2"]), f["A"], f["p0"])[0]


# ---------------------------------------------------------------- walk-forward exposure
def hmm_cols():
    return ["b", "spy", "lrv21", "disp", "ic13"]


def standardised(W):
    """Expanding-z of each component (literal common protocol). Returns Z (nan where undefined) and b's stats."""
    Z = np.column_stack([expanding_z(W[cname].to_numpy())[0] for cname in hmm_cols()])
    _, mb, sb = expanding_z(W["b"].to_numpy())
    return Z, mb, sb


def walk(W, model, K=2, first_k=None, last_k=None, seed=20261120, log=None):
    """Exposure series for weeks k in [first_k, last_k]. Uses only rows j with c_j <= t_k.

    model: 'hmm' or 'msr'. Returns DataFrame per week with E, Var, raw, and a list of refit records.
    """
    t_, c_ = W["t"].to_numpy(), W["c"].to_numpy()
    n = len(W)
    if model == "hmm":
        Z, mb, sb = standardised(W)
        okrow = np.isfinite(Z).all(1)
    else:
        xz = expanding_z(W["ic13_dec"].to_numpy())[0]
        yb = W["b"].to_numpy()
        okrow = np.isfinite(xz) & np.isfinite(yb)
    first_obs = int(np.argmax(okrow))
    assert okrow[first_obs:].all(), "gaps in the observation sequence"
    if first_k is None:
        first_k = int(np.argmax(np.isfinite(W["b"].to_numpy()))) + BURN
    last_k = n - 1 if last_k is None else last_k
    out, fits, f = [], [], None
    for k in range(first_k, last_k + 1):
        known = np.where(c_ <= t_[k])[0]
        jl = int(known.max())
        if (k - first_k) % REFIT == 0:
            if model == "hmm":
                f = hmm_fit(Z[first_obs: jl + 1], K, seed + k)
                al = hmm_filter(Z[first_obs: jl + 1], f)
            else:
                f = msr_fit(yb[first_obs: jl + 1], xz[first_obs: jl + 1], seed + k)
                al = msr_filter(yb[first_obs: jl + 1], xz[first_obs: jl + 1], f)
            rec = {"k": k, "date": str(W.index[k].date()), "T": f["T"], "ll": f["ll"], "bic": f["bic"],
                   "persistence": np.diag(f["A"]).tolist(), "iters": f["iters"],
                   "share_filtered_argmax": np.bincount(al.argmax(1), minlength=len(f["A"])).astype(float).__truediv__(len(al)).tolist(),
                   "mean_filtered_prob": al.mean(0).tolist(),
                   "n_starts_finite": int(sum(1 for v in f["start_lls"] if v is not None and np.isfinite(v)))}
            if model == "hmm":
                rec["state_mean_b_z"] = f["mu"][:, 0].tolist()
                rec["state_sd_b_z"] = np.sqrt(f["cov"][:, 0, 0]).tolist()
            else:
                rec.update({"c": f["c"].tolist(), "beta": f["beta"].tolist(), "sig": np.sqrt(f["sig2"]).tolist()})
            fits.append(rec)
            if log:
                log(model, K, rec["date"], "T", rec["T"], "bic", round(rec["bic"], 1), "persist", np.round(rec["persistence"], 3).tolist())
        # Hamilton filter through jl with the current parameters
        if model == "hmm":
            p = hmm_filter(Z[first_obs: jl + 1], f)[-1]
        else:
            p = msr_filter(yb[first_obs: jl + 1], xz[first_obs: jl + 1], f)[-1]
        q = p @ np.linalg.matrix_power(f["A"], k - jl)
        if model == "hmm":
            m_s = mb[jl] + sb[jl] * f["mu"][:, 0]
            v_s = sb[jl] ** 2 * f["cov"][:, 0, 0]
        else:
            m_s = f["c"] + f["beta"] * xz[k]
            v_s = f["sig2"]
        E = float(q @ m_s)
        V = float(q @ (v_s + m_s ** 2) - E * E)
        out.append({"k": k, "date": W.index[k], "jl": jl, "h": k - jl, "E": E, "Var": V, "raw": E / V,
                    "q_top": float(q[-1]), "q_bottom": float(q[0])})
    df = pd.DataFrame(out).set_index("date")
    return df, fits


def exposure(raw):
    """pi_t = raw_t / expanding mean of raw (up to t), clipped to [0, 2]; mean <= 0 -> pi = 1 (recorded)."""
    m = pd.Series(raw).expanding().mean().to_numpy()
    pi = np.where(m > 0, raw / np.where(m > 0, m, 1.0), 1.0)
    return np.clip(pi, 0.0, 2.0), int((m <= 0).sum())


def timed(pi, b, G):
    """x = pi b - 5 bp |d pi| G_t, G_t the week's book gross sum|w| + |w_spy| (as L6_complexity)."""
    dpi = np.abs(np.diff(np.concatenate([[pi[0]], pi])))
    dpi[0] = abs(pi[0] - 1.0)                      # entering from the untimed book
    return pi * b - COST * dpi * G
