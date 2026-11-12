"""Branch X1 (combine the round-1 winners): shared code. Imports only numpy/pandas/sklearn/torch and the harness.

Pieces copied from round 1 (not imported, so this folder is self-contained):
  * D_ensembles: 27 ranked inputs, boosted trees on a cross-sectional rank target, multi-horizon targets;
  * C_features: 24 price characteristics + 8 market-state interactions, Fama-MacBeth ridge;
  * A_loss: small MLP (32, 16), squared error on the cross-sectionally ranked target, all sessions;
  * E_regime: the fixed panic rule (market 252-session return < 0 and 21-session volatility above the 67th
    percentile of rows <= train_end), applied here as an overlay: the final score is residualised on momentum.
Every feature at row t uses rows <= t. Every target ends at or before row train_end + 6 (the end of y5[train_end]).
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import harness  # noqa: E402

HORIZONS = (3, 5, 10, 20)
HGB_ITERS = (50, 100, 200, 400)
DISK = None            # set to a directory by run.py to persist member predictions between processes
_FD, _FC, _P = {}, {}, {}

C_FEATS = ["rev1", "rev5", "rev21", "erev1", "erev5", "erev21", "mom63", "mom126", "mom252", "emom126", "emom252",
           "resmom252", "ivol21", "ivol63", "tvol21", "beta", "skew63", "max21", "dvol", "hi52", "vsrev5", "vsrev21",
           "vsmom252", "vserev5"]
C_INTER = [("rev5", "mvol"), ("erev5", "mvol"), ("rev21", "mvol"), ("erev21", "mvol"), ("rev1", "mvol"),
           ("mom252", "mvol"), ("rev5", "mret"), ("mom252", "mret")]


def xrank(a):
    return pd.DataFrame(a).rank(axis=1, pct=True).to_numpy() - 0.5


# ------------------------------------------------------------------ features
def feats_D(D):
    """Branch D's 27 inputs: (X float32 (T,N,27), ok)."""
    key = id(D["e"])
    if key not in _FD:
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
        _FD[key] = (np.nan_to_num(X, nan=0.0).astype(np.float32), D["elig"] & np.isfinite(D["Z"]).all(2))
    return _FD[key]


def feats_C(D):
    """Branch C's design: (X float32 (T,N,32) = 24 ranked characteristics + 8 state interactions, ok, state (T,2))."""
    key = id(D["r"])
    if key not in _FC:
        r, e = pd.DataFrame(D["r"].astype(np.float64)), pd.DataFrame(D["e"].astype(np.float64))

        def rs(x, n, mp=None):
            return x.rolling(n, min_periods=mp or max(2, int(n * 0.8))).sum()

        def sd(x, n):
            return x.rolling(n, min_periods=int(n * 0.8)).std()

        F = {}
        for n in (1, 5, 21):
            F["rev%d" % n], F["erev%d" % n] = rs(r, n, n), rs(e, n, n)
        for n in (63, 126, 252):
            F["mom%d" % n] = rs(r, n) - rs(r, 21, 21)
        for n in (126, 252):
            F["emom%d" % n] = rs(e, n) - rs(e, 21, 21)
        F["ivol21"], F["ivol63"], F["tvol21"] = sd(e, 21), sd(e, 63), sd(r, 21)
        F["resmom252"] = F["emom252"] / sd(e, 252)
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
        elig = D["elig"]

        def rk(a):
            a = np.where(elig & np.isfinite(a), a, np.nan)
            u = pd.DataFrame(a).rank(axis=1).to_numpy()
            n = np.sum(np.isfinite(a), 1, keepdims=True)
            return ((u - 0.5) / np.maximum(n, 1) - 0.5) * np.sqrt(12.0)

        cols = {f: rk(F[f].to_numpy()) for f in C_FEATS}
        rm = pd.Series(D["rm"].astype(np.float64))
        st = {"mvol": (rm.rolling(21, min_periods=15).std().expanding(min_periods=60).rank(pct=True) - 0.5).fillna(0.0).to_numpy(),
              "mret": (rm.rolling(21, min_periods=15).sum().expanding(min_periods=60).rank(pct=True) - 0.5).fillna(0.0).to_numpy()}
        X = np.stack([cols[f] for f in C_FEATS] + [cols[f] * st[s][:, None] for f, s in C_INTER], 2)
        ok = elig & np.isfinite(cols["rev5"])
        _FC[key] = (np.where(np.isfinite(X), X, 0.0).astype(np.float32), ok, np.c_[st["mvol"], st["mret"]].astype(np.float32))
    return _FC[key]


