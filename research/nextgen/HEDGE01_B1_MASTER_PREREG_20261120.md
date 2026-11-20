# HEDGE-01 — frozen empirical MASTER hedge-transfer test

**Registration:** 2026-11-20, before any MASTER+B1 full-fund return calculation. This is an addition to the EXISTING draft allocation PR #186, not a new PR, live strategy change or reopened 2020–25 holdout. Historical results are reused and may only be reported as descriptive.

## The previously validated model we will exploit

In research/riskfield/OOS_RESULT.json, the B1 beta estimator (21/63-session intraday beta and 252-session daily OLS, pooled monthly refit) reduces next-month per-name beta MSE by about 33% relative to B0, paired t 7.56 on the already examined 2020–25 period. Changing beta hedge in separate momentum/reversal books lowered weekly variance (paired t 2.42). The same project's HAR regime-switching/forgetting variants failed development. We will not rerun those synthetic or architecture model searches.

**New question:** Does applying the *existing*, causally monthly-refitted B1 to the SPY hedge of the currently admitted MASTER five-session stock book increase whole-fund net excess performance, after SPY hedge turnover and financing?

## Fixed comparison contract

Champion: existing 302-week S0 baseline, 21.69132654% CAGR, 0.93694624 total-return/vol ratio (NOT excess Sharpe), 0.81378154 T-bill-excess Sharpe under modeled net debit. Original SPY 1.3/0.7 trend core, fixed 0.3 long / 0.3 short MASTER stock book, 5bp unit turnover charge, rates dated before decisions.

One challenger: freeze every MASTER stock weight and the SPY core. Change only the SPY book hedge from the original beta to B1. Build historical B1 via the original riskfield.beta.build and riskfield.risk.forecasts using HF21, HF63 and daily OLS; Risk.forecasts enforces maturity by month-start cutoff tmax=a-1-21. The frozen end-2025 B1 coefficients are NOT used to forecast 2020–2025. Note B1 was validated on 21-session beta targets but MASTER trades on a five-session horizon.

Missing B1 on a held issuer: use the baseline beta for those same shares, record held-gross coverage and reject economic promotion if any week is below 90% coverage. Beta source has known current-constituent survivorship limitations; no issuer CIK map joins. Candidate's SPY hedge alone is clipped to the historical baseline's SAME gross budget, max(1.9, B0 gross that week); no stock-book or core weight is changed. Record how often the hedge is clipped and the residual beta. Do NOT impose a new 1.9 hard cap on historical B0.

Evaluate SAME dated funding rate under BOTH existing net-debit and segregated-stock-short-proceeds assumptions (counterfactual, not broker validated). Recalculate the debit and additional 5bp SPY turnover costs after changing hedge. Saturday Nov 21 financing study owns live-broker account policy, not this experiment.

## Execution/stop conditions

1. Reproduce the original 302 B0 fund returns against the committed audit weekly ledger to 1e-12 before reading any B1 fund result. Fail if original data, dates, money rates, gross or SPY hedge mismatch; no overwrite of input caches or result folders.
2. Align stock names and Thursday decisions exactly to the historical riskfield intraday source. All incomplete original stock outcomes and missing B1 coverage are explicit defects. Only return the measured net-effect after the baseline gate succeeds.
3. Report the cash-adjusted net excess Sharpe for both arms, absolute difference, net CAGR, period-matched annual return difference, HAC mean-return SE, 1500 fixed-seed stationary-block bootstrap Sharpe CI, year splits, max drawdown, gross cap binding, SPY turnover, two funding conventions and held-gross B1 coverage.
4. **Decision standard:** +0.15 excess Sharpe or +2 points/year net return at matched ex-ante risk is a materiality TARGET, not an observed result. A positive reused-sample number, even statistically significant, cannot change live trading. First approve a separately locked Protocol-9 forward hedge shadow. The existing H9 broad-book 104-week read stays untouched.

Implementation is a read-only local ZIP artifact. Local engineering tests: **27/27 passed**. Tested source SHA256: core.py = 1d948628d3fa775c5a5b62f840d2d8f5e29a5b71dc831a490e3f3d2917ab905b; reproduce.py = c5fa56515caa6a6195984bcb5b7799b753350eb7f3ff25d64a791c7c374c0d92; test_hedge_capture.py = a22bf2f5606f9de549031966ba814651ef64b753c19555db4491dd547d64d61f. No actual historical candidate fund return has been computed here; the required MASTER and intraday HF caches reside on the owner's Mac.

**Investment outcome: NOT YET TESTED. No live fund or broker changes.**