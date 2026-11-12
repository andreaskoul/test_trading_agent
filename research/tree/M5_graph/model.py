"""Branch M5 best configuration's fit_predict (name in BEST; definitions in run.py CONFIGS, m5lib.py, gnn.py).

Kept current while the branch runs. Data: harness.load() and harness.load_extra("peers") only; year y's text graph is
used for sessions of year y.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import run  # noqa: E402

BEST = "R4_C24_peermomrev"
fit_predict = run.CONFIGS[BEST][0]()

if __name__ == "__main__":
    from harness import walk_forward, score, load
    D = load()
    print(score(walk_forward(fit_predict, seeds=(0, 1, 2), D=D), "M5 model.py check (%s)" % BEST, D=D))
