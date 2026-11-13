"""Branch Q7 (Layer 3, Amendment 8): industry-relative and announcement-aware reversal for the D trees.

    from model import make
    pred = harness.walk_forward(make("F1"), seeds=(0, 1, 2))

Configurations (STATE.json plan, declared before scoring):
  ref  D trees as in D_ensembles/model.py: 27 inputs, HGB on the 5-session cross-sectional rank target.
  F1   D's 27 inputs + 9 added (ADDED below), same HGB, 5-session target.
  F2   F1's inputs, rank average of HGB at 3/5/10/20-session targets (the D_hgb_mh form).
  H1   D's 27 inputs; target horizon per name by tercile of 63-session mean FINRA share volume on each Thursday
       (low -> 20, mid -> 10, high -> 5 sessions).

Typed inputs (CLAUDE.md rules 1-4), frozen by load_inputs() with their sha256 checked:
  * industry: .cache/p8/gics.json "firms"[ticker]["industry_code"] / ["sector"] (current S&P 500/400 lists, applied
    to the past: a disclosed look-ahead; names not in today's lists have no code -> typed missing);
  * announcements: .cache/p8/decay_earnings_events.parquet columns ticker, t0 only (t0 <= 2019-12-31); no outcome
    column is read;
  * share volume: harness.load_extra("finra")["total"].
Every feature at row t uses rows <= t.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import harness  # noqa: E402

ROOT = harness.ROOT
GICS = os.path.join(ROOT, ".cache", "p8", "gics.json")
EVENTS = os.path.join(ROOT, ".cache", "p8", "decay_earnings_events.parquet")
SHA = {GICS: "daba07b7b767142226359d5e2e8927b4fe3e398daaa96d92c62c3713648cfb2c",
       EVENTS: "a7831d1d55328788a885d6e5e3b41c05470a5e800037f36cd272e9d2cb94eed0"}
END = pd.Timestamp("2019-12-31")
HGB_ITERS = (50, 100, 200, 400)
HORIZONS = (3, 5, 10, 20)
H1_MAP = (20, 10, 5)                      # volume tercile 0 (low), 1 (mid), 2 (high)
ADDED = ["irel_r1", "irel_r5", "irel_r21", "irel_e1", "irel_e5", "irel_e21", "imom5", "imom21", "emask5"]
_C = {}


class InputDefect(Exception):
    pass


def xrank(a):
    return pd.DataFrame(a).rank(axis=1, pct=True).to_numpy() - 0.5


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def load_inputs(D):
    """Frozen typed inputs aligned to D's columns: industry code (-1 missing), sector code (-1 missing), event matrix."""
    key = ("inp", id(D["e"]))
    if key in _C:
        return _C[key]
    for p, h in SHA.items():
        if _sha(p) != h:
            raise InputDefect(f"{p}: sha256 changed since first use (rule 4)")
    g = json.load(open(GICS))
    firms = g.get("firms")
    if not isinstance(firms, dict) or len(firms) < 800:
        raise InputDefect("gics.json: 'firms' missing or too small")
    names = D["names"]
    ic, sc = {}, {}
    ind, sec = np.full(len(names), -1), np.full(len(names), -1)
    for j, n in enumerate(names):
        f = firms.get(n)
        if f is None:
            continue
        if not str(f.get("industry_code", "")).isdigit() or len(str(f["industry_code"])) != 6 or not f.get("sector"):
            raise InputDefect(f"gics.json: {n} lacks a typed 6-digit industry_code or sector")
        ind[j] = ic.setdefault(f["industry_code"], len(ic))
        sec[j] = sc.setdefault(f["sector"], len(sc))
    ev = pd.read_parquet(EVENTS, columns=["ticker", "t0"])
    if not np.issubdtype(ev["t0"].dtype, np.datetime64):
        raise InputDefect("events: t0 is not a typed datetime")
    ev = ev[ev["t0"] <= END]
    ix = {n: j for j, n in enumerate(names)}
    sidx = pd.Index(D["S"])
    ev = ev[ev["ticker"].isin(ix) & ev["t0"].isin(sidx)]
    E = np.zeros(D["e"].shape, bool)
    E[sidx.get_indexer(ev["t0"]), [ix[t] for t in ev["ticker"]]] = True
    _C[key] = (ind, sec, E)
    return _C[key]


