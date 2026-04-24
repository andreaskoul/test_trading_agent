# Evaluation Report

- Runs evaluated: **36**
- Assets: **GC=F**
- Pooled trades: **69089**

## Sharpe distribution (all assets pooled)

- mean   : +0.679
- median : +0.679
- std    : 0.167
- p5     : +0.396
- p95    : +0.896
- min    : +0.237
- max    : +0.990

## Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)

- Observed Sharpe (pooled)   : 1.583
- Trials                     : 36
- E[max SR] under null       : 0.130
- PSR vs 0                   : 1.000
- **Deflated SR (P > null)** : **1.000**
- Skewness                   : +1.053
- Excess kurtosis            : +8.907
- Min Track Record Length    : 1.9903843175664135

## Bootstrap 95% CI (block bootstrap)

- Point Sharpe : 1.583
- 2.5% / 97.5% : [1.465, 1.700]  (2000 resamples)

## Monte Carlo permutation test

- One-sided p-value vs random shuffle: **0.996** (lower = more evidence of sequential edge)

## Transaction cost sensitivity

| Cost (bps) | Mean Sharpe |
|-----------:|-------------:|
| 0.0 | +1.004 |
| 0.5 | +0.679 |
| 1.0 | +0.353 |
| 2.0 | -0.298 |
| 5.0 | -2.253 |

## Seed ensemble (pooled trades per split)

### GC=F

| Split | Sharpe |
|------:|-------:|
| 0 | +0.539 |
| 1 | +0.602 |
| 2 | +0.753 |
| 3 | +0.732 |
| 4 | +0.785 |
| 5 | +0.657 |

## Algorithm ensemble (T2.2)

Per-algorithm mean Sharpe across all CPCV splits, seeds, and assets.

| Algorithm | Mean Sharpe | Std | Runs |
|:----------|------------:|----:|-----:|
| grpo | +0.708 | 0.128 | 18 |
| ppo | +0.650 | 0.194 | 18 |

## Cross-asset meta-labeling gate (T1.1, Lopez de Prado)

HistGBM classifier trained on trades from ALL other splits across ALL
assets (cross-asset leave-one-out). Predicts P(profit) from entry
embedding+direction+vol-quantile. Actions with P < threshold are gated.

| Threshold | Mean Sharpe | Pooled Sharpe | Trades | Total Return |
|----------:|------------:|--------------:|-------:|-------------:|
| 0.50 | +3.831 | +3.634 | 27179 | +249366441899836.656 |
| 0.55 | +5.443 | +5.265 | 16129 | +221989583644.016 |
| 0.60 | +6.784 | +7.292 | 9002 | +20381837.460 |

## Red flags

- Permutation p-value > 0.10 (p=0.996)
- Edge collapses at >=5 bps transaction cost

## Plots

- ![Sharpe histogram](sharpe_hist.png)
- ![Equity curves](equity_curves.png)
- ![Transaction cost curve](cost_curve.png)