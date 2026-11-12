"""Branch D (trees, ensembles, stacking): shared experiment code. All features for row t use rows <= t only."""
import os
import sys

import numpy as np
import pandas as pd
from scipy.optimize import nnls
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import harness  # noqa: E402

_F = {}      # feature cache
_P = {}      # base prediction cache: (model, te, seed, rows-key) -> array


def xrank(a):
    """Cross-sectional rank per row in [-0.5, 0.5]; NaN stays NaN."""
    return pd.DataFrame(a).rank(axis=1, pct=True).to_numpy() - 0.5


def features(D):
    """(T, N, F) float32 of cross-sectionally ranked features, NaN -> 0 (the median). Backward-looking windows only."""
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
    elig = D["elig"]
    cols = []
    for k, v in f.items():
        a = v.to_numpy().copy()
        a[~elig] = np.nan
        cols.append(xrank(a))
    X = np.stack(cols, 2)
    X = np.concatenate([D["Z"].astype(np.float64).clip(-4, 4) / 4, X], 2)   # the five characteristics, scaled
    X = np.nan_to_num(X, nan=0.0).astype(np.float32)
    _F[key] = (X, ["Z%d" % i for i in range(5)] + list(f))
    return _F[key]


def target(D, h, te):
    """h-session hedged return entered at the next close, sum e[t+2 .. t+1+h]; rows whose window ends after the
    y5 window of train_end (row te+6) are NaN. For h=5 this reproduces D['y5'] (which the harness already blanks)."""
    if h == 5:
        return D["y5"].astype(np.float64)
    e = D["e"].astype(np.float64)
    T = len(e)
    cs = np.cumsum(np.nan_to_num(e), 0)
    nanc = np.cumsum(np.isnan(e), 0)
    y = np.full(e.shape, np.nan)
    last = min(te, te + 5 - h)                       # window end t+1+h <= te+6
    t = np.arange(0, last + 1)
    t = t[t + 1 + h < T]
    y[t] = cs[t + 1 + h] - cs[t + 1]
    y[t] = np.where((nanc[t + 1 + h] - nanc[t + 1]) > 0, np.nan, y[t])
    return y


def train_rows(D, te, step="thu", lo=0):
    S = D["S"]
    idx = np.arange(len(S))
    if step == "thu":
        m = S.weekday == 3
    elif step == "all":
        m = np.ones(len(S), bool)
    else:                                            # every k-th session
        m = idx % int(step) == 0
    return idx[m & (idx <= te) & (idx >= lo)]


def design(D, rows, y=None, tgt="rank"):
    """Stack rows. Returns X, t (target transform), row id, mask indices."""
    X, _ = features(D)
    elig = D["elig"][rows] & np.isfinite(D["Z"][rows]).all(2)
    if y is None:
        return X[rows], elig
    yy = y[rows].copy()
    m = elig & np.isfinite(yy)
    yy[~m] = np.nan
    if tgt == "rank":
        yt = xrank(yy)
    elif tgt == "z":
        mu, sd = np.nanmean(yy, 1, keepdims=True), np.nanstd(yy, 1, keepdims=True)
        yt = np.clip((yy - mu) / sd, -3, 3)
    else:
        yt = yy - np.nanmean(yy, 1, keepdims=True)
    rid = np.repeat(np.asarray(rows)[:, None], yy.shape[1], 1)
    return X[rows][m], yt[m], rid[m], m


def ic_rows(p, y, rid):
    """Mean per-row Spearman IC of flat predictions."""
    df = pd.DataFrame({"p": p, "y": y, "r": rid})
    return float(df.groupby("r")[["p", "y"]].apply(lambda g: g["p"].corr(g["y"], method="spearman")).mean())


def predict_rows(model, D, rows):
    X, _ = features(D)
    Xp = X[rows]
    p = model.predict(Xp.reshape(-1, Xp.shape[2])).reshape(Xp.shape[:2])
    ok = D["elig"][rows] & np.isfinite(D["Z"][rows]).all(2)
    p = p.astype(np.float64)
    p[~ok] = np.nan
    return p


