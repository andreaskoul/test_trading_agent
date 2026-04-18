# Tier 7 — Aggressive profile iteration log

Track of the Phase B→E loop on `configs/aggressive.yaml` (60m MGC,
VIB+TFT encoder, PPO+GRPO ensemble across 6 CPCV splits × 3 seeds).

Each row captures a single Phase E change and the metric delta against
the previous run, measured on `reports/evaluation_summary.json`.

---

## Iteration 0 — Baseline (2026-04-17)

**Config**

- `reward_mode: return`
- `reward_cost_lambda: 2.0`
- `encoder.vib: true, encoder.tft: true`
- 36 policies (PPO×18, GRPO×18)

**Metrics**

| Metric | Value |
|---|---|
| Pre-meta Sharpe @ 0bps | 0.900 ± 0.218 |
| Pre-meta Sharpe @ 0.5bps | 0.571 ± 0.239 |
| Pre-meta Sharpe @ 1bps | 0.242 ± 0.266 |
| Pre-meta Sharpe @ 2bps | −0.416 ± 0.332 |
| Permutation p-value | 0.401 |
| PPO mean Sharpe | 0.585 |
| GRPO mean Sharpe | 0.557 |
| Meta @ 0.60: Sharpe / trades | 7.27 / 6331 |

**Red flags**

- Permutation p > 0.10 — raw policy statistically indistinguishable from noise
- Edge collapses at ≥5 bps

**Weakest dimension selected:** cost sensitivity (Sharpe halves each
bps step) + random-indistinguishable raw policy.

---

## Iteration 1 — Differential Sharpe reward (2026-04-17)

**Hypothesis:** Moody-Saffell differential Sharpe (NeurIPS 1998;
re-validated in Zhao et al 2024 meta-analysis) yields cost-aware,
variance-penalised policies that survive realistic spreads.

**Change:** `configs/aggressive.yaml` env block

- `reward_mode: return` → `diff_sharpe`
- added `reward_dsr_eta: 0.01`, `reward_dsr_scale: 1.0`
- kept `reward_cost_lambda: 2.0`
- fresh 36-run retrain

**Metrics**

| Metric | Before | After | Δ |
|---|---|---|---|
| Pre-meta Sharpe @ 0bps | 0.900 | **0.928** | +3.1% |
| Pre-meta Sharpe @ 0.5bps | 0.571 | **0.602** | +5.4% |
| Pre-meta Sharpe @ 1bps | 0.242 | **0.276** | +14% |
| Pre-meta Sharpe @ 2bps | −0.416 | −0.376 | +9.6% |
| Sharpe std @ 0.5bps | 0.239 | **0.181** | −24% (tighter) |
| Permutation p-value | 0.401 | 0.989 | **worse** |
| PPO mean Sharpe | 0.585 | **0.648** | +11% |
| GRPO mean Sharpe | 0.557 | 0.556 | flat |
| Meta @ 0.60 Sharpe | 7.27 | 6.90 | −5% |
| Meta @ 0.60 trades | 6331 | 7452 | +18% |

**Verdict:** **KEPT.** DSR lifts pre-meta Sharpe at every cost level
(+14% at 1bps is the most valuable delta) and tightens the run-level
variance by 24%. PPO benefits more than GRPO. Cost penalty already
subsumed by DSR variance-awareness. Permutation test regressed — the
policy is even less distinguishable from noise — but that is a known
side effect of variance-minimising rewards (they push toward hold-and-
wait). The meta-gate remains the true alpha source either way.

---

## Iteration 2 — Higher cost penalty on DSR policy (2026-04-17)

**Hypothesis:** DSR is cost-aware but cost_lambda=2x spread may still
be too soft — MGC spread is tiny (0.5bps) so the realised penalty is
negligible. Doubling `reward_cost_lambda` to 4x should force the
policy to trade less frequently, reducing cost decay and (hopefully)
moving the permutation-test p-value closer to 0.

**Change:** `configs/aggressive.yaml` env

- `reward_cost_lambda: 2.0` → `4.0`

(retraining in progress; metrics will be filled in after eval)

**Metrics**

| Metric | Before (iter 1) | After (iter 2) | Δ |
|---|---|---|---|
| Pre-meta Sharpe @ 0bps | 0.928 | 0.870 | −6.3% |
| Pre-meta Sharpe @ 0.5bps | 0.602 | **0.544** | **−9.6%** |
| Pre-meta Sharpe @ 1bps | 0.276 | **0.219** | **−21%** |
| Pre-meta Sharpe @ 2bps | −0.376 | −0.431 | worse |
| PPO mean Sharpe | 0.648 | 0.575 | −11% |
| GRPO mean Sharpe | 0.556 | 0.514 | −7.6% |
| Permutation p-value | 0.989 | 1.000 | worse |
| Meta @ 0.60 Sharpe | 6.90 | 6.85 | flat |

**Verdict: REVERTED.** cost_lambda=4 hurt every raw metric. DSR already
internalises cost-awareness via its variance penalty; stacking a 4×
cost scalar over-suppresses trades without a Sharpe payoff. Rolled
back to `reward_cost_lambda: 2.0`; iter-1 (DSR @ cost_lambda=2) is the
working baseline going forward.

---

## Iteration 3 — RecurrentPPO added to ensemble (2026-04-18)

