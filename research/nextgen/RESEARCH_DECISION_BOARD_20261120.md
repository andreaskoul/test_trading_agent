# Whole-fund research decision board — 2026-11-20

Purpose: replace activity-driven research with verified improvements in future **whole-fund net excess returns**. This document belongs to existing allocation PR #186, coordinating PR #184 accounting and #185 statistics. No change to main, fund/, broker, existing model scores or forward records.

## Verified historical benchmark: already reused, not new holdout

Source: research/tree/L4_exploit/b0_audit_runner/weekly_b0_ledger.csv, blob 2313f28e85f973152094f423df16d5f492531b56. B0 was reproduced exactly by the owner's local runner; 302 weeks, 2020-01-02 to 2025-12-11, 2177 calendar days.

| Whole-fund statistic | Existing 5-bp stock-trading, net-debit finance model |
| --- | ---: |
| CAGR | 21.69132654% |
| Legacy annualised return/volatility **NOT EXCESS SHARPE** | 0.93694624 |
| **Cash-rate-adjusted excess Sharpe** | **0.81378154** |
| Annual arithmetic excess return versus period T-bills | 18.20785905% |
| Annual total-return volatility | 22.37378783% |
| Maximum drawdown | -29.98544666% |
| Average fund gross exposure | 1.76847563x |
| Book trading cost per year (5 bp per turnover unit) | 1.95897403% NAV |
| Weeks gross above historical 1.9x threshold | 159 of 302 |
| Model training / PIT issuer provenance independently verified | NO |

Reproduction convention: weekly NAV return r, calendar duration d and as-of annual cash rate rf yield period-normalised weekly excess x = (7/d)*r - (7/360)*rf. Annualised excess Sharpe = sqrt(52)*mean(x)/sample_sd(x). CAGR = exp(365.25*sum(log(1+r))/sum(d))-1. All challenger reports must use identical cash benchmark, dates and financing assumptions; preserve legacy 0.937 only as a labelled compatibility metric.

**Historical fixed-position economic sensitivities; NOT achievable strategies:**

| Alternative modeling assumption | CAGR | Cash-excess Sharpe |
| --- | ---: | ---: |
| Zero margin charge | 23.36809% | 0.87497 |
| Current net-debit margin model | 21.69133% | 0.81378 |
| Short proceeds segregated | 20.15126% | 0.75715 |
| Stock turnover charge 2.5 bp versus base 5 bp | 22.88493% | 0.85892 |
| Stock turnover charge 10 bp versus base 5 bp | 19.33805% | 0.72349 |

Rate/cost changes are accounting sensitivity, **not** measured alpha. Alpaca paper accounts omit live borrowing expenses. Live financing relies on actual settled debit, borrow availability and short-proceeds arrangements.

## Conclusive negative evidence and stop rules

- MASTER remains one admitted alpha. Eleven challenger alpha types failed incremental empirical gates; latest MASTER architecture screen (2026-11-20) rejected all development variants (IC increments about +0.008, t <= 0.52).
- Bigger MASTER book B5a: increment only +0.0504 *legacy* whole-fund ratio, paired HAC SE 0.0540, one-sided p 0.175; not established.
- Covariance-optimised book: stronger standalone book Sharpe but worse fund Sharpe and fixed-gross net book return. Volatility/liquidity timing and alpha ensembling largely failed.
- Recent nextgen optimizers, forecast calibration, multi-alpha and sequential evidence modules are **engineering prototypes**, not empirical net returns.
- No new synthetic investment experiments, model families, PRs or micro-audits just to report activity. Retain code as regression infrastructure; do not make a trading decision from its test count.

## Three active economic questions, priority order

**F1: financing and investable exposure.** OWNER'S ALREADY SCHEDULED 21 NOV 2026 08:00 UTC study. Same historical exposure path under (a) modeled net debit, (b) short proceeds segregated, (c) 2x daily-reset fund. Require live account-specific interest, collateral, fees, tracking and path dependence. Report net excess Sharpe/CAGR, gross, drawdown and risk at matched exposure. Do not duplicate this study, or infer live finance from paper account zero expense.

**P1: one capital-aware SPY trend + MASTER challenger.** Only one preregistered portfolio construction against the fixed core+MASTER champion. Both use the **same** permitted SPY 1.3x/0.7x core, MASTER ranks, funding convention, portfolio beta, risk budget, gross and cost policy. The historical L4 soft gross exception is different from live P9 gross_guard's 1.9x cap: do not pass off a different leverage policy as better alpha. Predeclare the objective, inputs, coefficients, constraints, missing-data rules and kill criteria using data through 2019 ONLY. If causal return-unit calibration cannot be independently checked, do NOT install an aggressive mean-variance allocator. Report 2020-25 and 2026 as descriptive reused-window comparisons only; no post hoc selection.

