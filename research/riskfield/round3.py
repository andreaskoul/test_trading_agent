"""Risk-field research, round 3 (PREREG.md Amendment 6): contagion of news-derived shocks.

    python research/riskfield/round3.py dev     # -> DEV3_RESULT.md/json
    python research/riskfield/round3.py read    # ONCE; refuses if OOS3_READ.lock exists -> OOS3_RESULT.md/json
"""
import json
import os
import sys

import pandas as pd
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import alpha as A                                                                     # noqa: E402
import risk as K                                                                      # noqa: E402
from oos import holm                                                                  # noqa: E402

ALPHAS = ("C1", "C2", "C3")


def run(period, a_period):
    D = K.Data()
    c, b, hl = K.RTESTS3["C4"]
    out = {"C4": {f"h{h}": K.compare(D, c, b, h, period, hl)[0] for h in K.HS}}
    AD = A.build(a_period[1], contagion=True)
    for k in ALPHAS:
        out[k] = A.stats(AD, k + "B", a_period)
        out[k + "_unbanded"] = A.stats(AD, k, a_period)
    return out


def table(out, title):
    r = out["C4"]
    L = [f"# Risk-field research, round 3 (news-shock contagion): {title}", "",
         f"* C4 volatility contagion: h5 gain {r['h5']['gain']:.5f} (t {r['h5']['t']:.2f}); h22 gain {r['h22']['gain']:.5f} "
         f"(t {r['h22']['t']:.2f}); {r['h5']['names_per_day']:.0f} names/day", "",
         "| Test | slope | DK t | banded net %/yr | banded Sharpe | unbanded net %/yr | names | weeks |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k in ALPHAS:
        a, u = out[k], out[k + "_unbanded"]
        L.append(f"| {k} | {a['b']:.5f} | {a['t']:.2f} | {a['net_pct_yr']:.2f} | {a['sharpe']:.2f} | {u['net_pct_yr']:.2f} | {a['names']:.0f} | {a['weeks']} |")
    return L


def dev():
    out = run(K.DEV, A.DEV)
    fin = []
    if out["C4"]["h5"]["t"] >= 1.5 and out["C4"]["h22"]["gain"] >= 0:
        fin.append("C4")
    fin += [k for k in ALPHAS if out[k]["t"] >= 1.5 and out[k]["net_mean_bp"] > 0]
    out["finalists"] = fin
    json.dump(out, open(os.path.join(HERE, "DEV3_RESULT.json"), "w"), indent=1, default=float)
    L = table(out, "development") + ["", f"**Finalists:** {', '.join(fin) if fin else 'none'}"]
    open(os.path.join(HERE, "DEV3_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


def read():
    lock = os.path.join(HERE, "OOS3_READ.lock")
    if os.path.exists(lock):
        raise SystemExit("already read: " + open(lock).read())
    fin = json.load(open(os.path.join(HERE, "DEV3_RESULT.json")))["finalists"]
    if not fin:
        raise SystemExit("no finalists: nothing to read")
    out = run(K.OOS, A.OOS)
    res = {}
    for k in fin:
        r = out[k]
        t = r["h5"]["t"] if k == "C4" else r["t"]
        ok = (r["h5"]["gain"] > 0 and r["h22"]["gain"] > 0) if k == "C4" else r["net_mean_bp"] > 0
        res[k] = {"p": float(norm.sf(t)), "ok_sign": bool(ok)}
    holm(res)
    for k in res:
        res[k]["pass"] = bool(res[k]["p_holm"] < 0.05 and res[k]["ok_sign"])
    at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    json.dump({"read_at": at, "finalists": fin, "stats": out, "results": res}, open(os.path.join(HERE, "OOS3_RESULT.json"), "w"),
              indent=1, default=float)
    open(lock, "w").write(f"read {at}\n")
    L = table(out, f"out-of-sample read (one read, {at})")
    L += ["", "Only finalists count; the rest is reported.", ""] + [
        f"* **{k}**: p one-sided {r['p']:.4f}, Holm {r['p_holm']:.4f}, {'**pass**' if r['pass'] else 'fail'}" for k, r in res.items()]
    open(os.path.join(HERE, "OOS3_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"dev": dev, "read": read}[sys.argv[1]]()
