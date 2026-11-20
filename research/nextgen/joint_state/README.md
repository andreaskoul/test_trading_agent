# Joint-state research: all serious-compute model families

**Branch:** `research/joint-state-sv-regimes-alpha-mpc-20261120` (draft research only)

**Purpose:** investigate the joint conditional law of market/factor risk, latent states and the profitability of the *existing* MASTER alpha, then solve a robust multi-period policy. This is **not a replacement for the live fund** or the locked H9 forward program. None of these diagnostic model-fit runs authorizes a trading change.

## Precisely what is implemented

| Family | Actual executable estimator | Primary scope |
|---|---|---|
| Covariance | Rolling causally fitted PCA factors + POET sparse positive-definite residual | risk, 5-session |
| Conditional variance | HEAVY-style realized-variance recursion with stationarity constrained QML | factor risk |
| Conditional variance | Joint Gaussian quasi-likelihood realized GARCH with return/measurement equations | factor risk |
| Bayesian covariance | PyMC AR(1) latent factor log-volatility, Student-t return likelihood, NUTS or ADVI posterior variance | factor risk + credible intervals |
| Market states | Gaussian HMM, log-space EM, live filtered probabilities, predictive likelihood | risk state |
| Market states | Explicit-duration, expanded-state Gaussian HSMM, learned duration PMFs | risk-state persistence |
| Breaks | Adams–MacKay conjugate Normal–Inverse-Gamma Bayesian online change-point filter | structural shifts |
| Conditional MASTER | Kalman empirical-Bayes AR(1) time-varying alpha coefficient | weekly label reliability |
| Conditional MASTER | Full PyMC Bayesian AR(1) alpha efficacy posterior | parameter uncertainty |
| Conditional MASTER | Bayesian ridge/partial-pooling regression on known market state features | state-dependent efficacy |
| Nonlinear MASTER | Multi-seed PyTorch soft mixture-of-experts, chronological early stopping and uncertainty | nonlinear conditional efficacy |
| Portfolio control | Student-t posterior predictive paths, CVXPY multi-period stochastic CVaR, uncertainty/risk penalty, margin+borrow+SPY/stock cost, common gross rule | **model decision diagnostic only** |

No stub simulation results are reported as returns. Mathematical details and reference research design are in `SPEC.md`.

## Environment

Use an isolated Python **3.12** venv and read requirements before installing. To run only tests and POET/HMM/Kalman, NumPy + SciPy + Pandas + pytest suffice. Advanced `torch`, `pymc`, `arviz`, `pytensor` and `cvxpy` are separate optional installs because platform binary compatibility varies. On an M-series Mac, PyMC can be expensive in memory and CPU; monitor peak RAM but **do not arbitrarily cap research compute because the model is sophisticated**.

```sh
python3.12 -m venv /private/tmp/joint_state_venv
source /private/tmp/joint_state_venv/bin/activate
python -m pip install -r research/nextgen/joint_state/requirements-base.txt
python -m pip install -r research/nextgen/joint_state/requirements-advanced.txt
python -m pytest -q research/nextgen/joint_state/tests
```

If PyMC errors on ArviZ imports, use a clean venv with versions resolved together; do not modify your existing research environment. The PyMC NUTS path has **not** been run on the assistant's environment due to a preinstalled ArviZ/PyMC compatibility error. CVXPY is absent in that environment as well; its executable path is tested only after you install the advanced dependencies.

## Existing input schemas: no data build necessary

- **Risk:** `.cache/riskfield/hf.npz` from `research/riskfield/panel.py bars` with `S` sessions, `names`, `R` shape `(T,14,N)`, `rv` shape `(T,N)`. The loader truncates to **2019-12-31** and flags historical current-constituent survivorship. No CIK joins are attempted.
- **MASTER development:** `.cache/tree/dev.npz` from `research/tree/harness.py load()` containing `S`, `names`, `master_h5_ref`, `y5`, `elig`, `rm`, `beta`. This file must end on or before **2019-12-31**. `y5` must be a genuinely completed *5-session future residual-return* label; each origin is fit only after label maturity. The code stops if it finds a different schema.
- Run from the **test_trading_agent repository root** with `python -m research.nextgen.joint_state.runner ...`. The branch is intentionally isolated at `research/nextgen/joint_state/`.

Example paths (adjust to the true worktrees):

```sh
export HF="$HOME/test_trading_agent/.claude/worktrees/riskfield/.cache/riskfield/hf.npz"
export DEV="$HOME/test_trading_agent/.cache/tree/dev.npz"
python -m research.nextgen.joint_state.runner check --hf-cache "$HF" --alpha-cache "$DEV"
```

### Run A — risk forecasting (all four models)

Full model comparison, with the Bayesian model deliberately allowed to perform substantial inference:

```sh
python -m research.nextgen.joint_state.runner risk \
  --hf-cache "$HF" --models poet heavy realized_garch bayes_sv \
  --factors 3 --lookback 252 --step 42 --draws 700 \
  --out "$HOME/ResearchData/joint_state/risk_a_20261120"
```

For a **small engineering smoke run**, pass `--max-names 80 --max-origins 2 --draws 100`; that is NOT a representative full empirical comparison. The full run can be expensive, especially Bayesian NUTS across origins and factors. Outputs contain 5-day QLIKE on two *test portfolios*, not actual MASTER NAV. The data reader stops on unexpected data quality; do not bypass coverage failures to force a pass.

### Run B — filtered regimes (all three methods)

```sh
python -m research.nextgen.joint_state.runner regimes \
  --hf-cache "$HF" --models hmm hsmm bocpd \
  --out "$HOME/ResearchData/joint_state/regimes_b_20261120"
```

