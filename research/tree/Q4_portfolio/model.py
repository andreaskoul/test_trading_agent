"""Branch Q4 best construction by net Sharpe (development 2013-2019): mvnl_nt on the D trees signal.

Mean-variance long/short weights w = Sigma^-1 (mu - A lam), dollar- and beta-neutral (A = [1, beta_t]), gross 1, with
mu_i = sigma_i z_i (z = normal score of the cross-sectional rank) and Sigma = Ledoit-Wolf (2020) analytical nonlinear
shrinkage of the last 252 sessions of residual returns D["e"] (see lib.lw_nonlinear); then an L1 no-trade region:
each weight stays put unless it is more than 2 x mean|target weight| from the target, in which case it moves to the
region's edge; gross renormalised to 1. The width 2 was chosen on 2013-2016 from {0.5, 1, 2} (TUNING.jsonl); it is
the grid edge, and a wider grid (2/3/4/6) picked 6, which barely trades (mvnl_ntx_trees): the tuning surface is flat.

Caveat: at gross 1 this book's volatility is about 1.4 %/yr (net +0.88 %/yr); matching the control's 6.4 %/yr needs
about 4.5x gross. Its Sharpe gain over the control is not significant (vol-matched paired t 0.72) and the
construction does not transfer to the IPCA, blend or MASTER signals on 2013-2016.
"""
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "3")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import lib  # noqa: E402

SPEC = {"target": "mvnl", "nt": 2.0}


def build_weights(scores, D, rows):
    """Weights (len(rows) x names), row j chosen on Thursday rows[j] from data <= rows[j]."""
    return lib.build(SPEC, scores, D, rows)[0]


if __name__ == "__main__":
    import json
    D = lib.harness.load()
    s = lib.signals(D)["trees"]
    rows = lib.val_rows(D, s)
    W = build_weights(s, D, rows)
    net = lib.simulate(W, D, rows)["net"][1:]
    sh = float(net.mean() / net.std(ddof=1) * np.sqrt(52))
    logged = [json.loads(l) for l in open(os.path.join(lib.HERE, "RESULTS.jsonl")) if '"mvnl_nt_trees"' in l][0]
    print({"net_sharpe": sh, "logged": logged["net_sharpe"], "net_pct_per_year": 52 * 100 * net.mean(),
           "max_drawdown": lib.max_dd(net), "ok": abs(sh - logged["net_sharpe"]) < 1e-9})
