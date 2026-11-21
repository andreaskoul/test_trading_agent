# JOINT-01 — academic risk, regimes, MASTER alpha and robust trading research

**Branch:** `research/joint-alpha-risk-models-20261121`  
**Status:** research-only implementation; tests and fixture integration completed. **No actual MASTER economic uplift measured.**

This is a new isolated research package. It **never** imports `fund/` or a trading SDK, places orders, fetches market data, rewrites existing datasets, or touches locked H9 forward records. It runs on **your own caches**. Dates after **2019-12-31** are hidden in the risk runners and explicitly prohibited for alpha calibration. Past 2020–2026 has already been examined and MUST NOT be treated as a fresh held-out model-selection window.

### Setup

```bash
cd /path/to/test_trading_agent
python3 -m venv /tmp/joint01-venv
source /tmp/joint01-venv/bin/activate
python -m pip install -r research/joint_risk_alpha/requirements.txt
# Optional expensive backends:
python -m pip install 'torch>=2.2' 'cvxpy>=1.5'
# Optional alternative Bayesian implementation (native particle-MCMC does NOT require it):
python -m pip install 'pymc>=5' 'arviz<1'
PYTHONPATH=. python -m pytest -q research/joint_risk_alpha/tests
```

`pymc` may be incompatible with very new ArviZ; use the built-in `sv` particle-MCMC engine instead. `cvxpy` is required only for the `mpc` stage; it is not imported by the other tracks.

### Cache locations

`hf.npz`: the existing `research/riskfield/panel.py bars` output. It contains `S` (sessions), `names` with SPY, `R` (session × 14 × ticker: overnight + 13 30-minute log returns), `rv` (realised variance). The original 2016–2025 file is accepted; the runner masks dates after December 2019 **before fitting or scoring anything**.

`dev.npz`: the pre-2019 ".cache/tree/dev.npz" consumed by `research/tree/harness.py`, containing `S, names, master_h5_ref, y5, elig, Z, r, rm`. No model retraining of the original MASTER weights. The file MUST end by 2019-12-31, and the five-session labels mature six trading sessions after decision; the runner respects this cutoff.

Example paths below are illustrative: use the actual worktree locations confirmed by the coordinator. The project uses **no** `.cache/p8/edgar/ciks.json` map, ticker-specific filings or connected accounts.

### Read-only run sequence

```bash
cd /path/to/test_trading_agent
HF="/absolute/path/to/riskfield/worktree/.cache/riskfield/hf.npz"
DEV="/absolute/path/to/research/tree/worktree/.cache/tree/dev.npz"
OUT="$HOME/ResearchData/joint01_20261121"
mkdir -p "$OUT" && chmod 700 "$OUT"

# 1. Dynamic factor risk: fixed PCA calibrated 2016–2017, evaluated 2018–2019.
#    Four DISTINCT methods; all outcomes are already development/reused evidence.
PYTHONPATH=. OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 \
python -m research.joint_risk_alpha.runner risk \
  --hf "$HF" --models ewma,poet,heavy,garch \
  --factors 4 --max-names 120 --stride 21 --lookback 252 \
  --out "$OUT/risk_comparison.json"

# 2. More expensive Bayesian factor stochastic volatility: particle marginal MH
#    300 posterior draws, 150 burn iterations, 256 particles per factor per origin.
PYTHONPATH=. OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 \
python -m research.joint_risk_alpha.runner risk \
  --hf "$HF" --models ewma,sv --factors 4 --stride 63 \
  --sv-draws 300 --sv-tune 150 \
  --out "$OUT/risk_bayesian_particle.json"

# 3. Causal latent regimes: Gaussian HMM, explicit-duration HSMM, and BOCPD.
PYTHONPATH=. python -m research.joint_risk_alpha.runner regimes \
  --hf "$HF" --states 3 --max-duration 20 \
  --out "$OUT/regime_filters.json"

# 4. MASTER dynamic signal strength: hierarchical Kalman, posterior soft gate,
#    nonlinear Torch mixture-of-experts (no new independent alpha).
PYTHONPATH=. OMP_NUM_THREADS=2 python -m research.joint_risk_alpha.runner alpha \
  --dev "$DEV" --models constant,kalman,gated,moe \
  --moe-hidden 64 --moe-experts 3 --moe-epochs 250 --device cpu \
  --out "$OUT/master_alpha_strength.json"

# Faster split calibration, excluding the nonlinear network:
PYTHONPATH=. python -m research.joint_risk_alpha.runner alpha \
  --dev "$DEV" --models constant,kalman,gated \
  --out "$OUT/master_alpha_reference.json"
```

For MPS acceleration on newer Macs, change `--device cpu` to `--device mps` for the nonlinear MoE; GPU acceleration is not required for the other models. Increase posterior draws, warmup, factors, names and architectures **when academically justified**, while preserving the number of model trials and using only time-causal development validation. Do not alter settings after reviewing 2020–2026. For more frequent risk origins, reduce `--stride` from 21 to 5; `sv` costs rise roughly linearly with origin count × particle count × draws × history length.

