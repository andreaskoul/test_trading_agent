# Risk-field research: development results

Run 2026-11-07T11:10:17+00:00. Development periods only. Gain = benchmark loss minus candidate loss (positive = better).

| Test | h=5 gain | h=5 t | h=22 gain | h=22 t | names/day | finalist |
|---|---:|---:|---:|---:|---:|---|
| R1 | -0.00017 | -0.53 | -0.00022 | -0.96 | 375 | no |
| R2 | 0.00224 | 2.39 | 0.00142 | 1.70 | 409 | yes |
| R3 | -0.00058 | -0.63 | -0.00083 | -0.69 | 414 | no |
| R4 | -0.00003 | -0.73 | -0.00004 | -1.52 | 414 | no |
| R5 | -0.00305 | -1.33 | -0.00063 | -0.27 | 414 | no |
| N1 | -0.00022 | -1.00 | 0.00029 | 0.58 | 28 | no |

| Beta test | MSE gain | t | weeks | benchmark MSE | finalist |
|---|---:|---:|---:|---:|---|
| H-B1 | 0.03591 | 7.11 | 148 | 0.1263 | yes |
| H-B2 | 0.00043 | 0.76 | 148 | 0.0904 | no |

| Alpha test | slope | DK t | net bp/week | net %/yr | Sharpe | names | finalist |
|---|---:|---:|---:|---:|---:|---:|---|
| A1 | -0.00022 | -0.93 | -6.3 | -3.41 | -0.54 | 308 | no |
| A2 | 0.00046 | 2.46 | -3.1 | -1.68 | -0.36 | 308 | no |
| A3 | 0.00054 | 3.33 | -1.8 | -0.97 | -0.26 | 374 | no |

Reported (not tested):

* MS_vs_M0_h5: gain 0.00246, t 2.31
* M0_vs_EWMA_h5: gain 0.13819, t 7.45
* N1placebo_vs_NB_h5: gain 0.00031, t 0.88
* MS_vs_M0_h22: gain 0.00059, t 1.36
* M0_vs_EWMA_h22: gain 0.11074, t 4.56
* N1placebo_vs_NB_h22: gain 0.00049, t 1.19

**Finalists:** R2, H-B1
