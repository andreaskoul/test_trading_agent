# Verifying F2, the off-exchange short-volume ratio (Amendment 15)

Read 2026-11-08T02:51:47+00:00.

**1. Replication, S&P 400 current list 2016-2025 (one read):** -2.7 bp per sd, DK t -1.61, one-sided p 0.0537; book net 2.35% a year at 2 bp (Sharpe 0.47), 1.53% at 5 bp; 360 names. **fail**

**2. Controls, S&P 500 OOS 2020-2025:**

| Regressor | bp per sd | DK t |
|---|---:|---:|
| F2 | -4.0 | -2.38 |
| reversal_5d | -6.0 | -0.89 |
| log_vol_20d | 2.5 | 0.43 |
| log_dollar_volume_20d | -3.7 | -1.17 |

F2 robust to the controls (t <= -1.65): **yes**

**3. Stability (descriptive), S&P 500:**

| Period | bp per sd | t |
|---|---:|---:|
| 2012 | -3.5 | -1.28 |
| 2013 | -1.5 | -0.59 |
| 2014 | -4.8 | -1.58 |
| 2015 | -3.9 | -1.50 |
| 2016 | 0.8 | 0.18 |
| 2017 | -8.3 | -3.05 |
| 2018 | 2.7 | 0.76 |
| 2019 | -1.9 | -0.55 |
| 2020 | 0.4 | 0.07 |
| 2021 | 2.2 | 0.72 |
| 2022 | -5.0 | -1.24 |
| 2023 | -4.7 | -1.05 |
| 2024 | -4.6 | -1.69 |
| 2025 | -8.3 | -1.82 |
| before_2018_08 | -2.9 | -2.22 |
| after_2018_08 | -2.9 | -1.82 |
