"""Contract tests for Protocol 11 (shadow only; fund/p11.py, research/eventrisk/PLAN.md).

    python fund/tests/test_p11.py

Fixtures (fund/tests/fixtures/p11/, made by build.py there on 2026-11-14):
* closes.csv: Alpaca SIP closes (adjusted) of the 2026-11-12 entries, ECHO and SPY, 420 days to 2026-11-11, the
  information set entry_vol used for those entries (the recomputed sigma_e equals the recorded one to 1e-15);
* p11_screen_2026-11-11.json: seven rows of a real P11 screen dry run for as-of 2026-11-11 (Alpaca closes since 2022,
  EDGAR 8-K item 2.02 acceptance times, Finnhub calendar), with its pooled multiple (c 19.85, k 9.35, 6,707 ratios);
* calendar.json: Alpaca's trading calendar 2025-01-01 .. 2027-04-30;
* rebuild/live/: the live records on fund-data as of 2026-11-14 (cohorts 09-30 .. 11-11, every live log 10-15 ..
  11-13, frozen returns, bill rates, entry volatilities, the pre-Protocol-7 news checks), trimmed to the fields the
  rebuild reads; rebuild/recorded_nav.json: the recorded NAV of every day in lifecycle/state.json.
Real positions: WMT (entered 2026-11-12, H 6, reports 11-19 before the open: inside), CRM (H 11, reports 12-02 after
the close: outside), TTD and FOX (no date on Finnhub's calendar within 100 days). ECHO has no report history (EDGAR
gives it no 8-K 2.02); its position is hypothetical (entry 2026-11-12, H 6, screen hedge beta) on its real closes.
"""
import copy
import glob
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import types

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(HERE, "fixtures", "p11")
FUND = os.path.dirname(HERE)
ROOT = os.path.dirname(FUND)
sys.path.insert(0, FUND)
os.environ.pop("FUND_DRYRUN", None)
import p11  # noqa: E402

PX = pd.read_csv(os.path.join(FX, "closes.csv"), index_col=0, parse_dates=True)
SCR = json.load(open(os.path.join(FX, "p11_screen_2026-11-11.json")))
SESS = [pd.Timestamp(s) for s in SCR["sessions"]]
LOG = json.load(open(os.path.join(FX, "rebuild", "live", "lifecycle", "live", "2026-11-12.json")))
LOTS = {L["ticker"]: L for L in LOG["lots_after"] if L["entry_day"] == "2026-11-12"}


def resid(L):
    """entry_vol's residual returns for the lot, from the fixture closes (lifecycle.py entry_vol, live entry)."""
    r = PX[[L["ticker"], "SPY"]].pct_change().dropna()
    return r[L["ticker"]] - float(L["beta"]) * r["SPY"]


def rec(t, row=None, pooled=None):
    L = LOTS[t]
    return p11.entry_record(L, SCR["rows"][t] if row is None else row, SCR["pooled"] if pooled is None else pooled, resid(L), SESS)


def echo_lot():
    r = PX[["ECHO", "SPY"]].pct_change().dropna()
    beta = 1.301108254                                                   # its hedge beta on the 2026-11-11 screen
    s = p11.sigma_entry(r["ECHO"] - beta * r["SPY"], np.zeros(len(r), bool))["sigma"]
    return {"ticker": "ECHO", "cohort": "2026-11-11", "entry_day": "2026-11-12", "H": 6, "beta": beta, "sigma_e": s, "W": s * math.sqrt(6)}


# ---------------------------------------------------------------- (a)-(d) the four positions
def test_a_report_inside_widens_and_scales_down():
    x = rec("WMT")
    assert x["defect"] is None and x["n_E"] == 1 and x["report_inside"] is True
    assert x["window"] == ["2026-11-13", "2026-11-20"] and "2026-11-19" in x["reaction_sessions"]
    assert x["masked_sessions"] == 4                                     # four past WMT reports in the 420-day window
    # by hand: H 6, one report, c* 27.7377: W11 = sigma_d sqrt(5 + c*), s = sqrt(6 / (5 + c*))
    assert abs(x["c_star"] - 27.737747725176522) < 1e-12 and abs(x["sigma_d"] - 0.01601225571598823) < 1e-15
    assert abs(x["W11"] - 0.01601225571598823 * math.sqrt(5 + 27.737747725176522)) < 1e-15
    assert abs(x["scalar"] - math.sqrt(6 / 32.737747725176522)) < 1e-15
    assert abs(x["W11"] - 0.0916172) < 1e-6 and abs(x["scalar"] - 0.4281059) < 1e-6
    assert x["W11"] > x["W"] > 0 and x["sigma_d"] * math.sqrt(6) < x["W11"] and x["scalar"] < 1
    assert x["W"] == LOTS["WMT"]["W"] and x["sigma_e"] == LOTS["WMT"]["sigma_e"]          # the live values, untouched


