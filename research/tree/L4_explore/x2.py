"""X2, overnight minus intraday (Lou, Polk and Skouras 2019), development only (STATE.json plan.X2).
Step 2: survivorship contract (Layer 3 Amendment 10). Step 3 runs only if step 2 passes.

    python3 research/tree/L4_explore/x2.py      # -> X2_DEV.json
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
sys.path.insert(0, TREE)
import harness as H  # noqa: E402
from holdout2 import nw  # noqa: E402

W = 21


def main():
    D = H.load()
    X = H.load_extra("intraday")
    R = X["R"].astype(np.float64)                        # (sessions, 14, names); 0 = overnight
    on, idr = R[:, 0, :], R[:, 1:, :].sum(1)
    idr[~np.isfinite(R[:, 1:, :]).all(1)] = np.nan
    S = D["S"]
    has = np.isfinite(on)
    first = int(np.where(has.any(1))[0][0])
    cs = np.vstack([np.zeros((1, on.shape[1])), np.cumsum(has, 0)])
    avail = np.full(on.shape, np.nan)
    for t in range(W - 1, len(S)):
        avail[t] = ((cs[t + 1] - cs[t + 1 - W]) == W).astype(float)
    rows = np.array([t for t in np.where(S.weekday == 3)[0] if t >= first + W - 1 and S[t].year <= 2019])
    a = avail.copy()
    a[~D["elig"]] = np.nan
    ic = H.weekly_ic(a, D, rows)
    m, t, n = nw(ic[np.isfinite(ic)])
    share = float(np.nanmean([np.nansum(avail[r] * D["elig"][r]) / D["elig"][r].sum() for r in rows]))
    res = {"label": "development (2016-2019 source window)", "source_note": str(X["note"]),
           "open_prices_dev_panel": "dev.npz: none. extra_intraday.npz: overnight + 13 half-hour bars, 2016-01-04 .. 2019-12-31, current constituents only. 2020-2025: no open prices on disk in any panel found.",
           "survivorship_contract": {"availability_ic_mean": m, "nw_t": t, "weeks": n,
                                     "share_eligible_names_available": share, "pass": bool(abs(t) < 2)}}
    if abs(t) < 2:
        csum = lambda v: np.vstack([np.zeros((1, v.shape[1])), np.cumsum(np.nan_to_num(v), 0)])  # noqa: E731
        co, ci = csum(on), csum(idr)
        sig = np.full(on.shape, np.nan)
        for tt in range(W - 1, len(S)):
            sig[tt] = (co[tt + 1] - co[tt + 1 - W]) - (ci[tt + 1] - ci[tt + 1 - W])
        sig[avail != 1] = np.nan
        icx = H.weekly_ic(sig, D, rows)
        base = D["master_h5_ref"].astype(np.float64)
        comb = np.full(sig.shape, np.nan)
        for r in rows:
            ok = np.isfinite(sig[r]) & np.isfinite(base[r]) & D["elig"][r]
            from scipy.stats import rankdata
            comb[r, ok] = 0.5 * rankdata(base[r, ok]) / ok.sum() + 0.5 * rankdata(sig[r, ok]) / ok.sum()
        ib = H.weekly_ic(np.where(np.isfinite(comb), base, np.nan), D, rows)
        icc = H.weekly_ic(comb, D, rows)
        k = np.isfinite(icc) & np.isfinite(ib)
        mi, ti, ni = nw(icc[k] - ib[k])
        res["gate"] = {"signal_ic": nw(icx[np.isfinite(icx)]), "master_ic_same_names": float(ib[k].mean()), "combined_ic": float(icc[k].mean()),
                       "increment": mi, "increment_nw_t": ti, "weeks": ni, "pass": bool(ti >= 2)}
    json.dump(res, open(os.path.join(HERE, "X2_DEV.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
