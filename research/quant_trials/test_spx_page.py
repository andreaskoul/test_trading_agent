"""Contract tests for the shadow-page numbers (spx_forward.page): every figure must equal an independent computation.

    python test_spx_page.py
"""

import numpy as np
import pandas as pd
from scipy import stats as sps

import features as F
import spx_forward as FW
import strategies as ST

TOL = 1e-12
RNG = np.random.default_rng(7)


def weeks(n):
    days = RNG.choice([7, 7, 7, 6, 8], n).astype(float)               # holidays move a period by a day
    spy = RNG.normal(0.002, 0.02, n)
    s = np.where(RNG.random(n) < 0.7, ST.UP, ST.DOWN)
    mrate = (0.04 + ST.MARGIN_SPREAD) * days / 360
    book = RNG.normal(0.0005, 0.012, n)
    turnover = RNG.uniform(0.1, 0.6, n)
    return days, spy, s, mrate, book, turnover


def test_series_stats_equal_backtest_stats():
    for n in (26, 60):
        days, spy, s, mrate, book, turnover = weeks(n)
        total = s * spy + book - np.maximum(s - 1, 0) * mrate
        ref = ST.stats(pd.DataFrame({"days": days, "book": book, "total": total, "spy": spy, "s": s, "mrate": mrate,
                                     "turnover": turnover}))
        got = FW.series_stats(total, spy, s, mrate, days, turnover)
        assert abs(got["ann"] * 100 - ref["book_sleeve_pct_yr"]) < TOL * 100
        assert abs(got["vs_spy"] * 100 - ref["vs_spy_pct_yr"]) < TOL * 100
        assert abs(got["vs_rm"] * 100 - ref["vs_risk_matched_pct_yr"]) < TOL * 100
        assert abs(got["sharpe"] - ref["sharpe"]) < 1e-9
        assert abs(got["max_dd"] * 100 - ref["max_dd_pct"]) < TOL * 100
        assert abs(got["turnover_ann"] * 100 - ref["turnover_pct_yr"]) < 1e-9
        assert abs(got["cum"] - (np.prod(1 + total) - 1)) < TOL


def test_nothing_annualised_before_26_weeks():
    days, spy, s, mrate, book, turnover = weeks(25)
    got = FW.series_stats(book, spy, s, mrate, days, turnover)
    assert got["ann"] is None and got["vs_spy"] is None and got["vs_rm"] is None and got["sharpe"] is None
    assert got["cum"] is not None and got["max_dd"] is not None


def test_ic_stats():
    x = RNG.normal(0.02, 0.1, 40)
    for h in (5, 20):
        got = FW.ic_stats(x, h)
        t = F.nw_t(x, max(4, h - 1))
        assert abs(got["t"] - t) < TOL and abs(got["p"] - sps.norm.sf(t)) < TOL and abs(got["mean"] - x.mean()) < TOL