def test_b_no_report_inside_is_the_daily_width():
    x = rec("CRM")
    assert x["defect"] is None and x["n_E"] == 0 and x["report_inside"] is False
    assert x["window"] == ["2026-11-13", "2026-11-30"] and x["reaction_sessions"] == ["2026-12-03"]
    assert abs(x["W11"] - x["sigma_d"] * math.sqrt(11)) < 1e-15 and x["scalar"] == 1.0
    assert x["sigma_d"] < x["sigma_e"]                                  # past report days left out of the quiet-day vol


def test_c_no_calendar_date_is_a_defect_and_shadow_equals_live():
    for t in ("TTD", "FOX"):
        x = rec(t)
        assert SCR["rows"][t]["calendar"] == [] and SCR["rows"][t]["n_firm"] == 12
        assert x["defect"] == "no_calendar_date" and x["report_inside"] is None
        assert x["W11"] == LOTS[t]["W"] and x["scalar"] == 1.0


def test_d_no_report_history_is_a_defect_and_shadow_equals_live():
    L = echo_lot()
    row = SCR["rows"]["ECHO"]
    assert row["n_firm"] == 0 and row["report_sessions"] == []
    r = PX[["ECHO", "SPY"]].pct_change().dropna()
    x = p11.entry_record(L, row, SCR["pooled"], r["ECHO"] - L["beta"] * r["SPY"], SESS)
    assert x["defect"] == "no_report_history" and x["W11"] == L["W"] and x["scalar"] == 1.0
    # the same row with a calendar date inside the window is still the defect (PLAN: fewer than one past report)
    x2 = p11.entry_record(L, {**row, "calendar": [["2026-11-17", "bmo"]]}, SCR["pooled"], r["ECHO"] - L["beta"] * r["SPY"], SESS)
    assert x2["defect"] == "no_report_history" and x2["W11"] == L["W"] and x2["report_inside"] is True


def test_no_pooled_multiple_and_no_screen_are_defects_that_alert():
    x = rec("WMT", pooled={"c": None, "k": None})
    assert x["defect"] == "no_pooled_multiple" and x["W11"] == LOTS["WMT"]["W"] and x["scalar"] == 1.0
    L = LOTS["WMT"]
    y = p11.entry_record(L, None, None, pd.Series(dtype=float), [])
    assert y["defect"] == "no_p11_screen" and y["W11"] == L["W"]
    assert {"no_pooled_multiple", "no_p11_screen", "input_mismatch"} == set(p11.ALERT)


def test_input_contract_catches_inputs_that_do_not_reproduce_the_entry():
    L = {**LOTS["CRM"], "sigma_e": LOTS["CRM"]["sigma_e"] * 1.05}       # the recorded sigma_e is not what the closes give
    x = p11.entry_record(L, SCR["rows"]["CRM"], SCR["pooled"], resid(LOTS["CRM"]), SESS)
    assert x["defect"] == "input_mismatch" and x["W11"] == L["W"]


# ---------------------------------------------------------------- (e) the study's multiples
def _study():
    import importlib.util
    spec = importlib.util.spec_from_file_location("eventrisk_study", os.path.join(ROOT, "research", "eventrisk", "study.py"))
    S = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(S)
    return S


def _panel(seed=7, T=900, N=40):
    rng = np.random.default_rng(seed)
    S = pd.bdate_range("2019-01-02", periods=T)
    vol = rng.uniform(0.01, 0.03, N)
    e = pd.DataFrame(rng.standard_normal((T, N)) * vol, index=S, columns=[f"F{i}" for i in range(N)])
    E = pd.DataFrame(False, index=S, columns=e.columns)
    for i, c in enumerate(e.columns):
        E.iloc[(i * 7) % 63 + 100::63, i] = True                       # a report every 63 sessions
    mult = rng.uniform(2, 6, N)
    e = e.where(~E, e * mult)                                            # firm-specific report-day variance
    return e, E


