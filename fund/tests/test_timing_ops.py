"""Contracts for the 2026-10-31 operational changes: the go-live gate's records, the cost statistic, price
provenance, the late-served news audit, the decision ledger and the entry-day "priced in" log.

    python fund/tests/test_timing_ops.py          (or pytest, if installed)

Fixtures (fund/tests/fixtures/timing/) are trimmed copies of the live record on fund-data as of 2026-10-30: the
lifecycle fills, each session's live record status, a real news check (2026-10-29), the lifecycle events and frozen
returns, and the 2026-10-28 cohort's desk inputs (MSFT and GOOGL, whose earnings came after the as-of close).
"""
import json
import os
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(HERE, "fixtures", "timing")
sys.path.insert(0, os.path.dirname(HERE))
import attribution as A                                           # noqa: E402
import news_audit as NA                                           # noqa: E402
import ops_stats as O                                             # noqa: E402

SESSIONS = json.load(open(os.path.join(FX, "sessions.json")))


def test_gate_reads_lifecycle_records():
    # The failure class: under Protocol 7 the gate read retired execution.json files and showed 0% executed.
    share, bad = O.executed_share(["2026-10-14", "2026-10-21"], os.path.join(FX, "live"), SESSIONS)
    assert share == 1.0 and bad == {"2026-10-14": [], "2026-10-21": []}
    with tempfile.TemporaryDirectory() as d:                     # a session without a submitted record fails its week
        for f in os.listdir(os.path.join(FX, "live")):
            shutil.copy(os.path.join(FX, "live", f), d)
        os.remove(os.path.join(d, "2026-10-20.json"))
        share, bad = O.executed_share(["2026-10-14", "2026-10-21"], d, SESSIONS)
        assert share == 0.5 and bad["2026-10-14"] == ["2026-10-20"] and bad["2026-10-21"] == []


def test_cost_is_the_signed_value_weighted_mean():
    F = pd.read_csv(os.path.join(FX, "fills_lifecycle.csv"))
    c = O.cost_stats(F)
    G = F[F["slip_bp"].notna() & (F["filled_qty"] > 0)]
    v = G["filled_qty"] * G["fill"]
    assert c["n"] == len(G) and abs(c["mean_bp"] - (G["slip_bp"] * v).sum() / v.sum()) < 1e-9
    assert c["upper95_bp"] > c["mean_bp"] and c["fill_rate"] == 1.0
    assert c["upper95_bp"] < 5.0                                   # the registered 5 bp/side is conservative here
    assert abs(c["median_abs_bp"] - G["slip_bp"].abs().median()) < 1e-9


def test_price_provenance_and_unchanged_prices():
    # The failure class: prices() silently fell back to the previous close; the value must not change, its source
    # must now be visible.
    os.environ.setdefault("ALPACA_API_KEY", "test"); os.environ.setdefault("ALPACA_SECRET_KEY", "test")
    import broker
    snap = {"AAA": {"latestTrade": {"p": 10.0, "t": "2026-10-29T19:57:01Z"},
                    "latestQuote": {"bp": 9.99, "ap": 10.01, "t": "2026-10-29T19:57:02Z"}},
            "BBB": {"latestTrade": None, "dailyBar": None, "prevDailyBar": {"c": 20.0}}}
    real = broker.api
    broker.api = lambda method, path, body=None, base=None: (200, snap)
    try:
        assert broker.prices(["AAA", "BBB"]) == {"AAA": 10.0, "BBB": 20.0}
        q = broker.quotes(["AAA", "BBB"])
        assert q["AAA"]["src"] == "latestTrade" and q["AAA"]["bid"] == 9.99 and q["AAA"]["trade_ts"]
        assert q["BBB"]["src"] == "prevDailyBar" and q["BBB"]["trade_ts"] is None
    finally:
        broker.api = real


def test_news_audit_counts_an_article_served_late():
    rec = json.load(open(os.path.join(FX, "news_2026-10-29.json")))
    checked = {i: k for i, k in rec["lots"].items() if k.get("status") == "checked" and k.get("headlines")}
    target = sorted(checked)[0]
    hi = rec["close_ts"]

    def fetch(t, lo, hi_):
        i = next(i for i in rec["lots"] if i.split("|")[-1] == t)
        arts = [{"headline": h, "datetime": hi - 3600, "source": "x"} for h in rec["lots"][i].get("headlines") or []]
        if i == target:                                            # published 30 min before the cutoff, served later
            arts.append({"headline": "Late served item", "datetime": hi - 1800, "source": "late"})
        return arts

    a = NA.audit_day(rec, {}, fetch=fetch)
    assert a["lots"][target]["n_missed"] == 1 and a["lots"][target]["missed"][0]["lag_lb_min"] > 0
    assert sum(L.get("n_missed", 0) for i, L in a["lots"].items() if i != target) == 0


