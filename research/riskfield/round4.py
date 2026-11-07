"""Risk-field research, round 4 (PREREG.md Amendment 7): next-day contagion of news-day shocks (order timing).

    python research/riskfield/round4.py dev     # -> DEV4_RESULT.md/json
    python research/riskfield/round4.py read    # ONCE; refuses if OOS4_READ.lock exists -> OOS4_RESULT.md/json
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "regime"))
import alpha as A                                                                     # noqa: E402
import panel as PN                                                                    # noqa: E402
import regime as RG                                                                   # noqa: E402
from intl import dk_t                                                                 # noqa: E402
from oos import holm                                                                  # noqa: E402

DEV = (pd.Timestamp("2011-06-01"), pd.Timestamp("2019-12-31"))
OOS = (pd.Timestamp("2020-01-02"), pd.Timestamp("2025-12-30"))
TESTS = ("D1", "D2", "D3")


def build(period):
    P = RG.panel()
    S, names = P["S"], P["names"]
    z = np.load(os.path.join(PN.CACHE, "news_days.npz"))
    assert list(z["names"]) == list(names) and len(z["S"]) == len(S)
    e = P["e"]
    e0 = np.nan_to_num(e)
    sh_all = np.where(z["earn"] | z["uns"], e0, 0.0)
    sh_earn = np.where(z["earn"], e0, 0.0)
    days = [t for t in range(260, len(S) - 2) if period[0] <= S[t] <= period[1]]
    out = {k: {"d": [], "y1": [], "y2": [], "x": [], "R": []} for k in TESTS}
    month, Wt, Wc, has = None, None, None, None
    for t in days:
        if (S[t].year, S[t].month) != month:
            month = (S[t].year, S[t].month)
            tau = t
            while tau > 0 and (S[tau - 1].year, S[tau - 1].month) == month:
                tau -= 1
            Wt, has = PN.text_kernel(names, S[tau])
            Wc = A.co_kernel(e[tau - 252:tau], P["elig"][tau - 1])
        el = P["elig"][t] & np.isfinite(e[t + 1])
        a = np.where(P["elig"][t], sh_all[t], np.nan)
        er = np.where(P["elig"][t], sh_earn[t], np.nan)
        sig = {"D1": np.where(el & has, A.fld(Wt, np.where(has, a, np.nan)), np.nan),
               "D2": np.where(el, A.fld(Wc, a), np.nan),
               "D3": np.where(el & has, A.fld(Wt, np.where(has, er, np.nan)), np.nan)}
        for k, s in sig.items():
            zz = RG.zs(s)
            out[k]["d"].append(t)
            out[k]["x"].append(zz)
            out[k]["y1"].append(np.where(el, e[t + 1], np.nan))
            out[k]["y2"].append(np.where(el, e[t + 2], np.nan))
            out[k]["R"].append(np.where(el, P["close"][t + 1] / P["close"][t] - 1, np.nan))
    return out, P


def stats(o, P):
    res = {}
    for h in ("y1", "y2"):
        blocks = [(np.full(len(x), i), y, x) for i, (x, y) in enumerate(zip(o["x"], o[h]))]
        b, t, n = dk_t(blocks)
        res[h] = {"b": b, "t": t, "n": n, "bp_per_sd": b * 1e4}
    # daily decile book (reported): beta-hedged with SPY, 5 bp per unit of one-sided turnover
    g, prev, net = [], None, []
    for t, x, R in zip(o["d"], o["x"], o["R"]):
        w, wspy = RG.decile_book(x, P["beta"][t])
        rm = P["spy"][t + 1] / P["spy"][t] - 1
        gr = float(np.nansum(w * R) + wspy * rm)
        to = 1.0 if prev is None else float(np.abs(w - prev[0]).sum() + abs(wspy - prev[1]))
        prev = (w, wspy)
        g.append(gr)
        net.append(gr - RG.COST * to)
    g, net = np.array(g), np.array(net)
    res["book"] = {"gross_bp_day": float(g.mean() * 1e4), "net_bp_day": float(net.mean() * 1e4),
                   "gross_sharpe": float(g.mean() / g.std() * np.sqrt(252)), "days": len(g)}
    return res


def run(period):
    out, P = build(period)
    return {k: stats(out[k], P) for k in TESTS}


def table(r, title):
    L = [f"# Risk-field research, round 4 (next-day news contagion): {title}", "",
         "| Test | slope e(t+1), bp per sd | DK t | e(t+2) bp/sd | t | daily book gross bp | net bp | gross Sharpe |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k in TESTS:
        a = r[k]
        L.append(f"| {k} | {a['y1']['bp_per_sd']:.2f} | {a['y1']['t']:.2f} | {a['y2']['bp_per_sd']:.2f} | {a['y2']['t']:.2f} | "
                 f"{a['book']['gross_bp_day']:.2f} | {a['book']['net_bp_day']:.2f} | {a['book']['gross_sharpe']:.2f} |")
    return L


def dev():
    r = run(DEV)
    fin = [k for k in TESTS if r[k]["y1"]["t"] >= 1.5]
    r["finalists"] = fin
    json.dump(r, open(os.path.join(HERE, "DEV4_RESULT.json"), "w"), indent=1, default=float)
    L = table(r, "development") + ["", f"**Finalists:** {', '.join(fin) if fin else 'none'}"]
    open(os.path.join(HERE, "DEV4_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


def read():
    lock = os.path.join(HERE, "OOS4_READ.lock")
    if os.path.exists(lock):
        raise SystemExit("already read: " + open(lock).read())
    fin = json.load(open(os.path.join(HERE, "DEV4_RESULT.json")))["finalists"]
    if not fin:
        raise SystemExit("no finalists: nothing to read")
    r = run(OOS)
    res = {k: {"p": float(norm.sf(r[k]["y1"]["t"])), "ok_sign": r[k]["y1"]["b"] > 0} for k in fin}
    holm(res)
    for k in res:
        res[k]["pass"] = bool(res[k]["p_holm"] < 0.05 and res[k]["ok_sign"])
    at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    json.dump({"read_at": at, "finalists": fin, "stats": r, "results": res}, open(os.path.join(HERE, "OOS4_RESULT.json"), "w"),
              indent=1, default=float)
    open(lock, "w").write(f"read {at}\n")
    L = table(r, f"out-of-sample read (one read, {at})") + ["", "Only finalists count.", ""] + [
        f"* **{k}**: p one-sided {v['p']:.4f}, Holm {v['p_holm']:.4f}, {'**pass**' if v['pass'] else 'fail'}" for k, v in res.items()]
    open(os.path.join(HERE, "OOS4_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"dev": dev, "read": read}[sys.argv[1]]()
