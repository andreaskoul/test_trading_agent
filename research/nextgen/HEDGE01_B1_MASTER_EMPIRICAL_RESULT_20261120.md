# HEDGE-01: B1 beta-to-MASTER economic transfer — empirical outcome (20 November 2026)

**Final decision:** **REJECT B1 for the existing MASTER book; keep incumbent B0 hedge.** Not a claim that intraday beta measurement is bad for all books. No live fund, orders, risk policy, alpha or forward records changed. **This document is a post-result report, separate from the frozen preregistration** at research/nextgen/HEDGE01_B1_MASTER_PREREG_20261120.md.

## Provenance and quality

Owner ran the read-only local package against existing MASTER h5 walk-forward scores, quant-tf panel, riskfield 30-minute bars and committed 302-week B0 audit. The B0 exact-reproduction gate succeeded before candidate computation. Results and all weekly rows were committed on research/tree-layer3 under:

- research/tree/L4_exploit/hedge01_run/RESULT.json (Git blob c13100fb4049fdb01c92889ba2ab16216e6bcdab)
- research/tree/L4_exploit/hedge01_run/WEEKLY.csv (Git blob 022fa1c22d34a5e711fee06be21868f3b529c31e)
- research/tree/L4_exploit/hedge01_run/COORDINATOR_PATCHES.diff (Git blob f8b8f23391d9a421d3b628ea0c3a6ac79342110e)

**Source status:** REUSED_DESCRIPTIVE_LOW_B1_COVERAGE. As of 2026-11-20 the historical 2020–25 candidate sample was already seen by other projects. The pre-registered 90% held-gross B1 coverage rule failed in **167/302 weeks**; minimum coverage 76.44%, mean 89.25%, due in part to the riskfield current-constituent intraday sample. Missing B1 betas fall back to B0. The candidate hedge was clipped to the baseline-soft-gross rule in 137/302 weeks. **This is not a clean fully-covered independent holdout and is not eligible for trading promotion.**

## Frozen whole-fund performance comparison

| 2020–2025, 302 weeks | B0 incumbent | B1 with identical stocks/core | Change |
| --- | ---: | ---: | ---: |
| CAGR | 21.69132654% | 21.23583353% | -0.45549301 percentage points/year |
| Conventional cash-rate-adjusted excess Sharpe | 0.81378154 | 0.80928187 | **-0.00449967** |
| Annualised total-return vol | 22.37378783% | 21.95130210% | -0.42248573 percentage points |
| Max drawdown | -29.98544666% | -29.48533267% | +0.500114 percentage points |
| Segregated-proceeds CAGR | 20.15125772% | 19.69348332% | -0.45777439 percentage points/year |
| Segregated-proceeds excess Sharpe | 0.75714971 | 0.75125794 | -0.00589177 |

- Paired return difference B1−B0: **−0.442228 percentage points annualised arithmetic**, HAC SE **0.355525**; no compelling statistical evidence of improvement.
- Paired stationary-block bootstrap **95% excess-Sharpe difference interval: [−0.03257754, +0.02283397]**, nowhere near research materiality target +0.15. The interval is conditional on this reused history, NOT proof from a clean holdout.
- By year B1−B0 mean weekly bp: 2020 −1.03; 2021 −0.55; 2022 +1.25; 2023 −0.42; 2024 −0.63; 2025 −4.38. B1 worse 5/6 years.

### Exact period-matched return attribution

Reaggregated WEEKLY.csv independently, preserving each week’s actual calendar-day duration and the simulator's 52-week annualisation convention:

| B1 vs B0 contribution | Annualised arithmetic NAV percentage points |
| --- | ---: |
| Changed SPY hedge market P&L | **−0.45682030** |
| Additional SPY-hedge transaction costs | **−0.04995486** |
| Margin-financing savings | **+0.06454710** |
| **Total B1−B0** | **−0.44222806** |

The per-period accounting identity has maximal absolute numerical error ~1.65e−17. The stored RESULT.json annualised SPY turnover (+0.047606%) and funding (−0.068604%) use period-weighted annualisation over 2,177 calendar days; the above decomposition uses **52 × mean(7 × component / duration)**, which exactly sums to the reported arithmetic-return delta. Do not conflate these normalisations.

Both beta forecasts produce almost neutral MASTER books (mean residual B0 book beta ≈−0.00159, B1 desired ≈−0.00747), and realised B0/B1 hedge positions correlate ≈0.981. Their stock-market signal/weights were frozen; changing hedge has limited scope to earn more. The changed hedged exposure had an unfavourable SPY return path, partially offset by reduced modelled interest. This does not invalidate B1 for momentum/reversal or other books with materially larger beta.

## Three coordinator integration corrections

The original local runner failed closed three times, before any candidate result:

1. Original construct.run returns a numeric-index DataFrame. Compare rows to B0 ledger using actual decision dates from the ORIGINAL strategy's periods generator, not row.name.date().
2. quant-tf and riskfield both name a module panel. Load riskfield panel/risk/beta under isolated module references and restore existing top-level import aliases; never silently use the wrong panel.
3. Genuine March 2020 three-month T-bill rate was −0.04% annualised. Allow realistic slightly negative risk-free rates (−1% minimum) while still requiring nonnegative modeled margin interest and bounded duration.

Owner reran the patched historical comparison and obtained the results above; all original 27 tests passed. Separately, a **corrected read-only reusable package** incorporating these corrections and **four new engineering regression tests** passed **31/31** in a clean local container. Because the corrected package uses stronger import isolation than the owner scratch patch, its exact revised code has NOT been rerun through the full 302-week private-cache data in this container. Neither changes economic model selection nor authorises another historical tuning exercise.

## Go/no-go

**No-go:** adopting B1 for MASTER, rerunning B1 hyperparameters on this seen sample, interpreting lower MSE as guaranteed positive fund returns, or drawing forward conclusions from a quality-failed retrospective comparison.

**Keep:** existing B1 forward evaluation for other equity books, the point-in-time riskfield model and this negative result in the model trial inventory.

**Next fund-level economic focus:** follow the owner's independent November 21 financing/instrument study first; it is more economically material than B1's hedging change. Only thereafter consider one frozen, matched-capital construction of the validated MASTER book against the incumbent. Any regime/variance model research must distinguish successful risk prediction from profitable strategy timing, and evaluate decision-level net NAV under a frozen cap/funding policy. Do not reopen previous Q9/X3/Q10/M1/Q6 failures merely because the model class is sophisticated.

**Measured new improvement in net whole-fund performance: NO.** Research E1/E2 historical descriptive; no E3/E4 forward strategy evidence.