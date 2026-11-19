# OOF-01 — Point-in-time score-to-return calibration

Date: 2026-11-19. Research only. The work changes only research/nextgen/oof_calibration/ and never accesses historical market-data caches, broker services, live fund code, or the 2020–2026 reused holdout. Branch derived from research/tree-layer3 at 4b0d7b2c759c543c3dcf56a35ed36fca4fb0a661. Existing draft PRs #176–#179 remain independent.

## Hypothesis and causal interface

MASTER outputs cross-sectional scores, while the cost-aware optimiser requires holding-period fractional expected return units. Treating ranks as expected returns, or calibrating on evaluation-period labels, would generate invalid allocation decisions and temporal leakage.

ScoreObservation requires a stable historical security ID (never today's ticker), UTC-aware decision timestamp, score release timestamp, declared upstream model-training target cutoff, label end timestamp, optional realised beta-hedged excess target, outcome availability timestamp, and decision-time eligibility. All timestamps are validated with:

- upstream_train_target_end <= score_available < decision < target_end;
- label availability >= target end;
- every training cross-section must have all labels both completed and available STRICTLY before (forecast decision - embargo);
- no partial survivor-only label cross-sections; no duplicate (decision, historical security ID) keys.

This is a necessary data contract, not proof of upstream MASTER model training integrity. In particular, declared model provenance needs external verification. Forecasts here are CROSS-SECTIONAL beta-hedged excess alpha returns whose date sum is near zero, not unhedged absolute equity expected returns. No live integration is authorised.

## Rolling ridge mathematical construction

Within each complete eligible date, score percentile ranks are centered to [-1,1], using average ranks for ties. Let y_it denote realised beta-hedged excess return, x_it centered rank, and y_tilde_it = y_it - cross-sectional mean(y_it). Date sufficient statistics are q_t = mean_i(x_it*y_tilde_it), h_t = mean_i(x_it^2), and fixed ridge lambda=0.03. The fitted slope is

    beta_hat = mean_t(q_t) / (mean_t(h_t) + lambda)
    predicted_cross_sectional_alpha_it = beta_hat * x_it.

Every decision date carries equal weight, regardless of the number of eligible names. Define residual date score u_t = q_t - beta_hat*(h_t+lambda). HAC variance is computed on DATE-LEVEL u_t using a Bartlett Newey–West estimator with 4 lags, divided by T*(mean(h)+lambda)^2. Conservative slope is sign(beta_hat)*max(abs(beta_hat)-1.96*SE,0). The 1.96 coefficient is an engineering shrinkage heuristic, NOT a sequential p-value, multiplicity correction, or a statistically valid claim of confidence after multiple adaptive trials. Insufficient mature history yields zero expected alpha.

The initial locked synthetic experiment uses a 52-date rolling window, 26 minimum training dates, one-day embargo, 32 names per date, and fully deterministic timestamps and seeds.

## Stage A: locked 40-replication synthetic signal/no-signal/break experiment

Every path contains 80 development dates and 32 strictly forward evaluation dates, with 32 synthetic names per date. Seven-day label horizon plus one-day publication delay and one-day embargo. True cross-sectional rank slope: 0.010 throughout (stable), 0 throughout (null), or 0.010 for development and 0 for evaluation (break). Idiosyncratic return noise sigma=0.012, common date shock sigma=0.003. Seed sequence 20261119..20261158.

Metric: DATE-BALANCED MSE of cross-sectionally demeaned target returns. Lower is better. NOT NAV performance or fund Sharpe.

| Scenario | Zero forecast | Rolling unshrunk | Rolling conservative | Conservative minus raw MSE reduction ± MC SE |
|---|---:|---:|---:|---:|
| Stable | 0.00017446463 | **0.00013993465** | 0.00014056726 | -0.00000063261 ± 0.00000005910 |
| Null | **0.00013969171** | 0.00013975580 | 0.00013969297 | +0.00000006284 ± 0.00000002169 |
| Break | **0.00013969171** | 0.00015661143 | 0.00014873387 | +0.00000787756 ± 0.00000019200 |

Negative finding: conservative shrinkage slightly harms accuracy when a stable genuine signal exists. Following a breakdown it reduces the error of unshrunk calibration, but BOTH remain worse than a zero forecast. A tight estimate from stale history does not establish current predictability.

## Stage B: exploratory adaptation after inspecting Stage A

This hypothesis was developed AFTER viewing Stage A, so it is an EXPLORATORY adaptation experiment rather than another pristine validation, even though independent synthetic seeds were used (20261201..20261240).

Compare 12-date rolling ridge (minimum 8 dates) against a one-dimensional scalar Kalman filter. Each newly available complete date supplies a cross-sectional OLS slope and residual-based observation variance. The filter assumes random-walk slope process variance Q=(0.0015)^2 per seven days and prior state variance (0.02)^2. It processes date labels only AFTER their availability and propagates forecast-state uncertainty to the current decision date during the label maturation gap. Both candidates apply the same 1.96 standard-error soft-threshold.

| Scenario | Zero MSE | 12-date rolling conservative | State-space conservative | State minus rolling MSE ± paired MC SE |
|---|---:|---:|---:|---:|
| Stable | 0.00017687863 | **0.00014298975** | 0.00015381374 | +0.0000108240 ±0.0000001762 |
| Null | **0.00014076097** | 0.00014080703 | **0.00014076097** | -0.0000000461 ±0.0000000216 |
| Break | **0.00014076097** | 0.00014294858 | 0.00014124008 | -0.0000017085 ±0.0000001236 |

The state-space filter refuses out-of-sequence delayed historical labels, which require a replay or a separate out-of-sequence measurement algorithm. It more rapidly suppresses spurious forecasts after a break or under the null, but badly underperforms the rolling baseline in a stable predictive regime. It still loses to zero when the signal disappears. There is no universal winner and no basis for a trading strategy recommendation.

## Reproducibility

Commands from repository root:

    python -m pytest -q research/nextgen/oof_calibration
    python -m pytest -q research/nextgen
    python -m research.nextgen.oof_calibration.reproduce

Executed locally with Python 3.13, NumPy, SciPy and pytest. **35 new unit tests pass** for data availability, future label perturbation, absence of in-sample decisions, missing issuer outcomes, date-balanced ranking, input permutation invariance, Kalman uncertainty projection, out-of-sequence late-label fail-closed checks, and deterministic experiment settings. Package statement coverage in a separate 33-test run: 92% (318 statements / 26 missed). The additional reproduction-contract test was added afterward; all 35 now pass. Branch-specific four previously merged modules plus this lane: **72 passed + 8 subtests**. Local cross-branch compatibility with STILL-UNMERGED PRs #176–#179: **139 passed + 32 subtests**. GitHub source blob hashes of all seven Python files are verified against exact locally tested files.

## Next actionable, NOT yet executed

1. Export OOF MASTER per-issuer score rows with stable historical IDs and true known-as-of timestamps. Do not fabricate data vintages or infer identities from current tickers.
2. Validate model-training target cutoffs and historical PIT universe including delistings. Treat partial labels as hard defects.
3. Build the true beta-hedged excess target for the exact action/holding clock, with rate and hedge vintages.
4. Compare zero, raw rolling, conservative rolling, and state-space hypotheses on development data as **exploratory**; pre-register candidate family and new forward decisions. Inference must respect overlapping labels and weekly dependence.
5. Only after a matched-risk and realistic financing/NAV reconciliation may the calibrated outputs feed the portfolio allocator. No Sharpe above 1 has been demonstrated.

Academic method context:
- Fama & MacBeth (1973), Risk, Return, and Equilibrium: Empirical Tests, JPE, DOI 10.1086/260061. This implementation is pooled date-balanced regression, NOT literally Fama–MacBeth's two-pass estimator.
- Newey & West (1987), A Simple, Positive Semi-Definite HAC Covariance Matrix, Econometrica, DOI 10.2307/1913610.
- López de Prado (2018), Advances in Financial Machine Learning, Wiley, Chapter 7, purged overlapping-label tests.
- Kan & Zhou (2007), Optimal Portfolio Choice with Parameter Uncertainty, JFQA, DOI 10.1017/S0022109000004129.

**Decision:** accept causal calibration as isolated research infrastructure. Reject any inference of improved historical trading Sharpe or superiority of the state-space filter.
