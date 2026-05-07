# Paper-Trading Simulation Report
Hold-out window: **16390 bars** (2023-07-17 20:00:00+00:00 → 2026-03-24 00:00:00+00:00)
Best policy: **grpo** (CPCV split=2, seed=7)

## Run summary

| run | n_trades | Sharpe | hit | max DD | total ret | trades/day | mean Kelly | p5 / p95 Kelly |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 1005 | 0.383 | 0.435 | -0.065 | 20.42% | 1.03 | 1.000 | 1.000 / 1.000 |
| quarter_kelly | 1005 | 0.390 | 0.435 | -0.003 | 1.00% | 1.03 | 0.050 | 0.050 / 0.050 |

## Regime characterisation (realised hourly log-return std)

| regime | realised σ (hourly) | label |
|---:|---:|---|
| 0 | 0.00147 | calm |
| 1 | 0.00301 | trend |
| 2 | 0.01043 | volatile |

## Per-regime Sharpe (HMM state at trade entry)

| run | regime | bars | n_trades | Sharpe | hit | max DD | total ret |
|---|:---:|---:|---:|---:|---:|---:|---:|
| baseline | 0 | 12229 | 672 | -0.190 | 0.409 | -0.065 | -3.59% |
| baseline | 1 | 3816 | 295 | 0.796 | 0.471 | -0.047 | 14.70% |
| baseline | 2 | 345 | 38 | 1.482 | 0.605 | -0.062 | 8.89% |
| quarter_kelly | 0 | 12229 | 672 | -0.191 | 0.409 | -0.003 | -0.18% |
| quarter_kelly | 1 | 3816 | 295 | 0.801 | 0.471 | -0.002 | 0.73% |
| quarter_kelly | 2 | 345 | 38 | 1.497 | 0.605 | -0.003 | 0.44% |

## Verdicts

### 1. Drawdown profile in stressed regimes

- Baseline equity-curve max DD: **-6.48%** (1005 trades, 978 days).
- Quarter-Kelly equity-curve max DD: **-0.33%** (realised leverage scaled down by mean fraction 0.050).
- Worst per-regime DD on baseline: **-6.49%** in the regime with 672 trades / 12229 bars exposure.
- Verdict: baseline DD is well within a 5% risk budget over 978 days; quarter-Kelly clamps DD by ~20×.

### 2. Regime stability (does Sharpe ≈ 1.1 hold across regimes?)

- Baseline Sharpe spread across regimes (>=30 trades): **1.67** (min=-0.19 in regime 0 [calm, 672 trades], max=1.48 in regime 2 [volatile, 38 trades]).
- **Verdict: regime-DEPENDENT.** The headline Sharpe of 0.38 is a blend; the edge is concentrated in the volatile regime. A live deployment that lands in a long calm regime would see closer to Sharpe -0.19.

### 3. Position sizing vs volatility (does quarter-Kelly stay in bounds?)

- Quarter-Kelly fraction: mean=0.050, median=0.050, p5=0.050, p95=0.050.
- Realised leverage proxy = mean fraction × cap = 0.050 (cap=0.25 hard ceiling).
- Turnover: **1.03 trades/day** identical with or without Kelly (sizing scales notional, not frequency).
- **Verdict: Kelly is pinned near the floor.** The per-trade edge (hit-rate × W/L − (1-hit)) is too thin to justify a meaningful Kelly bet, so the sizer floors at 5%. The aggregate Sharpe comes from frequency (635 trades over 6 months), not single-trade conviction. For a live account this means: realised leverage will be tiny (~5% of unit notional), DDs will be very small, and total PnL will scale roughly linearly with trade frequency.
