"""Quant trials · Stage 1 runner and ledger (inner folds 2019/2020/2021 only; nothing after 2021 is scored).

    python trials.py run <TRIAL> [--h 5] [--folds 2019 2020 2021]   # A B C D E F G as in the plan
    python trials.py compare <hashA> <hashB>                         # paired weekly-IC difference
    python trials.py report                                          # TRIALS.md from trials.csv

Every run appends one row per fold to reports/research/quant_trials/trials.csv (config, hash, metrics) and
keeps its (D, N) predictions in .cache/quant_trials/preds/ so any two configs can be paired later.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

import features as F
import models as M
import panel as P

LEDGER = os.path.join(P.REPORT, "trials.csv")
PREDS = os.path.join(P.CACHE, "preds")
os.makedirs(PREDS, exist_ok=True)
STAGE1_LAST_YEAR = 2021
COLS = ["time", "git", "hash", "trial", "arm", "model", "h", "placebo", "variant", "fold", "n_weeks", "ic", "ic_t",
        "spread", "ndcg5", "secs", "cfg", "info"]                    # hard stop for this stage: 2022-25 is the confirmation window


def chash(cfg):
    return hashlib.sha1(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:10]


def git_rev():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return ""


# ------------------------------------------------------------------------------------------------- text arms
class Text:
    """Fold-fitted text encoders. Everything that learns (PCA, k-means, Siamese) sees training rows only."""

    def __init__(self, p):
        self.p = p
        self._st = {}

    def state(self, hl):
        if hl not in self._st:
            self._st[hl] = self.p.state(hl)
        return self._st[hl]

    def _train_rows(self, train):
        """Training decisions with news that day: (d, i) and today's mean vectors."""
        d, i = np.where(self.p.n[train] > 0)
        d = train[d]
        return d, i, self.state(0)[d, i]

    def pca(self, train, k=64, seed=0):
        from sklearn.decomposition import PCA
        _, _, V = self._train_rows(train)
        rng = np.random.default_rng(seed)
        if len(V) > 40000:
            V = V[rng.choice(len(V), 40000, replace=False)]
        return PCA(k, random_state=seed).fit(V)

    def build(self, arm, train, y, h):
        """(D, N, k) semantic block for `arm`, plus info."""
        p = self.p
        if arm in ("pca_today", "pca_hl5", "pca_hl20"):
            hl = {"pca_today": 0, "pca_hl5": 5, "pca_hl20": 20}[arm]
            pc = self.pca(train)
            S = self.state(hl)
            Z = pc.transform(S.reshape(-1, S.shape[-1])).reshape(p.D, p.N, -1).astype(np.float32)
            Z[np.abs(S).sum(-1) == 0] = 0.0
            return Z, {"pca_var": float(pc.explained_variance_ratio_.sum())}
        if arm == "proto_hl5":
            from sklearn.cluster import KMeans
            _, _, V = self._train_rows(train)
            V = V / np.linalg.norm(V, axis=1, keepdims=True)
            rng = np.random.default_rng(0)
            if len(V) > 40000:
                V = V[rng.choice(len(V), 40000, replace=False)]
            km = KMeans(16, n_init=4, random_state=0).fit(V)
            C = km.cluster_centers_ / np.linalg.norm(km.cluster_centers_, axis=1, keepdims=True)
            S = self.state(5)
            nrm = np.linalg.norm(S, axis=-1, keepdims=True)
            U = np.where(nrm > 0, S / np.maximum(nrm, 1e-9), 0.0)
            return (U @ C.T.astype(np.float32)).astype(np.float32), {}
        if arm == "siamese_hl5":
            d, i, V = self._train_rows(train)
            t = y[d, i]
            ok = np.isfinite(t)
            d, i, V, t = d[ok], i[ok], V[ok], t[ok]
            q = np.quantile(t, [1 / 3, 2 / 3])
            lab = np.digitize(t, q)
            tower, auc = M.siamese(V, lab)
            S = self.state(5)
            import torch
            with torch.no_grad():
                Z = np.concatenate([tower(torch.as_tensor(S[k: k + 64].reshape(-1, S.shape[-1]))).numpy()
                                    for k in range(0, p.D, 64)]).reshape(p.D, p.N, -1).astype(np.float32)
            Z[np.abs(S).sum(-1) == 0] = 0.0
            return Z, {"siamese_auc": auc}
        raise ValueError(arm)


