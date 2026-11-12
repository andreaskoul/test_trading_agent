"""Descriptive: % a year of the whole fund (200-session core 1.3x/0.7x + beta-hedged decile book) over the holdout
2020-2025, for the holdout predictions of the finalists and the MASTER 5-day reference. Same simulator as
research/sharpe/construct.py (S0 deciles). Nothing here is a test; the holdout was read once already.
"""
import json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "research", "sharpe"))
import construct as K
import smoothed_spread as SS
import harness as H
import holdout as HO
K.YEARS = range(2020, 2026)

def stats(df):
    yrs = df.days.sum() / 365.25
    wk = df.total * 7 / df.days
    v = np.cumprod(1 + df.total.values)
    dd = float((v / np.maximum.accumulate(np.concatenate([[1], v]))[1:] - 1).min())
    by = df.groupby("year").total.apply(lambda x: 100 * (np.prod(1 + x) - 1)).round(1).to_dict()
    return {"pct_per_year": 100 * (np.prod(1 + df.total) ** (1 / yrs) - 1), "sharpe": float(wk.mean() / wk.std() * 52 ** .5),
            "vol_pct": 100 * float(wk.std() * 52 ** .5), "worst_fall_pct": 100 * dd, "by_year": by,
            "spy_pct_per_year": 100 * (np.prod(1 + df.spy) ** (1 / yrs) - 1),
            "spy_by_year": df.groupby("year").spy.apply(lambda x: 100 * (np.prod(1 + x) - 1)).round(1).to_dict()}

d = K.T.build(); K.RF = K.ST.dtb3()
P = {"MASTER": np.load(os.path.join(K.QT, ".cache", "quant_trials", "sp500_tf_master_h5.npz"))["h5"].astype(np.float64)}
for f in ("X1_8p", "D_hgb_mh"):
    P[f] = np.load(os.path.join(ROOT, ".cache", "tree", "holdout_pred_finalists", f + ".npy")).astype(np.float64)
rows = np.array([t for t, *_ in K.ST.periods(d, K.YEARS)])
for k in list(P):
    P[k + "+smooth"] = SS.smooth(P[k], rows)
sec = K.sectors(d["names"]); panic = K.panic_flags(d); grp = np.zeros(len(sec), int)
out = {}
zero = np.full(d["r"].shape, np.nan)
for cost in (5e-4, 1e-4):
    for g in (0.6, 1.0):
        K.GROSS_SIDE = g / 2
        for k, p in P.items():
            out[f"{k}|gross {g}|{cost*1e4:.0f}bp"] = stats(K.run(d, p, "S0", cost, sec, grp, panic))
    out[f"core only|{cost*1e4:.0f}bp"] = stats(K.run(d, zero, "S0", cost, sec, grp, panic))
json.dump(out, open(os.path.join(HERE, "OOS_RETURNS.json"), "w"), indent=1, default=float)
for k, v in out.items():
    print(f"{k:34s} {v['pct_per_year']:5.1f}%/yr Sharpe {v['sharpe']:.2f} vol {v['vol_pct']:.1f} fall {v['worst_fall_pct']:.1f} | {v['by_year']}")
print("SPY", round(out['core only|5bp']['spy_pct_per_year'], 1), out['core only|5bp']['spy_by_year'])
