# Evaluation Report

- Runs evaluated: **18**
- Pooled trades: **19454**

## Sharpe distribution

- mean   : -0.125
- median : -0.116
- std    : 0.276
- p5     : -0.600
- p95    : +0.314
- min    : -0.775
- max    : +0.389

## Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)

- Observed Sharpe (pooled)   : -0.053
- Trials                     : 18
- E[max SR] under null       : 0.211
- PSR vs 0                   : 0.321
- **Deflated SR (P > null)** : **0.010**
- Skewness                   : +1.186
- Excess kurtosis            : +6.193
- Min Track Record Length    : inf

## Bootstrap 95% CI (block bootstrap)

- Point Sharpe : -0.053
- 2.5% / 97.5% : [-0.295, 0.179]  (2000 resamples)

## Monte Carlo permutation test

- One-sided p-value vs random shuffle: **0.022** (lower = more evidence of sequential edge)

## Transaction cost sensitivity

| Cost (bps) | Mean Sharpe |
|-----------:|-------------:|
| 0.0 | +0.656 |
| 1.0 | +0.266 |
| 2.0 | -0.125 |
| 5.0 | -1.296 |
| 10.0 | -3.248 |

## Seed ensemble (pooled trades per split)

| Split | Sharpe |
|------:|-------:|
| 0 | -0.296 |
| 1 | -0.242 |
| 2 | -0.224 |
| 3 | -0.161 |
| 4 | +0.307 |
| 5 | -0.127 |

## Algorithm ensemble (T2.2)

Per-algorithm mean Sharpe across all CPCV splits and seeds.

| Algorithm | Mean Sharpe | Std | Runs |
|:----------|------------:|----:|-----:|
| a2c | -0.170 | 0.186 | 6 |
| ppo | -0.068 | 0.282 | 6 |
| recurrent_ppo | -0.136 | 0.331 | 6 |

## Meta-labeling gate (T1.1, Lopez de Prado)

Per-split HistGBM classifier trained on trades from the OTHER splits,
predicting P(profit) from entry embedding+direction+vol-quantile. Actions
with P < threshold are gated to HOLD.

| Threshold | Mean Sharpe | Pooled Sharpe | Trades | Total Return |
|----------:|------------:|--------------:|-------:|-------------:|
| 0.50 | +3.049 | +3.115 | 3547 | +429.851 |
| 0.55 | +4.050 | +4.223 | 2023 | +76.889 |
| 0.60 | +5.130 | +5.512 | 1083 | +16.520 |

## Red flags

- Mean Sharpe <= 0
- DSR p-value > 0.05 (deflated=0.010)
- Edge collapses at >=5 bps transaction cost

## Plots

- ![Sharpe histogram](sharpe_hist.png)
- ![Equity curves](equity_curves.png)
- ![Transaction cost curve](cost_curve.png)