def standardise(X, train):
    Xr = X[train].reshape(-1, X.shape[-1])
    mu, sd = np.nanmean(Xr, 0), np.nanstd(Xr, 0)
    sd[~np.isfinite(sd) | (sd == 0)] = 1.0
    return ((X - mu) / sd).astype(np.float32)


def shuffle_names(Z, seed=0):
    """Placebo: within each date, each name gets another name's text block."""
    rng = np.random.default_rng(seed)
    out = np.empty_like(Z)
    for d in range(len(Z)):
        out[d] = Z[d, rng.permutation(Z.shape[1])]
    return out


# ------------------------------------------------------------------------------------------------- one config
def run_config(p, T, cfg, folds, extra_info=None, confirm=False):
    """cfg: trial, arm (text arm or 'none'/'intensity'), model ('ridge'|'mlp'|'seq'|'seq_ang'|'xs:<mask>'),
    h, seeds, placebo (bool), names (subset or None), train_start."""
    h = cfg["h"]
    y_raw = p.target(h)
    names_mask = np.ones(p.N, bool)
    if cfg.get("exclude"):
        names_mask = ~np.isin(p.names, cfg["exclude"])
    rows = []
    hsh = chash(cfg)
    for fy in folds:
        assert fy <= STAGE1_LAST_YEAR or confirm      # 2022-25 only through confirm.py, after the prereg
        train, test = F.fold_index(p, fy, h, start=pd.Timestamp(cfg.get("train_start", "2016-01-04")))
        if cfg.get("train_exclude"):                       # e.g. drop the COVID sessions from training
            lo, hi = map(pd.Timestamp, cfg["train_exclude"])
            train = train[(p.S[train] < lo) | (p.S[train] > hi)]
        y = y_raw.copy()
        y[:, ~names_mask] = np.nan
        y[test[-1] + 1:] = np.nan            # fold_index already keeps every test target inside its year
        sd = np.nanstd(y[train])
        ys = y / sd
        blocks, info = [p.price], {}
        if cfg["arm"] != "none":
            blocks.append(p.intensity)
        if cfg["arm"] not in ("none", "intensity"):
            Z, inf = T.build(cfg["arm"], train, ys, h)
            info.update(inf)
            if cfg.get("placebo"):
                Z = shuffle_names(Z)
            blocks.append(Z)
        X = standardise(np.concatenate(blocks, -1), train)
        X[:, ~names_mask] = np.nan
        t0 = time.time()
        model = cfg["model"]
        if model == "ridge":
            pred, inf = M.ridge(X, ys, train, test, h)
        elif model == "ridge_ic":
            pred, inf = M.ridge_ic(X, ys, train, test, h)
        elif model == "gbrt_ic":
            pred, inf = M.gbrt_ic(X, ys, train, test, h, seeds=cfg.get("seeds", 5))
        elif model in ("mlp", "seq", "seq_ang"):
            pred, inf = M.net(X, ys, train, test, h, kind="seq" if model.startswith("seq") else "mlp",
                              seeds=cfg.get("seeds", 5), angular=model == "seq_ang")
        elif model.startswith("rff"):
            P_ = int(model.split(":")[1]) if ":" in model else 4000
            g = "median" if model.startswith("rff_med") else 2.0
            pred, inf = M.rff_ridge(X, ys, train, test, h, P=P_, gamma=g, seeds=cfg.get("seeds", 5))
        elif model == "gbrt":
            pred, inf = M.gbrt(X, ys, train, test, h, seeds=cfg.get("seeds", 5))
        elif model.startswith("xs"):
            _, mname, *ang = model.split(":")
            mask = cross_mask(p, mname, train, ys, T, cfg)
            pred, inf = M.net(X, ys, train, test, h, kind="xs", seeds=cfg.get("seeds", 5), mask=mask,
                              angular=bool(ang))
            inf["mask_density"] = float(mask.mean())
        else:
            raise ValueError(model)
        info.update(inf)
        np.save(os.path.join(PREDS, f"{hsh}_{fy}.npy"), pred.astype(np.float32))
        wk = F.thursdays(p, test)
        ic = F.weekly_ic(pred, y, wk)
        sp = F.tercile_spread(pred, y, wk)
        nd = F.ndcg_at(pred, y, wk)
        rows.append({
            "time": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "git": git_rev(), "hash": hsh,
            "trial": cfg["trial"], "arm": cfg["arm"], "model": model, "h": h, "placebo": bool(cfg.get("placebo")),
            "variant": cfg.get("variant", ""), "fold": fy, "n_weeks": int(np.isfinite(ic).sum()),
            "ic": float(np.nanmean(ic)), "ic_t": float(F.nw_t(ic, F.nw_lag(h))),
            "spread": float(np.nanmean(sp)), "ndcg5": float(np.nanmean(nd)),
            "secs": round(time.time() - t0, 1), "cfg": json.dumps(cfg, sort_keys=True),
            "info": json.dumps({**info, **(extra_info or {})}, default=float)})
        print(f"  {cfg['trial']} {cfg['arm']:<12} {model:<12} h={h:<2} {fy}: IC {rows[-1]['ic']:+.4f} "
              f"(t {rows[-1]['ic_t']:+.2f}) spread {rows[-1]['spread']*1e4:+.1f}bp  {rows[-1]['secs']}s",
              flush=True)
    df = pd.DataFrame(rows).reindex(columns=COLS)
    df.to_csv(LEDGER, mode="a", header=not os.path.exists(LEDGER), index=False)
    return hsh, df


