# Joint geometry extension for the existing advanced research suite

**Branch:** `research/manifold-spd-grassmann-diffusion-20261121`  
**Stacked on:** PR #188, `research/joint-state-sv-regimes-alpha-mpc-20261120`  
**Operational scope:** read-only research. No orders, broker requests, HTTP/network, live weights, fund-data commits, H9 forward reads or trading-rule changes. Every scoring/fit routine uses the already available **2016–2019 intraday** and **2013–2019 MASTER development** caches only. See `SPEC.md` for equations, causal cutoff and source papers.

## Included executable model families

| Method group | Methods | Score / target |
|---|---|---|
| Covariance / positive-definite geometry | Euclidean fixed-basis mean, Log-Euclidean and affine-invariant Karcher means, Bures–Wasserstein barycenter, SPDNet (learnable Stiefel BiMap + ReEig/LogEig) | Same-origin next-5-session factor realized-covariance Stein and QLIKE |
| Strong conventional covariance controls | Fixed-factor sample covariance, EWMA `.94`, HEAVY, realized GARCH | **Same factor basis, dates, realized-covariance targets** |
| Factor-subspace and latent states | Grassmann principal angles, affine-invariant intrinsic regime prototypes, density-corrected diffusion maps + Nyström + HMM (with/without Grassmann drift) | Filtered next-5-session factor-portfolio risk; no hindsight state labels |
| Conditional MASTER efficacy | Gaussian process on log-SPD, diffusion-map GP, joint SPD/macro GP, Fisher–Rao regime-probability GP, nonlinear diffusion-gated neural mixture-of-experts | Weekly MASTER rank-slope forecast error, using only fully matured 5-session labels |
| Robust multi-period control | SPD geodesic covariance ambiguity, Bures/affine/Log-Euclidean risk families, Student-t mixture paths, worst-case factor-risk epigraph and CVaR MPC | Feasibility and **model-only predicted** utility, NOT portfolio backtest return |

These algorithms are separate from the **original, unchanged** risk/alpha/control code in PR #188, which remains a benchmark. No test in this branch establishes a new whole-fund net Sharpe.

## Local setup

Use a **separate worktree**, not `main` or the live execution worktree. The branch is stacked on PR #188, so it already includes that source tree.

```bash
cd ~/test_trading_agent
git fetch origin research/manifold-spd-grassmann-diffusion-20261121
git worktree add --detach ~/joint_geometry_research origin/research/manifold-spd-grassmann-diffusion-20261121
cd ~/joint_geometry_research

python3.12 -m venv /private/tmp/joint_geometry_venv
source /private/tmp/joint_geometry_venv/bin/activate
python -m pip install -r research/nextgen/joint_state/requirements-base.txt
python -m pip install -r research/nextgen/joint_state/requirements-advanced.txt
python -m pytest -q research/nextgen/joint_geometry/tests
```

Only install dependencies into the isolated venv, not your research/production environments. Torch is needed for `spdnet` and `manifold_moe`; CVXPY for `control`. Existing PR #188 PyMC/ArviZ environment compatibility is not required by the new manifold implementation.

## Cache discovery and first contract check

Set paths **where the data actually live** (not necessarily this worktree). The code **reads the original NPZs only**.

```bash
export HF=/absolute/path/to/riskfield/.cache/riskfield/hf.npz
export DEV=/absolute/path/to/test_trading_agent/.cache/tree/dev.npz

python -m research.nextgen.joint_geometry.runner check \
  --hf-cache "$HF" --alpha-cache "$DEV"
```

Inputs: `HF` has `S` dates, `names`, `R` `(T,14,N)` log returns and `rv`; `DEV` has `S`, `names`, `master_h5_ref`, `y5`, `elig`, `rm`, `beta`. The 2016–2019 HF panel is truncated before 2020; alpha cache must itself end at 2019-12-31 or earlier. Output forbidden inside either repo or any data cache. `check` writes nothing. Each other run requires a **new nonexistent** output folder.

## Experiments — can run independently or concurrently

### 1. SPD covariance including HEAVY and GARCH controls

```bash
OPENBLAS_NUM_THREADS=3 OMP_NUM_THREADS=3 python -m research.nextgen.joint_geometry.runner covariance \
  --hf-cache "$HF" --rank 4 \
  --methods sample_cov ewma_cov heavy realized_garch euclidean logeuclidean affine bures spdnet \
  --epochs 350 --seeds 11 17 23 \
  --out "$HOME/ResearchData/joint_geometry/covariance_01"
```

