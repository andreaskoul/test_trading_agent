"""Contract tests for the forward beta records (research/riskfield/forward.py).

    cd research/quant_trials && PYTHONPATH=. python ../riskfield/test_forward.py
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import forward as FWD  # noqa: E402


def _bars(days, names, rng, drop=()):
    """Synthetic regular-session bars: 13 bars a day per name; `drop` = (day index, name, bar k) to remove."""
    rows = []
    px = {n: 100.0 for n in names}
    for i, d in enumerate(days):
        for n in names:
            px[n] *= np.exp(rng.normal(0, 0.005))                      # overnight
            for k in range(13):
                o = px[n]
                px[n] *= np.exp(rng.normal(0, 0.003))
                if (i, n, k) not in drop:
                    rows.append((d, n, k, o, px[n]))
    return pd.DataFrame(rows, columns=["date", "ticker", "k", "open", "close"])


def test_day_returns_match_the_research_definition():
    """Overnight = log(open of the 09:30 bar / previous 15:30 close); then 13 intraday returns; the 14 sum to the
    close-to-close log return."""
    rng = np.random.default_rng(0)
    days = pd.bdate_range("2026-09-01", periods=5)
    b = _bars(days, ["AAA", "SPY"], rng)
    R = FWD.day_returns(b, days, ["AAA", "SPY"])
    assert R.shape == (5, 14, 2)
    assert np.isnan(R[0, 0]).all()                                      # no previous close on the first day
    c = b[b.k == 12].pivot(index="date", columns="ticker", values="close")[["AAA", "SPY"]].to_numpy()
    cc = np.diff(np.log(c), axis=0)
    assert np.allclose(R[1:].sum(1), cc, atol=1e-12)


def test_a_day_missing_a_bar_or_with_a_jump_is_missing():
    rng = np.random.default_rng(1)
    days = pd.bdate_range("2026-09-01", periods=3)
    b = _bars(days, ["AAA", "SPY"], rng, drop={(1, "AAA", 5)})
    R = FWD.day_returns(b, days, ["AAA", "SPY"])
    assert np.isnan(R[1, :, 0]).all() and np.isfinite(R[1, :, 1]).all()
    b2 = b.copy()
    b2.loc[(b2.date == days[2]) & (b2.ticker == "SPY") & (b2.k == 7), "close"] *= 2.0     # a bad print
    R2 = FWD.day_returns(b2, days, ["AAA", "SPY"])
    assert np.isnan(R2[2, :, 1]).all()


def test_hf_beta_recovers_a_known_beta_and_needs_enough_days():
    rng = np.random.default_rng(2)
    T = 63
    rm = rng.normal(0, 0.004, (T, 14))
    R = np.stack([1.5 * rm + rng.normal(0, 0.001, (T, 14)), rm], -1)
    b = FWD.hf_beta(R, 1, 50)
    assert abs(b[0] - 1.5) < 0.02 and abs(b[1] - 1) < 1e-12
    R[:20, :, 0] = np.nan
    assert np.isnan(FWD.hf_beta(R, 1, 50)[0])


def test_ols_beta_is_the_funds_ingredient():
    """B0 = 2/3 x ols_beta + 1/3 must equal the shrunk beta the S&P panel builds (sp500_test.build)."""
    rng = np.random.default_rng(3)
    T = 300
    rm = rng.normal(0, 0.01, T)
    r = np.column_stack([0.8 * rm + rng.normal(0, 0.01, T), 1.3 * rm + rng.normal(0, 0.02, T)])
    r[5, 1] = np.nan
    lo, hi = np.minimum(-2 * rm, 4 * rm)[:, None], np.maximum(-2 * rm, 4 * rm)[:, None]
    w = pd.DataFrame(np.clip(r, lo, hi))
    m = pd.Series(rm)
    ref = (2 / 3) * w.rolling(252, min_periods=200).cov(m).div(m.rolling(252, min_periods=200).var(), axis=0).values + 1 / 3
    got = 2 / 3 * FWD.ols_beta(r, rm, T - 1) + 1 / 3
    assert np.allclose(got, ref[-1], atol=1e-10), (got, ref[-1])


def test_b1_uses_the_frozen_coefficients():
    import json
    c = json.load(open(FWD.FROZEN))
    assert set(c) >= {"intercept", "hf21", "hf63", "ols"}
    assert abs(FWD.b1(c, 1.0, 1.0, 1.0) - (c["intercept"] + c["hf21"] + c["hf63"] + c["ols"])) < 1e-12
    assert 0.9 < c["hf21"] + c["hf63"] + c["ols"] < 1.1                 # a blend, not a rescaling


def test_split_in_cache_forces_a_refetch(tmp=None):
    """A symbol whose overlap closes changed (split re-adjustment) is fetched again over the whole window."""
    import tempfile
    rng = np.random.default_rng(4)
    days = pd.bdate_range("2026-09-01", periods=8)
    full = _bars(days, ["AAA", "SPY"], rng)
    with tempfile.TemporaryDirectory() as d:
        FWD.BARS = os.path.join(d, "bars.parquet")
        full[full.date <= days[4]].to_parquet(FWD.BARS)                  # cached through day 4
        later = full.copy()
        later.loc[later.ticker == "AAA", ["open", "close"]] /= 2          # AAA split 2:1 after caching
        calls = []

        def fake(symbols, start, end):
            calls.append((tuple(symbols), str(start)))
            x = later[later.ticker.isin(symbols) & (later.date >= pd.Timestamp(start)) & (later.date <= pd.Timestamp(end))]
            return x.reset_index(drop=True)
        real, FWD.fetch = FWD.fetch, fake
        try:
            got = FWD.bars_for(["AAA", "SPY"], days[2:], days)
        finally:
            FWD.fetch = real
        assert calls[0][1] == str(days[4].date())                        # one overlap session
        assert (("AAA",), str(days[2].date())) in calls                   # AAA refetched over the window
        R = FWD.day_returns(got, days[2:], ["AAA", "SPY"])
        assert np.isfinite(R[1:]).all() and np.nanmax(np.abs(R)) < 0.1         # no split jump inside the window


def test_first_fetch_into_an_empty_cache_keeps_numeric_prices():
    """2026-11-07 dry run: concatenating onto an empty cache made prices objects and np.log failed."""
    import tempfile
    rng = np.random.default_rng(5)
    days = pd.bdate_range("2026-09-01", periods=4)
    full = _bars(days, ["AAA", "SPY"], rng)
    with tempfile.TemporaryDirectory() as d:
        FWD.BARS = os.path.join(d, "bars.parquet")
        real, FWD.fetch = FWD.fetch, lambda symbols, start, end: full[full.ticker.isin(symbols)].reset_index(drop=True)
        try:
            got = FWD.bars_for(["AAA", "SPY"], days, days)
        finally:
            FWD.fetch = real
        R = FWD.day_returns(got, days, ["AAA", "SPY"])
        assert np.isfinite(R[1:]).all()
        assert pd.read_parquet(FWD.BARS).close.dtype == float


def test_requests_never_ask_for_sip_bars_newer_than_15_minutes():
    """2026-11-11: the weekly screen at 22:15 UTC asked for bars to 04:00 UTC the next day; Alpaca refused every request
    (HTTP 403, recent SIP data). The end is capped at now - 16 minutes; past windows are unchanged."""
    real_now, real_get = FWD._now, FWD._get
    urls = []
    try:
        FWD._get = lambda u: urls.append(u) or {"bars": {}}
        FWD._now = lambda: pd.Timestamp("2026-11-11T22:16:00Z")          # the weekly screen's start
        FWD._chain(["AAPL"], "2026-08-01", "2026-11-11")
        assert "end=2026-11-11T22%3A00%3A00Z" in urls[-1], urls[-1]
        FWD._now = lambda: pd.Timestamp("2026-11-13T03:45:00Z")          # the Friday S&P job
        FWD._chain(["AAPL"], "2026-08-01", "2026-11-12")
        assert "end=2026-11-13T03%3A29%3A00Z" in urls[-1], urls[-1]       # Thursday's 21:00 UTC close is inside
        FWD._now = lambda: pd.Timestamp("2026-11-20T00:00:00Z")          # a past window keeps its end
        FWD._chain(["AAPL"], "2026-08-01", "2026-11-05")
        assert "end=2026-11-06T04%3A00%3A00Z" in urls[-1], urls[-1]
    finally:
        FWD._now, FWD._get = real_now, real_get


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
            print("ok", k)