def cross_mask(p, name, train, ys, T, cfg):
    N = p.N
    eye = np.eye(N, dtype=bool)
    if name == "own":
        return eye
    if name == "full":
        return np.ones((N, N), bool)
    if name == "sector":
        m = eye.copy()
        for grp in P.SECTORS.values():
            ix = [p.names.index(t) for t in grp if t in p.names]
            m[np.ix_(ix, ix)] = True
        return m
    if name in ("granger", "random"):
        G = granger_mask(p, train, ys, T, cfg)
        if name == "granger":
            return G
        rng = np.random.default_rng(1)
        k = int(G.sum() - N)
        off = np.where(~eye.ravel())[0]
        R = eye.copy().ravel()
        R[rng.choice(off, k, replace=False)] = True
        return R.reshape(N, N)
    raise ValueError(name)


_GRANGER = {}


def granger_mask(p, train, ys, T, cfg, max_lag=5, q=0.01):
    """mask[i, j] True when j's text score Granger-causes i's residual return on the training window
    (OLS F-test of 5 lags of s_j added to 5 lags of e_i; Benjamini-Hochberg at q over all ordered pairs).
    The text score s_j is an in-sample ridge of the own forward target on the arm's text block."""
    key = (cfg["arm"], cfg["h"], int(train[-1]))
    if key in _GRANGER:
        return _GRANGER[key]
    from scipy import stats
    from sklearn.linear_model import Ridge
    blocks = [p.intensity]
    if cfg["arm"] not in ("none", "intensity"):
        blocks.append(T.build(cfg["arm"], train, ys, cfg["h"])[0])
    Zs = standardise(np.concatenate(blocks, -1), train)
    Xr, yr = M._rows(Zs, ys, train)
    s = Ridge(alpha=100).fit(Xr, yr).predict(np.nan_to_num(Zs).reshape(-1, Zs.shape[-1])).reshape(p.D, p.N)
    e = np.nan_to_num(p.e)
    t = train[(train >= max_lag)]
    N = p.N
    pv = np.ones((N, N))
    for i in range(N):
        yi = e[t, i]
        own = np.stack([e[t - k, i] for k in range(1, max_lag + 1)], 1)
        X0 = np.column_stack([np.ones(len(t)), own])
        r0 = yi - X0 @ np.linalg.lstsq(X0, yi, rcond=None)[0]
        rss0 = r0 @ r0
        for j in range(N):
            if j == i:
                continue
            X1 = np.column_stack([X0] + [s[t - k, j] for k in range(1, max_lag + 1)])
            r1 = yi - X1 @ np.linalg.lstsq(X1, yi, rcond=None)[0]
            rss1 = r1 @ r1
            df2 = len(t) - X1.shape[1]
            Fst = ((rss0 - rss1) / max_lag) / (rss1 / df2)
            pv[i, j] = stats.f.sf(Fst, max_lag, df2)
    off = ~np.eye(N, dtype=bool)
    ps = np.sort(pv[off])
    m = len(ps)
    passed = ps <= q * np.arange(1, m + 1) / m
    thr = ps[np.where(passed)[0].max()] if passed.any() else -1
    G = np.eye(N, dtype=bool) | (off & (pv <= thr))
    _GRANGER[key] = G
    print(f"    granger: {int(G.sum() - N)} edges of {m} (q={q})", flush=True)
    return G


