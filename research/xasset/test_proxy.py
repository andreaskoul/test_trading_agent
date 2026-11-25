"""Contracts for research/xasset/proxy.py.

    python research/xasset/test_proxy.py          (or pytest, if installed)

Two failure classes have tests that are shown to fail on a deliberate fault:
* the date mask: no computed series may have a date before 2003-01-01 (the 1962-2002 returns stay unread);
  the fault is a `validation_window` that keeps every date;
* a missing interest differential must be a typed defect that drops the observation, never a zero; the fault is a
  pipeline that fills the missing foreign rate with 0.
The fault-injection runs use synthetic series only, so no pre-2003 return of real data is ever computed. The real-data
tests read the frozen cache (.cache/xasset-proxy, sha256 in MANIFEST.json) and only through validation_window().
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proxy as P                                                   # noqa: E402

HAVE_CACHE = os.path.exists(os.path.join(P.CACHE, "fred_DGS10.csv"))


# ------------------------------------------------------------------ synthetic fixtures (not real data)
def _synthetic(start="1995-01-01", end="2010-12-31", seed=7):
    rng = np.random.default_rng(seed)
    d = pd.bdate_range(start, end)
    y = pd.Series(0.05 + np.cumsum(rng.normal(0, 0.0005, len(d))), index=d)
    rf = pd.Series(0.03 + np.cumsum(rng.normal(0, 0.0002, len(d))), index=d)
    spot = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.006, len(d)))), index=d)
    m = pd.date_range(start, end, freq="MS")
    i_f = pd.Series(0.02 + rng.normal(0, 0.001, len(m)), index=m)
    i_us = pd.Series(0.03 + rng.normal(0, 0.001, len(m)), index=m)
    return y, rf, spot, i_f, i_us


def _synthetic_pipeline():
    """Every construction on synthetic data that spans 1995-2010; returns the registry."""
    P.COMPUTED.clear()
    y, rf, spot, i_f, i_us = _synthetic()
    P.treasury_excess(P.month_end(y), rf, 10, monthly=True, name="t_m")
    P.treasury_excess(y, rf, 10, monthly=False, name="t_d")
    P.treasury_excess(P.month_end(y), rf, 10, monthly=True, method="exact", name="t_m_x")
    fx, _ = P.currency_excess(P.month_end(spot), i_f, i_us, "XXX", monthly=True, name="fx_m")
    P.currency_excess(spot, i_f, i_us, "XXX", monthly=False, name="fx_d")
    e = P.etf_excess(spot * 100, rf, monthly=True, name="e_m")
    P.pair_stats(fx, e, "syn")
    return dict(P.COMPUTED)


# ------------------------------------------------------------------ 1. the date mask
def test_validation_window_keeps_2003_on():
    s = pd.Series(1.0, index=pd.date_range("2002-12-01", "2003-02-01"))
    w = P.validation_window(s)
    assert w.index.min() == pd.Timestamp("2003-01-01") and len(w) == 32
    try:
        P.validation_window(pd.Series([1.0, 2.0]))
    except TypeError:
        pass
    else:
        raise AssertionError("a non-date index must be refused")


def test_mask_holds_on_every_construction():
    reg = _synthetic_pipeline()
    assert len(reg) >= 8
    P.assert_masked(reg)                                              # passes with the real mask


def test_mask_check_fails_on_a_deliberate_fault():
    real = P.validation_window
    P.validation_window = lambda x: x                                 # fault: no mask
    try:
        reg = _synthetic_pipeline()
    finally:
        P.validation_window = real
    try:
        P.assert_masked(reg)
    except AssertionError as e:
        assert "before 2003-01-01" in str(e)
    else:
        raise AssertionError("the mask check did not catch an unmasked pipeline")


def test_real_validation_run_is_masked():
    if not HAVE_CACHE:
        print("  SKIP: no frozen cache (run proxy.py fetch)")
        return
    out = P.run_validation()                                          # raises inside if any series is unmasked
    P.assert_masked(P.COMPUTED)
    assert out["mask_check"]["earliest_date"] >= "2003-01-01"
    assert len(P.COMPUTED) >= 40


# ------------------------------------------------------------------ 2. a missing differential is a defect, not zero
def _missing_diff_fixture():
    m = pd.date_range("2004-01-31", "2008-12-31", freq="ME")
    spot = pd.Series(np.linspace(1.0, 1.2, len(m)), index=m)
    months = pd.date_range("2004-01-01", "2008-12-01", freq="MS")
    i_f = pd.Series(0.04, index=months)
    i_us = pd.Series(0.02, index=months)
    i_f[pd.Timestamp("2005-06-01")] = np.nan                         # the foreign rate of June 2005 is missing
    i_us[pd.Timestamp("2007-03-01")] = np.nan                        # and the US rate of March 2007
    return spot, i_f, i_us


def check_missing_differential(fn):
    """fn(spot, i_f, i_us) -> (returns, defects). Raises unless the two periods that accrue over a missing rate are
    dropped and counted per currency and year."""
    spot, i_f, i_us = _missing_diff_fixture()
    r, defects = fn(spot, i_f, i_us)
    for d in ("2005-07-31", "2007-04-30"):                          # periods starting at end of June 2005 / March 2007
        assert pd.Timestamp(d) not in r.index, f"the period ending {d} has no differential but has a return"
    assert len(r) == len(spot) - 1 - 2, f"{len(r)} returns"
    by = {(x["currency"], x["year"]): x["count"] for x in defects if x["kind"] == "missing_interest_differential"}
    assert by == {("XXX", 2005): 1, ("XXX", 2007): 1}, by
    # the periods with both rates carry the 2 % differential
    k = pd.Timestamp("2005-08-31")
    dt = (k - pd.Timestamp("2005-07-31")).days / 365.0
    assert abs(r[k] - (np.log(spot[k] / spot[pd.Timestamp("2005-07-31")]) + 0.02 * dt)) < 1e-12


def test_missing_differential_is_a_defect():
    check_missing_differential(lambda s, f, u: P.currency_excess(s, f, u, "XXX", monthly=True, name="t_md"))


def test_missing_differential_check_fails_on_a_deliberate_fault():
    def faulty(s, f, u):                                              # fault: a missing rate becomes zero
        return P.currency_excess(s, f.fillna(0.0), u.fillna(0.0), "XXX", monthly=True, name="t_md_fault")
    try:
        check_missing_differential(faulty)
    except AssertionError:
        pass
    else:
        raise AssertionError("the defect check did not catch a zero-filled differential")


# ------------------------------------------------------------------ 3. construction arithmetic
def test_par_duration_and_convexity():
    y = np.array([0.01, 0.05, 0.12])
    for n in (2, 10, 30):
        D, C = P.par_duration_convexity(y, n)
        v = 1 / (1 + y / 2)
        assert np.allclose(D, (1 - v ** (2 * n)) / y, rtol=1e-12)
        # numerical second derivative of the price at par
        h = 1e-5
        price = lambda yy: P._par_price_after(y, yy, n, np.zeros_like(y))   # noqa: E731
        assert np.allclose(price(y), 1.0, atol=1e-12)
        num_c = (price(y + h) - 2 + price(y - h)) / h ** 2
        assert np.allclose(C, num_c, rtol=1e-4)


def test_taylor_matches_exact_for_a_small_move_and_flat_yield_earns_carry():
    idx = pd.to_datetime(["2010-01-31", "2010-02-28", "2010-03-31"])
    y = pd.Series([0.04, 0.041, 0.041], index=idx)
    rf = pd.Series([0.01, 0.01, 0.01], index=idx)
    a = P.treasury_excess(y, rf, 10, monthly=True, name="ta")
    b = P.treasury_excess(y, rf, 10, monthly=True, method="exact", name="tb")
    assert abs(a.iloc[0] - b.iloc[0]) < 2e-4                        # 10 bp move: second-order error is tiny
    dt = 31 / 365.0
    assert abs(a.iloc[1] - (0.041 - 0.01) * dt) < 1e-12              # no yield change: carry minus cash


# ------------------------------------------------------------------ 4. contracts on the real frozen fixtures
def test_typed_quote_direction_and_maturity():
    if not HAVE_CACHE:
        print("  SKIP: no frozen cache")
        return
    _, c = P.spot_series("JPY")
    assert c["direction"].startswith("foreign per USD")
    _, c = P.spot_series("GBP")
    assert c["direction"] == "USD per foreign"
    for sid, n in (("DGS1", 1), ("DGS10", 10), ("DGS30", 30)):
        assert P.treasury_series(sid)[1]["maturity_years"] == n


def test_declared_discontinuation_is_removed():
    if not HAVE_CACHE:
        print("  SKIP: no frozen cache")
        return
    s, c = P.treasury_series("DGS30")
    w = P.validation_window(s)                                         # presence only, 2003+
    assert c["declared_discontinuation"] == ["2002-02-18", "2006-02-09"]
    assert w["2003-01-01":"2006-02-08"].notna().sum() == 0


def test_implausible_rate_fails_its_contract():
    if not HAVE_CACHE:
        print("  SKIP: no frozen cache")
        return
    try:                                                              # Swiss call money: 2016-08 below -2 %
        P.rate_series("IRSTCI01CHM156N")
    except P.InputDefect as e:
        assert "plausible range" in str(e)
    else:
        raise AssertionError("an out-of-range rate passed its contract")


def test_frozen_file_mismatch_is_a_defect():
    if not HAVE_CACHE:
        print("  SKIP: no frozen cache")
        return
    m = P._manifest()
    real = m["files"]["fred_DGS10.csv"]["sha256"]
    orig = P._manifest
    P._manifest = lambda: {"files": {**m["files"], "fred_DGS10.csv": {**m["files"]["fred_DGS10.csv"],
                                                                         "sha256": "0" * 64}}}
    try:
        P.frozen("fred_DGS10.csv")
    except P.InputDefect:
        pass
    else:
        raise AssertionError("a changed frozen file was accepted")
    finally:
        P._manifest = orig
    assert P._sha(P.frozen("fred_DGS10.csv")) == real


if __name__ == "__main__":
    fails = 0
    for k, f in list(globals().items()):
        if k.startswith("test_") and callable(f):
            try:
                f()
                print(f"PASS {k}")
            except Exception as e:                                    # noqa: BLE001
                fails += 1
                print(f"FAIL {k}: {type(e).__name__}: {e}")
    sys.exit(1 if fails else 0)
