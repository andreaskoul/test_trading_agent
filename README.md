# DL+RL Gold Trading Agent

A reference implementation of an xLSTM-encoder + PPO trading agent on gold,
wrapped in the **Minimum Viable Robustness** statistical stack that most
published DL-trading work skips: Combinatorial Purged K-Fold CV, Deflated
Sharpe Ratio, block bootstrap, Monte Carlo permutation test, transaction-cost
sensitivity, and seed ensembling.

The goal of this repo is **not** to claim a deployable edge. It is to make it
easy to tell, from a single report, whether a given configuration actually
has a statistically robust edge — and to fail loudly when it doesn't.

## Architecture

```
data/raw/gold.parquet             (real MGC 60m OHLCV from GitHub)
        |
        v
src/data/features.py              (log returns, ATR, EMA, TEMA-MACD, z-scores)
        |
        v
src/data/triple_barrier.py        (AFML Ch. 3 labels with t1 index)
        |
        +--> src/validation/cpcv.py          (N=6, k=2 -> 15 splits, 5 paths)
        |
        v
src/models/xlstm_lite.py          (sLSTM + mLSTM encoder, 128-dim)
        |
        +--> src/training/pretrain_encoder.py   (Focal Loss, frozen after)
        |
        v
src/env/{trading_env.py, embedding_env.py}      (Gymnasium, TB exits)
        |
        v
src/training/train_ppo.py         (SB3 PPO, 3 seeds, calm->vol curriculum)
        |
        v
src/training/evaluate.py          (DSR, PSR, bootstrap, permutation,
                                   cost sweep, seed ensemble, red flags)
        |
        v
reports/evaluation_report.md + reports/*.png
        |
        v
src/training/finetune.py          (small-lr refinement on held-out 20%)
```

## Data

Real **Micro Gold Futures (MGC) 60-minute OHLCV**, 19 664 bars spanning
2023-01 → 2026-03, fetched from
`raw.githubusercontent.com/domzack/mgc-ohlcv-data`. The loader
(`src/data/loader.py`) falls back to `yfinance` (for users outside a
restricted network) and finally to a GBM/GARCH synthetic series so the
pipeline can always run.

## Reproducing

```bash
pip install -r requirements.txt
python3 tests/test_smoke.py                      # 8 tests, all should pass

python3 scripts/01_build_data.py                 # loader + features + labels
python3 scripts/02_pretrain_encoder.py --fast    # 6 frozen encoders
python3 scripts/03_train_ppo.py --fast           # 6 splits x 3 seeds = 18 PPO runs
python3 scripts/04_evaluate.py                   # -> reports/evaluation_report.md
python3 scripts/05_finetune.py                   # -> reports/finetune_report.md
python3 scripts/06_run_cockpit.py                # -> http://localhost:8765
```

`--fast` is the default session budget (18 runs, 15 000 steps each). Drop it
for the full config (15 splits × 5 seeds × 60 000 steps).

## Running the cockpit

`scripts/06_run_cockpit.py` starts a FastAPI server that serves a
multi-panel dark web cockpit on `http://localhost:8765/` and drives the
trained policies live. Panels:

1. **Price + entry markers + HMM regime shading** (left big panel)
2. **Equity curve** streaming from the paper engine
3. **Trade log** — click any row to get a Claude-generated explanation
4. **Signal gauge** — current position, meta-label P(profit) vs gate
   threshold, HMM regime posterior
5. **Performance overview** — pooled Sharpe, DSR, bootstrap CI, algo
   ensemble, and red flags from the last `evaluation_summary.json`
6. **Explain / chat panel** — type a `trade_id`, get a short plain-English
   explanation anchored in the stored meta-label prob, regime, and
   extreme embedding dimensions

Top-bar knobs: asset selector (GC=F, SI=F, …), manifest run selector,
Replay vs Live mode, replay speed, **realistic cost knobs**
(spread bps, slippage bps, commission USD per round trip), and the
meta-label gate threshold. All cost knobs apply to *the next trade* —
existing trades in the log were recorded under the cost model that was
active when they fired.