# ------------------------------------------------------------------------------------------------- pairing
def compare(a, b, folds=F.INNER_FOLDS, p=None):
    """Weekly IC(a) - IC(b) over the pooled inner folds, paired, with NW t; per-fold means too."""
    led = pd.read_csv(LEDGER)
    ca = json.loads(led[led.hash == a].cfg.iloc[0])
    cb = json.loads(led[led.hash == b].cfg.iloc[0])
    assert ca["h"] == cb["h"]
    p = p or F.Panel()
    y = p.target(ca["h"])
    diffs, per = [], {}
    for fy in folds:
        fa, fb = os.path.join(PREDS, f"{a}_{fy}.npy"), os.path.join(PREDS, f"{b}_{fy}.npy")
        if not (os.path.exists(fa) and os.path.exists(fb)):
            continue
        _, test = F.fold_index(p, fy, ca["h"])
        yy = y.copy()
        yy[test[-1] + 1:] = np.nan
        for c in (ca, cb):
            if c.get("exclude"):
                yy[:, np.isin(p.names, c["exclude"])] = np.nan
        wk = F.thursdays(p, test)
        d = F.weekly_ic(np.load(fa), yy, wk) - F.weekly_ic(np.load(fb), yy, wk)
        per[fy] = float(np.nanmean(d))
        diffs.append(d)
    d = np.concatenate(diffs)
    return {"diff": float(np.nanmean(d)), "t": float(F.nw_t(d, F.nw_lag(ca["h"]))), "per_fold": per,
            "n": int(np.isfinite(d).sum())}


def _key(cfg, **over):
    c = {k: v for k, v in {**cfg, **over}.items() if k != "trial"}
    return json.dumps(c, sort_keys=True)