def test_decision_ledger_rows_and_one_value_by_hand():
    rep = A.build(os.path.join(FX, "base"))
    ev = json.load(open(os.path.join(FX, "base", "lifecycle", "state.json")))["events"]
    n_live = sum(1 for e in ev if e["action"] not in A.SKIP and "|" in e["id"]
                 and np.sign(e["to"] if e["action"] in A.ADD else e["from"]))
    assert sum(r["book"] == "live" for r in rep["rows"]) == n_live
    R = pd.read_csv(os.path.join(FX, "base", "lifecycle", "returns.csv"), parse_dates=["date"]).pivot_table(
        index="date", columns="ticker", values="ret")
    beta = {r["ticker"]: r["beta_hedge"] for r in json.load(open(os.path.join(FX, "base", "2026-10-07", "screen.json")))["rows"]}
    row = next(r for r in rep["rows"] if r["book"] == "live" and r["ticker"] == "MRVL" and r["action"] == "entry"
               and r["day"] == "2026-10-08")
    d1 = R.index[R.index > pd.Timestamp("2026-10-08")][0]
    assert abs(row["y1"] - (R.at[d1, "MRVL"] - beta["MRVL"] * R.at[d1, "SPY"])) < 1e-12
    assert all(c["t"] is None or c["weeks"] >= 5 for c in rep["stats"])   # no t-statistic below 5 weeks


def test_ledger_agreement_reproduces_rule_a():
    # Rule A's applicability count (reports/research/p8/E_SOFT_READ.md): live soft entries from the 2026-10-15
    # session whose side matches the residual move on the news session, 7 of 12. The ledger must give the same.
    rep = A.build(os.path.join(FX, "base"))
    R = [r for r in rep["rows"] if r["book"] == "live" and r["action"] == "entry" and r["class"] == "soft"
         and r["day"] >= "2026-10-15" and r.get("agree") is not None]
    assert (sum(r["agree"] for r in R), len(R)) == (7, 12)
    orcl = next(r for r in R if r["ticker"] == "ORCL")             # short on 10-15 after a -7% residual day: agrees
    assert orcl["side"] == -1 and orcl["news_session"] == "2026-10-14" and orcl["news_move"] < -0.05 and orcl["agree"] == 1
    lo, hi = A.wilson(7, 12)
    assert abs(lo - 0.32) < 0.01 and abs(hi - 0.81) < 0.01


def test_ledger_segments_add_up_by_hand():
    # One real lot (MRVL, entered long 2026-10-08): its per-session rows are side x (r - beta r_SPY) for each session
    # after entry up to its closing event, numbered from 1; 'before entry' is the move from the as-of close to entry.
    ev = json.load(open(os.path.join(FX, "base", "lifecycle", "state.json")))["events"]
    R = pd.read_csv(os.path.join(FX, "base", "lifecycle", "returns.csv"), parse_dates=["date"]).pivot_table(
        index="date", columns="ticker", values="ret")
    coh = A.cohort_info(os.path.join(FX, "base"))
    rows = [r for r in A.segments(ev, coh, R, "live") if r["id"] == "2026-10-07|MRVL"]
    b = coh["2026-10-07"]["beta"]["MRVL"]
    res = R["MRVL"] - b * R["SPY"]
    held = [r for r in rows if r["k"] >= 1]
    shut = min(e["day"] for e in ev if e["id"] == "2026-10-07|MRVL" and e["action"] != "entry" and abs(e["to"]) < 1e-9)
    assert [r["k"] for r in held] == list(range(1, len(held) + 1)) and held[-1]["day"] == shut
    assert all(abs(r["y"] - res[pd.Timestamp(r["day"])]) < 1e-12 for r in held)       # long: side = +1
    assert all(r["seg"] == ("1-3" if r["k"] <= 3 else "4-15" if r["k"] <= 15 else "16+") for r in held)
    pre = next(r for r in rows if r["seg"] == "before entry")
    assert abs(pre["y"] - res[(res.index > pd.Timestamp("2026-10-07")) & (res.index <= pd.Timestamp("2026-10-08"))].sum()) < 1e-12


