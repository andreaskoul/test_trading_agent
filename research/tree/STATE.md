# Tree search: progress ledger

*Rebuilt 2026-11-12 13:25 UTC by `state.py` from each branch's logs. To resume a branch after a usage limit: send its agent (or a new one) the `resume` line of its `STATE.json`.*

| branch | phase | status | scored | best | metric | model.py | REPORT.md | verdict |
|---|---:|---|---:|---|---:|---|---|---|
| A_loss | 1 | done | 12 | mse_rank | 2.45 | no | no | development lead; finalist A_mse_rank failed the holdout |
| B_arch | 1 | done | 11 | mlp_Z_res_deep | 1.96 | yes | yes | no gain over a small MLP |
| C_features | 1 | done | 15 | C13 C06 Fama-MacBeth | 2.29 | yes | no | features carried into X1 |
| D_ensembles | 1 | done | 7 | hgb_multihorizon | 2.41 | yes | yes | finalist D_hgb_mh failed the holdout |
| E_regime | 1 | done | 15 | E13 kernel ridge + panic | 1.62 | yes | no | panic rule carried into X1; adaptation +0.005 |
| M1_dyntrade | 2 | done | 18 |  |  | yes | yes | no-trade band carried to S&P 400 confirmation; no MASTER gain |
| M2_ipca | 2 | in progress | 12 | M05_C24_wk_xn_U | 2.27 | no | no |  |
| M3_cae | 2 | done (seed ensemble never ran) | 8 | ca2_c32_k3 | 2.00 | yes | yes | no finalist; factor structure does not beat direct prediction |
| M4_sdf | 2 | not started | 0 |  |  | no | no |  |
| M5_graph | 2 | not started | 0 |  |  | no | no |  |
| M6_ssl | 2 | not started | 0 |  |  | no | no |  |
| N1_fundamentals | 2 | not started | 0 |  |  | no | no |  |
| N2_short | 2 | done | 11 | c3 MASTER+F2 0.7/0.3 | 1.14 | yes | yes | no finalist; increment t 1.14, double-ML t 1.61 |
| N3_intraday | 2 | done | 20 | N3_c8_control_tot21 | 1.72 | yes | yes | no finalist; increment is 1-month reversal, not intraday |
| N4_news | 2 | not started | 0 |  |  | no | no |  |
| X1_combine | 1 | done | 11 | 8p_hgbD_mh+fmC_mh+mlpC_mh_panic | 2.91 | yes | yes | finalist X1_8p failed the holdout (p 0.0173 vs 0.0167) |
| X2_costs | 1 | done | 11 | c1_base_mh | 2.41 | yes | yes | smoothing cuts costs; hurt MASTER in the holdout |
| X3_online | 1 | done | 32 | c32_fm_exp | online, extra lag 52w | 2.47 | yes | yes | updating inside the year does not help |
