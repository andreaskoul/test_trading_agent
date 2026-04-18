# Evaluation Report

- Runs evaluated: **54**
- Assets: **GC=F**
- Pooled trades: **112687**

## Sharpe distribution (all assets pooled)

- mean   : +0.576
- median : +0.615
- std    : 0.194
- p5     : +0.242
- p95    : +0.849
- min    : +0.120
- max    : +0.856

## Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)

- Observed Sharpe (pooled)   : 1.337
- Trials                     : 54
- E[max SR] under null       : 0.109
- PSR vs 0                   : 1.000
- **Deflated SR (P > null)** : **1.000**
- Skewness                   : +1.149
- Excess kurtosis            : +10.025
- Min Track Record Length    : 2.3938607550407007

## Bootstrap 95% CI (block bootstrap)

- Point Sharpe : 1.337
- 2.5% / 97.5% : [1.244, 1.427]  (2000 resamples)

## Monte Carlo permutation test

- One-sided p-value vs random shuffle: **0.712** (lower = more evidence of sequential edge)

## Transaction cost sensitivity

| Cost (bps) | Mean Sharpe |
|-----------:|-------------:|
| 0.0 | +0.902 |
| 0.5 | +0.576 |
| 1.0 | +0.250 |
| 2.0 | -0.403 |
| 5.0 | -2.361 |

## Seed ensemble (pooled trades per split)

### GC=F

| Split | Sharpe |
|------:|-------:|
| 0 | +0.433 |
| 1 | +0.462 |
| 2 | +0.633 |
| 3 | +0.677 |
| 4 | +0.633 |
| 5 | +0.602 |

## Algorithm ensemble (T2.2)

Per-algorithm mean Sharpe across all CPCV splits, seeds, and assets.

| Algorithm | Mean Sharpe | Std | Runs |
|:----------|------------:|----:|-----:|
| grpo | +0.556 | 0.201 | 18 |
| ppo | +0.648 | 0.146 | 18 |
| recurrent_ppo | +0.525 | 0.208 | 18 |

## Cross-asset meta-labeling gate (T1.1, Lopez de Prado)

HistGBM classifier trained on trades from ALL other splits across ALL
assets (cross-asset leave-one-out). Predicts P(profit) from entry
embedding+direction+vol-quantile. Actions with P < threshold are gated.

| Threshold | Mean Sharpe | Pooled Sharpe | Trades | Total Return |
|----------:|------------:|--------------:|-------:|-------------:|
| 0.50 | +4.296 | +4.169 | 37155 | +25877123586288196255744.000 |
| 0.55 | +5.878 | +5.987 | 20369 | +3648866941109582.000 |
| 0.60 | +6.872 | +7.158 | 10291 | +602558839.009 |

## Red flags

- Permutation p-value > 0.10 (p=0.712)
- Edge collapses at >=5 bps transaction cost

## Plots

- ![Sharpe histogram](sharpe_hist.png)
- ![Equity curves](equity_curves.png)
- ![Transaction cost curve](cost_curve.png)