"""Progress ledger for the tree search, so any branch can resume after a usage limit (owner, 2026-11-12).

    python research/tree/state.py            # rebuild STATE.md (read-only on every branch file)
    python research/tree/state.py --init B   # create B/STATE.json if missing (never overwrites)

Fix 2026-11-13: earlier versions rewrote every branch's STATE.json, including those of agents still running (Q3
reported the clobber); best was chosen by t, against Amendment 2; and "name: spec" plan entries never left pending.
STATE.json belongs to the branch's agent; this script only reads it.

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
         "N1_fundamentals": 2, "N2_short": 2, "N3_intraday": 2, "N4_news": 2, "X4_exploit": 3, "X5_overfit": 3,
         "Q1_seqnet": 3, "Q2_xsattn": 3, "Q3_rankgbm": 3, "Q4_portfolio": 3}
METRIC = {"N2_short": "increment_t", "N3_intraday": "increment_t", "N1_fundamentals": "increment_t", "N4_news": "increment_t", "Q4_portfolio": "net_sharpe"}


def rows(path):
    return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []


def branch_state(b):
    d = os.path.join(HERE, b)
    p = os.path.join(d, "STATE.json")
    old = json.load(open(p)) if os.path.exists(p) else {}
    R = rows(os.path.join(d, "RESULTS.jsonl"))
    key = METRIC.get(b, "ic")                                  # Amendment 2: mean IC (mean increment for track N), not t
    if key == "increment_t":
        key = "increment"
    scored = [r.get("name") for r in R]

    def admissible(r):
        by = r.get("ic_by_year")
        return key != "ic" or not by or sum(v > 0 for v in by.values()) >= 5
    cands = [r for r in R if key in r and r[key] is not None and admissible(r)]
    best = max(cands, key=lambda r: r[key], default=None)
    plan = old.get("plan", [])
    planned = [str(c).split(":")[0].strip() for c in plan]
    st = {
        "branch": b, "phase": PHASE.get(b), "status": old.get("status", "not started" if not os.path.isdir(d) else "in progress"),
        "configurations_scored": len(R), "scored": scored,
        "best": {k: best.get(k) for k in ("name", "ic", "ic_t", "increment", "increment_t", "net_sharpe", "decile_net_pct_per_year", "decile_net_sharpe") if best and k in best} if best else None,
        "plan": plan, "pending": [c for c in planned if c not in scored],
        "deliverables": {f: os.path.exists(os.path.join(d, f)) for f in ("model.py", "REPORT.md")},
        "verdict": old.get("verdict"), "notes": old.get("notes", []),
        "resume": (f"Read research/tree/{b}/STATE.json first. Do not re-score anything in 'scored' (RESULTS.jsonl is the "
                   f"record). Score only 'pending', then write the missing deliverables. Update STATE.json after every "
                   f"configuration: append to 'notes' what you did and what you plan next."),
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if old:                                                    # the ledger shows the agent's own status/best when present
        st["status"] = old.get("status", st["status"])
    return st


def init(b):
    p = os.path.join(HERE, b, "STATE.json")
    if os.path.exists(p):
        raise SystemExit(f"{p} exists; not overwritten")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(branch_state(b), open(p, "w"), indent=1)


def main():
    names = sorted(set(PHASE) | {os.path.basename(x) for x in glob.glob(os.path.join(HERE, "*_*")) if os.path.isdir(x) and "__" not in x})
    S = [branch_state(b) for b in names if b in PHASE or os.path.isdir(os.path.join(HERE, b))]
    L = ["# Tree search: progress ledger", "", f"*Rebuilt {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} by `state.py` from each branch's "
         "logs. To resume a branch after a usage limit: send its agent (or a new one) the `resume` line of its `STATE.json`.*", "",
         "| branch | phase | status | scored | best (Amendment 2 rule) | mean IC / increment / net Sharpe | model.py | REPORT.md | verdict |", "|---|---:|---|---:|---|---:|---|---|---|"]
    for s in S:
        b = s["best"] or {}
        m = b.get("increment", b.get("net_sharpe", b.get("ic")))
        L.append(f"| {s['branch']} | {s['phase']} | {s['status']} | {s['configurations_scored']} | {(b.get('name') or '')[:40]} | "
                 f"{'' if m is None else f'{m:.4f}'} | {'yes' if s['deliverables']['model.py'] else 'no'} | "
                 f"{'yes' if s['deliverables']['REPORT.md'] else 'no'} | {s['verdict'] or ''} |")
    open(os.path.join(HERE, "STATE.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "--init":
        init(sys.argv[2])
    else:
        main()
