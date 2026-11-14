"""N4_news configurations (planned in STATE.json before scoring). Usage: python run.py c0 c1 ...  (appends RESULTS.jsonl,
saves .cache/tree/preds/N4_news/<name>.npy, updates STATE.json)."""
import os
import sys

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib  # noqa: E402
from lib import harness, xrank  # noqa: E402
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("d_model", os.path.join(os.path.dirname(HERE), "D_ensembles", "model.py"))
Dm = importlib.util.module_from_spec(_spec)   # D_ensembles/model.py (the D trees)
_spec.loader.exec_module(Dm)

NEWS_START = np.datetime64("2015-04-01")
ITERS = (50, 100, 200, 400)
NAMES_X = None


def nx():
    return lib.news()["X"]


def col(k):
    return list(lib.news()["names_X"]).index(k)


def mrank(D):
    m = D["master_h5_ref"].astype(np.float64)
    return xrank(m, D["elig"])


def blend(D, s, w=0.3):
    """Fixed 0.7 rank(MASTER) + 0.3 rank(s) over MASTER's names; s missing -> neutral 0.5."""
    m = D["master_h5_ref"].astype(np.float64)
    ok = np.isfinite(m) & D["elig"]
    rm = xrank(np.where(ok, m, np.nan))
    rs = xrank(np.where(ok, s, np.nan))
    rs = np.where(ok & ~np.isfinite(rs), 0.0, rs)
    p = (1 - w) * rm + w * rs
    p[~ok] = np.nan
    return p


def resid_ret5(D):
    e = np.nan_to_num(D["e"].astype(np.float64))
    c = np.vstack([np.zeros((1, e.shape[1])), np.cumsum(e, 0)])
    out = np.full(e.shape, np.nan)
    out[4:] = c[5:] - c[:-5]
    out[~D["elig"]] = np.nan
    return out


def news_design(D):
    """[MASTER centred rank, 13 news columns], (T, N, 14)."""
    return np.concatenate([np.nan_to_num(mrank(D))[..., None], nx()], 2)


def train_thu(D, te):
    S = D["S"]
    return np.where((S.weekday == 3) & (np.arange(len(S)) <= te) & (S.to_numpy() >= NEWS_START))[0]


def fm_fit_predict(D, te, rows, seed):
    X = news_design(D)
    ym = D["master_h5_ref"]
    bs = []
    for t in train_thu(D, te):
        m = D["elig"][t] & np.isfinite(ym[t]) & np.isfinite(D["y5"][t])
        if m.sum() < 50:
            continue
        y = xrank(np.where(m, D["y5"][t], np.nan)[None])[0][m]
        A = np.column_stack([np.ones(m.sum()), X[t][m]])
        bs.append(np.linalg.lstsq(A, y, rcond=None)[0])
    b = np.mean(bs, 0)
    p = b[0] + X[rows] @ b[1:]
    p[~(D["elig"][rows] & np.isfinite(ym[rows]))] = np.nan
    return p


def hgb_pick(Xt, t, rid, seed, val_weeks):
    kw = dict(learning_rate=0.03, max_leaf_nodes=8, min_samples_leaf=400, l2_regularization=1.0, max_features=0.5,
              early_stopping=False, random_state=seed)
    ur = np.unique(rid)
    cut = ur[-val_weeks]
    a, b = rid < cut - 8, rid >= cut
    m = HistGradientBoostingRegressor(max_iter=ITERS[-1], **kw).fit(Xt[a], t[a])
    best = (-9.0, ITERS[0])
    for i, p in enumerate(m.staged_predict(Xt[b]), 1):
        if i in ITERS:
            ic = Dm._ic(p, t[b], rid[b])
            if ic > best[0] + 1e-4:
                best = (ic, i)
    return HistGradientBoostingRegressor(max_iter=best[1], **kw).fit(Xt, t), best[1]


def c3_fit_predict(D, te, rows, seed):
    X = news_design(D)
    ym = D["master_h5_ref"]
    tr = train_thu(D, te)
    yy = D["y5"][tr].astype(np.float64).copy()
    m = D["elig"][tr] & np.isfinite(ym[tr]) & np.isfinite(yy)
    yy[~m] = np.nan
    t = xrank(yy)[m]
    rid = np.repeat(tr[:, None], yy.shape[1], 1)[m]
    g, n = hgb_pick(X[tr][m], t, rid, seed, 26)
    print("   c3 te", te, "seed", seed, "trees", n, "train weeks", len(tr), flush=True)
    Xp = X[rows]
    p = g.predict(Xp.reshape(-1, Xp.shape[2])).reshape(Xp.shape[:2])
    p[~(D["elig"][rows] & np.isfinite(ym[rows]))] = np.nan
    return p


