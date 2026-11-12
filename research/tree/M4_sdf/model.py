"""Branch M4 best configuration (see STATE.json "best"): Kozak-Nagel-Santosh shrunk SDF (sdf.py docstring).
Deterministic: the seed is unused."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import sdf  # noqa: E402

CONFIG = ("X324", "wk", "mv", "raw")         # S04_X324_wk_mv (highest IC t, 7/7 years positive); S01 = ("C24", "wk", "l2", "raw")
fit_predict = sdf.make(*CONFIG)

if __name__ == "__main__":
    from harness import walk_forward, score, load
    D = load()
    print(score(walk_forward(fit_predict, seeds=(0, 1, 2), D=D), "M4 model.py check", D=D))
