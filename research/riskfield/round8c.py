"""Risk-field research, Amendment 12: the measured-cost OOS read (2 bp a side) of S1-S3 and A3, 2020-2025.

    python research/riskfield/round8c.py read    # ONCE; refuses if OOS8_READ.lock exists -> OOS8_RESULT.md/json
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import alpha as A                                                                     # noqa: E402
import regime as RG                                                                   # noqa: E402
import risk as K                                                                      # noqa: E402
import round8 as R8                                                                   # noqa: E402
from oos import holm                                                                  # noqa: E402

COSTS = {"gross": 0.0, "2bp": 2e-4, "5bp": 5e-4}


def stats(d):
    m, t, n = K.nw_t(d, 10)
    return {"mean_bp_day": m * 1e4, "t": t, "days": n, "net_pct_yr": float((np.prod(1 + d) ** (252 / len(d)) - 1) * 100),
            "sharpe": float(d.mean() / d.std(ddof=1) * np.sqrt(252))}


def read():
    lock = os.path.join(HERE, "OOS8_READ.lock")
    if os.path.exists(lock):
        raise SystemExit("already read: " + open(lock).read())
    P = RG.panel()
    S = P["S"]
    lo = max(int(np.searchsorted(S.values, np.datetime64(R8.OOS[0]))), 260)
    hi = int(np.searchsorted(S.values, np.datetime64(R8.OOS[1]), side="right")) - 2
    out, cache = {}, {}
    for k, (kind, lag) in R8.TESTS.items():
        if kind not in cache:
            cache[kind] = R8.scores(P, kind, lo - 3, hi)
        s, b, rB = cache[kind]
        out[k + "c"] = {}
        for cn, c in COSTS.items():
            R8.COST = c
            d, info = R8.simulate(P, s, b, rB, lag, lo, hi)
            out[k + "c"][cn] = stats(d) | info
            if cn == "2bp":
                yrs = S[lo:hi + 1].year
                out[k + "c"]["years_2bp"] = {int(y): float((np.prod(1 + d[yrs == y]) - 1) * 100) for y in sorted(set(yrs))}
    a3 = {}
    for cn, c in COSTS.items():
        RG.COST = c
        AD = A.build(A.OOS[1])
        st = A.stats(AD, "A3", A.OOS)
        a3[cn] = st
    out["A3c"] = a3
    res = {}
    for k in ("S1c", "S2c", "S3c"):
        res[k] = {"p": float(norm.sf(out[k]["2bp"]["t"])), "ok": out[k]["2bp"]["mean_bp_day"] > 0}
    # A3c: the net weekly book at 2 bp, NW t (5 lags) on its weekly net returns
    RG.COST = 2e-4
    AD = A.build(A.OOS[1])
    X = AD[(AD.date >= A.OOS[0]) & (AD.date <= A.OOS[1])]
    m, t, n = K.nw_t(X["A3_net"].to_numpy(), 5)
    out["A3c"]["net_book_t_2bp"] = t
    res["A3c"] = {"p": float(norm.sf(t)), "ok": m > 0}
    holm(res)
    for k in res:
        res[k]["pass"] = bool(res[k]["p_holm"] < 0.05 and res[k]["ok"])
    at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    json.dump({"read_at": at, "stats": out, "results": res}, open(os.path.join(HERE, "OOS8_RESULT.json"), "w"), indent=1, default=float)
    open(lock, "w").write(f"read {at}\n")
    L = ["# Risk-field research, round 8 at measured costs (Amendment 12): out-of-sample read 2020-2025 (one read)", "",
         f"Read {at}.", "", "| Test | gross bp/day | 2 bp: net bp/day | t | net %/yr | Sharpe | 5 bp: net %/yr | trades/yr | p Holm | pass |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for k in ("S1c", "S2c", "S3c"):
        g, c2, c5 = out[k]["gross"], out[k]["2bp"], out[k]["5bp"]
        L.append(f"| {k} | {g['mean_bp_day']:.2f} | {c2['mean_bp_day']:.2f} | {c2['t']:.2f} | {c2['net_pct_yr']:.2f} | {c2['sharpe']:.2f} | "
                 f"{c5['net_pct_yr']:.2f} | {c2['trades_per_year']:.0f} | {res[k]['p_holm']:.4f} | {'**yes**' if res[k]['pass'] else 'no'} |")
    a = out["A3c"]
    L.append(f"| A3c (weekly) | {a['gross']['net_mean_bp']:.1f} bp/wk | {a['2bp']['net_mean_bp']:.1f} bp/wk | {a['net_book_t_2bp']:.2f} | "
             f"{a['2bp']['net_pct_yr']:.2f} | {a['2bp']['sharpe']:.2f} | {a['5bp']['net_pct_yr']:.2f} | — | {res['A3c']['p_holm']:.4f} | "
             f"{'**yes**' if res['A3c']['pass'] else 'no'} |")
    L += ["", "S tests by year at 2 bp, %: " + "; ".join(f"{k}: " + ", ".join(f"{y} {v:+.1f}" for y, v in out[k]["years_2bp"].items())
                                                     for k in ("S1c", "S2c", "S3c"))]
    open(os.path.join(HERE, "OOS8_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__" and sys.argv[1:] == ["read"]:
    read()
