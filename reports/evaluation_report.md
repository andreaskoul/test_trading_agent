# Evaluation Report

- Runs evaluated: **36**
- Assets: **GC=F**
- Pooled trades: **22967**

## Sharpe distribution (all assets pooled)

- mean   : +0.567
- median : +0.543
- std    : 0.370
- p5     : -0.021
- p95    : +1.122
- min    : -0.263
- max    : +1.311

## Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)

- Observed Sharpe (pooled)   : 1.483
- Trials                     : 36
- E[max SR] under null       : 0.225
- PSR vs 0                   : 1.000
- **Deflated SR (P > null)** : **1.000**
- Skewness                   : +0.656
- Excess kurtosis            : +0.043
- Min Track Record Length    : 2.155224761264245

## Bootstrap 95% CI (block bootstrap)

- Point Sharpe : 1.483
- 2.5% / 97.5% : [1.269, 1.699]  (2000 resamples)

## Monte Carlo permutation test

- One-sided p-value vs random shuffle: **0.608** (lower = more evidence of sequential edge)

## Transaction cost sensitivity

| Cost (bps) | Mean Sharpe |
|-----------:|-------------:|
| 0.0 | +0.988 |
| 0.5 | +0.567 |
| 1.0 | +0.146 |
| 2.0 | -0.695 |
| 5.0 | -3.219 |

## Seed ensemble (pooled trades per split)

### GC=F

| Split | Sharpe |
|------:|-------:|
| 0 | +0.164 |
| 1 | +0.516 |
| 2 | +0.698 |
| 3 | +0.721 |
| 4 | +0.866 |
| 5 | +0.496 |

## Algorithm ensemble (T2.2)

Per-algorithm mean Sharpe across all CPCV splits, seeds, and assets.

| Algorithm | Mean Sharpe | Std | Runs |
|:----------|------------:|----:|-----:|
| grpo | +0.447 | 0.247 | 18 |
| ppo | +0.687 | 0.429 | 18 |

## Cross-asset meta-labeling gate (T1.1, Lopez de Prado)

HistGBM classifier trained on trades from ALL other splits across ALL
assets (cross-asset leave-one-out). Predicts P(profit) from entry
embedding+direction+vol-quantile. Actions with P < threshold are gated.

| Threshold | Mean Sharpe | Pooled Sharpe | Trades | Total Return |
|----------:|------------:|--------------:|-------:|-------------:|
| 0.50 | +3.118 | +3.112 | 9651 | +1573.068 |
| 0.55 | +3.934 | +4.001 | 6837 | +700.915 |
| 0.60 | +4.791 | +4.994 | 4656 | +212.723 |

## Red flags

- Permutation p-value > 0.10 (p=0.608)
- Edge collapses at >=5 bps transaction cost

## Plots

- ![Sharpe histogram](sharpe_hist.png)
- ![Equity curves](equity_curves.png)
- ![Transaction cost curve](cost_curve.png)