"""Risk-field research: the single out-of-sample read (PREREG.md §9).

    python research/riskfield/oos.py read     # ONCE; refuses if OOS_READ.lock exists; writes OOS_RESULT.md/json

Finalists come from DEV_RESULT.json. Holm across all finalists (§§4-7); P1 and P2 are a second family (§8).
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
import books as BK                                                                    # noqa: E402
import risk as K                                                                      # noqa: E402


def holm(res, key="p"):
    ps = sorted((r[key], k) for k, r in res.items())
    run = 0.0
    for i, (p, k) in enumerate(ps):
        run = max(run, min(1.0, (len(ps) - i) * p))
        res[k]["p_holm"] = run


def best_models(D, Bt, res):
    """The mechanical winners of §8, and their OOS forecasts (T x N)."""
    risk_pass = [k for k in K.RTESTS if k in res and k != "N1" and res[k]["pass"]]
    rk = max(risk_pass, key=lambda k: res[k]["h5"]["gain"]) if risk_pass else None
    cand, _, hl = K.RTESTS[rk] if rk else ("MS", None, None)
    regs = D.regressors(cand, 5)
    mask = np.broadcast_to(D.stock, (D.T, D.N)) & np.all([np.isfinite(r) for r in regs], 0)
    yh, s2 = K.forecasts(D, regs, D.y[5], mask, 5, K.OOS[1], hl)
    sig = np.sqrt(np.exp(yh + s2[:, None] / 2))
    if res.get("H-B2", {}).get("pass"):
        bk = "B2"
    elif res.get("H-B1", {}).get("pass"):
        bk = "B1"
    else:
        bk = "B0"
    if bk == "B0":
        bb = Bt["B0"]
    else:
        regs = [Bt["b21"], Bt["b63"], Bt["ols"]] + ([D.field("text", Bt["b63"])] if bk == "B2" else [])
        m = np.broadcast_to(D.stock, (D.T, D.N)) & Bt["thu"][:, None] & np.all([np.isfinite(r) for r in regs], 0)
        bb, _ = K.forecasts(D, regs, Bt["tgt"], m, 21, K.OOS[1])
    return rk or "MS", sig, bk, bb


def read():
    lock = os.path.join(HERE, "OOS_READ.lock")
    if os.path.exists(lock):
        raise SystemExit("already read: " + open(lock).read())
    dev = json.load(open(os.path.join(HERE, "DEV_RESULT.json")))
    fin = dev["finalists"]
    D = K.Data()
    Bt = BT.build(D)
    res = {}
    AD = None
    for k in fin:
        if k in K.RTESTS:
            c, b, hl = K.RTESTS[k]
            r = {f"h{h}": K.compare(D, c, b, h, K.OOS, hl)[0] for h in K.HS}
            r["p"] = float(norm.sf(r["h5"]["t"]))
            r["ok_sign"] = r["h5"]["gain"] > 0 and r["h22"]["gain"] > 0
        elif k.startswith("H-B"):
            r = BT.compare(D, Bt, k, K.OOS)
            r["p"] = float(norm.sf(r["t"]))
            r["ok_sign"] = r["gain"] > 0
        else:
            AD = AD if AD is not None else A.build(A.OOS[1])
            r = A.stats(AD, k, A.OOS)
            r["p"] = float(norm.sf(r["t"]))
            r["ok_sign"] = r["net_mean_bp"] > 0
        res[k] = r
    if res:
        holm(res)
    for k, r in res.items():
        r["pass"] = bool(r["p_holm"] < 0.05 and r["ok_sign"])
    rk, sig, bk, bb = best_models(D, Bt, res)
    P = {}
    if bk != "B0" or rk != "MS" or True:
        books = BK.run(D, bb, sig, K.OOS)
        P = BK.p_stats(books)
        P["P1"]["p"] = float(norm.sf(P["P1"]["t"])) if bk != "B0" else None
        P["P2"]["p"] = float(norm.sf(P["P2"]["t"]))
        fam = {k: v for k, v in P.items() if v["p"] is not None}
        holm(fam)
        P["best_risk"], P["best_beta"] = rk, bk
    at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    out = {"read_at": at, "finalists": fin, "results": res, "books": P}
    json.dump(out, open(os.path.join(HERE, "OOS_RESULT.json"), "w"), indent=1, default=float)
    open(lock, "w").write(f"read {at}\n")
    L = ["# Risk-field research: out-of-sample read (one read)", "", f"Read {at}. Origins 2020-01-02 .. 2025-12-31.", "",
         "| Test | statistic | t | p one-sided | p Holm | pass |", "|---|---|---:|---:|---:|---|"]
    for k, r in res.items():
        if k in K.RTESTS:
            st = f"h5 gain {r['h5']['gain']:.5f} (t {r['h5']['t']:.2f}); h22 gain {r['h22']['gain']:.5f} (t {r['h22']['t']:.2f})"
            t = r["h5"]["t"]
        elif k.startswith("H-B"):
            st, t = f"MSE gain {r['gain']:.5f} on {r['mse_bench']:.4f}", r["t"]
        else:
            st, t = f"net {r['net_pct_yr']:.2f}%/yr, Sharpe {r['sharpe']:.2f}", r["t"]
        L.append(f"| {k} | {st} | {t:.2f} | {r['p']:.4f} | {r['p_holm']:.4f} | {'**yes**' if r['pass'] else 'no'} |")
    if P:
        L += ["", f"Consequences (best risk model {P['best_risk']}, best beta {P['best_beta']}):", "",
              f"* P1 hedge: squared-return gain {P['P1']['gain']:.2e} (t {P['P1']['t']:.2f}), p Holm {P['P1'].get('p_holm')}; "
              + "; ".join(f"{k} weekly sd {v['sd_base_pct_wk']:.3f}% -> {v['sd_p1_pct_wk']:.3f}%" for k, v in P["P1"]["books"].items()),
              f"* P2 inverse-vol weights: Sharpe {P['P2']['sharpe_iv']:.2f} vs {P['P2']['sharpe_eq']:.2f} (t {P['P2']['t']:.2f}), "
              f"net {P['P2']['net_pct_yr_iv']:.2f} vs {P['P2']['net_pct_yr_eq']:.2f} %/yr, p Holm {P['P2'].get('p_holm')}"]
    open(os.path.join(HERE, "OOS_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__" and sys.argv[1:] == ["read"]:
    read()
