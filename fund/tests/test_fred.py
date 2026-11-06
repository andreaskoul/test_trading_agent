"""Contract: FRED downloads are content-checked and retried (fund/common.py: fred_series; CHANGELOG 2026-11-07).

    python fund/tests/test_fred.py

The failure class: one bad FRED response (not the CSV) failed the weekly scoring step on 2026-10-21 (pandas
"Expected 1 fields in line 5, saw 3") and the research books' run on 2026-10-22, whose empty fallback then crashed on
its date filter. The good response is the head of the real DTB3 file; no network call is made.
"""
import io
import os
import sys
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import common                                                    # noqa: E402

GOOD = open(os.path.join(HERE, "fixtures", "fred", "DTB3_head.csv"), "rb").read()
HTML = b"<!DOCTYPE html>\n<html>\n<head><title>FRED</title></head>\n<body>\n<p>Service unavailable, try again</p>\n</body></html>\n"


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _serve(*bodies):
    calls = []

    def urlopen(url, timeout=None):
        calls.append(url)
        b = bodies[min(len(calls), len(bodies)) - 1]
        if isinstance(b, Exception):
            raise b
        return _Resp(b)
    return urlopen, calls


def _with(urlopen, fn):
    old = urllib.request.urlopen
    urllib.request.urlopen = urlopen
    try:
        return fn()
    finally:
        urllib.request.urlopen = old


def test_good_csv_parses_to_fractions():
    u, calls = _serve(GOOD)
    s = _with(u, lambda: common.fred_series("DTB3", wait=0))
    assert len(calls) == 1 and isinstance(s.index, pd.DatetimeIndex) and len(s) >= 30
    assert abs(s.iloc[0] - 0.0133) < 1e-12                       # 1954-01-04, 1.33% in the file


def test_bad_response_then_good_is_retried():
    for bad in (HTML, b"", OSError("connection reset"), GOOD.replace(b"DTB3", b"DGS10", 1)):
        u, calls = _serve(bad, GOOD)
        s = _with(u, lambda: common.fred_series("DTB3", wait=0))
        assert len(calls) == 2 and len(s) >= 30, bad


def test_always_bad_fails_loudly_after_three():
    u, calls = _serve(HTML)
    try:
        _with(u, lambda: common.fred_series("DTB3", wait=0))
    except RuntimeError as e:
        assert "after 3 attempts" in str(e) and len(calls) == 3
    else:
        raise AssertionError("no error")


def test_qshadow_fallback_is_dated_and_filters():
    import qshadow
    old = qshadow.fred_series
    qshadow.fred_series = lambda fid: (_ for _ in ()).throw(RuntimeError("FRED down"))
    try:
        rf = qshadow.dtb3()
    finally:
        qshadow.fred_series = old
    assert rf.empty and isinstance(rf.index, pd.DatetimeIndex)
    assert rf[rf.index < pd.Timestamp("2026-10-21")].empty      # the 2026-10-22 crash: an integer index here


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
