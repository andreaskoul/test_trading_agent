"""Earnings-announcement premium (research/eventrisk/PREREG.md, Amendment 2). Nothing here trades.

    python research/eventrisk/premium.py dev
    python research/eventrisk/premium.py oos      # one read (OOS2_READ.lock)
"""
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import study as K

HERE = os.path.dirname(os.path.abspath(__file__))
COST, MIN_A = 2e-4, 10


def weights(mask):
    n = mask.sum()
    return np.where(mask, 1.0 / n, 0.0) if n else np.zeros(mask.shape)


def run(period, shift=0):
    D = K.build(shift)
    S, e = D["S"], D["e"]
    F, rv, nE, ok = K.window(D, 5)
    x = e.rolling(5, min_periods=5).sum().shift(-5).to_numpy()
    per = K.in_period(S, 5, period)
    thu = np.array([d.weekday() == 3 for d in S]) & per
    ap1, ap2, c1, c2, nA = [], [], [], [], []
    wa_prev = wn_prev = np.zeros(x.shape[1])
    for t in np.where(thu)[0]:
        m = ok[t] & np.isfinite(x[t])
        A, N = m & (nE[t] >= 1), m & (nE[t] == 0)
        if A.sum() < MIN_A or N.sum() < MIN_A:
            wa, wn = np.zeros(x.shape[1]), np.zeros(x.shape[1])
            ap1.append(0.0); ap2.append(0.0)
        else:
            wa, wn = weights(A), weights(N)
            ap1.append(float(x[t][A].mean() - x[t][N].mean())); ap2.append(float(x[t][A].mean()))
        ta, tn = np.abs(wa - wa_prev).sum(), np.abs(wn - wn_prev).sum()
        c1.append(COST * (ta + tn)); c2.append(COST * ta)
        wa_prev, wn_prev = wa, wn
        nA.append(int(A.sum()))
    out = {"weeks": len(ap1), "weeks_counted": int(sum(n >= MIN_A for n in nA)), "announcers_per_counted_week": float(np.mean([n for n in nA if n >= MIN_A]))}
    for name, r, c in (("AP1", np.array(ap1), np.array(c1)), ("AP2", np.array(ap2), np.array(c2))):
        mean, t, n = K.nw_t(r, 2)
        net = r - c
        mn, tn_, _ = K.nw_t(net, 2)
        out[name] = {"gross_pct_per_year": 5200 * mean, "t": t, "p_one_sided": K.p_one(t), "sharpe": float(mean / r.std() * math.sqrt(52)),
                     "net_pct_per_year": 5200 * mn, "t_net": tn_, "sharpe_net": float(mn / net.std() * math.sqrt(52)),
                     "cost_pct_per_year": 5200 * float(c.mean()), "weekly_sd_pct": 100 * float(r.std())}
    return out


def main():
    period = sys.argv[1]
    lock = os.path.join(HERE, "OOS2_READ.lock")
    if period == "oos":
        if os.path.exists(lock):
            sys.exit("the read was already made: " + open(lock).read())
        open(lock, "w").write(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    res = run(period)
    res["placebo_calendar_shift_21"] = run(period, shift=21)
    res["run"], res["period"] = datetime.now(timezone.utc).isoformat(timespec="seconds"), period
    json.dump(res, open(os.path.join(HERE, {"dev": "DEV2_RESULT.json", "oos": "OOS2_RESULT.json"}[period]), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