def _loo_group_mean(X, M, grp, k):
    """Leave-one-out equal-weight mean of X over names in the same group with M true, per row. NaN if group missing."""
    G = np.zeros((X.shape[1], k))
    ok = grp >= 0
    G[np.where(ok)[0], grp[ok]] = 1.0
    Xm = np.where(M, X, 0.0)
    s, c = Xm @ G, M.astype(float) @ G
    gi = np.where(ok, grp, 0)
    S_, C_ = s[:, gi], c[:, gi]
    S_, C_ = S_ - Xm, C_ - M
    out = np.where(C_ >= 2, S_ / np.maximum(C_, 1), np.nan)          # >= 2 others, i.e. >= 3 members with self
    out[:, ~ok] = np.nan
    return out


def added_features(D):
    """The 9 added raw (unranked) features, (T, N, 9) float64, rows <= t only."""
    key = ("add", id(D["e"]))
    if key in _C:
        return _C[key]
    ind, sec, E = load_inputs(D)
    el = D["elig"]
    out = {}
    loo = {}
    for nm, X in (("r", D["r"].astype(np.float64)), ("e", D["e"].astype(np.float64))):
        M = el & np.isfinite(X)
        a = _loo_group_mean(X, M, ind, ind.max() + 1)
        b = _loo_group_mean(X, M, sec, sec.max() + 1)
        loo[nm] = np.where(np.isfinite(a), a, b)
        x = pd.DataFrame(X)
        gm = pd.DataFrame(loo[nm])
        for w in (1, 5, 21):
            mp = max(1, int(w * 0.8))
            out[f"irel_{nm}{w}"] = (x.rolling(w, min_periods=mp).sum() - gm.rolling(w, min_periods=mp).sum()).to_numpy()
    gm = pd.DataFrame(loo["r"])
    out["imom5"] = gm.rolling(5, min_periods=4).sum().to_numpy()
    out["imom21"] = gm.rolling(21, min_periods=17).sum().to_numpy()
    e = D["e"].astype(np.float64)
    mask = E | np.vstack([np.zeros((1, E.shape[1]), bool), E[:-1]])     # t0 and t0+1
    em = pd.DataFrame(np.where(mask & np.isfinite(e), 0.0, e)).rolling(5, min_periods=4).sum().to_numpy()
    covered = pd.DataFrame(E.astype(float)).rolling(126, min_periods=1).max().to_numpy() > 0
    out["emask5"] = np.where(covered, em, np.nan)
    _C[key] = np.stack([out[k] for k in ADDED], 2)
    return _C[key]


def _d_features(D):
    """Branch D's 27 inputs, exactly as D_ensembles/model.py."""
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
    return [v.to_numpy() for v in f.values()]


def features(D, fs):
    """fs 'D' -> (T, N, 27); 'F' -> (T, N, 36) = D's 27 + ADDED, ranked across eligible names, NaN -> 0."""
    key = ("X", fs, id(D["e"]))
    if key in _C:
        return _C[key]
    raw = _d_features(D)
    if fs == "F":
        A = added_features(D)
        raw += [A[:, :, i] for i in range(A.shape[2])]
    cols = []
    for a in raw:
        a = a.copy()
        a[~D["elig"]] = np.nan
        cols.append(xrank(a))
    X = np.concatenate([D["Z"].astype(np.float64).clip(-4, 4) / 4, np.stack(cols, 2)], 2)
    for k in [k for k in _C if k[0] == "X"]:
        del _C[k]
    _C[key] = np.nan_to_num(X, nan=0.0).astype(np.float32)
    return _C[key]


def target(D, h, te):
    """Sum of e over rows t+2 .. t+1+h (y5 convention); no window ends after row te+6."""
    if h == 5:
        y = D["y5"].astype(np.float64).copy()
        y[te + 1:] = np.nan
        return y
    e = D["e"].astype(np.float64)
    cs, nanc = np.cumsum(np.nan_to_num(e), 0), np.cumsum(np.isnan(e), 0)
    y = np.full(e.shape, np.nan)
    t = np.arange(0, min(te, te + 5 - h) + 1)
    t = t[t + 1 + h < len(e)]
    y[t] = np.where((nanc[t + 1 + h] - nanc[t + 1]) > 0, np.nan, cs[t + 1 + h] - cs[t + 1])
    return y