The HMM/HSMM are trained before 2018 and scored with 2018–19 online predictive densities; the Bayesian change-point track reports per-date posterior break probabilities instead of a directly comparable multivariate density. **Do not select a regime count based on 2020–26 fund returns.** Label state permutations have no economic interpretation without interpretation and robustness checks.

### Run C — conditional MASTER alpha (all five methods)

```sh
python -m research.nextgen.joint_state.runner alpha \
  --alpha-cache "$DEV" --models constant kalman state_regression moe bayesian \
  --refit-every 13 --draws 700 --device cpu \
  --out "$HOME/ResearchData/joint_state/master_c_20261120"
```

This uses 2013–2016 matured development labels for initial training and scores 2017–19. Every weekly origin updates training **only after five future sessions have matured**; origin dates are not shuffled. Models predict the weekly decile rank-slope and report MSE and Gaussian negative log-density using the original per-week sampling variance. The neural model uses a chronological validation fold and multiple seeds. If PyMC inference is expensive, it is acceptable to run only C's Bayesian component separately with `--models bayesian` and a new output directory; do not change its design based on 2020–2026 results.

### Run D — posterior-path robust multi-period optimization

```sh
python -m research.nextgen.joint_state.runner optimize \
  --hf-cache "$HF" --alpha-cache "$DEV" --origin 2019-11-01 \
  --forecaster heavy --factors 3 --lookback 252 \
  --scenarios 1000 --horizon 4 --financing segregated \
  --out "$HOME/ResearchData/joint_state/mpc_d_20261120"
```

This executable **integrates** a causal MASTER efficacy posterior, factor covariance, multivariate Student-t posterior scenarios, hard matched portfolio cap and SPY hedge, turnover, capital, cash and borrow assumptions. The output is a *model-predicted policy diagnostic*, NOT a historical backtest or evidence of improved net Sharpe. It does not send orders. Do not adopt the policy without a matched whole-fund empirical accounting comparison and a separately approved Protocol-9 forward shadow. Financing assumptions must be reconciled with the independently scheduled broker study.

## Contract gates and disclosures

- **Read-only inputs:** no broker APIs, no GitHub API, no HTTP requests, no scraping, no writes into either cache. Creates one previously nonexistent output directory only; refuses to overwrite.
- **No future labels:** covariance PCA and volatility training use strictly earlier intraday sessions; alpha models fit only completed 5-session targets; regime states are *filtered*, not hindsight smoothed.
- **Survivorship:** current-member HF panel cannot be used as a clean historical PIT portfolio without reconstruction. The result explicitly records that limitation; if live coverage is inadequate, the economic evaluation is blocked.
- **2020–26:** already-viewed data and the existing H9 104-week holdout are not opened by these experiments. The experiments only score **development <=2019**.
- **Posterior uncertainty:** Bayesian full SV/alpha NUTS needs convergence checks (R-hat, effective sample size, divergences) before any decision inference; ADVI is an approximation, not proof of calibrated tails.
- **Research multiplicity:** the prior effective trial inventory is at least 162; this release adds distinct model classes and must expand the log before any future alpha promotion.
- **No promise of higher Sharpe:** the software offers methods, diagnostics and a path to a causal decision study; the actual *whole-fund* incumbent comparator still needs a separate locked experiment.

## Outputs and interpretation

Each run produces a `MANIFEST.json` and model-specific JSON in a new external directory. Files include source SHA-256 hashes. **Risk:** QLIKE versus proper daily realized variance proxies. **Regimes:** filtered state vectors and log predictive density. **Alpha:** prediction error vs frozen MASTER slope baseline. **MPC:** model-predicted utility and feasible first-step targets (never an order). These four output families are distinct and should not be collapsed into a single "Sharpe improvement" until the independent economic experiment.

### Dedicated smoke profile (engineering only)

Use a short, **different** output directory for each command. These are readiness checks, not an investment experiment:

```sh
python -m research.nextgen.joint_state.runner risk --hf-cache "$HF" \
  --models poet heavy realized_garch --factors 2 --step 105 --max-origins 2 \
  --max-names 80 --out "$HOME/ResearchData/joint_state/smoke_risk"
python -m research.nextgen.joint_state.runner regimes --hf-cache "$HF" \
  --models hmm hsmm bocpd --max-names 80 \
  --out "$HOME/ResearchData/joint_state/smoke_regimes"
python -m research.nextgen.joint_state.runner alpha --alpha-cache "$DEV" \
  --models constant kalman state_regression moe --moe-epochs 25 \
  --moe-seeds 11 --refit-every 52 --out "$HOME/ResearchData/joint_state/smoke_alpha"
```

The full programme uses the defaults (400 MoE epochs and three seeds, 13-week rolling refits) and the Bayesian PyMC methods in the main commands above. The smoke settings must not be promoted to model-selection conclusions.

### Compare models statistically on identical development origins

After the separate full model runs finish, perform an exact-date paired comparison (HAC and by-year gains; **no automatic model selection**):

```sh
python -m research.nextgen.joint_state.runner compare \
  --risk-results "$HOME/ResearchData/joint_state/risk_a_20261120" \
  --regime-results "$HOME/ResearchData/joint_state/regimes_b_20261120" \
  --alpha-results "$HOME/ResearchData/joint_state/master_c_20261120" \
  --out "$HOME/ResearchData/joint_state/paired_20261120"
```

The comparison fails if models were scored on different dates or actual labels. Positive development QLIKE, predictive density, or alpha efficacy improvements do **not** prove net whole-fund Sharpe; further research requires a separately registered causal fund-level decision test. If the expensive PyMC model has not finished yet, run comparisons only on completed model files with the required baseline; do not alter hyperparameters using repeated 2020–26 reads.
