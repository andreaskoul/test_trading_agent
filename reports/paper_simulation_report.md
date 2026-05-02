# Paper-Trading Simulation Report
Hold-out window: **3278 bars** (2025-09-09 09:00:00+00:00 → 2026-03-24 00:00:00+00:00)
Best policy: **ppo** (CPCV split=5, seed=29)

## Run summary

| run | n_trades | Sharpe | hit | max DD | total ret | trades/day | mean Kelly | p5 / p95 Kelly |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 635 | 1.090 | 0.487 | -0.043 | 57.37% | 3.27 | 1.000 | 1.000 / 1.000 |
| quarter_kelly | 635 | 1.081 | 0.487 | -0.002 | 2.45% | 3.27 | 0.053 | 0.050 / 0.067 |

## Regime characterisation (realised hourly log-return std)

| regime | realised σ (hourly) | label |
|---:|---:|---|
| 2 | 0.00000 | calm |
| 0 | 0.00229 | trend |
| 1 | 0.00691 | volatile |

## Per-regime Sharpe (HMM state at trade entry)

| run | regime | bars | n_trades | Sharpe | hit | max DD | total ret |
|---|:---:|---:|---:|---:|---:|---:|---:|
| baseline | 0 | 2615 | 508 | 0.636 | 0.461 | -0.038 | 15.83% |
| baseline | 1 | 662 | 127 | 2.153 | 0.591 | -0.036 | 35.86% |
| baseline | 2 | 1 | 0 | 0.000 | 0.000 | 0.000 | 0.00% |
| quarter_kelly | 0 | 2615 | 508 | 0.659 | 0.461 | -0.002 | 0.85% |
| quarter_kelly | 1 | 662 | 127 | 2.097 | 0.591 | -0.002 | 1.58% |
| quarter_kelly | 2 | 1 | 0 | 0.000 | 0.000 | 0.000 | 0.00% |

## Verdicts

### 1. Drawdown profile in stressed regimes

- Baseline equity-curve max DD: **-4.29%** (635 trades, 194 days).
- Quarter-Kelly equity-curve max DD: **-0.22%** (realised leverage scaled down by mean fraction 0.053).
- Worst per-regime DD on baseline: **-3.76%** in the regime with 508 trades / 2615 bars exposure.
- Verdict: baseline DD is well within a 5% risk budget over 194 days; quarter-Kelly clamps DD by ~20×.

### 2. Regime stability (does Sharpe ≈ 1.1 hold across regimes?)

- Baseline Sharpe spread across regimes (>=30 trades): **1.52** (min=0.64 in regime 0 [trend, 508 trades], max=2.15 in regime 1 [volatile, 127 trades]).
- **Verdict: regime-DEPENDENT.** The headline Sharpe of 1.09 is a blend; the edge is concentrated in the volatile regime. A live deployment that lands in a long trend regime would see closer to Sharpe 0.64.

### 3. Position sizing vs volatility (does quarter-Kelly stay in bounds?)

- Quarter-Kelly fraction: mean=0.053, median=0.050, p5=0.050, p95=0.067.
- Realised leverage proxy = mean fraction × cap = 0.053 (cap=0.25 hard ceiling).
- Turnover: **3.27 trades/day** identical with or without Kelly (sizing scales notional, not frequency).
- **Verdict: Kelly is pinned near the floor.** The per-trade edge (hit-rate × W/L − (1-hit)) is too thin to justify a meaningful Kelly bet, so the sizer floors at 5%. The aggregate Sharpe comes from frequency (635 trades over 6 months), not single-trade conviction. For a live account this means: realised leverage will be tiny (~5% of unit notional), DDs will be very small, and total PnL will scale roughly linearly with trade frequency.
