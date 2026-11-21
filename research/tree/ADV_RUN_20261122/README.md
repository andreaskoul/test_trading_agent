# Advanced research suites (PRs #188/#189/#191/#192) run on the local caches (2026-11-22)

**Scope.** Development data only: intraday panel 2016-2019 (current constituents, so survivorship is not
point-in-time certified) and the alpha panel ≤ 2019. Code: `origin/research/advanced-research-audit-20261122`.
Environment: an isolated arm64 Python 3.11 venv with pymc 5.28, cvxpy 1.9 and torch 2.15. PyTensor was run with
Apple clang (`PYTENSOR_FLAGS=cxx=/usr/bin/clang++`), because Homebrew's Intel clang++ cannot compile it.
**Tests: 129 passed, 0 skipped.** No suite produces investment-return evidence; all are forecast diagnostics.

| Suite | Result |
|---|---|
| D alpha: frozen-MASTER efficacy (constant, Kalman, state regression, MoE, Bayesian NUTS) | All within −0.2% to +2.0% of the constant model's MSE (2.759e-4); no model beats a constant |
| D regimes (HMM, HSMM, BOCPD) | Predictive log density only (HMM 1.93, HSMM 1.86, BOCPD null); no baseline, no decision |
| A risk (POET, HEAVY, realized GARCH, Bayesian SV) | Fail-closed: under 90% forward-label coverage at 2018-05-03 |
| C coupled risk, paired QLIKE gain over static-factor POET (34 monthly origins 2018-19, HAC) | **Matrix-HEAVY: SPY variance +0.152 (t 2.48), equal-weight stocks +0.159 (t 1.85), both years positive.** DCC +0.12 (1.11); t-score +0.08 (0.81); particle SV +0.00 (0.02). Holm over 8 tests: Matrix-HEAVY SPY p ≈ 0.0065 against 0.00625 — borderline fail |
| B geometry covariance (QLIKE, lower is better) | Euclidean 0.90 < Bures 1.09 < log-Euclidean 1.36 < affine 1.39 < SPDNet 2.33: the geometric metrics are worse than plain Euclidean |
| B geometry alpha (GP and MoE on SPD and diffusion features predicting MASTER efficacy) | All worse than constant: diffusion GP t −2.25, log-SPD macro GP −2.34, Fisher GP −1.60, log-SPD GP −1.71, MoE −1.19 |
| B states | Fail-closed: insufficient matured training/test coverage |
| E MPC (HEAVY forecaster, 1,000 scenarios) | Solver returned a constraint violation |
| E geometric MPC | Fail-closed: "no matched point-in-time current risk state for MASTER" |

**Defect to report to the authoring session.** The coupled-risk diagnostics show MASTER constituent coverage **0.0**
at every origin, and the geometric MPC cannot match MASTER to the intraday names. So every MASTER-linked
risk/control path ran without MASTER: the alpha and intraday name mapping is broken or empty. The MPC failure is a
solver infeasibility that needs a feasibility check before the solve.

**Reading.**
* About 25 model variants produce one forecast-accuracy lead: Matrix-HEAVY for market variance (t 2.48 over 2 years,
  borderline under Holm). It is consistent with the HEAVY literature and with riskfield's HAR result.
* No investment evidence. The repository's history says better variance forecasts have not turned into Sharpe here:
  volatility targeting, C5 and RISK-02 all failed.
* The alpha-side models lose to a constant.
