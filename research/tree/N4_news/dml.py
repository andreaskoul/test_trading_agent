"""Double ML (partially linear, as N2_short/dml.py) for N4 news scores on 2016-2019 Thursdays.

Y = centred rank of y5; T = centred rank of the news score; W = MASTER rank + D_ensembles' 27 inputs. Nuisances
E[Y|W], E[T|W] by HistGradientBoosting, cross-fitted by calendar year (4 folds). theta = sum(rT rY)/sum(rT^2); SE from
influence terms summed by week, Newey-West 4 lags. MASTER's names only.

    python dml.py tone21 c5 c6 pred:c3 ...   (appends to RESULTS.jsonl, updates STATE.json)
"""
import json
import os
import sys
import time

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib  # noqa: E402
import run as R  # noqa: E402
from lib import harness, xrank  # noqa: E402


def score_of(D, key):
    X = lib.news()
    if key == "tone21":
        return X["raw_tone21"].astype(np.float64)
    if key == "c5":
        return xrank(R.resid_ret5(D), D["elig"]) * np.nan_to_num(xrank(X["raw_abn5"].astype(np.float64), D["elig"]))
    if key == "c6":
        tn = np.nan_to_num(xrank(X["raw_tone5"].astype(np.float64), D["elig"]))
        nv = xrank(X["raw_nov5"].astype(np.float64), D["elig"]) + 0.5
        return tn * np.where(np.isfinite(nv), nv, 0.5)
    if key.startswith("pred:"):
        return np.load(os.path.join(lib.PREDS, key[5:] + ".npy")).astype(np.float64)
    if key.startswith("raw_"):
        return X[key].astype(np.float64)
    raise SystemExit(key)


def nw_se(psi_week, J, lags=4):
    n = len(psi_week)
    u = psi_week - psi_week.mean()
    v = u @ u / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (u[l:] @ u[:-l]) / n
    return np.sqrt(v * n) / J


def run(D, key):
    rows = np.concatenate([harness.thursdays(D, y) for y in lib.YEARS])
    mN = D["elig"] & np.isfinite(D["master_h5_ref"])
    Xd = R.Dm._features(D)[rows].astype(np.float64)
    W = np.concatenate([np.nan_to_num(R.mrank(D)[rows])[..., None], Xd], -1)
    sc = score_of(D, key)
    T = xrank(np.where(mN, sc, np.nan))[rows]
    T = np.where(mN[rows] & ~np.isfinite(T), 0.0, T)          # missing news score -> neutral (explicit in the score)
    Y = xrank(np.where(mN, D["y5"].astype(np.float64), np.nan))[rows]
    wk = np.broadcast_to(np.arange(len(rows))[:, None], T.shape)
    yr = np.broadcast_to(D["S"][rows].year.to_numpy()[:, None], T.shape)
    m = mN[rows] & np.isfinite(T) & np.isfinite(Y)
    W, T, Y, wk, yr = W[m], T[m], Y[m], wk[m], yr[m]
    rY, rT = np.empty_like(Y), np.empty_like(T)
    for y in lib.YEARS:
        te, tr = yr == y, yr != y
        for tgt, out in ((Y, rY), (T, rT)):
            g = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=500,
                                              l2_regularization=1.0, early_stopping=False, random_state=0)
            g.fit(W[tr], tgt[tr])
            out[te] = tgt[te] - g.predict(W[te])
    J = rT @ rT
    theta = (rT @ rY) / J
    psi = rT * (rY - theta * rT)
    se = nw_se(np.bincount(wk, weights=psi, minlength=len(rows)), J)
    Tc, Yc = T - T.mean(), Y - Y.mean()
    by = {}
    for y in lib.YEARS:
        k = yr == y
        by[int(y)] = float((rT[k] @ rY[k]) / (rT[k] @ rT[k]))
    return {"name": f"DML {key} | MASTER + D 27 inputs", "theta": float(theta), "theta_t": float(theta / se),
            "theta_se": float(se), "theta_by_year": by, "raw_slope": float((Tc @ Yc) / (Tc @ Tc)),
            "share_of_score_variance_explained_by_controls": float(1 - J / (Tc @ Tc)), "n_obs": int(len(Y)),
            "years": list(lib.YEARS), "note": "partially linear DML, HGB nuisances cross-fitted by year (4 folds), NW(4) weekly sums; MASTER names",
            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}


if __name__ == "__main__":
    D = harness.load()
    for k in sys.argv[1:]:
        r = run(D, k)
        with open(lib.LOG, "a") as f:
            f.write(json.dumps(r) + "\n")
        print(json.dumps({a: (round(b, 4) if isinstance(b, float) else b) for a, b in r.items()}), flush=True)
        lib.state(note="DML %s: theta %+.4f (t %.2f), by year %s, raw slope %+.4f" % (
            k, r["theta"], r["theta_t"], {a: round(b, 4) for a, b in r["theta_by_year"].items()}, r["raw_slope"]))
