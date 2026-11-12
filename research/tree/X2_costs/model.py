"""Branch X2 best configuration (c2a_mh_ema_hl1, see REPORT.md). Imports lib.py (this folder) and the harness only.

    from model import fit_predict
    pred = harness.walk_forward(fit_predict, seeds=(0, 1, 2))

Branch D's boosted trees (27 ranked price features, rank target) fitted on 3-, 5-, 10- and 20-session hedged-return
targets, cross-sectional ranks averaged with equal weights; then each stock's rank is exponentially smoothed over the
current and the 12 preceding Thursdays (half-life 1 week). Past weeks are scored by the same fitted model from the
features of their own row, so a score for row t uses data up to row t only.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402

fit_predict = lib.make(members=(("all", 3, 1), ("all", 5, 1), ("all", 10, 1), ("all", 20, 1)), hl=1)
