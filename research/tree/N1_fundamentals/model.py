"""Branch N1 best configuration so far: comp_blend70.

0.7 x rank(MASTER 5-day, frozen) + 0.3 x rank(equal-weight literature composite of point-in-time fundamentals:
profitability (gross profit / assets, else operating income / assets), -accruals, -asset growth, +payout / assets,
+SUE; each a cross-sectional rank at the prediction row; missing = neutral). No fitting: train rows are unused.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402

W_MASTER = 0.7


def fit_predict(D, train_end, pred_rows, seed):
    lib._C["D"] = D if "master_h5_ref" in D else lib.data()
    return lib.blend(lib.composite(lib.COMPOSITE), W_MASTER)[pred_rows]


if __name__ == "__main__":
    from lib import harness
    D = harness.load()
    print(harness.increment(harness.walk_forward(fit_predict, seeds=(0,), D=D), "model.py check", None, D=D))
