# Decision ledger: what followed each decision

Updated 2026-11-21T01:12:26+00:00. Reporting only. y = the position side x the stock's residual return after the decision's close; for exits, y > 0 means the stock kept moving the position's way after we left. t is clustered by week. Small samples: read n before the mean.

## 5 sessions after the decision

| book | decision | news | n | weeks | mean bp | median bp | t | share > 0 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| control | capacity | hard | 16 | 4 | +53 | -85 |  | 44% |
| control | capacity | other | 5 | 3 | +196 | +46 |  | 60% |
| control | capacity | soft | 1 | 1 | -746 | -746 |  | 0% |
| control | caps_rebalance | hard | 4 | 1 | -89 | +21 |  | 50% |
| control | entry | hard | 52 | 6 | -105 | -118 | -0.62 | 46% |
| control | entry | other | 16 | 3 | -152 | -85 |  | 38% |
| control | entry | soft | 19 | 5 | +33 | +60 | +0.24 | 58% |
| control | flip_close | hard | 3 | 2 | +480 | +246 |  | 100% |
| control | flip_close | other | 1 | 1 | -833 | -833 |  | 0% |
| control | horizon | hard | 13 | 3 | -319 | -174 |  | 38% |
| control | horizon | other | 7 | 3 | -370 | -314 |  | 29% |
| control | horizon | soft | 14 | 3 | -202 | -118 |  | 21% |
| control | horizon_extend | hard | 2 | 1 | +42 | +42 |  | 50% |
| control | horizon_extend | soft | 1 | 1 | -361 | -361 |  | 0% |
| control | news_exit | hard | 3 | 3 | -372 | -362 |  | 0% |
| control | news_exit | other | 2 | 2 | -537 | -537 |  | 0% |
| control | news_exit | soft | 1 | 1 | +40 | +40 |  | 100% |
| control | news_increase | hard | 23 | 5 | +1 | +85 | +0.02 | 57% |
| control | news_increase | other | 3 | 2 | +191 | +29 |  | 67% |
| control | news_increase | soft | 3 | 2 | +516 | +766 |  | 67% |
| control | news_reduce | hard | 8 | 4 | -442 | -323 |  | 25% |
| control | news_reduce | other | 1 | 1 | +639 | +639 |  | 100% |
| control | news_reduce | soft | 1 | 1 | +263 | +263 |  | 100% |
| control | stop | other | 1 | 1 | +529 | +529 |  | 100% |
| live | capacity | hard | 9 | 4 | +427 | -65 |  | 44% |
| live | capacity | other | 4 | 2 | +305 | +276 |  | 75% |
| live | entry | hard | 42 | 6 | -100 | -108 | -0.58 | 48% |
| live | entry | other | 16 | 3 | -152 | -85 |  | 38% |
| live | entry | soft | 17 | 4 | -8 | +50 |  | 53% |
| live | flip_close | hard | 3 | 3 | +537 | +414 |  | 100% |
| live | flip_close | other | 1 | 1 | -833 | -833 |  | 0% |
| live | horizon | hard | 8 | 3 | -451 | -76 |  | 50% |
| live | horizon | other | 8 | 4 | -391 | -402 |  | 25% |
| live | horizon | soft | 15 | 3 | -228 | -122 |  | 20% |
| live | horizon_extend | hard | 1 | 1 | -89 | -89 |  | 0% |
| live | horizon_extend | soft | 1 | 1 | -361 | -361 |  | 0% |
| live | news_exit | hard | 3 | 3 | -372 | -362 |  | 0% |
| live | news_exit | other | 2 | 2 | -537 | -537 |  | 0% |
| live | news_exit | soft | 1 | 1 | +40 | +40 |  | 100% |
| live | news_increase | hard | 17 | 5 | -59 | -175 | -0.55 | 47% |
| live | news_increase | other | 3 | 2 | +191 | +29 |  | 67% |
| live | news_increase | soft | 3 | 2 | +516 | +766 |  | 67% |
| live | news_reduce | hard | 7 | 4 | -332 | -261 |  | 29% |
| live | news_reduce | other | 1 | 1 | +639 | +639 |  | 100% |
| live | stop | other | 1 | 1 | +529 | +529 |  | 100% |
| not_entered | a3_soft | soft | 3 | 1 | +164 | +313 |  | 67% |
| not_entered | not_entered | hard | 17 | 3 | -220 | -254 |  | 35% |
| not_entered | not_entered | soft | 1 | 1 | -760 | -760 |  | 0% |
| not_entered | stale | hard | 2 | 2 | -511 | -511 |  | 0% |
| not_entered | stale | other | 3 | 3 | -710 | -871 |  | 33% |
| not_entered | stale | soft | 19 | 6 | +69 | -24 | +0.29 | 47% |

## 10 sessions after the decision

