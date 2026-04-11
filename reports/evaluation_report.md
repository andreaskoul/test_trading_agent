# Evaluation Report

- Runs evaluated: **18**
- Pooled trades: **19349**

## Sharpe distribution

- mean   : -0.103
- median : -0.076
- std    : 0.309
- p5     : -0.651
- p95    : +0.279
- min    : -0.714
- max    : +0.333

## Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)

- Observed Sharpe (pooled)   : 0.023
- Trials                     : 18
- E[max SR] under null       : 0.212
- PSR vs 0                   : 0.580
- **Deflated SR (P > null)** : **0.049**
- Skewness                   : +1.294
- Excess kurtosis            : +7.556
- Min Track Record Length    : 5131.602605521564

## Bootstrap 95% CI (block bootstrap)

- Point Sharpe : 0.023
- 2.5% / 97.5% : [-0.210, 0.241]  (2000 resamples)

## Monte Carlo permutation test

- One-sided p-value vs random shuffle: **0.003** (lower = more evidence of sequential edge)

## Transaction cost sensitivity

| Cost (bps) | Mean Sharpe |
|-----------:|-------------:|
| 0.0 | +0.673 |
| 1.0 | +0.285 |
| 2.0 | -0.103 |
| 5.0 | -1.268 |
| 10.0 | -3.208 |

## Seed ensemble (pooled trades per split)

| Split | Sharpe |
|------:|-------:|
| 0 | -0.469 |
| 1 | -0.057 |
| 2 | -0.122 |
| 3 | -0.015 |
| 4 | +0.252 |
| 5 | -0.215 |

## Meta-labeling gate (T1.1, Lopez de Prado)

Per-split HistGBM classifier trained on trades from the OTHER splits,
predicting P(profit) from entry embedding+direction+vol-quantile. Actions
with P < threshold are gated to HOLD.

| Threshold | Mean Sharpe | Pooled Sharpe | Trades | Total Return |
|----------:|------------:|--------------:|-------:|-------------:|
| 0.50 | +2.571 | +2.892 | 3506 | +222.231 |
| 0.55 | +3.387 | +3.877 | 1930 | +43.081 |
| 0.60 | +4.706 | +5.134 | 1013 | +10.623 |

## Red flags

- Mean Sharpe <= 0
- DSR p-value > 0.05 (deflated=0.049)
- Edge collapses at >=5 bps transaction cost

## Plots

- ![Sharpe histogram](sharpe_hist.png)
- ![Equity curves](equity_curves.png)
- ![Transaction cost curve](cost_curve.png)