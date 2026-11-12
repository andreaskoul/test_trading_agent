"""Holdout finalist: D configuration hgb_multihorizon: boosted trees on D inputs, rank average over 3/5/10/20-session targets (built with X1 lib, which reproduced it exactly as 1a).
Wraps research/tree/X1_combine/lib.py unchanged."""
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "3")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "X1_combine"))
import lib  # noqa: E402

_fp = lib.combine(None, groups=[[("hgb", "D", h) for h in lib.HORIZONS]], panic=False)


def fit_predict(D, train_end, pred_rows, seed):
    lib._P.clear()
    return _fp(D, train_end, pred_rows, seed)
