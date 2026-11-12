"""Diagnostics (no new configurations): gross vs net for every scored row; for the best (mvnl_nt_trees) and its control,
the gross-return split by residual-vol tercile of names (size proxy) and net by high- vs low-volatility weeks."""
import json
import os

import numpy as np

import lib
import run

D = lib.harness.load()
S = lib.signals(D)
R = {k: lib.val_rows(D, v) for k, v in S.items()}
res = [json.loads(l) for l in open(os.path.join(lib.HERE, "RESULTS.jsonl"))]
out = {}
for r in res:
    sig, sp = r["signal"], r["spec"]
    rows = R[sig]
    W = lib.m1.build("decile", S[sig], D, rows) if sp["target"] == "decile" else lib.build(sp, S[sig], D, rows)[0]
    sim = lib.simulate(W, D, rows)
    g, n = sim["gross"][1:], sim["net"][1:]
    assert abs(n.mean() * 52 * 100 - r["net_pct_per_year"]) < 1e-9, r["name"]
    out[r["name"]] = {"gross_pct": 52 * 100 * g.mean(), "gross_sharpe": g.mean() / g.std(ddof=1) * np.sqrt(52),
                      "cost_pct": 52 * 100 * sim["cost"][1:].mean(), "net_pct": r["net_pct_per_year"], "turn": r["turnover"]}
    if r["name"] in ("mvnl_nt_trees", "C_band_trees"):
        terc = {0: [], 1: [], 2: []}
        for j, t in enumerate(rows[1:], 1):
            v = lib.resid_vol_all = lib.m1.resid_vol(D, t)
            m = W[j] != 0
            q = np.nanquantile(v[lib.mask(S[sig], D, t)], [1 / 3, 2 / 3])
            k = np.digitize(v, q)
            y = np.nan_to_num(D["y5"][t])
            for c in range(3):
                terc[c].append(float((W[j] * (k == c)) @ y))
        out[r["name"]]["gross_pct_by_residvol_tercile"] = {c: 52 * 100 * np.mean(terc[c]) for c in range(3)}
        # high- vs low-vol weeks: equal-weight cross-sectional mean residual vol at t (known at t), median split
        wv = np.array([np.nanmean(lib.m1.resid_vol(D, t)[D["elig"][t]]) for t in rows[1:]])
        hi = wv > np.median(wv)
        out[r["name"]]["net_pct_hi_vol_weeks"] = 52 * 100 * n[hi].mean()
        out[r["name"]]["net_pct_lo_vol_weeks"] = 52 * 100 * n[~hi].mean()
        out[r["name"]]["sharpe_hi_vol_weeks"] = n[hi].mean() / n[hi].std(ddof=1) * np.sqrt(52)
        out[r["name"]]["sharpe_lo_vol_weeks"] = n[~hi].mean() / n[~hi].std(ddof=1) * np.sqrt(52)
json.dump(out, open(os.path.join(lib.HERE, "DIAG.json"), "w"), indent=1)
for k, v in out.items():
    print(k, {a: (round(b, 2) if isinstance(b, float) else {c: round(d, 2) for c, d in b.items()}) for a, b in v.items()})
