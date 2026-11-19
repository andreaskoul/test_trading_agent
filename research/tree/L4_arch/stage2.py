"""Stage 2 assembly (2020-2025 walk-forward, a reused window): seed-averaged score panels aligned exactly like
quant-tf .cache/quant_trials/sp500_tf_master_h5.npz (key h5, sessions x names of the full build), and each variant's
weekly IC against base MASTER's (the as-run panel), paired. Writes RESULT.json["stage2"]."""
import json
import os

import numpy as np
import pandas as pd

import arch as A
import run as R
from arch import F
from gate import nw_t

BASE = os.path.join(A.QT, ".cache", "quant_trials", "sp500_tf_master_h5.npz")
YEARS = range(2020, 2026)


def main():
    d = A.build("2025-12-31")
    S = d["S"]
    base = np.load(BASE)["h5"].astype(np.float64)
    assert base.shape == d["y5"].shape, (base.shape, d["y5"].shape)
    out = json.load(open(R.RESULT))
    res = {"label": "2020-2025 walk-forward (reused window); annual refits on all data before each test year, "
                    "3 seeds; base = as-run MASTER panel (5 seeds)", "variants": {}}
    for v in out["stage1"]["go_on"]:
        p = np.full(base.shape, np.nan, dtype=np.float32)
        for y in YEARS:
            runs = []
            for s in A.SEEDS:
                z = np.load(R.pred_path(f"{v}_s{s}_y{y}"))
                rows = z["rows"]
                runs.append(z["scores"])
            with np.errstate(all="ignore"):
                p[rows] = np.nanmean(runs, 0)
        path = os.path.join(A.CACHE, f"sp500_tf_master_{v}_h5.npz")
        np.savez_compressed(path, h5=p, meta=json.dumps({"variant": v, "seeds": list(A.SEEDS), "years": list(YEARS),
                                                         "aligned_to": BASE}))
        inc, ic_v, ic_b, by = [], [], [], {}
        for y in YEARS:
            yrs = np.where(S.year == y)[0]
            yrs = yrs[yrs + 1 + 5 <= yrs[-1]]
            wk = A.thursdays(S, yrs)
            yy = d["y5"].copy()
            yy[yrs[-1] + 1:] = np.nan
            a = F.weekly_ic(p.astype(np.float64), yy, wk)
            b = F.weekly_ic(base, yy, wk)
            m = np.isfinite(a) & np.isfinite(b)
            inc.append(a[m] - b[m]); ic_v.append(a[m]); ic_b.append(b[m])
            by[y] = {"ic": float(a[m].mean()), "base_ic": float(b[m].mean()), "increment": float((a[m] - b[m]).mean())}
        inc, ic_v, ic_b = map(np.concatenate, (inc, ic_v, ic_b))
        res["variants"][v] = {"panel": path, "ic": float(ic_v.mean()), "ic_nw_t": nw_t(ic_v),
                              "base_ic": float(ic_b.mean()), "base_ic_nw_t": nw_t(ic_b),
                              "increment": float(inc.mean()), "increment_nw_t": nw_t(inc), "weeks": int(len(inc)),
                              "by_year": by}
    out["stage2"] = res
    out["updated"] = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(out, open(R.RESULT, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
