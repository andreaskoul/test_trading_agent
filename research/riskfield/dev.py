"""Risk-field research: the development statistics (PREREG.md §9) and the finalists.

    python research/riskfield/dev.py      # -> DEV_RESULT.json / DEV_RESULT.md (development periods only)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import alpha as A                                                                     # noqa: E402
import beta as B                                                                      # noqa: E402
import risk as K                                                                      # noqa: E402


def ewma_vs_m0(D, h, period):
    """Reported only: M0 against RiskMetrics (lambda 0.94 on close-to-close squared returns), on M0's sample."""
    r2 = D.r ** 2
    s = np.full(r2.shape, np.nan)
    acc = np.nanmean(r2[:22], 0)
    for t in range(D.T):
        x = r2[t]
        acc = np.where(np.isfinite(x), 0.94 * acc + 0.06 * x, acc)
        s[t] = acc
    regs = D.regressors("M0", h)
    mask = np.broadcast_to(D.stock, (D.T, D.N)) & np.all([np.isfinite(r) for r in regs], 0) & np.isfinite(s)
    y0, s0 = K.forecasts(D, regs, D.y[h], mask, h, period[1])
    F0 = np.exp(y0 + s0[:, None] / 2)
    L = K.qlike(D.rvbar[h], np.where(mask, s, np.nan)) - K.qlike(D.rvbar[h], F0)
    o = K.origins(D, h, period)
    L[~o] = np.nan
    daily = np.nanmean(np.where(np.isfinite(L).sum(1)[:, None] > 0, L, 0), 1)
    daily = np.where(np.isfinite(L).sum(1) > 0, np.nansum(L, 1) / np.maximum(np.isfinite(L).sum(1), 1), np.nan)
    daily[~o] = np.nan
    m, t, n = K.nw_t(daily, h + 5)
    return {"gain": m, "t": t, "days": n}


def main():
    D = K.Data()
    out = {"risk": {}, "reported": {}, "beta": {}, "alpha": {}}
    for name, (cand, bench, hl) in K.RTESTS.items():
        out["risk"][name] = {f"h{h}": K.compare(D, cand, bench, h, K.DEV, hl)[0] for h in K.HS}
        print(name, json.dumps(out["risk"][name]))
    for h in K.HS:
        out["reported"][f"MS_vs_M0_h{h}"] = K.compare(D, "MS", "M0", h, K.DEV)[0]
        out["reported"][f"M0_vs_EWMA_h{h}"] = ewma_vs_m0(D, h, K.DEV)
        out["reported"][f"N1placebo_vs_NB_h{h}"] = K.compare(D, "N1_placebo", "NB", h, K.DEV)[0]
    print(json.dumps(out["reported"], indent=1))
    Bt = B.build(D)
    for test in ("H-B1", "H-B2"):
        out["beta"][test] = B.compare(D, Bt, test, K.DEV)
        print(test, out["beta"][test])
    AD = A.build(A.DEV[1])
    for k in ("A1", "A2", "A3", "A2B", "A3B"):
        out["alpha"][k] = A.stats(AD, k, A.DEV)
        print(k, out["alpha"][k])
    fin = []
    for k, r in out["risk"].items():
        if r["h5"]["t"] >= 1.5 and r["h22"]["gain"] >= 0:
            fin.append(k)
    for k, r in out["beta"].items():
        if r["t"] >= 1.5:
            fin.append(k)
    for k, r in out["alpha"].items():
        if r["t"] >= 1.5 and r["net_mean_bp"] > 0:
            fin.append(k)
    out["finalists"] = fin
    out["run_at"] = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    json.dump(out, open(os.path.join(HERE, "DEV_RESULT.json"), "w"), indent=1, default=float)
    L = ["# Risk-field research: development results", "", f"Run {out['run_at']}. Development periods only. "
         "Gain = benchmark loss minus candidate loss (positive = better).", "",
         "| Test | h=5 gain | h=5 t | h=22 gain | h=22 t | names/day | finalist |", "|---|---:|---:|---:|---:|---:|---|"]
    for k, r in out["risk"].items():
        L.append(f"| {k} | {r['h5']['gain']:.5f} | {r['h5']['t']:.2f} | {r['h22']['gain']:.5f} | {r['h22']['t']:.2f} | "
                 f"{r['h5']['names_per_day']:.0f} | {'yes' if k in fin else 'no'} |")
    L += ["", "| Beta test | MSE gain | t | weeks | benchmark MSE | finalist |", "|---|---:|---:|---:|---:|---|"]
    for k, r in out["beta"].items():
        L.append(f"| {k} | {r['gain']:.5f} | {r['t']:.2f} | {r['weeks']} | {r['mse_bench']:.4f} | {'yes' if k in fin else 'no'} |")
    L += ["", "| Alpha test | slope | DK t | net bp/week | net %/yr | Sharpe | names | finalist |", "|---|---:|---:|---:|---:|---:|---:|---|"]
    for k, r in out["alpha"].items():
        L.append(f"| {k} | {r['b']:.5f} | {r['t']:.2f} | {r['net_mean_bp']:.1f} | {r['net_pct_yr']:.2f} | {r['sharpe']:.2f} | "
                 f"{r['names']:.0f} | {'yes' if k in fin else 'no'} |")
    L += ["", "Reported (not tested):", ""] + [f"* {k}: gain {v['gain']:.5f}, t {v['t']:.2f}" for k, v in out["reported"].items()]
    L += ["", f"**Finalists:** {', '.join(fin) if fin else 'none'}"]
    open(os.path.join(HERE, "DEV_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
