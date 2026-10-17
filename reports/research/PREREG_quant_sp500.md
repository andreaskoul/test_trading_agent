# Pre-registration: the refit five-factor quant model on the S&P 500 (DRAFT, not signed)

**Status:** draft. `research/quant_trials/sp500_test.py` refuses to score anything until the owner signs this off
and the commit is pushed.

**Dated:** 2026-10-17.

## Why this test
In the refit-cadence study (`reports/research/quant_trials/REFIT.md`), the shadow quant book's five price factors
did something on the 31-name news panel:
* The factors are 12-1 momentum, 1-month reversal, 1-week reversal, low volatility and nearness to the 52-week
  high.
* Refit walk-forward by ridge, with quarterly refits on an expanding window, they scored a mean weekly IC of
  **+0.067 at h = 20 sessions over 2022–25 (NW t 2.5)**, against ≈ 0 over 2018–21.
* That came from a window that had already been read, on 31 large caps.

This test asks whether the *procedure* works on the universe it was designed for.

**What has been seen before.**
* The frozen quant ridge (`artefacts/llm/ridge_stocks.json`) was fit on S&P 500 weekly data from 2004-01 to
  2026-03, so the factors' premia on this universe were studied in an earlier project.
* What has **not** been computed is this procedure's walk-forward performance on the S&P 500: quarterly IC-tuned
  ridge refits, the 20-session residual target, out-of-sample ICs.
* This is therefore a test of the procedure, not of unseen factor history. **The clean evidence is the forward
  shadow book from 2026-10.**
* Jan–Sep 2026 (the sealed P8 holdout) is never loaded. Data ends 2025-12-31.

## Data
**Universe.** Point-in-time S&P 500 membership (`data/raw/stocks/sp500_membership.csv`). A name is eligible at
session d if it is a member on d.
* Prices are yfinance adjusted closes. Delisted names without data are dropped (survivorship bias).
* Measured at draft time: prices exist for 621 of the 850 names ever in the index since 2009. Eligible members with
  data per day: about 349 (2013), 419 (2019) and 487 (2025). Coverage is reported per year.

**Signals.** The five signals exactly as `fund/screen.py`, on daily sessions:
* mom12_1 = log P(d−20) − log P(d−252)
* rev1m = −(log P(d) − log P(d−20))
* rev1w = −(log P(d) − log P(d−5))
* lowvol = −std of 60 daily log returns
* high52 = P(d) / max P over 252 sessions

Each is z-scored across eligible members per session.

**Target.** The 20-session residual return from close(d+1) to close(d+21): r − β·r_SPY, with β the shrunk Welch
β over 252 sessions to d. It is cross-sectionally demeaned.

**Splits.**
* Training starts 2010-01-04.
* Test years 2013–2025 are predicted by **quarterly refits on an expanding window**, with a 20-session embargo.
* Ridge α is chosen in each training window by rank IC on its last 20% (grid 1e-2 … 1e5).
* Test decisions are kept only when their target window ends inside the same calendar year.

## Primary hypothesis (one test)
**H-SP.** The refit model's mean weekly (Thursday) cross-sectional Spearman IC with the 20-session residual return
is > 0. It is pooled over 2013–2025, with Newey–West t (lag 4) and a one-sided p.

**Pass** only if all of the following hold:
1. one-sided p < 0.05;
2. mean IC > 0 in both 2013–2019 and 2020–2025;
3. mean IC ≥ 0 in 2022;
4. the weekly long-short decile spread on the 5-session residual return from close(d+1), held one week, is > 0
   net of 10 bp per unit of one-way turnover.

## Secondary (descriptive only, no pass/fail)
* 2022–25 on its own: the window where the lead appeared, on a different universe.
* The frozen ridge's IC on the same decisions, labelled in-sample, and refit minus frozen.
* Sector-neutral IC, within GICS sectors.
* Per-year table and coverage.

## After the read
* The read is made once; results go to `reports/research/quant_trials/SP500.md` whatever they are.
* **If it passes,** the procedure may be proposed as a P8 deterministic input under its rules: sealed read,
  amendment.
* **Either way,** the forward shadow book keeps running.

**Owner sign-off:** _pending_