def volume_tercile(D):
    """Per row, the tercile (0 low, 1 mid, 2 high) of the 63-session mean FINRA total share volume among eligible
    names with a value; -1 where missing. Rows <= t only."""
    key = ("terc", id(D["e"]))
    if key in _C:
        return _C[key]
    V = harness.load_extra("finra")["total"].astype(np.float64)
    if V.shape != D["e"].shape:
        raise InputDefect("finra total: shape does not match the panel")
    v = pd.DataFrame(V).rolling(63, min_periods=40).mean().to_numpy().copy()
    v[~D["elig"]] = np.nan
    p = pd.DataFrame(v).rank(axis=1, pct=True).to_numpy()
    t = np.where(np.isfinite(p), np.minimum((p * 3 - 1e-9).astype(int), 2), -1)
    _C[key] = t
    return t


def h1_target(D, te):
    """The name's cross-sectional rank (all names, same horizon) of its own-horizon return; horizon by volume tercile."""
    terc = volume_tercile(D)
    ranks = {h: xrank(target(D, h, te)) for h in set(H1_MAP)}
    y = ranks[5].copy()
    for k, h in enumerate(H1_MAP):
        y = np.where(terc == k, ranks[h], y)
    return y


def _ic(p, y, rid):
    df = pd.DataFrame({"p": p, "y": y, "r": rid})
    return float(df.groupby("r")[["p", "y"]].apply(lambda g: g["p"].corr(g["y"], method="spearman")).mean())


def hgb(D, te, rows, seed, fs="D", h=5, return_model=False):
    """Branch D's boosted trees: Thursdays <= te, rank target, trees by rank IC on the last 104 training Thursdays
    (8-row gap), refit on all training rows. h is a horizon in sessions or "H1"."""
    X = features(D, fs)
    ok = D["elig"] & np.isfinite(D["Z"]).all(2)
    S = D["S"]
    tr = np.where((S.weekday == 3) & (np.arange(len(S)) <= te))[0]
    if h == "H1":
        yy = h1_target(D, te)[tr]
    else:
        yy = target(D, h, te)[tr]
    m = ok[tr] & np.isfinite(yy)
    yy = yy.copy()
    yy[~m] = np.nan
    rid = np.repeat(tr[:, None], yy.shape[1], 1)[m]
    Xt, t = X[tr][m], xrank(yy)[m]
    kw = dict(learning_rate=0.03, max_leaf_nodes=8, min_samples_leaf=400, l2_regularization=1.0, max_features=0.5,
              early_stopping=False, random_state=seed)
    cut = tr[-104]
    a, b = rid < cut - 8, rid >= cut
    mdl = HistGradientBoostingRegressor(max_iter=HGB_ITERS[-1], **kw).fit(Xt[a], t[a])
    best = (-9.0, HGB_ITERS[0])
    for i, p in enumerate(mdl.staged_predict(Xt[b]), 1):
        if i in HGB_ITERS:
            ic = _ic(p, t[b], rid[b])
            if ic > best[0] + 1e-4:
                best = (ic, i)
    mdl = HistGradientBoostingRegressor(max_iter=best[1], **kw).fit(Xt, t)
    Xp = X[rows]
    p = mdl.predict(Xp.reshape(-1, Xp.shape[2])).reshape(Xp.shape[:2]).astype(np.float64)
    p[~ok[rows]] = np.nan
    return (p, mdl, best[1]) if return_model else p


CONFIGS = {"ref": [("D", 5)], "F1": [("F", 5)], "F2": [("F", h) for h in HORIZONS], "H1": [("D", "H1")],
           "ref_mh": [("D", h) for h in HORIZONS]}


def make(name):
    specs = CONFIGS[name]

    def fit_predict(D, train_end, pred_rows, seed):
        rows = np.asarray(pred_rows)
        with np.errstate(all="ignore"):
            return np.nanmean([xrank(hgb(D, int(train_end), rows, seed, fs, h)) for fs, h in specs], 0)
    return fit_predict


BEST = "F2"                    # best by the branch rule (STATE.json); its gain over ref_mh is attributed to the GICS coverage leak (REPORT.md)
fit_predict = make(BEST)
