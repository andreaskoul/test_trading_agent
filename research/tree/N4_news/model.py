"""N4_news best configuration by mean increment, c6 (it does NOT meet the selection rule: positive in 1 of 4 years).

    0.7 rank(MASTER) + 0.3 rank(s),  s = centred rank(tone5) x (rank(novelty5) in [0, 1])

tone5 = mean hand-list tone of single-symbol headlines in the last 5 sessions (lexicon.py; not Loughran-McDonald),
novelty5 = share of the last 5 sessions' headlines not seen (normalised text) for the name in the prior 21 sessions.
Missing tone -> 0 (neutral), missing novelty -> 0.5. No fit. Inputs: .cache/tree/extra_news_dev.npz (features.py).

    python model.py    # reproduces the c6 increment over MASTER on 2016-2019
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib  # noqa: E402
from lib import harness, xrank  # noqa: E402


def predict(D, X=None):
    X = X or lib.news()
    tn = np.nan_to_num(xrank(X["raw_tone5"].astype(np.float64), D["elig"]))
    nv = xrank(X["raw_nov5"].astype(np.float64), D["elig"]) + 0.5
    s = tn * np.where(np.isfinite(nv), nv, 0.5)
    m = D["master_h5_ref"].astype(np.float64)
    ok = np.isfinite(m) & D["elig"]
    rm = xrank(np.where(ok, m, np.nan))
    rs = xrank(np.where(ok, s, np.nan))
    rs = np.where(ok & ~np.isfinite(rs), 0.0, rs)
    p = 0.7 * rm + 0.3 * rs
    p[~ok] = np.nan
    return p


if __name__ == "__main__":
    D = harness.load()
    r = harness.increment(predict(D), "N4 model.py (c6)", None, "", D, lib.YEARS)
    saved = np.load(os.path.join(lib.PREDS, "c6.npy")).astype(np.float64)
    print("increment %+.6f t %.3f years+ %d; max |pred - saved c6| %.2e" % (
        r["increment"], r["increment_t"], r["years_increment_positive"], np.nanmax(np.abs(predict(D) - saved))))
