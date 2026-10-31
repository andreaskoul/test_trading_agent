"""P8 inference engine (PREREG_thesis_tree.md §2). Validated on simulated data by research/p8/test_inference.py.

EVENT-LEVEL TEST  y_i = beta s_i + a_c(i) + e_i, c = season x GICS sector (fixed effects), g = GICS industry (cluster).
  Frisch-Waugh-Lovell: with s~ = M s, y~ = M y (demeaned within c), beta^ = s~'y~ / D, D = s~'s~.
  CRV1 variance: V = k * sum_g (sum_{i in g} s~_i e^_i)^2 / D^2, k = G/(G-1) * (N-1)/(N-K), K = 1 + #cells.
  (a) Wild cluster restricted bootstrap (WCR; Cameron, Gelbach & Miller 2008; Roodman et al. 2019), Rademacher
      w_g, the null beta = 0 imposed: u_r = y~, y* = a_c + w_g u_r, y~* = M(w o y~).
      Since M s~ = s~:  beta*_b = sum_g w_g A_g / D,  A_g = sum_{i in g} s~_i y~_i.
      Cluster scores: sum_{i in g} s~_i e*_i = w_g A_g - (S Y w)_g - beta*_b Q_g, where
      S[g,c] = sum_{i in g, c} s~_i, Y[c,g'] = (1/n_c) sum_{j in c, g'} y~_j, Q_g = sum_{i in g} s~_i^2.
      p = (1 + #{d t*_b >= d t^}) / (B + 1), d = the pre-registered sign (+1 / -1). One-sided.
  (b) Randomization inference: s permuted within cells (the cell means, hence M, are invariant), the studentised
      t recomputed, p = (1 + #{d t_perm >= d t^}) / (B + 1).
  The test's p-value is max(p_a, p_b): it passes only if both pass (§2).

MONTHLY PORTFOLIO TEST  Fama-MacBeth: each month, OLS of the next-month target on the signal z-scored within the
  month; slope series b_m; t = mean / sqrt(NW_3 / T) (Newey-West, Bartlett weights, lag 3); one-sided p from the simulated small-sample null of the NW t (nw_p; Amendment 5).
  Long-short: top minus bottom decile (tercile if < 300 names in the month), equal weight, signed by the direction;
  net of 10 bp per round trip at the legs' own turnover: net_m = gross_m - 0.001 (to_L,m + to_S,m), to = share of a
  leg's names not in it the month before.

HOLM  step-down at alpha over the family; a hypothesis that could not be run enters with p = 1.
"""
import numpy as np
import pandas as pd
from scipy import stats


RADEMACHER = np.array([-1.0, 1.0])
# Webb (2023) six-point weights (mean 0, variance 1): with G <= 12 clusters Rademacher has only 2^G distinct draws
WEBB = np.array([-np.sqrt(1.5), -1.0, -np.sqrt(0.5), np.sqrt(0.5), 1.0, np.sqrt(1.5)])


def _codes(x):
    return pd.factorize(pd.Series(x).astype(str), sort=True)[0]


def _demean(v, cell, n_cells):
    s = np.bincount(cell, weights=v, minlength=n_cells)
    n = np.bincount(cell, minlength=n_cells)
    return v - (s / np.maximum(n, 1))[cell]


