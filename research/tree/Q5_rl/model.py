"""Branch Q5_rl best policy by net Sharpe with drawdown no worse than the control (development 2013-2019):
rrl_dsr on the D trees signal.

Moody-Saffell recurrent reinforcement learning with the online differential Sharpe ratio (lib.train_rrl_dsr) on the
13-parameter smooth-band policy (lib.rrl_step): entry at percentile |p - .5| > k, held names keep their side while
|p - .5| > k - h, size tilted by vol^-theta_v and signal strength, sides 0.5 each (dollar-neutral, gross 1), times a
book exposure sigmoid(b0 + beta . x_t) <= 1 from 8 causal market-state inputs. Returns are on beta-hedged residuals
(y5), so each book carries the implicit SPY leg -sum w_i beta_i. Initialised at the control band (k .4, h .1).
Training length 3 passes, chosen on walk-forward 2014-2016 from {1, 3, 10} (TUNING.jsonl).

Walk-forward: year y in 2014-2019 uses the policy trained on weeks whose y5 ended before y; the book carries over;
2013 holds the control band. Seeds 0, 1, 2: the scored series is the mean of the three seed sub-books' weekly nets.
"""
import json
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "3")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import torch  # noqa: E402

import lib  # noqa: E402

SPEC = {"method": "rrl_dsr", "length": 3, "seeds": (0, 1, 2), "signal": "trees", "logged_name": "rrl_dsr_trees"}


def seed_books(scores, D, rows=None):
    """Per-seed weights (seeds, len(Pd rows), names) for M1's validation rows; rows before 2014 hold the band."""
    Pd = lib.prep(D, scores)
    if rows is not None:
        assert np.array_equal(np.asarray(rows), Pd["rows"]), "rows must be M1's validation rows for this signal"
    T, n, ns = len(Pd["rows"]), Pd["Y"].shape[1], len(SPEC["seeds"])
    Wb = lib.control_band(D, scores, Pd)
    W = np.tile(Wb[None], (ns, 1, 1))
    f = Pd["first"]
    pu = pw = torch.as_tensor(np.tile(Wb[f[2014] - 1], (ns, 1)))
    for y in range(2014, 2020):
        j0, j1 = f[y], (f[y + 1] if y < 2019 else T)
        phi = lib.train_rrl_dsr(Pd, Pd["te"][y], SPEC["seeds"], (SPEC["length"],))[SPEC["length"]]
        with torch.no_grad():
            _, Wy, pu, pw = lib.run_seq(lib.rrl_stepper(phi, Pd), Pd, j0, j1, pu, pw)
        W[:, j0:j1] = Wy.numpy().transpose(1, 0, 2)
    return W, Pd


def build_weights(scores, D, rows):
    """Weights (len(rows) x names): the mean of the three seed books (row j chosen from data <= rows[j])."""
    return seed_books(scores, D, rows)[0].mean(0)


if __name__ == "__main__":
    D = lib.harness.load()
    s = lib.signals(D)[SPEC["signal"]]
    W, Pd = seed_books(s, D)
    j14 = Pd["first"][2014]
    net = np.mean([lib.net_of(W[i], Pd)[0] for i in range(len(W))], 0)[j14:]
    sh = lib.shp(net)
    logged = [json.loads(l) for l in open(os.path.join(lib.HERE, "RESULTS.jsonl")) if json.loads(l)["name"] == SPEC["logged_name"]][0]
    ctl = lib.net_of(lib.control_band(D, s, Pd), Pd)[0][j14:]
    print({"net_sharpe_2014_2019": sh, "logged": logged["net_sharpe"], "net_pct_per_year": 52 * 100 * net.mean(),
           "max_drawdown": lib.max_dd(net), "band_net_sharpe": lib.shp(ctl), "band_max_drawdown": lib.max_dd(ctl),
           "ok": abs(sh - logged["net_sharpe"]) < 1e-6})
