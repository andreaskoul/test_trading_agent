# Tree search, round 1 (explore): results on the development sample

*Compiled 2026-11-12 from each branch's `RESULTS.jsonl`. Development sample 2013-2019, walk-forward, 3 seeds. The standard error of a mean IC is about 0.01. References: ridge -0.002; MASTER 5-day 0.0125 (t 1.43). Nothing here is evidence; the holdout is unread.*

The agents were stopped twice by the account's usage limit. Branches A and C did not write their reports; their logs are complete for the configurations listed.

## A_loss (12 configurations)

| configuration | IC | t | years positive of 7 | decile net % a year | net Sharpe |
|---|---:|---:|---:|---:|---:|
| mse_rank | +0.0188 | +2.45 | 6 | -1.0 | -0.19 |
| ic_sharpe | +0.0169 | +2.39 | 6 | +0.1 | +0.01 |
| mse_gauss | +0.0204 | +2.37 | 6 | -0.9 | -0.13 |
| huber_z | +0.0206 | +2.37 | 6 | -0.1 | -0.01 |
| listmle | +0.0197 | +2.27 | 6 | -1.2 | -0.19 |
| pairwise | +0.0181 | +2.09 | 6 | -0.3 | -0.04 |
| mse_raw | +0.0125 | +2.06 | 6 | -0.5 | -0.09 |
| ic_gauss | +0.0174 | +1.80 | 6 | +1.5 | +0.22 |
| softmax_ce | +0.0108 | +1.43 | 5 | -1.5 | -0.25 |
| cls_quintile | +0.0072 | +1.11 | 4 | -1.7 | -0.38 |
| spread_sharpe | -0.0024 | -0.31 | 4 | -3.0 | -0.58 |
| spread | -0.0045 | -0.69 | 4 | -4.2 | -0.86 |

## B_arch (11 configurations)

| configuration | IC | t | years positive of 7 | decile net % a year | net Sharpe |
|---|---:|---:|---:|---:|---:|
| mlp_Z_res_deep | +0.0162 | +1.96 | 6 | -0.1 | -0.03 |
| gru_e20_Z_xattn | +0.0153 | +1.68 | 6 | +0.7 | +0.11 |
| mlp_Z_xattn | +0.0141 | +1.52 | 6 | -0.4 | -0.07 |
| gru_e20_Z | +0.0127 | +1.50 | 6 | -1.8 | -0.31 |
| mlp_Z_gate | +0.0117 | +1.48 | 6 | -1.4 | -0.25 |
| mlp_Z | +0.0135 | +1.47 | 6 | -1.0 | -0.17 |
| gru_e20 | +0.0109 | +1.45 | 5 | -1.1 | -0.21 |
| gru_e20_Z_gate | +0.0114 | +1.44 | 4 | -2.4 | -0.44 |
| mlp_Z_wide_nonorm | +0.0113 | +1.21 | 5 | -2.3 | -0.36 |
| cnn_e60 | +0.0053 | +0.85 | 3 | -3.6 | -0.71 |
| tfm_e60 | +0.0015 | +0.23 | 4 | -3.5 | -0.67 |

## C_features (15 configurations)

