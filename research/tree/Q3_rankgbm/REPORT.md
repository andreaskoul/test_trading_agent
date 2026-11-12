# Branch Q3_rankgbm (Layer 3, Amendment 3): learning-to-rank and other boosted-tree variants

*Written by the branch agent; saved by the coordinating session because the agent's writes were refused. Development
data 2013-2019 only, walk-forward, seeds 0-2 (the `_s10` re-scores use seeds 0-9).*

**Verdict: no.** Learning-to-rank objectives, monotone constraints, DART, larger or deeper ensembles, native missing
values, ranked characteristics and a shorter training window all fail to beat squared-error trees on a ranked target.
The formal best, `ens_ctrl_mh_huber` (rank average of the control, LightGBM on a multi-horizon target and LightGBM
with Huber loss), has IC 0.0222 against the control's 0.0216: paired weekly difference +0.0006, Newey-West t +0.48
(4 lags, 353 weeks), positive in 4 of 7 years. That is noise. James-Stein shrinkage factor 0: every configuration
shrinks to the branch mean 0.0190. Nominated only as the formal best, with no evidence of improvement.

## Setup

* Records: `RESULTS.jsonl`; predictions `.cache/tree/preds/Q3_rankgbm/`.
* Control `ref_control` = `D_ensembles/model.py` unchanged; reproduces branch D's 0.0216 exactly.
* Inputs: D's features, imported unchanged: 25 columns (5 characteristics Z + 20 ranked return features; D's
  docstring says 27).
* Tree count chosen by rank IC on the last 104 training Thursdays (8-row gap), then refit on all training rows. No
  early stopping on random splits; no use of the validation year.
* Ranking objectives: each Thursday one query group; grades = within-week quintile (5) or ventile (20); linear gains,
  full truncation. 3 threads throughout.
* Installs: lightgbm 4.7.0 into the project venv. xgboost 3.4.1 installed but would not load (system libomp 17.0.4
  lacks `___kmpc_dispatch_deinit`); uninstalled rather than upgrade a shared system library. Substitute for
  `rank:pairwise`: a sampled pairwise RankNet custom objective in LightGBM (32 same-week partners per row, pairs
  weighted by |Δrank|).

## All configurations

IC = mean weekly Spearman IC. Shrunk = James-Stein toward the branch mean 0.0190 (k 19, factor 0). ΔIC = paired
difference vs ref_control (`harness.increment`, base = ref_control predictions), Newey-West t at 4 lags. Decile net =
top-minus-bottom decile at 5 bp a side.

