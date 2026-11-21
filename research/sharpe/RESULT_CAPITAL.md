# Capital-efficient core, overlay sizing, netting, fund volatility scale — results (2026-11-21)

Pre-registration: `PREREG_CAPITAL.md` (commit dc8aeb2, before any statistic). Code: `capital.py` (one read,
`READ_CAPITAL.lock`), `overlay_rule.py`. Numbers: `RESULT_CAPITAL.json`, `RESULT_OVERLAY_RULE.json`,
`RESULT_NETTING.json`.

**This is a cost-and-path comparison of one exposure rule (the 200-session 1.3×/0.7× core).** It is not a new
exposure rule and not an alpha claim. Research only; any change of instrument, core weight, exposure band or overlay
scale is a proposal for the owner.

**Paper versus real money.** Alpaca paper accounts charge no margin interest or borrow fees. At these exposures the
paper NAV overstates a real-money account by about 1.4-2.7 %/yr (PR #184). All figures below use real-money
financing assumptions.

## Recommendation

1. **Hold only the core's excess over 1× through a 2× daily-reset S&P fund** (E2: 0.7 SPY + 0.3 of the 2× fund in
   up-trends, 0.7 SPY in down-trends). Do not hold the whole core in it (E1).
   * On the fund's real 2020-2025 positions, E2 earns +0.25 %/yr over margin (HAC SE 0.08) under the simulator's
     debit convention, and +0.29 %/yr (SE 0.08) under segregated short proceeds.
   * Excess Sharpe 0.834 against 0.822 (net debit, cash earning the T-bill).
   * Average account gross falls from 1.77 to 1.54. The number of weeks above the 1.9 cap falls **from 159 of 302 to
     0**, at the same market exposure.
   * In up-trend weeks it frees 0.3 of gross for the stock book.
   * It is a proposal for the owner (instrument policy).
2. **Do not adopt the registered overlay rule as written.** With a 95% lower bound *and* a 50% haircut *and*
   half-tangency, it sizes every book here at about zero. It would have held no MASTER book before 2020 (development
   Sharpe −0.16), and that book then earned +5.1 %/yr.
3. **The fund-level volatility scale is not worth pursuing** (descriptive). On 2020-2025 it lowered the fund's excess
   Sharpe from 0.78 to 0.62.

## Item 1 — capital-efficient core

