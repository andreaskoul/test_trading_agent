# Capital-efficient core, overlay sizing, netting, fund volatility scale — pre-registration (2026-11-21)

Scheduled research task from the owner's brief of 2026-11-10 (Sharpe > 1, beat the S&P). Research only: nothing
under `fund/` changes. Instruments, core weight, exposure band and overlay scale are the owner's policy (CLAUDE.md
rule 17); any change is a proposal. This file is committed before any statistic below is computed.

**What this is not.** Item 1 compares *how the same exposure rule is financed and held*: a cost-and-path comparison of
the 200-session 1.3×/0.7× core. It is not a new exposure rule and not an alpha claim. Items 2 and 4 are rules and
descriptions; items 2-4 spend no sealed read.

**Paper versus real money.** Alpaca paper accounts charge no margin interest or borrow fees. At the fund's exposures
the paper NAV therefore overstates a real-money account by about 1.4-2.7 %/yr (net-debit and segregated-proceeds
conventions; PR #184 financing note). Every figure here uses real-money financing assumptions.

## Common definitions

* **Core exposure path** e_t: 1.3 when the total-return index closed above its 200-session mean at the previous close,
  else 0.7 (as `research/exposure/exposure.py` P3 and `strategies.py` UP/DOWN/TREND). It is the same path in every
  arm.
* **Margin rate:** T-bill (French RF, or DTB3 for 2020-2025) + 2.43 %/yr (`strategies.MARGIN_SPREAD`).
* **Cash conventions, reported side by side and never mixed:**
  * (R) idle cash earns the T-bill;
  * (S) the fund simulator's convention: idle cash earns 0, and only debit is charged.
* **Switching cost:** 2 bp per unit of exposure traded (as exposure.py). Daily constant-weight rebalancing is assumed
  in every arm (a stated simplification, applied identically).

## Item 1 — capital-efficient core

**Arms** (same e_t):
* **M, margin:** hold e_t of the index. Borrow (e_t − 1)⁺ at the margin rate; under (R), cash (1 − e_t)⁺ earns the
  T-bill.
* **E1, all-2× fund:** hold h_t = e_t/2 of NAV in the 2× daily-reset fund, with the rest as cash. No borrowing.
* **E2, minimum-cost mix:** hold a_t of a 1× index fund and b_t of the 2× fund, with a + 2b = e_t and a + b ≤ 1, and
  b as small as possible: e = 1.3 → a = 0.7, b = 0.3; e = 0.7 → a = 0.7, b = 0. The rest is cash.

**2× fund model, fixed now** (then checked, not refitted):
* daily r₂ₓ = 2 r_idx − (rf + s) − ER₂ₓ/252, with ER₂ₓ = 0.89 %/yr (the 2× S&P fund's stated expense ratio) and
  embedded financing on the borrowed 1× at rf + s, s = 0.50 %/yr;
* the 1× index fund costs ER₁ₓ = 0.0945 %/yr;
* before 2006 these are synthetic on the French market return (CRSP value-weighted, not the S&P 500; labelled so).

**Check against the real fund**, SSO against SPY, from SSO's first full month (2006-07) to the latest close:
* the daily tracking difference r_SSO − (2 r_SPY − rf_d), its annualised mean and sd;
* the implied annual drag compared with the assumed ER₂ₓ + s;
* as a sensitivity, item 1 is rerun with the implied drag if it differs from the assumption by more than
  0.25 %/yr (the assumption stays primary).

Data: adjusted closes from yfinance, frozen with sha256 at first fetch.

**Samples:**
* (a) 1927-2026, the French daily file (core starts after a 200-session warm-up);
* (b) 2006-07 to the latest close, with real SPY and SSO;
* (c) **whole fund 2020-2025**, on the audited weekly ledger
  (`research/tree/L4_exploit/b0_audit_runner/weekly_b0_ledger.csv`, research/tree-layer3; 302 weeks).

**Sample (c) arms:** the stock book's weights, hedge and returns are taken from the ledger unchanged; only the
core's holding changes.
* M-net, the simulator's debit max(LMV − SMV − 1, 0), where LMV and SMV are long and short market value, with the
  core SPY and the hedge netted.
* M-seg, short-sale proceeds not credited: debit max(LMV − 1, 0).
* E1 and E2: the core held as above, priced with real SSO and SPY over each holding period (close of the day after
  the decision to close of the day after the next decision). Each is financed under both debit conventions.
* The weekly SPY return implied by the ledger is checked against yfinance SPY over the same windows (must agree
  within 5 bp a week on ≥ 95% of weeks; otherwise stop and report).

**Statistics, per arm and sample:**
* arithmetic %/yr and compounded %/yr;
* excess Sharpe over the T-bill; volatility; worst rolling 12 months;
* tracking difference against M (mean %/yr and its sd);
* average account gross (market value) and the gross freed against M, overall and in 1.3× weeks;
* for (c), the fund-level figures under both debit conventions and both cash conventions.

**One read:** this file's commit is the registration; the computation runs once, with `READ_CAPITAL.lock` written
first. There is no hypothesis test; the paired difference and its HAC standard error (4 lags) are reported.

## Item 2 — overlay risk budget (derived, no data fitting)

For a core with Sharpe S_c and volatility σ_c and an uncorrelated overlay with Sharpe S_o, the maximum-Sharpe mix
sets σ_o/σ_c = S_o/S_c (tangency of two uncorrelated assets), and the combined Sharpe is √(S_c² + S_o²). A half-scale
version (half-Kelly logic) gives up a quarter of the overlay's variance contribution to the gain, for robustness to
estimation error.

**Rule:**
σ_o = ½ · σ_c · S_used / S_c, where S_used = max(0, ½ · L) and L = Ŝ_o − 1.645 · SE(Ŝ_o)
(one-sided 95% lower bound, Lo 2002 iid standard error √((1 + Ŝ²/2)/years)).

The overlay's gross is g = σ_o / σ_unit, with σ_unit the overlay's volatility per unit of gross, capped by the gross
available (0.6). The Sharpe a book needs for the full 0.6 solves S_used = 2 S_c σ_unit · 0.6 / σ_c.

**Inputs:**
* S_c and σ_c from item 1, sample (a), arm M under (R).
* σ_unit from the MASTER book on the ledger (`book_net_return` volatility / its gross).

**Tabulated for:**
* F2, the short-volume tilt: Ŝ derived from its recorded out-of-sample t (−1.88 over 2020-2025, 6 years) as
  |t|/√6, labelled "derived from a t-statistic; no return series on file";
* the broad trees book at its point-in-time figure (`research/tree/R2_pit/RESULT.json`): realistic cost model
  0.03 ± 0.32, plus the 14 bp row;
* MASTER on its pre-2020 development Sharpe (−0.16) and its 2020-2025 Sharpe.

**Discussion required:** the rule would have set MASTER to 0 before 2020, and the book then earned 5.1 %/yr.

## Item 3 — signals in one book (netting)

**Registered as a typed defect before counting:** no forward record of an F2 short-volume book exists on `fund-data`,
`research-data` or any branch (searched 2026-11-21). The overlap with the news (7B lifecycle) book cannot be counted.

What is reported instead, from records that spend no sealed read:
* the 7B book's names and gross since 2026-11-12, from fund-data;
* the formula for gross saved by netting two books with name-overlap share q and sign agreement a;
* a statement of what record is needed: the F2 forward book, as Protocol 10 announced.

No return statistic.

## Item 4 — fund-level volatility scale (descriptive on spent samples; not a test)

**Scale:** w_t = clip(σ*_t / σ̂_t, 0.5, 1.5), with
* σ̂_t the 63-session EWMA volatility (α = 2/64 on squared daily returns, known at t − 1);
* σ*_t the expanding mean of σ̂ up to t − 1 (causal), starting after 252 sessions.

**Applied to:**
* (a) the 1927-2026 core, arm M under (R). The scaled exposure is w_t·e_t, financed at the margin rate on
  (w e − 1)⁺.
* (c) the 2020-2025 whole fund, weekly: a 13-week EWMA (≈ 63 sessions) on weekly excess returns, with the target as
  the expanding mean.
  * Return: r′ = rf + w (r − rf) − (w − 1)⁺ · rate · days/360 · max(net exposure, 0).
  * This approximation is stated: the extra exposure is financed at the margin rate.

**Report:** %/yr, Sharpe, volatility and worst 12 months, with and without the scale, plus the average w. It is
labelled "descriptive on spent samples; not a test". Clean evidence would need forward weeks or an untouched market;
the 2026-11-10 test of a standalone volatility target failed.
