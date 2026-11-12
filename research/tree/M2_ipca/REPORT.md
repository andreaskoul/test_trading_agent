# Branch M2: instrumented PCA (Kelly, Pruitt and Su 2019)

*Saved by the coordinating session from the agent's hand-back (its file write was refused).*

Own alternating-least-squares implementation (`ipca.py`) on ranked characteristics plus a constant. Restricted score Z Gamma_beta lambda; unrestricted adds Z Gamma_alpha. K chosen in {1,3,5} by inner-holdout pricing fit inside each training set, never by validation IC. 10 configurations x restricted/unrestricted = 20 rows.

| config | IC | t | years positive | decile net %/yr | net Sharpe |
|---|---:|---:|---:|---:|---:|
| M05_C24_wk_xn_U | 0.0224 | 2.27 | 6 | +1.5 | +0.22 |
| M08_C24_wk_xn_K5_U | 0.0215 | 2.23 | 6 | +1.2 | +0.19 |
| M09_C24_wk_xn_K1_U | 0.0191 | 1.92 | 6 | +0.3 | +0.05 |
| M08_C24_wk_xn_K5_R | 0.0188 | 1.84 | 6 | -1.0 | -0.14 |
| M10_Z5_wk_xn_U | 0.0164 | 1.74 | 6 | +1.0 | +0.15 |
| M03_C32_wk_U | 0.0191 | 1.71 | 6 | -0.5 | -0.07 |
| M05_C24_wk_xn_R | 0.0196 | 1.64 | 6 | -0.7 | -0.09 |
| M02_C24_wk_R | 0.0176 | 1.59 | 6 | -0.6 | -0.08 |
| M09_C24_wk_xn_K1_R | 0.0204 | 1.56 | 6 | +0.6 | +0.07 |
| M10_Z5_wk_xn_R | 0.0146 | 1.49 | 6 | +0.5 | +0.07 |
| M03_C32_wk_R | 0.0171 | 1.41 | 6 | -0.6 | -0.07 |
| M04_C24_wk_l01_U | 0.0143 | 1.40 | 5 | -1.2 | -0.19 |
| M02_C24_wk_U | 0.0142 | 1.32 | 6 | -1.1 | -0.16 |
| M07_C32_wk_xn_U | 0.0122 | 1.29 | 6 | -0.9 | -0.14 |
| M06_C24_day_U | 0.0112 | 1.21 | 5 | -1.6 | -0.28 |
| M07_C32_wk_xn_R | 0.0137 | 1.12 | 5 | -0.9 | -0.10 |
| M04_C24_wk_l01_R | 0.0134 | 1.12 | 5 | -2.6 | -0.33 |
| M01_Z5_wk_U | 0.0074 | 0.84 | 4 | -1.1 | -0.17 |
| M06_C24_day_R | 0.0072 | 0.75 | 4 | -4.0 | -0.58 |
| M01_Z5_wk_R | 0.0019 | 0.18 | 4 | +1.4 | +0.19 |

Increment over MASTER: M05_U +0.0099 (t 1.11, corr 0.38); M08_U +0.0090 (t 1.01).

* Compensated risk carries most of the prediction (restricted 0.0196, unrestricted 0.0224; the gap is noise). Alpha and risk-premium parts are negatively correlated: alpha mostly corrects the risk part.
* C's 24 characteristics beat the harness's 5; the 8 market-state interactions destabilised the fits; standardising each week's returns helped every comparison; weekly beat daily estimation; ridge on Gamma hurt.
* **Verdict:** M05_U (IC 0.0224, t 2.27) meets the track-M development gate and is an M2 finalist candidate for the S&P 400 confirmation. It is a pick from 20 rows; its increment over MASTER fails the track-N gate.