def event_test(y, s, cell, cluster, direction=1, B=9999, seed=0, chunk=500, return_draws=False, ri=True):
    y, s = np.asarray(y, float), np.asarray(s, float)
    ok = np.isfinite(y) & np.isfinite(s)
    y, s = y[ok], s[ok]
    c, g = _codes(np.asarray(cell)[ok]), _codes(np.asarray(cluster)[ok])
    N, C, G = len(y), c.max() + 1, g.max() + 1
    yt, st = _demean(y, c, C), _demean(s, c, C)
    D = st @ st
    k = G / (G - 1) * (N - 1) / (N - 1 - C)

    def tstat(stv):
        b = stv @ yt / D
        e = yt - b * stv
        sc = np.bincount(g, weights=stv * e, minlength=G)
        return b, b / np.sqrt(k * (sc @ sc) / D ** 2)

    b0, t0 = tstat(st)
    rng = np.random.default_rng(seed)
    # (a) WCR
    A = np.bincount(g, weights=st * yt, minlength=G)
    Q = np.bincount(g, weights=st * st, minlength=G)
    n_c = np.bincount(c, minlength=C)
    S = np.zeros((G, C)); np.add.at(S, (g, c), st)
    Yc = np.zeros((C, G)); np.add.at(Yc, (c, g), yt)
    Yc /= np.maximum(n_c, 1)[:, None]
    SY = S @ Yc                                              # G x G
    tw = []
    for i in range(0, B, chunk):
        W = rng.choice(WEBB if G <= 12 else RADEMACHER, size=(min(chunk, B - i), G))
        bb = W @ A / D
        sc = W * A - W @ SY.T - bb[:, None] * Q
        tw.append(bb / np.sqrt(k * (sc ** 2).sum(1) / D ** 2))
    tw = np.concatenate(tw)
    p_wild = (1 + np.sum(direction * tw >= direction * t0)) / (B + 1)
    if not ri:
        return {"beta": float(b0), "t": float(t0), "p_wild": float(p_wild), "n": int(N), "clusters": int(G),
                **({"draws": tw} if return_draws else {})}
    # (b) randomization inference within cells
    order = np.argsort(c, kind="stable")
    starts = np.searchsorted(c[order], np.arange(C))
    ends = np.append(starts[1:], N)
    tr = np.empty(B)
    for i in range(B):
        perm = order.copy()
        for a_, z_ in zip(starts, ends):
            if z_ - a_ > 1:
                perm[a_:z_] = rng.permutation(perm[a_:z_])
        sp = np.empty(N); sp[order] = st[perm]
        tr[i] = tstat(sp)[1]
    p_ri = (1 + np.sum(direction * tr >= direction * t0)) / (B + 1)
    return {"beta": float(b0), "t": float(t0), "p_wild": float(p_wild), "p_ri": float(p_ri),
            "p": float(max(p_wild, p_ri)), "n": int(N), "clusters": int(G), "cells": int(C),
            **({"draws": tw} if return_draws else {})}


def nw_t(x, lag=3):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    T = len(x)
    u = x - x.mean()
    v = u @ u / T
    for L in range(1, lag + 1):
        v += 2 * (1 - L / (lag + 1)) * (u[L:] @ u[:-L]) / T
    return x.mean() / np.sqrt(v / T), T


_NW_REF = {}


def nw_p(t, T, lag=3, draws=200_000, seed=12345):
    """One-sided p of a Newey-West t from its small-sample null distribution (i.i.d. Gaussian series of length T,
    the same lag), simulated once per (T, lag). With T = 48 the t(T-1) reference over-rejects (6.6% at 5% under
    i.i.d., 8.1% at AR(1) 0.3); this reference is exact under i.i.d. and matches Kiefer-Vogelsang (2005) fixed-b
    (5.1%; 5.3% at AR(1) 0.1). research/p8/test_inference.py."""
    key = (T, lag)
    if key not in _NW_REF:
        rng = np.random.default_rng(seed)
        X = rng.normal(size=(draws, T))
        U = X - X.mean(1, keepdims=True)
        v = (U * U).sum(1) / T
        for L in range(1, lag + 1):
            v += 2 * (1 - L / (lag + 1)) * (U[:, L:] * U[:, :-L]).sum(1) / T
        _NW_REF[key] = np.sort(X.mean(1) / np.sqrt(v / T))
    ref = _NW_REF[key]
    return float((1 + len(ref) - np.searchsorted(ref, t, side="left")) / (len(ref) + 1))