### Joint predictive scenarios → Wasserstein-robust CVaR MPC

The optimizer is functional **only when given proper, dated predictive forecasts**. The research pipeline deliberately does NOT pretend that cross-sectional MASTER rank scores are calibrated five-session expected return inputs.

Prepare a model forecast file, outside the repo and with no future realised returns, containing:

| Key | Shape | Meaning |
| --- | --- | --- |
| `mu` | `(H, N+1)` | Conditional expected weekly NAV excess return per asset; **last column SPY** |
| `cov` | `(N+1, N+1)` | Positive-definite one-week predictive covariance in matching units |
| `alpha_std` | `(H, N+1)` | Nonnegative posterior mean uncertainty |
| `previous` | `(N,)` | Current *hypothetical* stock-book weights, NAV units |
| `beta` | `(N,)` | Dated SPY beta exposures (stock book) |
| `core`, `hedge_prev` | scalars | Frozen SPY trend-core exposure and prior SPY book hedge |
| `asof`, `fit_end`, `label_maturity_end` | date strings | Data provenance, **all ≤ 2019-12-31** |
| `half_spread_bp`, `adv_max_weight_change` | optional `(N,)` | Measured spread and ADV weight-change caps |

```bash
# Prediction-only forecast NPZ -> Student-t scenarios, frozen seed.
PYTHONPATH=. python -m research.joint_risk_alpha.runner scenario \
  --forecast-npz "$OUT/causal_forecast.npz" --draws 1024 --df 6 \
  --out "$OUT/predictive_scenarios.npz"

# Convex MPC: CVaR of net fund loss, nonlinear impact, gross/borrow,
# scenario uncertainty, Wasserstein linear-return ambiguity penalty.
PYTHONPATH=. python -m research.joint_risk_alpha.runner mpc \
  --scenario-npz "$OUT/predictive_scenarios.npz" \
  --gross 1.9 --wasserstein-radius .0005 \
  --out "$OUT/mpc_hypothetical_weights.json"
```

**CRITICAL:** The `mpc` mode writes hypothetical **research** weights only. Never load those into the live broker or `fund/`. The current cap argument is a comparable **hard** research constraint; the historical B0 soft 1.9× rule is NOT identical. Before any paired fund comparison, both champion and candidate must use the same owner-approved gross/core/hedge/cost/financing rule. Under a frozen core already using excess gross, the hard optimizer may legitimately find little space for stock alpha.

### Mathematical evaluation and stop/go hierarchy

1. **Risk prediction**: paired mean Gaussian predictive log-score and variance QLIKE for the *same* next-five-session realised factor covariance, plus tail calibration when available. Pre-fit basis and model only on completed historical data. The first PCA factor is SPY; three additional principal component factor portfolios are learned from 2016–2017. POET operates in the underlying stock cross-section and is projected into the same factor basis. The covariance scores are *not* NAV return Sharpe.
2. **Regime inference**: compare filtered HMM vs explicit-duration HSMM vs BOCPD probabilities for causal changes in future factor volatility; identify state instability and label scarcity before attempting any trade gating. Never use full-sample Viterbi or smoothing.
3. **Conditional alpha**: compare constant MASTER cross-sectional efficacy, delayed-update Bayesian Kalman, a soft filtered-state Bayesian ridge and nonlinear MoE. The measured target is the slope of future five-session `y5` on frozen MASTER ranks, not next-week fund Sharpe; weekly clusters, 2017–2019 calendar development splits, label maturation and held-out-week MSE matter. Do not count each security as an independent regime event.
4. **Portfolio decision**: integrate credible causal *return-unit* forecasts and predictive covariance with conservative settled-debit/short proceeds, actual spreads/impact and the approved core/cap policy. Evaluate paired **whole-fund** excess Sharpe/CAGR/tails, not predicted objective. This layer remains an interface until broker financing and causal forecasts can be joined.
5. **Forward proof**: reused 2020–2026 history is not a new holdout. Need independent approved P9 shadow protocol with locked read, separate from H9 104-week F0/F1/F2 broad-book experiment, before any promotion. No orders, merge or changes to `main`.

**Risks explicitly retained:** current-member intraday survivorship bias; truncated horizon of intraday histories; forecast covariances based on overlapping log-return quadratics; weak number of independent historical *regimes*; negative early-sample MASTER efficacy; paper financing does not equal live costs; conditional covariance forecast improvement ≠ net investment edge.

**Model inventory:** EWMA, POET, HEAVY, realized GARCH, particle-MCMC SV, optional PyMC SV, Gaussian HMM, HSMM, BOCPD, dynamic-Kalman MASTER, Bayesian softly-gated MASTER, nonlinear MoE, Student-t posterior predictive simulation, distributionally robust CVaR MPC. All are **research implementations**, not independently validated performance improvements.
