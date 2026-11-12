"""Branch Q3_rankgbm: learning-to-rank objectives, monotone constraints and other tree ensembles vs squared-error trees.

Inputs are branch D's 25 inputs (5 characteristics + 20 ranked return features; D's docstring says 27) (D_ensembles/model.py, imported unchanged). Every model trains on the
Thursdays <= train_end only; the number of trees is chosen by rank IC on the last `val_weeks` training Thursdays
(8-row gap), never on the validation year, then the model is refitted on all training rows.
"""
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "3")
import numpy as np
import pandas as pd
import lightgbm as lgb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "D_ensembles"))
import harness  # noqa: E402
import model as dmodel  # noqa: E402  (branch D best = the declared control)

# return-direction features eligible for a monotone constraint (momentum / reversal); sign from training ICs
MONO = ["e1", "e5", "e10", "e21", "e63", "e126", "mom12_1", "r5", "r21", "sharpe63", "z5"]


def xrank(a):
    return pd.DataFrame(a).rank(axis=1, pct=True).to_numpy() - 0.5


def feature_names(D):
    X = dmodel._features(D)
    n = X.shape[2]
    names = ["Z%d" % i for i in range(5)] + ["e1", "e5", "e10", "e21", "e63", "e126", "mom12_1", "r5", "r21", "v10",
                                              "v21", "v63", "v250", "vratio", "max21", "min21", "sharpe63", "z5", "dd126", "beta"]
    assert len(names) == n, (len(names), n)
    return names


_FX = {}


def feats(D, kind="D"):
    """kind "D": branch D's inputs unchanged (NaN -> 0, Z clipped at +-4 and scaled).
    "nan": the same ranked features with NaN left native (LightGBM learns a default direction for missing values,
    which for trees is equivalent to missing indicators). "rankZ": Z cross-sectionally ranked instead of clipped.
    "nan_rankZ": both. Same backward-looking windows as D; row t uses rows <= t only."""
    if kind == "D":
        return dmodel._features(D)
    key = (id(D["e"]), kind)
    if key in _FX:
        return _FX[key]
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
    Z = D["Z"].astype(np.float64)
    if "rankZ" in kind:
        Zc = []
        for j in range(Z.shape[2]):
            a = Z[:, :, j].copy()
            a[~D["elig"]] = np.nan
            Zc.append(xrank(a))
        Z = np.stack(Zc, 2)
    else:
        Z = Z.clip(-4, 4) / 4
    X = np.concatenate([Z, np.stack(cols, 2)], 2)
    if "nan" not in kind:
        X = np.nan_to_num(X, nan=0.0)
    _FX.clear()
    _FX[key] = X.astype(np.float32)
    return _FX[key]


def ic_rows(p, y, rid):
    df = pd.DataFrame({"p": p, "y": y, "r": rid})
    return float(df.groupby("r")[["p", "y"]].apply(lambda g: g["p"].corr(g["y"], method="spearman")).mean())


def build(D, te, h=5, tgt="rank", lo_year=None, feat="D"):
    """Training design on Thursdays <= te: X, continuous rank target t (in [-0.5,0.5]), row ids (sorted)."""
    X = feats(D, feat)
    if tgt == "mh":
        S = D["S"]
        rws = np.where((S.weekday == 3) & (np.arange(len(S)) <= te))[0]
        acc = np.zeros((len(rws), X.shape[1]))
        cnt = np.zeros_like(acc)
        for hh in (3, 5, 10, 20):
            y = dmodel._target(D, hh, te)[rws].copy()
            m = D["elig"][rws] & np.isfinite(D["Z"][rws]).all(2) & np.isfinite(y)
            y[~m] = np.nan
            yr = xrank(y)
            acc += np.nan_to_num(yr)
            cnt += np.isfinite(yr)
        m = cnt == 4
        yy = np.where(m, acc / 4, np.nan)
        yy = xrank(yy)
        rid = np.repeat(rws[:, None], X.shape[1], 1)
        Xt, t, rid = X[rws][m], yy[m], rid[m]
    else:
        Xt, t, rid, rows = dmodel._design(D, X, dmodel._target(D, h, te), te)
    if lo_year is not None:
        k = D["S"][rid].year >= lo_year
        Xt, t, rid = Xt[k], t[k], rid[k]
    return Xt, t, rid


def grades(t, rid, n):
    """Integer relevance 0..n-1 from the within-week rank target."""
    return np.clip(np.floor((t + 0.5) * n), 0, n - 1).astype(np.int32)


def gauss(t):
    from scipy.stats import norm
    return norm.ppf(np.clip(t + 0.5, 1e-3, 1 - 1e-3))


def group_sizes(rid):
    _, c = np.unique(rid, return_counts=True)
    return c


def ranknet_objective(rid, t, K, seed, weighted):
    """Sampled pairwise logistic (RankNet) loss as a LightGBM custom objective: each row is paired with K random rows
    of the same Thursday; pair loss log(1 + exp(-sign(t_i - t_j)(s_i - s_j))), optionally weighted by |t_i - t_j|."""
    rng = np.random.default_rng(seed)
    starts = np.r_[0, np.cumsum(group_sizes(rid))[:-1]]
    sizes = group_sizes(rid)
    g = np.repeat(np.arange(len(sizes)), sizes)
    J = (starts[g][:, None] + (rng.random((len(t), K)) * sizes[g][:, None]).astype(np.int64))
    dy = t[:, None] - t[J]
    sgn = np.sign(dy)
    w = np.abs(dy) if weighted else (sgn != 0).astype(np.float64)
    w = w / max(w.mean(), 1e-12)

    def obj(preds, dataset):
        ds = (preds[:, None] - preds[J]) * sgn
        sig = 1.0 / (1.0 + np.exp(ds))          # sigmoid(-ds)
        grad = -(w * sgn * sig).sum(1) / K
        hess = (w * sig * (1 - sig)).sum(1) / K
        # symmetric part: row i is also the partner j of other rows
        np.add.at(grad, J.ravel(), ((w * sgn * sig) / K).ravel())
        np.add.at(hess, J.ravel(), ((w * sig * (1 - sig)) / K).ravel())
        return grad, hess + 1e-6
    return obj


