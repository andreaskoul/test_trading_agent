# Nextgen D — inference safeguards (research-only)

This directory does not read market data, change the fund, retrain MASTER or inspect returns from reused research periods.

## Paired Sharpe interval

The annualised excess-return Sharpe difference is computed at identical periods with the identical cash series. Bootstrap samples draw common **circular moving-block indices** for candidate returns, control returns and risk-free cash. This retains within-block serial correlation and across-strategy dependence.

**Important:** this is a simple percentile bootstrap **exploratory confidence interval**, **not** Ledoit & Wolf's studentized hypothesis test. It does **not** output a p-value, undo multiple comparisons, or turn 2020–2026 into a previously untouched holdout. Its confidence coverage can be poor in small samples or with unusual dependence. No investment conclusion follows from an interval on reused dates.

Block length, cash vintage, candidate population, dates, seed and bootstrap draw count must be registered **before** viewing an unseen future evaluation sample.

## Multiple testing

The Holm step-down procedure adjusts only **valid input p-values** for a fully pre-registered family and controls FWER without assuming independence. It must not be applied to raw bootstrap confidence intervals. Previously tried or abandoned ideas belong in a trial inventory; retrospective exclusion invalidates a claim of complete family-wise correction.

## Test instructions

From repository root, run:

    python -m pytest -q research/nextgen/inference

Combined with other workstreams after review:

    python -m pytest -q research/nextgen

## Academic references

- Ledoit & Wolf (2008), *Robust performance hypothesis testing with the Sharpe ratio*, J Empirical Finance 15(5), 850–859, DOI 10.1016/j.jempfin.2008.03.002.
- Harvey, Liu & Zhu (2016), *… and the Cross-Section of Expected Returns*, RFS 29(1), DOI 10.1093/rfs/hhv059.
- Bailey & López de Prado (2014), *The Deflated Sharpe Ratio*, JPM 40(5), DOI 10.3905/jpm.2014.40.5.094.

All figures are conditional on synthetic tests. Do not merge into live fund or treat as production inference until further audited tests.
