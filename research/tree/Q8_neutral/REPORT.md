# Q8_neutral: neutralising the weekly score (Layer 3, Amendment 8)

*Written by the branch agent; saved by the coordinating session because the agent's writes were refused.
**Development results on S&P 500 2013-2019, not out of sample.** Survivorship gap: 241 of 738 names unpriced; 23.5% of
eligible name-weeks without a target. Plan written to STATE.json before scoring; 12 rows.*

## Verdict

**No neutralisation earns a place.** It acts as a risk lever, as the literature says: partial neutralisation (N1,
p 0.5) cuts the sd of weekly IC by about 20%, within-sector ranks (N2w) by about 35%, and both cut the decile book's
drawdown. It always costs mean IC. Decile net Sharpe rises for trees (0.15 → 0.32) and MASTER (−0.26 → −0.11), but
neither paired difference is significant (NW t 0.31, 0.93), both gains are in 2013-16 and vanish in 2017-19, and the
M1 band book does not improve. N1 hurts IPCA (−2.75 %/yr, t −1.59). The Ehsani-Harvey-Li rule (2013-16) says
neutralise trees and MASTER and keep IPCA; applied on 2017-19 it made trees worse, left IPCA unchanged and was mixed
for MASTER; its inputs flip between periods (trees ratio 0.29 → 0.79). Registered winners (`model.BEST_BY_SIGNAL`):
trees N1, IPCA N0, MASTER N1, none a significant gain.

## Configurations

* Signals: trees (`Q4 sig_trees.npy`), IPCA (`sig_ipca.npy`), MASTER (`D["master_h5_ref"]`), validation Thursdays
  2013-19.
* **N0**: centred rank of the raw score (reproduces `harness.score`; trees decile Sharpe 0.1499 in both).
* **N1**: s = centred rank over scored eligible names; E = [1, z(beta), z(log ADV), z(vol60), sector dummies];
  s −= 0.5·E·pinv(E)·s; re-ranked. Exposures causal: beta = `D["beta"][t]`; ADV = log mean FINRA Reg SHO total share
  volume t−19..t (≥ 10 sessions); vol60 = sd of `D["r"]` t−59..t (≥ 40); cross-sectional z, no winsorisation; missing
  exposure → z 0.
* **N2w**: centred percentile rank within the name's sector group.
* **N2rule** (Ehsani-Harvey-Li, 2013-16 only): rank-weighted book w (sides 0.5) split into w_across (sector mean) and
  w_within; weekly gross w·y5; neutralise iff SR(across)/SR(within) < corr(across, within). The decile-book version
  (descriptive) gave the same decisions.
* Metrics: weekly IC mean, sd, t; `harness.decile_net` at 5 bp (%/yr, Sharpe, max DD); M1 band 0.1 (first week
  dropped); paired differences vs N0 (NW t, 4 lags); 2013-16 / 2017-19 split.

## Results, 2013-19

| Signal | Config | IC | IC sd | IC t | Decile net %/yr | Decile Sharpe | Decile max DD | Band %/yr | Band Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| trees | N0 | 0.0236 | 0.184 | 2.41 | 1.04 | 0.15 | 19.3% | 2.20 | 0.35 |
| trees | N1 | 0.0213 | 0.142 | 2.81 | 1.49 | **0.32** | 13.0% | 1.53 | 0.35 |
| trees | N2w | 0.0169 | 0.114 | 2.78 | 0.37 | 0.08 | 13.5% | 1.38 | 0.32 |
| IPCA | N0 | 0.0224 | 0.185 | 2.27 | 1.48 | **0.22** | 13.2% | 2.24 | 0.36 |
| IPCA | N1 | 0.0176 | 0.143 | 2.32 | −1.27 | −0.28 | 12.3% | 0.28 | 0.07 |
| IPCA | N2w | 0.0135 | 0.121 | 2.09 | 0.13 | 0.03 | 8.4% | 0.01 | 0.00 |
| MASTER | N0 | 0.0125 | 0.164 | 1.43 | −1.73 | −0.26 | 23.4% | −0.28 | −0.05 |
| MASTER | N1 | 0.0110 | 0.136 | 1.52 | −0.51 | **−0.11** | 13.0% | −0.06 | −0.01 |
| MASTER | N2w | 0.0088 | 0.116 | 1.42 | −0.99 | −0.21 | 14.6% | −0.83 | −0.18 |

Paired differences vs N0 (NW t):

| Signal | Config | Period | IC diff (t) | Decile diff %/yr (t) | Band diff %/yr (t) |
|---|---|---|---|---|---|
| trees | N1 | 2013-19 | −0.0023 (−0.81) | +0.45 (0.31) | −0.67 (−0.53) |
| trees | N1 | 2013-16 | −0.0021 (−0.56) | +0.85 (0.43) | −0.11 (−0.06) |
| trees | N1 | 2017-19 | −0.0025 (−0.60) | −0.08 (−0.04) | −1.41 (−0.78) |
| trees | N2w | 2013-19 | −0.0066 (−1.41) | −0.66 (−0.48) | −0.82 (−0.66) |
| IPCA | N1 | 2013-19 | −0.0049 (−1.50) | −2.75 (−1.59) | −1.96 (−1.28) |
| IPCA | N1 | 2017-19 | −0.0034 (−0.76) | −2.25 (−0.89) | −0.80 (−0.36) |
| IPCA | N2w | 2013-19 | −0.0090 (−1.99) | −1.35 (−0.89) | −2.23 (−1.67) |
| MASTER | N1 | 2013-19 | −0.0015 (−0.70) | +1.22 (0.93) | +0.22 (0.19) |
| MASTER | N1 | 2013-16 | +0.0002 (0.08) | +2.05 (1.13) | +0.99 (0.62) |
| MASTER | N1 | 2017-19 | −0.0039 (−1.26) | +0.12 (0.06) | −0.81 (−0.52) |
| MASTER | N2w | 2013-19 | −0.0038 (−0.90) | +0.74 (0.63) | −0.55 (−0.52) |

