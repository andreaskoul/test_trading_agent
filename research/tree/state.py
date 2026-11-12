"""Progress ledger for the tree search, so any branch can resume after a usage limit (owner, 2026-11-12).

    python research/tree/state.py            # rebuild STATE.md and every <branch>/STATE.json from the logs on disk

Each branch's STATE.json holds what is on disk: configurations scored (from RESULTS.jsonl), the best so far, which
deliverables exist, the planned configurations not yet scored (from PLAN in the branch's STATE.json, kept), and the
exact resume instruction. A resumed or replacement agent reads its STATE.json first and scores only what is missing.
"""
import glob
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PHASE = {"A_loss": 1, "B_arch": 1, "C_features": 1, "D_ensembles": 1, "E_regime": 1, "X1_combine": 1, "X2_costs": 1,
         "X3_online": 1, "M1_dyntrade": 2, "M2_ipca": 2, "M3_cae": 2, "M4_sdf": 2, "M5_graph": 2, "M6_ssl": 2,
         "N1_fundamentals": 2, "N2_short": 2, "N3_intraday": 2, "N4_news": 2}
METRIC = {"N2_short": "increment_t", "N3_intraday": "increment_t", "N1_fundamentals": "increment_t", "N4_news": "increment_t"}


def rows(path):
    return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []


def branch_state(b):
    d = os.path.join(HERE, b)
    p = os.path.join(d, "STATE.json")
    old = json.load(open(p)) if os.path.exists(p) else {}
    R = rows(os.path.join(d, "RESULTS.jsonl"))
    key = METRIC.get(b, "ic_t")
    scored = [r.get("name") for r in R]
    best = max((r for r in R if key in r), key=lambda r: r[key], default=None)
    plan = old.get("plan", [])
    st = {
        "branch": b, "phase": PHASE.get(b), "status": old.get("status", "not started" if not os.path.isdir(d) else "in progress"),
        "configurations_scored": len(R), "scored": scored,
        "best": {k: best.get(k) for k in ("name", "ic", "ic_t", "increment", "increment_t", "decile_net_pct_per_year", "decile_net_sharpe") if best and k in best} if best else None,
        "plan": plan, "pending": [c for c in plan if c not in scored],
        "deliverables": {f: os.path.exists(os.path.join(d, f)) for f in ("model.py", "REPORT.md")},
        "verdict": old.get("verdict"), "notes": old.get("notes", []),
        "resume": (f"Read research/tree/{b}/STATE.json first. Do not re-score anything in 'scored' (RESULTS.jsonl is the "
                   f"record). Score only 'pending', then write the missing deliverables. Update STATE.json after every "
                   f"configuration: append to 'notes' what you did and what you plan next."),
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if os.path.isdir(d):
        json.dump(st, open(p, "w"), indent=1)
    return st


def main():
    names = sorted(set(PHASE) | {os.path.basename(x) for x in glob.glob(os.path.join(HERE, "*_*")) if os.path.isdir(x) and "__" not in x})
    S = [branch_state(b) for b in names if b in PHASE or os.path.isdir(os.path.join(HERE, b))]
    L = ["# Tree search: progress ledger", "", f"*Rebuilt {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} by `state.py` from each branch's "
         "logs. To resume a branch after a usage limit: send its agent (or a new one) the `resume` line of its `STATE.json`.*", "",
         "| branch | phase | status | scored | best | metric | model.py | REPORT.md | verdict |", "|---|---:|---|---:|---|---:|---|---|---|"]
    for s in S:
        b = s["best"] or {}
        m = b.get("increment_t", b.get("ic_t"))
        L.append(f"| {s['branch']} | {s['phase']} | {s['status']} | {s['configurations_scored']} | {(b.get('name') or '')[:40]} | "
                 f"{'' if m is None else f'{m:.2f}'} | {'yes' if s['deliverables']['model.py'] else 'no'} | "
                 f"{'yes' if s['deliverables']['REPORT.md'] else 'no'} | {s['verdict'] or ''} |")
    open(os.path.join(HERE, "STATE.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