| config | spec | IC | t | yrs+ | shrunk | decile net %/yr | net Sharpe | ΔIC | NW t | yrs Δ>0 | corr w/ ctrl |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ref_control | D HGB, squared error, 5-session rank target | 0.0216 | 2.30 | 6/7 | 0.0190 | +0.4 | +0.05 | — | — | — | 1.00 |
| lgb_l2 | LightGBM port of the control | 0.0204 | 2.23 | 6/7 | 0.0190 | -0.2 | -0.03 | -0.0012 | -1.14 | 2/7 | 0.96 |
| lgb_lambdarank_q5 | lambdarank, 5 grades | 0.0171 | 1.88 | 6/7 | 0.0190 | -0.4 | -0.07 | -0.0045 | -1.45 | 2/7 | 0.81 |
| lgb_lambdarank_q20 | lambdarank, 20 grades | 0.0154 | 1.75 | 6/7 | 0.0190 | +0.2 | +0.03 | -0.0062 | -1.78 | 2/7 | 0.80 |
| lgb_lambdarank_2side | top lambdarank minus bottom lambdarank | 0.0214 | 2.14 | 6/7 | 0.0190 | +1.3 | +0.20 | -0.0002 | -0.10 | 4/7 | 0.90 |
| lgb_xendcg_q20 | rank_xendcg listwise, 20 grades | 0.0005 | 0.06 | 4/7 | 0.0190 | -1.5 | -0.20 | -0.0211 | -1.25 | 1/7 | -0.15 |
| lgb_ranknet | sampled pairwise RankNet | 0.0206 | 2.28 | 6/7 | 0.0190 | +0.2 | +0.03 | -0.0010 | -0.80 | 2/7 | 0.96 |
| lgb_mono | monotone on 11 momentum/reversal features | 0.0192 | 2.08 | 6/7 | 0.0190 | +0.0 | +0.01 | -0.0024 | -1.76 | 1/7 | 0.94 |
| lgb_dart | DART | 0.0205 | 2.38 | 6/7 | 0.0190 | -0.1 | -0.02 | -0.0011 | -0.60 | 3/7 | 0.93 |
| lgb_big | 31 leaves, ≤1200 trees, colsample .3, bagging .7 | 0.0169 | 2.19 | 6/7 | 0.0190 | -0.4 | -0.07 | -0.0047 | -1.46 | 1/7 | 0.80 |
| lgb_gauss | Gaussianised rank target | 0.0187 | 2.33 | 6/7 | 0.0190 | -0.1 | -0.02 | -0.0029 | -0.98 | 2/7 | 0.90 |
| lgb_huber | Huber loss, Gaussianised rank | 0.0209 | 2.13 | 6/7 | 0.0190 | +1.7 | +0.23 | -0.0007 | -0.38 | 3/7 | 0.94 |
| lgb_mh | one target: mean rank of 3/5/10/20-session returns | 0.0215 | 2.27 | 6/7 | 0.0190 | +0.4 | +0.06 | -0.0001 | -0.06 | 3/7 | 0.87 |
| lgb_win5 | last 5 training years only | 0.0203 | 2.20 | 6/7 | 0.0190 | +0.3 | +0.04 | -0.0013 | -0.86 | 3/7 | 0.90 |
| lgb_nan | missing values native (LightGBM) | 0.0201 | 2.15 | 6/7 | 0.0190 | +0.7 | +0.10 | -0.0015 | -1.54 | 2/7 | 0.96 |
| lgb_rankZ | Z ranked across names instead of clipped | 0.0199 | 2.06 | 6/7 | 0.0190 | +0.5 | +0.07 | -0.0017 | -0.61 | 2/7 | 0.85 |
| **ens_ctrl_mh_huber** | rank average of ref_control, lgb_mh, lgb_huber | **0.0222** | 2.28 | 6/7 | 0.0190 | +0.8 | +0.11 | **+0.0006** | **+0.48** | 4/7 | 0.97 |
| ref_control_s10 | control, seeds 0-9 | 0.0215 | 2.29 | 6/7 | 0.0190 | +0.7 | +0.10 | -0.0001 | -0.25 | 5/7 | 0.99 |
| lgb_mh_s10 | lgb_mh, seeds 0-9 | 0.0220 | 2.36 | 6/7 | 0.0190 | +0.9 | +0.14 | +0.0004 | +0.18 | 3/7 | 0.87 |

## IC by year

| config | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 |
|---|---|---|---|---|---|---|---|
| ref_control | +0.026 | +0.021 | +0.054 | -0.015 | +0.014 | +0.030 | +0.021 |
| lgb_mh | +0.022 | +0.034 | +0.058 | -0.015 | +0.011 | +0.029 | +0.011 |
| lgb_huber | +0.023 | +0.022 | +0.054 | -0.021 | +0.021 | +0.029 | +0.019 |
| lgb_lambdarank_2side | +0.019 | +0.023 | +0.058 | -0.010 | +0.021 | +0.019 | +0.019 |
| lgb_lambdarank_q5 | +0.013 | +0.016 | +0.046 | -0.002 | +0.015 | +0.017 | +0.014 |
| lgb_xendcg_q20 | +0.006 | -0.007 | -0.027 | +0.033 | -0.014 | +0.009 | +0.003 |
| ens_ctrl_mh_huber | +0.024 | +0.027 | +0.058 | -0.018 | +0.016 | +0.030 | +0.017 |
| ref_control_s10 | +0.024 | +0.022 | +0.054 | -0.016 | +0.015 | +0.030 | +0.021 |
| lgb_mh_s10 | +0.023 | +0.035 | +0.058 | -0.015 | +0.012 | +0.030 | +0.010 |

