"""Branch M1 best construction (see REPORT.md): weekly weights from a score panel, no predictor fitted.

    import sys; sys.path.insert(0, "research/tree/M1_dyntrade")
    from model import construct
    import lib
    D = lib.harness.load()
    rows, W = construct(D["master_h5_ref"].astype(float), D)        # W: (len(rows), n_names), +0.5 / -0.5 a side
    print(lib.summary(lib.simulate(W, D, rows), skip_first=False))   # net %/yr, Sharpe, turnover, 5 bp a side

Default: the no-trade band (enter a side at the 10% tail, leave it only past the 20% tail, equal weights). It is the
one construction whose weekly gain over the plain decile book is consistent on both bases (paired t 2.5 MASTER, 2.3
trees). kind="gp_mv_diag" gives the Garleanu-Pedersen book with the derived trade rate (lib.gp_params, past data only).
Weights at row t use scores, eligibility and y5-availability at t (the harness's mask), D["e"] up to t, and realised
ICs of weeks whose y5 ended by t.

    python3 research/tree/M1_dyntrade/run.py            # every logged configuration, appends RESULTS.jsonl
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402


def construct(scores, D, kind="band", **kw):
    rows = lib.val_rows(D, scores)
    if kind == "band":
        kw.setdefault("band", 0.1)
    return rows, lib.build(kind, scores, D, rows, **kw)
