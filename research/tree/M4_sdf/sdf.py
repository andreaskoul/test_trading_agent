"""Branch M4: shrinking the cross-section (Kozak, Nagel and Santosh 2020), implemented from the paper (no package).

Characteristics Z_t: the 24 price-only features of branch C (read-only import of C_features/lib.py), cross-sectional
ranks scaled to unit variance over eligible names (missing -> 0). Optional "X": the 24 plus all 276 pairwise products
and 24 squares (324), each product cross-sectionally demeaned and scaled to unit variance, as in the paper.

Managed portfolios F_t = Z_t' x_t / n_t, where x_t is the next-period hedged return of row t, standardised per period
and clipped at +-3 ("xnorm"). Periods: "wk" = training Thursdays with x = y5 (non-overlapping 5-session returns);
"d5" = every training session with x = y5 (overlapping); "d1" = every session with x = e[t+2] (next session after
entry, the same entry convention as y5).

SDF weights on training periods only, with mu = mean F, Sigma = cov F (eigendecomposition Sigma = Q diag(d) Q'):
  "mv":  b = pinv(Sigma) mu                                     (unshrunk mean-variance SDF)
  "l2":  b = (Sigma + gamma I)^-1 mu = Q diag(1/(d+gamma)) Q' mu   (the paper's prior: PC directions with small
         variance are shrunk the most)
  "en":  argmin (mu - Sigma b)' Sigma^-1 (mu - Sigma b) + gamma b'b + g1 |b|_1   on raw characteristics ("raw")
         or on PC portfolios ("pc", b in PC coordinates, sparsity in PCs); solved as an elastic net regression of
         y = Sigma^-1/2 mu on X = Sigma^1/2 (sklearn, no intercept).
  "pck": unshrunk SDF on the top-k PCs of Sigma, k by the same CV (truncation instead of shrinkage).
Gamma is parametrised as in the paper, gamma = tr(Sigma) / (T kappa^2), kappa on a log grid, and chosen (with g1 for
"en") by 3-fold contiguous cross-validation inside the training periods of the out-of-fold cross-sectional R^2 of
the pricing error, R^2 = 1 - (mu2 - Sigma2 b1)'(mu2 - Sigma2 b1) / mu2'mu2. Never by validation-year IC.

Score at prediction row t: Z_t b (the expected return the SDF implies). Deterministic: the seed is unused.
"""
import json
import os
import sys
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from C_features import lib  # noqa: E402  (read-only import)

KAPPAS = np.logspace(-2.5, 1.0, 36)
_BASE = {}
_F = {}


def base(D):
    key = id(D["r"])
    if key not in _BASE:
        X, ok = lib.design(D, lib.GROUPS["all"], "rank")
        _BASE[key] = (X, ok)
    return _BASE[key]


def zrow(D, t, chars):
    """Characteristics of row t: (N, K) with zeros outside the eligible names; and the eligible mask."""
    X, ok = base(D)
    z = X[t].astype(np.float64)
    m = ok[t]
    if chars == "C24":
        return np.where(m[:, None], z, 0.0), m
    iu = np.triu_indices(z.shape[1])
    p = (z[:, :, None] * z[:, None, :])[:, iu[0], iu[1]]
    if m.sum() > 2:
        pm = p[m]
        p = (p - pm.mean(0)) / (pm.std(0) + 1e-12)
    out = np.hstack([z, p])
    return np.where(m[:, None], out, 0.0), m


def periods(D, freq, te):
    S = D["S"]
    rows = np.arange(0, te + 1)
    if freq == "wk":
        rows = rows[S[rows].weekday == 3]
    return rows


def target_row(D, t, freq):
    if freq == "d1":
        return D["e"][t + 2].astype(np.float64) if t + 2 < len(D["e"]) else np.full(D["e"].shape[1], np.nan)
    return D["y5"][t].astype(np.float64)


def managed(D, chars, freq, te):
    """F (P, K) for training periods <= te. Cached by row; rows <= te never change across folds of walk_forward."""
    key = (id(D["r"]), chars, freq)
    c = _F.setdefault(key, {})
    rows = periods(D, freq, te)
    out, used = [], []
    for t in rows:
        if t not in c:
            x = target_row(D, t, freq)
            z, m = zrow(D, t, chars)
            m = m & np.isfinite(x)
            if m.sum() < 50 or (np.abs(z[m]) > 0).sum(0).min() < 50:          # warm-up: a characteristic missing
                c[t] = None
            else:
                xx = x[m]
                xx = np.clip((xx - xx.mean()) / (xx.std() + 1e-12), -3, 3)
                c[t] = z[m].T @ xx / m.sum()
        if c[t] is not None:
            out.append(c[t])
            used.append(t)
    return np.array(out), np.array(used)


def mom(F):
    mu = F.mean(0)
    Sig = np.cov(F, rowvar=False, bias=False)
    d, Q = np.linalg.eigh(Sig)
    d = np.clip(d, 0, None)
    return mu, Sig, d, Q


def b_l2(mu, d, Q, gamma):
    return Q @ ((Q.T @ mu) / (d + gamma))


def b_mv(mu, d, Q):
    keep = d > d.max() * 1e-10
    return Q[:, keep] @ ((Q[:, keep].T @ mu) / d[keep])


