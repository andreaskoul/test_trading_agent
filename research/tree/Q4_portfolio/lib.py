"""Branch Q4 (layer 3, Amendment 3): portfolio construction on fixed signals, development data 2013-2019 only.

Book convention is M1's (research/tree/M1_dyntrade/lib.py, simulate): weights w_t over names chosen on Thursday t from
data <= t, entered at the next close, held 5 sessions, return w_t . y5_t (y5 = beta-hedged residual return), cost
5 bp x sum|w_t - w_{t-1}|. Names leave when they are not eligible / unscored / have no y5 at t (M1's mask).
The first scored week is dropped from every statistic (M1 summary, skip_first).

Constructions (all from data <= t):
* control      M1 band book (enter at the 10% tails, exit past the 20% tails), equal weights, sides 0.5.
* rank         signal-strength sizing: w_i proportional to (rank_i - mean rank) over all masked names, sides 0.5.
* mvnl         mean-variance: w = Sigma^-1 (mu - A lam), A = [1, beta_t] (dollar- and beta-neutral), gross 1;
               mu_i = sigma_i z_i (Grinold, z = normal score of the rank; the IC scale cancels at fixed gross);
               Sigma = Ledoit-Wolf (2020) analytical nonlinear shrinkage of the correlation of the last 252
               sessions of D["e"] (each name standardised by its own residual vol), rescaled by those vols x 5.
* pa(tau)      partial adjustment toward any target (Garleanu-Pedersen style): x_t = (1-tau) x_{t-1} + tau x*_t on the
               names still in the mask, then rescaled to the target's gross (and, for mvnl, re-projected neutral).
* nt(k)        L1 no-trade region (the exact rule under a linear cost and a diagonal risk approximation): each weight
               stays where it was unless it is more than delta = k x mean|target weight| from the target, in which
               case it moves to the edge of that region; then gross renormalised to 1. k tuned on 2013-2016.
* legvol       leg volatility matching: long leg scaled by a, short by b, a + b = 1, a sigma_L = b sigma_S
               (ex-ante leg vols from the same shrunk covariance).
* vm           volatility-managed scaling (Moreira-Muir 2017): s_t = min(cap, c_t / var_t), var_t = variance of the
               target book's daily residual return over the last 21 sessions (current weights x past e), c_t = median
               of var over past weeks (expanding; s = 1 for the first 13 weeks); cap 2 (declared a priori).
* dd           drawdown-conditioned exposure: from the book's own net weeks that have ended by t (rows[k] + 6 <= t),
               exposure 0.5 while the drawdown of that known curve exceeds 1.0 x its past annualised vol, back to 1
               when it is below 0.5 x (declared a priori).
"""
import os
import sys

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(v, "3")

import importlib.util

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
sys.path.insert(0, TREE)
import harness  # noqa: E402

PREDS = os.path.join(ROOT, ".cache", "tree", "preds", "Q4_portfolio")
COST = harness.COST
COV_WIN, VM_WIN = 252, 21


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


m1 = _mod("m1lib_q4", os.path.join(TREE, "M1_dyntrade", "lib.py"))
mask, val_rows, simulate, zscore, sides = m1.mask, m1.val_rows, m1.simulate, m1.zscore, m1.sides


# ---------------------------------------------------------------- signals
def xrank(a, elig):
    return pd.DataFrame(np.where(elig, a, np.nan)).rank(axis=1, pct=True).to_numpy() - 0.5


def signals(D):
    S = {"master": D["master_h5_ref"].astype(np.float64),
         "trees": np.load(os.path.join(PREDS, "sig_trees.npy")),
         "ipca": np.load(os.path.join(PREDS, "sig_ipca.npy"))}
    # X4's pre-declared blend: equal thirds of centred ranks on MASTER's names, missing component = 0 (X4 comb.blend)
    rows = np.concatenate([harness.thursdays(D, y) for y in harness.VAL_YEARS])
    el = D["elig"][rows]
    base = xrank(S["master"][rows], el)
    out = sum(np.nan_to_num(xrank(S[k][rows], el) if k != "master" else base, nan=0.0) / 3 for k in ("master", "ipca", "trees"))
    full = np.full(D["y5"].shape, np.nan)
    full[rows] = np.where(np.isfinite(base), out, np.nan)
    S["blend"] = full
    return S