def test_e_multiples_reproduce_the_study():
    S = _study()
    e, E = _panel()
    sd_s = S.sigma(e.mask(E)).ffill(limit=1)
    sd_p = p11.sd_daily(e, E)
    pd.testing.assert_frame_equal(sd_s, sd_p)
    a, b = S.multiples(e, E, sd_s), p11.multiples(e, E, sd_p)
    pd.testing.assert_frame_equal(a[0], b[0])
    for u, v in zip(a[1:], b[1:]):
        assert np.array_equal(np.isnan(u), np.isnan(v)) and np.allclose(u, v, equal_nan=True, rtol=0, atol=1e-12)
    assert np.isfinite(b[1][-1]) and 1 <= b[2][-1] <= 200                 # the pooled c and k are formed on this panel
    # a firm with no ratio gets the pooled multiple (Decision 2)
    E2 = E.copy(); E2["F0"] = False
    _, c_t, _, cs = p11.multiples(e, E2, p11.sd_daily(e, E2))
    assert abs(cs[-1, 0] - c_t[-1]) < 1e-12
    # the residual definition is the study's (load), on real closes
    r = PX.pct_change(fill_method=None)
    names = [c for c in PX.columns if c != "SPY"]
    lo, hi = np.minimum(-2 * r["SPY"], 4 * r["SPY"]), np.maximum(-2 * r["SPY"], 4 * r["SPY"])
    w = r[names].clip(lower=lo, upper=hi, axis=0)
    ols = w.rolling(252, min_periods=200).cov(r["SPY"]).div(r["SPY"].rolling(252, min_periods=200).var(), axis=0)
    ref = r[names].sub((2 / 3 * ols + 1 / 3).shift(1).mul(r["SPY"], axis=0))
    pd.testing.assert_frame_equal(ref, p11.residuals(r[names], r["SPY"]))


def test_pooled_multiple_needs_200_past_ratios():
    e, E = _panel(N=3, T=600)
    _, c_t, k_t, cs = p11.multiples(e, E, p11.sd_daily(e, E))
    assert np.isnan(c_t).all() and np.isnan(cs).all()                    # too few ratios: no pooled multiple


def test_ratios_are_frozen_at_first_computation():
    e, E = _panel(N=5, T=500)
    q = p11.ratios(e, E, p11.sd_daily(e, E))
    s0 = q["F1"].dropna().index[0]
    q2, new = p11.freeze_ratios(q, {("F1", s0): 123.0})
    assert q2.at[s0, "F1"] == 123.0 and ("F1", s0) not in new and len(new) == int(q.notna().sum().sum()) - 1


def test_catalyst_session_is_lifecycle_unchanged():
    import ast
    src = open(os.path.join(FUND, "lifecycle.py")).read()
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "catalyst_session")
    ns = {"pd": pd}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "lifecycle.py", "exec"), ns)
    for e in (("2026-11-19", "bmo"), ("2026-12-02", "amc"), ("2027-02-01", ""), ("2026-11-26", "bmo"), ("2026-11-21", "dmh"), None):
        assert ns["catalyst_session"](e, SESS) == p11.catalyst_session(e, SESS)


# ---------------------------------------------------------------- (h) the tests can fail: planted faults
def test_h_planted_faults_are_caught():
    L = LOTS["WMT"]
    e = resid(L)
    masked = p11.entry_record(L, SCR["rows"]["WMT"], SCR["pooled"], e, SESS)
    unmasked = p11.entry_record(L, {**SCR["rows"]["WMT"], "report_sessions": []}, SCR["pooled"], e, SESS)
    assert abs(unmasked["sigma_d"] - L["sigma_e"]) < 1e-15                # masking disabled: sigma_d is sigma_e again
    assert masked["sigma_d"] < L["sigma_e"] - 1e-4 and masked["W11"] != unmasked["W11"]
    # the report one session later than the window: no longer inside
    late = p11.entry_record(L, {**SCR["rows"]["WMT"], "calendar": [["2026-11-20", "amc"]]}, SCR["pooled"], e, SESS)
    assert late["n_E"] == 0 and late["scalar"] == 1.0
    # a shifted calendar (the study's placebo) changes n_E
    shifted = p11.entry_record(L, {**SCR["rows"]["WMT"], "calendar": [["2026-12-19", "bmo"]]}, SCR["pooled"], e, SESS)
    assert shifted["n_E"] == 0 and masked["n_E"] == 1


