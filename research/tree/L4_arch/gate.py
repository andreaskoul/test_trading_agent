"""Stage 1 gate (development, data <= 2019-12-31): paired weekly IC increment of each variant over the base on the
Thursdays of 2018-2019; pass = NW t (4 lags) >= 1.0 and the mean increment positive in 2018 and in 2019; at most the
two best by mean increment go on. Also the base reproduction check against the as-run 2018 refit (dev.npz
master_h5_ref, rows <= 2019 only). Writes RESULT.json["stage1"]."""
import json
import os

import numpy as np
import pandas as pd

import arch as A
import run as R
from arch import F


def nw_t(x, L=4):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n, e = len(x), x - x.mean()
    v = e @ e / n
    for l in range(1, L + 1):
        v += 2 * (1 - l / (L + 1)) * (e[l:] @ e[:-l]) / n
    return float(x.mean() / np.sqrt(v / n))


def panel(v, d, seeds=A.SEEDS):
    out = np.full(d["y5"].shape, np.nan)
    runs, infos = [], []
    for s in seeds:
        z = np.load(R.pred_path(f"{v}_s{s}_y2018"))
        rows = z["rows"]
        p = np.full(d["y5"].shape, np.nan)
        p[rows] = z["scores"]
        runs.append(p)
        infos.append(json.loads(str(z["info"])))
    with np.errstate(all="ignore"):
        out[rows] = np.nanmean([r_[rows] for r_ in runs], 0)
    return out, runs, infos


def week_ic(pred, d, year):
    S = d["S"]
    yrs = np.where(S.year == year)[0]
    yrs = yrs[yrs + 1 + 5 <= yrs[-1]]
    wk = A.thursdays(S, yrs)
    y = d["y5"].copy()
    y[yrs[-1] + 1:] = np.nan
    return wk, F.weekly_ic(pred, y, wk)


def main():
    d = A.build("2019-12-31")
    res = {"label": "development (data <= 2019-12-31; train <= 2017, scored 2018-2019)", "variants": {}}
    base, base_runs, base_info = panel("base", d)
    b_ic = {y: week_ic(base, d, y)[1] for y in (2018, 2019)}
    dev = np.load(os.path.join(A.ROOT, ".cache", "tree", "dev.npz"))
    ref = dev["master_h5_ref"].astype(np.float64)                     # as-run panel, rows <= 2019 only
    r18 = week_ic(ref, d, 2018)[1]
    r19 = week_ic(ref, d, 2019)[1]
    res["base"] = {"ic_2018": float(np.nanmean(b_ic[2018])), "ic_2019": float(np.nanmean(b_ic[2019])),
                   "ic_2018_19": float(np.nanmean(np.concatenate(list(b_ic.values())))),
                   "seed_ic_2018_19": [float(np.nanmean(np.concatenate([week_ic(r_, d, y)[1] for y in (2018, 2019)])))
                                       for r_ in base_runs],
                   "fits": [{k: i[k] for k in ("epochs", "best_epoch", "val_ic", "train_sec")} for i in base_info],
                   "reproduction": {
                       "as_run_ic_2018": float(np.nanmean(r18)),
                       "as_run_ic_2019_refit_2019": float(np.nanmean(r19)),
                       "note": "as-run panel = 5 seeds (0-4); its 2018 rows come from the same training window as "
                               "stage 1 (refit before 2018); its 2019 rows from the refit before 2019. Stage-1 base = "
                               "seeds 0-2, one fit before 2018 scoring both years.",
                       "weekly_corr_2018_base_vs_as_run": float(np.corrcoef(b_ic[2018][np.isfinite(r18)],
                                                                            r18[np.isfinite(r18)])[0, 1])}}
    rank = []
    for v in ("A1", "A2", "A3", "A4"):
        try:
            p, runs, info = panel(v, d)
        except FileNotFoundError:
            res["variants"][v] = {"missing": True}
            continue
        inc, by = [], {}
        icv = {}
        for y in (2018, 2019):
            a = week_ic(p, d, y)[1]
            icv[y] = a
            m = np.isfinite(a) & np.isfinite(b_ic[y])
            inc.append(a[m] - b_ic[y][m])
            by[y] = float(np.mean(a[m] - b_ic[y][m]))
        allinc = np.concatenate(inc)
        t = nw_t(allinc)
        passed = bool(t >= 1.0 and by[2018] > 0 and by[2019] > 0)
        res["variants"][v] = {"ic_2018_19": float(np.nanmean(np.concatenate(list(icv.values())))),
                              "ic_2018": float(np.nanmean(icv[2018])), "ic_2019": float(np.nanmean(icv[2019])),
                              "increment": float(allinc.mean()), "increment_nw_t": t, "weeks": int(len(allinc)),
                              "increment_2018": by[2018], "increment_2019": by[2019], "pass": passed,
                              "seed_ic_2018_19": [float(np.nanmean(np.concatenate([week_ic(r_, d, y)[1]
                                                                                  for y in (2018, 2019)])))
                                                  for r_ in runs],
                              "fits": [{k: i[k] for k in ("epochs", "best_epoch", "val_ic", "train_sec")}
                                       for i in info]}
        if passed:
            rank.append((allinc.mean(), v))
    res["go_on"] = [v for _, v in sorted(rank, reverse=True)[:2]]
    res["stage2_runs"] = bool(res["go_on"])
    out = json.load(open(R.RESULT)) if os.path.exists(R.RESULT) else {}
    out["stage1"] = res
    out["updated"] = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(out, open(R.RESULT, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