def fm_test(df, signal, target, month="month", firm="firm", direction=1, cost_rt=0.001):
    """df: one row per (month, firm), `target` already aligned to the month after the signal."""
    slopes, net, gross, months = [], [], [], []
    prev = {}
    for m, x in df.dropna(subset=[signal, target]).groupby(month, sort=True):
        if len(x) < 30:
            continue
        z = (x[signal] - x[signal].mean()) / x[signal].std(ddof=1)
        slopes.append(np.polyfit(z.values, x[target].values, 1)[0])
        q = 10 if len(x) >= 300 else 3
        r = x[signal].rank(method="first") * direction
        top = set(x[firm][r >= r.quantile(1 - 1 / q)]); bot = set(x[firm][r <= r.quantile(1 / q)])
        tg = x.set_index(firm)[target]
        gm = tg[list(top)].mean() - tg[list(bot)].mean()
        to = lambda leg, k: 1.0 if k not in prev else len(leg - prev[k]) / max(len(leg), 1)
        net.append(gm - cost_rt * (to(top, "L") + to(bot, "S")))
        gross.append(gm)
        prev = {"L": top, "S": bot}
        months.append(m)
    t, T = nw_t(np.array(slopes) * direction)
    p = nw_p(t, T)
    return {"slope": float(np.mean(slopes)), "t": float(t), "p": p, "months": T,
            "ls_gross": float(np.mean(gross)), "ls_net": float(np.mean(net)),
            "series": pd.DataFrame({"month": months, "slope": slopes, "gross": gross, "net": net})}


def holm(p, alpha=0.05):
    """Step-down Holm; returns the adjusted p-values and the pass flags, in the input order."""
    p = np.asarray(p, float)
    m = len(p)
    o = np.argsort(p)
    adj = np.empty(m)
    run = 0.0
    for r, i in enumerate(o):
        run = max(run, min(1.0, (m - r) * p[i]))
        adj[i] = run
    return adj, adj <= alpha


def _mean_p(y, g, null, direction, B, rng):
    """One clustering: the CR1 t of mean(y) - null against t(G-1), and a wild cluster restricted bootstrap (null
    imposed; Rademacher, Webb under 13 clusters). One-sided p-values (direction +1: H0 mean <= null)."""
    G = g.max() + 1
    n = len(y)

    def tstat(v):
        m = v.mean()
        sc = np.bincount(g, weights=v - m, minlength=G)
        se = np.sqrt(G / (G - 1) * (sc @ sc)) / n
        return (m - null) / se if se > 0 else 0.0

    t0 = tstat(y)
    p_cr1 = float(stats.t.sf(direction * t0, G - 1))
    u = y - null
    pool = WEBB if G < 13 else RADEMACHER
    hits = 0
    for _ in range(B):
        w = rng.choice(pool, size=G)
        hits += direction * tstat(null + w[g] * u) >= direction * t0
    return float(t0), p_cr1, float((1 + hits) / (B + 1))


def mean_test(y, week, industry, null=0.0, direction=1, B=9999, seed=0):
    """PREREG_family_E.md section 3: a mean with no cross-sectional regressor. One-sided p = the largest of the CR1 and
    wild-bootstrap p-values under clustering by calendar week and by industry. Returns mean, t (week clusters), p."""
    y = np.asarray(y, float)
    ok = np.isfinite(y)
    y = y[ok]
    gw, gi = _codes(np.asarray(week)[ok]), _codes(np.asarray(industry)[ok])
    rng = np.random.default_rng(seed)
    tw, pw1, pw2 = _mean_p(y, gw, null, direction, B, rng)
    ti, pi1, pi2 = _mean_p(y, gi, null, direction, B, rng)
    t2, p2 = _two_way(y, gw, gi, null, direction)
    return {"n": int(len(y)), "mean": float(y.mean()), "t_week": tw, "t_industry": ti, "t_two_way": t2,
            "p": max(pw1, pw2, pi1, pi2, p2),
            "p_parts": {"cr1_week": pw1, "wild_week": pw2, "cr1_ind": pi1, "wild_ind": pi2, "cr1_two_way": p2}}


def _two_way(y, gw, gi, null, direction):
    """Cameron-Gelbach-Miller two-way clustered variance of the mean (week, industry): V_w + V_i - V_wi, with V_w or
    V_i alone if that is larger (Family E Amendment 2: the one-way tests over-rejected under both shocks)."""
    n, m = len(y), y.mean()

    def v(g):
        G = g.max() + 1
        sc = np.bincount(g, weights=y - m, minlength=G)
        return G / (G - 1) * (sc @ sc) / n ** 2, G
    (vw, Gw), (vi, Gi) = v(gw), v(gi)
    vwi, _ = v(_codes(gw.astype(np.int64) * (gi.max() + 1) + gi))
    V = max(vw + vi - vwi, vw, vi)
    t = (m - null) / np.sqrt(V) if V > 0 else 0.0
    return float(t), float(stats.t.sf(direction * t, min(Gw, Gi) - 1))

