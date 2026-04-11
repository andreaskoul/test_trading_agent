# Evaluation Report

- Runs evaluated: **18**
- Pooled trades: **20054**

## Sharpe distribution

- mean   : -0.134
- median : -0.117
- std    : 0.244
- p5     : -0.515
- p95    : +0.166
- min    : -0.515
- max    : +0.434

## Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)

- Observed Sharpe (pooled)   : -0.120
- Trials                     : 18
- E[max SR] under null       : 0.208
- PSR vs 0                   : 0.144
- **Deflated SR (P > null)** : **0.002**
- Skewness                   : +1.028
- Excess kurtosis            : +4.028
- Min Track Record Length    : inf

## Bootstrap 95% CI (block bootstrap)

- Point Sharpe : -0.120
- 2.5% / 97.5% : [-0.356, 0.097]  (2000 resamples)

## Monte Carlo permutation test

- One-sided p-value vs random shuffle: **0.001** (lower = more evidence of sequential edge)

## Transaction cost sensitivity

| Cost (bps) | Mean Sharpe |
|-----------:|-------------:|
| 0.0 | +0.647 |
| 1.0 | +0.256 |
| 2.0 | -0.134 |
| 5.0 | -1.305 |
| 10.0 | -3.257 |

## Seed ensemble (pooled trades per split)

| Split | Sharpe |
|------:|-------:|
| 0 | -0.218 |
| 1 | -0.301 |
| 2 | -0.162 |
| 3 | -0.119 |
| 4 | +0.190 |
| 5 | -0.177 |

## Red flags

- Mean Sharpe <= 0
- DSR p-value > 0.05 (deflated=0.002)
- Edge collapses at >=5 bps transaction cost

## Plots

- ![Sharpe histogram](sharpe_hist.png)
- ![Equity curves](equity_curves.png)
- ![Transaction cost curve](cost_curve.png)