This can be compute intensive: refits of HEAVY/GARCH at weekly origins and optional neural SPDNet. **Do not read the resulting method scoreboard to tune hyperparameters on 2018–19 without logging the new trial**. First run an exact source contract and use baseline scores on exactly matched dates. The code trains the fixed factor basis before July 2016; SPDNet targets must mature by December 2017; scores are 2018–19 development only.

### 2. Filtered nonlinear manifold regimes

```bash
OPENBLAS_NUM_THREADS=3 python -m research.nextgen.joint_geometry.runner states \
  --hf-cache "$HF" --rank 4 --states 3 --dimension 3 \
  --methods airm diffusion_hmm diffusion_grassmann \
  --out "$HOME/ResearchData/joint_geometry/states_01"
```

Density-corrected diffusion maps are trained before 2018. HMM states are filtered sequentially through the test period; Karcher means from the intrinsic AIRM model also remain frozen. Risk QLIKE is compared against frozen training risk. This is **not** evidence the regime predicts expected return direction.

### 3. Manifold-conditional MASTER alpha reliability

```bash
OPENBLAS_NUM_THREADS=3 OMP_NUM_THREADS=3 python -m research.nextgen.joint_geometry.runner alpha \
  --hf-cache "$HF" --alpha-cache "$DEV" --rank 4 \
  --methods constant logspd_gp diffusion_gp logspd_macro_gp fisher_gp manifold_moe \
  --refit 13 --epochs 400 --seeds 11 17 23 \
  --out "$HOME/ResearchData/joint_geometry/alpha_01"
```

The rank slope is an ex-post completed 5-session residual-return target, **not** a return available on the signal date. Gaussian processes propagate predictive uncertainty, MoE trains on already matured weekly labels with chronological early stopping, Fisher–Rao uses full *filtered* regime probabilities rather than hard state-switching.

### 4. Geodesic covariance ambiguity and distributionally robust MPC

```bash
OPENBLAS_NUM_THREADS=3 python -m research.nextgen.joint_geometry.runner control \
  --hf-cache "$HF" --alpha-cache "$DEV" --rank 4 \
  --origin 2019-11-01 --metric affine \
  --financing segregated --scenarios 1000 --horizon 4 \
  --out "$HOME/ResearchData/joint_geometry/mpc_01"
```

Outputs are a **model-predicted first-step portfolio diagnostic only**, not a real trade, live portfolio policy, approved alpha or measured Sharpe. Compare `affine`, `logeuclidean`, `bures` only within development/trial inventory; do not cherry-pick after viewing an already-reused investment window. This layer uses the historical soft gross convention **explicitly**; it must not be confused with the hard cap of any live account.

## Engineering smoke tests (NOT investment experiments)

For a quick one-time integration check, use separate new output directories and `--max-origins 3 --epochs 7 --seeds 11` for covariance; `--max-origins 3` for states; `--first 2018-05-01 --max-origins 3 --epochs 7 --seeds 11` for neural alpha. These settings are only to detect missing packages, schema or numerical faults—not to select an investment model. The bundled automated tests use generated mathematical fixtures; their returns and risk scores must **never** be quoted as empirical trading improvements.

## Known quality gates and what happens next

- Riskfield's half-hour bars use **current S&P constituents**, not independently proven point-in-time eligibility. A 2018–19 predictive score is descriptive and cannot certify original historical issuer membership. No CIK join is attempted.
- All geometry-based risk and market features use **returns only through the prior completed session** (`t−1`) because the actual order clock can precede Thursday's official close. MASTER score timestamp remains an independent external prerequisite; the optimiser produces no live order.
- Only 2018–19 *development* scoring is allowed. 2020–25 has already been repeatedly opened; it is not a fresh holdout. The broad-book H9 104-week lock is untouched. No forward MASTER allocation shadow is registered by these commands.
- The next economic test is separate: freeze one decision model and a **matched-capital trend-core + MASTER champion** under broker-credible financing, then measure whole-fund **cash-excess net Sharpe** and annual net return. Forecast QLIKE/MSE alone does not equal a performance increase.

## Output schema

Each run creates `MANIFEST.json` and `RESULT.json` in a new folder outside the repositories/caches. The manifest records cache checksums, cutoff, model names, risk basis fit time, survivorship warning and the explicit label `economic_fund_return_improvement=NOT_TESTED`. Results include per-date forecast losses, by-year scores, paired HAC where enough origins, posterior uncertainty and numerical optimizer feasibility. No automatic model promotion occurs.
