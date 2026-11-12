"""Branch M5 runner: python3 run.py NAME [NAME ...]. Skips names already in STATE.json "scored"; logs every score."""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import harness  # noqa: E402
import m5lib  # noqa: E402
import gnn  # noqa: E402

RES = os.path.join(HERE, "RESULTS.jsonl")
INC = os.path.join(HERE, "INCREMENT.jsonl")
STATE = os.path.join(HERE, "STATE.json")

REV = [0, 1, 2, 3, 4, 5]                 # C24 columns: rev1 rev5 rev21 erev1 erev5 erev21


def cat(*fns):
    def f(D):
        parts = [fn(D) for fn in fns]
        return np.concatenate([p[0] for p in parts], 2), parts[0][1]
    return f


def base(which):
    return lambda D: m5lib.base_design(D, which)


def peer(which, cols=None, gap=True, okfrom=None):
    def f(D):
        P, _ = m5lib.peer_design(D, which, cols=cols, gap=gap)
        return P, m5lib.base_design(D, okfrom or which)[1]
    return f


CONFIGS = {
    "R0_C24_fm": (lambda: m5lib.ridge(base("C24")), "control: FM ridge on C's 24 ranked characteristics, no peers"),
    "R1_peerrev_alone": (lambda: m5lib.ridge(peer("C24", REV)),
                         "peer features alone: cosine-weighted peer means and own-minus-peer gaps of raw/hedged returns 1,5,21; FM ridge"),
    "R2_Z5_peer": (lambda: m5lib.ridge(cat(base("Z5"), peer("Z5"), peer("C24", REV, okfrom="Z5"))),
                   "5 characteristics + their peer means/gaps + peer return means/gaps; FM ridge"),
    "R3_C24_peer": (lambda: m5lib.ridge(cat(base("C24"), peer("C24", None, gap=False), peer("C24", REV))),
                    "C24 + peer means of all 24 + gaps of the 6 return features; FM ridge"),
    "G0_mlp_C24": (lambda: gnn.make("C24", graph=False), "control: per-node MLP (H32, 1 layer, no edges), C24, 15 epochs"),
    "G1_sage_C24": (lambda: gnn.make("C24", graph=True), "GraphSAGE cosine-mean, 1 layer H32, C24, 15 epochs; same net as G0 plus edges"),
    "G2_gat_C24": (lambda: gnn.make("C24", graph=True, agg="gat"), "graph attention over 10 neighbours + self, 1 layer H32, C24"),
    "G3_sage2_C24": (lambda: gnn.make("C24", graph=True, L=2), "GraphSAGE 2 layers H32, C24"),
    "G4_mlp_Z5": (lambda: gnn.make("Z5", graph=False), "control: per-node MLP, 5 characteristics"),
    "G5_sage_Z5": (lambda: gnn.make("Z5", graph=True), "GraphSAGE 1 layer, 5 characteristics"),
}


def state_update(name, res, plan, note):
    s = json.load(open(STATE))
    if name not in s["scored"]:
        s["scored"].append(name)
    s["configurations_scored"] = len(s["scored"])
    s["plan"] = plan
    s["pending"] = [p for p in plan if p not in s["scored"]]
    s["status"] = "in progress" if s["pending"] else "scored"
    s["notes"].append(note)
    if s["best"] is None or res["ic"] > s["best"]["ic"]:
        s["best"] = {"name": name, "ic": res["ic"], "ic_t": res["ic_t"]}
    s["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(s, open(STATE, "w"), indent=1)


if __name__ == "__main__":
    D = harness.load()
    plan = list(CONFIGS)
    for name in sys.argv[1:]:
        s = json.load(open(STATE))
        if name in s["scored"]:
            print("skip", name)
            continue
        mk, note = CONFIGS[name]
        t0 = time.time()
        pred = harness.walk_forward(mk(), seeds=(0, 1, 2), D=D)
        np.save(os.path.join(HERE, "pred_%s.npy" % name), pred.astype(np.float32))
        res = harness.score(pred, name, RES, note=note, D=D)
        dt = time.time() - t0
        print(name, "IC %.4f t %.2f min %.4f net %.1f%%/yr sh %.2f  %.0fs" % (res["ic"], res["ic_t"], res["min_year_ic"],
              res["decile_net_pct_per_year"], res["decile_net_sharpe"], dt), {k: round(v, 3) for k, v in res["ic_by_year"].items()})
        state_update(name, res, plan, "%s scored: IC %.4f t %.2f (%.0fs). Next: remaining plan." % (name, res["ic"], res["ic_t"], dt))
