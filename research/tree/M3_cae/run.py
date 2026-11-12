"""Run one or more named configurations: python3 run.py name [name ...]. Each is logged to RESULTS.jsonl."""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from harness import load, walk_forward, score, increment  # noqa: E402
import model  # noqa: E402

CONFIGS = {
    "ca1_z5_k3": dict(chars_set="Z5", K=3, hidden=(16,)),
    "ca0_z5_k3": dict(chars_set="Z5", K=3, hidden=()),
    "ca1_c32_k3": dict(chars_set="C32", K=3, hidden=(32,)),
    "ca1_c32_k1": dict(chars_set="C32", K=1, hidden=(32,)),
    "ca1_c32_k5": dict(chars_set="C32", K=5, hidden=(32,)),
    "ca0_c32_k3": dict(chars_set="C32", K=3, hidden=()),
    "ca2_c32_k3": dict(chars_set="C32", K=3, hidden=(32, 16)),
    "ca1_c32_k3_alpha": dict(chars_set="C32", K=3, hidden=(32,), alpha=True),
    "ca1_c32_k3_ens5": dict(chars_set="C32", K=3, hidden=(32,), n_ens=5),
}

if __name__ == "__main__":
    D = load()
    log = os.path.join(HERE, "RESULTS.jsonl")
    for name in sys.argv[1:]:
        cfg = CONFIGS[name]
        t0 = time.time()
        pred = walk_forward(model.make(**cfg), seeds=(0, 1, 2), D=D)
        np.save(os.path.join(HERE, "pred_%s.npy" % name), pred.astype(np.float32))
        res = score(pred, name, log, note="%s | %.1f min" % (json.dumps(cfg), (time.time() - t0) / 60), D=D)
        print(name, "IC %.4f t %.2f min_year %.4f net %.1f%%/yr sharpe %.2f | %.1f min" % (
            res["ic"], res["ic_t"], res["min_year_ic"], res["decile_net_pct_per_year"], res["decile_net_sharpe"],
            (time.time() - t0) / 60), {k: round(v, 3) for k, v in res["ic_by_year"].items()}, flush=True)