Other configurations' yearly ICs: `summary.json`.

## Reading

1. **Learning to rank does not help.** One-sided lambdarank is worse than squared error on the same trees (0.0171 at
   5 grades, 0.0154 at 20, vs 0.0204): NDCG weights the top of the list, while IC and the long/short book use the
   whole ranking. A separate bottom model (`lgb_lambdarank_2side`) recovers the loss (0.0214, decile net +1.3 %/yr)
   but only ties the control (t -0.10), at about 10 minutes per walk-forward against under 1. RankNet ties squared
   error. rank_xendcg failed outright (IC 0.0005, correlation -0.15 with the control), not investigated. Poh et al.
   2020's large gains were against a weak MLP on monthly momentum features without costs; against squared-error trees
   on a cross-sectionally ranked target (already a rank-aware regression) we find none. Agrees with A_loss (mse_rank
   best).
2. **Monotone constraints hurt** (-0.0024, t -1.76, better in 1 of 7 years): reversal and momentum interact
   non-monotonically.
3. **Bigger or different ensembles do not help**: DART flat; deeper/larger worse (-0.0047, t -1.46); 5-year window
   flat. D's low-capacity settings (8 leaves, ≥400 rows per leaf) are near the optimum.
4. **Target transforms**: one LightGBM model on the multi-horizon target matches the control (0.0215 at 3 seeds,
   0.0220 at 10). Huber gives the best decile net (+1.7 %/yr, net Sharpe 0.23) at IC 0.0209: it changes the tails,
   not the mean IC; Gu-Kelly-Xiu's Huber claim is not confirmed on IC. Gaussianised target with squared error is
   worse (0.0187).
5. **Literature-note variants give no gain**: native missing values 0.0201, ranked Z 0.0199, against 0.0204 for the
   LightGBM port.
6. **Seed spread**: control 0.0216 (3 seeds) vs 0.0215 (10); lgb_mh 0.0215 vs 0.0220. Seed effects of ±0.0005 are as
   large as the best configuration's edge (+0.0006).
7. **Shrinkage factor 0**: the spread of the 19 ICs is no larger than their sampling error. The formula treats
   configurations as independent while they share weeks (correlation 0.8-0.97 with the control), so the paired
   Newey-West t is the sharper test. None is significant; the largest is +0.48.

## Best configuration

`model.py` implements `ens_ctrl_mh_huber` (equal-weight rank average of ref_control, lgb_mh, lgb_huber, each refit
per year and seed); re-running reproduces the logged IC exactly (0.022161877). Versus the control: IC 0.0222 vs
0.0216; decile net +0.8 vs +0.4 %/yr; net Sharpe 0.11 vs 0.05; paired ΔIC +0.0006, NW t +0.48, 4 of 7 years. The
`_s10` rows are seed checks, not candidates.

## Caveats

* Development panel: 241 of 738 ever-eligible names unpriced; 23.5% of eligible name-weeks without a target. Affects
  candidates and control alike; the paired difference on the same weeks is the right comparison.
* Selection: the best is chosen from 17 candidates on the same seven years; its selection-adjusted IC is about the
  shrunk 0.019, not 0.0222.
* Every tree configuration is negative in 2016.
* rank_xendcg's failure was not debugged; the listwise conclusion rests on lambdarank and RankNet.

## Process notes

* `research/tree/state.py` rewrote this branch's STATE.json mid-run, crashing `run.py` once after `lgb_mono` (no result
  lost; `run.py` now rebuilds STATE.json from RESULTS.jsonl). The coordinator has since made `state.py` read-only.
* Every configuration was added to `plan` before scoring. The two literature-note variants (`lgb_nan`, `lgb_rankZ`),
  the combination and both seed re-scores were added after the coordinator's notes.

Files: `lib.py`, `run.py`, `analyse.py`, `model.py`, `summary.json`, `RESULTS.jsonl`, `STATE.json`, `log1-3.txt`.
