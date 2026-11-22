# R3: survivorship bound on MASTER's 2020-2025 book (reused window; descriptive, not a test)

*Run by a branch agent; saved by the coordinating session. Numbers from `RESULT.json`. Same code, configuration and
seeds 0-4; annual walk-forward refits 2020-2025; 60 fits, 95.6 MPS hours.*

**Repair.** The MASTER S&P 500 panel was missing 79 names, 11,589 of 152,654 eligible name-weeks (7.6%). 15 names
had no prices at all, mostly 2024-26 takeovers and the 2023 bank failures; the price vendor drops delisted tickers.
* Filled from Alpaca daily bars (the cached chunks plus a targeted 2016-2024 fetch): 99.3% of the missing name-weeks
  now have y5, and 96.1% are scoreable.
* Untouched names are unchanged (asserted).
* Delisting returns were declared before any fit: −100% for FDIC failures, −30% for unexplained ends, takeovers at
  the last close. 57 events: 35 takeovers, 19 renames, 3 FDIC.

| | ORIG (retrained) | REPAIRED | Paired difference |
|---|---:|---:|---|
| Weekly IC (NW t) | 0.0340 (3.30) | 0.0293 (2.61) | −0.0047 (t −0.97) |
| Decile book, %/yr arithmetic (Sharpe) | 5.40 (0.810) | 4.22 (0.705) | −1.19 %/yr (t −0.86) |
| Whole fund (trend core + book), %/yr compounded (Sharpe) | 22.08 (0.949) | 20.09 (0.909) | Sharpe −0.040 (LW HAC SE 0.063, p 0.52) |

* The saved as-run scores give IC 0.0326, book Sharpe 0.77 and fund 21.69 %/yr (0.937). The retrained ORIG agrees:
  score correlation 0.986, IC +0.0014 (t 0.80).
* Seed noise: the sd of single-seed IC is 0.009 in either arm. Per-seed IC differences are −0.0095, +0.0019,
  −0.0010, −0.0080, −0.0083.
* By year, the REPAIRED book is weaker in 2021 (−3.9 against −1.6) and 2025 (3.9 against 9.4), and stronger in 2022-23.
* The repaired names themselves: 77 held (7.8% of book gross), contributing +0.34 %/yr (t 0.67).
  * Removing them leaves the REPAIRED book unchanged (4.23 %/yr).
  * The difference comes from the model retrained on the fuller cross-section ranking ordinary names differently,
    plus seed noise.
  * Delisting returns net −0.21% over six years: SIVB and SBNY were long at −100%, FRC short.

**Side findings.**
* The yfinance PARA column is corrupt for 2020-22 (closes about 80,000).
* Exited tickers are reused for other securities in yfinance (LB, INFO, SBNY, FB); eligibility masks them.
* `broad/symbols.json` lacks several S&P names (AVB, EQR, EA, BK, MMC, HOLX, K, IPG).

Files: `r3.py`, `report.py`, `fetch_extra.py`, `workers.sh`, `RESULT.json`, `CHECKS.json`, `STATE.json`;
`.cache/tree/r3/`.
