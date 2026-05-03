# Retraining the agent on a longer historical corpus

Phase S (Sep 2026 onwards) split data acquisition from training so they
can be triggered independently. This doc walks through the full cycle.

## TL;DR

1. **Fetch** new data via Actions (Stooq + yfinance, 2016 → now).
2. **Pull** it locally from the `data` branch.
3. **Retrain** on your own machine (≈ 7 hours; GPU strongly recommended).
4. **Push** the new artefacts to a feature branch.
5. **Backtest** that branch via the Multi-window backtest Action.

## Step-by-step

### 1. Fetch a longer history

Trigger **Actions → Fetch historical data → Run workflow** with:

| Input | Recommended |
|---|---|
| `start_date` | `2016-01-01` |
| `end_date` | (empty = today) |
| `asset` | `GC=F` |
| `interval` | `60m` |
| `macros` | `VIX,GSPC,TNX` |
| `source` | `auto` (Stooq for 60m, yfinance for macros) |
| `commit_to_data_branch` | `true` |

Expect the run to finish in ~5 min. The job log prints the actual date
range each source returned — check it. If Stooq's hourly history turns
out to be shorter than advertised, the run still succeeds and writes
whatever it got.

### 2. Pull the data locally

```bash
git fetch origin data
git checkout data -- data/raw/
```

This drops `gold_60m_historical.parquet` and the refreshed `macro_*.parquet`
files into your working tree without changing your branch.

### 3. Update the config

Edit `configs/default.yaml` (or `configs/aggressive.yaml`) so the
training pipeline reads the new asset path:

```yaml
data:
  assets:
    - symbol: "GC=F"
      raw_path: "data/raw/gc_60m_historical.parquet"   # was gc_60m.parquet
      features_path: "data/processed/features_gc_60m.parquet"
      labels_path: "data/processed/labels_gc_60m.parquet"
```

### 4. Run the training pipeline

This is heavy. **GPU strongly recommended** — on a 2-CPU laptop expect
~12 hours; on a single mid-range GPU ~2 hours.

```bash
# Build features + labels from the new raw OHLCV
python scripts/01_build_data.py

# Pretrain the xLSTM-lite encoder (multitask: direction + vol + meta)
python scripts/02_pretrain_encoder.py

# Train the 36 PPO/GRPO runs (6 CPCV splits × 3 seeds × 2 algos)
python scripts/03_train_ppo.py

# Compute per-run + pooled metrics
python scripts/04_evaluate.py

# Hold-out gate (PASS/FAIL deployment decision)
python scripts/04b_holdout_eval.py
```

If `04b` returns exit 0 (PASS), the new artefacts in `artefacts/` are
deployment-ready.

### 5. Push the new artefacts

```bash
git checkout -b retrain/<descriptive-name>
git add artefacts/ reports/ configs/
git commit -m "retrain on 2016-2026 corpus"
git push -u origin HEAD
```

### 6. Backtest the new model

Trigger **Actions → Multi-window backtest → Run workflow**:

- `branch`: the feature branch you just pushed
- `seed`: 42 (or whatever)
- `n_windows`: 20
- `notional`: 100000

The report lands as a workflow artefact and on the `backtest_history`
branch. After several runs accumulate, compare them with:

```bash
git fetch origin backtest_history
git checkout backtest_history -- reports/backtest/
python scripts/compare_backtests.py reports/backtest/*.json --out compare.md
```

## Why isn't training itself a workflow?

Free Actions runners are 2-CPU and have a 6h per-job limit. The full
36-run training pipeline takes ~7 hours on a 2-CPU box, which is too
tight. A future Phase T could split the work across matrix jobs (e.g.
4 parallel jobs × 9 PPO runs each) but that adds operational complexity
and isn't worth it until the training corpus is stable. For now, run
locally or on a paid runner.

## Caveats

- **Stooq's 60m history is unverified**: advertised back to ~2007, but
  the actual response can be shorter or partial. Look at the
  `Fetch historical data` job log to see the date range you actually got.
- **The on-disk pre-training segment** (`data/raw/gold.parquet[2023-01-02
  : 2023-07-17]`) is preserved as-is; the new historical parquet has a
  different filename.
- **Macros are overwritten** on each fetch — they're additive (longer
  series strictly dominate), so this is safe. Cache via `force_refresh=False`
  inside `fetch_macro_series` already prevents duplicate yfinance calls
  during a normal `01_build_data.py` run.