# ---------------------------------------------------------------- audit
def test_audit_row_against_hand_arithmetic():
    x = rec("WMT")
    win = [s for s in SESS if s > pd.Timestamp("2026-11-12")][:6]
    ew = np.array([0.001, -0.002, 0.0, 0.003, 0.05, -0.004])            # the report session (11-19) is the fifth
    row = p11.audit_row("k", x, ew, win)
    assert abs(row["realised_window"] - float((ew ** 2).sum())) < 1e-18 and abs(row["e2_report"] - 0.05 ** 2) < 1e-18
    assert abs(row["ratio_shadow"] - row["realised_window"] / x["W11"] ** 2) < 1e-15
    assert abs(row["forecast_report"] - x["c_star"] * x["sigma_d"] ** 2) < 1e-18
    bad = p11.audit_row("k", x, np.r_[ew[:5], np.nan], win)
    assert bad["note"] == "missing_returns" and math.isnan(bad["ratio_shadow"])
    assert p11.removal_rule([{"ratio_shadow": 1.0}] * 99)["decided"] is False
    rr = p11.removal_rule([{"ratio_shadow": 2.0}] * 100)
    assert rr["decided"] and rr["outside_0.7_1.5"]


# ---------------------------------------------------------------- (f) the NAV proof, (g) failure injection
CAL = json.load(open(os.path.join(FX, "calendar.json")))


def _fake_broker():
    from zoneinfo import ZoneInfo
    m = types.ModuleType("broker")
    m.ET, m.DATA = ZoneInfo("America/New_York"), "offline"

    def api(method, path, body=None, base=None):
        if path.startswith("/v2/calendar"):
            q = dict(x.split("=") for x in path.split("?", 1)[1].split("&"))
            return 200, [c for c in CAL if q["start"] <= c["date"] <= q["end"]]
        raise RuntimeError(f"offline test: no network ({path[:40]})")
    m.api = api
    return m


def _lifecycle(state):
    """fund/lifecycle.py as the reconcile job runs it (`daily` mode), offline: the module's own code with the broker's
    calendar served from the fixture, no new closes (every day is already frozen in returns.csv) and no new bill rate
    (every day is in rf_used.csv). The recorded days apply the live logs exactly as the nightly rebuild does."""
    import common
    common.STATE = state
    sys.modules["broker"] = _fake_broker()
    src = open(os.path.join(FUND, "lifecycle.py")).read()
    src = src[:src.index('\nif mode == "trade":')]
    ns = {"__name__": "lifecycle_offline", "__file__": os.path.join(FUND, "lifecycle.py")}
    argv = sys.argv
    sys.argv = ["lifecycle.py", "daily"]
    try:
        exec(compile(src, os.path.join(FUND, "lifecycle.py"), "exec"), ns)
    finally:
        sys.argv = argv
    ns["closes"] = lambda tickers, start, end: pd.DataFrame()
    ns["rf_daily"] = lambda: pd.Series(dtype=float)
    return ns


