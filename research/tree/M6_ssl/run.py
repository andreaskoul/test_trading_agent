"""python3 run.py name [name ...]: score named configurations (RESULTS.jsonl) and update STATE.json."""
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
    "ctrl_Z": dict(kind=None, base="Z"),
    "mae16_emb": dict(kind="mae", d=16, base=None),
    "mae16_embZ": dict(kind="mae", d=16, base="Z"),
    "con16_emb": dict(kind="con", d=16, base=None),
    "con16_embZ": dict(kind="con", d=16, base="Z"),
    "com16_emb": dict(kind="com", d=16, base=None),
    "com16_embZ": dict(kind="com", d=16, base="Z"),
    "com16_peerZ": dict(kind="com", d=16, base="Z", use_emb=False, peer=True),
    "ctrl_C": dict(kind=None, base="C"),
}
STATE = os.path.join(HERE, "STATE.json")


def note_state(name, res, plan, line):
    st = json.load(open(STATE))
    st["scored"] = sorted(set(st["scored"]) | {name})
    st["configurations_scored"] = len(st["scored"])
    st["plan"] = plan
    st["pending"] = [p for p in plan if p not in st["scored"]]
    st["status"] = "in progress"
    st["notes"].append(line)
    st["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(st, open(STATE, "w"), indent=1)


if __name__ == "__main__":
    D = load()
    log = os.path.join(HERE, "RESULTS.jsonl")
    plan = list(CONFIGS)
    for name in sys.argv[1:]:
        cfg = CONFIGS[name]
        t0 = time.time()
        pred = walk_forward(model.make(**cfg), seeds=(0, 1, 2), D=D)
        np.save(os.path.join(HERE, "pred_%s.npy" % name), pred.astype(np.float32))
        mins = (time.time() - t0) / 60
        res = score(pred, name, log, note="%s | %.1f min" % (json.dumps(cfg), mins), D=D)
        msg = "%s IC %.4f t %.2f min_year %.4f net %.1f%%/yr sharpe %.2f | %.1f min" % (
            name, res["ic"], res["ic_t"], res["min_year_ic"], res["decile_net_pct_per_year"], res["decile_net_sharpe"], mins)
        print(msg, {k: round(v, 3) for k, v in res["ic_by_year"].items()}, flush=True)
        note_state(name, res, plan, "scored " + msg)
