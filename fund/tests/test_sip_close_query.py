"""Contract test: the reconcile's second close source (Alpaca SIP daily bar) must ask for a window Alpaca answers at
the reconcile's own time, 01:10 UTC (20:10 or 21:10 New York) after the session.

History.
* 2026-11-20: end = day + 1 was refused with 403 "subscription does not permit querying recent SIP data"; all 258
  priced fills since 2026-10-01 had an empty close_alpaca. PR #187 changed the end to the session's date.
* 2026-11-21 and 11-24 01:10 UTC (sessions 11-20 and 11-23, both reconciles since): still 403. The PR #187 check used a past date (end 2026-11-19 asked on
  2026-11-20), so it could not fail. Alpaca reads a date-only end as the end of that day in New York; at 01:10 UTC
  that is still about four hours ahead, inside the 15-minute recent-data limit.

Real fixture, observed 2026-11-24 21:34 UTC (read-only probe, SPY and AAPL):
* end 2026-11-24 -> 403; end 2026-11-24T23:00:00Z -> 403;
* end 2026-11-24T21:05:00Z -> 200, bars t 2026-11-24T05:00:00Z, AAPL c 354.07, SPY c 718.78 (= yfinance closes);
* start = end = 2026-11-23 (date-only, asked the next day) -> 200.
The model below encodes exactly that: a date-only end means New York midnight at the end of that date, an instant end
means itself; Alpaca refuses any end later than now - 15 minutes; a bar is returned when its t (New York midnight of
the session) is within [start, end].

execute.py runs at import, so the function is taken from its source, as test_p11 does for catalyst_session.
"""
import ast
import os
from urllib.parse import parse_qs, urlparse

import pandas as pd

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "execute.py")
NY = "America/New_York"


def load():
    tree = ast.parse(open(SRC).read())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "sip_close_query")
    ns = {"pd": pd}
    exec(compile(ast.Module([fn], []), SRC, "exec"), ns)
    return ns["sip_close_query"]


def params(q):
    return {k: v[0] for k, v in parse_qs(urlparse(q).query).items()}


def instant(v, *, is_end):
    """Alpaca's reading of a start/end parameter, as observed (see the module docstring)."""
    if "T" in v:
        return pd.Timestamp(v).tz_convert("UTC")
    d = pd.Timestamp(v).tz_localize(NY)
    return (d + pd.Timedelta(days=1) if is_end else d).tz_convert("UTC")


def answer(q, now_utc, session):
    """(status, bar returned) under the observed rules."""
    p = params(q)
    start, end = instant(p["start"], is_end=False), instant(p["end"], is_end=True)
    if end > now_utc - pd.Timedelta(minutes=15):
        return 403, False
    bar_t = pd.Timestamp(session).tz_localize(NY).tz_convert("UTC")
    return 200, start <= bar_t <= end


def reconcile_time(session):
    """The runner's reconcile: 01:10 UTC on the day after the session."""
    return (pd.Timestamp(session) + pd.Timedelta(days=1)).tz_localize("UTC") + pd.Timedelta(hours=1, minutes=10)


def test_model_reproduces_the_observed_answers():
    now = pd.Timestamp("2026-11-24 21:34", tz="UTC")
    base = "/v2/stocks/bars?symbols=SPY,AAPL&timeframe=1Day&feed=sip&adjustment=raw"
    assert answer(base + "&start=2026-11-24&end=2026-11-24", now, "2026-11-24") == (403, False)
    assert answer(base + "&start=2026-11-24&end=2026-11-24T23:00:00Z", now, "2026-11-24") == (403, False)
    assert answer(base + "&start=2026-11-24&end=2026-11-24T21:05:00Z", now, "2026-11-24") == (200, True)
    assert answer(base + "&start=2026-11-23&end=2026-11-23", now, "2026-11-23") == (200, True)


def test_the_reconcile_gets_the_session_bar():
    """Winter (EST), summer (EDT), the DST change weeks, and a 13:00 early close; the date-only end fails all."""
    f = load()
    for session in ["2026-11-19", "2026-11-24", "2026-11-27", "2026-07-15", "2026-03-09", "2026-11-02",
                    "2026-12-31"]:
        q = f(["AAPL", "SPY"], pd.Timestamp(session))
        assert answer(q, reconcile_time(session), session) == (200, True), (session, q)


def test_request_shape():
    p = params(load()(["AAPL", "SPY"], pd.Timestamp("2026-11-24")))
    assert p["start"] == "2026-11-24" and p["end"] == "2026-11-24T21:00:00Z"      # 16:00 EST
    assert p["symbols"] == "AAPL,SPY" and p["feed"] == "sip" and p["adjustment"] == "raw" and p["timeframe"] == "1Day"
    assert params(load()(["SPY"], pd.Timestamp("2026-07-15")))["end"] == "2026-07-15T20:00:00Z"   # 16:00 EDT


def test_failure_controls():
    """The two earlier windows must fail the reconcile-time check (they did fail live)."""
    for session in ["2026-11-19", "2026-11-24"]:
        d = pd.Timestamp(session).date()
        for end in [d, d + pd.Timedelta(days=1)]:          # PR #187 and the original day + 1
            q = f"/v2/stocks/bars?symbols=SPY&timeframe=1Day&feed=sip&adjustment=raw&start={d}&end={end}"
            assert answer(q, reconcile_time(session), session)[0] == 403, (session, end)


def test_status_is_logged_not_swallowed():
    src = open(SRC).read()
    assert "if s_ != 200:" in src and "Alpaca closes unavailable (HTTP" in src


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
