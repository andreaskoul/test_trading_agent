"""Contracts for EDGAR acceptance times (fund/edgar_time.py).

    python fund/tests/test_edgar_time.py

Fixtures are real values for Apple's earnings 8-Ks: SEC's filing index pages show the acceptance in Eastern time
("Accepted 2023-11-02 16:30:32", "Accepted 2024-02-01 16:30:30"); the live API reads "2024-02-01T21:30:30.000Z".
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import amend7b2 as A2                                             # noqa: E402
from edgar_time import et_from_api                               # noqa: E402


def test_live_api_is_utc():
    assert et_from_api("2024-02-01T21:30:30.000Z") == pd.Timestamp("2024-02-01 16:30:30")     # EST
    assert et_from_api(pd.Timestamp("2024-02-01 21:30:30")) == pd.Timestamp("2024-02-01 16:30:30")
    assert et_from_api("2023-11-02T20:30:32.000Z") == pd.Timestamp("2023-11-02 16:30:32")     # EDT


def test_b1_session_of_a_before_open_release_in_winter():
    # The failure class: a 07:00 EST release read from the API as 12:00 "Eastern" stays on the right day only by luck;
    # one at 12:30 EST (17:30Z) was placed after the close, a session late. Converted, both are that day's session.
    days = [pd.Timestamp(d) for d in ("2026-11-02", "2026-11-03", "2026-11-04")]
    for z in ("2026-11-03T12:00:00.000Z", "2026-11-03T17:30:00.000Z"):
        rel = A2.release_session("earnings", "2026-11-03", [et_from_api(z)], None, days)
        assert rel["session"] == "2026-11-03", z
    rel = A2.release_session("earnings", "2026-11-03", [et_from_api("2026-11-03T21:05:00.000Z")], None, days)   # 16:05 EST
    assert rel["session"] == "2026-11-04"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
