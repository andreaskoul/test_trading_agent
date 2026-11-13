"""Score one configuration: python3 run.py <name> [smoke].

Before scoring: the name and spec are appended to STATE.json "plan" and "pending". After: RESULTS.jsonl line, predictions
saved as float32 to .cache/tree/preds/Q1_seqnet/<name>.npy, STATE.json updated (scored, best by Amendment 2's rule).
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
sys.path.insert(0, TREE)
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import harness  # noqa: E402

STATE = os.path.join(HERE, "STATE.json")
RES = os.path.join(HERE, "RESULTS.jsonl")
PRED = os.path.join(ROOT, ".cache", "tree", "preds", "Q1_seqnet")
CONFIGS = json.load(open(os.path.join(HERE, "configs.json")))


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rd():
    return json.load(open(STATE))


def wr(s):
    s["updated"] = now()
    tmp = STATE + ".tmp"
    json.dump(s, open(tmp, "w"), indent=1)
    os.replace(tmp, STATE)


def build(name):
    cfg = dict(CONFIGS[name])
    if cfg.get("model_py"):                                   # the deliverable itself, research/tree/Q1_seqnet/model.py
        import importlib.util
        sp = importlib.util.spec_from_file_location("q1_model", os.path.join(HERE, "model.py"))
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        return m.fit_predict
    if cfg.pop("control", False):
        import importlib.util
        sp = importlib.util.spec_from_file_location("b_model", os.path.join(TREE, "B_arch", "model.py"))
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        return m.fit_predict
    cfg.pop("spec", None)
    cfg.pop("seeds", None)
    from seq import make
    return make(**cfg)


def _nm(x):
    return x["name"] if isinstance(x, dict) else str(x).split(":")[0].strip()


def sync(s):
    """Rebuild scored/best from RESULTS.jsonl (the record), so a reformatted STATE.json cannot lose anything."""
    rows = [json.loads(l) for l in open(RES)] if os.path.exists(RES) else []
    det = []
    for r in rows:
        yp = int(sum(v > 0 for v in r["ic_by_year"].values()))
        det.append(dict(name=r["name"], ic=round(r["ic"], 5), ic_t=round(r["ic_t"], 3), years_positive=yp,
                        decile_net_pct_per_year=round(r["decile_net_pct_per_year"], 2)))
    s["scored"] = [d["name"] for d in det]
    s["scored_detail"] = det
    s["configurations_scored"] = len(det)
    ok = [d for d in det if d["years_positive"] >= 5]
    s["best"] = max(ok, key=lambda d: d["ic"]) if ok else None
    s["pending"] = [p for p in s["pending"] if _nm(p) not in s["scored"]]
    return s


if __name__ == "__main__":
    name = sys.argv[1]
    spec = CONFIGS[name].get("spec", json.dumps(CONFIGS[name]))
    if len(sys.argv) > 2 and sys.argv[2] == "smoke":            # timing only, never scored or logged
        D = harness.load()
        fp = build(name)
        y = int(sys.argv[3]) if len(sys.argv) > 3 else 2019
        t0 = time.time()
        p = fp(D, harness.train_end(D, y), harness.thursdays(D, y), 0)
        print(name, "one %d fit: %.1fs" % (y, time.time() - t0), getattr(fp, "log", ""))
        sys.exit(0)
    s = rd()
    s = sync(s)
    if name in s["scored"]:
        print("already scored:", name)
        sys.exit(0)
    if not any(p.startswith(name + ":") for p in s["plan"]):
        s["plan"].append(f"{name}: {spec}")
    if name not in [_nm(p) for p in s["pending"]]:
        s["pending"].append(name)
    s["status"] = "running"
    wr(s)
    t0 = time.time()
    D = harness.load()
    fp = build(name)
    seeds = tuple(CONFIGS[name].get("seeds", (0, 1, 2)))
    pred = harness.walk_forward(fp, seeds=seeds, D=D)
    mins = (time.time() - t0) / 60
    res = harness.score(pred, name, RES, note=f"{spec} | {mins:.1f} min", D=D)
    os.makedirs(PRED, exist_ok=True)
    np.save(os.path.join(PRED, name + ".npy"), pred.astype(np.float32))
    if getattr(fp, "log", None):
        with open(os.path.join(HERE, f"log_{name}.json"), "w") as f:
            json.dump(fp.log, f)
    s = sync(rd())
    yp = int(sum(v > 0 for v in res["ic_by_year"].values()))
    s["best_rule"] = "Amendment 2: highest development mean IC among configurations positive in >= 5 of 7 years"
    s["notes"].append(f"{now()} scored {name}: IC {res['ic']:.4f} t {res['ic_t']:.2f} {yp}/7 yrs, {mins:.1f} min; best so far {s['best']['name'] if s['best'] else None}")
    wr(s)
    print(json.dumps(res))