def d_fit_predict(news=False):
    def f(D, te, rows, seed):
        X = Dm._features(D)
        if news:
            X = np.concatenate([X, nx()], 2)          # news 0 (neutral) / indicators 0 before the archive
        Xp = X[rows]
        ok = D["elig"][rows] & np.isfinite(D["Z"][rows]).all(2)
        p = np.asarray(Dm._fit("hgb", 5, D, X, te, seed)(Xp.reshape(-1, Xp.shape[2])), dtype=np.float64).reshape(Xp.shape[:2])
        p[~ok] = np.nan
        return xrank(p)
    return f


def wf(fn, D, seeds):
    return harness.walk_forward(fn, seeds=seeds, D=D, years=lib.YEARS)


def run(name, D):
    if name == "c0":
        pred, note = D["master_h5_ref"].astype(np.float64), "MASTER 5-day reference, 2016-2019"
        return lib.evaluate(pred, name, note, D)
    if name == "c1":
        pred = blend(D, lib.news()["raw_tone21"].astype(np.float64))
        return lib.evaluate(pred, name, "0.7 rank MASTER + 0.3 rank tone21 (hand list), missing tone neutral; no fit", D)
    if name == "c2":
        pred = wf(fm_fit_predict, D, (0,))
        return lib.evaluate(pred, name, "Fama-MacBeth rank(y5) on MASTER rank + 13 news cols, train Thursdays 2015-04..te", D)
    if name == "c3":
        pred = wf(c3_fit_predict, D, (0, 1, 2))
        return lib.evaluate(pred, name, "HGB (D settings, 26-week tree pick) on MASTER rank + 13 news cols, train 2015-04..te", D)
    if name == "ref_D":
        pred = wf(d_fit_predict(False), D, (0, 1, 2))
        return lib.evaluate(pred, name, "D trees (D_ensembles/model.py), 2016-2019; control for c4", D)
    if name == "c4":
        ctrl = np.load(os.path.join(lib.PREDS, "ref_D.npy")).astype(np.float64)
        pred = wf(d_fit_predict(True), D, (0, 1, 2))
        return lib.evaluate(pred, name, "D trees + 13 news cols (27+13 inputs), seeds 0-2", D, control=ctrl, control_name="ref_D")
    if name == "c5":
        X = lib.news()
        s = xrank(resid_ret5(D), D["elig"]) * np.nan_to_num(xrank(X["raw_abn5"].astype(np.float64), D["elig"]))
        return lib.evaluate(blend(D, s), name, "0.7 MASTER + 0.3 rank(rank e5 x rank abn5) (news-driven drift / no-news reversal)", D)
    if name == "c6":
        X = lib.news()
        tn = np.nan_to_num(xrank(X["raw_tone5"].astype(np.float64), D["elig"]))
        nv = xrank(X["raw_nov5"].astype(np.float64), D["elig"]) + 0.5
        s = tn * np.where(np.isfinite(nv), nv, 0.5)
        return lib.evaluate(blend(D, s), name, "0.7 MASTER + 0.3 rank(tone5 rank x novelty5 rank in [0,1])", D)
    raise SystemExit(f"unknown {name}")


if __name__ == "__main__":
    D = harness.load()
    for nm in sys.argv[1:]:
        r = run(nm, D)
        extra = "" if "vs_control" not in r else "; vs ref_D %+.4f (t %.2f, %d/4)" % (
            r["vs_control"]["increment"], r["vs_control"]["increment_t"], r["vs_control"]["years_increment_positive"])
        lib.state(scored=nm, note="scored %s: IC %.4f, increment %+.4f (t %.2f), %d/4 years, covered %+.4f (t %.2f)%s" % (
            nm, r["ic"], r["increment"], r["increment_t"], r["years_increment_positive"], r["covered_subset"]["increment"],
            r["covered_subset"]["increment_t"], extra))
