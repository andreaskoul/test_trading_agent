"""Branch N1 best configuration: fm_fixed70.

0.7 x rank(MASTER 5-day, frozen) + 0.3 x rank(fundamentals score). The fundamentals score is a Fama-MacBeth
combination: weekly cross-sectional ridge-OLS (lambda 1e-3 x n) of the ranked 5-session target on 13 centred
cross-sectional ranks of point-in-time SEC XBRL characteristics (lib.CHARS + log assets; missing = 0), over all
training Thursdays 2009..train_end, coefficients averaged. Deterministic (seed unused). Where MASTER is NaN, NaN.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402
import run_fit  # noqa: E402

W_MASTER = 0.7


def fit_predict(D, train_end, pred_rows, seed):
    tr = lib.train_thursdays(train_end)
    b = run_fit.fm(run_fit.X_at(tr, run_fit.FEATS), lib.target_rank(D, tr)).mean(0)   # D's y5 is blanked after train_end
    s = np.full(D["y5"].shape, np.nan)
    s[pred_rows] = run_fit.X_at(pred_rows, run_fit.FEATS) @ b
    return lib.blend(s, W_MASTER)[pred_rows]


if __name__ == "__main__":
    from lib import harness
    D = lib.data()
    r = harness.increment(harness.walk_forward(fit_predict, seeds=(0,), D=D), "model.py check", None, D=D)
    print(r["ic"], r["increment"], r["increment_t"])
