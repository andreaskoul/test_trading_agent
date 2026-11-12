"""Reported beside the holdout tests (PREREG Amendment 1): each finalist's decile spread net of 5 bp a side, raw and
with the X2 score smoothing (exponential, half-life 1 week, over the current and up to 12 preceding Thursdays).

Uses only the saved holdout predictions. The first weeks of 2020 have fewer than 12 earlier holdout Thursdays to
smooth over (2019 Thursdays were not predicted in the holdout run); this is disclosed in the output.

    python research/tree/smoothed_spread.py X1_8p A_mse_rank D_hgb_mh
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import harness as H        # noqa: E402
import holdout as HO       # noqa: E402

HL, LOOK = 1.0, 12


def smooth(pred, rows):
    out = np.full(pred.shape, np.nan)
    w = 0.5 ** (np.arange(LOOK + 1) / HL)
    R = pd.DataFrame(pred[rows]).rank(axis=1, pct=True).to_numpy()
    for i in range(len(rows)):
        lo = max(0, i - LOOK)
        block = R[lo:i + 1][::-1]
        ww = w[:len(block)][:, None] * np.isfinite(block)
        num = np.nansum(block * w[:len(block)][:, None], 0)
        den = ww.sum(0)
        s = np.where(den > 0, num / np.where(den > 0, den, 1), np.nan)
        s[~np.isfinite(R[i])] = np.nan
        out[rows[i]] = s
    return out


def main():
    D = HO.full_panel()
    rows = np.concatenate([H.thursdays(D, y) for y in HO.YEARS])
    rows = rows[rows < len(D["S"]) - 7]
    res = {}
    for f in sys.argv[1:]:
        p = np.load(os.path.join(ROOT, ".cache", "tree", "holdout_pred_finalists", f"{f}.npy")).astype(np.float64)
        for tag, q in (("raw", p), ("smoothed_hl1", smooth(p, rows))):
            net = H.decile_net(q, D, rows)
            ic = H.weekly_ic(q, D, rows)
            res[f"{f}_{tag}"] = {"ic": float(np.nanmean(ic)), "decile_net_pct_per_year": float(52 * net.mean() * 100),
                                 "decile_net_sharpe": float(net.mean() / net.std(ddof=1) * math.sqrt(52)), "weeks": int(len(net))}
    res["note"] = "the first 12 holdout weeks are smoothed over fewer than 12 earlier weeks"
    json.dump(res, open(os.path.join(HERE, "HOLDOUT_SMOOTHED.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
