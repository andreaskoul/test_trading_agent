"""Branch X2 (return after trading costs): shared code. Base predictor = branch D's boosted trees (27 ranked price
features, cross-sectional rank target, tree count chosen by rank IC on the last 104 training Thursdays), copied here.

What X2 adds, all without look-ahead:
* a fitted model (rows <= train_end only) scores the prediction rows AND the `LOOKBACK` Thursdays before the first
  prediction row; each of those scores uses features up to its own row only;
* exponential smoothing of each stock's cross-sectional rank across past weeks (half-life in weeks);
* a no-trade band: a name in last week's top (bottom) decile of the final score gets +band (-band) added to its rank,
  so it leaves the decile only when its rank falls more than `band` inside the threshold;
* horizons 10/20 sessions (targets end at or before row train_end+6, as y5 does), feature subsets, and a
  turnover-charged target.
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import harness  # noqa: E402

LOOKBACK = 12
HGB_ITERS = (50, 100, 200, 400)
FAST = ("e1", "e5", "r5", "z5")            # the 1- and 5-session reversal features
_F, _M = {}, {}
CACHE_DIR = None                           # optional disk cache of member scores (set by run.py only)


def xrank(a):
    return pd.DataFrame(a).rank(axis=1, pct=True).to_numpy() - 0.5


def features(D):
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
        cols.append(xrank(a))
    X = np.concatenate([D["Z"].astype(np.float64).clip(-4, 4) / 4, np.stack(cols, 2)], 2)
    _F.clear()
    _F[key] = (np.nan_to_num(X, nan=0.0).astype(np.float32), ["Z%d" % i for i in range(5)] + list(f))
    return _F[key]


def target(D, h, te):
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


def _ic(p, y, rid):
    df = pd.DataFrame({"p": p, "y": y, "r": rid})
    return float(df.groupby("r")[["p", "y"]].apply(lambda g: g["p"].corr(g["y"], method="spearman")).mean())


def _hgb(Xt, t, rid, rows, seed):
    kw = dict(learning_rate=0.03, max_leaf_nodes=8, min_samples_leaf=400, l2_regularization=1.0, max_features=0.5,
              early_stopping=False, random_state=seed)
    cut = rows[-104]
    a, b = rid < cut - 8, rid >= cut
    m = HistGradientBoostingRegressor(max_iter=HGB_ITERS[-1], **kw).fit(Xt[a], t[a])
    best = (-9.0, HGB_ITERS[0])
    for i, p in enumerate(m.staged_predict(Xt[b]), 1):
        if i in HGB_ITERS:
            ic = _ic(p, t[b], rid[b])
            if ic > best[0] + 1e-4:
                best = (ic, i)
    return HistGradientBoostingRegressor(max_iter=best[1], **kw).fit(Xt, t)


def ext_rows(D, pred_rows):
    """The LOOKBACK Thursdays before the first prediction row, then the prediction rows."""
    S = D["S"]
    thu = np.where((S.weekday == 3) & (np.arange(len(S)) < pred_rows[0]))[0]
    return np.concatenate([thu[-LOOKBACK:], np.asarray(pred_rows)])


def member(D, te, pred_rows, seed, tag, h):
    """Raw scores of one fitted model on ext_rows. tag: 'all' (27 features), 'slow' (without FAST), 'tc' (27 features,
    5-session target charged 10 bp when the first-stage in-sample score changed decile since the previous Thursday)."""
    global CACHE_DIR
    key = (tag, h, int(te), int(seed), int(pred_rows[0]), len(pred_rows))
    if key in _M:
        return _M[key]
    path = CACHE_DIR and os.path.join(CACHE_DIR, "%s_h%d_%d_%d.npy" % (tag, h, te, seed))
    if path and os.path.exists(path):
        _M[key] = np.load(path).astype(np.float64)
        return _M[key]
    X, names = features(D)
    if tag == "slow":
        X = X[:, :, [i for i, n in enumerate(names) if n not in FAST]]
    S = D["S"]
    rows = np.where((S.weekday == 3) & (np.arange(len(S)) <= te))[0]
    y = target(D, h, te)[rows].copy()
    okr = D["elig"][rows] & np.isfinite(D["Z"][rows]).all(2)
    if tag == "tc":
        p1 = np.full(y.shape, np.nan)
        mk = ("model", "all", 5, int(te), int(seed))
        if mk not in _M:                                                   # stage-1 scores came from the disk cache: refit
            keep, CACHE_DIR = CACHE_DIR, None
            _M.pop(("all", 5, int(te), int(seed), int(pred_rows[0]), len(pred_rows)), None)
            member(D, te, pred_rows, seed, "all", 5)
            CACHE_DIR = keep
        m1 = _M[mk]
        p1[okr] = m1.predict(X[rows][okr])                                 # in-sample scores, rows <= train_end
        dec = np.ceil(pd.DataFrame(p1).rank(axis=1, pct=True).to_numpy() * 10)
        changed = np.zeros(y.shape, bool)
        changed[1:] = dec[1:] != dec[:-1]
        y = y - 2 * harness.COST * changed
    m = okr & np.isfinite(y)
    y[~m] = np.nan
    rid = np.repeat(rows[:, None], y.shape[1], 1)
    model = _hgb(X[rows][m], xrank(y)[m], rid[m], rows, seed)
    _M[("model", tag, h, int(te), int(seed))] = model
    er = ext_rows(D, pred_rows)
    Xp = X[er]
    p = model.predict(Xp.reshape(-1, Xp.shape[2])).reshape(Xp.shape[:2]).astype(np.float64)
    p[~(D["elig"][er] & np.isfinite(D["Z"][er]).all(2))] = np.nan
    if path:
        np.save(path, p.astype(np.float32))
    _M[key] = p
    return p


def ema(R, hl):
    """Exponentially weighted mean of each stock's past ranks (rows = weeks, oldest first); weights renormalised over
    the weeks with a rank; NaN where the current week has none. Uses rows <= j for row j."""
    w = 0.5 ** (1.0 / hl)
    out = np.full(R.shape, np.nan)
    num, den = np.zeros(R.shape[1]), np.zeros(R.shape[1])
    for j in range(len(R)):
        f = np.isfinite(R[j])
        num, den = w * num + np.where(f, R[j], 0.0), w * den + f
        out[j] = np.where(f, num / np.maximum(den, 1e-12), np.nan)
    return out


def band(R, b):
    """No-trade band on the decile book: last week's top (bottom) decile members get +b (-b) on this week's rank."""
    out = np.full(R.shape, np.nan)
    top = bot = np.zeros(R.shape[1], bool)
    for j in range(len(R)):
        r = pd.Series(R[j]).rank(pct=True).to_numpy()
        a = r + b * top - b * bot
        out[j] = a
        q = pd.Series(a).rank(pct=True).to_numpy()
        top, bot = q > 0.9, q <= 0.1
    return out


def make(members, hl=None, b=0.0):
    """members: ((tag, horizon, weight), ...). Returns fit_predict."""
    def fit_predict(D, train_end, pred_rows, seed):
        ps = [xrank(member(D, train_end, pred_rows, seed, tag, h)) for tag, h, _ in members]
        w = np.array([x[2] for x in members], float)
        s = np.tensordot(w / w.sum(), np.nan_to_num(np.stack(ps)), 1)
        s[~np.isfinite(np.stack(ps)).all(0)] = np.nan
        s = xrank(s)
        if hl:
            s = ema(s, hl)
        if b:
            s = band(s, b)
        return s[-len(pred_rows):]
    return fit_predict
