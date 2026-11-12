"""Branch D best configuration (see REPORT.md). Self-contained: numpy, pandas, sklearn and the harness only.

    from model import fit_predict
    pred = harness.walk_forward(fit_predict, seeds=(0, 1, 2))

An equal-weight average of cross-sectional ranks over the MEMBERS below. Every member is trained on the Thursdays
<= train_end, on a cross-sectional rank target, from 27 inputs: the five characteristics D["Z"] and 22 return features
built from D["e"], D["r"], D["beta"] with backward-looking windows only, ranked across the eligible names of each day.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor

# (kind, target horizon in sessions). Edited to the best configuration found; see REPORT.md.
MEMBERS = (("hgb", 5),)
HGB_ITERS = (50, 100, 200, 400)
_F = {}


def _xrank(a):
    return pd.DataFrame(a).rank(axis=1, pct=True).to_numpy() - 0.5


def _features(D):
    key = id(D["e"])
    if key in _F:
        return _F[key]
    e, r = pd.DataFrame(D["e"].astype(np.float64)), pd.DataFrame(D["r"].astype(np.float64))
    f = {}
    for w in (1, 5, 10, 21, 63, 126):
        f[f"e{w}"] = e.rolling(w, min_periods=max(1, int(w * 0.8))).sum()
    f["mom12_1"] = e.shift(21).rolling(231, min_periods=180).sum()
    f["r5"] = r.rolling(5, min_periods=4).sum()
    f["r21"] = r.rolling(21, min_periods=17).sum()
    for w in (10, 21, 63, 250):
        f[f"v{w}"] = e.rolling(w, min_periods=int(w * 0.8)).std()
    f["vratio"] = f["v10"] / f["v63"]
    f["max21"] = e.rolling(21, min_periods=17).max()
    f["min21"] = e.rolling(21, min_periods=17).min()
    f["sharpe63"] = f["e63"] / (f["v63"] * np.sqrt(63))
    f["z5"] = f["e5"] / (f["v63"] * np.sqrt(5))
    f["dd126"] = e.cumsum() - e.cumsum().rolling(126, min_periods=100).max()
    f["beta"] = pd.DataFrame(D["beta"].astype(np.float64))
    cols = []
    for v in f.values():
        a = v.to_numpy().copy()
        a[~D["elig"]] = np.nan
        cols.append(_xrank(a))
    X = np.concatenate([D["Z"].astype(np.float64).clip(-4, 4) / 4, np.stack(cols, 2)], 2)
    _F.clear()
    _F[key] = np.nan_to_num(X, nan=0.0).astype(np.float32)
    return _F[key]


def _target(D, h, te):
    """Sum of e over rows t+2 .. t+1+h (same one-session entry lag as y5); nothing ends after row te+6."""
    if h == 5:
        return D["y5"].astype(np.float64)
    e = D["e"].astype(np.float64)
    cs, nanc = np.cumsum(np.nan_to_num(e), 0), np.cumsum(np.isnan(e), 0)
    y = np.full(e.shape, np.nan)
    t = np.arange(0, min(te, te + 5 - h) + 1)
    t = t[t + 1 + h < len(e)]
    y[t] = np.where((nanc[t + 1 + h] - nanc[t + 1]) > 0, np.nan, cs[t + 1 + h] - cs[t + 1])
    return y


def _design(D, X, y, te):
    S = D["S"]
    rows = np.where((S.weekday == 3) & (np.arange(len(S)) <= te))[0]
    yy = y[rows].copy()
    m = D["elig"][rows] & np.isfinite(D["Z"][rows]).all(2) & np.isfinite(yy)
    yy[~m] = np.nan
    rid = np.repeat(rows[:, None], yy.shape[1], 1)
    return X[rows][m], _xrank(yy)[m], rid[m], rows


def _ic(p, y, rid):
    df = pd.DataFrame({"p": p, "y": y, "r": rid})
    return float(df.groupby("r")[["p", "y"]].apply(lambda g: g["p"].corr(g["y"], method="spearman")).mean())


def _fit(kind, h, D, X, te, seed):
    Xt, t, rid, rows = _design(D, X, _target(D, h, te), te)
    if kind == "hgb":
        kw = dict(learning_rate=0.03, max_leaf_nodes=8, min_samples_leaf=400, l2_regularization=1.0, max_features=0.5,
                  early_stopping=False, random_state=seed)
        # number of trees by rank IC on the last 104 training Thursdays (8-row gap), never by squared error
        cut = rows[-104]
        a, b = rid < cut - 8, rid >= cut
        m = HistGradientBoostingRegressor(max_iter=HGB_ITERS[-1], **kw).fit(Xt[a], t[a])
        best = (-9.0, HGB_ITERS[0])
        for i, p in enumerate(m.staged_predict(Xt[b]), 1):
            if i in HGB_ITERS:
                ic = _ic(p, t[b], rid[b])
                if ic > best[0] + 1e-4:
                    best = (ic, i)
        return HistGradientBoostingRegressor(max_iter=best[1], **kw).fit(Xt, t).predict
    if kind == "et":
        return ExtraTreesRegressor(n_estimators=200, min_samples_leaf=1000, max_features=0.33, n_jobs=2,
                                   random_state=seed).fit(Xt, t).predict
    Xd = Xt.astype(np.float64)                                             # ridge
    b = np.linalg.solve(Xd.T @ Xd + len(t) / 100 * np.eye(Xd.shape[1]), Xd.T @ t)
    return lambda Z: Z.astype(np.float64) @ b


def fit_predict(D, train_end, pred_rows, seed):
    X = _features(D)
    Xp = X[pred_rows]
    ok = D["elig"][pred_rows] & np.isfinite(D["Z"][pred_rows]).all(2)
    out = []
    for kind, h in MEMBERS:
        p = np.asarray(_fit(kind, h, D, X, train_end, seed)(Xp.reshape(-1, Xp.shape[2])), dtype=np.float64).reshape(Xp.shape[:2])
        p[~ok] = np.nan
        out.append(_xrank(p))
    return np.mean(out, 0)