# ---------------------------------------------------------------- base learners
def hgb(D, te, rows, seed, h=5, tgt="rank", iters=(50, 100, 200, 400), lr=0.03, leaves=8, msl=400, l2=1.0, mf=0.5,
        step="thu", pick=True, block_bag=0, val_weeks=104, info=None):
    """Gradient-boosted trees. Number of trees chosen by rank IC on the last `val_weeks` Thursdays of the training
    rows (never by MSE; early_stopping=False), then refit on all training rows."""
    y = target(D, h, te)
    tr = train_rows(D, te, step)
    X, t, rid, _ = design(D, tr, y, tgt)
    kw = dict(learning_rate=lr, max_leaf_nodes=leaves, min_samples_leaf=msl, l2_regularization=l2, max_features=mf,
              early_stopping=False, random_state=seed)
    n = iters[-1] if not pick else None
    if pick and len(iters) > 1:
        thu = train_rows(D, te, "thu")
        cut = thu[-val_weeks]
        a = rid < cut - 8                                 # gap so the inner targets do not overlap the inner validation
        b = (rid >= cut) & np.isin(rid, thu)
        m = HistGradientBoostingRegressor(max_iter=iters[-1], **kw).fit(X[a], t[a])
        best = (-9, iters[0])
        for i, p in enumerate(m.staged_predict(X[b]), 1):
            if i in iters:
                ic = ic_rows(p, t[b], rid[b])
                if ic > best[0] + 1e-4:
                    best = (ic, i)
        n = best[1]
        if info is not None:
            info.append((te, h, n, round(best[0], 4)))
    elif pick:
        n = iters[0]
    if block_bag:
        rng = np.random.default_rng(seed)
        blocks = (rid - rid.min()) // 126                 # half-year blocks
        ub = np.unique(blocks)
        out = []
        for _ in range(block_bag):
            sel = np.isin(blocks, rng.choice(ub, size=max(2, int(len(ub) * 0.6)), replace=False))
            m = HistGradientBoostingRegressor(max_iter=n, **{**kw, "random_state": int(rng.integers(1 << 30))}).fit(X[sel], t[sel])
            out.append(xrank(predict_rows(m, D, rows)))
        return np.mean(out, 0)
    m = HistGradientBoostingRegressor(max_iter=n, **kw).fit(X, t)
    return predict_rows(m, D, rows)


def forest(D, te, rows, seed, kind="et", h=5, tgt="rank", n=200, msl=1000, mf=0.33, step="thu", ms=None):
    y = target(D, h, te)
    X, t, rid, _ = design(D, train_rows(D, te, step), y, tgt)
    if kind == "et":
        m = ExtraTreesRegressor(n_estimators=n, min_samples_leaf=msl, max_features=mf, n_jobs=2, random_state=seed,
                                bootstrap=ms is not None, max_samples=ms)
    else:
        m = RandomForestRegressor(n_estimators=n, min_samples_leaf=msl, max_features=mf, n_jobs=2, random_state=seed,
                                  max_samples=ms or 0.5)
    m.fit(X, t)
    return predict_rows(m, D, rows)


def ridge(D, te, rows, seed, h=5, tgt="rank", lam=1.0, step="thu", cols=None):
    y = target(D, h, te)
    X, t, rid, _ = design(D, train_rows(D, te, step), y, tgt)
    Xf, _ = features(D)
    if cols is not None:
        X = X[:, cols]
    X = X.astype(np.float64)
    b = np.linalg.solve(X.T @ X + lam * len(t) / 100 * np.eye(X.shape[1]), X.T @ t)
    Xp = Xf[rows] if cols is None else Xf[rows][:, :, cols]
    p = Xp.astype(np.float64) @ b
    ok = D["elig"][rows] & np.isfinite(D["Z"][rows]).all(2)
    p[~ok] = np.nan
    return p


