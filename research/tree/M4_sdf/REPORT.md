# Branch M4: shrinking the cross-section (Kozak, Nagel and Santosh 2020)

*Saved by the coordinating session from the agent's hand-back (its file write was refused).*

Managed portfolios F = Z'x/n from ranked characteristics (C24, or X324 with all pairwise products and squares); SDF weights b = (Sigma + gamma I)^-1 mu, gamma (and the elastic-net L1 term) chosen by 3-fold contiguous cross-validation of the out-of-fold pricing-error R^2 inside the training rows; score Z_t b.

| config | IC | t | years positive | decile net %/yr | net Sharpe |
|---|---:|---:|---:|---:|---:|
| S04_X324_wk_mv | 0.0141 | 3.67 | 7 | +0.4 | +0.11 |
| S11_X324_d5_l2 | 0.0119 | 2.43 | 6 | +0.7 | +0.15 |
| S01_C24_wk_l2 | 0.0200 | 2.20 | 6 | +0.2 | +0.03 |
| S06_C24_wk_en_pc | 0.0199 | 2.17 | 6 | -0.3 | -0.05 |
| S12_C24_d1_l2 | 0.0193 | 2.08 | 6 | -0.7 | -0.11 |
| S10_C24_d5_l2 | 0.0180 | 2.01 | 6 | -1.2 | -0.20 |
| S05_C24_wk_en_raw | 0.0217 | 2.00 | 6 | +1.0 | +0.13 |
| S07_X324_wk_en_raw | 0.0165 | 1.88 | 6 | +1.7 | +0.26 |
| S09_C24_wk_pck | 0.0184 | 1.78 | 6 | -0.3 | -0.03 |
| S02_C24_wk_mv | 0.0107 | 1.47 | 4 | -1.4 | -0.27 |
| S08_X324_wk_en_pc | 0.0067 | 1.32 | 6 | +0.0 | +0.01 |
| S03_X324_wk_l2 | 0.0068 | 1.30 | 6 | -0.1 | -0.03 |

Increment over MASTER: S04 +0.0016 (t 0.18, corr 0.07); S11 -0.0006 (t -0.08).

* Shrinkage beats the unshrunk SDF on 24 characteristics (0.0200 vs 0.0107); on 324 the minimum-norm pseudo-inverse (S04) beats cross-validated shrinkage.
* S04 has the highest t of any phase-2 model (3.67, positive in all 7 years) from a small but very steady IC (0.0141), nearly orthogonal to MASTER.
* **Verdict:** S04 meets the track-M development gate and is an M4 finalist candidate for the S&P 400 confirmation; it adds nothing to MASTER.
