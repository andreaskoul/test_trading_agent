# Statistically Robust DL+RL Gold Trading Agent

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
```

`--fast` is the default session budget (18 runs, 15 000 steps each). Drop it
for the full config (15 splits × 5 seeds × 60 000 steps).

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

## Layout

```
configs/default.yaml            # hyperparams and CPCV/cost knobs
src/
  data/                         # loader, features, triple_barrier
  models/                       # xlstm_lite, policy, precompute
  env/                          # trading_env, embedding_env (precomputed obs)
  validation/                   # cpcv, deflated_sr, bootstrap, metrics
  training/                     # pretrain_encoder, train_ppo, evaluate, finetune
scripts/                        # 01..05 entry points
tests/test_smoke.py             # end-to-end smoke test
artefacts/                      # encoders, policies, manifest (generated)
data/                           # raw + processed parquets (generated)
reports/                        # markdown + png outputs (generated)
```
