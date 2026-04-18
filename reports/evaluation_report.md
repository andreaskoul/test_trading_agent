# Evaluation Report

- Runs evaluated: **36**
- Assets: **GC=F**
- Pooled trades: **75219**

## Sharpe distribution (all assets pooled)

- mean   : +0.544
- median : +0.541
- std    : 0.223
- p5     : +0.226
- p95    : +0.867
- min    : +0.080
- max    : +0.929

## Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)

- Observed Sharpe (pooled)   : 1.316
- Trials                     : 36
- E[max SR] under null       : 0.124
- PSR vs 0                   : 1.000
- **Deflated SR (P > null)** : **1.000**
- Skewness                   : +1.269
- Excess kurtosis            : +12.397
- Min Track Record Length    : 2.4311447292406

## Bootstrap 95% CI (block bootstrap)

- Point Sharpe : 1.316
- 2.5% / 97.5% : [1.205, 1.430]  (2000 resamples)

## Monte Carlo permutation test

- One-sided p-value vs random shuffle: **1.000** (lower = more evidence of sequential edge)

## Transaction cost sensitivity

| Cost (bps) | Mean Sharpe |
|-----------:|-------------:|
| 0.0 | +0.870 |
| 0.5 | +0.544 |
| 1.0 | +0.219 |
| 2.0 | -0.431 |
| 5.0 | -2.382 |

## Seed ensemble (pooled trades per split)

### GC=F

| Split | Sharpe |
|------:|-------:|
| 0 | +0.300 |
| 1 | +0.515 |
| 2 | +0.650 |
| 3 | +0.670 |
| 4 | +0.636 |
| 5 | +0.488 |

## Algorithm ensemble (T2.2)

Per-algorithm mean Sharpe across all CPCV splits, seeds, and assets.

| Algorithm | Mean Sharpe | Std | Runs |
|:----------|------------:|----:|-----:|
| grpo | +0.514 | 0.235 | 18 |
| ppo | +0.575 | 0.206 | 18 |

## Cross-asset meta-labeling gate (T1.1, Lopez de Prado)

HistGBM classifier trained on trades from ALL other splits across ALL
assets (cross-asset leave-one-out). Predicts P(profit) from entry
embedding+direction+vol-quantile. Actions with P < threshold are gated.

| Threshold | Mean Sharpe | Pooled Sharpe | Trades | Total Return |
|----------:|------------:|--------------:|-------:|-------------:|
| 0.50 | +3.986 | +3.839 | 24643 | +32243724295382.230 |
| 0.55 | +5.677 | +5.548 | 13433 | +3697420556.634 |
| 0.60 | +6.854 | +7.337 | 6857 | +407738.921 |

## Red flags

- Permutation p-value > 0.10 (p=1.000)
- Edge collapses at >=5 bps transaction cost

## Plots

- ![Sharpe histogram](sharpe_hist.png)
- ![Equity curves](equity_curves.png)
- ![Transaction cost curve](cost_curve.png)