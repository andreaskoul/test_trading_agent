# Decision ledger: what followed each decision

Updated 2026-11-18T01:14:33+00:00. Reporting only. y = the position side x the stock's residual return after the decision's close; for exits, y > 0 means the stock kept moving the position's way after we left. t is clustered by week. Small samples: read n before the mean.

## 5 sessions after the decision

| book | decision | news | n | weeks | mean bp | median bp | t | share > 0 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| control | capacity | hard | 9 | 3 | +130 | -106 |  | 44% |
| control | capacity | other | 5 | 3 | +196 | +46 |  | 60% |
| control | capacity | soft | 1 | 1 | -746 | -746 |  | 0% |
| control | entry | hard | 40 | 5 | -156 | -120 | -0.72 | 42% |
| control | entry | other | 16 | 3 | -152 | -85 |  | 38% |
| control | entry | soft | 17 | 4 | -8 | +50 |  | 53% |
| control | flip_close | hard | 1 | 1 | +979 | +979 |  | 100% |
| control | flip_close | other | 1 | 1 | -833 | -833 |  | 0% |
| control | horizon | hard | 11 | 3 | -376 | -174 |  | 36% |
| control | horizon | other | 7 | 3 | -370 | -314 |  | 29% |
| control | horizon | soft | 14 | 3 | -202 | -118 |  | 21% |
| control | horizon_extend | hard | 2 | 1 | +42 | +42 |  | 50% |
| control | horizon_extend | soft | 1 | 1 | -361 | -361 |  | 0% |
| control | news_exit | hard | 3 | 3 | -372 | -362 |  | 0% |
| control | news_exit | other | 2 | 2 | -537 | -537 |  | 0% |
| control | news_exit | soft | 1 | 1 | +40 | +40 |  | 100% |
| control | news_increase | hard | 21 | 4 | +7 | +86 |  | 57% |
| control | news_increase | other | 3 | 2 | +191 | +29 |  | 67% |
| control | news_increase | soft | 3 | 2 | +516 | +766 |  | 67% |
| control | news_reduce | hard | 8 | 4 | -442 | -323 |  | 25% |
| control | news_reduce | other | 1 | 1 | +639 | +639 |  | 100% |
| control | stop | other | 1 | 1 | +529 | +529 |  | 100% |
| live | capacity | hard | 7 | 3 | +612 | +506 |  | 57% |
| live | capacity | other | 4 | 2 | +305 | +276 |  | 75% |
| live | entry | hard | 36 | 5 | -151 | -120 | -0.75 | 42% |
| live | entry | other | 16 | 3 | -152 | -85 |  | 38% |
| live | entry | soft | 17 | 4 | -8 | +50 |  | 53% |
| live | flip_close | hard | 2 | 2 | +697 | +697 |  | 100% |
| live | flip_close | other | 1 | 1 | -833 | -833 |  | 0% |
| live | horizon | hard | 7 | 3 | -536 | -187 |  | 43% |
| live | horizon | other | 8 | 4 | -391 | -402 |  | 25% |
| live | horizon | soft | 15 | 3 | -228 | -122 |  | 20% |
| live | horizon_extend | hard | 1 | 1 | -89 | -89 |  | 0% |
| live | horizon_extend | soft | 1 | 1 | -361 | -361 |  | 0% |
| live | news_exit | hard | 3 | 3 | -372 | -362 |  | 0% |
| live | news_exit | other | 2 | 2 | -537 | -537 |  | 0% |
| live | news_exit | soft | 1 | 1 | +40 | +40 |  | 100% |
| live | news_increase | hard | 15 | 4 | -16 | +86 |  | 53% |
| live | news_increase | other | 3 | 2 | +191 | +29 |  | 67% |
| live | news_increase | soft | 3 | 2 | +516 | +766 |  | 67% |
| live | news_reduce | hard | 7 | 4 | -332 | -261 |  | 29% |
| live | news_reduce | other | 1 | 1 | +639 | +639 |  | 100% |
| live | stop | other | 1 | 1 | +529 | +529 |  | 100% |
| not_entered | not_entered | hard | 8 | 2 | -244 | -480 |  | 38% |
| not_entered | not_entered | soft | 1 | 1 | -760 | -760 |  | 0% |
| not_entered | stale | hard | 2 | 2 | -511 | -511 |  | 0% |
| not_entered | stale | other | 2 | 2 | -1293 | -1293 |  | 0% |
| not_entered | stale | soft | 18 | 5 | +77 | +15 | +0.30 | 50% |

