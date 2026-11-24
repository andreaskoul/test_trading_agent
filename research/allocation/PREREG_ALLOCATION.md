# Core/book allocation: frozen candidates and a Bayesian sizing rule, evaluated forward — pre-registration (2026-11-24)

Research only: nothing under `fund/` changes. The core weight, its band, the instruments and the book's scale are
the owner's policy (CLAUDE.md rule 17). Every candidate below is fixed in this file before any forward week is
computed for it. The inputs are published figures, copied by `prior.py` from named fields at named revisions into
`PRIOR.json`. No new statistic of any return series was computed to write this file.

## Why

The owner (2026-11-24): "Study a smaller trend core, larger book allocation, and a second independently validated
book … Freeze candidate policies before prospective evaluation; do not optimize them against the reused 2020–25
period." The earlier frontier analysis found that under the 1.3×/0.7× core and the 1.9× cap the fund's excess
Sharpe tops out at about 0.88, so passing 1 needs a different core-to-book ratio or a second book.

## What the published evidence already says (`PRIOR.json`)

**The MASTER book's Sharpe, weighted by years across every walk-forward sample:**

| Sample | Book Sharpe | Years | Source field |
|---|---:|---:|---|
| development 2013–2019 | −0.16 | 7 | `RESULT_OVERLAY_RULE.json` rows."MASTER book, development 2013-2019".S_hat |
| 2020–2025, survivorship-repaired (reused window) | 0.70 | 6 | `R3_master_pit/RESULT.json` P7_book_and_fund.REPAIRED.book.sharpe |
| 2026 to the sealed test's last week | −0.44 | 0.83 | `H7_DECOMP.json` pct_2026, at the 2020–25 book volatility (approximation) |
| **pooled** | **0.20** (SE 0.27) | 13.8 | |

* **Posterior** (prior N(0, 0.5²) on the annual Sharpe, normal likelihood): mean **0.15**, sd 0.24 on all the
  evidence. On 2020–2025 alone it would be 0.38 (sd 0.34). Dropping the other 7.8 years is not justified: they are the
  same model, walk-forward, and the development years were used to *choose* it, which biases them up, not down.
* **Today's sizing is already about right for that evidence.** For two uncorrelated sleeves, the maximum-Sharpe
  book volatility is σ_o = σ_c · S_o / S_c (core S_c 0.558, σ_c 17.2%, 1927–2026; book 11.0% volatility per unit of
  gross). The book's current gross of 0.6 is the tangency for S_o = **0.21**, and the posterior mean gives a gross
  of 0.43.
* **The pay-off is asymmetric** (excess Sharpe of core plus book, long-history core, uncorrelated, no cap):

  | True book Sharpe | gross 0.43 | 0.6 (today) | 0.9 | 1.2 | 1.96 |
  |---:|---:|---:|---:|---:|---:|
  | 0.0 | 0.538 | 0.521 | 0.483 | 0.442 | 0.347 |
  | 0.2 | 0.591 | 0.592 | 0.583 | 0.564 | 0.504 |
  | 0.4 | 0.644 | 0.664 | 0.683 | 0.686 | 0.660 |
  | 0.7 | 0.724 | 0.772 | 0.833 | 0.869 | 0.895 |

  A larger book gains about +0.1 if the 2020–25 figure is the truth, and loses 0.1–0.2 if the pooled figure is.
* **What Sharpe 1 needs** (uncorrelated sleeves, core 0.558): one book with Sharpe ≥ **0.83**, or two independent
  books of ≥ **0.59** each. No allocation of the present book gets there unless its true Sharpe is ≥ 0.83.

**Power of a forward test.** A one-sided 5% test that the book's Sharpe exceeds the 0.21 implied by today's sizing
has these chances of passing:

| True book Sharpe | 52 weeks | 104 weeks | 156 weeks | 260 weeks |
|---:|---:|---:|---:|---:|
| 0.4 | 7% | 8% | 9% | 11% |
| 0.7 | 11% | 15% | 19% | 25% |

A forward horse race between allocations cannot settle the question in any horizon that matters. So this file
registers a **decision rule that learns from the forward weeks**, not a test, and states what the candidates'
forward records are for.

## Inputs, forward (no new trading code)

Every candidate is a linear combination of series that are already recorded weekly. No shadow book is needed:
* the core: SPY close-to-close over each record's holding period and the T-bill (DTB3), with the trend state of the
  fund's rule (`s` in the forward S&P ledger);
* the MASTER forward book: `research-data:fund_state/live/research/spx/ledger.json`, rows `bk == "fw_master_h5"`,
  field `book` (net of its own turnover cost), divided by the record's Σ|w| over names (gross per unit). This
  begins with as-of 2026-10-29;
* the live 7B news book, from the account records, as a second series. It is reported separately and never pooled
  with MASTER.

## The frozen candidates

Financing is real money: margin at T-bill + 2.43% on (exposure − 1)⁺, with the 2× fund priced as in
`research/sharpe/PREREG_CAPITAL.md` (E2).

| | Core | Book gross |
|---|---|---|
| **A0, incumbent** | 1.3× / 0.7×, margin | 0.6 |
| **A1, E2 only** | 1.3× / 0.7× as 0.7 SPY + 0.3 of the 2× fund / 0.7 SPY | 0.6 |
| **A2, E2 + freed gross** | as A1 | 0.9 in up-trend weeks (the 0.3 E2 frees), 0.6 in down-trend weeks |
| **A3, Bayesian tangency** | as A1 | g = clip(σ_c · S_post / (S_c · σ_unit), 0, 1.9 − core gross), S_post the posterior mean below; 0.43 at registration |
| **A4, smaller core** | 1.0× / 0.5×, no borrowing | as A3, capped at 0.9 |

**The posterior behind A3 and A4** is updated every 13 forward weeks. Prior N(0, 0.5²). Likelihood: the pooled
Sharpe of the three samples above plus the forward weeks' annualised Sharpe of the MASTER book, weighted by years,
with the Lo (2002) iid standard error. S_c, σ_c and σ_unit stay fixed at the values in `PRIOR.json`; they are
never re-estimated on forward weeks.

## Reports and decisions

* **Every 13 forward weeks:** the posterior (mean, sd), A3's gross, and each candidate's cumulative %/yr and
  excess Sharpe, labelled "descriptive; no test".
* **No candidate is "selected" by its forward return.** The registered recommendation to the owner is A3's sizing
  at the current posterior. A move of the book's gross above today's 0.6 is recommended only while the posterior
  mean is ≥ 0.21 (the Sharpe today's sizing implies). A move to the smaller core (A4) is recommended only if the
  posterior mean is ≥ 0.6, where it starts to matter under the 1.9× cap.
* **A second book** enters this framework only after it passes its own pre-registered out-of-sample test. Then
  its correlation with MASTER, estimated on that test's weeks, enters the two-book tangency
  w ∝ Σ⁻¹ μ.

## Not claimed

* The table of combined Sharpes assumes uncorrelated sleeves, the long-history core and no cap. The realised
  2020–25 fund had a stronger core (excess Sharpe about 0.8). It is a sizing argument, not a forecast.
* The 2026 book Sharpe uses the 2020–25 book volatility, not 2026's own, because no 2026 volatility field is on file.
* A normal prior with sd 0.5 is a choice. With sd 1.0 the posterior mean is 0.18 (sd 0.26; `PRIOR.json` posterior_prior_sd_1.0_all_evidence).
