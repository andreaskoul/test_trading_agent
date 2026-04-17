# Evaluation Report

- Runs evaluated: **36**
- Assets: **GC=F**
- Pooled trades: **73499**

## Sharpe distribution (all assets pooled)

- mean   : +0.571
- median : +0.636
- std    : 0.239
- p5     : +0.129
- p95    : +0.849
- min    : +0.016
- max    : +0.939

## Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)

- Observed Sharpe (pooled)   : 1.408
- Trials                     : 36
- E[max SR] under null       : 0.126
- PSR vs 0                   : 1.000
- **Deflated SR (P > null)** : **1.000**
- Skewness                   : +1.098
- Excess kurtosis            : +9.406
- Min Track Record Length    : 2.257596586335547

## Bootstrap 95% CI (block bootstrap)

- Point Sharpe : 1.408
- 2.5% / 97.5% : [1.288, 1.527]  (2000 resamples)

## Monte Carlo permutation test

- One-sided p-value vs random shuffle: **0.401** (lower = more evidence of sequential edge)

## Transaction cost sensitivity

| Cost (bps) | Mean Sharpe |
|-----------:|-------------:|
| 0.0 | +0.900 |
| 0.5 | +0.571 |
| 1.0 | +0.242 |
| 2.0 | -0.416 |
| 5.0 | -2.392 |

## Seed ensemble (pooled trades per split)

### GC=F

| Split | Sharpe |
|------:|-------:|
| 0 | +0.294 |
| 1 | +0.577 |
| 2 | +0.627 |
| 3 | +0.559 |
| 4 | +0.788 |
| 5 | +0.587 |

## Algorithm ensemble (T2.2)

Per-algorithm mean Sharpe across all CPCV splits, seeds, and assets.

| Algorithm | Mean Sharpe | Std | Runs |
|:----------|------------:|----:|-----:|
| grpo | +0.557 | 0.268 | 18 |
| ppo | +0.585 | 0.206 | 18 |

## Cross-asset meta-labeling gate (T1.1, Lopez de Prado)

HistGBM classifier trained on trades from ALL other splits across ALL
assets (cross-asset leave-one-out). Predicts P(profit) from entry
embedding+direction+vol-quantile. Actions with P < threshold are gated.

| Threshold | Mean Sharpe | Pooled Sharpe | Trades | Total Return |
|----------:|------------:|--------------:|-------:|-------------:|
| 0.50 | +3.644 | +3.508 | 25143 | +17985833528753.801 |
| 0.55 | +5.243 | +5.264 | 13271 | +3041153705.606 |
| 0.60 | +6.933 | +7.266 | 6331 | +207628.914 |

## Red flags

- Permutation p-value > 0.10 (p=0.401)
- Edge collapses at >=5 bps transaction cost

## Plots

- ![Sharpe histogram](sharpe_hist.png)
- ![Equity curves](equity_curves.png)
- ![Transaction cost curve](cost_curve.png)