BASE = {}


def cached(name, D, te, rows, seed):
    """Base prediction with a process-level cache (the walk-forward calls each (te, seed) once per model)."""
    k = (name, int(te), int(seed), int(rows[0]), int(rows[-1]), len(rows))
    if k not in _P:
        _P[k] = BASE[name](D, te, rows, seed)
    return _P[k]


def ew(names):
    def f(D, te, rows, seed):
        with np.errstate(all="ignore"):
            return np.nanmean([xrank(cached(n, D, te, rows, seed)) for n in names], 0)
    return f


def stack(names, shrink=0.0, first_year=2011, mode="nnls"):
    """Stacking on genuinely out-of-sample base predictions: for the model predicting year Y, each base learner is
    refitted walk-forward for every earlier year y in first_year..Y-1 (train_end(y) -> Thursdays of y whose targets
    end by train_end(Y)); non-negative least squares of the rank target on the base ranks gives the weights, which are
    then shrunk toward equal weights by `shrink`. With no earlier year the weights are equal."""
    def f(D, te, rows, seed, info=None):
        S = D["S"]
        Y = int(S[rows[0]].year)
        A, b = [], []
        for y in range(first_year, Y):
            r = harness.thursdays(D, y)      # full year (shares the cache); targets after te are NaN in D['y5']
            Dm = dict(D)
            y5 = D["y5"].copy()
            tey = harness.train_end(D, y)
            y5[tey + 1:] = np.nan
            Dm["y5"] = y5
            Dm["e"] = D["e"]
            _F[id(Dm["e"])] = features(D)
            ps = [xrank(cached(n, Dm, tey, r, seed)) for n in names]
            yt = xrank(np.where(D["elig"][r], D["y5"][r].astype(np.float64), np.nan))
            m = np.isfinite(yt) & np.all([np.isfinite(p) for p in ps], 0)
            A.append(np.stack([p[m] for p in ps], 1))
            b.append(yt[m])
        k = len(names)
        w = np.ones(k) / k
        if A:
            A, b = np.concatenate(A), np.concatenate(b)
            if mode == "nnls":
                ww, _ = nnls(A, b)
            else:                                       # non-negative ridge: augment with sqrt(lam) I
                lam = 0.1 * len(b) / 12
                ww, _ = nnls(np.vstack([A, np.sqrt(lam) * np.eye(k)]), np.concatenate([b, np.zeros(k)]))
            if ww.sum() > 0:
                w = (1 - shrink) * ww / ww.sum() + shrink * w
        if info is not None:
            info.append((Y, seed, np.round(w, 2).tolist()))
        ps = np.stack([xrank(cached(n, D, te, rows, seed)) for n in names], 0)
        ok = np.isfinite(ps).all(0)
        p = np.tensordot(w, np.nan_to_num(ps), 1)
        p[~ok] = np.nan
        return p
    return f


def run(name, fn, note, seeds=(0, 1, 2)):
    import time
    t0 = time.time()
    D = RUN_D
    pred = harness.walk_forward(fn, seeds=seeds, D=D)
    res = harness.score(pred, name, os.path.join(os.path.dirname(os.path.abspath(__file__)), "RESULTS.jsonl"), note=note, D=D)
    by = " ".join("%+.3f" % v for v in res["ic_by_year"].values())
    print("%-28s IC %+.4f t %+.2f | %s | pos %d/7 | dec %+.1f%%/y sh %+.2f | %.0fs" % (
        name, res["ic"], res["ic_t"], by, sum(v > 0 for v in res["ic_by_year"].values()), res["decile_net_pct_per_year"],
        res["decile_net_sharpe"], time.time() - t0), flush=True)
    np.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pred_%s.npy" % name), pred.astype(np.float32))
    return pred


RUN_D = None
