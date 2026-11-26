"""Contracts for the cross-asset read's guard (xasset_lib.PRE2003_GUARD), checks and read script.

    python research/xasset/test_xasset.py          (or pytest)

Fault-injection tests use synthetic series only: no pre-2003 return of real data is computed by any test. Real-data
tests read the frozen caches through the guard (2003+ only) and are skipped if the caches are absent.
"""
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xasset_lib as L                                              # noqa: E402
import xasset_checks as C                                           # noqa: E402
import xasset_read as R                                             # noqa: E402

G = L.PRE2003_GUARD
HAVE = os.path.isdir(L.FREE_CACHE) and os.path.isdir(L.PROXY_CACHE) and os.path.isdir(L.CHECK_CACHE)


def _raises(fn, exc=L.Pre2003Error):
    try:
        fn()
    except exc:
        return True
    return False


def _fake_pst(start="2001-06-01", end="2004-06-30"):
    d = pd.bdate_range(start, end)
    rng = np.random.default_rng(3)
    px = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(d))))
    return pd.DataFrame({"PRICE": px, "ADJ": px, "PRICE_CONTRACT": 20000300, "CARRY": px, "CARRY_CONTRACT": 1,
                         "FORWARD": px, "FORWARD_CONTRACT": 2}, index=d)


# ------------------------------------------------------------------ the guard
def test_derived_raises_on_pre2003_outside_read():
    s = pd.Series(1.0, index=pd.date_range("2002-12-30", "2003-01-03"))
    assert _raises(lambda: G.derived(s, "t"))
    assert G.derived(s[s.index >= "2003-01-01"], "t2").index.min() >= L.VALID_START


def test_deliberate_fault_leaky_loader_is_caught():
    """Fault: a frame that still holds pre-2003 dates (as a loader without the guard would return) reaches a
    construction. The construction's `derived` must raise; with the guard's raw() applied it must not."""
    fake = _fake_pst()
    assert _raises(lambda: L.pst_excess_daily("FAKE", frame=fake))
    ok = L.pst_excess_daily("FAKE", frame=G.raw(fake, "fake"))
    assert ok.index.min() >= L.VALID_START


def test_deliberate_fault_registry_check_fails():
    bad = {"x": pd.Series([1.0], index=[pd.Timestamp("2002-12-31")])}
    assert _raises(lambda: G.assert_clean(bad), AssertionError)
    G.assert_clean({"y": pd.Series([1.0], index=[pd.Timestamp("2003-01-02")])})


def test_raw_masks_and_synthetic_refuses_real_data():
    s = pd.Series(1.0, index=pd.date_range("2002-12-01", "2003-02-01"))
    assert G.raw(s, "t").index.min() == L.VALID_START
    with G.synthetic():
        assert _raises(lambda: G.raw(s, "t"))
        assert G.derived(s, "t").index.min() < L.VALID_START          # synthetic dates are allowed
    assert G.mode is None


def test_level_check_only_from_its_caller_and_derived_still_raises():
    def other():
        with G.level_check():
            pass
    assert _raises(other)

    def pre2003_level_counts():                                       # the admitted caller's name
        with G.level_check():
            s = pd.Series(1.0, index=pd.date_range("2002-12-30", "2003-01-02"))
            assert len(G.raw(s, "t")) == 4                            # levels visible
            assert _raises(lambda: G.derived(s, "t"))                 # returns / statistics are not
    pre2003_level_counts()
    assert G.mode is None


def test_coverage_mode_returns_presence_only():
    def coverage_counts():
        with G.coverage():
            s = pd.Series([3.5, np.nan, 7.25], index=pd.date_range("1990-01-01", periods=3))
            p = G.raw(s, "t")
            assert p.iloc[0] == 1.0 and np.isnan(p.iloc[1]) and p.iloc[2] == 1.0
    coverage_counts()

    def not_allowed():
        with G.coverage():
            pass
    assert _raises(not_allowed)


def test_read_mode_lock_first_and_once():
    with tempfile.TemporaryDirectory() as d:
        lock = os.path.join(d, "READ.lock")

        def run_read():
            with G.read(lock, {"t": 1}):
                assert os.path.exists(lock)                           # created before anything inside runs
                s = pd.Series(1.0, index=pd.date_range("1990-01-01", periods=3))
                assert G.derived(s, "t").index.min().year == 1990
        run_read()
        assert _raises(run_read)                                      # lock exists: refuses
        assert G.mode is None

        def not_run_read():
            with G.read(os.path.join(d, "other.lock"), {}):
                pass
        assert _raises(not_run_read)
        assert not os.path.exists(os.path.join(d, "other.lock"))