## 10 sessions after the decision

| book | decision | news | n | weeks | mean bp | median bp | t | share > 0 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| control | capacity | hard | 5 | 2 | -656 | -388 |  | 20% |
| control | capacity | other | 5 | 3 | +122 | -243 |  | 20% |
| control | capacity | soft | 1 | 1 | +192 | +192 |  | 100% |
| control | entry | hard | 28 | 4 | -406 | -331 |  | 32% |
| control | entry | other | 16 | 3 | -294 | -313 |  | 25% |
| control | entry | soft | 17 | 4 | -71 | -104 |  | 41% |
| control | flip_close | hard | 1 | 1 | -1208 | -1208 |  | 0% |
| control | flip_close | other | 1 | 1 | -925 | -925 |  | 0% |
| control | horizon | hard | 9 | 2 | -281 | -46 |  | 44% |
| control | horizon | other | 7 | 3 | -380 | -277 |  | 14% |
| control | horizon | soft | 14 | 3 | -148 | -266 |  | 36% |
| control | horizon_extend | soft | 1 | 1 | +4 | +4 |  | 100% |
| control | news_exit | hard | 1 | 1 | -83 | -83 |  | 0% |
| control | news_exit | other | 2 | 2 | -434 | -434 |  | 0% |
| control | news_exit | soft | 1 | 1 | +435 | +435 |  | 100% |
| control | news_increase | hard | 14 | 4 | -722 | -576 |  | 21% |
| control | news_increase | other | 3 | 2 | +121 | +6 |  | 67% |
| control | news_increase | soft | 3 | 2 | +500 | +243 |  | 67% |
| control | news_reduce | hard | 5 | 3 | -65 | +112 |  | 80% |
| control | news_reduce | other | 1 | 1 | +1189 | +1189 |  | 100% |
| control | stop | other | 1 | 1 | +589 | +589 |  | 100% |
| live | capacity | hard | 5 | 2 | -656 | -388 |  | 20% |
| live | capacity | other | 4 | 2 | +231 | -166 |  | 25% |
| live | entry | hard | 26 | 4 | -330 | -211 |  | 35% |
| live | entry | other | 16 | 3 | -294 | -313 |  | 25% |
| live | entry | soft | 17 | 4 | -71 | -104 |  | 41% |
| live | flip_close | hard | 1 | 1 | -1208 | -1208 |  | 0% |
| live | flip_close | other | 1 | 1 | -925 | -925 |  | 0% |
| live | horizon | hard | 6 | 2 | -602 | -212 |  | 33% |
| live | horizon | other | 8 | 4 | -436 | -385 |  | 12% |
| live | horizon | soft | 15 | 3 | -147 | -224 |  | 33% |
| live | horizon_extend | soft | 1 | 1 | +4 | +4 |  | 100% |
| live | news_exit | hard | 1 | 1 | -83 | -83 |  | 0% |
| live | news_exit | other | 2 | 2 | -434 | -434 |  | 0% |
| live | news_exit | soft | 1 | 1 | +435 | +435 |  | 100% |
| live | news_increase | hard | 11 | 4 | -969 | -719 |  | 9% |
| live | news_increase | other | 3 | 2 | +121 | +6 |  | 67% |
| live | news_increase | soft | 3 | 2 | +500 | +243 |  | 67% |
| live | news_reduce | hard | 5 | 3 | -65 | +112 |  | 80% |
| live | news_reduce | other | 1 | 1 | +1189 | +1189 |  | 100% |
| live | stop | other | 1 | 1 | +589 | +589 |  | 100% |
| not_entered | not_entered | hard | 3 | 1 | -992 | -586 |  | 0% |
| not_entered | not_entered | soft | 1 | 1 | +219 | +219 |  | 100% |
| not_entered | stale | hard | 1 | 1 | -296 | -296 |  | 0% |
| not_entered | stale | other | 2 | 2 | -2675 | -2675 |  | 0% |
| not_entered | stale | soft | 14 | 4 | +388 | +244 |  | 71% |

## Does the desk's side match the news-day move?

Share of names whose side equals the sign of the residual move on the news session. Break-even for a follow-through trade: (2a - 1) x mu >= the round-trip cost.

