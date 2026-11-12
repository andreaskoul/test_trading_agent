"""Configuration sets 3-4: fitted combinations on training Thursdays only.

fm_ridge: Fama-MacBeth. Weekly cross-sectional OLS (small ridge) of the ranked target on the ranked characteristics
(missing = 0) over training Thursdays 2009..train_end; coefficients averaged -> fundamentals score. MASTER weight: a
second Fama-MacBeth of the target on [rank MASTER, rank fundamentals score] over training Thursdays where MASTER exists
(2013..train_end; its frozen scores are out of sample); for 2013 (no MASTER training rows) the registered 0.7 is used.
hgb_blend: HistGradientBoosting (early_stopping=False) on ranked fundamentals (NaN kept) + ranked D["Z"], ranked target,
training Thursdays 2009..train_end; prediction ranked and blended 0.7 MASTER / 0.3 trees (fixed in advance).
"""
import sys
import numpy as np
import lib
from lib import harness
from run_blend import run, PLAN

FEATS = list(lib.CHARS) + ["logassets"]
D = lib.data()
R = lib.ranks()
Zr = [lib.xrank(D["Z"][:, :, k].astype(np.float64), D["elig"]) for k in range(D["Z"].shape[2])]


def X_at(rows, feats=FEATS, fill=True, z=False):
    cols = [R[f][rows] for f in feats] + ([z_[rows] for z_ in Zr] if z else [])
    X = np.stack(cols, -1)
    return np.nan_to_num(X, nan=0.0) if fill else X


def fm(X, Y, lam=1e-3):
    bs = []
    for t in range(X.shape[0]):
        m = np.isfinite(Y[t])
        if m.sum() < 50:
            continue
        x, y = X[t][m], Y[t][m]
        bs.append(np.linalg.solve(x.T @ x + lam * len(y) * np.eye(x.shape[1]), x.T @ y))
    return np.array(bs)


def master_weight(Dm, te, fscore_fn):
    tr = lib.train_thursdays(te, start=2013)
    if len(tr) == 0:
        return 0.7
    Y = lib.target_rank(Dm, tr)
    F = lib.xrank(fscore_fn(tr), Dm["elig"][tr])
    M = R["master"][tr]
    X = np.stack([M, np.nan_to_num(F, nan=0.0)], -1)
    Y = np.where(np.isfinite(M), Y, np.nan)
    b = fm(np.nan_to_num(X, nan=0.0), Y).mean(0)
    b = np.clip(b, 0, None)
    return float(b[0] / b.sum()) if b.sum() > 0 else 0.7


def fit_fm(feats=FEATS, lam=1e-3):
    def fit_predict(Dm, te, rows, seed):
        tr = lib.train_thursdays(te)
        b = fm(X_at(tr, feats), lib.target_rank(Dm, tr), lam).mean(0)
        fs = lambda rr: X_at(rr, feats) @ b
        w = master_weight(Dm, te, fs)
        print(f"  te={te} w_master={w:.2f} b=" + " ".join(f"{f}:{v:+.3f}" for f, v in zip(feats, b)), flush=True)
        s = np.full(Dm["y5"].shape, np.nan); s[rows] = fs(rows)
        return lib.blend(s, w)[rows]
    return fit_predict


def fit_hgb(w=0.7, z=True, iters=200, feats=FEATS):
    from sklearn.ensemble import HistGradientBoostingRegressor
    def fit_predict(Dm, te, rows, seed):
        tr = lib.train_thursdays(te)
        X, Y = X_at(tr, feats, fill=False, z=z), lib.target_rank(Dm, tr)
        m = np.isfinite(Y) & Dm["elig"][tr]
        mdl = HistGradientBoostingRegressor(max_iter=iters, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=500,
                                            l2_regularization=1.0, early_stopping=False, random_state=seed)
        mdl.fit(X[m], Y[m])
        Xp = X_at(rows, feats, fill=False, z=z)
        p = mdl.predict(Xp.reshape(-1, Xp.shape[-1])).reshape(len(rows), -1)
        p = np.where(Dm["elig"][rows], p, np.nan)
        s = np.full(Dm["y5"].shape, np.nan); s[rows] = p
        return lib.blend(s, w)[rows]
    return fit_predict


if __name__ == "__main__":
    which = sys.argv[1:]
    if "fm_ridge" in which:
        run("fm_ridge", fit_fm(), "Fama-MacBeth on 13 ranked characteristics (missing 0), MASTER weight by FM on 2013..train_end (0.7 in 2013)")
    if "hgb_blend" in which:
        run("hgb_blend", fit_hgb(), "HGB (200 it, lr .05, 15 leaves, min leaf 500) on ranked fundamentals (NaN kept) + ranked Z, rank target; 0.7 MASTER / 0.3 trees fixed")

    P2 = ['comp_blend70','comp_blend50','fm_ridge','hgb_blend','dml_composite','hgb_zonly_blend70','hgb_fundonly_blend70','fm_fixed70','comp_lit7_blend70']
    if "hgb_zonly_blend70" in which:
        run("hgb_zonly_blend70", fit_hgb(feats=[]), "CONTROL for hgb_blend: same HGB on ranked Z only (no fundamentals), 0.7 MASTER / 0.3 trees", P2)
    if "hgb_fundonly_blend70" in which:
        run("hgb_fundonly_blend70", fit_hgb(z=False), "same HGB on ranked fundamentals only (no Z), 0.7 MASTER / 0.3 trees", P2)
