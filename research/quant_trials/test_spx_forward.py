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
    got, Rm_, days_, net, dw = FW.book_return(d, a, b, "b")
    want = float((w * np.nan_to_num(R)).sum() + -0.1 * Rm) - ST.COST * (np.abs(w2 - w).sum() + abs(-0.05 + 0.1))
    assert abs(got - want) < 1e-12 and abs(net - (w.sum() - 0.1)) < 1e-12
    assert abs(dw - (np.abs(w2 - w).sum() + 0.05)) < 1e-12


def test_unobserved_period_is_none():
    d = T.build()
    t = len(d["S"]) - 1                                   # decided on the last close: close(t+1) not yet known
    a, b = _rec(d, t - 5, np.zeros(len(d["names"])), 0.0), _rec(d, t, np.zeros(len(d["names"])), 0.0)
    assert FW.period(d, a, b) is None


def test_running_mark_equals_booked_week_before_rebalance_costs():
    """At the next record's exit close, the provisional mark of a book equals its booked week plus the costs that are
    only charged at booking (turnover into the next positions, and a sleeve change)."""
    d = T.build()
    (t, R, Rm, days), (t2, *_) = ST.periods(d, [2021])[:2]
    rng = np.random.default_rng(1)
    n = len(d["names"])
    w = np.where(rng.random(n) < 0.05, rng.normal(0, 0.02, n), 0.0) * d["elig"][t]
    w2 = np.where(rng.random(n) < 0.05, rng.normal(0, 0.02, n), 0.0) * d["elig"][t2]
    a, b = _rec(d, t, w, -0.1, s=1.3), _rec(d, t2, w2, -0.05, s=0.7)
    run = FW.running(d, a)
    k = run["dates"].index(str(d["S"][t2 + 1].date()))
    book, Rm_, days_, net, dw = FW.book_return(d, a, b, "b")
    mrate = (a["dtb3"] + ST.MARGIN_SPREAD) * days_ / 360
    booked = 1.3 * Rm_ - ST.COST * abs(0.7 - 1.3) + book - max(1.3 + net - 1, 0) * mrate
    assert abs(run["series"]["b"][k] - (booked + ST.COST * dw + ST.COST * abs(0.7 - 1.3))) < 1e-12
    assert abs(run["series"]["spy"][k] - Rm_) < 1e-12 and run["series"]["b"][0] == 0.0


def test_friday_morning_shows_the_previous_week():
    """The failure class (2026-11-06): the Friday 03:45 job adds the new Thursday record before its entry close (that
    Friday) exists, so the page drew no running week, and the previous week, which ends at that close, was neither
    booked nor drawn. The page must then show the previous record's week, from its own entry close."""
    d = T.build()
    t = len(d["S"]) - 1                                   # the newest record decided on the last close
    z = np.zeros(len(d["names"]))
    prev, new = _rec(d, t - 5, z, -0.1), _rec(d, t, z, -0.1)
    assert FW.running(d, new) is None
    run = FW.current_week(d, [prev, new])
    assert run is not None and run["asof"] == prev["asof"] and run["from"] == str(d["S"][t - 4].date())
    assert run["to"] == str(d["S"][-1].date())
    older = _rec(d, t - 10, z, -0.1)                      # once the newest week has an entry close, it is the one shown
    assert FW.current_week(d, [older, prev])["asof"] == prev["asof"]
    assert FW.current_week(d, [new]) is None


def test_daily_lines_keep_booked_weeks_and_mark_closes_inside():
    """The chart's booked lines at every close: each week's end stays exactly the booked (ledger) value, and a close
    inside a week is the week's start value chained with the running mark of that week's record at that close."""
    d = T.build()
    per = ST.periods(d, [2022])[:4]
    rng = np.random.default_rng(2)
    n = len(d["names"])
    recs = []
    for t, *_ in per:
        r = _rec(d, t, np.zeros(n), 0.0, s=float(rng.choice([1.3, 0.7])))
        r["books"] = {bk: {"weights": {d["names"][i]: float(x) for i, x in enumerate(
            np.where(rng.random(n) < 0.05, rng.normal(0, 0.02, n), 0.0) * d["elig"][t]) if x},
            "w_spy": -0.1, "scale": 1.0} for bk in FW.BOOKS}
        r.update(models="x", dtb3_date=r["asof"], expected_names=n, coverage={}, excluded_members=[])
        recs.append(r)
    pl = []
    for a, b in zip(recs[:-1], recs[1:]):
        s = a["sleeve"]["s"]
        for bk in FW.BOOKS:
            book, Rm, days, net, dw = FW.book_return(d, a, b, bk)
            mrate = (a["dtb3"] + ST.MARGIN_SPREAD) * days / 360
            t, t2 = (int(np.searchsorted(d["S"], pd.Timestamp(r["asof"]))) for r in (a, b))
            pl.append({"bk": bk, "asof": a["asof"], "to": b["asof"], "start": str(d["S"][t + 1].date()),
                       "end": str(d["S"][t2 + 1].date()), "book": book, "spy": Rm, "s": s, "s_next": b["sleeve"]["s"],
                       "total": s * Rm - ST.COST * abs(b["sleeve"]["s"] - s) + book - max(s + net - 1, 0) * mrate,
                       "net": net, "turnover": dw, "mrate": mrate, "days": days})
    pg = FW.page(recs, {"pl": pl, "ic": []}, "x")
    weekly = {k: list(v) for k, v in pg["lines"]["series"].items()}
    wdates = list(pg["lines"]["dates"])
    FW.daily_lines(d, recs, pg)
    L_ = pg["lines"]
    t0, t3 = (int(np.searchsorted(d["S"], pd.Timestamp(recs[i]["asof"]))) for i in (0, -1))
    assert L_["dates"] == [str(x.date()) for x in d["S"][t0 + 1: t3 + 2]]          # every close, once
    for k, v in L_["series"].items():
        assert len(v) == len(L_["dates"])
        assert [v[L_["dates"].index(x)] for x in wdates] == weekly[k]                  # booked points unchanged
    for i, w in enumerate(pg["weeks"]):                                                # a close inside each week
        run = FW.running(d, recs[i], pg["bench"]["sbar"])
        x = run["dates"][2]
        assert x < w["end"]
        for k in ("spy", "sleeve", "risk_matched", "fw_master_h5"):
            want = (1 + weekly[k][i]) * (1 + run["series"][k][2]) - 1
            assert abs(L_["series"][k][L_["dates"].index(x)] - want) < 1e-12


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