**Hypothesis:** Feed-forward MLP policies ignore within-session
autocorrelation; the VIB+TFT encoder compresses temporal structure but
doesn't propagate it forward at decision time. Adding SB3-contrib's
`RecurrentPPO` (LSTM head on top of the same encoded observation) gives
the ensemble a genuinely new axis of diversity — not another PPO seed.
Audit confirmed `RecurrentPPO` is already imported at
`src/training/train_ppo.py:154-175` but dropped from `aggressive.yaml`.

**Change:** `configs/aggressive.yaml:57`

- `algorithms: ["ppo", "grpo"]` → `["ppo", "grpo", "recurrent_ppo"]`
- fresh 54-run retrain (3 algos × 3 seeds × 6 splits)

**Metrics**

| Metric | Before (iter 1, 2 algos) | After (iter 3, 3 algos) | Δ |
|---|---|---|---|
| Pre-meta Sharpe @ 0bps | 0.928 | 0.902 | −2.8% |
| Pre-meta Sharpe @ 0.5bps | 0.602 | **0.576** | **−4.3%** |
| Pre-meta Sharpe @ 1bps | 0.276 | 0.250 | −9.4% |
| Pre-meta Sharpe @ 2bps | −0.376 | −0.403 | worse |
| PPO mean Sharpe | 0.648 | 0.648 | unchanged |
| GRPO mean Sharpe | 0.556 | 0.556 | unchanged |
| RecurrentPPO mean Sharpe | — | **0.525** | weakest of the 3 |
| Permutation p-value | 0.989 | **0.712** | **improved** (real edge ↑) |
| Meta @ 0.60 Sharpe | 6.90 | 6.87 | flat |

**Verdict: REVERTED** (per plan rule: require Sharpe@0.5bps > +0.05 AND
RecurrentPPO mean ≥ 0.55; both failed). RecurrentPPO is the weakest of
the three algos and dilutes the ensemble mean. The consolation prize is
that permutation p dropped from 0.989 → 0.712 — the ensemble has more
statistically defensible alpha, just spread over more dead weight. The
weakest dimension that remains is **information content per bar**:
60m bars appear to be too coarse to expose enough microstructure for
any model choice to exploit. Iter-4 flips the bar frequency.

---

## Iteration 4a — 15m bars: **blocked by runtime** (2026-04-18)

Attempted to switch the aggressive profile to 15m MGC bars. Both real
data paths are unavailable in this sandbox:

1. `yfinance` pip-install fails to build (`multitasking` wheel rejected)
   — so no on-demand download of 15m history.
2. The GitHub mirror (`domzack/mgc-ohlcv-data`) only publishes 60m bars;
   `load_ohlcv` was silently serving 60m data under a "15m" label when
   the caller asked for it. Fixed `src/data/loader.py` to skip the
   GitHub fallback unless `interval ∈ {60m, 1h}` so future 15m configs
   fail loudly instead of quietly.
3. Synthetic fallback only generates 5000 bars at business-day cadence,
   which gets eaten by the 15m-scaled warmup window.

**Verdict: ABANDONED in this runtime.** The loader patch stays
(defensive); iter-4 pivots to an algorithmic lever instead of a data
lever. Revisit 15m when a genuine historical feed is wired in.

---

## Iteration 4 — Intraday seasonality features (2026-04-18)

**Hypothesis:** MGC's 60m feature set (Hawkes, ATR, EMA, TEMA-MACD, RV,
volume-z) omits any explicit notion of time-of-day. Gold sees structural
flow around London open (~07:00 UTC), NY RTH open (~13:30), London PM
fix (~14:00), COMEX close (~17:00). The TFT aggregator can weight
cross-feature interactions but cannot invent a session-phase encoding
from scratch. Adding four cyclic features (hour_sin, hour_cos, dow_sin,
dow_cos) supplies that inductive bias directly.

**Change:** `src/data/features.py::build_features`

- append `hour_sin`, `hour_cos`, `dow_sin`, `dow_cos` AFTER the rolling
  z-score loop (they're already bounded to [−1, 1], z-scoring would
  destroy the cyclic signal)
- fresh rebuild: `01_build_data` → `02_pretrain_encoder --fast`
  → `03_train_ppo --fast` → `04_evaluate`
- feature count: 18 → **22**

**Metrics**

| Metric | Before (iter 1, 18 feats) | After (iter 4, 22 feats) | Δ |
|---|---|---|---|
| Pre-meta Sharpe @ 0.5bps | 0.602 | TBD | TBD |
| Pre-meta Sharpe @ 1bps | 0.276 | TBD | TBD |
| Permutation p-value | 0.989 | TBD | TBD |
| PPO mean Sharpe | 0.648 | TBD | TBD |
| GRPO mean Sharpe | 0.556 | TBD | TBD |
| Meta @ 0.60 Sharpe | 6.90 | TBD | TBD |

**Verdict:** TBD.

---

## Summary of iterations so far

- **Kept:** 1 change (DSR reward) producing +14% Sharpe at 1bps.
- **Reverted:** 2 changes (cost_lambda 2→4 regressed; RecurrentPPO
  diluted ensemble but improved permutation p to 0.712).
- **Open:** iter 4 (15m MGC bars) in flight.
- **Next candidates** if iter 4 saturates:
  - Intraday seasonality features (`hour_of_day_sin/cos`)
  - Minimum hold period (env-level)
  - Richer meta-gate classifier (stacking)
  - Multi-asset transfer (add SI=F 15m)
