# Partial-universe run (kept as the record of an incident)

The weekly run of 2026-10-07 22:15 UTC (local runner) decided this week from 299 of the 500 S&P names.
launchd started the job with a 256 open-file limit, and the screen's parallel price download lost
201 names ("unable to open database file"). The book was committed at 23:27 UTC; nothing was traded.

The fix (PR #65) raises the limit for every job; under launchd the same download prices 500 of 501.
By the owner's decision (2026-10-08 ~01:10 UTC), the week was re-decided on the full universe, well
before the Thursday 19:00 UTC deadline and before any trade. The rerun's files are one level up.
This run is kept unchanged and is not scored.