| book | decision | news | n | weeks | mean bp | median bp | t | share > 0 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| control | capacity | hard | 9 | 3 | -467 | -277 |  | 22% |
| control | capacity | other | 5 | 3 | +122 | -243 |  | 20% |
| control | capacity | soft | 1 | 1 | +192 | +192 |  | 100% |
| control | entry | hard | 40 | 5 | -210 | -165 | -0.94 | 32% |
| control | entry | other | 16 | 3 | -294 | -313 |  | 25% |
| control | entry | soft | 17 | 4 | -71 | -104 |  | 41% |
| control | flip_close | hard | 1 | 1 | -1208 | -1208 |  | 0% |
| control | flip_close | other | 1 | 1 | -925 | -925 |  | 0% |
| control | horizon | hard | 9 | 2 | -281 | -46 |  | 44% |
| control | horizon | other | 7 | 3 | -380 | -277 |  | 14% |
| control | horizon | soft | 14 | 3 | -148 | -266 |  | 36% |
| control | horizon_extend | soft | 1 | 1 | +4 | +4 |  | 100% |
| control | news_exit | hard | 2 | 2 | -422 | -422 |  | 0% |
| control | news_exit | other | 2 | 2 | -434 | -434 |  | 0% |
| control | news_exit | soft | 1 | 1 | +435 | +435 |  | 100% |
| control | news_increase | hard | 21 | 4 | -440 | -221 |  | 29% |
| control | news_increase | other | 3 | 2 | +121 | +6 |  | 67% |
| control | news_increase | soft | 3 | 2 | +500 | +243 |  | 67% |
| control | news_reduce | hard | 7 | 3 | -523 | +33 |  | 57% |
| control | news_reduce | other | 1 | 1 | +1189 | +1189 |  | 100% |
| control | stop | other | 1 | 1 | +589 | +589 |  | 100% |
| live | capacity | hard | 7 | 3 | -12 | -277 |  | 43% |
| live | capacity | other | 4 | 2 | +231 | -166 |  | 25% |
| live | entry | hard | 36 | 5 | -188 | -165 | -0.82 | 31% |
| live | entry | other | 16 | 3 | -294 | -313 |  | 25% |
| live | entry | soft | 17 | 4 | -71 | -104 |  | 41% |
| live | flip_close | hard | 2 | 2 | -375 | -375 |  | 50% |
| live | flip_close | other | 1 | 1 | -925 | -925 |  | 0% |
| live | horizon | hard | 6 | 2 | -602 | -212 |  | 33% |
| live | horizon | other | 8 | 4 | -436 | -385 |  | 12% |
| live | horizon | soft | 15 | 3 | -147 | -224 |  | 33% |
| live | horizon_extend | soft | 1 | 1 | +4 | +4 |  | 100% |
| live | news_exit | hard | 2 | 2 | -422 | -422 |  | 0% |
| live | news_exit | other | 2 | 2 | -434 | -434 |  | 0% |
| live | news_exit | soft | 1 | 1 | +435 | +435 |  | 100% |
| live | news_increase | hard | 15 | 4 | -635 | -599 |  | 27% |
| live | news_increase | other | 3 | 2 | +121 | +6 |  | 67% |
| live | news_increase | soft | 3 | 2 | +500 | +243 |  | 67% |
| live | news_reduce | hard | 6 | 3 | -282 | +73 |  | 67% |
| live | news_reduce | other | 1 | 1 | +1189 | +1189 |  | 100% |
| live | stop | other | 1 | 1 | +589 | +589 |  | 100% |
| not_entered | not_entered | hard | 8 | 2 | -321 | -338 |  | 38% |
| not_entered | not_entered | soft | 1 | 1 | +219 | +219 |  | 100% |
| not_entered | stale | hard | 2 | 2 | -401 | -401 |  | 0% |
| not_entered | stale | other | 2 | 2 | -2675 | -2675 |  | 0% |
| not_entered | stale | soft | 18 | 5 | +218 | +166 | +0.75 | 67% |

## Does the desk's side match the news-day move?

Share of names whose side equals the sign of the residual move on the news session. Break-even for a follow-through trade: (2a - 1) x mu >= the round-trip cost.

| book | decision | news | agree / n | share | 95% interval |
|---|---|---|---:|---:|---|
| control | entry | hard | 40/65 | 62% | 49%-72% |
| control | entry | other | 11/18 | 61% | 39%-80% |
| control | entry | soft | 13/20 | 65% | 43%-82% |
| live | entry | hard | 30/49 | 61% | 47%-74% |
| live | entry | other | 11/18 | 61% | 39%-80% |
| live | entry | soft | 11/17 | 65% | 41%-83% |
| not_entered | a3_soft | soft | 3/4 | 75% | 30%-95% |
| not_entered | not_entered | hard | 15/23 | 65% | 45%-81% |
| not_entered | not_entered | soft | 1/1 | 100% | 21%-100% |
| not_entered | stale | hard | 1/2 | 50% | 9%-91% |
| not_entered | stale | other | 2/4 | 50% | 15%-85% |
| not_entered | stale | soft | 13/22 | 59% | 39%-77% |