**C1: implementation cost and capacity.** Paper execution audit: 258 priced fills, 5.64 bp median absolute fill-close deviation, but no direct arrival shortfall or live market impact. PR #187 fixed SIP close lookup in main. Obtain timestamped bid/ask at decision (feed disclosed), reference SIP close, partial-fill opportunity cost and scale/ADV. Historical COST_STUDY half-spread mean 2.29 bp and median 1.37 bp across a limited S&P500 sample, excludes impact. Do not change order timing without prospective execution evidence.

**ALPHA SEARCH PAUSED.** New candidate must show PIT-compliant, survivorship-checked independent development incremental signal, at least t >= 2 and positive in 2/3 of development years, log effective prior trials >= 162, and show plausible net economic value and capital capacity. Previously opened 2020-2026 is never new untouched OOS. No issuer CIK joins through stale current-owner ticker CIK map.

## Objective and evidence gates

**Primary fund metric:** paired, cash-rate-adjusted, **net** whole-fund weekly NAV excess return after credible borrowing, margin, cash, spreads, impact and constrained allocation. Report absolute delta excess Sharpe, matched-ex-ante-risk annual net return difference, paired HAC/block-bootstrap uncertainty, maximum drawdown, tail loss, gross, financing and AUM capacity. Post hoc volatility scaling is a descriptive diagnostic, not investable forward construction.

**Economic research target, NOT an observed gain:** at least +0.15 absolute excess Sharpe OR +2 percentage points/year net return at matched ex-ante risk, no material tail/drawdown worsening. This screens for economic materiality; final statistical promotion rule and trial adjustment must be registered BEFORE any future outcome. Positive reused-sample effects cannot be declared confirmed improvements.

Evidence ladder:
- E0 source/tests and PIT checks.
- E1 historical B0 return ledger exactly reproduced (ACHIEVED).
- E2 conditional financial/accounting sensitivity quantified, account-specific settled cost still unknown (ACHIEVED with qualifications).
- E3 **independent Protocol 9 MASTER forward shadow** registered before outcome maturity under approved rules (NOT YET).
- E4 fully matured truly forward paired net returns assessed once under pre-registered test (NOT YET).
- E5 owner-approved small real-money pilot after risk, borrow and compliance gates (NOT YET).

Important forward separation: H9 104-week F0/F1/F2 locked read covers BROAD STOCK BOOKS, NOT a whole-fund Protocol 9 core+MASTER allocator. H9 first 2026-11-19 book can be recorded 2026-12-05 and forbids interim comparative returns before week 104; do not contaminate this program. A P9 challenger requires separately approved frozen shadow registration and its own read protocol. H9 reported <3GB free disk on 2026-11-19, installation owned by coordinator.

## Scoreboard and ownership

| Track | Measured progress as of Nov 20 | Next numerical deliverable | Capital decision |
| --- | --- | --- | --- |
| Champion | 302/302 weeks reproduce; 0.814 excess Sharpe in simulator | same-path cash/financing audit | unchanged |
| Funding | annual existing margin cost ~1.375% NAV vs 2.654% segmented conditional | Saturday same-path financing/instrument study | no funding policy chosen |
| Allocation | 11 candidate alphas failed; 159/302 historical gross above 1.9x | one matched-cap gross-aware candidate on local data | no proven improvement |
| Execution | 258 paper fills; missing SIP reference corrected in PR 187 | 2 weeks prospective quote/reference coverage | no timing change |
| Forward | H9 lock documented; P9 alternative not yet registered | explicit independent shadow approval and record integrity | no forward evidence |

**Daily iteration rules:** read current repo and this board first. Prioritise an identifiable net-NAV improvement, not number of tests. Before scoring a new candidate fix champion, hypothesis, expected materiality, costs, capital/financing, comparisons, dependent data windows, multiplicity and stop conditions. Avoid overlap with the owner financing study and running agents. Use local owner scripts only when caches are inaccessible; fail closed on PIT/provenance and never touch live trading or append-only records. Each report must end with **Improved whole-fund performance: YES/NO/NOT YET TESTED**, effect and uncertainty, and the next evidence gate.

**Decision 2026-11-20: NO CHANGE to strategy, leverage, MASTER, core, orders or capital policy.**