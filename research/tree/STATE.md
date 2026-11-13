# Tree search: progress ledger

*Rebuilt 2026-11-13 14:35 UTC by `state.py` from each branch's logs. To resume a branch after a usage limit: send its agent (or a new one) the `resume` line of its `STATE.json`.*

| branch | phase | status | scored | best (Amendment 2 rule) | mean IC / increment / net Sharpe | model.py | REPORT.md | verdict |
|---|---:|---|---:|---|---:|---|---|---|
| A_loss | 1 | done | 12 | huber_z | 0.0206 | no | no | development lead; finalist A_mse_rank failed the holdout |
| B_arch | 1 | done | 11 | mlp_Z_res_deep | 0.0162 | yes | yes | no gain over a small MLP |
| C_features | 1 | done | 15 | C13 C06 Fama-MacBeth | 0.0209 | yes | no | features carried into X1 |
| D_ensembles | 1 | done | 7 | hgb_multihorizon | 0.0236 | yes | yes | finalist D_hgb_mh failed the holdout |
| E_regime | 1 | done | 15 | E13 kernel ridge + panic | 0.0167 | yes | no | panic rule carried into X1; adaptation +0.005 |
| H7_build | None | in progress | 0 |  |  | no | no |  |
| L1_lit | None | in progress | 0 |  |  | no | yes |  |
| L2_practice | None | in progress | 0 |  |  | no | yes |  |
| L3_lit | None | in progress | 0 |  |  | no | yes |  |
| M1_dyntrade | 2 | done | 18 |  |  | yes | yes | construction rule: no-trade band for the S&P 400 confirmation |
| M2_ipca | 2 | done | 20 | M05_C24_wk_xn_U | 0.0224 | yes | yes | PASSED the S&P 400 read (IC 0.0183, t 2.17, Holm); S&P 500 check IC 0.012 (t 1.02), descriptive |
| M3_cae | 2 | done (seed ensemble never ran) | 8 | ca2_c32_k3 | 0.0213 | yes | yes | no finalist; factor structure does not beat direct prediction |
| M4_sdf | 2 | done | 12 | S05_C24_wk_en_raw | 0.0217 | yes | yes | failed the S&P 400 read (IC 0.0033, t 0.86) |
| M5_graph | 2 | done | 13 | R0_C24_fm | 0.0208 | yes | yes | no finalist; edges lower IC in 6 of 7 pairs |
| M6_ssl | 2 | done | 12 | com16_peerZ | 0.0197 | yes | yes | no finalist; embedding adds nothing over its control |
| N1_fundamentals | 2 | done | 23 | fm_ridge | 0.0055 | yes | yes | failed the S&P 500 2020-25 read (increment 0.000, t -0.02) |
| N2_short | 2 | done | 11 | c2 MASTER+F2 0.5/0.5 | 0.0020 | yes | yes | no finalist; increment t 1.14, double-ML t 1.61 |
| N3_intraday | 2 | done | 20 | N3_c3c_anchoredfm2 | 0.0118 | yes | yes | no finalist; increment is 1-month reversal, not intraday |
| N4_news | 2 | not started | 0 |  |  | no | no |  |
| Q1_seqnet | 3 | done | 18 | gru60_D27_ic_es | 0.0225 | yes | yes | No: sequence encoders add <0.0025 IC (t<=0.6) over the same network without them; nominee gru60_D27_ic_es IC .0225 (3 seeds) / .0206 (seeds 0-9) vs control .0141 (+.0065..+.0084, NW t 1.2-1.8) and D trees .0216-.0236 (not beaten); the gain comes from the 27 inputs + IC loss, not the sequences. |
| Q2_xsattn | 3 | done | 19 | moe_unif_d128_s10 | 0.0237 | yes | yes | No: cross-name attention (full, ISAB, pooling) and market-state gating never beat their ablations (best pair -0.0007, NW t -0.41, seeds 0-9; gate -0.0035); the best network (no module) IC 0.0237 ties D trees 0.0236 (t 0.02, weekly-IC corr 0.94); no module candidate nominated. |
| Q3_rankgbm | 3 | done | 19 | ens_ctrl_mh_huber | 0.0222 | yes | yes | No: ranking objectives, monotone constraints, DART, bigger trees, NaN-native, ranked Z, short window do not beat squared-error trees; best ens_ctrl_mh_huber IC 0.0222 vs control 0.0216, paired +0.0006 (NW t +0.48); JS shrinkage factor 0 |
| Q4_portfolio | 3 | done | 30 | mvnl_nt_trees | 0.6351 | yes | yes | No construction beats the M1 no-trade band by more than noise (best vol-matched paired t 0.72); best net Sharpe mvnl_nt_trees (LW2020 mean-variance + L1 no-trade region) 0.64 vs control 0.35, max DD 2.8% (12.2% at control vol) vs 16.2%, but post hoc, grid-edge tuned, fails on the other three signals in 2013-16 and earns only +0.88%/yr at gross 1: not nominated; keep the band. |
| Q5_rl | 3 | done | 30 | C_mvnlnt_trees | 0.7441 | yes | yes | No RL construction beats both controls: best rrl_dsr_trees (online-DSR Moody-Saffell RRL) net Sharpe 0.43 vs band 0.31 (vol-matched +0.82%/yr, t 1.50) but below mvnl_nt 0.74 (t -0.75), fails on MASTER; PPO/EIIE/E2E lose to the band; nothing nominated. |
| Q6_trade | 3 | in progress | 0 |  |  | no | no |  |
| Q7_features | 3 | in progress | 1 | ref_control | 0.0216 | yes | no |  |
| Q8_neutral | 3 | done | 12 | ipca_N2rule | 0.4238 | yes | yes | No neutralisation earns a place. N1 (p 0.5) cuts weekly IC sd ~20% and N2w ~35%, and both cut decile drawdown, but mean IC falls every time. Decile net Sharpe rises for trees (0.15->0.32) and MASTER (-0.26->-0.11), not significant (NW t 0.31, 0.93), all in 2013-16 (2017-19 diffs -0.08, +0.12 %/yr); band book not improved; IPCA hurt by N1 (-2.7 %/yr, t -1.59). EHL rule (2013-16): neutralise trees and MASTER, keep IPCA; applied 2017-19 trees worse (0.20->0.07), MASTER mixed (decile -0.28->-0.18, band 0.15->0.00), IPCA unchanged; the rule's inputs are unstable across periods. Neutralisation is a risk lever, not a net-return lever on these signals. Development results, not OOS; survivorship gap; current GICS applied to the past. |
| X1_combine | 1 | done | 11 | 8p_hgbD_mh+fmC_mh+mlpC_mh_panic | 0.0282 | yes | yes | finalist X1_8p failed the holdout (p 0.0173 vs 0.0167) |
| X2_costs | 1 | done | 11 | c1_base_mh | 0.0236 | yes | yes | smoothing cuts costs; hurt MASTER in the holdout |
| X3_online | 1 | done | 32 | c32_fm_exp | online, extra lag 52w | 0.0231 | yes | yes | updating inside the year does not help |
| X4_exploit | 3 | done | 10 | X4_mit33 | 0.0247 | yes | yes | no blend beats its best piece; IPCA does not beat its ridge control (t 0.23); band helps single fast signals (t 2-2.65); pre-declared blend: thirds + band |
| X5_overfit | 3 | done | 0 |  |  | no | yes | PBO and DSR did not predict survival; shrunk IC forecast better; choose by mean IC, not t (6 points, post hoc) |
