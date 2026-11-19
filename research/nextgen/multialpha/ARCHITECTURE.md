# MULTI-01 — Factor-aware, cost-constrained, selective multi-alpha architecture

Research record: 2026-11-19. This is a STACKED research branch based on PR #181 (GROSS-01), not a change to main, fund, the live runner or existing tree logs.

## Decision after inspecting current research state

**Exploit, rather than restart model discovery.** The 2020–2025 Layer 4 B0 MASTER baseline reported 0.936946 raw-return/vol ratio, whereas B4 MASTER+trees was 0.840566 and B3 multi-horizon MASTER was 0.864951. Their difference did not justify a new traded ML ensemble. The M2 IPCA signal passed an S&P400 test but did not demonstrate significant incremental value over MASTER. Q8 risk neutralisation reduced some volatility but generally reduced mean IC and had no significant fund advantage. Recent PEAD, insider and 13F variants failed registered development gates. The 2020–2026 return period has been reused for research and is NOT a new sealed holdout.

**Adopt a multi-alpha capable interface without automatically admitting new alpha.** The existing MASTER portfolio remains the incumbent comparator, while trees, IPCA, news, event, macro and others remain shadow unless causally demonstrated incremental whole-fund net benefit. Approval metadata alone is not statistical evidence or permission to trade.

## Composable implementation

- signals.py: each packet requires historical security IDs, actual signal release and upstream training-target timestamps, a matching holding horizon, calibrated beta-hedged fractional residual return units, governance status, and an explicit evidence reference. Alternative forecasts of the same return are weighted-average estimates, never summed blindly. Independently verified incremental return components may be added with explicit scaling. Exact or near-collinear incremental duplicates fail closed. Shadow/rejected sources contribute zero trading alpha.
- factors.py: residual return risk covariance S = B F B_transpose + diagonal(specific_variances), where F is PSD, each specific variance strictly positive, and SPY covariance is checked jointly for PSD. Factor loadings and covariance are required to have as-of vintage.
- portfolio.py: fixes the core SPY leverage s externally; stock residual weights w are optimized under full-fund mean/variance risk, real beta-hedge q=s-beta_transpose*w, exact fund gross |q|+sum(|w|), book and per-name caps, optional factor bands B_transpose*w, dollar neutrality, shortability, spread, nonlinear 3/2 impact, SPY turnover cost and explicit hypothetical funding plus borrow rates. Gross, long positions and cash debit use EXACT linear-epigraph constraints. Invalid input or solver/post-check failure aborts.
- study.py: deterministic controlled 100-replication synthetic experiment with hidden true residual-return vector only revealed to evaluation AFTER portfolio construction.

This is a SINGLE-PERIOD decision model. It does not estimate multi-period alpha decay, actual broker cash settlement, historical short borrow availability or real fund NAV. The model assumes segregated short-sale proceeds when calculating a conservative debit. Neither 1.9 fund gross nor 0.5 debit is an approved live fund limit. Factor neutrality is optional, not imposed universally: Q8 research showed it can discard legitimate expected premia.

## Objective and exposure identities

Calibrated residual expected return: expected fund excess = s*mu_SPY + w_transpose*mu_residual.

Covariance of residuals: S = B F B_transpose + D, with the joint block covariance of (residual stock returns, SPY) PSD.

Whole-fund variance = s^2*variance_SPY + 2*s*c_transpose*w + w_transpose*S*w.

Maximize expected excess minus gamma/2 times variance, spread/impact/SPY turnover, plus borrowing and short fees. Exact fund gross constraint: |s-beta_transpose*w| + sum_i |w_i| <= G. Under the explicit conservative financing assumption, debit = max(max(q,0)+sum_i max(w_i,0)-1,0) <= permitted_debit. Fees use holding_days/day_count, not nominal annual dollars.

## Synthetic falsification: informative versus spurious incremental alpha

100 independent paired six-security synthetic problems, fixed core=1.3x, gross cap=1.9, debit cap=0.5, 6% hypothetical annual margin rate, factor-risk and cost controls. The true expected return is used for scoring ONLY after the optimizer has selected weights, never for fitting or trading.

| Admission case | Mean predicted utility gain | Mean TRUE conditional net utility change | Monte Carlo standard error | Fraction true gains |
|---|---:|---:|---:|---:|
| Genuinely complementary independent residual alpha | +0.0021010 | **+0.0013707** | 0.0001809 | 81% |
| Deliberately misapproved spurious noise | +0.0056280 | **-0.0029842** | 0.0002419 | 7% |

This is synthetic one-period net QUADRATIC UTILITY, not annual fund return, portfolio Sharpe, or a genuine investment result. It reveals the necessity of the alpha admission gate: even a mathematically correct constrained optimizer can be persuaded to destroy true expected utility if its forecasts are unvalidated.

## Verification and provenance

Four core Python files match locally executed GitHub blobs byte-for-byte. The full independent local MULTI-01 module had 40 passing adversarial tests and 95% statement coverage; 14 review-size smoke tests are checked into this PR. Local cross-branch compatibility with all earlier research workstreams (including other unmerged draft PRs) had **205 passing tests and 32 subtests**. This is not GitHub CI. Run from a checked out stacked branch:

    python -m pytest -q research/nextgen/multialpha/test_repo_smoke.py
    python -m research.nextgen.multialpha.study

Exact scenario results are in RESULTS_SYNTHETIC.json. A separately provided full source package contains the longer tests and logs.

## Literature and practitioner inputs

- Garleanu and Pedersen (2013), Dynamic Trading with Predictable Returns and Transaction Costs, https://doi.org/10.1111/jofi.12080 . Their multi-period alpha decay is NOT implemented by this single-period program.
- Jensen, Kelly, Malamud, Pedersen, Machine Learning and the Implementable Efficient Frontier, https://www.aqr.com/insights/research/working-paper/machine-learning-and-the-implementable-efficient-frontier . Net-of-cost utility is the economically relevant target.
- AQR, Transactions Costs: Practical Application, https://www.aqr.com/-/media/AQR/Documents/Insights/White-Papers/AQR-Transactions-Costs---Practical-Application.pdf . Optimizing solely for minimum trading costs is not equivalent to maximizing net alpha when signal decay varies.
- Quantitative Finance Stack Exchange, Combining alphas for mean variance optimizer, https://quant.stackexchange.com/questions/79899/combining-alphas-for-mean-variance-optimizer . Useful discussion of scaling and transfer coefficients, NOT empirical validation.

## Next registered EXPLOIT gates

1. Reconcile actual cash, margin, borrow fees and SPY hedge with an independent fund NAV ledger; approve account-specific leverage and factor bands.
2. Obtain verifiable point-in-time out-of-fold MASTER forecasts, training cutoffs, PIT issuers and delisted securities; calibrate expected beta-hedged excess return units before allocating.
3. Estimate factor/idio covariance with genuine historical as-of vintages; measure predictive versus realized utility at matched risk, capital, transaction cost and AUM.
4. Promote any additional alpha only with verified conditional incremental net economic value and a new forward, pre-registered paired experiment. Do not rebrand reused 2013–2026 as OOS.
5. After the single-period architecture is validated, explore dynamic alpha decay/transaction scheduling and then true multi-sleeve capital allocation as a separate research hypothesis.

**Decision:** Accept this as the mathematical target ARCHITECTURE and research implementation. Reject a claim of higher measured real-world net fund Sharpe or permission for live orders.