**The 2× fund model, checked against the real SSO** (from 2006-10, its first date with a 200-session SPY trend):
* implied annual drag over 2 × SPY − T-bill: **1.75 %/yr**, against an assumed 1.20 %/yr (0.89% fee + 0.50%
  financing − 2 × SPY's fee);
* tracking sd 3.6 %/yr; the drag was 7.95 % in 2008 and 0.8-1.8 % in other years.
* The difference exceeds 0.25 %/yr, so the pre-registered sensitivity rerun of (a) was triggered (below).

**(a) 1927-03 to 2026-09**, French daily market, synthetic funds, cash earning the T-bill (R). The core is at 1.3× on
72.5% of days.

| Arm | Arithmetic %/yr | Compounded %/yr | Excess Sharpe | Vol | Worst 12 months | Gross in 1.3× weeks | vs margin, %/yr |
|---|---:|---:|---:|---:|---:|---:|---:|
| M, margin | 12.61 | 11.77 | 0.558 | 17.20 | −50.5% | 1.30 | n/a |
| E1, all in 2× | 12.46 | 11.60 | 0.549 | 17.20 | −50.7% | 0.65 | −0.15 |
| **E2, 1× + 2× for the excess** | **12.88** | **12.07** | **0.573** | 17.20 | −50.5% | **1.00** | **+0.27** |

* Sensitivity with the real fund's implied drag: E2 +0.15 %/yr, E1 −0.47 %/yr.
* Under cash convention S (idle cash earns 0): E2 +0.27, E1 −1.21.

**(b) 2006-10 to 2026-11, real SPY and SSO**, (R). The core is at 1.3× on 79.4% of days.

| Arm | Compounded %/yr | Excess Sharpe | Worst 12 months | Gross in 1.3× weeks | vs margin (HAC SE) |
|---|---:|---:|---:|---:|---:|
| M | 11.49 | 0.587 | −37.9% | 1.30 | n/a |
| E1 | 11.11 | 0.573 | −38.7% | 0.65 | −0.38 (0.15) |
| **E2** | **11.76** | **0.601** | −38.0% | **1.00** | **+0.24 (0.05)** |

**(c) Whole fund 2020-2025, the audited 302-week ledger** (stock book unchanged, only the core's holding changes).
* Checks: the weekly SPY return implied by the ledger matches yfinance in 100% of weeks (largest gap 0.006 bp). M
  under (net, S) reproduces the audited B0 to 1e-16.

| Arm, debit / cash convention | Compounded %/yr | Excess Sharpe | Worst 52 weeks | Average gross | Weeks > 1.9 | vs M (HAC SE) |
|---|---:|---:|---:|---:|---:|---:|
| M, net / S (= audited B0) | 21.69 | 0.814 | −20.5% | 1.77 | 159 | n/a |
| M, net / R | 21.92 | 0.822 | −19.9% | 1.77 | 159 | n/a |
| M, segregated / R | 20.20 | 0.759 | −20.5% | 1.77 | 159 | n/a |
| E1, net / R | 21.57 | 0.807 | −20.4% | 1.26 | 0 | −0.33 (0.19) |
| **E2, net / R** | **22.25** | **0.834** | −19.9% | **1.54** | **0** | **+0.25 (0.08)** |
| E2, net / S | 21.97 | 0.824 | −20.5% | 1.54 | 0 | +0.21 (0.08) |
| **E2, segregated / R** | **20.58** | **0.772** | −20.5% | 1.54 | 0 | **+0.29 (0.08)** |

**Why E2 wins and E1 loses.** Margin costs (e − 1)⁺ × (T-bill + 2.43%). E2 replaces only that borrowed slice with a
2× fund whose embedded financing is about the T-bill + 0.5-0.9%, plus its fee. E1 also pays the 2× fund's drag on the
first 1× of exposure, which margin finances for free with the fund's own equity.

**Caveats.**
* Leveraged-fund decay under daily rebalancing is in the real-data arms (b) and (c), and only modelled in (a).
* Daily constant weights are assumed in every arm.
* Reg T counts the 2× fund at market value, which is what frees gross; the risk is unchanged.
* SSO's tracking error is 3.6 %/yr, and 2008's drag was 8%.

## Item 2 — overlay risk budget (derived; `RESULT_OVERLAY_RULE.json`)

**Rule.** σ_o = ½ σ_c S_used / S_c, with S_used = max(0, ½ L) and L = Ŝ − 1.645 √((1 + Ŝ²/2)/years).
* Basis: for two uncorrelated sleeves the maximum-Sharpe mix sets σ_o/σ_c = S_o/S_c, and the combined Sharpe is
  √(S_c² + S_o²). The ½ is half-Kelly robustness.
* Inputs: core S_c 0.558, σ_c 17.2% (1927-2026, arm M); MASTER book volatility per unit of gross 11.0%.

| Overlay | Ŝ (years) | 95% lower bound | S_used | Overlay vol | Gross (cap 0.6) |
|---|---:|---:|---:|---:|---:|
| F2 short-volume tilt (Ŝ derived from OOS t −1.88; no return series on file) | 0.77 (6) | 0.003 | 0.002 | 0.03% | 0.002 |
| Broad trees book, point in time, realistic costs | 0.03 (9.6) | −0.50 | 0 | 0 | 0 |
| Broad trees book, point in time, 14 bp | 0.12 (9.6) | −0.41 | 0 | 0 | 0 |
| MASTER book, development 2013-2019 | −0.16 (7) | −0.79 | 0 | 0 | 0 |
| MASTER book, 2020-2025 | 0.77 (6) | 0.004 | 0.002 | 0.03% | 0.003 |

**The full 0.6 of gross** needs S_used = 0.43, i.e. a measured Ŝ of **2.04 over 6 years** (1.66 over 10).

**What the MASTER case implies.**
* The rule is triply conservative: the lower bound, the ½ haircut and half-tangency. With 6-10 years of data, the
  lower bound alone removes any Sharpe below about 0.7.
* MASTER shows the cost. Before 2020 its book Sharpe was −0.16, so the rule holds nothing. Holding nothing gives
  16.07 %/yr against 21.69 %/yr with the book, 2020-2025 (`research/tree/L4_exploit`).
* A usable rule would shrink the *point estimate* (for example S_used = ½ Ŝ, or a Bayesian posterior mean with a prior
  centred at 0), not stack a lower bound on top. At S_used = ½ × 0.77 the rule gives gross of about 0.54, close to
  today's 0.6.
* That alternative is a reading here, not registered. It is a proposal for the owner.

## Item 3 — signals in one book (netting; `RESULT_NETTING.json`)

**Typed defect:** no forward F2 short-volume book record exists on `fund-data`, `research-data` or any branch
(searched 2026-11-21), so its overlap with the news book cannot be counted.
* What exists: the 7B book has 20 open lots (10 long, 10 short; model gross 0.76) and 28 names in its target weights
  since 2026-11-12.
* Formula: gross(a + b) = Σ|a| + Σ|b| − 2 Σ_{opposite-side names} min(|a_i|, |b_i|). Same-side overlap saves no
  gross; it concentrates.
* Needed: the F2 forward book's weekly weights, as Protocol 10 announced. No return statistic was computed.

## Item 4 — fund-level volatility scale: descriptive on spent samples, not a test

Scale: w = clip(σ* / σ̂, 0.5, 1.5); σ̂ is a 63-session (13-week) EWMA known the day (week) before, and σ* its
expanding mean.

| | Without scale | With scale | Average w |
|---|---|---|---:|
| Core, 1928-2026 (daily, arm M, R) | 12.44 %/yr, Sharpe 0.546, vol 17.3%, worst 12m −50.5% | 12.09 %/yr, Sharpe 0.550, vol 16.5%, worst 12m −42.6% | 1.14 |
| Whole fund, 2021-2025 (weekly) | 17.56 %/yr, Sharpe 0.776, vol 18.5%, worst 52w −20.5% | 18.03 %/yr, Sharpe 0.619, vol 23.9%, worst 52w −26.0% | 1.30 |

On the long core the scale trims the worst year but not the Sharpe. On the fund it levers up a calm 2021-2024 and
lowers the Sharpe. The 2026-11-10 test of a standalone volatility target failed. Clean evidence would need forward
weeks or an untouched market.
