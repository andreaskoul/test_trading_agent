# Advanced research audit addendum — 2026-11-22

**Scope:** This branch stacks on `research/coupled-factor-tail-risk-20261122` (PR #191), which already stacks on #189 and #188. Nothing is merged into `main` or production `fund/`.

## Two corrected mathematical contracts

### 1. Particle SV posterior covariance must integrate the whole covariance matrix

For the filtered, resampled latent log-variance particle distribution `h^(p)` and frozen factor-return correlation `R0`, the one-step forecast uses

```text
h_next^(p) = mu + phi * (h_filter^(p) - mu)
s_i^(p) = exp(h_next_i^(p) / 2)
Sigma_ij(next) = R0_ij / P * sum_p s_i^(p) * s_j^(p)
```

The previous version calculated `R0_ij * sqrt(E[s_i²] E[s_j²])`, which is **not** `E[s_i s_j] R0_ij` unless the relevant volatility uncertainty degenerates appropriately. The corrected estimator preserves positive semidefiniteness because it averages PSD covariance matrices. It uses plug-in mean transition without adding next-period transition noise, consistent with a one-step conditional-mean latent forecast. Thus this is not a full posterior predictive integration over transition innovations; a later research comparison could add that as a separately registered model.

### 2. The proxy follows the same information set as the factor forecast

At origin index `t`, the factor covariance training slice is `[t-lookback, t)`, and the scored future is `[t+1,t+6)`. To prevent a partial `t` information mismatch, the optional MASTER rank-book proxy now takes `master_h5_ref[t-1]` and computes its SPY trend over exactly `[t-200,t)`. The proxy no longer silently replaces missing SPY returns with zero. A missing earlier session fails closed with `INCOMPLETE_TREND_HISTORY`.

**Important remaining timing limitation:** this is an internally coherent prior-session research contract, not an independently certified live execution timestamp. The output is an *unhedged proxy*, not a backtest of the actual fund book.

## Review / tests

```bash
git fetch origin research/advanced-research-audit-20261122
git worktree add --detach ../advanced-research-audit origin/research/advanced-research-audit-20261122
cd ../advanced-research-audit
python3.12 -m venv /private/tmp/advanced-audit-venv
source /private/tmp/advanced-audit-venv/bin/activate
python -m pip install -r research/nextgen/joint_state/requirements-base.txt
python -m pytest -q research/nextgen/coupled_risk/tests
```

For all suites and optional heavy models, follow `research/nextgen/ADVANCED_RESEARCH_EXECUTION_MATRIX_20261122.md` (from the parent research branch), in a separate environment as documented. The full risk/alpha comparison must use the owner's existing local inputs. Research scoring cannot establish a whole-fund net Sharpe increase.

## Verification status

- Three source/test files changed and committed to the isolated audit branch.
- Three new regression cases added, including same-origin data perturbations.
- **Tests have not been executed on this new audit commit in this tool environment:** GitHub repository content was inspected via the connector, but the execution container cannot resolve GitHub. Previously reported 26 green tests for PR #191 were on the prior commit and must not be presented as verification of these amendments.
- Do not merge before the owner runs tests and checks actual private development cache inputs.
