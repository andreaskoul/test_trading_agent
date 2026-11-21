# Coupled dynamic factor covariance and tail-risk research

**Separate stacked research branch:** `research/coupled-factor-tail-risk-20261122` (base: PR #188). No changes to `main`, `fund/`, broker, cache, or any locked forward experiment. This package extends (does not duplicate) the open model suites in PR #188 and PR #189.

## Implemented executable research methods

| Model | Math / distinct assumption | Cost |
| --- | --- | --- |
| Static POET baseline | PCA factor covariance + thresholded PSD residual | moderate |
| **Matrix-HEAVY** | `H[t+1]=(1-a-b) S + a RV[t]+b H[t]`, QML a,b | moderate |
| **DCC(1,1)** | realized-diagonal variance recursion and learned conditional factor correlation | moderate-high |
| **Student-t score-robust covariance** | PSD return/realized outer-product recursion; downweighted extreme Mahalanobis shocks | moderate-high |
| **Correlated particle stochastic volatility** | jointly evolving factor log-variance states, non-diagonal innovation covariance, Student-t likelihood, particle bootstrap and 3×3 phi/noise parameter model averaging | **high** |

This extension tackles a limitation of the existing #188 factor-SV: its factor log-volatilities were inferred independently. The particle model carries correlated latent log-volatility innovations and a factor-return correlation structure. It **does not** infer fully time-varying correlations, so dynamic correlation is addressed by separate DCC and score filters; none of these is a fully general multivariate Bayesian Wishart process. The robust score filter is **Student-t-score-motivated**, not mathematically identical to a Fisher-scaled GAS estimator.

### Environment

Python ≥3.10; NumPy, SciPy, pytest. No PyMC/CVXPY needed for this extension. The base PR #188 and stacked geometry PR #189 remain available for advanced Bayesian posterior, MoE, GP, SPD manifold, robust MPC. Use a new virtual environment if existing local deps conflict. The package is bundled as an archive to allow an isolated owner code inspection; extract in a **scratch checkout** of the research branch before running. No script installs packages or accesses the network.

### Data contracts

Risk: existing `research/riskfield` 30-minute cache `hf.npz`: arrays `S` (ordered session dates), `names`, `R` `(T,14,N)` (overnight + 13 half-hour log returns), `rv`. Only sessions `<=2019-12-31` are used. A strict 95% intraday and daily window coverage gate applies to fitted securities; historical current-constituent survivorship is explicitly flagged.

Optional development MASTER: `.cache/tree/dev.npz` with `S`, `names`, `master_h5_ref`, `elig`. **Any alpha file extending after 2019 is rejected**. Its optional output is a *risk proxy* for MASTER book weights; not a verified original fund NAV backtest. For the exact fund book, matched 2013–19 PIT membership, betas and core exposure need independent certification.

### Inspect then test

```bash
# From a separate research worktree after checking out the branch:
unzip -l research/nextgen/coupled_factor_tail_suite_20261122.zip
unzip research/nextgen/coupled_factor_tail_suite_20261122.zip -d /private/tmp/coupled_factor_risk_source
# Inspect models.py, adapters.py, runner.py, tests/test_models.py first.
cd /private/tmp/coupled_factor_risk_source
python -m pytest -q research/nextgen/coupled_risk/tests
```

### Run existing local data

```bash
HF="/absolute/path/to/riskfield/.cache/riskfield/hf.npz"
DEV="/absolute/path/to/tree/.cache/tree/dev.npz"
python -m research.nextgen.coupled_risk.runner check \
  --hf-cache "$HF" --alpha-cache "$DEV"

OPENBLAS_NUM_THREADS=3 OMP_NUM_THREADS=3 \
python -m research.nextgen.coupled_risk.runner run \
  --hf-cache "$HF" --alpha-cache "$DEV" \
  --models poet matrix_heavy dcc t_score particle_sv \
  --factors 3 --lookback 252 --particles 1000 --step 21 \
  --out "$HOME/ResearchData/coupled_factor_risk/full_20261122"
```

The output must not already exist and must not be inside an input data or project directory. Exact source SHA and dates are included in `RESULT.json`. All inputs are read-only. `--max-origins 2 --max-names 80 --particles 64` is for code/compute smoke testing only and has no investment inference. Full 2018–19 development origins plus 1000 particles are intended for substantive statistical study. Increase particle count to 2000–5000 if diagnostics/Monte Carlo uncertainty demand it; `phi_grid=(.90,.97,.995)` and `q_grid=(.10,.25,.5)` are pre-fixed in source.

### Evaluation and advancement

- Fixed common dates, 5-session horizon: QLIKE of realized portfolio quadratic variation vs `5 × predicted daily covariance` for SPY and equal-stock portfolios; optional MASTER rank-book proxy if alignment and coverage are adequate.
- Paired, >=12 time origins HAC for model-vs-POET QLIKE (5 lags), yearly breakdown; no model auto-selection. This is **development-period** forecasting, not a fresh holdout and not a fund Sharpe improvement.
- The particle SMC latent-volatility innovations have *joint* covariance; model weights average a pre-fixed grid by likelihood. `ess_min`, `ess_mean`, and all model weights are saved. If severe ESS collapse or a dominance/degeneracy problem occurs, increase particles/check parameterization before trusting predictive output; do not fit 2020–26 for tuning.
- Prior 162+ effective alpha model trials remain in the promotion inventory. To change MASTER or whole-fund allocation, first achieve independent predictive calibration, broker-credible costs and separately approved Protocol-9 forward shadow. H9 broad-book 104-week read is unrelated and must remain locked.

### Engineering status

**26/26 local engineering tests pass**; a 2-origin end-to-end smoke run on generated test-fixture inputs completed all five model methods and produced a matched-date comparative report. This is **not an investment experiment**; no user's private cache was available in the execution environment. No new net whole-fund return or Sharpe improvement is claimed.

### References

Engle (2002) Dynamic Conditional Correlation; Shephard & Sheppard (2010) HEAVY; Harvey (2013) Dynamic Models for Volatility and Heavy Tails; Creal, Koopman & Lucas (2013) Generalized Autoregressive Score Models; Kastner (2019) sparse Bayesian factor SV; Pitt & Shephard (1999) particle filters; Fan, Liao & Mincheva (2013) POET; Patton (2011) imperfect realized-volatility proxies.
