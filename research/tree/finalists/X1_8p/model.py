"""Holdout finalist: X1 configuration 8p: rank average of D trees (D inputs), C Fama-MacBeth ridge and an MLP on C inputs, each trained on 3/5/10/20-session targets, with the fixed panic overlay.
Wraps research/tree/X1_combine/lib.py unchanged."""
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "3")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "X1_combine"))
import lib  # noqa: E402

_fp = lib.combine(None, groups=[[("hgb", "D", h) for h in lib.HORIZONS], [("fm", "C", h) for h in lib.HORIZONS], [("mlp", "C", h) for h in lib.HORIZONS]], panic=True)


def fit_predict(D, train_end, pred_rows, seed):
    lib._P.clear()
    return _fp(D, train_end, pred_rows, seed)