def report(path=os.path.join(P.REPORT, "TRIALS.md")):
    """Pooled inner-fold summary of every config, with paired differences against its twins:
    price-only ('none'), intensity-only, and its own shuffled-text placebo."""
    led = pd.read_csv(LEDGER)
    led = led[led.trial != "A"].drop_duplicates(["hash", "fold"], keep="last")
    cfgs = {h: json.loads(c) for h, c in zip(led.hash, led.cfg)}
    by_key = {_key(c): h for h, c in cfgs.items()}
    p = F.Panel()
    ycache = {}
    rows = []
    for h, cfg in cfgs.items():
        if cfg["h"] not in ycache:
            ycache[cfg["h"]] = p.target(cfg["h"])
        sub = led[led.hash == h].sort_values("fold")
        ics = []
        for fy in sub.fold:
            _, test = F.fold_index(p, fy, cfg["h"])
            y = ycache[cfg["h"]].copy()
            y[test[-1] + 1:] = np.nan
            if cfg.get("exclude"):
                y[:, np.isin(p.names, cfg["exclude"])] = np.nan
            ics.append(F.weekly_ic(np.load(os.path.join(PREDS, f"{h}_{fy}.npy")), y, F.thursdays(p, test)))
        ic = np.concatenate(ics)
        row = {"hash": h, "trial": cfg["trial"], "arm": cfg["arm"] + (" (placebo)" if cfg.get("placebo") else ""),
               "model": cfg["model"], "h": cfg["h"], "variant": cfg.get("variant", ""),
               "folds": " ".join(f"{v:+.3f}" for v in sub.ic), "ic": np.nanmean(ic),
               "ic_t": F.nw_t(ic, F.nw_lag(cfg["h"]))}
        twins = {"vs_price": _key(cfg, arm="none", placebo=False), "vs_intensity": _key(cfg, arm="intensity",
                 placebo=False), "vs_placebo": _key(cfg, placebo=True)}
        for name, k in twins.items():
            if k in by_key and by_key[k] != h and cfg["arm"] not in ("none",) and not cfg.get("placebo"):
                if name == "vs_intensity" and cfg["arm"] == "intensity":
                    continue
                c = compare(h, by_key[k], folds=list(sub.fold), p=p)
                row[name] = f"{c['diff']:+.4f} (t {c['t']:+.2f}; " + " ".join(
                    f"{v:+.3f}" for v in c["per_fold"].values()) + ")"
                row[name + "_allpos"] = all(v > 0 for v in c["per_fold"].values())
        rows.append(row)
    df = pd.DataFrame(rows).sort_values(["trial", "h", "model", "arm"])
    df.to_csv(os.path.join(P.REPORT, "summary.csv"), index=False)
    n_cfg, n_runs = led.hash.nunique(), len(led)
    with open(path, "w") as f:
        f.write("# Quant trials · Stage 1 ledger summary (inner folds 2019-2021)\n\n")
        f.write(f"Generated by `trials.py report` from `trials.csv`: {n_cfg} configurations, {n_runs} fold runs. "
                "IC = mean weekly (Thursday) cross-sectional Spearman IC over the 31 names, pooled over the folds; "
                "t = Newey-West. `vs_*` = paired weekly IC difference against the twin "
                "(pooled diff, t, then per-fold diffs).\n\n")
        cols = ["trial", "arm", "model", "h", "variant", "folds", "ic", "ic_t", "vs_price", "vs_intensity",
                "vs_placebo"]
        d2 = df.reindex(columns=cols).copy()
        d2["ic"] = d2["ic"].map(lambda v: f"{v:+.4f}")
        d2["ic_t"] = d2["ic_t"].map(lambda v: f"{v:+.2f}")
        f.write(d2.fillna("").to_markdown(index=False))
        f.write("\n")
    return df


def grid(trial, arms, models, hs, placebo=(False,), seeds=5, **kw):
    for h in hs:
        for arm in arms:
            for model in models:
                for pl in placebo:
                    if pl and arm in ("none", "intensity"):
                        continue
                    cfg = {"trial": trial, "arm": arm, "model": model, "h": h, "placebo": pl, **kw}
                    if not model.startswith("ridge"):
                        cfg["seeds"] = seeds
                    yield cfg


def run_many(cfgs, folds=F.INNER_FOLDS, skip_done=True):
    p = F.Panel()
    T = Text(p)
    done = set(pd.read_csv(LEDGER).hash) if (skip_done and os.path.exists(LEDGER)) else set()
    out = []
    for cfg in cfgs:
        h = chash(cfg)
        if h in done:
            print("  skip", h, cfg["arm"], cfg["model"], cfg["h"])
            continue
        out.append(run_config(p, T, cfg, folds)[0])
    return out


