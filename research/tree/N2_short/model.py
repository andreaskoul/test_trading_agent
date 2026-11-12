"""Branch N2 best configuration (by development increment t, which is below the 1.5 gate): c3, a fixed rank average
0.7 x MASTER 5-day + 0.3 x F2 (minus the 20-session FINRA short-volume ratio), on MASTER's names only.
Weights decided before any result. Features causal (sessions up to the prediction row); nothing is fitted.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402


def fit_predict(D, train_end, pred_rows, seed):
    return lib.combine(D, pred_rows, 0.7, ["f2"], [0.3])


if __name__ == "__main__":
    from lib import harness
    D = harness.load()
    print(harness.increment(harness.walk_forward(fit_predict, seeds=(0,), D=D), "model.py check", D=D))
