"""Score the declared Q7 configurations in order (STATE.json plan). python run.py [names...]"""
import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "3")
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import model as M  # noqa: E402

H = M.harness
LOG = os.path.join(HERE, "RESULTS.jsonl")
PRED = os.path.join(H.ROOT, ".cache", "tree", "preds", "Q7_features")
STATE = os.path.join(HERE, "STATE.json")
NOTES = {"ref_control": "declared control: D_ensembles/model.py unchanged (HGB, D 27 inputs, 5-session rank target)",
         "ref_mh": "second reference: finalists/D_hgb_mh form (D 27 inputs, rank average of HGB at 3/5/10/20)",
         "F1": "D trees + 9 industry-relative / industry-momentum / earnings-masked reversal inputs, 5-session target",
         "F2": "F1 inputs on the multi-horizon target (3/5/10/20 rank average)",
         "H1": "D inputs; target horizon by FINRA share-volume tercile (low 20, mid 10, high 5)"}
CFG = {"ref_control": "ref", "ref_mh": "ref_mh", "F1": "F1", "F2": "F2", "H1": "H1"}
NEXT = ["ref_control", "ref_mh", "F1", "F2", "H1"]


def covered_mask(D):
    ind, _, _ = M.load_inputs(D)
    return ind >= 0


def restrict(p, cov):
    q = p.copy()
    q[:, ~cov] = np.nan
    return q


def update_state(name, res, inc):
    s = json.load(open(STATE))
    if name not in s["scored"]:
        s["scored"].append(name)
    s["pending"] = [x for x in s["pending"] if x != name]
    s["configurations_scored"] = len(s["scored"])
    rows = [json.loads(line) for line in open(LOG)]
    full = {r["name"]: r for r in rows if "ic_by_year" in r and "increment" not in r}
    cand = [r for r in full.values() if sum(v > 0 for v in r["ic_by_year"].values()) >= 5]
    if cand:
        b = max(cand, key=lambda r: r["ic"])
        s["best"] = {"name": b["name"], "ic": b["ic"], "ic_t": b["ic_t"], "decile_net_pct_per_year": b["decile_net_pct_per_year"],
                     "decile_net_sharpe": b["decile_net_sharpe"], "rule": "highest development mean IC among configurations positive in >= 5 of 7 years"}
    nxt = s["pending"][0] if s["pending"] else "diagnostics, model.py, REPORT.md"
    msg = f"scored {name}: IC {res['ic']:.4f} (t {res['ic_t']:.2f}), net {res['decile_net_pct_per_year']:.2f}%/yr"
    if inc:
        msg += f", increment vs ref_control {inc['increment']:+.4f} (NW t {inc['increment_t']:.2f})"
    s["notes"].append(msg + f"; next: {nxt}")
    s["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(s, open(STATE, "w"), indent=1)


def run(name, D):
    t0 = time.time()
    pred = H.walk_forward(M.make(CFG[name]), seeds=(0, 1, 2), D=D)
    os.makedirs(PRED, exist_ok=True)
    np.save(os.path.join(PRED, f"{name}.npy"), pred.astype(np.float32))
    sec = int(time.time() - t0)
    res = H.score(pred, name, LOG, note=f"{NOTES[name]} | {sec}s", D=D)
    inc = None
    if name != "ref_control":
        base = np.load(os.path.join(PRED, "ref_control.npy")).astype(np.float64)
        inc = H.increment(pred, f"{name}_vs_ref_control", LOG, note="paired weekly IC difference vs ref_control", D=D, base=base)
        if name in ("F2",):
            mh = np.load(os.path.join(PRED, "ref_mh.npy")).astype(np.float64)
            H.increment(pred, f"{name}_vs_ref_mh", LOG, note="paired weekly IC difference vs ref_mh", D=D, base=mh)
        if name in ("F1", "F2"):
            cov = covered_mask(D)
            for bn in (["ref_control"] + (["ref_mh"] if name == "F2" else [])):
                b = np.load(os.path.join(PRED, f"{bn}.npy")).astype(np.float64)
                H.increment(restrict(pred, cov), f"{name}_vs_{bn}_gics_covered", LOG,
                            note="declared leak diagnostic: candidate and reference restricted to names with a GICS code",
                            D=D, base=restrict(b, cov))
    update_state(name, res, inc)
    print(name, json.dumps({k: res[k] for k in ("ic", "ic_t", "ic_by_year", "decile_net_pct_per_year")}), inc and inc["increment"], flush=True)


if __name__ == "__main__":
    D = H.load()
    for n in (sys.argv[1:] or NEXT):
        run(n, D)
