# CAL-01 — Forecast calibration, mean–variance regret and the economic search gate

**Research date:** 2026-11-19. **Status:** independent research-only mathematical and synthetic investigation, not a new empirical trading backtest. The only historical input is the *already published* B5a vs B0 paired-Sharpe-difference standard error and trial-family size. The project’s previously revisited 2013–2026 data are **not** treated as an untouched holdout.

## Prior context and non-overlap

- Base commit: \`research/tree-layer3\` at \`4b0d7b2c759c543c3dcf56a35ed36fca4fb0a661\`.
- The MASTER architecture/retraining and the core-financing study belong to the existing tree coordinator.
- PRs #176 (report reconciliation), #177 (financing stress) and #178 (162-model selection bias) are intentionally not modified or rebased here.
- This new work owns only \`research/nextgen/calibration/\`. It imports but never changes the merged \`research/nextgen/optimizer/core.py\`. It does not touch \`fund/\`, \`main\`, \`research/tree/\` logs, broker APIs, cached historical panels or runner state.

## Hypothesis CAL-01a: unconstrained optimizer amplification of return-estimation error

Given risk aversion \(\gamma>0\), *true* excess-return vector \(\mu\), and known positive-definite holding-period covariance \(\Sigma\), the quadratic mean–variance criterion is

\[
U_\mu(w)=\mu^\top w-\frac{\gamma}{2}w^\top\Sigma w.
\]

Let \(\hat\mu=\mu+\varepsilon\), with \(\mathbb E[\varepsilon]=0\) and \(\operatorname{Cov}(\varepsilon)=\Omega\succeq 0\). The estimate-based unconstrained solution at shrinkage \(\lambda\) is \(w_\lambda=(\lambda/\gamma)\Sigma^{-1}\hat\mu\). Set \(A=\mu^\top\Sigma^{-1}\mu\) and \(B=\operatorname{tr}(\Sigma^{-1}\Omega)\). Then **exactly under these assumptions**,

\[
\mathbb E U_\mu(w_\lambda)=
  \frac{\lambda}{\gamma}A-\frac{\lambda^2}{2\gamma}(A+B),\quad
\lambda^*=\frac{A}{A+B}.
\]

For no shrinkage, \(\mathbb E U_\mu(w_1)=(A-B)/(2\gamma)\), and regret against an oracle that knows \(\mu\) is \(B/(2\gamma)\). **If \(B>A\), the expected utility of the unshrunk strategy is negative relative to the zero-position benchmark**, despite the existence of genuine predictive information \(A>0\). Forecast noise concentrated in low-eigenvalue covariance directions is especially damaging.

**Caveat:** \(\mu\) and \(\Omega\) are *known only in this synthetic experiment*. This mathematical expression is not an implementable plug-in estimator. To deploy a shrinkage level in practice requires a causal, pre-registered method to estimate forecast error and signal variance, with all targets ending before decision times.

## Stage A: independent analytical Monte Carlo verification

- 24 synthetic assets; SPD \(\Sigma=X X^\top+\operatorname{diag}((0.015+0.005u_i)^2)\), seeded \(X\), four Gaussian factor loadings, and \(\mu=\operatorname{linspace}(-0.002,0.002,24)\).
- \(\gamma=5\); 20,000 independent Gaussian error draws for each \(\,B/A\in\{0.25,1,4,16\}\); seed \`20261119\`.
- Error covariance \(\Omega=(A\,B/A)/24 \cdot \Sigma\) gives the specified risk-weighted noise ratio.
- Each simulated forecast is used by both the unshrunk and analytically shrunk allocation. Performance is **true expected quadratic utility**, not a realised financial return path.

| Risk-weighted noise B/A | Optimal \(\lambda\) | Expected unshrunk / oracle utility | Expected shrunk / oracle utility |
|---:|---:|---:|---:|
| 0.25 | 0.8000 | 0.75 | 0.80 |
| 1 | 0.5000 | 0.00 | 0.50 |
| 4 | 0.2000 | −3.00 | 0.20 |
| 16 | 0.0588 | −15.00 | 0.0588 |

All four Monte Carlo utility estimates match their analytic predictions within simulation error. For example, at B/A=4: exact unshrunk \(-0.0286856\), MC \(-0.0285587\pm0.0000777\) standard error; exact shrunk \(0.0019124\), MC \(0.0019186\pm0.0000093\). These numbers are **not percentage NAV or Sharpe**.

## Stage B: synthetic experiment with actual merged cost-aware optimizer

- Use the unchanged merged \`research.nextgen.optimizer.core.solve\`, with **12** synthetic assets and **120 independently drawn forecasts per noise ratio**. The same forecasts enter both policies.
- Holding-period true \(\mu=\operatorname{linspace}(-0.0007,0.0007,12)\); \(\Sigma=0.0004 I+0.000025 \mathbf 1\mathbf 1^\top\).
- Constraints: gross \(0.6\), name limit \(0.075\), beta bound \(0.02\), dollar neutrality, prior weights zero; \(\gamma=6\).
- Cost assumptions: per-name half-spread 0.0002, daily volatility 0.02, ADV $500m, AUM $10m, impact coefficient 0.025.
- Predict using the **unconstrained theoretical** \(\lambda^* \in\{0.5,0.2\}\), *not* fitted on outcomes. Score positions using true \(\mu\) with exactly the stated quadratic risk, spread and impact; never score by ex-ante predicted utility or empirical realised returns.
- Costs, constraints and discontinuities invalidate the unconstrained \(\lambda\) optimality claim; this experiment is a falsification check, not a proof that these coefficients are constrained-optimal.

| B/A | Raw true expected **net utility** | Shrunk true expected net utility | Paired difference ± MC SE | Mean gross: raw → shrunk |
|---:|---:|---:|---:|---:|
| 1 | 0.0000479959 | 0.0000520767 | +0.0000040809 ±0.0000025293 | 0.5452 → 0.3124 |
| 4 | −0.0000468279 | 0.0000065921 | +0.0000534200 ±0.0000068017 | 0.5871 → 0.0947 |

At B/A=1, the improvement is only 1.61 Monte Carlo standard errors: **inconclusive**. At B/A=4 it is ~7.85 MC standard errors *in the fixed synthetic experiment*, and most of the change is substantial de-risking. Neither result says that shrinkage improves the actual fund's Sharpe.

## Stage C: conditional power of the only small positive Layer 4 result

Published **reused** \`research/tree/L4_exploit/RESULT.json\`, B5a versus B0, reports \(\Delta SR=0.050399043857478475\), a paired HAC standard error \(0.05402454118653946\), and \(302\) observations. Under a *hypothetical* future experiment with constant effect, stationary variance that scales as \(1/T\), independent evaluation periods, a one-sided normal test, and seven comparisons protected by Bonferroni at total \(\alpha=0.05\):

| Hypothetical forward duration | Approximate conditional power |
|---:|---:|
| 43 weeks | 1.795% |
| 52 weeks | 1.956% |
| 302 weeks | 6.462% |
| 520 weeks | 11.013% |

The required forward duration for 80% conditional power is \(\approx3759.79\) weeks (\(\approx72.30\) 52-week years); for a single **pre-specified** comparison it would be \(\approx2145.42\) weeks. **This is not a genuine forecast of research duration**: the original effect and SE are noisy, selected from repeatedly inspected data, and could change after adding realistic financing, regime and capacity modelling. The calculation is an argument to prioritise material, reliable effect sizes instead of marginal gains on an already reused sample.

## Reproducibility and exact source scope

From repo root (no cached market data):

\`\`\`bash
python -m research.nextgen.calibration.reproduce
python -m pytest -q research/nextgen
\`\`\`

The reproduction script reads **only** the already-published \`L4_exploit/RESULT.json\` for the prospective-power scenario. It does not refit models or recalculate portfolio returns. Executed local combined research branch suite: **64 tests + 16 subtests passed**; new module has **27 tests + 8 subtests**, 99% Python statement coverage (160/162). Eight GitHub Python blob hashes verified byte-for-byte against executed local files.

## Next experiment — causal, not yet executed

1. Build a security-ID and timestamp-aligned forecast/target table: \`prediction_at\`, \`available_at\`, \`target_end\`, model version, horizon, volatility, and PIT issuer membership. No current-ticker substitutions.
2. Define calibrated forecast \(\hat\mu_{i,t}\) in return units matching the exact holding interval; estimate \(\Omega\) from **purged rolling-origin, out-of-fold forecast errors** with shrinkage/regularisation, never from future labels. No oracle \(\mu\) will be available.
3. Estimate the signal-to-noise ratio causally, e.g. from cross-fitted forecast covariance with attenuation correction and conservative uncertainty bounds. The oracle \(\lambda^*\) above is for theorem/tests only. Include the \(\lambda=0\), constant shrinkage, and original decile baseline as simple controls.
4. Integrate true whole-fund financing, borrow status, cash interest, SPY hedge, changing margins and trading costs with matched risk, exposure and AUM sensitivity.
5. Preregister utility/turnover/Sharpe hypotheses and comparison family **before** new forward evaluations. Historical 2013–2026 is repeatedly viewed and cannot be restored as a clean model-selection holdout.

## Academic anchors

- Kan & Zhou (2007), *Optimal Portfolio Choice with Parameter Uncertainty*, JFQA 42(3), DOI [10.1017/S0022109000004129](https://doi.org/10.1017/S0022109000004129).
- DeMiguel, Garlappi & Uppal (2009), *Optimal Versus Naive Diversification*, RFS 22(5), DOI [10.1093/rfs/hhm075](https://doi.org/10.1093/rfs/hhm075).
- Kozak, Nagel & Santosh (2020), *Shrinking the Cross-Section*, JFE 135(2), DOI [10.1016/j.jfineco.2019.06.008](https://doi.org/10.1016/j.jfineco.2019.06.008).
- Harvey, Liu & Zhu (2016), *…and the Cross-Section of Expected Returns*, RFS 29(1), DOI [10.1093/rfs/hhv059](https://doi.org/10.1093/rfs/hhv059).

**Research-only; no merge into main or live fund; no claim of empirically increased net Sharpe.**