# ---------------------------------------------------------------- Ledoit-Wolf (2020) analytical nonlinear shrinkage
def lw_nonlinear(X):
    """Ledoit & Wolf (2020, Annals of Statistics 48(5)), 'Analytical nonlinear shrinkage of large-dimensional
    covariance matrices', transcribed from their published Matlab function analytical_shrinkage. X: n x p, demeaned
    here (so the effective n is n - 1). Returns the p x p shrunk covariance."""
    n, p = X.shape
    X = X - X.mean(0)
    n = n - 1
    sample = X.T @ X / n
    lam, u = np.linalg.eigh((sample + sample.T) / 2)
    order = np.argsort(lam)
    lam, u = lam[order], u[:, order]
    lam = np.maximum(lam[max(0, p - n):], 0)                   # the min(p, n) non-zero eigenvalues
    lam = np.maximum(lam, 1e-12 * max(lam.max(), 1e-300))
    m = len(lam)
    L = np.tile(lam[:, None], (1, m))                         # L[i, j] = lam_i
    h = n ** (-1 / 3)
    H = h * L.T                                                # bandwidth for kernel centred at lam_j
    x = (L - L.T) / H
    ftilde = (3 / 4 / np.sqrt(5)) * np.mean(np.maximum(1 - x ** 2 / 5, 0) / H, 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        Hftemp = (-3 / 10 / np.pi) * x + (3 / 4 / np.sqrt(5) / np.pi) * (1 - x ** 2 / 5) * np.log(np.abs((np.sqrt(5) - x) / (np.sqrt(5) + x)))
    edge = np.isclose(np.abs(x), np.sqrt(5))
    Hftemp[edge] = (-3 / 10 / np.pi) * x[edge]
    Hftilde = np.mean(Hftemp / H, 1)
    if p <= n:
        c = p / n
        d = lam / ((np.pi * c * lam * ftilde) ** 2 + (1 - c - np.pi * c * lam * Hftilde) ** 2)
    else:
        Hf0 = (1 / np.pi) * (3 / 10 / h ** 2 + 3 / 4 / np.sqrt(5) / h * (1 - 1 / 5 / h ** 2)
                             * np.log((1 + np.sqrt(5) * h) / (1 - np.sqrt(5) * h))) * np.mean(1 / lam)
        d0 = 1 / (np.pi * (p - n) / n * Hf0)
        d1 = lam / (np.pi ** 2 * lam ** 2 * (ftilde ** 2 + Hftilde ** 2))
        d = np.concatenate([np.full(p - n, d0), d1])
    return (u * d) @ u.T


_COV = {}


def cov_at(D, t, linear=False):
    """Shrunk 5-session residual covariance at Thursday t over names with >= 150 finite e in the last 252 sessions.
    Returns (index of names, covariance, residual 5-session vol of all names). Cached per t."""
    if (t, linear) in _COV:
        return _COV[(t, linear)]
    e = D["e"][max(0, t - COV_WIN + 1):t + 1].astype(np.float64)
    ok = np.isfinite(e).sum(0) >= 150
    idx = np.where(ok)[0]
    E = e[:, idx]
    sd = np.nanstd(E, 0)
    Zs = np.where(np.isfinite(E), (E - np.nanmean(E, 0)) / sd, 0.0)
    if linear:
        from sklearn.covariance import LedoitWolf
        R = LedoitWolf().fit(Zs).covariance_
    else:
        R = lw_nonlinear(Zs)
    dg = np.sqrt(np.diag(R))
    R = R / np.outer(dg, dg)                                   # back to a correlation (zero-filling shrinks the diagonal)
    C = R * np.outer(sd, sd) * 5
    vol = np.full(e.shape[1], np.nan)
    vol[idx] = sd * np.sqrt(5)
    _COV[(t, linear)] = (idx, C, vol)
    return _COV[(t, linear)]


def sub_cov(D, t, names, linear=False):
    """Covariance on `names` (bool mask): shrunk block where available, diagonal (median-vol) elsewhere."""
    idx, C, vol = cov_at(D, t, linear)
    sel = np.where(names)[0]
    pos = {k: i for i, k in enumerate(idx)}
    med = np.nanmedian(vol)
    out = np.diag(np.array([(vol[k] if np.isfinite(vol[k]) else med) ** 2 for k in sel]))
    have = np.array([k in pos for k in sel])
    ii = np.array([pos[k] for k in sel[have]], dtype=int)
    hi = np.where(have)[0]
    out[np.ix_(hi, hi)] = C[np.ix_(ii, ii)]
    return sel, out


# ---------------------------------------------------------------- targets
def t_band(s, m, state, band=0.1):
    n = len(s)
    idx = np.where(m)[0]
    pct = np.zeros(n)
    pct[idx] = pd.Series(s[m]).rank(pct=True).to_numpy()
    top = m & ((pct > 0.9) | (state.get("top", np.zeros(n, bool)) & (pct > 0.9 - band)))
    bot = m & ((pct <= 0.1) | (state.get("bot", np.zeros(n, bool)) & (pct <= 0.1 + band)))
    state["top"], state["bot"] = top, bot
    w = np.zeros(n)
    w[top], w[bot] = 0.5 / top.sum(), -0.5 / bot.sum()
    return w


def t_rank(s, m):
    w = np.zeros(len(s))
    r = pd.Series(s[m]).rank().to_numpy()
    w[m] = r - r.mean()
    return sides(w)


def neutral_project(v, C, A):
    """Minimum-change (in Sigma^-1 metric) projection of v = Sigma^-1 mu onto A' w = 0."""
    Ci_A = np.linalg.solve(C, A)
    lam = np.linalg.solve(A.T @ Ci_A, A.T @ v)
    return v - Ci_A @ lam


def t_mvnl(s, m, D, t, linear=False):
    sel, C = sub_cov(D, t, m, linear)
    vol = np.sqrt(np.diag(C))
    mu = zscore(s, m)[sel] * vol
    v = np.linalg.solve(C, mu)
    b = np.nan_to_num(D["beta"][t][sel].astype(np.float64), nan=1.0)
    A = np.column_stack([np.ones(len(sel)), b])
    v = neutral_project(v, C, A)
    w = np.zeros(len(s))
    w[sel] = v / np.abs(v).sum()
    return w


def legvol(w, D, t):
    """Scale the legs so their ex-ante residual vols match, gross 1."""
    nz = w != 0
    sel, C = sub_cov(D, t, nz)
    ws = w[sel]
    L, S = np.where(ws > 0, ws, 0), np.where(ws < 0, ws, 0)
    sl, ss = np.sqrt(L @ C @ L) / max(L.sum(), 1e-12), np.sqrt(S @ C @ S) / max(-S.sum(), 1e-12)   # vol per unit leg
    a = ss / (sl + ss)                                          # long gross a, short gross 1 - a: a sl = (1-a) ss
    out = w.copy()
    out[w > 0] *= a / w[w > 0].sum()
    out[w < 0] *= (1 - a) / -w[w < 0].sum()
    return out


def book_var(w, D, t):
    e = np.nan_to_num(D["e"][max(0, t - VM_WIN + 1):t + 1].astype(np.float64))
    return float(np.var(e @ w, ddof=1))


# ---------------------------------------------------------------- the builder
def build(spec, scores, D, rows, tune_sink=None):
    """spec: dict with target in {"band", "rank", "mvnl"}, optional tau (partial adjustment), legvol (bool),
    vm (cap, or None), dd (bool). Returns W (len(rows) x n) and the exposure scale series."""
    n = scores.shape[1]
    W = np.zeros((len(rows), n))
    state, prev = {}, np.zeros(n)
    tau = spec.get("tau", 1.0)
    vars_, scale = [], np.ones(len(rows))
    for j, t in enumerate(rows):
        m = mask(scores, D, t)
        s = scores[t]
        tgt = spec["target"]
        if tgt == "band":
            x = t_band(s, m, state, spec.get("band", 0.1))
        elif tgt == "rank":
            x = t_rank(s, m)
        elif tgt == "mvnl":
            x = t_mvnl(s, m, D, t)
        elif tgt == "mvlw":                                     # ablation: linear Ledoit-Wolf (2004) instead of nonlinear
            x = t_mvnl(s, m, D, t, linear=True)
        else:
            raise ValueError(tgt)
        if spec.get("nt") and j > 0:                          # L1 no-trade region around the target (soft threshold)
            dl = spec["nt"] * np.abs(x[x != 0]).mean()
            p = np.where(m, prev, 0.0)
            x = np.where(m, np.clip(p, x - dl, x + dl), 0.0)
            x = x / np.abs(x).sum() if tgt in ("mvnl", "mvlw") else sides(x)
        if tau < 1.0 and j > 0:
            p = np.where(m, prev, 0.0)
            x = (1 - tau) * p + tau * x
            if tgt in ("mvnl", "mvlw"):
                x = x / np.abs(x).sum()
            else:
                x = sides(x)
        if spec.get("legvol"):
            x = legvol(x, D, t)
        prev = x.copy()                                         # partial adjustment runs on the unscaled book
        W[j] = x
        if spec.get("vm"):
            v = book_var(x, D, t)
            past = np.array(vars_)
            vars_.append(v)
            if len(past) >= 13:
                scale[j] = min(spec["vm"], np.median(past) / max(v, 1e-12))
    if spec.get("vm"):
        W = W * scale[:, None]
    if spec.get("dd"):
        W, scale = dd_overlay(W, D, rows)
    return W, scale


def dd_overlay(W, D, rows, on=1.0, off=0.5, low=0.5):
    """Exposure low while the known net curve of the scaled book is in a drawdown > on x past annualised vol."""
    n_rows = len(rows)
    Wout = W.copy()
    scale = np.ones(n_rows)
    prev = np.zeros(W.shape[1])
    net = np.full(n_rows, np.nan)
    state = 1.0
    for j, t in enumerate(rows):
        known = [k for k in range(j) if rows[k] + 6 <= t]
        if len(known) >= 26:
            r = net[known]
            eq = np.cumsum(r)
            ddv = float(np.max(eq) - eq[-1])
            vol = float(np.std(r, ddof=1) * np.sqrt(52))
            if state == 1.0 and ddv > on * vol:
                state = low
            elif state == low and ddv < off * vol:
                state = 1.0
        scale[j] = state
        w = W[j] * state
        y = np.nan_to_num(D["y5"][t])
        # the overlay's own record uses the unscaled book's return, so the rule watches the strategy, not itself
        net[j] = float(W[j] @ y) - COST * float(np.abs(W[j] - (W[j - 1] if j else 0)).sum())
        Wout[j] = w
        prev = w
    return Wout, scale


# ---------------------------------------------------------------- metrics
def nw_t(d, lags=4):
    d = d[np.isfinite(d)]
    n, dd = len(d), d - d.mean()
    v = dd @ dd / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (dd[l:] @ dd[:-l]) / n
    return float(d.mean() / np.sqrt(v / n))


def max_dd(net):
    eq = np.cumprod(1 + net)
    return float(np.max(1 - eq / np.maximum.accumulate(eq)))


def stats(net, turn, gross_series, years):
    sh = lambda x: float(x.mean() / x.std(ddof=1) * np.sqrt(52)) if len(x) > 2 else float("nan")
    by = {int(y): float(52 * net[years == y].mean() * 100) for y in np.unique(years)}
    a, b = years <= 2016, years >= 2017
    return {"net_pct_per_year": float(52 * net.mean() * 100), "net_sharpe": sh(net), "max_drawdown": max_dd(net),
            "turnover": float(turn.mean()), "vol_pct_per_year": float(net.std(ddof=1) * np.sqrt(52) * 100),
            "mean_gross": float(gross_series.mean()), "by_year_net_pct": by,
            "net_sharpe_2013_2016": sh(net[a]), "net_sharpe_2017_2019": sh(net[b]),
            "net_pct_2013_2016": float(52 * net[a].mean() * 100), "net_pct_2017_2019": float(52 * net[b].mean() * 100),
            "max_drawdown_2013_2016": max_dd(net[a]), "max_drawdown_2017_2019": max_dd(net[b])}


def run(spec, scores, D, rows):
    W, scale = build(spec, scores, D, rows)
    sim = simulate(W, D, rows)
    net, turn = sim["net"][1:], sim["turn"][1:]
    years = D["S"][rows[1:]].year.to_numpy()
    return net, stats(net, turn, np.abs(W[1:]).sum(1), years), W
