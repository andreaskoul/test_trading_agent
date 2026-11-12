"""Configuration 5: double machine learning (Chernozhukov et al. 2018), partially linear model, development
Thursdays 2013-2019 on names where MASTER is defined.

Y = ranked 5-session target; T = rank of the equal-weight literature composite (missing = neutral 0);
controls W = rank MASTER + the five ranked characteristics D["Z"] (NaN kept). Nuisances E[Y|W], E[T|W] by
HistGradientBoosting (early_stopping=False), cross-fitted by calendar year (each year's residuals from models fitted on
the other six). theta = sum(rT rY) / sum(rT^2); SE from influence terms summed by week, Newey-West 4 lags.
Descriptive estimate of the composite's partial effect, not a forecast (folds use later years).
Usage: python3 dml.py [treatment]   (treatment in composite | any lib characteristic); appends to RESULTS_DML.jsonl
"""
import json, sys, time
import numpy as np
import lib
from lib import harness
from sklearn.ensemble import HistGradientBoostingRegressor


def nw(psi, lags=4):
    n = len(psi); u = psi - psi.mean(); v = u @ u / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (u[l:] @ u[:-l]) / n
    return v * n


def run(treat="composite"):
    D, R = lib.data(), lib.ranks()
    rows = np.concatenate([harness.thursdays(D, y) for y in harness.VAL_YEARS])
    Zr = np.stack([lib.xrank(D["Z"][rows][:, :, k].astype(np.float64), D["elig"][rows]) for k in range(5)], -1)
    W = np.concatenate([R["master"][rows][..., None], Zr], -1)
    Tm = lib.composite() if treat == "composite" else R[treat]
    T = np.nan_to_num(lib.xrank(Tm[rows], D["elig"][rows]), nan=0.0)
    Y = lib.target_rank(D, rows)
    wk = np.broadcast_to(np.arange(len(rows))[:, None], Y.shape)
    yr = np.broadcast_to(D["S"][rows].year.to_numpy()[:, None], Y.shape)
    m = np.isfinite(Y) & np.isfinite(R["master"][rows]) & D["elig"][rows]
    W, T, Y, wk, yr = W[m], T[m], Y[m], wk[m], yr[m]
    rY, rT = np.empty_like(Y), np.empty_like(T)
    for y in harness.VAL_YEARS:
        te, tr = yr == y, yr != y
        for tgt, out in ((Y, rY), (T, rT)):
            g = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=500,
                                              early_stopping=False, random_state=0).fit(W[tr], tgt[tr])
            out[te] = tgt[te] - g.predict(W[te])
    J = float(rT @ rT)
    theta = float(rT @ rY) / J
    psi = rT * (rY - theta * rT)
    psi_w = np.bincount(wk, weights=psi)
    se = float(np.sqrt(nw(psi_w)) / J)
    by = {}
    for y in harness.VAL_YEARS:
        s = yr == y
        by[y] = float(rT[s] @ rY[s] / (rT[s] @ rT[s]))
    ols = float(np.polyfit(T, Y, 1)[0])
    res = {"name": f"dml_{treat}", "theta": theta, "se": se, "t": theta / se, "naive_slope": ols, "n": int(len(Y)),
           "weeks": int(len(np.unique(wk))), "theta_by_year": by, "years_positive": int(sum(v > 0 for v in by.values())),
           "var_share_T_explained_by_W": float(1 - rT.var() / T.var()), "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "note": "Y rank target, T ranked treatment (missing 0), W = rank MASTER + ranked Z; HGB nuisances cross-fitted by year; NW(4) by week"}
    with open(lib.os.path.join(lib.HERE, "RESULTS_DML.jsonl"), "a") as f:
        f.write(json.dumps(res) + "\n")
    print(json.dumps(res), flush=True)
    return res


if __name__ == "__main__":
    import run_blend
    for t in (sys.argv[1:] or ["composite"]):
        r = run(t)
        lib.update_state(r["name"], f"{r['name']}: theta {r['theta']:.4f} t {r['t']:.2f} (RESULTS_DML.jsonl)", run_blend.PLAN)