# ------------------------------------------------------------------ Amendment 1: fixed mirror convention
def _mirror_fixture():
    """Synthetic: the mirror equals PRICE on even sessions and CARRY (2 % away) on odd ones."""
    d = pd.bdate_range("2010-01-01", periods=200)
    px = pd.Series(100.0 + np.arange(200) * 0.01, index=d)
    j = pd.DataFrame({"PRICE": px, "PRICE_CONTRACT": 20100300, "CARRY": px * 1.02, "CARRY_CONTRACT": 20100600,
                      "FORWARD": px * 1.04, "FORWARD_CONTRACT": 20100900}, index=d)
    j["CH"] = np.where(np.arange(200) % 2 == 0, j.PRICE, j.CARRY)
    return j


def test_deliberate_fault_per_date_convention_is_rejected():
    """Fault: choosing, per date, whichever column is nearest makes every session 'agree' (100 %). The level check
    must refuse a per-date convention and, with the fixed column, count only the true agreement (50 %)."""
    j = _mirror_fixture()
    per_date = pd.Series(np.where(np.arange(len(j)) % 2 == 0, "PRICE", "CARRY"), index=j.index)
    assert _raises(lambda: C.level_agreement(j, per_date), ValueError)
    assert _raises(lambda: C.level_agreement(j, ["PRICE"] * len(j)), ValueError)
    assert _raises(lambda: C.mirror_pair("GOLD", per_date), ValueError)
    comp, agree, ident, _ = C.level_agreement(j, "PRICE")
    assert comp.all() and abs(agree.mean() - 0.5) < 1e-9 and abs(ident.mean() - 0.5) < 1e-9


def test_roll_days_around_convention_contract_changes():
    d = pd.bdate_range("2010-01-01", periods=40)
    lab = pd.Series([1] * 20 + [2] * 20, index=d)
    roll = C._roll_days(lab)
    change = d[20]
    assert roll[20] and not roll[0] and not roll[-1]
    assert all(roll[i] == (abs((d[i] - change).days) <= C.ROLL_WINDOW_DAYS) for i in range(40))


# ------------------------------------------------------------------ the read script
def test_read_refuses_without_a_passing_committed_gate():
    keep = L.CHECKS_OUT
    try:
        L.CHECKS_OUT = os.path.join(tempfile.gettempdir(), "no_such_CHECKS_XASSET.json")
        assert _raises(R.preflight, SystemExit)
    finally:
        L.CHECKS_OUT = keep
    if os.path.exists(L.CHECKS_OUT) and json.load(open(L.CHECKS_OUT)).get("gate") != "pass":
        assert _raises(R.preflight, SystemExit)
    assert not os.path.exists(L.LOCK)


def test_synthetic_path_runs_and_writes_no_lock():
    keep = R.DRAWS
    R.DRAWS = 50
    try:
        with G.synthetic():
            res = R.run_all(R.synthetic_world(0.0, 5), additional=False)["primary"]
    finally:
        R.DRAWS = keep
    assert res["verdict"] in ("supported", "rejected", "inconclusive")
    assert not os.path.exists(L.LOCK)


# ------------------------------------------------------------------ real data (2003+ only)
def test_check_helpers_produce_nothing_before_2003():
    if not HAVE:
        print("skip: caches absent")
        return
    G.registry.clear()
    C.commodity_pair("GOLD", "GC=F")
    L.intl_bond_monthly("UK")
    L.bond_future_monthly("UK")
    L.fx_excess("JPY", monthly=True)
    L.fx_excess("DEM", monthly=False)
    L.us_tsy("US10", monthly=True)
    assert G.registry
    G.assert_clean()
    assert min(v.index.min() for v in G.registry.values() if len(v)) >= L.VALID_START


def test_checks_file_holds_no_pre2003_statistic():
    if not os.path.exists(L.CHECKS_OUT):
        print("skip: no CHECKS_XASSET.json")
        return
    d = json.load(open(L.CHECKS_OUT))
    assert d["mask_check"]["earliest_date"] >= "2003-01-01"
    for k, v in d["markets"].items():
        if "window" in v:
            assert v["window"][0] >= "2003-01-01", k
    for k, v in d["level_checks_pre2003"].items():                   # counts only, keyed by decade
        assert set(v) <= {"applicable", "mirror", "convention", "by_decade_pre2003", "reason", "input_defect",
                          "pre2003_compared_sessions", "pre2003_agree", "pre2003_identical_4sd",
                          "pre2003_share_agree", "pre2003_share_identical_4sd", "passes"}, k
        assert v.get("convention") in (None, "PRICE", "CARRY", "FORWARD"), k        # one fixed column
        for dec, c in v.get("by_decade_pre2003", {}).items():
            assert dec.endswith("0s") and set(c) == {"common_sessions", "compared_sessions", "agree_within_0.5pct",
                                                     "identical_4_sig_digits"}
    assert "doubt" in d and "breadth_gate" in d


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        try:
            fn()
            print("ok  ", name)
        except Exception as e:                                       # noqa: BLE001
            fails += 1
            print("FAIL", name, repr(e)[:300])
    sys.exit(1 if fails else 0)
