"""Branch X3 best configuration: 32 columns (branch C's 24 price characteristics + 8 market-state interactions),
Fama-MacBeth average of per-session cross-sectional ridge slopes, expanding window, fitted ONCE A YEAR
(sessions d <= train_end). Development IC 0.0218, t 2.22, positive in 6 of 7 years.

The branch's finding is that within-year updating does not help, so the best configuration is the yearly control.
The best online scheme is the same model with ONLINE = True (cut = t - 6 at every prediction row): IC 0.0193, t 1.93.

Deterministic; the seed is ignored. D["y5"] is not used: the target is rebuilt from D["e"] on closed windows only
(lib.rebuilt_target; correlation with y5 on training rows 0.9999) and rank-standardised per session.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402

ONLINE = False
fit_predict = lib.make(kind="C32", online=ONLINE, mode="fm")
