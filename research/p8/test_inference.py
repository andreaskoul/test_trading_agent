"""Validation of research/p8/inference.py on simulated data (run before any P8 test uses it).

    python research/p8/test_inference.py

1. Exactness: the closed-form WCR draws equal brute-force re-estimation (y* built, demeaned, OLS, CRV1).
2. Size: under beta = 0 with industry-clustered signal and errors, rejection at one-sided 5% is ~5% for the wild
   bootstrap and the randomization test; naive i.i.d. OLS over-rejects (why clustering is needed).
3. Power: rejection rises with beta.
4. Newey-West: under AR(1) slopes (rho 0.3) the NW(3) t has size near 5%; Holm matches the textbook procedure.
Monte Carlo standard error of a 5% rate over R simulations: sqrt(.05 * .95 / R).
"""
import os
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inference as I                                            # noqa: E402


def sim(rng, beta=0.0, n_ind=60, n_sec=10, n_season=24, per=6, icc=0.15):
    """Firms in industries nested in sectors; events per (industry, season); signal and error both carry an
    industry-season common component (the case that breaks i.i.d. inference)."""
    ind = np.repeat(np.arange(n_ind), n_season * per)
    sea = np.tile(np.repeat(np.arange(n_season), per), n_ind)
    sec = ind % n_sec
    com_s = rng.normal(size=(n_ind, n_season))[ind, sea]
    com_e = rng.normal(size=n_ind)[ind] * np.sqrt(icc / 2) + rng.normal(size=(n_ind, n_season))[ind, sea] * np.sqrt(icc / 2)
    s = 0.6 * com_s + 0.8 * rng.normal(size=len(ind))
    e = com_e + np.sqrt(1 - icc) * rng.normal(size=len(ind))
    y = beta * s + e + 0.3 * rng.normal(size=(n_sec, n_season))[sec, sea]
    cell = sec * 1000 + sea
    return y, s, cell, ind


def test_exact():
    rng = np.random.default_rng(1)
    y, s, cell, ind = sim(rng, beta=0.05)
    out = I.event_test(y, s, cell, ind, B=20, seed=7, return_draws=True, ri=False)
    c, g = I._codes(cell), I._codes(ind)
    C, G, N = c.max() + 1, g.max() + 1, len(y)
    yt, st = I._demean(y, c, C), I._demean(s, c, C)
    k = G / (G - 1) * (N - 1) / (N - 1 - C)
    r2 = np.random.default_rng(7)
    W = r2.choice(I.WEBB if G <= 12 else I.RADEMACHER, size=(20, G))
    for b in range(5):
        ystar = (y - yt) + W[b][g] * yt                       # fitted FE + w_g * restricted residual
        ys = I._demean(ystar, c, C)
        bb = st @ ys / (st @ st)
        e = ys - bb * st
        sc = np.bincount(g, weights=st * e, minlength=G)
        tb = bb / np.sqrt(k * (sc @ sc) / (st @ st) ** 2)
        assert abs(tb - out["draws"][b]) < 1e-9, (tb, out["draws"][b])
    print("ok   exact: closed-form WCR draws equal brute force (5 draws, |diff| < 1e-9)")


def test_size_power():
    R = 300
    for beta in (0.0, 0.03, 0.06):
        rej = {"wild": 0, "ri": 0, "both": 0, "iid": 0}
        for r in range(R):
            rng = np.random.default_rng(1000 + r)
            y, s, cell, ind = sim(rng, beta=beta)
            o = I.event_test(y, s, cell, ind, B=399, seed=r)
            c = I._codes(cell); C = c.max() + 1
            yt, st = I._demean(y, c, C), I._demean(s, c, C)
            b = st @ yt / (st @ st); e = yt - b * st
            t_iid = b / np.sqrt((e @ e) / (len(y) - C - 1) / (st @ st))
            rej["wild"] += o["p_wild"] <= 0.05; rej["ri"] += o["p_ri"] <= 0.05
            rej["both"] += o["p"] <= 0.05; rej["iid"] += (1 - stats.norm.cdf(t_iid)) <= 0.05
        se = np.sqrt(.05 * .95 / R)
        print(f"beta {beta}: rejection at 5% (R={R}, MC se {se:.3f}): " + ", ".join(f"{k} {v / R:.3f}" for k, v in rej.items()))
        if beta == 0.0:
            assert abs(rej["wild"] / R - 0.05) < 3.5 * se and abs(rej["both"] / R - 0.05) < 3.5 * se, "size off"
    print("ok   size and power")


def test_nw_holm():
    R, rej = 2000, 0
    for r in range(R):
        rng = np.random.default_rng(r)
        x = np.zeros(48)
        u = rng.normal(size=48)
        for t in range(48):
            x[t] = 0.3 * (x[t - 1] if t else 0) + u[t]
        t, T = I.nw_t(x)
        rej += I.nw_p(t, T) <= 0.05
    se = np.sqrt(.05 * .95 / R)
    print(f"NW(3) one-sided size with the small-sample reference, AR(1) rho .3, T 48: {rej / R:.3f} (MC se {se:.3f}; "
          f"t(T-1) gave 0.081-0.086)")
    rej0 = 0
    for r in range(R):
        x = np.random.default_rng(10_000 + r).normal(size=48)
        rej0 += I.nw_p(I.nw_t(x)[0], 48) <= 0.05
    print(f"NW(3) size under i.i.d.: {rej0 / R:.3f}")
    assert abs(rej0 / R - 0.05) < 3.5 * se, "NW reference size off under i.i.d."
    # m = 7: 0.001 x 7 = 0.007 passes; 0.01 x 6 = 0.06 fails and stops the step-down
    adj, ok = I.holm([0.01, 0.04, 0.03, 0.2, 0.001, 1.0, 1.0])
    assert list(ok) == [False, False, False, False, True, False, False], (adj, ok)
    assert np.allclose(adj, [0.06, 0.16, 0.15, 0.6, 0.007, 1.0, 1.0]), adj   # 0.03 x 5, 0.04 x 4
    adj, ok = I.holm([0.004, 0.009, 0.012])                   # 0.012, 0.018, 0.012 -> monotone 0.012, 0.018, 0.018
    assert list(ok) == [True, True, True] and np.allclose(adj, [0.012, 0.018, 0.018]), adj
    print("ok   Newey-West size; Holm")


def test_webb_size():
    R, rej = 300, 0
    for r in range(R):
        rng = np.random.default_rng(5000 + r)
        y, s, cell, ind = sim(rng, beta=0.0, n_ind=11, n_sec=11, n_season=40, per=8)
        rej += I.event_test(y, s, cell // 1000, ind, B=399, seed=r, ri=False)["p_wild"] <= 0.05
    print(f"WCR with Webb weights, 11 clusters, one-sided 5%: {rej / R:.3f} (MC se {np.sqrt(.05 * .95 / R):.3f})")


if __name__ == "__main__":
    test_webb_size()
    test_exact()
    test_nw_holm()
    test_size_power()