The paper engine reuses the exact backtester code path — same env
config, same triple-barrier exit logic, same meta-label classifier —
so replay output is byte-for-byte identical to `04_evaluate.py` for
the same window (enforced by `tests/test_cockpit.py::test_paper_engine_matches_backtest`).

Set `ANTHROPIC_API_KEY` before launching to enable Claude explanations.
Without the key the cockpit falls back to a deterministic template
that still cites the meta-label probability, regime, and P&L.

## What the reports contain

`reports/evaluation_report.md`:
- Sharpe distribution across all PPO runs (mean, std, p5, p50, p95)
- Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014) accounting for the
  number of trials + higher-moment corrections
- Block-bootstrap 95 % CI on pooled trade returns
- Monte Carlo permutation p-value vs shuffle null
- Transaction-cost sweep at 0, 1, 2, 5, 10 bps — collapses here tell you the
  edge is friction-bound
- Seed ensemble Sharpe per CPCV split
- An automatically-populated **"Red flags"** section
- PNGs: Sharpe histogram, equity curves, cost curve

`reports/finetune_report.md`:
- Before / After / Δ table on a held-out 20 % tail window for the best
  (split, seed) by `sharpe − 5·|max_drawdown|`

## Red-flag rules

The evaluation script automatically flags:
- Mean Sharpe ≤ 0
- Deflated Sharpe p-value > 0.05
- Permutation p-value > 0.10
- Mean max drawdown < −25 %
- Edge collapses at ≥ 5 bps transaction cost

If any fire, the report says so in plain text — no hand-tuning to make them
disappear.

## Running the autonomous aggressive stack (Tier 7)

The `aggressive` profile is the experimental 60m MGC overlay that exercises
every Tier-5+ piece (VIB, TFT, GRPO, DSR reward, intraday seasonality).
`configs/default.yaml` is the safe daily baseline; `configs/aggressive.yaml`
shadows it with the hourly settings.

```bash
# one-time: install sb3-contrib for RecurrentPPO (if enabled)
pip install -r requirements.txt

# full pipeline, end to end, under the aggressive profile
TRADING_PROFILE=aggressive python scripts/01_build_data.py
TRADING_PROFILE=aggressive python scripts/02_pretrain_encoder.py --fast
TRADING_PROFILE=aggressive python scripts/03_train_ppo.py --fast
TRADING_PROFILE=aggressive python scripts/04_evaluate.py

# or: the autonomous loop (same profile propagated via subprocess env)
TRADING_PROFILE=aggressive python scripts/99_auto.py
```

Key flags in `configs/aggressive.yaml`:

- `encoder.vib: true` — variational information bottleneck on the xLSTM output
- `encoder.tft: true` — multi-head TFT aggregator across encoder groups
- `encoder.multitask: true` (iter-6) — auxiliary volatility-regression +
  meta-label heads share the xLSTM backbone during pretrain; `.encode()`
  stays shape-invariant so PPO/evaluation are unchanged
- `env.reward_mode: diff_sharpe` — Moody-Saffell differential Sharpe reward
- `ppo.algorithms: ["ppo", "grpo"]` — PPO + GRPO ensemble (6 splits × 3 seeds)
- `features` include 4 cyclic seasonality features (hour/dow sin-cos)
- `data.macro_symbols: [^VIX, ^GSPC, ^TNX]` (iter-6/7) — DeepTrader-style
  exogenous macros fetched from GitHub open-data (VIX daily; SPX/TNX monthly
  forward-filled), encoded as 5/20-bar log-returns; FMP REST API integrated
  as fallback (set `FMP_API_KEY` env var). DXY (`DX=F`) pending FMP domain
  access.
- `data.mi_threshold: 0.003` (iter-6) — Kraskov kNN mutual-information
  pruner drops features below the noise floor before the encoder sees them

Loader resolution chain: **cache → GitHub OHLCV → GitHub macro open-data →
FMP REST API (`FMP_API_KEY`) → yfinance → synthetic GBM+GARCH**. Each
source logs `source=<label>:<symbol>` so provenance is always auditable.

