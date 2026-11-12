"""Double machine learning (Chernozhukov et al. 2018), partially linear model, on the development Thursdays 2013-2019.

Y = rank of the 5-session target; T = a short-volume feature rank; controls W = MASTER rank + the five characteristics
D["Z"] (ranked). Nuisances E[Y|W] and E[T|W] by HistGradientBoosting (early_stopping=False), cross-fitted by calendar
year (7 folds: each year's residuals come from models fitted on the other six years). theta = sum(rT*rY)/sum(rT^2).
Standard error: influence terms summed by week, Newey-West 4 lags across weeks (cross-sectional dependence inside a
week is absorbed by the week sum). Usage: python3 dml.py  (appends to RESULTS.jsonl)
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib  # noqa: E402
from lib import harness  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402


def nw_se(psi_week, J, lags=4):
    n = len(psi_week)
    u = psi_week - psi_week.mean()
    v = u @ u / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (u[l:] @ u[:-l]) / n
    return np.sqrt(v * n) / J      # se of theta = sqrt(sum over weeks var) / J


def run(D, feat):
    R = lib.ranked(D)
    rows = np.concatenate([harness.thursdays(D, y) for y in harness.VAL_YEARS])
    Zr = np.stack([lib.xrank(D["Z"][:, :, k].astype(np.float64), D["elig"]) for k in range(D["Z"].shape[2])], -1)
    W = np.concatenate([R["master"][rows][..., None], Zr[rows]], -1)
    T = R[feat][rows]
    Y = lib.target_rank(D, rows)
    wk = np.broadcast_to(np.arange(len(rows))[:, None], T.shape)
    yr = np.broadcast_to(D["S"][rows].year.to_numpy()[:, None], T.shape)
    m = np.isfinite(W).all(-1) & np.isfinite(T) & np.isfinite(Y)
    W, T, Y, wk, yr = W[m], T[m], Y[m], wk[m], yr[m]
    rY, rT = np.empty_like(Y), np.empty_like(T)
    for y in harness.VAL_YEARS:
        te, tr = yr == y, yr != y
        for tgt, out in ((Y, rY), (T, rT)):
            g = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=500,
                                              l2_regularization=1.0, early_stopping=False, random_state=0)
            g.fit(W[tr], tgt[tr])
            out[te] = tgt[te] - g.predict(W[te])
    J = rT @ rT
    theta = (rT @ rY) / J
    psi = rT * (rY - theta * rT)
    psi_week = np.bincount(wk, weights=psi, minlength=len(rows))
    se = nw_se(psi_week, J)
    # comparison: the same regression without partialling out (raw rank on rank, pooled)
    Tc, Yc = T - T.mean(), Y - Y.mean()
    raw = (Tc @ Yc) / (Tc @ Tc)
    share_T_explained = 1 - (rT @ rT) / (Tc @ Tc)
    return {"name": f"DML {feat} | MASTER + Z", "theta": float(theta), "theta_t": float(theta / se), "theta_se": float(se),
            "raw_slope": float(raw), "share_of_feature_variance_explained_by_controls": float(share_T_explained),
            "n_obs": int(len(Y)), "weeks": int((np.bincount(wk) > 0).sum()),
            "note": "partially linear DML, HGB nuisances cross-fitted by year, NW(4) over weekly sums",
            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}


if __name__ == "__main__":
    D = harness.load()
    for f in sys.argv[1:] or ["f2", "f5", "f60"]:
        res = run(D, f)
        with open(os.path.join(HERE, "RESULTS.jsonl"), "a") as fh:
            fh.write(json.dumps(res) + "\n")
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in res.items()}))
