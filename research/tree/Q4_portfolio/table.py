"""Summary table for REPORT.md from RESULTS.jsonl and the saved weekly nets (adds the vol-matched paired difference:
candidate scaled ex post to its control's full-period vol, minus control, NW t 4 lags; a Sharpe-difference proxy)."""
import json
import os

import numpy as np

import lib

rows = [json.loads(l) for l in open(os.path.join(lib.HERE, "RESULTS.jsonl"))]
ctl = {r["signal"]: np.load(os.path.join(lib.PREDS, f"C_band_{r['signal']}.npy")) for r in rows}
print("| config | signal | net %/yr | Sharpe | Sharpe 13-16 | Sharpe 17-19 | vol %/yr | maxDD | maxDD at ctl vol | turn/wk | diff %/yr (t) | vol-matched diff %/yr (t) |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    n = np.load(os.path.join(lib.PREDS, f"{r['name']}.npy"))
    c = ctl[r["signal"]]
    k = c.std(ddof=1) / n.std(ddof=1)
    d = n * k - c
    t = lib.nw_t(d) if np.abs(d).sum() > 1e-12 else 0.0
    ddc = lib.max_dd(n * k)
    print(f"| {r['name']} | {r['signal']} | {r['net_pct_per_year']:+.2f} | {r['net_sharpe']:.2f} | {r['net_sharpe_2013_2016']:.2f} | "
          f"{r['net_sharpe_2017_2019']:.2f} | {r['vol_pct_per_year']:.1f} | {100*r['max_drawdown']:.1f}% | {100*ddc:.1f}% | "
          f"{100*r['turnover']:.1f}% | {r['vs_control_diff_pct_per_year']:+.2f} ({r['vs_control_t_nw4']:.2f}) | {52*100*d.mean():+.2f} ({t:.2f}) |")
