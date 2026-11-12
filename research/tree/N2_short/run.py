"""Branch N2 configurations. Usage: python3 run.py c1 c2 ...  (each logs one line to RESULTS.jsonl)

Decided in advance: fixed rank weights 0.5/0.5 and 0.7/0.3 (MASTER/F2); for validation year 2013 the fitted
combinations fall back to 0.7/0.3, since no training row carries a MASTER score before 2013.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib  # noqa: E402
from lib import harness  # noqa: E402

LOG = os.path.join(HERE, "RESULTS.jsonl")
SCREEN_LOG = os.path.join(HERE, "SCREEN.jsonl")
FIRST_MASTER = 2013


def is_first_year(D, te):
    return len(lib.train_rows(D, te, need_master=True)) < 20


def fp_f2(D, te, rows, seed):
    return lib.ranked(D)["f2"][rows]


def fp_fixed(w):
    def f(D, te, rows, seed):
        return lib.combine(D, rows, w, ["f2"], [1 - w])
    return f


def fp_fm(feats):
    def f(D, te, rows, seed):
        if is_first_year(D, te):
            return lib.combine(D, rows, 0.7, feats, [0.3 / len(feats)] * len(feats))
        b, t = lib.fama_macbeth(D, lib.train_rows(D, te), feats)
        return lib.combine(D, rows, b[0], feats, list(b[1:]))
    return f


def screen(D, te):
    """Training-row screen: keep a short feature if its weekly IC on rows <= te is positive with t >= 2."""
    tr = lib.train_rows(D, te, need_master=False)
    tab = {f: lib.feature_ic(D, tr, f) for f in lib.FEATS}
    keep = [f for f, (ic, t, n) in tab.items() if t >= 2.0]
    with open(SCREEN_LOG, "a") as fh:
        fh.write(json.dumps({"train_end": str(D["S"][te].date()), "ic_t_n": tab, "keep": keep}) + "\n")
    return keep or ["f2"]


def fp_screen(D, te, rows, seed):
    feats = screen(D, te) if seed == 0 else _SCREEN[te]
    _SCREEN[te] = feats
    return fp_fm(feats)(D, te, rows, seed)


_SCREEN = {}


def fp_hgb(D, te, rows, seed):
    from sklearn.ensemble import HistGradientBoostingRegressor
    feats = lib.FEATS
    if is_first_year(D, te):
        return lib.combine(D, rows, 0.7, ["f2"], [0.3])
    tr = lib.train_rows(D, te)
    Zr = np.stack([lib.xrank(D["Z"][:, :, k].astype(np.float64), D["elig"]) for k in range(D["Z"].shape[2])], -1)
    X = np.concatenate([lib.design(D, tr, feats, fill=False), Zr[tr]], -1)
    Y = lib.target_rank(D, tr)
    m = np.isfinite(X[..., 0]) & np.isfinite(Y)
    g = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=500,
                                      l2_regularization=1.0, early_stopping=False, random_state=seed)
    g.fit(X[m], Y[m])
    Xp = np.concatenate([lib.design(D, rows, feats, fill=False), Zr[rows]], -1)
    p = g.predict(Xp.reshape(-1, Xp.shape[-1])).reshape(Xp.shape[:2])
    return np.where(np.isfinite(Xp[..., 0]), p, np.nan)


CONFIGS = {
    "c1": ("F2 alone", fp_f2, "rank of minus the 20-session short-volume ratio; all names with data"),
    "c2": ("MASTER+F2 0.5/0.5", fp_fixed(0.5), "fixed rank average, decided in advance; MASTER's names only"),
    "c3": ("MASTER+F2 0.7/0.3", fp_fixed(0.7), "fixed rank average, decided in advance; MASTER's names only"),
    "c4": ("FM [MASTER, F2]", fp_fm(["f2"]), "Fama-MacBeth of rank target on training Thursdays with MASTER (2013+); 2013 fixed 0.7/0.3"),
    "c5": ("FM [MASTER, 7 short feats]", fp_fm(lib.FEATS), "FM on MASTER + f2,f5,f60,dratio,abn,abnshort,abntotal; 2013 fixed 0.7 + 0.3 split"),
    "c6": ("FM [MASTER, screened]", fp_screen, "features kept if training-row IC t>=2 (rows from 2012); FM weights; 2013 fixed"),
    "c7": ("HGB [MASTER, 7 feats, Z]", fp_hgb, "boosted trees on rank target, MASTER + short feats + 5 chars ranked; 2013 fixed 0.7/0.3"),
}


def main(keys):
    D = harness.load()
    for k in keys:
        name, fp, note = CONFIGS[k]
        pred = harness.walk_forward(fp, seeds=(0, 1, 2), D=D)
        res = harness.increment(pred, f"{k} {name}", LOG, note=note, D=D)
        if k == "c1":
            s = harness.score(pred, f"{k} {name} (score)", LOG, note=note, D=D)
            print(json.dumps({x: s[x] for x in ("ic", "ic_t", "ic_by_year", "decile_net_pct_per_year", "decile_net_sharpe")}))
        print(json.dumps({x: (round(v, 4) if isinstance(v, float) else v) for x, v in res.items() if x not in ("note", "at")}))


if __name__ == "__main__":
    main(sys.argv[1:] or list(CONFIGS))
