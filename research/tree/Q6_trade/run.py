"""Score the declared Q6 configurations (STATE.json "pending"), one RESULTS.jsonl row each.

    OMP_NUM_THREADS=3 nohup python research/tree/Q6_trade/run.py > research/tree/Q6_trade/run.log 2>&1 &
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import lib  # noqa: E402

HERE = lib.HERE
STATE = os.path.join(HERE, "STATE.json")
RESULTS = os.path.join(HERE, "RESULTS.jsonl")
THETA = {"T4": 0.25, "T5": 0.5, "T6": 0.75}
ORDER = ("C0", "C1", "C2", "T1", "T2", "T3", "T4", "T5", "T6")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def state_update(name, row, nxt):
    s = json.load(open(STATE))
    if name in s["pending"]:
        s["pending"].remove(name)
    if name not in s["scored"]:
        s["scored"].append(name)
    s["configurations_scored"] = len(s["scored"])
    s["notes"].append(f"scored {name} (net Sharpe sqrt $10M {row['net_sharpe']:.3f}, flat 5bp {row['net_sharpe_flat5']:.3f}); next: {nxt}")
    s["updated"] = now()
    json.dump(s, open(STATE, "w"), indent=1)


def main():
    os.makedirs(lib.PREDS, exist_ok=True)
    D = lib.harness.load()
    S = lib.signals(D)
    st = json.load(open(STATE))
    pending = list(st["pending"])
    done = {json.loads(l)["name"]: json.loads(l) for l in open(RESULTS)} if os.path.exists(RESULTS) else {}
    for sig in ("trees", "ipca", "master"):
        todo = [c for c in ORDER if f"{c}_{sig}" in pending]
        if not todo:
            continue
        sc = S[sig]
        rows = lib.val_rows(D, sc)
        SIG, ADV, info = lib.cost_inputs(D, rows)
        print(sig, "weeks", len(rows), info, flush=True)
        Ws, nets, evals, secs = {}, {}, {}, {}
        # the controls are needed for the paired statistics: build both first (again, if already scored)
        for c in ("C1", "C2"):
            t0 = time.time()
            Ws[c] = lib.build(c, sc, D, rows)
            evals[c], nets[c] = lib.evaluate(Ws[c], D, rows, SIG, ADV)
            secs[c] = time.time() - t0
        ctl_vol = nets["C1"]["net10"].std(ddof=1)
        for c in ORDER:
            name = f"{c}_{sig}"
            if name not in pending:
                continue
            t0 = time.time()
            if c in Ws:
                W, res, nt = Ws[c], evals[c], nets[c]
            else:
                W = lib.build(c if c not in THETA else "GP", sc, D, rows, ADV=ADV, theta=THETA.get(c))
                res, nt = lib.evaluate(W, D, rows, SIG, ADV)
                Ws[c], nets[c] = W, nt
            row = {"name": name, "signal": sig, "config": c, "theta": THETA.get(c),
                   "note": next(p["what"] for p in st["plan"] if p["name"] == name), **res}
            # paired statistics vs C1 and C2 (sqrt model, $10M), raw and vol-matched to C1's net vol
            cvm, vm = lib.vol_matched(W, D, rows, SIG, ADV, ctl_vol)
            row["volmatch_scale"] = cvm
            row["max_drawdown_at_c1_vol"] = lib.max_dd(vm)
            row["net_sharpe_volmatched"] = lib.sharpe(vm)
            for ctl in ("C1", "C2"):
                if ctl != c:
                    p = lib.paired(nt["net10"], nets[ctl]["net10"])
                    row[f"vs_{ctl}_diff_pct_per_year"], row[f"vs_{ctl}_t"] = p["diff_pct_per_year"], p["t"]
                    if ctl == "C1":
                        q = lib.paired(vm, nets["C1"]["net10"])
                    else:
                        _, vm2 = lib.vol_matched(Ws["C2"], D, rows, SIG, ADV, ctl_vol)
                        q = lib.paired(vm, vm2)
                    row[f"vs_{ctl}_volmatched_diff_pct_per_year"], row[f"vs_{ctl}_volmatched_t"] = q["diff_pct_per_year"], q["t"]
                    pf = lib.paired(nt["flat5"], nets[ctl]["flat5"])
                    row[f"vs_{ctl}_flat5_diff_pct_per_year"], row[f"vs_{ctl}_flat5_t"] = pf["diff_pct_per_year"], pf["t"]
            row["seconds"] = round(time.time() - t0 + secs.get(c, 0), 1)
            row["at"] = now()
            np.save(os.path.join(lib.PREDS, f"{name}.npy"), nt["net10"])
            np.savez(os.path.join(lib.PREDS, f"{name}_all.npz"), **nt)
            with open(RESULTS, "a") as f:
                f.write(json.dumps(row) + "\n")
            rest = [x for x in json.load(open(STATE))["pending"] if x != name]
            state_update(name, row, rest[0] if rest else "write model.py and REPORT.md")
            print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items() if k != "note"}), flush=True)


if __name__ == "__main__":
    main()
