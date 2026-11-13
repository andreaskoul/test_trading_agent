"""Score Q2_xsattn configurations with the STATE.json protocol.   python run.py name [name ...]"""
import contextlib
import fcntl
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from model import make  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
PRED = os.path.join(ROOT, ".cache", "tree", "preds", "Q2_xsattn")
STATE = os.path.join(HERE, "STATE.json")
LOG = os.path.join(HERE, "RESULTS.jsonl")   # absolute: harness.score appends to this path

# name -> (config overrides, one-line spec, control name)
CONFIGS = {
    "mlp_base": (dict(), "27 ranked inputs, token MLP d64 depth2, 1 FF block (no cross-name), 1 head, IC loss; ablation for sab/isab/pool/fgate", None),
    "mlp_isab": (dict(xs="isab"), "mlp_base + ISAB cross-name attention (16 induced points, 4 heads) before the FF block", "mlp_base"),
    "mlp_sab": (dict(xs="sab"), "mlp_base + full self-attention over the ~500 names before the FF block", "mlp_base"),
    "mlp_pool": (dict(xs="pool"), "mlp_base + mean-pooled cross-section context (DeepSets) before the FF block", "mlp_base"),
    "moe_unif": (dict(K=4, gate="uniform"), "mlp_base with 4 expert heads averaged uniformly; ablation for moe_gate", None),
    "moe_gate": (dict(K=4, gate="state"), "4 expert heads gated by softmax over 7 causal market-state numbers", "moe_unif"),
    "mlp_fgate": (dict(fgate=True), "mlp_base + MASTER market-guided input gate (27 * softmax(W state))", "mlp_base"),
    "hist_base": (dict(hist=True), "mlp_base + last 60 standardised daily hedged returns as a token input; ablation for hist_isab/hist_sab", None),
    "hist_isab": (dict(hist=True, xs="isab"), "hist_base + ISAB cross-name attention", "hist_base"),
    "hist_sab": (dict(hist=True, xs="sab"), "hist_base + full cross-name self-attention (MASTER-like: names attend on return-history embeddings)", "hist_base"),
    # round 2 (exploitation around the best round-1 cells)
    "moe_sab": (dict(K=4, xs="sab"), "moe_unif + full cross-name self-attention", "moe_unif"),
    "moe_unif_listnet": (dict(K=4, loss="listnet"), "moe_unif with ListNet softmax cross-entropy loss", None),
    "moe_unif_mse": (dict(K=4, loss="mse"), "moe_unif with squared error on the standardised rank", None),
    "moe_unif_na": (dict(K=4, na=True), "moe_unif + 22 missing-value indicators (coordinator note 3)", None),
    "moe_unif_d128": (dict(K=4, d=128, depth=3), "moe_unif wider and deeper: d128, depth 3", None),
    "moe_sab_na_inner3": (dict(K=4, xs="sab", na=True, inner=3), "moe_sab + na, 3 inner seeds per fit (9-net ensemble per year)", "moe_unif_na_inner3"),
    "moe_unif_na_inner3": (dict(K=4, na=True, inner=3), "moe_unif + na, 3 inner seeds per fit; ablation for moe_sab_na_inner3", None),
    # round 3: the cross-name module on the best network, then the nominated pair with seeds 0-9 (coordinator note 2)
    "d128_sab": (dict(K=4, d=128, depth=3, xs="sab"), "moe_unif_d128 + full cross-name self-attention", "moe_unif_d128"),
    "d128_pool": (dict(K=4, d=128, depth=3, xs="pool"), "moe_unif_d128 + mean-pooled cross-section context", "moe_unif_d128"),
}
SEEDS10 = tuple(range(10))
# name_s10 -> base name: the same configuration re-scored with walk_forward seeds 0..9 (extra logged configurations)
S10 = {"moe_unif_d128_s10": "moe_unif_d128", "d128_sab_s10": "d128_sab", "d128_pool_s10": "d128_pool"}
for _k, _v in S10.items():
    _o, _sp, _c = CONFIGS[_v]
    CONFIGS[_k] = (_o, _sp + "; walk_forward seeds 0-9", (_c + "_s10") if _c else None)


@contextlib.contextmanager
def locked():
    with open(STATE + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)


def state():
    with open(STATE) as f:
        return json.load(f)


def save(s):
    s["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(STATE, "w") as f:
        json.dump(s, f, indent=1)


def run(name):
    over, spec, ctrl = CONFIGS[name]
    with locked():
        s = state()
        if any(x["name"] == name for x in s["scored"]):
            print("already scored", name)
            return
        if not any(p.startswith(name + ":") for p in s["plan"]):
            s["plan"].append(f"{name}: {spec}")
        if name not in s["pending"]:
            s["pending"].append(name)
        s["status"] = "running"
        save(s)
    t0 = time.time()
    fp = make(**over)
    pred = H.walk_forward(fp, seeds=SEEDS10 if name in S10 else (0, 1, 2))
    res = H.score(pred, name, LOG, note=spec + (f"; control {ctrl}" if ctrl else ""))
    os.makedirs(PRED, exist_ok=True)
    np.save(os.path.join(PRED, f"{name}.npy"), pred.astype(np.float32))
    eps = [x["epochs"] for x in fp.log]
    with locked():
        _record(name, res, ctrl, over, eps, t0)
    print(json.dumps(res), flush=True)


def _record(name, res, ctrl, over, eps, t0):
    s = state()
    s["pending"] = [p for p in s["pending"] if p != name]
    yp = sum(v > 0 for v in res["ic_by_year"].values())
    s["scored"].append(dict(name=name, ic=round(res["ic"], 5), ic_t=round(res["ic_t"], 2), years_pos=int(yp),
                            decile_net=round(res["decile_net_pct_per_year"], 2), control=ctrl, config=over,
                            mean_epochs=round(float(np.mean(eps)), 1), minutes=round((time.time() - t0) / 60, 1)))
    s["configurations_scored"] = len(s["scored"])
    elig = [x for x in s["scored"] if x["years_pos"] >= 5]
    if elig:
        b = max(elig, key=lambda x: x["ic"])
        s["best"] = dict(name=b["name"], ic=b["ic"], years_pos=b["years_pos"])
    s["notes"].append(f"scored {name}: IC {res['ic']:.4f} t {res['ic_t']:.2f} {yp}/7 years, {res['decile_net_pct_per_year']:.1f}%/yr net, "
                      f"mean epochs {np.mean(eps):.1f}, {(time.time() - t0) / 60:.1f} min; next: see pending")
    save(s)


if __name__ == "__main__":
    for n in sys.argv[1:]:
        run(n)