# ------------------------------------------------------------------------------------------------- Trial A
def artefact(seeds=3, h=3, folds=F.INNER_FOLDS):
    """Trial A: the paper's own setup on our names. Target = close h sessions ahead, inputs = open/close/volume
    min-max scaled per name on the training partition (+ a text block), pooled transformer, MSE. Reports the
    paper's metrics next to persistence (y_hat = today's close) and the paper's long/cash rule."""
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    p = F.Panel()
    T = Text(p)
    raw = np.stack([p.open, p.close, p.volume], -1).astype(np.float64)
    lvl = p.level_target(h)
    out = []
    for fy in folds:
        train, test = F.fold_index(p, fy, h)
        lo = np.nanmin(raw[train], 0)
        hi = np.nanmax(raw[train], 0)
        Xp = ((raw - lo) / (hi - lo)).astype(np.float32)          # per name, fit on train only (paper's fix)
        y = ((lvl - lo[:, 1]) / (hi[:, 1] - lo[:, 1])).astype(np.float32)
        y[test[-1] + 1:] = np.nan
        Z, _ = T.build("pca_hl5", train, p.target(5) / np.nanstd(p.target(5)[train]), 5)
        Zs = standardise(Z, train)
        runs = {"persistence": Xp[..., 1].copy()}
        runs["paper_price"], _ = M.net(Xp, y, train, test, h, kind="seq", seeds=seeds)
        runs["paper_text"], _ = M.net(np.concatenate([Xp, Zs], -1), y, train, test, h, kind="seq", seeds=seeds)
        r3 = np.full(p.close.shape, np.nan)
        r3[:-h] = p.close[h:] / p.close[:-h] - 1
        rd = np.full(p.close.shape, np.nan)
        rd[:-1] = np.log(p.close[1:] / p.close[:-1])
        for name, pr in runs.items():
            m = np.zeros(y.shape, bool)
            m[test] = True
            m &= np.isfinite(y) & np.isfinite(pr)
            up = (pr > Xp[..., 1])
            act = (y > Xp[..., 1])
            long = np.where(up, r3, 0.0)
            out.append({"fold": fy, "model": name, "mse": mean_squared_error(y[m], pr[m]),
                        "mae": mean_absolute_error(y[m], pr[m]), "r2": r2_score(y[m], pr[m]),
                        "dir_acc": float((up[m] == act[m]).mean()) if name != "persistence" else np.nan,
                        "long_cash_3d_bp": float(np.nanmean(long[m]) * 1e4),
                        "buy_hold_3d_bp": float(np.nanmean(r3[m]) * 1e4),
                        "zero_fcst_mae_1d": float(np.nanmean(np.abs(rd[test])))})
            print(out[-1], flush=True)
    df = pd.DataFrame(out)
    df.to_csv(os.path.join(P.REPORT, "trial_A_artefact.csv"), index=False)
    pd.DataFrame([{"time": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "git": git_rev(), "hash": "trialA",
                   "trial": "A", "arm": "paper_level", "model": "seq", "h": h, "fold": int(r.fold),
                   "ic": np.nan, "cfg": json.dumps({"trial": "A", "h": h, "model": r.model}),
                   "info": json.dumps(r.to_dict(), default=float)} for _, r in df.iterrows()]).reindex(columns=COLS).to_csv(
        LEDGER, mode="a", header=False, index=False)
    return df


# ------------------------------------------------------------------------------------------------- COVID critique
CRASH = (pd.Timestamp("2020-02-15"), pd.Timestamp("2020-05-31"))


