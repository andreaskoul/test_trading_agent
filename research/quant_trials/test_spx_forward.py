"""Contract tests for spx_forward.py on the research build (no models needed): the live holding period and book
return must equal the backtest's (strategies.periods/backtest) for the same decisions and weights.

    python test_spx_forward.py
"""

import numpy as np
import pandas as pd

import sp500_test as T
import spx_forward as FW
import strategies as ST


def _rec(d, t, w, w_spy, s=1.3):
    names = list(d["names"])
    return {"asof": str(d["S"][t].date()), "sleeve": {"s": s}, "dtb3": 0.04,
            "books": {"b": {"weights": {names[i]: float(x) for i, x in enumerate(w) if x}, "w_spy": w_spy,
                            "scale": 1.0}}}


def test_period_matches_backtest():
    d = T.build()
    per = ST.periods(d, [2019])
    for (t, R, Rm, days), (t2, *_ ) in zip(per[:5], per[1:6]):
        a, b = _rec(d, t, np.zeros(len(d["names"])), 0.0), _rec(d, t2, np.zeros(len(d["names"])), 0.0)
        R_, Rm_, days_ = FW.period(d, a, b)
        assert np.allclose(np.nan_to_num(R_), np.nan_to_num(R), atol=1e-12) and abs(Rm_ - Rm) < 1e-12 and days_ == days


def test_book_return_matches_backtest_formula():
    d = T.build()
    (t, R, Rm, days), (t2, *_) = ST.periods(d, [2020])[:2]
    rng = np.random.default_rng(0)
    n = len(d["names"])
    w = np.where(rng.random(n) < 0.05, rng.normal(0, 0.02, n), 0.0) * d["elig"][t]
    w2 = np.where(rng.random(n) < 0.05, rng.normal(0, 0.02, n), 0.0) * d["elig"][t2]
    a, b = _rec(d, t, w, -0.1), _rec(d, t2, w2, -0.05)
    got, Rm_, days_, net = FW.book_return(d, a, b, "b")
    want = float((w * np.nan_to_num(R)).sum() + -0.1 * Rm) - ST.COST * (np.abs(w2 - w).sum() + abs(-0.05 + 0.1))
    assert abs(got - want) < 1e-12 and abs(net - (w.sum() - 0.1)) < 1e-12


def test_unobserved_period_is_none():
    d = T.build()
    t = len(d["S"]) - 1                                   # decided on the last close: close(t+1) not yet known
    a, b = _rec(d, t - 5, np.zeros(len(d["names"])), 0.0), _rec(d, t, np.zeros(len(d["names"])), 0.0)
    assert FW.period(d, a, b) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
