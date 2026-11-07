# Risk-field research: post-hoc breakdowns (descriptive, after the OOS read)

Beta forecasts, OOS weekly decisions 2020-2025, same names and weeks. The target is the next 21 sessions'
realised beta from 30-minute returns.

| Forecast | MSE | vs fund |
|---|---:|---:|
| B0 (fund) | 0.1459 | +0.0% |
| daily OLS, raw | 0.1224 | -16.1% |
| HF 63, raw | 0.1163 | -20.3% |
| calibrated daily OLS only | 0.1234 | -15.4% |
| calibrated HF 63 only | 0.1138 | -22.0% |
| B1 (HF 21 + HF 63 + daily OLS) | 0.0983 | -32.6% |

B1 against the fund's beta, by year (MSE):

| Year | fund | B1 | change |
|---|---:|---:|---:|
| 2020 | 0.1446 | 0.1320 | -8.7% |
| 2021 | 0.1533 | 0.0917 | -40.2% |
| 2022 | 0.0659 | 0.0390 | -40.9% |
| 2023 | 0.1403 | 0.0862 | -38.5% |
| 2024 | 0.1837 | 0.1307 | -28.9% |
| 2025 | 0.1933 | 0.1125 | -41.8% |

B1 coefficients on all decisions with targets ended by 2025-12-31: intercept 0.003, HF 21 0.332, HF 63 0.269, daily OLS 0.389.
B1 minus fund beta, OOS: mean -0.024, sd 0.213, 5th/95th percentiles -0.315 / +0.334.

## Round 5, I1 by year (descriptive, after the one read)

Slope in bp per sd of the text neighbours' earnings shocks, 10:00 → close; the top-minus-bottom decile spread.

| Year | bp/sd | t | spread bp | sessions |
|---|---:|---:|---:|---:|
| 2016 | −6.82 | −1.18 | −26.3 | 18 |
| 2017 | 0.82 | 0.44 | 4.3 | 101 |
| 2018 | 3.70 | 2.05 | 12.6 | 104 |
| 2019 | 3.49 | 1.34 | 12.5 | 105 |
| 2020 | 5.61 | 1.96 | 17.1 | 117 |
| 2021 | 1.81 | 0.99 | −5.1 | 92 |
| 2022 | 4.63 | 1.60 | 16.9 | 93 |
| 2023 | −2.49 | −1.02 | 2.8 | 103 |
| 2024 | 4.12 | 2.30 | 9.6 | 99 |
| 2025 | 2.56 | 1.17 | 4.9 | 105 |

The slope is positive in 5 of the 6 OOS years. 2016 has only 18 sessions, because bars and kernels start in February.
