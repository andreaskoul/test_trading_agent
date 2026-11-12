# Branch X5: overfitting diagnostics and their calibration (layer 3, L3.3)

*Saved by the coordinating session from the agent's hand-back (its file write was refused).*

Weekly IC series rebuilt for 72 saved configurations (D 7, M2 20, M3 8, M4 12, M5 13, M6 12), each matching its logged
IC to within 5e-5 (`ICMAT_CHECKS.json`). A, X1 and N1 have no saved predictions: coarse yearly ICs only.

**PBO (CSCV, S = 16, 12,870 splits), in-sample best by mean IC:** D .42, M2 .75, M3 .59, M4 .62, M5 .33, M6 .60. In every
branch the in-sample best does no better out of sample than the branch median: choosing within a branch is noise.
Shrinkage factor B = 0 in five of six branches (between-configuration spread smaller than sampling noise).

| Finalist | Dev IC | Chosen by | PBO (mean/t) | DSR branch | DSR cumulative | Shrunk IC | Holdout IC | Kept |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| X1_8p | .0282 | IC = t | n/a (yearly .17) | .97 | .78 | .0237 | .0224 | 79% |
| D_hgb_mh | .0236 | IC = t | .42 / .25 | .98 | .62 | .0214 | .0185 | 78% |
| M2 M05_U | .0224 | IC = t | .75 / .61 | .91 | .24 | .0151 | .0183 | 82% |
| A_mse_rank | .0188 | t (best IC .0206) | n/a | .74 | .63 | .0140 | .0078 | 41% |
| M4 S04 | .0141 | t (best IC .0217) | .62 / .36 | .995 | .75 | .0153 | .0033 | 23% |
| N1 fm_fixed70 | +.0047 | t (best +.0055) | n/a | .91 | .25 | +.0032 | -.0001 | -2% |

* PBO and DSR did not separate survivors from failures (Spearman with retention +0.32, -0.20, -0.09).
* The shrunk IC forecast holdout IC better than the raw development IC (mean absolute error 0.0048 vs 0.0069; closer
  in 5 of 6).
* Found after the fact: finalists that were also their branch's best by mean IC kept 78-82%; those chosen by t over a
  higher-IC sibling (with unusually low weekly IC sd) kept -2% to 41%. Development mean IC ranks the six holdout ICs
  exactly; development t does not. Six points, chosen after looking: a hypothesis, not a validated rule.

**Recommended rule:** choose within a branch by mean IC (never t), positive in at least 5 of 7 years; forecast by the
shrunk IC; rank across branches by shrunk IC; at most two finalists with declared controls; record power at the shrunk
IC, PBO, DSR and a low-variance flag; if power at the shrunk IC is below 50%, register that a fail decides nothing.
