"""Risk-field research, round 2 (PREREG.md Amendment 4): development, then the single OOS read.

    python research/riskfield/round2.py dev     # -> DEV2_RESULT.md/json
    python research/riskfield/round2.py read    # ONCE; refuses if OOS2_READ.lock exists -> OOS2_RESULT.md/json
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
import beta as BT                                                                     # noqa: E402
import risk as K                                                                      # noqa: E402
from oos import holm                                                                  # noqa: E402

A4_DEV = (pd.Timestamp("2016-02-01"), pd.Timestamp("2019-12-31"))


def run(period, a4_period):
    D = K.Data()
    out = {}
    c, b, hl = K.RTESTS2["R6"]
    out["R6"] = {f"h{h}": K.compare(D, c, b, h, period, hl)[0] for h in K.HS}
    out["H-B3"] = BT.compare(D, BT.build(D), "H-B3", period)
    AD = A.build(a4_period[1], D)
    out["A4B"] = A.stats(AD, "A4B", a4_period)
    out["A4"] = A.stats(AD, "A4", a4_period)                        # unbanded, reported
    return out


def table(out, title):
    r = out["R6"]
    L = [f"# Risk-field research, round 2: {title}", "",
         f"* R6 signed jumps: h5 gain {r['h5']['gain']:.5f} (t {r['h5']['t']:.2f}); h22 gain {r['h22']['gain']:.5f} (t {r['h22']['t']:.2f})",
         f"* H-B3 downside semibeta: MSE gain {out['H-B3']['gain']:.5f} (t {out['H-B3']['t']:.2f}) on {out['H-B3']['mse_bench']:.4f}"]
    for k in ("A4B", "A4"):
        a = out[k]
        L.append(f"* {k} realised skewness{' (unbanded, reported)' if k == 'A4' else ''}: slope {a['b']:.5f}, DK t {a['t']:.2f}, "
                 f"net {a['net_pct_yr']:.2f}%/yr, Sharpe {a['sharpe']:.2f}, {a['names']:.0f} names, {a['weeks']} weeks")
    return L


def dev():
    out = run(K.DEV, A4_DEV)
    fin = []
    if out["R6"]["h5"]["t"] >= 1.5 and out["R6"]["h22"]["gain"] >= 0:
        fin.append("R6")
    if out["H-B3"]["t"] >= 1.5:
        fin.append("H-B3")
    if out["A4B"]["t"] >= 1.5 and out["A4B"]["net_mean_bp"] > 0:
        fin.append("A4B")
    out["finalists"] = fin
    json.dump(out, open(os.path.join(HERE, "DEV2_RESULT.json"), "w"), indent=1, default=float)
    L = table(out, "development") + ["", f"**Finalists:** {', '.join(fin) if fin else 'none'}"]
    open(os.path.join(HERE, "DEV2_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


def read():
    lock = os.path.join(HERE, "OOS2_READ.lock")
    if os.path.exists(lock):
        raise SystemExit("already read: " + open(lock).read())
    fin = json.load(open(os.path.join(HERE, "DEV2_RESULT.json")))["finalists"]
    if not fin:
        raise SystemExit("no finalists: nothing to read")
    out = run(K.OOS, A.OOS)
    res = {}
    for k in fin:
        r = out[k]
        t = r["h5"]["t"] if k == "R6" else r["t"]
        ok = (r["h5"]["gain"] > 0 and r["h22"]["gain"] > 0) if k == "R6" else (r["gain"] > 0 if k == "H-B3" else r["net_mean_bp"] > 0)
        res[k] = {"p": float(norm.sf(t)), "ok_sign": ok}
    holm(res)
    for k in res:
        res[k]["pass"] = bool(res[k]["p_holm"] < 0.05 and res[k]["ok_sign"])
    at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    json.dump({"read_at": at, "finalists": fin, "stats": {k: out[k] for k in fin}, "results": res}, open(os.path.join(HERE, "OOS2_RESULT.json"), "w"),
              indent=1, default=float)
    open(lock, "w").write(f"read {at}\n")
    L = table({**out}, f"out-of-sample read (one read, {at})")
    L += ["", "Finalists only count; the rest is reported.", ""] + [
        f"* **{k}**: p one-sided {r['p']:.4f}, Holm {r['p_holm']:.4f}, {'**pass**' if r['pass'] else 'fail'}" for k, r in res.items()]
    open(os.path.join(HERE, "OOS2_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"dev": dev, "read": read}[sys.argv[1]]()