def covid_table(arms=("proto_hl5", "pca_hl5"), models=("ridge", "gbrt"), hs=(10, 20, 40, 60)):
    """Re-scores existing predictions (no refits): per fold, the text-minus-twin weekly IC difference
    (a) as run, (b) sector-neutral (prediction and target demeaned within sector clusters),
    (c) for 2020 without the Feb 15 - May 31 crash window. Twins: price-only and the arm's own placebo."""
    led = pd.read_csv(LEDGER)
    led = led[(led.trial != "A")].drop_duplicates(["hash", "fold"], keep="last")
    cfgs = {h: json.loads(c) for h, c in zip(led.hash, led.cfg)}
    by_key = {_key(c): h for h, c in cfgs.items()}
    p = F.Panel()
    grp = F.sector_ids(p.names)
    rows = []
    for h in hs:
        y = p.target(h)
        yn = F.neutralise(y, grp)
        for model in models:
            for arm in arms:
                base = {"arm": arm, "model": model, "h": h, "placebo": False}
                if model != "ridge":
                    base["seeds"] = 5
                k = _key(base)
                if k not in by_key:
                    continue
                for twin_name, twin in (("price", {**base, "arm": "none"}), ("placebo", {**base, "placebo": True})):
                    kt = _key(twin)
                    if kt not in by_key:
                        continue
                    a, b = by_key[k], by_key[kt]
                    for fy in sorted(led[led.hash == a].fold):
                        fa, fb = os.path.join(PREDS, f"{a}_{fy}.npy"), os.path.join(PREDS, f"{b}_{fy}.npy")
                        if not (os.path.exists(fa) and os.path.exists(fb)):
                            continue
                        _, test = F.fold_index(p, fy, h)
                        pa, pb = np.load(fa), np.load(fb)
                        yy, yyn = y.copy(), yn.copy()
                        yy[test[-1] + 1:] = np.nan
                        yyn[test[-1] + 1:] = np.nan
                        wk = F.thursdays(p, test)
                        d_raw = F.weekly_ic(pa, yy, wk) - F.weekly_ic(pb, yy, wk)
                        d_neu = F.weekly_ic(F.neutralise(pa, grp), yyn, wk) - F.weekly_ic(F.neutralise(pb, grp), yyn, wk)
                        keep = ~((p.S[wk] >= CRASH[0]) & (p.S[wk] <= CRASH[1]))
                        rows.append({"h": h, "model": model, "arm": arm, "twin": twin_name, "fold": fy,
                                     "diff": np.nanmean(d_raw), "diff_sector_neutral": np.nanmean(d_neu),
                                     "diff_ex_crash": np.nanmean(d_raw[keep])})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(P.REPORT, "covid_rescore.csv"), index=False)
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--trial", default="X")
    ap.add_argument("--arms", nargs="+", default=["none"])
    ap.add_argument("--models", nargs="+", default=["ridge"])
    ap.add_argument("--h", nargs="+", type=int, default=[5])
    ap.add_argument("--placebo", action="store_true", help="also run the shuffled-text placebo of each arm")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--exclude", nargs="*")
    ap.add_argument("--train-start")
    ap.add_argument("--variant", default="")
    ap.add_argument("--train-exclude", nargs=2)
    ap.add_argument("--folds", nargs="+", type=int, default=list(F.INNER_FOLDS))
    a = ap.parse_args()
    if a.cmd == "compare":
        print(compare(*a.args))
    elif a.cmd == "artefact":
        print(artefact().groupby("model").mean(numeric_only=True).to_string())
    elif a.cmd == "covid":
        df = covid_table()
        with pd.option_context("display.width", 250):
            print(df.pivot_table(index=["model", "arm", "h", "twin"], columns="fold",
                                 values=["diff", "diff_sector_neutral", "diff_ex_crash"]).round(3).to_string())
    elif a.cmd == "report":
        with pd.option_context("display.width", 250, "display.max_columns", 20, "display.max_colwidth", 60):
            print(report().drop(columns=["hash"]).to_string(index=False))
    elif a.cmd == "run":
        kw = {}
        if a.exclude:
            kw["exclude"] = a.exclude
        if a.train_start:
            kw["train_start"] = a.train_start
        if a.variant:
            kw["variant"] = a.variant
        if a.train_exclude:
            kw["train_exclude"] = a.train_exclude
        run_many(grid(a.trial, a.arms, a.models, a.h, (False, True) if a.placebo else (False,), a.seeds, **kw),
                 folds=a.folds)
