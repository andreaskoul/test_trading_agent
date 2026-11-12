"""Branch X1 best configuration (6p): the two round-1 winners, equal weight, plus the fixed panic overlay.

    score = rank-average of
              (a) boosted trees on branch D's 27 ranked inputs, trained on 3-, 5-, 10- and 20-session hedged-return
                  rank targets (ranks averaged over the four horizons), and
              (b) branch C's Fama-MacBeth ridge on 24 price characteristics + 8 market-state interactions (5 sessions);
    in panic weeks (market 252-session return < 0 and 21-session volatility above the 67th percentile of rows
    <= train_end) the score is replaced by its cross-sectional residual on 12-1 momentum.

Imports lib.py from this folder and the harness only. No disk cache is used here.

    from model import fit_predict
    pred = harness.walk_forward(fit_predict, seeds=(0, 1, 2))
"""
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "3")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402

TREES = [("hgb", "D", h) for h in lib.HORIZONS]
RIDGE = [("fm", "C", 5)]
_fp = lib.combine(None, groups=[TREES, RIDGE], panic=True)


def fit_predict(D, train_end, pred_rows, seed):
    lib._P.clear()                      # member cache is per call: nothing carries over between refits
    return _fp(D, train_end, pred_rows, seed)
