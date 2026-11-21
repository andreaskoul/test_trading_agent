# RISK-02: causal whole-fund variance-persistence diagnostic — recorded negative result

**Decision: STOP this particular weekly fund-risk modelling branch.** This result was calculated 2026-11-20 from the exact 302-week B0 CSV **after** the fixed protocol was committed to `research/nextgen/RISK02_FUND_VARIANCE_PREREG_20261120.md` (commit `f4e5b064f0662fb6c096c3fb1376b958bfe1a12f`). No candidate fund return, factor/stock model, trading rule, historical selection or synthetic performance experiment was run.

**Input:** the 302 chronological 2020–2025 B0 weekly NAV rows in `research/tree/L4_exploit/b0_audit_runner/weekly_b0_ledger.csv`, verified source Git blob `2313f28e85f973152094f423df16d5f492531b56`. This history has been examined before. Weekly variance proxy = squared cash-excess week return normalized by `sqrt(7/calendar_days)`, with 1e-8 flooring for QLIKE; outcome = mean of next four weekly proxies. All predictor inputs end no later than the PREVIOUS week, with fixed t>=52 warmup. Overlapping four-week outcomes require HAC; fixed NW lag 8. Comparison period 247 origins, 2021-01-07 through 2025-11-13.

| Fixed diagnostic | Recorded result | Preregistered pass |
|---|---:|---|
| High state origins | 109 (44.1%) | group n>=40 |
| Low state origins | 138 | group n>=40 |
| Mean next-4-week variance in high state | 0.0007082736834 | |
| Mean next-4-week variance in low state | 0.0006074783154 | |
| Conditional mean ratio high/low | **1.165924** | **>=1.4** |
| HAC z/t for conditional state mean difference | **0.836421** | **>=2.0** |
| Mean trailing-52-week forecast QLIKE | **0.38012841** | baseline |
| Mean EWMA(0.94) forecast QLIKE | **0.35375798** | lower is better |
| Mean paired QLIKE improvement (trailing-52 minus EWMA) | **+0.02637043** | |
| HAC SE / t of EWMA QLIKE improvement | **0.01715273 / 1.537390** | **t>=2.0** |

**Both preregistered gates FAILED.** EWMA point loss is about 6.9% lower than baseline, but the paired uncertainty is not sufficient. State high/low future realised variance differed only 17% and was noisy. No evidence that adding an elaborate HMM/GMM/boosted/deep regime model to these 302 reused weekly returns would be justified. This is not an exclusion of richer models on **better intraday data**; the prior riskfield pooled HAR already beat an EWMA on a different constituent-level intraday RV target. The correct inference is specific to this noisy whole-fund, weekly sample and simple lagged signal.

**By calendar year (mean EWMA−baseline QLIKE gain):** 2021 +0.143865; 2022 −0.032185; 2023 −0.010151; 2024 −0.011047; 2025 +0.042906. Even signs lack stability.

**Reproducibility:** separate source package `RISK02_fund_variance_evidence_20261120.zip` distributed in conversation, SHA256 `80f91443b92d4ad52de27bbf110f630b089a6b8b303c9e62d73ee6cf5ec1b0c5`. It contains a standard-library-only read-only runner and 24 unit tests. The unit tests passed in the local model container, and the full observed numerical results were independently computed using the exact committed GitHub CSV rows. **The Python runner has not yet been executed against the Mac's original CSV**, though its data-input blob check will enforce identity. Do not conflate the 24 tests with investment-performance evidence.

**Economic next action:** work on the scheduled owner financing / actual broker margin comparison, then one approved matched-capital trend-core+MASTER construction. For dynamic risk, the existing cross-sectional intraday riskfield evidence already justifies **shadow measurement**, not a fund timing rule; use new prospective data to identify material impact. No additional risk architecture, HMM/GARCH hyperparameter grid, weekly volatility exposure switch or new alpha PR generated from this failure.

**Measured net-fund investment improvement:** NOT TESTED in RISK-02. Earlier HEDGE-01 return change was negative. Live strategy and forward locks unchanged.
