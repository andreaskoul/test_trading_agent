"""Branch C best configuration (C13): 24 price-only characteristics + 8 market-state interactions, cross-sectional
ranks, Fama-MacBeth average of daily cross-sectional ridge slopes (expanding window, all sessions <= train_end).

Self-contained: numpy/pandas only. Deterministic (the seed is unused). All features are causal (rolling windows ending
at row t; market state is an expanding percentile up to row t).
"""
import numpy as np
import pandas as pd

FEATS = ["rev1", "rev5", "rev21", "erev1", "erev5", "erev21",
         "mom63", "mom126", "mom252", "emom126", "emom252", "resmom252",
         "ivol21", "ivol63", "tvol21", "beta", "skew63", "max21", "dvol",
         "hi52", "vsrev5", "vsrev21", "vsmom252", "vserev5"]
INTER = [("rev5", "mvol"), ("erev5", "mvol"), ("rev21", "mvol"), ("erev21", "mvol"), ("rev1", "mvol"), ("mom252", "mvol"),
         ("rev5", "mret"), ("mom252", "mret")]
LAM = 0.1
_CACHE = {}


def _raw(D):
    r = pd.DataFrame(D["r"].astype(np.float64))
    e = pd.DataFrame(D["e"].astype(np.float64))

    def rs(x, n, mp=None):
        return x.rolling(n, min_periods=mp or max(2, int(n * 0.8))).sum()

    def sd(x, n):
        return x.rolling(n, min_periods=int(n * 0.8)).std()

    F = {}
    for n in (1, 5, 21):                                         # short-term reversal, raw and hedged
        F["rev%d" % n] = rs(r, n, n)
        F["erev%d" % n] = rs(e, n, n)
    for n in (63, 126, 252):                                     # momentum, last 21 sessions skipped
        F["mom%d" % n] = rs(r, n) - rs(r, 21, 21)
    for n in (126, 252):
        F["emom%d" % n] = rs(e, n) - rs(e, 21, 21)
    F["ivol21"], F["ivol63"], F["tvol21"] = sd(e, 21), sd(e, 63), sd(r, 21)
    F["resmom252"] = F["emom252"] / sd(e, 252)                   # residual momentum, vol-scaled
    F["beta"] = pd.DataFrame(D["beta"].astype(np.float64))
    F["skew63"] = e.rolling(63, min_periods=50).skew()
    F["max21"] = r.rolling(21, min_periods=17).max()
    F["dvol"] = np.log(F["ivol21"] / sd(e, 126))                 # change in idiosyncratic volatility
    lp = np.log1p(r.clip(lower=-0.9)).fillna(0.0).cumsum().where(r.notna())
    F["hi52"] = lp - lp.rolling(252, min_periods=200).max()      # distance from the 52-week high
    F["vsrev5"] = F["rev5"] / F["tvol21"]
    F["vsrev21"] = F["rev21"] / sd(r, 63)
    F["vsmom252"] = F["mom252"] / sd(r, 252)
    F["vserev5"] = F["erev5"] / F["ivol63"]
    return {k: v.to_numpy() for k, v in F.items()}


def _rank(a, elig):
    a = np.where(elig & np.isfinite(a), a, np.nan)
    u = pd.DataFrame(a).rank(axis=1).to_numpy()
    n = np.sum(np.isfinite(a), 1, keepdims=True)
    return ((u - 0.5) / np.maximum(n, 1) - 0.5) * np.sqrt(12.0)


def _design(D):
    key = id(D["r"])
    if key not in _CACHE:
        F, elig = _raw(D), D["elig"]
        cols = {f: _rank(F[f], elig) for f in FEATS}
        rm = pd.Series(D["rm"].astype(np.float64))
        st = {"mvol": (rm.rolling(21, min_periods=15).std().expanding(min_periods=60).rank(pct=True) - 0.5).fillna(0.0).to_numpy(),
              "mret": (rm.rolling(21, min_periods=15).sum().expanding(min_periods=60).rank(pct=True) - 0.5).fillna(0.0).to_numpy()}
        X = np.stack([cols[f] for f in FEATS] + [cols[f] * st[s][:, None] for f, s in INTER], 2)
        ok = elig & np.isfinite(cols["rev5"])
        _CACHE[key] = (np.where(np.isfinite(X), X, 0.0).astype(np.float32), ok)
    return _CACHE[key]


def fit_predict(D, train_end, pred_rows, seed=0):
    X, ok = _design(D)
    te = int(train_end)
    y = np.where(D["elig"][: te + 1], D["y5"][: te + 1].astype(np.float64), np.nan)
    with np.errstate(all="ignore"):
        y = y - np.nanmean(y, 1, keepdims=True)
        y = np.clip(y / (np.nanstd(y, 1, keepdims=True) + 1e-12), -3, 3)     # per-day standardised target
    m = np.isfinite(y) & ok[: te + 1]
    Xm = X[: te + 1] * m[:, :, None]
    A = np.einsum("tnk,tnj->tkj", Xm, Xm, optimize=True).astype(np.float64)
    c = np.einsum("tnk,tn->tk", Xm, np.where(m, y, 0.0).astype(np.float32), optimize=True).astype(np.float64)
    n = m.sum(1).astype(np.float64)
    K, bs = X.shape[2], []
    for d in np.where(n >= 50)[0]:                               # Fama-MacBeth: one ridge cross-section per session
        Ad = A[d] / n[d]
        bs.append(np.linalg.solve(Ad + LAM * np.trace(Ad) / K * np.eye(K), c[d] / n[d]))
    b = np.mean(bs, 0)
    p = X[np.asarray(pred_rows)].astype(np.float64) @ b
    return np.where(ok[np.asarray(pred_rows)], p, np.nan)