def test_live_record_carries_the_a3_log():
    # The failure class (2026-11-05): run() built 7B A3's log of stopped soft views, but the live record writer copied
    # only a2, so lifecycle/live/<day>.json never showed what A3 stopped.
    src = open(os.path.join(os.path.dirname(HERE), "lifecycle.py")).read()
    assert '"a2": lv.get("a2"), "a3": lv.get("a3")' in src


def test_rebuild_diff_names_the_first_day_that_differs():
    # #140 (2026-11-05): the determinism check failed with no clue where. On a real NAV series (the account's, from
    # fund/tests/fixtures/core) and the real lifecycle events, a one-cent change on one day must be reported with both
    # values and that day.
    st = json.load(open(os.path.join(FX, "base", "lifecycle", "state.json")))
    nav = pd.read_csv(os.path.join(HERE, "fixtures", "core", "nav.csv"))
    a = {"rows": [{"date": d, "nav": float(v)} for d, v in zip(nav["date"], nav["equity"])], "events": st["events"]}
    rows = [dict(r) for r in a["rows"]]
    rows[5]["nav"] += 0.01
    d = O.rebuild_diff(a, {"rows": rows, "events": st["events"][:-1]})
    assert d["first_nav_diff"]["date"] == rows[5]["date"] and abs(d["first_nav_diff"]["diff"] - 0.01) < 1e-9
    assert len(d["events_only_first"]) == 1 and d["events_only_second"] == [] and d["dates_only_first"] == []
    assert O.rebuild_diff(a, a)["first_nav_diff"] is None


def test_ledger_tags_structural_and_priced_in_entries():
    # 7B A2 exempts structural lots from B1 (2026-11-05: FIS and ORCL entered with p_entry 1.5). Entry rows carry the
    # label and the entry decision's priced-in fraction, read from the live records' entry_check.
    base = os.path.join(FX, "base")
    ev = json.load(open(os.path.join(base, "lifecycle", "state.json")))["events"]
    coh = A.cohort_info(base)
    R = pd.read_csv(os.path.join(base, "lifecycle", "returns.csv"), parse_dates=["date"]).pivot_table(
        index="date", columns="ticker", values="ret")
    ec = {"2026-10-08": {"MRVL": {"p_entry": 1.5, "priced_in_entry": True}}}
    rows = A.rows_of(ev, coh, R, "live", ec)
    m = next(r for r in rows if r["ticker"] == "MRVL" and r["action"] == "entry" and r["day"] == "2026-10-08")
    assert m["p_entry"] == 1.5 and m["priced_in"] is True and m["structural"] is False
    other = next(r for r in rows if r["action"] == "entry" and r["day"] != "2026-10-08")
    assert other["priced_in"] is None                                # no entry_check logged for that day
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "lifecycle", "live"))
        json.dump({"entry_check": ec["2026-10-08"]}, open(os.path.join(tmp, "lifecycle", "live", "2026-10-08.json"), "w"))
        assert A.entry_checks(tmp) == ec
    finally:
        shutil.rmtree(tmp)


def test_entry_day_check_sees_the_move_after_the_signal_close():
    # The failure class: GOOGL's earnings came after the 2026-10-28 close; the desk's p was 0 and H 24, while the
    # stock had moved ~12% against SPY by the entry decision. The log must show the entry-day move and p >= 1.
    import entry_check as EC
    K = {"P_CAP": 1.5, "H_MIN": 3, "H8_MAX": 25, "STALE_AT": 2}   # Amendment 8's constants (fund/lifecycle.py)
    c = json.load(open(os.path.join(FX, "cohort_2026-10-28_entry.json")))
    R = pd.read_csv(os.path.join(FX, "base", "lifecycle", "returns.csv"), parse_dates=["date"]).pivot_table(
        index="date", columns="ticker", values="ret")
    ret = R.loc[pd.Timestamp("2026-10-29")].to_dict()             # close-based stand-in for the T-3 min return
    out = EC.entry_day_check([c], pd.Timestamp("2026-10-29"), ret, K)
    g = out["GOOGL"]
    assert g["p_desk"] == 0.0 and g["side"] == -1
    assert g["car_entry_day"] < -0.05 and g["p_entry"] >= 1 and g["priced_in_entry"]
    assert out["MSFT"]["p_entry"] < 1
    assert EC.entry_day_check([c], pd.Timestamp("2026-10-30"), ret, K) == {}   # only names entering that day


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
