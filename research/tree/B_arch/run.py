"""Score one named configuration: python3 run.py <name>. Every run appends a line to RESULTS.jsonl."""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import harness  # noqa: E402
from arch import make  # noqa: E402

CONFIGS = {
    # round 1: one cheap try per family
    "mlp_Z":            dict(),
    "gru_e20":          dict(chars=False, temporal="gru", L=20),
    "cnn_e60":          dict(chars=False, temporal="cnn", L=60),
    "tfm_e60":          dict(chars=False, temporal="tfm", L=60),
    "mlp_Z_xattn":      dict(xattn=True),
    "mlp_Z_gate":       dict(gate=True),
    "cnn_e60_Z_xattn":  dict(temporal="cnn", L=60, xattn=True),
}
CONFIGS.update(json.load(open(os.path.join(HERE, "round2.json"))) if os.path.exists(os.path.join(HERE, "round2.json")) else {})

if __name__ == "__main__":
    name = sys.argv[1]
    cfg = CONFIGS[name]
    years = harness.VAL_YEARS
    seeds = (0, 1, 2)
    if len(sys.argv) > 2 and sys.argv[2] == "smoke":          # timing only, not scored, not logged
        t0 = time.time()
        D = harness.load()
        fp = make(**cfg)
        te, rows = harness.train_end(D, 2019), harness.thursdays(D, 2019)
        p = fp(D, te, rows, 0)
        print(name, "one 2019 fit: %.1fs" % (time.time() - t0), p.shape)
        sys.exit(0)
    t0 = time.time()
    pred = harness.walk_forward(make(**cfg), seeds=seeds)
    mins = (time.time() - t0) / 60
    res = harness.score(pred, name, os.path.join(HERE, "RESULTS.jsonl"), note=json.dumps(cfg, sort_keys=True) + " | %.1f min" % mins)
    print(json.dumps(res))
