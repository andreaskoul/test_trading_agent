"""Branch M2 best configuration (M05_C24_wk_xn_U): unrestricted IPCA (Kelly, Pruitt and Su 2019).

Characteristics: the 24 price-only features of branch C (read-only import of C_features/lib.py), cross-sectional
ranks in [-0.5, 0.5] over eligible names (missing -> 0) plus a constant. Returns: Thursday 5-session hedged returns y5,
cross-sectionally standardised and clipped at +-3 (xnorm). ALS estimation on all training Thursdays; K chosen per
training set from {1, 3, 5} by inner-holdout predictive R^2 on the last 2 training years (never by validation IC).
Score = Z_t (Gamma_a + Gamma_b * mean(f)). Deterministic: the seed is unused.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import ipca  # noqa: E402

_restricted, fit_predict = ipca.make("C24", "weekly", "auto", Ks=(1, 3, 5), lam=0.0, xnorm=True)

if __name__ == "__main__":
    from harness import walk_forward, score, load
    D = load()
    print(score(walk_forward(fit_predict, seeds=(0, 1, 2), D=D), "M2 model.py check", D=D))