| book | decision | news | agree / n | share | 95% interval |
|---|---|---|---:|---:|---|
| control | entry | hard | 31/52 | 60% | 46%-72% |
| control | entry | other | 10/16 | 62% | 39%-82% |
| control | entry | soft | 12/19 | 63% | 41%-81% |
| live | entry | hard | 25/42 | 60% | 44%-73% |
| live | entry | other | 10/16 | 62% | 39%-82% |
| live | entry | soft | 11/17 | 65% | 41%-83% |
| not_entered | a3_soft | soft | 2/3 | 67% | 21%-94% |
| not_entered | not_entered | hard | 11/17 | 65% | 41%-83% |
| not_entered | not_entered | soft | 1/1 | 100% | 21%-100% |
| not_entered | stale | hard | 1/2 | 50% | 9%-91% |
| not_entered | stale | other | 1/3 | 33% | 6%-79% |
| not_entered | stale | soft | 10/19 | 53% | 32%-73% |

## Where the result comes from: residual return per session held

Per unit of position, side x (r - beta x r_SPY), bp per lot-session. 'before entry' is one value per lot: the move from the as-of close to the entry close (not P&L). Earnings sessions are split out only where one fell inside a holding (calendar recorded from the 2026-10-28 cohort).

| book | segment | split | lot-sessions | lots | weeks | mean bp | t |
|---|---|---|---:|---:|---:|---:|---:|
| control | before entry | all | 87 | 87 | 6 | -25.2 | -0.57 |
| control | before entry | long | 41 | 41 | 6 | -23.4 | -0.36 |
| control | before entry | short | 46 | 46 | 6 | -26.9 | -0.68 |
| control | 1-3 | all | 254 | 87 | 7 | +8.0 | +0.69 |
| control | 1-3 | long | 121 | 41 | 7 | +11.0 | +0.38 |
| control | 1-3 | short | 133 | 46 | 7 | +5.2 | +0.42 |
| control | 4-15 | all | 196 | 50 | 6 | -48.1 | -2.10 |
| control | 4-15 | earnings | 1 | 1 | 1 | +908.3 |  |
| control | 4-15 | other | 195 | 50 | 6 | -53.0 | -2.27 |
| control | 4-15 | long | 105 | 23 | 6 | -41.9 | -1.09 |
| control | 4-15 | short | 91 | 27 | 6 | -55.2 | -2.85 |
| live | before entry | all | 75 | 75 | 6 | -36.2 | -0.74 |
| live | before entry | long | 35 | 35 | 6 | -34.3 | -0.45 |
| live | before entry | short | 40 | 40 | 6 | -37.9 | -1.15 |
| live | 1-3 | all | 218 | 75 | 7 | +4.3 | +0.38 |
| live | 1-3 | long | 103 | 35 | 7 | +2.6 | +0.09 |
| live | 1-3 | short | 115 | 40 | 7 | +5.8 | +0.42 |
| live | 4-15 | all | 230 | 50 | 6 | -38.9 | -1.81 |
| live | 4-15 | earnings | 1 | 1 | 1 | +908.3 |  |
| live | 4-15 | other | 229 | 50 | 6 | -43.1 | -2.02 |
| live | 4-15 | long | 117 | 21 | 6 | -38.9 | -1.09 |
| live | 4-15 | short | 113 | 29 | 6 | -39.0 | -1.44 |
| live | 16+ | all | 3 | 1 | 2 | +5.1 |  |
| live | 16+ | long | 3 | 1 | 2 | +5.1 |  |

## Entries by structural label and 'priced in' at entry

7B Amendment 2 exempts structural lots from B1, so a structural name enters even when its move since the news is already the typical full reaction (p >= 1). Measurement only, before any rule change.

| book | structural | priced in | h | n | weeks | mean bp | t | share > 0 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| control | False | False | 5 | 4 | 1 | +963 |  | 75% |
| control | False | True | 5 | 1 | 1 | -459 |  | 0% |
| control | True | False | 5 | 4 | 1 | +38 |  | 50% |
| control | True | True | 5 | 3 | 1 | +175 |  | 67% |
| live | False | False | 5 | 3 | 1 | +1132 |  | 67% |
| live | False | True | 5 | 1 | 1 | -459 |  | 0% |
| live | True | False | 5 | 3 | 1 | -88 |  | 33% |
| live | True | True | 5 | 3 | 1 | +175 |  | 67% |

Rank IC of the desk's weights vs the next 5 sessions' residual return: mean -0.166 over 5 cohorts.
Rank IC of the desk's weights vs the next 10 sessions' residual return: mean -0.309 over 4 cohorts.
