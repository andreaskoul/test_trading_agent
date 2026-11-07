# Risk-field research: out-of-sample read (one read)

Read 2026-11-07T11:12:42+00:00. Origins 2020-01-02 .. 2025-12-31.

| Test | statistic | t | p one-sided | p Holm | pass |
|---|---|---:|---:|---:|---|
| R2 | h5 gain 0.00254 (t 2.24); h22 gain -0.00443 (t -0.61) | 2.24 | 0.0126 | 0.0252 | no |
| H-B1 | MSE gain 0.04835 on 0.1454 | 7.56 | 0.0000 | 0.0000 | **yes** |
| A3B | net -0.62%/yr, Sharpe -0.07 | 1.23 | 0.1100 | 0.1100 | no |

Consequences (best risk model MS, best beta B1):

* P1 hedge: squared-return gain 1.58e-05 (t 2.42), p Holm 0.015542064626774436; MOM weekly sd 1.950% -> 1.898%; REV weekly sd 1.664% -> 1.629%
* P2 inverse-vol weights: Sharpe -0.17 vs -0.09 (t -1.80), net -1.77 vs -1.18 %/yr, p Holm 0.9636889342606083