def mono_signs(Xt, t, rid, names, feats=MONO):
    """+1/-1 per constrained feature = sign of its mean weekly Spearman IC with the training target; 0 elsewhere."""
    df = pd.DataFrame(Xt[:, [names.index(f) for f in feats]], columns=feats)
    df["y"], df["r"] = t, rid
    ic = df.groupby("r").apply(lambda g: g[feats].corrwith(g["y"], method="spearman")).mean()
    return [int(np.sign(ic[f])) if f in feats else 0 for f in names], ic


DEFAULT = dict(obj="l2", tgt="rank", h=5, leaves=8, lr=0.03, min_data=400, l2=1.0, colsample=0.5, bagging=1.0,
               boosting="gbdt", iters=(50, 100, 200, 400), val_weeks=104, ngrades=5, label_gain="linear", trunc=1000,
               mono=False, lo_years=None, feat="D", K=32, weighted=True, two_side=False, depth=-1, extra={})


def _params(c, seed, n_obj=None):
    p = dict(learning_rate=c["lr"], num_leaves=c["leaves"], max_depth=c["depth"], min_data_in_leaf=c["min_data"],
             lambda_l2=c["l2"], feature_fraction=c["colsample"], bagging_fraction=c["bagging"],
             bagging_freq=1 if c["bagging"] < 1 else 0, boosting=c["boosting"], seed=seed, num_threads=3,
             deterministic=True, force_row_wise=True, verbose=-1, feature_fraction_seed=seed, bagging_seed=seed,
             drop_seed=seed)
    o = c["obj"]
    if o in ("lambdarank", "rank_xendcg"):
        p["objective"] = o
        if o == "lambdarank":
            p["lambdarank_truncation_level"] = c["trunc"]
        g = c["ngrades"]
        p["label_gain"] = list(range(g)) if c["label_gain"] == "linear" else [2 ** i - 1 for i in range(g)]
        p["eval_at"] = [1000]
    elif o == "huber":
        p["objective"], p["alpha"] = "huber", 0.9
    elif o == "ranknet":
        pass
    else:
        p["objective"] = "l2"
    p.update(c["extra"])
    return p


def _dataset(c, X, t, rid, seed, sign=1.0):
    o = c["obj"]
    if o in ("lambdarank", "rank_xendcg"):
        lab = grades(sign * t, rid, c["ngrades"])
        return lgb.Dataset(X, lab, group=group_sizes(rid), free_raw_data=False), None
    if o == "ranknet":
        return lgb.Dataset(X, sign * t, free_raw_data=False), ranknet_objective(rid, sign * t, c["K"], seed, c["weighted"])
    y = sign * t
    if c["tgt"] in ("gauss", "mh_gauss"):
        y = gauss(y)
    return lgb.Dataset(X, y, free_raw_data=False), None


def _train(c, X, t, rid, seed, n, names, mono, sign=1.0):
    ds, fobj = _dataset(c, X, t, rid, seed, sign)
    p = _params(c, seed)
    if fobj is not None:
        p["objective"] = fobj
    if mono is not None:
        p["monotone_constraints"] = [int(sign * s) for s in mono]
        p["monotone_constraints_method"] = "advanced"
    return lgb.train(p, ds, num_boost_round=n)


def fit_lgb(D, te, pred_rows, seed, cfg, info=None):
    c = {**DEFAULT, **cfg}
    names = feature_names(D)
    lo = None
    if c["lo_years"]:
        lo = int(D["S"][te].year) - c["lo_years"] + 1
    tg = "mh" if c["tgt"] in ("mh", "mh_gauss") else "rank"
    X, t, rid = build(D, te, c["h"], tg, lo, c["feat"])
    mono = mono_signs(X, t, rid, names)[0] if c["mono"] else None
    sides = (1.0, -1.0) if c["two_side"] else (1.0,)
    S = D["S"]
    thu = np.where((S.weekday == 3) & (np.arange(len(S)) <= te))[0]
    Xp = feats(D, c["feat"])[pred_rows]
    ok = D["elig"][pred_rows] & np.isfinite(D["Z"][pred_rows]).all(2)
    outs = []
    for sg in sides:
        n = c["iters"][-1]
        if len(c["iters"]) > 1:
            cut = thu[-c["val_weeks"]]
            a, b = rid < cut - 8, rid >= cut
            m = _train(c, X[a], t[a], rid[a], seed, c["iters"][-1], names, mono, sg)
            best = (-9.0, c["iters"][0])
            for i in c["iters"]:
                ic = ic_rows(m.predict(X[b], num_iteration=i), t[b] * sg, rid[b])
                if ic > best[0] + 1e-4:
                    best = (ic, i)
            n = best[1]
            if info is not None:
                info.append((int(S[te].year), seed, sg, n, round(best[0], 4)))
        m = _train(c, X, t, rid, seed, n, names, mono, sg)
        p = m.predict(Xp.reshape(-1, Xp.shape[2])).reshape(Xp.shape[:2]).astype(np.float64)
        p[~ok] = np.nan
        outs.append(sg * xrank(p))
    return np.mean(outs, 0)


def control(D, te, pred_rows, seed):
    return dmodel.fit_predict(D, te, pred_rows, seed)
