"""Reproduction check of model.py: walk-forward for 2013 and 2014, seeds 0-2, compared with the saved gru60_D27_ic_es predictions."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import harness as H, model
D = H.load()
yrs = (2013, 2014)
p = H.walk_forward(model.fit_predict, seeds=(0, 1, 2), years=yrs, D=D)
ref = np.load(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), ".cache/tree/preds/Q1_seqnet/gru60_D27_ic_es.npy")).astype(np.float64)
out = {}
for y in yrs:
    rows = H.thursdays(D, y)
    a, b = np.nanmean(H.weekly_ic(p, D, rows)), np.nanmean(H.weekly_ic(ref, D, rows))
    m = np.isfinite(p[rows]) & np.isfinite(ref[rows])
    out[y] = dict(ic_model_py=round(float(a), 5), ic_saved=round(float(b), 5), max_abs_diff=float(np.abs(p[rows][m] - ref[rows][m]).max()))
print(json.dumps(out))
json.dump(out, open(os.path.join(HERE, "REPRO.json"), "w"), indent=1)
