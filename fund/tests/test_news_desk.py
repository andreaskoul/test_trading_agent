"""Checks for the news desk's Phase 0 pieces: the firm-name matcher, transcript windows, podcast durations.

    python fund/tests/test_news_desk.py          (or pytest, if installed)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import news_cost as NC                    # noqa: E402
import news_ingest as NI                  # noqa: E402

FIRMS, THEMED = NC.matchers()


def test_everyday_word_names_need_a_company_suffix():
    assert "TGT" not in FIRMS("Goldman Raises Price Target On Apple")
    assert "TGT" in FIRMS("Target Corp cuts its outlook")
    assert not {"NWS", "NWSA"} & FIRMS("Breaking news from the Fed")
    assert "GAP" not in FIRMS("the gap between bid and ask widened")
    assert "GAP" in FIRMS("Gap Inc shares fell")


def test_aliases_tickers_and_source_tags():
    assert "GOOGL" in FIRMS("Alphabet's Google wins a cloud deal")
    assert "META" in FIRMS("Facebook parent expands data centers")
    assert "NVDA" in FIRMS("Shares of $NVDA rose")
    assert "XOM" in FIRMS("(NYSE: XOM) said on Tuesday")
    assert "ON" not in FIRMS("turned ON the lights")             # bare short tickers never match on their own
    assert FIRMS("no names here", ["AAPL", "NOT_A_TICKER"]) == {"AAPL"}


def test_themes():
    assert THEMED("New tariffs on Chinese steel")
    assert not THEMED("A quiet day at the zoo")


def test_windows_merge_overlaps():
    segs = [[t, 5, f"s{t}"] for t in range(0, 600, 10)]
    w = NC.windows(segs, [10, 12])                               # hits at 100 s and 120 s: one merged window
    assert len(w) == 1 and segs[w[0][0]][0] == 10 and segs[w[0][-1]][0] == 210
    assert len(NC.windows(segs, [2, 50])) == 2                   # 20 s and 500 s: two windows


def test_itunes_durations():
    assert NI._secs("1:02:03") == 3723 and NI._secs("45:00") == 2700 and NI._secs("1800") == 1800
    assert NI._secs(None) is None and NI._secs("n/a") is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
