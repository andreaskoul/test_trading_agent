import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import harness as h, model as md
YRS = (2017, 2018, 2019); LOG = os.path.join(HERE, "RESULTS.jsonl")
D = h.load()
cfgs = {
 "N3_c2a_rankavg_id21": (md.rank_avg({"id21": -0.2}, 0.8), "config2: 0.8 MASTER rank - 0.2 rank(id21), weights fixed in advance"),
 "N3_c2b_rankavg_id21_tow": (md.rank_avg({"id21": -0.1, "on21_minus_id21": 0.1}, 0.8), "config2: 0.8 MASTER - 0.1 id21 + 0.1 (on21-id21), fixed"),
 "N3_c3a_ridge4": (md.linear(["id21", "on21_minus_id21", "id5", "on21"], "ridge"), "config3: pooled ridge of y5 rank on MASTER rank + 4 feature ranks, Thursdays 2016..train_end"),
 "N3_c3c_anchoredfm2": (md.anchored_fm(["id21", "on21_minus_id21"]), "config3: MASTER coef fixed at its 2013..train_end mean IC; FM coefs of the 2 selected features on the residual y rank"),
 "N3_c3b_fm4": (md.linear(["id21", "on21_minus_id21", "id5", "on21"], "fm"), "config3: Fama-MacBeth mean of weekly OLS, same 5 regressors"),
}
only = sys.argv[1:] or list(cfgs)
for name in only:
    fp, note = cfgs[name]
    md._C.pop("coefs", None)
    pred = h.walk_forward(fp, seeds=(0, 1, 2), years=YRS, D=D)
    r = h.increment(pred, name, LOG, note=note, D=D, years=YRS)
    print(name, json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k not in ("note", "at")}))
    if "coefs" in md._C: print("  coefs (te, kind, [master, feats]):", md._C["coefs"][::3])
