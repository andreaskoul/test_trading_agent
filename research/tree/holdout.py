"""The one holdout read of the tree search (research/tree/PREREG.md section 4). Coordinating session only.

    python research/tree/holdout.py A_loss C_features ...     # at most three finalists; refuses a second run
"""
import importlib.util
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
QT = os.environ.get("QT_ROOT", os.path.join(os.path.dirname(ROOT), "quant-tf"))
sys.path.insert(0, HERE)
import harness as H     # noqa: E402

YEARS = (2020, 2021, 2022, 2023, 2024, 2025)


def full_panel():
    sys.path.insert(0, os.path.join(QT, "research", "quant_trials"))
    import sp500_test as T
    d = T.build()
    D = {"S": pd.DatetimeIndex(d["S"]), "names": list(d["names"]), "r": d["r"].astype(np.float32), "rm": d["rm"].astype(np.float32),
         "e": d["e"], "elig": d["elig"], "beta": d["beta"].astype(np.float32), "Z": d["Z"], "y5": d["y5"].astype(np.float32), "valid": d["valid"]}
    D["master_h5_ref"] = np.load(os.path.join(QT, ".cache", "quant_trials", "sp500_tf_master_h5.npz"))["h5"]
    return D


def nw_t(x, lags=4):
    x = x[np.isfinite(x)]
    n = len(x)
    d = x - x.mean()
    v = d @ d / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (d[l:] @ d[:-l]) / n
    return float(x.mean()), float(x.mean() / math.sqrt(v / n)), n


def main():
    finalists = sys.argv[1:]
    assert 1 <= len(finalists) <= 3, "at most three finalists"
    lock = os.path.join(HERE, "READ.lock")
    if os.path.exists(lock):
        sys.exit("the holdout was already read: " + open(lock).read())
    open(lock, "w").write(datetime.now(timezone.utc).isoformat(timespec="seconds") + " " + " ".join(finalists))
    D = full_panel()
    rows = np.concatenate([H.thursdays(D, y) for y in YEARS])
    rows = rows[rows < len(D["S"]) - 7]
    res = {"run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "finalists": {}}
    ref = H.weekly_ic(D["master_h5_ref"].astype(np.float64), D, rows)
    res["master_reference"] = {"ic": float(np.nanmean(ref)), "t": nw_t(ref)[1]}
    p = {}
    for f in finalists:
        spec = importlib.util.spec_from_file_location(f"model_{f}", os.path.join(HERE, f, "model.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pred = H.walk_forward(mod.fit_predict, seeds=(0, 1, 2), years=YEARS, D=D)
        np.save(os.path.join(ROOT, ".cache", "tree", f"holdout_pred_{f}.npy"), pred.astype(np.float32))
        ic = H.weekly_ic(pred, D, rows)
        mean, t, n = nw_t(ic)
        net = H.decile_net(pred, D, rows)
        both = np.isfinite(ic) & np.isfinite(ref)
        res["finalists"][f] = {"ic": mean, "t": t, "weeks": n, "p_one_sided": float(0.5 * math.erfc(t / math.sqrt(2))),
                               "ic_by_year": {y: float(np.nanmean(H.weekly_ic(pred, D, H.thursdays(D, y)[H.thursdays(D, y) < len(D['S']) - 7]))) for y in YEARS},
                               "decile_net_pct_per_year": float(52 * net.mean() * 100), "decile_net_sharpe": float(net.mean() / net.std(ddof=1) * math.sqrt(52)),
                               "ic_minus_master": float((ic[both] - ref[both]).mean()), "t_vs_master": nw_t(ic[both] - ref[both])[1]}
        p[f] = res["finalists"][f]["p_one_sided"]
    order = sorted(p, key=p.get)
    ok = True
    for i, f in enumerate(order):
        ok = ok and p[f] <= 0.05 / (len(p) - i)
        res["finalists"][f]["holm_pass"] = bool(ok)
    json.dump(res, open(os.path.join(HERE, "HOLDOUT_RESULT.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