Split, decile Sharpe (IC):

| Signal | N0 13-16 | N0 17-19 | N1 13-16 | N1 17-19 | N2w 13-16 | N2w 17-19 |
|---|---:|---:|---:|---:|---:|---:|
| trees | 0.12 (.025) | 0.20 (.021) | 0.36 (.023) | 0.26 (.019) | 0.08 (.019) | 0.07 (.014) |
| IPCA | 0.06 (.024) | 0.42 (.020) | −0.68 (.018) | 0.14 (.017) | −0.06 (.013) | 0.13 (.014) |
| MASTER | −0.25 (.010) | −0.28 (.017) | 0.07 (.010) | −0.33 (.013) | −0.22 (.009) | −0.18 (.008) |

## Ehsani-Harvey-Li rule (rank-weighted book, gross)

| Signal | Period | SR across | SR within | corr | ratio | Neutralise? |
|---|---|---:|---:|---:|---:|---|
| trees | **2013-16 (decision)** | 0.17 | 0.57 | 0.69 | 0.29 | **yes** |
| trees | 2017-19 | 0.53 | 0.67 | 0.54 | 0.79 | no |
| trees | 2013-19 | 0.30 | 0.61 | 0.63 | 0.49 | yes |
| IPCA | **2013-16** | 0.59 | 0.26 | 0.59 | 2.27 | **no** |
| IPCA | 2017-19 | 0.43 | 0.61 | 0.58 | 0.71 | no |
| IPCA | 2013-19 | 0.52 | 0.42 | 0.58 | 1.25 | no |
| MASTER | **2013-16** | −0.20 | 0.18 | 0.62 | −1.10 | **yes** |
| MASTER | 2017-19 | 0.81 | 0.30 | 0.52 | 2.68 | no |
| MASTER | 2013-19 | 0.22 | 0.23 | 0.58 | 0.96 | no |

Applied on 2017-19 (151 weeks) vs N0: trees N2w decile Sharpe 0.07 vs 0.20 (−0.95 %/yr, t −0.50), IC 0.014 vs 0.021,
band 0.53 vs 0.56; IPCA N0 unchanged; MASTER N2w −0.18 vs −0.28 (+0.94 %/yr, t 0.53), IC 0.008 vs 0.017, band 0.00 vs
0.15. Across and within correlate 0.5-0.7: the same tilts (low beta, low vol) pay both ways.

## Exposures (descriptive)

| Signal | corr with beta | log ADV | vol60 | R² on all of E | R² on sector dummies |
|---|---:|---:|---:|---:|---:|
| trees | −0.55 | −0.13 | −0.30 | 0.41 | 0.19 |
| IPCA | −0.42 | −0.11 | −0.28 | 0.39 | 0.21 |
| MASTER | −0.16 | −0.07 | −0.18 | 0.28 | 0.15 |

Trees and IPCA lean heavily to low beta (y5 is beta-hedged, so the tilt is learned). N1 roughly halves exposures.

## Sector data audit (CLAUDE.md rules 1-4)

* Source: `.cache/p8/gics.json`, built by `research/p8/gics.py` (exact match of each firm's GICS sub-industry name
  from `data/raw/stocks/sp{500,400}_current.csv` to Wikipedia's 8-digit codes); 902 firms, 0 unmatched.
* Typed field: sector = `industry_code[:2]` (11 values, 10-60). Not `sub_code` (DKS and FIVE in the retired
  "Specialty Stores" have null `sub_code` but typed `industry_code` 255040).
* Coverage: 533 of 850 panel names; 434 of 666 names eligible in some validation week; 71.4% of eligible name-weeks;
  92.2% of name-weeks with a target (7.8% "NA"). The 232 NA names are mostly former members (AABA, AET, CELG, RHT, TWX,
  FB, …), overlapping the unpriced names. Scored name-weeks in NA: trees 7.8%, MASTER 7.8%, IPCA 28.6%.
* Missing sector: its own group "NA"; never guessed.
* Look-ahead (disclosed): today's classification (2023 GICS, current members) applied to 2013-19; the 2018 creation of
  Communication Services is the large case; presence in the file depends on current membership.
* Other inputs: FINRA volume 97.1% of eligible name-weeks; vol60 prices 76.8% (100% for trees and MASTER); beta 100%.
  ADV proxy is FINRA share volume, not dollar volume (`dev.npz` has no price level).
* `model.check` raises on: sector coverage < 434; codes outside the 11; beta missing on a scored name; FINRA coverage
  < 95% or price coverage < 70%; output mask differing from input; a full projection (p 1) not zeroing exposures.
  Confirmed failing on a corrupted mask, a missing gics.json and empty FINRA data.

## Caveats

Development data already used by earlier branches; 2013-16 also set the rule's decision. Today's classification and
the survivorship gap. Flat 5 bp misses neutralisation's extra turnover (trees band turnover 0.26 → 0.32 with N1).

Files: `model.py` (`neutralise(scores, D, rows, mode)`, `BEST_BY_SIGNAL`, `check()`), `run.py`, `run.log`,
`RESULTS.jsonl` (12 rows; `net_sharpe` = decile net Sharpe; for N2rule rows the 2017-19 value of the applied choice),
`STATE.json`. Weekly arrays: `.cache/tree/preds/Q8_neutral/<signal>_<config>.npy` (row, IC, decile_net, band_net,
band_turnover) and `<signal>_<config>_scores.npy`.
