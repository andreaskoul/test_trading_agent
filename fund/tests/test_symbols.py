"""Contract: Finnhub symbols for class shares (fund/newsio.py: finnhub_symbol; CHANGELOG 2026-11-02).

    python fund/tests/test_symbols.py

The failure class: the screen and the kill checks asked Finnhub for BRK-B and BF-B (Yahoo's form) and got no articles,
so both names had no news (checked live 2026-11-01: BRK.B 249 October articles, BRK-B 0; BF.B 21, BF-B 0). The fetch
is checked here on the URL it would send, with no network call.
"""
import os
import sys
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import newsio                                                    # noqa: E402


def test_class_shares_keep_the_dot():
    for t in ("BRK.B", "BF.B", "AAPL"):
        assert newsio.finnhub_symbol(t) == t


def test_kill_check_fetch_sends_the_dot():
    seen = []

    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, *a):
            return b"[]"

    real, os.environ["FINNHUB_API_KEY"] = urllib.request.urlopen, os.environ.get("FINNHUB_API_KEY", "dummy")
    urllib.request.urlopen = lambda url, timeout=None: (seen.append(url), R())[1]
    try:
        newsio.finnhub_news("BRK.B", pd.Timestamp("2026-10-01", tz="UTC"), pd.Timestamp("2026-10-02", tz="UTC"))
    finally:
        urllib.request.urlopen = real
    assert seen and "symbol=BRK.B&" in seen[0], seen


def test_screen_uses_finnhubs_symbol():
    src = open(os.path.join(os.path.dirname(HERE), "screen.py")).read()
    assert "company-news?symbol={finnhub_symbol(t)}" in src and "company-news?symbol={ymap" not in src


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