def _synthetic(n_weeks, ic_fn, seed=0):
    """Records and a ledger with fixed weekly rows and ICs (no prices needed): page() only reads these."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2026-10-29", periods=n_weeks * 5 + 1, freq="B")
    th = [d for d in dates if d.weekday() == 3][: n_weeks + 1]
    recs = [{"asof": str(d.date()), "models": "live_2026-10-26", "sleeve": {"spy": 700.0, "ma200": 650.0, "s": ST.UP},
             "dtb3": 0.04, "dtb3_date": str(d.date()), "expected_names": 500, "coverage": {}, "excluded_members": [],
             "books": {b: {"weights": {"AAA": 0.25, "BBB": -0.25}, "w_spy": -0.1, "scale": 1.0} for b in FW.BOOKS}}
            for d in th]
    pl, ic = [], []
    for a, b in zip(recs[:-1], recs[1:]):
        for bk in FW.BOOKS:
            book, spy, net = rng.normal(0, 0.01), rng.normal(0.002, 0.02), -0.1
            mrate = (0.04 + ST.MARGIN_SPREAD) * 7 / 360
            total = ST.UP * spy + book - max(ST.UP + net - 1, 0) * mrate
            pl.append({"bk": bk, "asof": a["asof"], "to": b["asof"], "start": a["asof"], "end": b["asof"], "book": book,
                       "total": total, "spy": spy, "s": ST.UP, "s_next": ST.UP, "net": net, "turnover": 0.3,
                       "mrate": mrate, "days": 7})
    for k, r in enumerate(recs[:-1]):
        for bk, (m, strat, h) in FW.BOOKS.items():
            for hh in sorted({h, 5, 20}):
                ic.append({"book": bk, "asof": r["asof"], "h": hh, "n": 500, "ic": ic_fn(bk, hh, k)})
        for h in (5, 10):
            ic.append({"book": f"rec_ridge_h{h}", "asof": r["asof"], "h": h, "n": 500, "ic": ic_fn("ridge", h, k)})
    # every book's weeks share the same SPY row in reality: make them so
    first = {r["asof"]: r for r in pl if r["bk"] == "fw_master_h5"}
    for r in pl:
        f = first[r["asof"]]
        r["spy"] = f["spy"]
        r["total"] = ST.UP * r["spy"] + r["book"] - max(ST.UP + r["net"] - 1, 0) * r["mrate"]
    return recs, {"pl": pl, "ic": ic}


def test_page_lines_and_book_totals():
    recs, led = _synthetic(30, lambda bk, h, k: 0.01)
    pg = FW.page(recs, led, "2027-06-01")
    n = len(pg["weeks"])
    assert n == 30 and len(pg["lines"]["dates"]) == n + 1
    for b in pg["books"]:
        ser = pg["lines"]["series"][b["key"]]
        assert ser[0] == 0.0 and abs(ser[-1] - b["cum"]) < TOL and len(ser) == n + 1
        tot = np.array([w["total"] for w in b["weekly"]])
        assert abs(np.prod(1 + tot) - 1 - b["cum"]) < TOL
    W = pd.DataFrame(pg["weeks"])
    sbar = W.s.mean()
    rm = sbar * W.spy - max(sbar - 1, 0) * W.mrate
    assert abs(pg["lines"]["series"]["risk_matched"][-1] - (np.prod(1 + rm) - 1)) < TOL
    timing = W.s * W.spy - ST.COST * (W.s_next - W.s).abs() - np.maximum(W.s - 1, 0) * W.mrate
    assert abs(pg["lines"]["series"]["sleeve"][-1] - (np.prod(1 + timing) - 1)) < TOL
    assert abs(pg["lines"]["series"]["spy"][-1] - (np.prod(1 + W.spy) - 1)) < TOL


def test_stop_rule_uses_exactly_the_first_26_ic_weeks():
    bad = lambda bk, h, k: (-0.05 + 0.01 * np.sin(k)) if bk == "fw_master_h20" else 0.02 + 0.01 * np.cos(k)
    recs, led = _synthetic(25, bad)
    st = {b["key"]: b["status"] for b in FW.page(recs, led, "x")["books"]}
    assert st["fw_master_h20"].startswith("running (25 of 26")
    recs, led = _synthetic(26, bad)
    st = {b["key"]: b["status"] for b in FW.page(recs, led, "x")["books"]}
    assert st["fw_master_h20"] == "retired (stop rule)" and st["fw_master_h5"] == "running"
    # later weeks never change the 26-week verdict: strongly positive ICs after week 26
    late = lambda bk, h, k: bad(bk, h, k) if k < 26 else 0.5
    recs, led = _synthetic(40, late)
    st = {b["key"]: b["status"] for b in FW.page(recs, led, "x")["books"]}
    assert st["fw_master_h20"] == "retired (stop rule)"


def test_review_holm_over_four_books_on_first_52_weeks():
    def f(bk, h, k):
        base = {"fw_master_h5": 0.03, "fw_master_h20": 0.0, "fw_c2ft_h20": 0.01, "fw_ensemble": 0.04}.get(bk, 0.005)
        return base + 0.02 * np.sin(1.7 * k + len(bk))
    recs, led = _synthetic(52, f)
    pg = FW.page(recs, led, "x")
    rev = {b["key"]: b["review"] for b in pg["books"] if "review" in b}
    assert set(rev) == {"fw_master_h5", "fw_master_h20", "fw_c2ft_h20", "fw_ensemble"}
    ps = {k: v["p"] for k, v in rev.items()}
    order = sorted(ps, key=ps.get)
    adj, run = {}, 0.0
    for i, k in enumerate(order):                                      # Holm (1979), written out independently
        run = max(run, min(1.0, (4 - i) * ps[k]))
        adj[k] = run
    for k in rev:
        assert abs(rev[k]["p_holm"] - adj[k]) < TOL
        ridge = np.array([f("rec_ridge" if FW.BOOKS[k][2] != 20 else "fw_ridge_h20", FW.BOOKS[k][2], j)
                          for j in range(52)])
        own = np.array([f(k, FW.BOOKS[k][2], j) for j in range(52)])
        if FW.BOOKS[k][2] != 20:
            ridge = np.array([f("ridge", 5, j) for j in range(52)])
        assert abs(rev[k]["vs_ridge"] - (own - ridge).mean()) < TOL
        assert rev[k]["supported"] == (adj[k] < 0.05 and rev[k]["vs_ridge"] > 0)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
