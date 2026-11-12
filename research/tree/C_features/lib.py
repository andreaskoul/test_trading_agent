"""Branch C: price-only characteristics + ridge. Learner held fixed (ridge on per-day standardised targets).

All features are causal: rolling windows ending at row t. Cross-sectional transforms use eligible names of row t only.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GROUPS = {
    "rev": ["rev1", "rev5", "rev21", "erev1", "erev5", "erev21"],
    "mom": ["mom63", "mom126", "mom252", "emom126", "emom252", "resmom252"],
    "risk": ["ivol21", "ivol63", "tvol21", "beta", "skew63", "max21", "dvol"],
    "hv": ["hi52", "vsrev5", "vsrev21", "vsmom252", "vserev5"],
}
GROUPS["all"] = GROUPS["rev"] + GROUPS["mom"] + GROUPS["risk"] + GROUPS["hv"]

_RAW, _X, _STATE = {}, {}, {}


def raw_features(D):
    key = id(D["r"])
    if key in _RAW:
        return _RAW[key]
    r = pd.DataFrame(D["r"].astype(np.float64))
    e = pd.DataFrame(D["e"].astype(np.float64))

    def rs(x, n, mp=None):
        return x.rolling(n, min_periods=mp or max(2, int(n * 0.8))).sum()

    def sd(x, n):
        return x.rolling(n, min_periods=int(n * 0.8)).std()

    F = {}
    for n in (1, 5, 21):
        F["rev%d" % n] = rs(r, n, n)
        F["erev%d" % n] = rs(e, n, n)
    for n in (63, 126, 252):
        F["mom%d" % n] = rs(r, n) - rs(r, 21, 21)
    for n in (126, 252):
        F["emom%d" % n] = rs(e, n) - rs(e, 21, 21)
    F["ivol21"], F["ivol63"], F["tvol21"] = sd(e, 21), sd(e, 63), sd(r, 21)
    iv252 = sd(e, 252)
    F["resmom252"] = F["emom252"] / iv252                       # Blitz-Huij-Martens style, vol-scaled residual momentum
    F["beta"] = pd.DataFrame(D["beta"].astype(np.float64))
    F["skew63"] = e.rolling(63, min_periods=50).skew()
    F["max21"] = r.rolling(21, min_periods=17).max()
    F["dvol"] = np.log(F["ivol21"] / sd(e, 126))
    lp = np.log1p(r.clip(lower=-0.9)).fillna(0.0).cumsum().where(r.notna())
    F["hi52"] = lp - lp.rolling(252, min_periods=200).max()
    F["vsrev5"] = F["rev5"] / F["tvol21"]
    F["vsrev21"] = F["rev21"] / sd(r, 63)
    F["vsmom252"] = F["mom252"] / sd(r, 252)
    F["vserev5"] = F["erev5"] / F["ivol63"]
    F = {k: v.to_numpy() for k, v in F.items()}
    _RAW[key] = F
    return F


def xs(a, elig, how):
    """Cross-sectional transform over the eligible names of each row. NaN outside."""
    a = np.where(elig & np.isfinite(a), a, np.nan)
    if how == "z":
        lo, hi = np.nanpercentile(a, [1, 99], axis=1, keepdims=True)
        a = np.clip(a, lo, hi)
        return (a - np.nanmean(a, 1, keepdims=True)) / (np.nanstd(a, 1, keepdims=True) + 1e-12)
    u = pd.DataFrame(a).rank(axis=1).to_numpy()
    n = np.sum(np.isfinite(a), 1, keepdims=True)
    u = (u - 0.5) / np.maximum(n, 1)
    if how == "rank":
        return (u - 0.5) * np.sqrt(12.0)
    if how == "gauss":
        from scipy.special import ndtri
        return ndtri(u)
    raise ValueError(how)


def market_state(D):
    """Causal market-state scalars in [-0.5, 0.5]: expanding percentile of 21-session market vol and 21-session return."""
    key = id(D["rm"])
    if key in _STATE:
        return _STATE[key]
    rm = pd.Series(D["rm"].astype(np.float64))
    mv = rm.rolling(21, min_periods=15).std()
    mr = rm.rolling(21, min_periods=15).sum()
    out = {"mvol": (mv.expanding(min_periods=60).rank(pct=True) - 0.5).fillna(0.0).to_numpy(),
           "mret": (mr.expanding(min_periods=60).rank(pct=True) - 0.5).fillna(0.0).to_numpy()}
    _STATE[key] = out
    return out


def design(D, feats, how="rank", inter=()):
    """X: (T, N, K) float32, NaN->0 after transform (0 = cross-sectional middle). inter: (feature, state) pairs."""
    key = (id(D["r"]), tuple(feats), how, tuple(inter))
    if key in _X:
        return _X[key]
    F, elig = raw_features(D), D["elig"]
    cols = {f: xs(F[f], elig, how) for f in set(feats) | {f for f, _ in inter}}
    X = [cols[f] for f in feats]
    st = market_state(D)
    X += [cols[f] * st[s][:, None] for f, s in inter]
    X = np.stack(X, 2)
    ok = elig & np.isfinite(cols[feats[0]] if "rev5" not in cols else cols["rev5"])
    X = np.where(np.isfinite(X), X, 0.0).astype(np.float32)
    _X[key] = (X, ok)
    return _X[key]


def target(D, te):
    y = D["y5"][: te + 1].astype(np.float64)
    y = np.where(D["elig"][: te + 1], y, np.nan)
    y = y - np.nanmean(y, 1, keepdims=True)
    y = np.clip(y / (np.nanstd(y, 1, keepdims=True) + 1e-12), -3, 3)
    return y


def make(feats, how="rank", inter=(), lam=0.1, window="expanding", halflife=None, roll=None, fm=False, thursdays_only=False):
    """Ridge candidate. window: expanding | rolling (roll sessions) | ew (halflife sessions). fm: Fama-MacBeth average
    of per-day ridge slopes (same weights over days) instead of pooled."""
    cache = {}

    def fit_predict(D, te, rows, seed):
        X, ok = design(D, feats, how, inter)
        k = (id(D["r"]), te)
        if k not in cache:
            y = target(D, te)
            m = np.isfinite(y) & ok[: te + 1]
            Xm = X[: te + 1] * m[:, :, None]
            A = np.einsum("tnk,tnj->tkj", Xm, Xm, optimize=True).astype(np.float64)
            c = np.einsum("tnk,tn->tk", Xm, np.where(m, y, 0.0).astype(np.float32), optimize=True).astype(np.float64)
            n = m.sum(1).astype(np.float64)
            days = np.where(n >= 50)[0]
            if thursdays_only:
                days = days[D["S"][days].weekday == 3]
            if window == "rolling":
                days = days[days > te - roll]
            w = np.ones(len(days))
            if window == "ew":
                w = 0.5 ** ((te - days) / halflife)
            K = X.shape[2]
            if fm:
                bs = []
                for d in days:
                    Ad = A[d] / n[d]
                    bs.append(np.linalg.solve(Ad + lam * np.trace(Ad) / K * np.eye(K), c[d] / n[d]))
                b = (np.array(bs) * w[:, None]).sum(0) / w.sum()
            else:
                Aw = (A[days] * w[:, None, None]).sum(0) / (n[days] * w).sum()
                cw = (c[days] * w[:, None]).sum(0) / (n[days] * w).sum()
                b = np.linalg.solve(Aw + lam * np.trace(Aw) / K * np.eye(K), cw)
            cache[k] = b
        b = cache[k]
        p = X[rows].astype(np.float64) @ b
        return np.where(ok[rows], p, np.nan)

    fit_predict.cache = cache
    return fit_predict


def names(feats, inter=()):
    return list(feats) + ["%s*%s" % fi for fi in inter]
