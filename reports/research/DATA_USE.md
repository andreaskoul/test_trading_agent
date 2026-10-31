# Data-use ledger

Append-only. One row per read of a data window by a hypothesis or a family. Before any locked read, its row is added
with the lock file. After the read, the result's path is added to that row. The purpose:

* to know, for any window, how many hypotheses have looked at it;
* to keep a "fresh" window fresh.

The ledger was started on 2026-10-30 with Family E (PREREG_family_E.md), backfilled from the records below. Counts
are hypotheses whose statistic was computed. Tests that could not be built (p = 1 by rule) are not counted.

## Reads to date

| # | window | universe | family / hypotheses | n read | kind | date | record |
|---|---|---|---|---|---|---|---|
| 1 | 2012–2021 | S&P 500 point in time; S&P 400 current | Family H fit (H1, H3a, H3b, H4, H5) | 5 | fit, open | 2026-10-2x | `p8/fit_results.md`, `p8/DRY_FIT.lock` |
| 2 | 2012–2021 | S&P 500 point in time; S&P 400 current | earnings decay (SUE and CAR, h = 1…120), descriptive | 2 | fit, open | 2026-10-2x | `p8/decay_earnings.md` |
| 3 | 2012–2021 | S&P 500 members (survivors, yfinance) | technicals: gap levels, follow-through settings (27 tried) | — | fit, open | 2026-10-07/08 | `technicals_backtest.md` |
| 4 | 2022–2025 | S&P 500 members (survivors) | technicals pre-registration 1 (levels) and 2 (5 follow-through variables) | 6 | holdout, once | 2026-10-07/08 | `technicals_backtest.md` |
| 5 | 2022–2025 | 31-name panel | quant trials (news embeddings), 3 candidates | 3 | holdout, once | 2026-10-16 | `quant_trials/CONFIRM.md`, `DECISION.md` |
| 6 | 2013–2025 (incl. 2022–25) | S&P 500 | refit five-factor model | 1 | one read | 2026-10-2x | `quant_trials/SP500.md` |
| 7 | 2013–2025 (incl. 2022–25) | S&P 500 | transformers: 4 models × 3 horizons | 12 | one read | 2026-10-2x | `quant_trials/SP500_TRANSFORMERS.md` |
| 8 | 2013–2025 (incl. 2022–25) | S&P 500 | Timestral, zero-shot, 3 horizons | 3 | one read | 2026-10-2x | `quant_trials/SP500_TIMESTRAL.md` |
| 9 | 2022–2025 | S&P 500 point in time + S&P 400 current | Family H validation (H1, H3a, H3b, H4, H5 per universe; H4 shared) | 9 | locked | 2026-10-27 | `p8/VALIDATION_READ.lock` |
| 10 | 2026-01 – 2026-09 | S&P 400 current | Family H sealed: H1 | 1 | locked | 2026-10-27 | `p8/SEALED_READ.lock` |
| 11 | 2026-10-07 → | live | Protocols 6, 7 and 7B forward records | — | live | ongoing | `fund-data` |
| 12 | 2026 Q3 season → | S&P 500 + 400 | R5 forward predictions (read after ≥ 2 seasons) | — | forward | ongoing | `research-data`, PREREG_thesis_tree §5 |

**Running count of hypotheses read on 2022–2025: 34.** That is rows 4–9, counting the overlapping 2013–2025 reads.
Family E reports the Bonferroni p over this count plus its own reads as a diagnostic.

## Family E (pending; PREREG_family_E.md)

| # | window | universe | hypotheses | kind | lock | result |
|---|---|---|---|---|---|---|
| E-fit | 2016–2021; Finnhub 2025-11 – 2026-04 | S&P 500 point in time | E1 and E2 cell selection; E3 pipeline check | fit, open | — | `p8/E_DRY_FIT.json` (pending) |
| E-val | 2022–2025 | S&P 500 point in time | E1, E2 (m = 2) | locked | `p8/E_VALIDATION.lock` | pending |
| E-soft | 8-K 2022–2025 + Finnhub 2026-05 – 2026-10 | S&P 500 | E3 / rule A | locked | `p8/E_SOFT_READ.lock` | pending |
| E-sealed | 2026-01 – 2026-09 | S&P 500 point in time | E1 and E2 survivors | locked | `p8/E_SEALED.lock` | pending |