## Where the result comes from: residual return per session held

Per unit of position, side x (r - beta x r_SPY), bp per lot-session. 'before entry' is one value per lot: the move from the as-of close to the entry close (not P&L). Earnings sessions are split out only where one fell inside a holding (calendar recorded from the 2026-10-28 cohort).

| book | segment | split | lot-sessions | lots | weeks | mean bp | t |
|---|---|---|---:|---:|---:|---:|---:|
| control | before entry | all | 103 | 103 | 7 | -11.5 | -0.29 |
| control | before entry | long | 49 | 49 | 7 | -9.8 | -0.17 |
| control | before entry | short | 54 | 54 | 7 | -13.0 | -0.36 |
| control | 1-3 | all | 270 | 103 | 7 | +8.3 | +0.77 |
| control | 1-3 | long | 129 | 49 | 7 | +16.8 | +0.64 |
| control | 1-3 | short | 141 | 54 | 7 | +0.6 | +0.07 |
| control | 4-15 | all | 231 | 61 | 6 | -36.5 | -1.54 |
| control | 4-15 | earnings | 3 | 3 | 2 | +372.7 |  |
| control | 4-15 | other | 228 | 60 | 6 | -41.9 | -1.74 |
| control | 4-15 | long | 123 | 28 | 6 | -37.9 | -1.14 |
| control | 4-15 | short | 108 | 33 | 6 | -35.0 | -1.22 |
| control | 16+ | all | 2 | 2 | 1 | -65.1 |  |
| control | 16+ | long | 2 | 2 | 1 | -65.1 |  |
| live | before entry | all | 84 | 84 | 7 | -19.1 | -0.41 |
| live | before entry | long | 39 | 39 | 7 | -13.6 | -0.19 |
| live | before entry | short | 45 | 45 | 7 | -23.9 | -0.73 |
| live | 1-3 | all | 227 | 84 | 7 | +3.3 | +0.31 |
| live | 1-3 | long | 107 | 39 | 7 | +7.7 | +0.29 |
| live | 1-3 | short | 120 | 45 | 7 | -0.6 | -0.08 |
| live | 4-15 | all | 270 | 54 | 6 | -32.3 | -1.49 |
| live | 4-15 | earnings | 2 | 2 | 2 | +436.9 |  |
| live | 4-15 | other | 268 | 54 | 6 | -35.8 | -1.61 |
| live | 4-15 | long | 136 | 23 | 6 | -41.1 | -1.33 |
| live | 4-15 | short | 134 | 31 | 6 | -23.4 | -0.66 |
| live | 16+ | all | 10 | 6 | 2 | +23.9 |  |
| live | 16+ | long | 8 | 4 | 2 | +18.5 |  |
| live | 16+ | short | 2 | 2 | 1 | +45.5 |  |

## Entries by structural label and 'priced in' at entry

7B Amendment 2 exempts structural lots from B1, so a structural name enters even when its move since the news is already the typical full reaction (p >= 1). Measurement only, before any rule change.

| book | structural | priced in | h | n | weeks | mean bp | t | share > 0 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| control | False | False | 5 | 8 | 2 | +482 |  | 75% |
| control | False | False | 10 | 4 | 1 | +606 |  | 50% |
| control | False | True | 5 | 6 | 2 | +126 |  | 50% |
| control | False | True | 10 | 1 | 1 | -456 |  | 0% |
| control | True | False | 5 | 6 | 2 | +1 |  | 50% |
| control | True | False | 10 | 4 | 1 | -1 |  | 25% |
| control | True | True | 5 | 6 | 2 | +170 |  | 67% |
| control | True | True | 10 | 3 | 1 | +330 |  | 33% |
| live | False | False | 5 | 5 | 2 | +716 |  | 80% |
| live | False | False | 10 | 3 | 1 | +605 |  | 33% |
| live | False | True | 5 | 4 | 2 | +139 |  | 50% |
| live | False | True | 10 | 1 | 1 | -456 |  | 0% |
| live | True | False | 5 | 4 | 2 | -60 |  | 50% |
| live | True | False | 10 | 3 | 1 | -173 |  | 0% |
| live | True | True | 5 | 3 | 1 | +175 |  | 67% |
| live | True | True | 10 | 3 | 1 | +330 |  | 33% |

Rank IC of the desk's weights vs the next 5 sessions' residual return: mean -0.127 over 6 cohorts.
Rank IC of the desk's weights vs the next 10 sessions' residual return: mean -0.238 over 5 cohorts.