def _hashes(root, skip=None):
    out = {}
    for p in sorted(glob.glob(os.path.join(root, "**", "*"), recursive=True)):
        if os.path.isfile(p) and not (skip and skip in p):
            out[os.path.relpath(p, root)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def _state():
    d = tempfile.mkdtemp()
    shutil.copytree(os.path.join(FX, "rebuild", "live"), os.path.join(d, "live"))
    return d


def _p11_active(state, residuals_of=None, gate="2026-11-12"):
    """What Protocol 11 writes, on the same state: the screen's file in the 11-11 week, then the nightly stage."""
    shutil.copy(os.path.join(FX, "p11_screen_2026-11-11.json"), os.path.join(state, "live", "2026-11-11", "p11_screen.json"))
    old = p11.P11_SHADOW
    p11.P11_SHADOW = pd.Timestamp(gate)
    try:
        return p11.nightly(state=state, residuals_of=residuals_of or (lambda L, sessions: resid(L)))
    finally:
        p11.P11_SHADOW = old


def _dump(st):
    return json.dumps({k: st[k] for k in ("rows", "lots", "events", "cohorts", "reviews", "ext_done")}, sort_keys=True, default=str)


def test_f_nav_proof_rebuild_identical_with_and_without_p11():
    rec_nav = json.load(open(os.path.join(FX, "rebuild", "recorded_nav.json")))
    state = _state()
    try:
        before = _hashes(state)
        L0 = _lifecycle(state)
        st0 = L0["run"](fetch_news=False)                                # Protocol 11 inactive
        got = {r["date"]: r["nav"] for r in st0["rows"]}
        assert set(got) == set(rec_nav["nav"]) and len(got) == 27
        assert all(abs(got[d] - v) < 0.005 for d, v in rec_nav["nav"].items()), "the offline rebuild must be the recorded book"
        assert sorted(L["id"] for L in st0["lots"]) == rec_nav["lots"]
        assert _hashes(state) == before                                 # the rebuild itself wrote nothing new
        st = _p11_active(state)
        assert st["status"] == "ok" and st["new"] == 6 and st["counts"] == {"ok": 4, "no_calendar_date": 2}, st
        after = _hashes(state, skip=os.path.join("lifecycle", "p11"))
        assert {k: v for k, v in after.items() if not k.endswith("p11_screen.json")} == before   # nothing else changed
        assert sorted(k for k in _hashes(state) if k not in before) == [
            "live/2026-11-11/p11_screen.json", "live/lifecycle/p11/entries.json", "live/lifecycle/p11/status.json"]
        L1 = _lifecycle(state)
        st1 = L1["run"](fetch_news=False)                                # Protocol 11 active (its files present)
        assert [r["nav"] for r in st1["rows"]] == [r["nav"] for r in st0["rows"]]        # bit-identical NAV
        assert _dump(st1) == _dump(st0)                                  # lots, events, reviews byte-identical
        ck0, ck1 = L0["checks"](st0), L1["checks"](st1)
        assert ck0 == ck1 and not ck1["fails"]
        # the shadow values are only in p11's own file, never in a lot
        assert not any(k in L for L in st1["lots"] for k in ("W11", "scalar", "sigma_d", "n_E"))
        E = json.load(open(os.path.join(state, "live", "lifecycle", "p11", "entries.json")))
        assert E["2026-11-11|WMT|2026-11-12"]["W11"] > E["2026-11-11|WMT|2026-11-12"]["W"]
        # frozen at first write: a second night changes no record
        snap = open(os.path.join(state, "live", "lifecycle", "p11", "entries.json"), "rb").read()
        assert _p11_active(state)["new"] == 0
        assert open(os.path.join(state, "live", "lifecycle", "p11", "entries.json"), "rb").read() == snap
    finally:
        shutil.rmtree(state, ignore_errors=True)


def test_f_before_the_gate_nothing_is_written():
    state = _state()
    try:
        before = _hashes(state)
        assert p11.nightly(state=state) is None                          # P11_SHADOW 2026-11-16: no entry yet
        assert p11.screen(state=state, asof="2026-11-11") is None
        assert _hashes(state) == before
        assert p11.status("nightly", state=state) == "ok"
    finally:
        shutil.rmtree(state, ignore_errors=True)


def test_g_failures_are_non_blocking_and_set_a_non_ok_status():
    state = _state()
    try:
        before = _hashes(state)

        def boom(L, sessions):
            raise ConnectionError("Alpaca down")
        st = _p11_active(state, residuals_of=boom)
        assert st["status"] != "ok" and "shadow_error:ConnectionError" in st["status"] and st["new"] == 0
        assert "6 of 6 entries without a shadow record" in st["status"]
        assert {k: v for k, v in _hashes(state, skip=os.path.join("lifecycle", "p11")).items() if not k.endswith("p11_screen.json")} == before
        old = p11.P11_SHADOW
        p11.P11_SHADOW = pd.Timestamp("2026-11-12")
        try:
            assert p11.status("nightly", state=state, now=pd.Timestamp.now(tz="UTC").tz_localize(None)) == st["status"]
            assert p11.status("nightly", state=state, now=pd.Timestamp.now(tz="UTC").tz_localize(None) + pd.Timedelta(days=2)).startswith("stale")
            os.remove(os.path.join(state, "live", "lifecycle", "p11", "status.json"))
            assert "missing" in p11.status("nightly", state=state)
        finally:
            p11.P11_SHADOW = old
        # the next night succeeds: the records are written then (an error is never frozen as a record)
        assert _p11_active(state)["new"] == 6
        # the audit stage raising: counted, the entries kept
        real = p11.audit_row
        p11.audit_row = lambda *a, **k: (_ for _ in ()).throw(ValueError("planted"))
        try:
            shutil.copy(os.path.join(state, "live", "lifecycle", "returns.csv"), os.path.join(state, "returns.bak"))
            R = pd.read_csv(os.path.join(state, "live", "lifecycle", "returns.csv"))
            extra = pd.DataFrame([{"date": d.strftime("%Y-%m-%d"), "ticker": t, "ret": 0.0} for d in pd.bdate_range("2026-11-16", "2026-11-20") for t in ("WMT", "SPY")])
            pd.concat([R, extra]).to_csv(os.path.join(state, "live", "lifecycle", "returns.csv"), index=False)
            st3 = _p11_active(state)
            assert "shadow_error:ValueError audit" in st3["status"]
        finally:
            p11.audit_row = real
        # with the window passed, the audit writes one row for the one report window (WMT)
        st4 = _p11_active(state)
        assert st4["status"] == "ok" and st4["audit_rows"] == 1
        # the screen stage failing (no network): a shadow_error status, nothing else written
        sys.modules["broker"] = _fake_broker()
        os.environ["FUND_ASOF"] = "2026-11-18"
        os.makedirs(os.path.join(state, "live", "2026-11-18"))
        json.dump({"rows": [{"ticker": "WMT"}]}, open(os.path.join(state, "live", "2026-11-18", "screen.json"), "w"))
        out = p11.screen(state=state, asof="2026-11-18")
        assert out["status"].startswith("shadow_error:RuntimeError") and p11.status("screen", state=state).startswith("shadow_error")
        assert not os.path.exists(os.path.join(state, "live", "p11", "ratios.csv"))
    finally:
        os.environ.pop("FUND_ASOF", None)
        shutil.rmtree(state, ignore_errors=True)


def test_g_audit_on_real_frozen_returns():
    """The 11-12 WMT window ends 11-20; on the recorded returns to 11-13 nothing is audited yet."""
    state = _state()
    try:
        st = _p11_active(state)
        assert st["audit_rows"] == 0 and st["report_inside"] == 1
    finally:
        shutil.rmtree(state, ignore_errors=True)


def test_g_live_path_never_reads_p11():
    """No module of the trading path imports p11 or reads its files; the runner steps cannot fail a job."""
    for f in glob.glob(os.path.join(FUND, "*.py")):
        if os.path.basename(f) in ("p11.py", "ledger.py"):
            continue
        if os.path.basename(f) == "lifecycle_rules.py":                  # the date gate only, imported by p11 alone
            assert "import p11" not in open(f).read()
            continue
        src = open(f).read()
        assert "p11" not in src and "P11" not in src.replace("P11_SHADOW = ", ""), f
    led = open(os.path.join(FUND, "ledger.py")).read()
    i = led.index("def p11_block")
    j = led.index("P11 = {\"error\"", i)
    assert "try:\n    P11 = p11_block()" in led[i:j + 30] and "except Exception" in led[i:j + 30]
    run = open(os.path.join(FUND, "local", "runner.py")).read()
    for title in ("Protocol 11 (shadow) · weekly screen", "Protocol 11 (shadow) · screen status (issue when not ok)",
                  "Protocol 11 (shadow) · entries and audit", "Protocol 11 (shadow) · nightly status (issue when not ok)"):
        k = run.index(title)
        step = run[k:run.index("j.step(", k + 1) if "j.step(" in run[k + 1:] else len(run)]
        assert 'when="always", allow_fail=True' in step, title
    # the nightly steps run after the live rebuild and the control, before the records are committed
    assert run.index("python fund/lifecycle.py control") < run.index("python fund/p11.py nightly") < run.index('COMMIT_EXEC.format(copy=COPY_EXEC, msg=f"execution {mode}")')
    assert run.index('"python fund/lifecycle.py desk"') < run.index("python fund/p11.py screen") < run.index('Commit memo and performance')


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
            print("ok", k)
