# Tree search, phase 2: plan

*2026-11-12, after the phase-1 holdout read. Plan only: nothing here has run.*

## What phase 1 settled

* The S&P 500 daily price panel 2009–2025 is spent for stock selection. 114 configurations; no finalist passed; the
  development leads over MASTER reversed on the holdout.
* Whole-fund returns 2020–2025 (`OOS_RETURNS.json`, descriptive; 200-session core + decile book, 5 bp a side):

| | book gross 0.6 | book gross 1.0 |
|---|---|---|
| MASTER 5-day | 21.7%/yr, Sharpe 0.94 | 25.3%/yr, Sharpe 0.98 |
| Search's best (X1_8p) | 15.8%/yr, 0.75 | 15.3%/yr, 0.70 |
| Core only | 16.1%/yr, 0.79 | |
| S&P buy and hold | 15.0%/yr | |

  Only MASTER adds to the core. The search models subtract from it at 5 bp. Score smoothing helped X1 and *lowered*
  MASTER (21.7 to 20.7 at 0.6), so it is not a general fix.
* Network design, regime adaptation and weekly refitting added nothing. Inputs and the cost of trading did matter.

## The rule for phase 2

Gains can now come only from **information the panel does not contain**. Each branch adds new inputs to a **frozen
base** and is judged on the **increment** over that base:

* Base: the MASTER 5-day scores as already computed (no refit). The base's 2020–2025 performance is known; the
  relation of the new inputs to 2020–2025 returns is not, so the increment test is clean.
* Development 2013–2019 (gate: increment t ≥ 1.5); one read 2020–2025 per branch's finalist, Holm across branches.
* A pass earns a forward paper book. Forward weeks from 2026-11 are the only fully clean confirmation.

## Branches

| | Branch | New information | Why it can work | Cost |
|---|---|---|---|---|
| N1 | Fundamentals | SEC XBRL company facts (free): profitability, accruals, asset growth, investment; earnings surprise (already in `events.parquet`) | Slow signals with documented premia; low turnover, so they survive costs where price signals did not | No LLM; one bulk download |
| N2 | Short interest and flows | FINRA daily short volume (cached; F2 passed alone), as a feature in the base | The one validated non-price signal, never combined with MASTER | None |
| N3 | Intraday | 30-minute bars (cached, 2016–2025): overnight vs. intraday returns, closing-auction moves | Overnight/intraday return split is a documented, separate effect | None; survivorship disclosed |
| N4 | News | Alpaca/Benzinga headlines (from 2015, every member): counts, novelty, a dictionary tone; embeddings only if the cheap features pass | The fund's own thesis that news matters, tested at index scale for the first time | Dictionary: none. Embeddings: estimate before running |
| X | Combination | The passing branches' features in one model on top of MASTER | Breadth: independent signals add | After N1–N4 |
| P | Fund level | The validated sleeves together: core, MASTER book, F2 book, momentum-panic switch; sizing by the rule in the 21 Nov study | Sharpe rises with uncorrelated sleeves even if none improves | Descriptive on seen data; forward only |

Order: N2 and N3 first (data on disk, a day each), then N1, then N4, then X and P.

## Guards carried over

* One development file per branch that ends in 2019; holdout code runs only in the coordinating session.
* Every configuration logged; the count is reported with the result.
* Agents write `model.py` and their report early: the account's usage limits stopped agents four times in phase 1.
* Each agent gets its own worktree.
