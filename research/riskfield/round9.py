"""Risk-field research, round 9 (PREREG.md Amendment 13): news-filtered OU stat-arb (S4, S5) against S3, at 2 bp.

    python research/riskfield/round9.py dev     # development 2011-06..2019 -> DEV9_RESULT.md/json (no confirmation here)
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import alpha as A                                                                     # noqa: E402
import panel as PN                                                                    # noqa: E402
import regime as RG                                                                   # noqa: E402
import round8 as R8                                                                   # noqa: E402
import round8c as R8C                                                                 # noqa: E402


def blocks(P, lo, hi):
    z = np.load(os.path.join(PN.CACHE, "news_days.npz"))
    assert list(z["names"]) == list(P["names"])
    news = z["earn"] | z["uns"]
    c = np.vstack([np.zeros((1, news.shape[1])), np.cumsum(news, 0)])
    own = np.zeros(news.shape, bool)
    own[4:] = (c[5:] - c[:-5]) > 0
    ce = np.vstack([np.zeros((1, news.shape[1])), np.cumsum(z["earn"], 0)])
    earn5 = np.zeros(news.shape, bool)
    earn5[4:] = (ce[5:] - ce[:-5]) > 0
    S, names = P["S"], P["names"]
    nb = np.zeros(news.shape, bool)
    month = None
    for t in range(lo, hi + 1):
        if (S[t].year, S[t].month) != month:
            month = (S[t].year, S[t].month)
            tau = t
            while tau > 0 and (S[tau - 1].year, S[tau - 1].month) == month:
                tau -= 1
            W = A.co_kernel(P["e"][tau - 252:tau], P["elig"][tau - 1]) > 0
        nb[t] = (W.astype(float) @ earn5[t].astype(float)) > 0
    return own, own | nb


def dev():
    P = RG.panel()
    S = P["S"]
    lo = max(int(np.searchsorted(S.values, np.datetime64(R8.DEV[0]))), 260)
    hi = int(np.searchsorted(S.values, np.datetime64(R8.DEV[1]), side="right")) - 2
    s, b, rB = R8.scores(P, "co", lo - 3, hi)
    own, both = blocks(P, lo - 3, hi)
    out = {}
    for k, blk in (("S3", None), ("S4", own), ("S5", both)):
        out[k] = {}
        for cn, c in (("gross", 0.0), ("2bp", 2e-4)):
            R8.COST = c
            d, info = R8.simulate(P, s, b, rB, 2, lo, hi, blk)
            out[k][cn] = R8C.stats(d) | info
    fin = [k for k in ("S4", "S5") if out[k]["2bp"]["t"] >= 1.5 and out[k]["2bp"]["mean_bp_day"] > 0
           and out[k]["2bp"]["mean_bp_day"] > out["S3"]["2bp"]["mean_bp_day"]]
    out["finalists"] = fin
    json.dump(out, open(os.path.join(HERE, "DEV9_RESULT.json"), "w"), indent=1, default=float)
    L = ["# Risk-field research, round 9 (news-filtered stat-arb): development 2011-06..2019", "",
         "| Test | gross bp/day | 2 bp: net bp/day | t | net %/yr | Sharpe | trades/yr | avg open |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k in ("S3", "S4", "S5"):
        g, c = out[k]["gross"], out[k]["2bp"]
        L.append(f"| {k} | {g['mean_bp_day']:.2f} | {c['mean_bp_day']:.2f} | {c['t']:.2f} | {c['net_pct_yr']:.2f} | {c['sharpe']:.2f} | "
                 f"{c['trades_per_year']:.0f} | {c['avg_open']:.0f} |")
    L += ["", f"**Finalists:** {', '.join(fin) or 'none'} (a confirmation needs unread data: Amendment 13)"]
    open(os.path.join(HERE, "DEV9_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"dev": dev}[sys.argv[1]]()
