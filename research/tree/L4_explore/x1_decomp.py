"""Descriptive, after the X1 read (nothing here is a test): how much of the with-sleeve Sharpe comes from the gross-cap
scale-down alone? B0 scaled by the same c_t (and the same margin rule), with no sleeve. -> X1_DECOMP.json"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import x1 as X
P, _ = X.prices(); rf = X.ST.dtb3(); d = X.K.T.build()
X.K.RF, X.K.YEARS, X.K.GROSS_SIDE = rf, range(2020, 2026), 0.3
pred = np.load(os.path.join(X.K.QT, ".cache", "quant_trials", "sp500_tf_master_h5.npz"))["h5"].astype(np.float64)
F = X.fund_components(d, pred)
wt = json.load(open(os.path.join(HERE, "X1_DEV.json")))["weight"]["w_sleeve_per_core_unit"]
pos = {dt: i for i, dt in enumerate(P.index)}
G = np.array([F.gross_f.values[k] + wt * np.abs(X.sleeve_weights(P, pos[d["S"][int(t)]])).sum() for k, t in enumerate(F.t)])
c = np.minimum(1.0, X.FUND_GCAP / G)
scaled = c * (F.core.values + F.book.values) - np.maximum(c * F.net.values - 1, 0) * F.mrate.values
const = c.mean() * (F.core.values + F.book.values) - np.maximum(c.mean() * F.net.values - 1, 0) * F.mrate.values
wk = lambda v: np.asarray(v) * 7 / F.days.values
b0 = wk(F.total)
out = {"label": "2020-2025, descriptive after the read", "B0_scaled_by_c_t_no_sleeve": X.ann_stats(scaled, F.days),
       "B0_scaled_by_mean_c_no_sleeve": {**X.ann_stats(const, F.days), "mean_c": float(c.mean())},
       "lw2008_B0_scaled_vs_B0": X.lw_test(wk(scaled) * b0.std(ddof=1) / wk(scaled).std(ddof=1), b0)}
json.dump(out, open(os.path.join(HERE, "X1_DECOMP.json"), "w"), indent=1); print(json.dumps(out, indent=1))
