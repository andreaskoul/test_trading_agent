"""Branch Q6 best registered candidate (development 2013-2019): T1 rank hysteresis on the D trees signal.

Each Thursday t (data <= t): rank the eligible scored names; enter long in the top 10% and short in the bottom 10%;
a held long stays while its rank is above the 70th percentile, a held short while below the 30th; equal weights,
long side +0.5, short side -0.5 (gross 1, dollar-neutral; returns are the beta-hedged y5, as for every control).

Judged under the square-root cost model (lib.simulate_sqrt: half-spread 2.3 bp + 0.5 sigma_i sqrt(|dw| AUM / ADV_i),
AUM $10M). Not significant against either control: vs C1 band +0.34 %/yr (t 0.90; vol-matched t 1.31); behind the
C2 control mvnl_nt vol-matched (-1.41 %/yr, t -0.55). Development data, not out of sample.

    python research/tree/Q6_trade/model.py
"""
import json
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "3")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import lib  # noqa: E402

NAME = "T1_trees"


def build_weights(scores, D, rows):
    """Weights (len(rows) x names); row j chosen on Thursday rows[j] from data <= rows[j]."""
    return lib.build("T1", scores, D, rows)


if __name__ == "__main__":
    D = lib.harness.load()
    s = lib.signals(D)["trees"]
    rows = lib.val_rows(D, s)
    SIG, ADV, _ = lib.cost_inputs(D, rows)
    W = build_weights(s, D, rows)
    net = lib.simulate_sqrt(W, D, rows, lib.AUM, SIG, ADV)["net"][1:]
    sh = lib.sharpe(net)
    logged = [json.loads(l) for l in open(os.path.join(lib.HERE, "RESULTS.jsonl")) if json.loads(l)["name"] == NAME][0]
    saved = np.load(os.path.join(lib.PREDS, f"{NAME}.npy"))
    print({"net_sharpe": sh, "logged": logged["net_sharpe"], "net_pct_per_year": 52 * 100 * net.mean(),
           "max_drawdown": lib.max_dd(net), "ok": abs(sh - logged["net_sharpe"]) < 1e-9 and np.allclose(net, saved)})
