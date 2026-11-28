"""Contract tests for the volatility study's data layer (research/volforecast). Each test has a planted fault that it
must reject. Run: ~/.fund-runner/venv-vol/bin/python -I research/volforecast/test_vol.py"""
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import data as DATA  # noqa: E402
import features as F  # noqa: E402

IDX = pd.bdate_range("2020-01-01", periods=300)


def _series(vals):
    return pd.Series(np.asarray(vals, float), index=IDX[:len(vals)])


def test_forward_target_window_is_t_plus_1_to_t_plus_h():
    rv = _series(np.arange(1, 101))
    for H in (1, 5, 22):
        y = F.forward_target(rv, H)
        t = 10
        assert abs(y.iloc[t] - H * np.mean(np.arange(t + 2, t + 2 + H))) < 1e-9, H   # rv[t+1..t+H] = t+2..t+H+1
        assert y.iloc[-H:].isna().all()                                            # incomplete windows dropped
        assert y.iloc[:-H].notna().all()


def test_forward_target_fault_includes_day_t():
    """Planted fault: a target that includes day t (shift 0) must disagree with the registered one."""
    rv = _series(np.arange(1, 101))
    bad = 5 * rv.rolling(5).mean().shift(-4)                                      # rv[t..t+4]
    assert (F.forward_target(rv, 5) - bad).abs().max() > 1


def test_forward_target_valid_share():
    v = np.ones(60)
    v[11:13] = np.nan                                                              # 2 of the 5 days after t=10 missing
    y5 = F.forward_target(_series(v), 5)
    assert np.isnan(y5.iloc[10])                                                   # 3/5 valid < 80%
    v[12] = 1
    y5 = F.forward_target(_series(v), 5)
    assert abs(y5.iloc[10] - 5.0) < 1e-12                                          # 4/5 valid: H x mean of valid


def _frame(n=300, seed=0):
    rng = np.random.default_rng(seed)
    r = rng.standard_normal(n) * 0.01
    c = 100 * np.exp(np.cumsum(r))
    o = c * np.exp(rng.standard_normal(n) * 0.002)
    h = np.maximum(o, c) * np.exp(np.abs(rng.standard_normal(n)) * 0.004)
    lo = np.minimum(o, c) * np.exp(-np.abs(rng.standard_normal(n)) * 0.004)
    D = pd.DataFrame({"open": o, "high": h, "low": lo, "close": c}, index=IDX[:n])
    D["ret"] = np.log(D["close"]).diff()
    D["rv"] = D["ret"] ** 2 * (1 + rng.random(n))
    D["r2"] = D["ret"] ** 2
    return D


def test_features_have_no_lookahead():
    D = _frame()
    X0 = F.common_features(D)
    t0 = 200
    D2 = D.copy()
    D2.iloc[t0 + 1:, :] = D2.iloc[t0 + 1:, :] * 3                                  # change only the future
    X1 = F.common_features(D2)
    a, b = X0.iloc[:t0 + 1], X1.iloc[:t0 + 1]
    assert np.allclose(a.values, b.values, equal_nan=True), "a feature at t moved when only t+1.. changed"


def test_lookahead_fault_is_detected():
    """Planted fault: a centred rolling mean reads the future; the same comparison must catch it."""
    D = _frame()
    t0 = 200
    D2 = D.copy()
    D2.iloc[t0 + 1:, :] *= 3
    f0 = D["rv"].rolling(5, center=True).mean().iloc[:t0 + 1]
    f1 = D2["rv"].rolling(5, center=True).mean().iloc[:t0 + 1]
    assert not np.allclose(f0.values, f1.values, equal_nan=True)


def test_masked_days_are_excluded_from_features():
    D = _frame()
    mask = pd.Series(False, index=D.index)
    mask.iloc[150] = True
    D2 = D.copy()
    D2.iloc[150, D2.columns.get_loc("rv")] = 1e3                                    # a huge report-day value
    X = F.common_features(D2, mask=mask)
    assert X["rv_w"].iloc[150:155].max() < 1                                         # never enters the averages


def test_realised_measures():
    rng = np.random.default_rng(1)
    r = rng.standard_normal(200_000) * 0.001
    m = DATA.measures(r)
    assert abs(m["rv"] - (r ** 2).sum()) < 1e-15
    assert abs(m["rs_pos"] + m["rs_neg"] - m["rv"]) < 1e-12
    assert abs(m["bv"] / m["rv"] - 1) < 0.01                                        # Gaussian: BV ~ RV
    rj = r.copy()
    rj[1000] = 0.05                                                                 # a jump
    mj = DATA.measures(rj)
    assert mj["rv"] - mj["bv"] > 0.5 * 0.05 ** 2                                    # BV is robust to the jump


def test_to15_sums_triples():
    R5 = pd.DataFrame(np.arange(78 * 2, dtype=float).reshape(2, 78), index=IDX[:2],
                      columns=[f"r{i:02d}" for i in range(1, 79)])
    R5.iloc[1, 3:6] = np.nan
    Q = F.to15(R5)
    assert Q.shape == (2, 26)
    assert Q.iloc[0, 0] == 0 + 1 + 2 and Q.iloc[0, 25] == 75 + 76 + 77
    assert np.isnan(Q.iloc[1, 1])                                                   # all three missing -> NaN


def test_early_close_truncation():
    F.EARLY = {pd.Timestamp("2020-01-02")}
    D = pd.DataFrame(np.ones((2, 26)), index=IDX[:2], columns=[f"q{i:02d}" for i in range(1, 27)])
    R = F.intraday(D, 15)
    assert R.iloc[1].notna().sum() == 14 and R.iloc[0].notna().sum() == 26          # 09:30-13:00 = 14 slots
    F.EARLY = None


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        try:
            fn()
            print("ok  ", name)
        except Exception as e:                                                       # noqa: BLE001
            fails += 1
            print("FAIL", name, repr(e)[:200])
    sys.exit(1 if fails else 0)
