# Evaluation Report

- Runs evaluated: **36**
- Assets: **GC=F**
- Pooled trades: **170220**

## Sharpe distribution (all assets pooled)

- mean   : +0.436
- median : +0.409
- std    : 0.095
- p5     : +0.314
- p95    : +0.586
- min    : +0.225
- max    : +0.716

## Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)

- Observed Sharpe (pooled)   : 0.923
- Trials                     : 36
- E[max SR] under null       : 0.083
- PSR vs 0                   : 1.000
- **Deflated SR (P > null)** : **1.000**
- Skewness                   : +0.939
- Excess kurtosis            : +3.388
- Min Track Record Length    : 4.008900243957339

## Bootstrap 95% CI (block bootstrap)

- Point Sharpe : 0.923
- 2.5% / 97.5% : [0.850, 0.994]  (2000 resamples)

## Monte Carlo permutation test

- One-sided p-value vs random shuffle: **0.967** (lower = more evidence of sequential edge)

## Transaction cost sensitivity

| Cost (bps) | Mean Sharpe |
|-----------:|-------------:|
| 0.0 | +0.737 |
| 0.5 | +0.436 |
| 1.0 | +0.135 |
| 2.0 | -0.468 |
| 5.0 | -2.277 |

## Seed ensemble (pooled trades per split)

### GC=F

| Split | Sharpe |
|------:|-------:|
| 0 | +0.456 |
| 1 | +0.515 |
| 2 | +0.496 |
| 3 | +0.362 |
| 4 | +0.355 |
| 5 | +0.416 |

## Algorithm ensemble (T2.2)

Per-algorithm mean Sharpe across all CPCV splits, seeds, and assets.

| Algorithm | Mean Sharpe | Std | Runs |
|:----------|------------:|----:|-----:|
| grpo | +0.443 | 0.090 | 18 |
| ppo | +0.429 | 0.098 | 18 |

## Cross-asset meta-labeling gate (T1.1, Lopez de Prado)

HistGBM classifier trained on trades from ALL other splits across ALL
assets (cross-asset leave-one-out). Predicts P(profit) from entry
embedding+direction+vol-quantile. Actions with P < threshold are gated.

| Threshold | Mean Sharpe | Pooled Sharpe | Trades | Total Return |
|----------:|------------:|--------------:|-------:|-------------:|
| 0.50 | +4.074 | +3.985 | 36479 | +2360577034782655381504.000 |
| 0.55 | +5.671 | +5.455 | 12784 | +66796037437.021 |
| 0.60 | +6.279 | +5.992 | 4984 | +110099.094 |

## Red flags

- Legacy permutation p > 0.50 (p=0.967, diagnostic only)
- Edge collapses at >=5 bps transaction cost

## Plots

- ![Sharpe histogram](sharpe_hist.png)
- ![Equity curves](equity_curves.png)
- ![Transaction cost curve](cost_curve.png)