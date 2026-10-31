"""SEC EDGAR acceptance times in US Eastern (the clock the market and the session rules use).

Two sources, two encodings, both written as "...Z". Verified 2026-10-31 on Apple's filing index pages, where SEC
shows the acceptance in Eastern time (0000320193-24-000005: "Accepted 2024-02-01 16:30:30"), and on 31,973 filings
of 8 large filers, where the bulk value minus the live value was +4.0 h (20,451) or +5.0 h (11,521), with one equal:

* live API (data.sec.gov/submissions/CIK*.json) gives true UTC: "2024-02-01T21:30:30.000Z" = 16:30:30 EST;
* SEC's bulk submissions.zip gives UTC plus the Eastern offset: "2024-02-02T02:30:30.000Z" for the same filing.

The code had read both as Eastern clock time. For the live API that puts a release made during market hours one
session late. For the bulk file it puts most before-open releases one session late.
"""

import pandas as pd

ET = "America/New_York"


def et_from_api(s):
    """Eastern clock time (naive) of a live-API acceptanceDateTime (a string, or a naive Timestamp holding UTC)."""
    t = pd.Timestamp(s)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return t.tz_convert(ET).tz_localize(None)


def et_from_bulk(s):
    """Eastern clock time (naive) of a bulk submissions.zip acceptanceDateTime (string, or naive Timestamp as stored)."""
    t = pd.Timestamp(str(s)[:19])                       # the value as written, without its misleading "Z"
    utc = t.tz_localize("UTC").tz_convert(ET).tz_localize(None)       # value - offset = the true UTC clock
    return et_from_api(utc)
