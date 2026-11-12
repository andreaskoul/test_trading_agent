"""Config 4: double machine learning (Chernozhukov et al. 2018), partially linear model
    y = theta * d + g(MASTER rank, Z) + e,   d = m(MASTER rank, Z) + v.
Rows: Thursdays 2016-2019, eligible names with MASTER score, y5 and the intraday feature (no fill).
y = cross-sectional rank of y5; d = cross-sectional rank of the feature; controls = MASTER rank + 5 Z ranks.
g, m: HistGradientBoosting, cross-fitted with year folds (each year predicted by a model fit on the other years).
theta: residual-on-residual; t from weekly Fama-MacBeth slopes with Newey-West (4 lags), and pooled OLS with
week-clustered SE. Inference only, not a predictor (folds use later years to partial out)."""
import os, sys, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import harness as h, features as fe
from sklearn.ensemble import HistGradientBoostingRegressor

D = h.load(); F = fe.build(D)
LOG = os.path.join(HERE, "RESULTS.jsonl")
Mr = fe.rank_rows(D["master_h5_ref"].astype(np.float64))
Zr = np.stack([fe.rank_rows(D["Z"][:, :, j].astype(np.float64)) for j in range(D["Z"].shape[2])], -1)
Yr = fe.rank_rows(np.where(D["elig"], D["y5"], np.nan).astype(np.float64))


def nw_t(x, L=4):
    n = len(x); dd = x - x.mean(); v = dd @ dd / n
    for l in range(1, L + 1): v += 2 * (1 - l / (L + 1)) * (dd[l:] @ dd[:-l]) / n
    return x.mean() / np.sqrt(v / n)


def run(key, years_est=(2017, 2018, 2019)):
    d_all = fe.rank_rows(np.where(D["elig"] & np.isfinite(D["master_h5_ref"]), F[key], np.nan))
    rows = np.concatenate([h.thursdays(D, y) for y in (2016, 2017, 2018, 2019)])
    T, X, Y, Dd, YR = [], [], [], [], []
    for t in rows:
        m = D["elig"][t] & np.isfinite(Mr[t]) & np.isfinite(Yr[t]) & np.isfinite(d_all[t])
        if m.sum() < 50: continue
        X.append(np.column_stack([Mr[t][m], Zr[t][m]])); Y.append(Yr[t][m]); Dd.append(d_all[t][m])
        T.append(np.full(m.sum(), t)); YR.append(np.full(m.sum(), D["S"][t].year))
    X, Y, Dd, T, YR = map(np.concatenate, (X, Y, Dd, T, YR))
    ry, rd = np.full(len(Y), np.nan), np.full(len(Y), np.nan)
    for y in (2016, 2017, 2018, 2019):
        te, tr = YR == y, YR != y
        for tgt, res in ((Y, ry), (Dd, rd)):
            g = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=200, random_state=0)
            g.fit(X[tr], tgt[tr]); res[te] = tgt[te] - g.predict(X[te])
    out = {}
    for lab, yrs in (("2017-2019", years_est), ("2016-2019", (2016, 2017, 2018, 2019))):
        k = np.isin(YR, yrs)
        th = (rd[k] @ ry[k]) / (rd[k] @ rd[k])
        e = ry[k] - th * rd[k]
        # week-clustered SE
        sc = pd.Series(rd[k] * e).groupby(T[k]).sum().to_numpy()
        se = np.sqrt(sc @ sc) / (rd[k] @ rd[k])
        wk = pd.DataFrame({"t": T[k], "d": rd[k], "y": ry[k]}).groupby("t").apply(lambda g: (g.d @ g.y) / (g.d @ g.d)).to_numpy()
        out[lab] = {"theta": float(th), "t_clustered": float(th / se), "theta_fm": float(wk.mean()), "t_fm_nw4": float(nw_t(wk)),
                    "weeks": int(len(wk)), "n": int(k.sum()),
                    "theta_by_year": {int(y): float(pd.Series(wk).groupby(pd.Series(D["S"][np.unique(T[k])].year)).mean().get(y, np.nan)) for y in yrs}}
    rec = {"name": f"N3_c4_dml_{key}", "note": "config4: DML partial slope of y5 rank on feature rank after HGB partialling out MASTER rank + Z ranks; year-fold cross-fitting", **out}
    with open(LOG, "a") as f: f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec, indent=1))


if __name__ == "__main__":
    import time; t0 = time.time()
    for k in sys.argv[1:] or ["id21", "on21_minus_id21"]:
        run(k)
    print("secs", time.time() - t0)