def b_pck(mu, d, Q, k):
    idx = np.argsort(d)[::-1][:k]
    return Q[:, idx] @ ((Q[:, idx].T @ mu) / d[idx])


def b_en(mu, d, Q, gamma, g1, space):
    from sklearn.linear_model import ElasticNet
    keep = d > d.max() * 1e-10
    if space == "pc":                                               # coordinates = PC portfolios
        Xr = np.diag(np.sqrt(d[keep]))
        yr = (Q[:, keep].T @ mu) / np.sqrt(d[keep])
    else:
        Xr = (Q[:, keep] * np.sqrt(d[keep])) @ Q[:, keep].T
        yr = Q[:, keep] @ ((Q[:, keep].T @ mu) / np.sqrt(d[keep]))
    n = len(yr)
    l2, l1 = gamma / n, g1 / (2 * n)
    alpha = l2 + l1
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = ElasticNet(alpha=alpha, l1_ratio=l1 / alpha, fit_intercept=False, max_iter=5000, tol=1e-6).fit(Xr, yr)
    bb = m.coef_
    if space == "pc":
        full = np.zeros(len(d))
        full[np.where(keep)[0]] = bb
        return Q @ full, int((bb != 0).sum())
    return bb, int((bb != 0).sum())


def r2(mu2, Sig2, b):
    e = mu2 - Sig2 @ b
    return 1 - e @ e / (mu2 @ mu2)


def grid(method, mu, d, Q, T, en_space):
    """List of (params, b) over the method's grid."""
    tau = d.sum()
    out = []
    if method == "mv":
        out.append(({}, b_mv(mu, d, Q)))
    elif method == "l2":
        for k in KAPPAS:
            out.append(({"kappa": float(k)}, b_l2(mu, d, Q, tau / (T * k ** 2))))
    elif method == "pck":
        for k in range(1, len(d) + 1):
            out.append(({"k": k}, b_pck(mu, d, Q, k)))
    elif method == "en":
        for k in KAPPAS[::3]:
            g = tau / (T * k ** 2)
            # L1 scale: relative to the largest |gradient| at b=0 (2 |mu| in these coordinates)
            gmax = 2 * np.abs(mu).max() if en_space == "raw" else 2 * np.abs(Q.T @ mu).max()
            for f in (0.0, 0.01, 0.03, 0.1, 0.2, 0.4, 0.7):
                if f == 0.0:
                    out.append(({"kappa": float(k), "l1": 0.0}, b_l2(mu, d, Q, g)))
                    continue
                bb, nz = b_en(mu, d, Q, g, f * gmax, en_space)
                out.append(({"kappa": float(k), "l1": f}, bb))
    return out


def fit(F, method, en_space="raw", folds=3):
    """CV-select the grid point by mean out-of-fold pricing-error R^2, then refit on all periods."""
    P = len(F)
    mu, Sig, d, Q = mom(F)
    cv = None
    if method != "mv":
        edges = np.linspace(0, P, folds + 1).astype(int)
        scores = None
        for i in range(folds):
            te_ = np.zeros(P, bool)
            te_[edges[i]:edges[i + 1]] = True
            mu1, _, d1, Q1 = mom(F[~te_])
            mu2, Sig2, _, _ = mom(F[te_])
            g = grid(method, mu1, d1, Q1, (~te_).sum(), en_space)
            s = np.array([r2(mu2, Sig2, b) for _, b in g])
            scores = s if scores is None else scores + s
            params = [p for p, _ in g]
        scores = scores / folds
        j = int(np.argmax(scores))
        cv = {"params": params[j], "cv_r2": float(scores[j])}
    g = grid(method, mu, d, Q, P, en_space) if method == "mv" else None
    if method == "mv":
        b = g[0][1]
    elif method == "l2":
        b = b_l2(mu, d, Q, d.sum() / (P * cv["params"]["kappa"] ** 2))
    elif method == "pck":
        b = b_pck(mu, d, Q, cv["params"]["k"])
    else:
        gm = d.sum() / (P * cv["params"]["kappa"] ** 2)
        if cv["params"]["l1"] == 0:
            b = b_l2(mu, d, Q, gm)
        else:
            gmax = 2 * np.abs(mu).max() if en_space == "raw" else 2 * np.abs(Q.T @ mu).max()
            b, _ = b_en(mu, d, Q, gm, cv["params"]["l1"] * gmax, en_space)
    nz = int((np.abs(b) > 1e-12).sum()) if not (method == "en" and en_space == "pc") else None
    return b, cv, nz


def make(chars, freq, method, en_space="raw", log=None, tag=""):
    cache = {}

    def fit_predict(D, te, rows, seed):
        if te not in cache:
            F, used = managed(D, chars, freq, te)
            b, cv, nz = fit(F, method, en_space)
            cache[te] = b
            if log:
                with open(log, "a") as f:
                    f.write(json.dumps({"tag": tag, "train_end": str(D["S"][te].date()), "periods": len(F), "K": F.shape[1],
                                        "cv": cv, "nonzero": nz, "b_norm": float(np.linalg.norm(b))}) + "\n")
        b = cache[te]
        out = np.full((len(rows), D["y5"].shape[1]), np.nan)
        for i, t in enumerate(rows):
            z, m = zrow(D, t, chars)
            out[i] = np.where(m, z @ b, np.nan)
        return out

    return fit_predict