| configuration | IC | t | years positive of 7 | decile net % a year | net Sharpe |
|---|---:|---:|---:|---:|---:|
| C13 C06 Fama-MacBeth | +0.0209 | +2.29 | 6 | -0.3 | -0.04 |
| C06 all 24 + market-state interactions | +0.0203 | +2.23 | 6 | +0.8 | +0.14 |
| C07 rev + risk groups | +0.0197 | +2.17 | 6 | -0.3 | -0.05 |
| C10 C06 with gaussianised ranks | +0.0199 | +2.11 | 6 | +0.1 | +0.01 |
| C11 C06 rolling 3y window | +0.0196 | +2.08 | 6 | +0.0 | +0.01 |
| C08 all 24 + all x market vol | +0.0183 | +2.04 | 6 | -0.1 | -0.02 |
| C14 C06 heavy shrinkage lam 3 | +0.0185 | +1.96 | 6 | -1.4 | -0.21 |
| C05 all 24 | +0.0182 | +1.93 | 6 | +0.4 | +0.06 |
| C15 C06 Thursdays only | +0.0182 | +1.90 | 6 | -0.1 | -0.01 |
| C12 C06 exp-weighted hl 2y | +0.0178 | +1.87 | 6 | +1.0 | +0.16 |
| C09 C06 with z-scores | +0.0185 | +1.86 | 6 | -0.9 | -0.14 |
| C01 rev group | +0.0122 | +1.42 | 6 | -0.5 | -0.09 |
| C03 risk group | +0.0146 | +1.37 | 6 | -0.2 | -0.03 |
| C04 52w-high + vol-scaled | +0.0119 | +1.30 | 6 | -1.3 | -0.21 |
| C02 mom group | +0.0047 | +0.47 | 6 | -1.7 | -0.27 |

## D_ensembles (7 configurations)

| configuration | IC | t | years positive of 7 | decile net % a year | net Sharpe |
|---|---:|---:|---:|---:|---:|
| hgb_multihorizon | +0.0236 | +2.41 | 6 | +1.0 | +0.15 |
| hgb | +0.0216 | +2.30 | 6 | +0.4 | +0.05 |
| ew_all6 | +0.0233 | +2.21 | 6 | +1.0 | +0.14 |
| rf | +0.0206 | +2.13 | 6 | +1.5 | +0.22 |
| ew_hgb_et_ridge | +0.0218 | +2.00 | 6 | +0.8 | +0.11 |
| et | +0.0211 | +2.00 | 6 | +0.9 | +0.12 |
| ridge | +0.0181 | +1.64 | 6 | -0.4 | -0.05 |

## E_regime (15 configurations)

| configuration | IC | t | years positive of 7 | decile net % a year | net Sharpe |
|---|---:|---:|---:|---:|---:|
| E13 kernel ridge + panic | +0.0167 | +1.62 | 6 | +0.7 | +0.10 |
| E04 panic rule | +0.0163 | +1.59 | 5 | +1.0 | +0.13 |
| E15 panic rule vol median | +0.0163 | +1.59 | 5 | +1.0 | +0.13 |
| E12 panic mom+52wh off | +0.0138 | +1.32 | 5 | +0.2 | +0.03 |
| E11 panic rule ew52 base | +0.0124 | +1.27 | 5 | -0.6 | -0.08 |
| E14 kernel h0.7 shrink0.3 | +0.0130 | +1.26 | 5 | +0.2 | +0.03 |
| E05 kernel ridge | +0.0124 | +1.20 | 5 | -0.1 | -0.02 |
| E10 static ridge control | +0.0110 | +1.05 | 5 | -0.6 | -0.08 |
| E01 ew ridge hl52 | +0.0100 | +1.02 | 5 | -1.5 | -0.19 |
| E06 exp weights | +0.0113 | +1.01 | 5 | -0.8 | -0.09 |
| E09 mixture of experts | +0.0105 | +0.97 | 5 | -0.1 | -0.01 |
| E03 interaction ridge | +0.0096 | +0.96 | 5 | -0.9 | -0.12 |
| E02 rolling ridge 104w | +0.0076 | +0.77 | 5 | -1.9 | -0.25 |
| E08 hypernet | +0.0062 | +0.59 | 4 | -1.0 | -0.13 |
| E07 ic timing 52w | +0.0026 | +0.26 | 3 | -3.2 | -0.42 |

**Total configurations scored in round 1: 60.**

## Reading

* Ranked or gaussianised targets, a wider set of price features, and boosted trees each reach an IC near 0.02, against 0.0125 for MASTER. The differences among them are inside the noise.
* Network design (attention, recurrent and convolutional encoders) added nothing over a small MLP.
* Regime adaptation added about half a standard error; the branch's own control shows most of its gain came from ranking the target.
* After 5 bp a side the decile spread is about zero for every configuration.
