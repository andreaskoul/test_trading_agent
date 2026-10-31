"""SEC EDGAR acceptance times in US Eastern (the clock the market and the session rules use).

The live API (data.sec.gov/submissions/CIK*.json) writes acceptanceDateTime in true UTC ("...Z"). Verified
2026-10-31 on Apple's filing index pages, where SEC shows the acceptance in Eastern time: 0000320193-24-000005,
"Accepted 2024-02-01 16:30:30", reads "2024-02-01T21:30:30.000Z" in the API. The code had read it as Eastern clock
time, which puts a release made during market hours one session late.

SEC's bulk submissions.zip is not a substitute. It mixes encodings for the same field:
* on 31,973 filings of 8 large filers it read 4 or 5 hours later than the API (UTC plus the Eastern offset);
* on a sample of other filers it matched the API (true UTC) for 7% of filings and all of those in an odd-hour sample.

So no single conversion is right for it. Use the live API for acceptance times.
"""

import pandas as pd

ET = "America/New_York"


def et_from_api(s):
    """Eastern clock time (naive) of a live-API acceptanceDateTime (a string, or a naive Timestamp holding UTC)."""
    t = pd.Timestamp(s)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return t.tz_convert(ET).tz_localize(None)
