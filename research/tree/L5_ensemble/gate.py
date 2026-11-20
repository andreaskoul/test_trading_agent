"""Stage 1 gate for Layer 5 E (development, data <= 2019-12-31; refit before 2018, scored 2018-2019).

E = equal-weight mean of the 20 models' cross-sectional percentile ranks; C = d_model 256, beta 5, nanmean of the raw
scores of seeds 0-4 (the as-run rule). Pass = paired weekly IC increment E - C with NW t (4 lags) >= 1.0 and a positive
mean increment in 2018 and in 2019. Also: each configuration's 5-seed IC, the seed-count variance-reduction curve.
Weekly IC and NW t are L4_arch gate.py's (copied). Writes RESULT.json["stage1"]."""
import itertools
import json
import os
import sys

import numpy as np
import pandas as pd

import ens as A
import run as R
from ens import F


def nw_t(x, L=4):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n, e = len(x), x - x.mean()
    v = e @ e / n
    for l in range(1, L + 1):
        v += 2 * (1 - l / (L + 1)) * (e[l:] @ e[:-l]) / n
    return float(x.mean() / np.sqrt(v / n))


def week_ic(pred, d, year):
    S = d["S"]
    yrs = np.where(S.year == year)[0]
    yrs = yrs[yrs + 1 + 5 <= yrs[-1]]
    wk = A.thursdays(S, yrs)
    y = d["y5"].copy()
    y[yrs[-1] + 1:] = np.nan
    return wk, F.weekly_ic(pred, y, wk)


def ic2(pred, d):
    return {y: week_ic(pred, d, y)[1] for y in (2018, 2019)}


def mean_ic(icd):
    return float(np.nanmean(np.concatenate([icd[2018], icd[2019]])))


def load(t, shape):
    z = np.load(R.pred_path(t))
    p = np.full(shape, np.nan)
    p[z["rows"]] = z["scores"]
    return p, z["rows"], json.loads(str(z["info"]))


def prank(p, rows):
    out = np.full(p.shape, np.nan)
    out[rows] = pd.DataFrame(p[rows]).rank(axis=1, pct=True).to_numpy()
    return out


def avg(panels, rows):
    out = np.full(panels[0].shape, np.nan)
    with np.errstate(all="ignore"):
        out[rows] = np.nanmean([q[rows] for q in panels], 0)
    return out


def paired(a, b):
    inc, by = [], {}
    for y in (2018, 2019):
        m = np.isfinite(a[y]) & np.isfinite(b[y])
        inc.append(a[y][m] - b[y][m])
        by[y] = float(np.mean(a[y][m] - b[y][m]))
    allinc = np.concatenate(inc)
    return {"increment": float(allinc.mean()), "increment_nw_t": nw_t(allinc), "weeks": int(len(allinc)),
            "increment_2018": by[2018], "increment_2019": by[2019]}


def main():
    d = A.build("2019-12-31")
    shp = d["y5"].shape
    raw, rk, info, rows = {}, {}, {}, None
    for (m, b) in A.GRID:
        for s in A.SEEDS:
            t = R.name(m, b, s, 2018)
            p, rows_, inf = load(t, shp)
            assert rows is None or np.array_equal(rows, rows_)
            rows = rows_
            raw[(m, b, s)], info[(m, b, s)] = p, inf
            rk[(m, b, s)] = prank(p, rows)
    keys = list(raw)
    E = avg([rk[k] for k in keys], rows)
    C = avg([raw[(256, 5, s)] for s in A.SEEDS], rows)
    C_rank = avg([rk[(256, 5, s)] for s in A.SEEDS], rows)
    icE, icC, icCr = ic2(E, d), ic2(C, d), ic2(C_rank, d)
    g = paired(icE, icC)
    g["pass"] = bool(g["increment_nw_t"] >= 1.0 and g["increment_2018"] > 0 and g["increment_2019"] > 0)
    g["would_pass_layer5_common_t2"] = bool(g["increment_nw_t"] >= 2.0 and g["increment_2018"] > 0
                                            and g["increment_2019"] > 0)
    res = {"label": "development (data <= 2019-12-31; train <= 2017, scored Thursdays 2018-2019)",
           "E": {"ic_2018_19": mean_ic(icE), "ic_2018": float(np.nanmean(icE[2018])),
                 "ic_2019": float(np.nanmean(icE[2019])), "ic_nw_t": nw_t(np.concatenate(list(icE.values())))},
           "C": {"ic_2018_19": mean_ic(icC), "ic_2018": float(np.nanmean(icC[2018])),
                 "ic_2019": float(np.nanmean(icC[2019])), "ic_nw_t": nw_t(np.concatenate(list(icC.values())))},
           "gate_E_minus_C": g,
           "sensitivity_E_minus_C_rank_avg": {**paired(icE, icCr), "C_rank_ic_2018_19": mean_ic(icCr)},
           "pass": g["pass"], "configs": {}, "variance_reduction": {}}
    for (m, b) in A.GRID:
        five = avg([raw[(m, b, s)] for s in A.SEEDS], rows)
        ic5 = ic2(five, d)
        cfgk = f"d{m}_b{b}"
        res["configs"][cfgk] = {
            "ic5_2018_19": mean_ic(ic5), "ic5_2018": float(np.nanmean(ic5[2018])),
            "ic5_2019": float(np.nanmean(ic5[2019])),
            "seed_ic_2018_19": [mean_ic(ic2(raw[(m, b, s)], d)) for s in A.SEEDS],
            "val_ic": [info[(m, b, s)]["val_ic"] for s in A.SEEDS],
            "epochs": [info[(m, b, s)]["epochs"] for s in A.SEEDS],
            "train_min": [round(info[(m, b, s)]["train_sec"] / 60, 1) for s in A.SEEDS]}
        curve = {}
        for k in range(1, len(A.SEEDS) + 1):
            v = [mean_ic(ic2(avg([raw[(m, b, s)] for s in sub], rows), d))
                 for sub in itertools.combinations(A.SEEDS, k)]
            curve[k] = {"mean": float(np.mean(v)), "min": float(np.min(v)), "max": float(np.max(v)),
                        "sd": float(np.std(v)), "n_subsets": len(v)}
        res["variance_reduction"][cfgk] = curve
    curve = {}
    for k in range(1, len(A.SEEDS) + 1):
        v = [mean_ic(ic2(avg([rk[(m, b, s)] for (m, b) in A.GRID for s in sub], rows), d))
             for sub in itertools.combinations(A.SEEDS, k)]
        curve[k] = {"mean": float(np.mean(v)), "min": float(np.min(v)), "max": float(np.max(v)),
                    "sd": float(np.std(v)), "n_subsets": len(v), "models": 4 * k}
    res["variance_reduction"]["grid_rank_ensemble"] = curve
    out = json.load(open(R.RESULT)) if os.path.exists(R.RESULT) else {}
    out["stage1"] = res
    out["updated"] = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(out, open(R.RESULT, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    sys.exit(main())
