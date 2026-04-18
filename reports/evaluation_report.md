# Evaluation Report

- Runs evaluated: **36**
- Assets: **GC=F**
- Pooled trades: **51734**

## Sharpe distribution (all assets pooled)

- mean   : +0.553
- median : +0.557
- std    : 0.218
- p5     : +0.167
- p95    : +0.895
- min    : +0.116
- max    : +0.930

## Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)

- Observed Sharpe (pooled)   : 1.335
- Trials                     : 36
- E[max SR] under null       : 0.150
- PSR vs 0                   : 1.000
- **Deflated SR (P > null)** : **1.000**
- Skewness                   : +0.930
- Excess kurtosis            : +5.692
- Min Track Record Length    : 2.414773127175043

## Bootstrap 95% CI (block bootstrap)

- Point Sharpe : 1.335
- 2.5% / 97.5% : [1.204, 1.469]  (2000 resamples)

## Monte Carlo permutation test

- One-sided p-value vs random shuffle: **0.973** (lower = more evidence of sequential edge)

## Transaction cost sensitivity

| Cost (bps) | Mean Sharpe |
|-----------:|-------------:|
| 0.0 | +0.881 |
| 0.5 | +0.553 |
| 1.0 | +0.225 |
| 2.0 | -0.432 |
| 5.0 | -2.403 |

## Seed ensemble (pooled trades per split)

### GC=F

| Split | Sharpe |
|------:|-------:|
| 0 | +0.383 |
| 1 | +0.492 |
| 2 | +0.495 |
| 3 | +0.597 |
| 4 | +0.753 |
| 5 | +0.606 |

## Algorithm ensemble (T2.2)

Per-algorithm mean Sharpe across all CPCV splits, seeds, and assets.

| Algorithm | Mean Sharpe | Std | Runs |
|:----------|------------:|----:|-----:|
| grpo | +0.537 | 0.224 | 18 |
| ppo | +0.569 | 0.211 | 18 |

## Cross-asset meta-labeling gate (T1.1, Lopez de Prado)

HistGBM classifier trained on trades from ALL other splits across ALL
assets (cross-asset leave-one-out). Predicts P(profit) from entry
embedding+direction+vol-quantile. Actions with P < threshold are gated.

| Threshold | Mean Sharpe | Pooled Sharpe | Trades | Total Return |
|----------:|------------:|--------------:|-------:|-------------:|
| 0.50 | +3.117 | +3.036 | 17746 | +57275727.984 |
| 0.55 | +4.536 | +4.471 | 9065 | +257643.663 |
| 0.60 | +5.836 | +5.922 | 3812 | +669.590 |

## Red flags

- Permutation p-value > 0.10 (p=0.973)
- Edge collapses at >=5 bps transaction cost

## Plots

- ![Sharpe histogram](sharpe_hist.png)
- ![Equity curves](equity_curves.png)
- ![Transaction cost curve](cost_curve.png)