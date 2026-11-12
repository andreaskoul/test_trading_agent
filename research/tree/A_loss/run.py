"""Score named configurations: python3 run.py name1 name2 ...   (every scored configuration is appended to RESULTS.jsonl)"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import harness  # noqa: E402
import losslib  # noqa: E402

CONFIGS = {
    # round 1: one objective each, same model, same features, same optimiser
    "mse_raw": dict(loss="mse_raw"),
    "mse_rank": dict(loss="mse_rank"),
    "mse_gauss": dict(loss="mse_gauss"),
    "huber_z": dict(loss="huber"),
    "ic_gauss": dict(loss="ic"),
    "listmle": dict(loss="listmle"),
    "softmax_ce": dict(loss="softmax_ce"),
    "pairwise": dict(loss="pairwise"),
    "cls_quintile": dict(loss="cls"),
    "spread": dict(loss="spread"),
    "spread_sharpe": dict(loss="spread_sharpe"),
    "ic_sharpe": dict(loss="ic_sharpe"),
}
CONFIGS.update(json.load(open(os.path.join(HERE, "extra.json"))) if os.path.exists(os.path.join(HERE, "extra.json")) else {})

if __name__ == "__main__":
    D = harness.load()
    for name in sys.argv[1:]:
        cfg = CONFIGS[name]
        t0 = time.time()
        pred = harness.walk_forward(losslib.make(**cfg), seeds=(0, 1, 2), D=D)
        secs = time.time() - t0
        r = harness.score(pred, name, os.path.join(HERE, "RESULTS.jsonl"), note=json.dumps(cfg) + f" | {secs:.0f}s", D=D)
        print(name, f"{secs:.0f}s ic={r['ic']:.4f} t={r['ic_t']:.2f} dec={r['decile_net_pct_per_year']:.2f}",
              {k: round(v, 3) for k, v in r["ic_by_year"].items()}, flush=True)
