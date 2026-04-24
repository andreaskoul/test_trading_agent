# Evaluation Report

- Runs evaluated: **36**
- Assets: **GC=F**
- Pooled trades: **52132**

## Sharpe distribution (all assets pooled)

- mean   : +0.533
- median : +0.522
- std    : 0.212
- p5     : +0.204
- p95    : +0.855
- min    : +0.087
- max    : +0.910

## Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)

- Observed Sharpe (pooled)   : 1.276
- Trials                     : 36
- E[max SR] under null       : 0.149
- PSR vs 0                   : 1.000
- **Deflated SR (P > null)** : **1.000**
- Skewness                   : +0.638
- Excess kurtosis            : +0.187
- Min Track Record Length    : 2.576199082538082

## Bootstrap 95% CI (block bootstrap)

- Point Sharpe : 1.276
- 2.5% / 97.5% : [1.128, 1.398]  (2000 resamples)

## Monte Carlo permutation test

- One-sided p-value vs random shuffle: **0.796** (lower = more evidence of sequential edge)

## Transaction cost sensitivity

| Cost (bps) | Mean Sharpe |
|-----------:|-------------:|
| 0.0 | +0.889 |
| 0.5 | +0.533 |
| 1.0 | +0.177 |
| 2.0 | -0.536 |
| 5.0 | -2.673 |

## Seed ensemble (pooled trades per split)

### GC=F

| Split | Sharpe |
|------:|-------:|
| 0 | +0.362 |
| 1 | +0.396 |
| 2 | +0.505 |
| 3 | +0.593 |
| 4 | +0.707 |
| 5 | +0.631 |

## Algorithm ensemble (T2.2)

Per-algorithm mean Sharpe across all CPCV splits, seeds, and assets.

| Algorithm | Mean Sharpe | Std | Runs |
|:----------|------------:|----:|-----:|
| grpo | +0.460 | 0.139 | 18 |
| ppo | +0.605 | 0.245 | 18 |

## Cross-asset meta-labeling gate (T1.1, Lopez de Prado)

HistGBM classifier trained on trades from ALL other splits across ALL
assets (cross-asset leave-one-out). Predicts P(profit) from entry
embedding+direction+vol-quantile. Actions with P < threshold are gated.

| Threshold | Mean Sharpe | Pooled Sharpe | Trades | Total Return |
|----------:|------------:|--------------:|-------:|-------------:|
| 0.50 | +3.218 | +3.073 | 17518 | +8675606.795 |
| 0.55 | +4.591 | +4.469 | 8757 | +62154.912 |
| 0.60 | +5.815 | +5.678 | 4118 | +464.041 |

## Red flags

- Legacy permutation p > 0.50 (p=0.796, diagnostic only)
- Edge collapses at >=5 bps transaction cost

## Plots

- ![Sharpe histogram](sharpe_hist.png)
- ![Equity curves](equity_curves.png)
- ![Transaction cost curve](cost_curve.png)