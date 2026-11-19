# L5_pead: post-earnings-announcement drift book — failed the development gate (no 2020-2025 read)

*Written by the branch agent; saved by the coordinating session because subagent report writes are refused.
**Development (2013-2019) only**; `READ_L5P.lock` was not created. Numbers from `RESULT.json`.*

**Gate** (paired whole-fund weekly increment, fund plus drift book minus B0): −0.095 %/yr, NW t −0.24 over 353 weeks
(needs ≥ 2.0); positive in 4 of 7 years (needs ≥ 5). **Fails.**
* By year, %: 2013 +0.10, 2014 −0.50, 2015 +1.70, 2016 −1.25, 2017 +0.10, 2018 +0.72, 2019 −1.51.
* Whole fund: B0 14.25 %/yr (Sharpe 0.957); with the book 14.13 (0.948).

**Book alone** (0.3 a side, beta-hedged, net 5 bp): +0.46 %/yr, Sharpe 0.22, NW t 0.57.
* By year, %/yr: +1.35, −1.61, +4.55, −1.47, +1.87, +0.62, −2.22 (2013-2019).
* Turnover 20.7×/yr; costs 1.03 %/yr; about 1.5 %/yr before costs, consistent with the P8 drift study.
* About 23 names a side; active in 73% of weeks.

**Gross cap (structural).** With the core at 1.3× (89% of development weeks), B0 already sits near the 1.9 gross
cap. The added book's mean scale is 0.022 in those weeks and 0.974 when the core is at 0.7×. Any additive book is
therefore traded almost only in down-trend weeks.

**Survivorship contract.** The by-name event-availability indicator has IC +0.0030 (t 1.18): passes. The
time-varying indicator has +0.0011 (t 0.47).

**Method.**
* Events: `.cache/p8/events.parquet` (S&P 500, finite SUE, 22,028 events, sha256 357390fd…6623d79). t0 re-derived
  from the acceptance time with 0 mismatches.
* `decay_earnings_events.parquet` was not used: it ends in 2021, and it keeps only events with 121 future sessions,
  a filter that looks ahead.
* Quintile breakpoints come from the prior 252 sessions' events (at least 500).
* Hold the names with t0 in [t−19, t], trading at close t+1 or later.

**Difference from the failed earnings-announcement premium** (2026-11-10): that study held announcers *through* the
report with no news; this one holds them *after* the report, signed by the surprise (underreaction).
**Caveat:** SUE uses first-filed XBRL EPS, taken as equal to the released EPS.

Files: `run.py`, `RESULT.json`, `STATE.json`, `dev.log`.