def feats(D, fs):
    """fs: 'D' (27), 'C' (32, with interactions), 'Ct' (24 characteristics + the 2 state scalars, for trees),
    'U' (D's 27 + C's 24 + 2 state scalars)."""
    if fs == "D":
        return feats_D(D)
    X, ok, st = feats_C(D)
    if fs == "C":
        return X, ok
    key = (id(D["r"]), fs)
    if key not in _FC:
        S = np.broadcast_to(st[:, None, :], X.shape[:2] + (2,))
        parts = [X[:, :, :24], S]
        if fs == "U":
            XD, okD = feats_D(D)
            parts, ok = [XD] + parts, ok & okD
        _FC[key] = (np.concatenate(parts, 2).astype(np.float32), ok)
    return _FC[key]


def target(D, h, te):
    """Sum of e over rows t+2 .. t+1+h (the y5 convention); no window ends after row te+6. h=5 is D['y5'],
    which the harness has already blanked after train_end."""
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


# ------------------------------------------------------------------ members
def _ic(p, y, rid):
    df = pd.DataFrame({"p": p, "y": y, "r": rid})
    return float(df.groupby("r")[["p", "y"]].apply(lambda g: g["p"].corr(g["y"], method="spearman")).mean())


def hgb(D, te, rows, seed, fs="D", h=5):
    """Branch D's boosted trees: Thursdays <= te, rank target, number of trees by rank IC on the last 104 training
    Thursdays (8-row gap), refit on all training rows. early_stopping=False."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    X, ok = feats(D, fs)
    S = D["S"]
    tr = np.where((S.weekday == 3) & (np.arange(len(S)) <= te))[0]
    yy = target(D, h, te)[tr]
    m = ok[tr] & np.isfinite(yy)
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
    return p


def fmridge(D, te, rows, seed, fs="C", h=5, lam=0.1):
    """Branch C's learner: Fama-MacBeth average of per-session ridge slopes, per-day standardised target, all
    sessions <= te. Deterministic."""
    X, ok = feats(D, fs)
    y = np.where(D["elig"][: te + 1], target(D, h, te)[: te + 1], np.nan)
    with np.errstate(all="ignore"):
        y = y - np.nanmean(y, 1, keepdims=True)
        y = np.clip(y / (np.nanstd(y, 1, keepdims=True) + 1e-12), -3, 3)
    m = np.isfinite(y) & ok[: te + 1]
    Xm = X[: te + 1] * m[:, :, None]
    A = np.einsum("tnk,tnj->tkj", Xm, Xm, optimize=True).astype(np.float64)
    c = np.einsum("tnk,tn->tk", Xm, np.where(m, y, 0.0).astype(np.float32), optimize=True).astype(np.float64)
    n = m.sum(1).astype(np.float64)
    K, bs = X.shape[2], []
    for d in np.where(n >= 50)[0]:
        Ad = A[d] / n[d]
        bs.append(np.linalg.solve(Ad + lam * np.trace(Ad) / K * np.eye(K), c[d] / n[d]))
    p = X[rows].astype(np.float64) @ np.mean(bs, 0)
    return np.where(ok[rows], p, np.nan)


def mlp(D, te, rows, seed, fs="C", h=5, epochs=8, batch=64, lr=1e-3, wd=1e-4, hidden=(32, 16), drop=0.1):
    """Branch A's network and optimiser: MLP (32, 16), squared error on the cross-sectional rank of the target,
    every session <= te, batches of 64 dates."""
    import torch
    import torch.nn as nn
    torch.set_num_threads(3)
    torch.manual_seed(seed)
    X, ok = feats(D, fs)
    tr = np.arange(260, te + 1)
    yy = target(D, h, te)[tr]
    m = ok[tr] & np.isfinite(yy)
    keep = m.sum(1) >= 50
    tr, yy, m = tr[keep], yy[keep], m[keep]
    yy[~m] = np.nan
    T = torch.tensor(np.nan_to_num(xrank(yy)), dtype=torch.float32)
    Xt, mt = torch.tensor(X[tr]), torch.tensor(m, dtype=torch.float32)
    layers, d = [], X.shape[2]
    for k in hidden:
        layers += [nn.Linear(d, k), nn.ReLU(), nn.Dropout(drop)]
        d = k
    net = nn.Sequential(*layers, nn.Linear(d, 1))
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=wd)
    g = torch.Generator().manual_seed(seed)
    net.train()
    for _ in range(epochs):
        perm = torch.randperm(len(tr), generator=g)
        for i in range(0, len(perm) - batch // 2, batch):
            b = perm[i:i + batch]
            s = net(Xt[b]).squeeze(-1)
            loss = (((s - T[b]) ** 2 * mt[b]).sum(1) / mt[b].sum(1).clamp(min=1)).mean()
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
    net.eval()
    with torch.no_grad():
        p = net(torch.tensor(X[rows])).squeeze(-1).numpy().astype(np.float64)
    return np.where(ok[rows], p, np.nan)


KINDS = {"hgb": hgb, "fm": fmridge, "mlp": mlp}


def member(spec, D, te, rows, seed):
    """spec = (kind, feature set, horizon). Cached in memory and, when DISK is set, on disk by (spec, te, seed)."""
    kind, fs, h = spec
    s = 0 if kind == "fm" else int(seed)
    k = (kind, fs, h, int(te), s, int(rows[0]), int(rows[-1]), len(rows))
    if k in _P:
        return _P[k]
    path = DISK and os.path.join(DISK, "_".join(str(x) for x in k) + ".npy")
    if path and os.path.exists(path):
        p = np.load(path)
    else:
        p = KINDS[kind](D, te, rows, s, fs=fs, h=h)
        if path:
            os.makedirs(DISK, exist_ok=True)
            np.save(path, p)
    _P[k] = p
    return p


# ------------------------------------------------------------------ the panic overlay (branch E's fixed rule)
def panic_rows(D, te, rows, vol_q=0.67):
    """True for prediction rows where the market's 252-session return is negative and its 21-session volatility is
    above the vol_q quantile of rows <= te. Uses D['rm'] up to each row only."""
    rm = pd.Series(D["rm"].astype(np.float64))
    trend, vol = rm.rolling(252).sum().to_numpy(), rm.rolling(21).std().to_numpy()
    thr = np.nanquantile(vol[: te + 1], vol_q)
    return (trend[rows] < 0) & (vol[rows] > thr)


def remove_momentum(score, D, rows, flag):
    """In flagged rows, replace the score by its cross-sectional residual on the 12-1 momentum characteristic
    (D['Z'][..., 0]); names without the characteristic keep their demeaned score."""
    out = score.copy()
    for i, t in enumerate(rows):
        if not flag[i]:
            continue
        s, z = score[i], D["Z"][t][:, 0].astype(np.float64)
        m = np.isfinite(s) & np.isfinite(z)
        if m.sum() < 50:
            continue
        zc, sc = z[m] - z[m].mean(), s[m] - s[m].mean()
        beta = (zc @ sc) / (zc @ zc)
        o = s - np.nanmean(s)
        o[m] = sc - beta * zc
        out[i] = o
    return out


def combine(specs, panic=False, groups=None):
    """Equal-weight average of the members' cross-sectional ranks. groups: optional list of lists of specs; ranks are
    averaged within a group first, then across groups (so each learner family has the same weight)."""
    def fit_predict(D, train_end, pred_rows, seed):
        te, rows = int(train_end), np.asarray(pred_rows)
        with np.errstate(all="ignore"):
            if groups:
                p = np.nanmean([xrank(np.nanmean([xrank(member(s, D, te, rows, seed)) for s in g], 0)) for g in groups], 0)
            else:
                p = np.nanmean([xrank(member(s, D, te, rows, seed)) for s in specs], 0)
        if panic:
            p = remove_momentum(p, D, rows, panic_rows(D, te, rows))
        return p
    return fit_predict