Iteration history lives in `reports/iteration_log.md`. Cumulative net deltas
vs the original return-reward baseline (iter-0): pre-meta Sharpe @ 0bps
**0.881 → 1.004 (+14%)**, pre-meta Sharpe @ 0.5bps **0.571 → 0.679 (+19%)**,
meta-gate Sharpe @ 0.60 **→ 6.78**, **GRPO mean Sharpe 0.447 → 0.708 (+58%
in iter-7)**, Sharpe std 0.370 → **0.167 (−55%, tighter ensemble)**.

**Phase H (2026-04-24) — pre-deployment validation stack.** The apparent
"permutation p-value regression" (0.608 → 0.996 across iter-6/7) turned out
to be a broken test: Sharpe ratio is permutation-invariant, so the
element-wise shuffle test reports p ≈ 1 trivially via tie-comparisons.
Phase H replaces it with a centred block-bootstrap edge test (Politis &
Romano) that draws with replacement and tests H0: E[r] ≤ 0. On iter-7
data the new test reports **p = 0.0005** — the edge is real. Phase H
also adds a TRUE hold-out gate (`scripts/04b_holdout_eval.py`) on a
20%-tail window never seen by CPCV or PPO: **Sharpe 1.090, bootstrap
p = 0.001, DSR 0.969** on 635 trades. Kelly fractional sizing (off by
default) and live-feed quality gates (NaN/gap/staleness/exchange-hours)
ship in `src/live/paper_engine.py` and `src/live/feed.py`. See the
Phase H section in `reports/iteration_log.md` for the full comparison.

**Phase I (2026-04-26) — paper-trading simulation.**
`scripts/07_paper_simulation.py` drives the best CPCV policy through
`PaperEngine` over the same 20% hold-out, twice: byte-parity baseline
vs. quarter-Kelly (`cap=0.25, floor=0.05`). Headline: Sharpe is
**regime-dependent** — 0.64 in the trend regime (80% of bars), 2.15 in
the volatile regime (20% of bars). The 1.09 hold-out figure is a blend.
Quarter-Kelly pins to floor (mean fraction 0.053) because the per-trade
edge is too thin for a meaningful Kelly bet — the aggregate Sharpe
comes from frequency, not conviction. Drawdown profile: −4.29% on
unscaled notional over 6 months; −0.22% at quarter-Kelly. Reports
land in `reports/paper_simulation_report.md` and `paper_simulation.json`.

```bash
TRADING_PROFILE=aggressive python scripts/07_paper_simulation.py
```

Known runtime limits:

- 15m MGC bars are **not** reachable in this sandbox (yfinance blocked,
  github mirror 60m-only). `load_ohlcv` will fail loudly if a non-60m
  interval is requested on GC=F.
- FMP REST API domain is currently blocked in this sandbox (HTTP 403).
  `^VIX`, `^GSPC`, `^TNX` use GitHub open-data instead; `DX=F` falls
  through to synthetic until FMP becomes reachable. Set `FMP_API_KEY` and
  call `fetch_macro_series(..., force_refresh=True)` to pull live data
  in an unrestricted environment.
- In older runs (iter-6) macro symbols fell through to the synthetic
  GBM+GARCH path. `load_ohlcv` logs `source=synthetic:<symbol>` so you
  can tell. Iter-7 uses real GitHub open-data for all three macro symbols.
- Meta-gate compounded returns are a statistical artefact of high
  selectivity and should not be used as a live-PnL estimate — trust
  the per-trade Sharpe instead.

## Layout

```
configs/default.yaml            # hyperparams and CPCV/cost knobs
src/
  data/                         # loader, features, triple_barrier
  models/                       # xlstm_lite, policy, precompute
  env/                          # trading_env, embedding_env (precomputed obs)
  validation/                   # cpcv, deflated_sr, bootstrap, metrics
  training/                     # pretrain_encoder, train_ppo, evaluate, finetune
  live/                         # paper_engine, feed (streaming bars)
  ui/                           # server (FastAPI) + static/index.html cockpit
scripts/                        # 01..06 entry points (06 = cockpit)
tests/test_smoke.py             # end-to-end smoke test
tests/test_cockpit.py           # paper-engine parity + API smoke test
artefacts/                      # encoders, policies, manifest (generated)
data/                           # raw + processed parquets (generated)
reports/                        # markdown + png outputs (generated)
```
