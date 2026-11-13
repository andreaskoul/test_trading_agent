"""Unit tests for the square-root cost model (synthetic panel; no development data read beyond the dict shape).

    python research/tree/Q6_trade/test_cost.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402


def synth(T=3, n=4):
    D = {"y5": np.zeros((T, n))}
    rows = np.arange(T)
    SIG = np.full((T, n), 0.02)
    ADV = np.full((T, n), 1e8)
    return D, rows, SIG, ADV


def test_zero_trade_zero_cost():
    D, rows, SIG, ADV = synth()
    W = np.zeros((3, 4))
    s = lib.simulate_sqrt(W, D, rows, 1e7, SIG, ADV)
    assert np.all(s["cost"] == 0) and np.all(s["impact"] == 0) and np.all(s["spread"] == 0)
    W = np.tile([0.25, 0.25, -0.25, -0.25], (3, 1))          # held book: only the first week trades
    s = lib.simulate_sqrt(W, D, rows, 1e7, SIG, ADV)
    assert s["cost"][0] > 0 and s["cost"][1] == 0 and s["cost"][2] == 0 and s["impact"][1] == 0


def test_sqrt_scaling():
    sig, adv, aum = np.array([0.02]), np.array([1e8]), 1e7
    _, i1 = lib.trade_cost(np.array([0.01]), sig, adv, aum)
    _, i4 = lib.trade_cost(np.array([0.04]), sig, adv, aum)
    # impact per unit traded scales with sqrt(trade): x4 trade -> x2 per unit, x8 in total
    assert np.isclose(i4[0] / 0.04, 2 * i1[0] / 0.01) and np.isclose(i4[0], 8 * i1[0])
    # impact per unit scales with sqrt(AUM / ADV)
    _, ia = lib.trade_cost(np.array([0.01]), sig, adv, aum * 100)
    assert np.isclose(ia[0], 10 * i1[0])
    _, ib = lib.trade_cost(np.array([0.01]), sig, adv * 4, aum)
    assert np.isclose(ib[0], i1[0] / 2)
    # half-spread is linear and sign-free
    sp, _ = lib.trade_cost(np.array([-0.03]), sig, adv, aum)
    assert np.isclose(sp[0], 0.03 * lib.HS)


def test_known_value():
    # 1% of ADV traded, daily vol 2%, K 0.5: impact per unit = 0.5 * 0.02 * 0.1 = 10 bp (the JKMP anchor)
    sp, im = lib.trade_cost(np.array([0.1]), np.array([0.02]), np.array([1e8]), 1e7)   # $1M of $100M ADV
    assert np.isclose(im[0] / 0.1, 0.001), im[0] / 0.1


def test_net_equals_gross_minus_cost():
    D, rows, SIG, ADV = synth()
    rng = np.random.default_rng(0)
    D["y5"] = rng.normal(0, 0.02, (3, 4))
    W = rng.normal(0, 0.25, (3, 4))
    s = lib.simulate_sqrt(W, D, rows, 1e7, SIG, ADV)
    assert np.allclose(s["net"], s["gross"] - s["cost"]) and np.allclose(s["cost"], s["spread"] + s["impact"])


if __name__ == "__main__":
    for f in (test_zero_trade_zero_cost, test_sqrt_scaling, test_known_value, test_net_equals_gross_minus_cost):
        f()
        print("ok", f.__name__)
