# Decision ledger: what followed each decision

Updated 2026-11-28T01:12:35+00:00. Reporting only. y = the position side x the stock's residual return after the decision's close; for exits, y > 0 means the stock kept moving the position's way after we left. t is clustered by week. Small samples: read n before the mean.

## 5 sessions after the decision

| book | decision | news | n | weeks | mean bp | median bp | t | share > 0 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| control | capacity | hard | 23 | 5 | -56 | -121 | -0.42 | 39% |
| control | capacity | other | 5 | 3 | +196 | +46 |  | 60% |
| control | capacity | soft | 2 | 2 | -227 | -227 |  | 50% |
| control | caps_rebalance | hard | 4 | 1 | -89 | +21 |  | 50% |
| control | entry | hard | 65 | 7 | -100 | -119 | -0.75 | 45% |
| control | entry | other | 18 | 4 | -95 | -85 |  | 39% |
| control | entry | soft | 20 | 6 | +56 | +97 | +0.41 | 60% |
| control | flip_close | hard | 3 | 2 | +480 | +246 |  | 100% |
| control | flip_close | other | 1 | 1 | -833 | -833 |  | 0% |
| control | horizon | hard | 17 | 4 | -159 | +34 |  | 53% |
| control | horizon | other | 7 | 3 | -370 | -314 |  | 29% |
| control | horizon | soft | 15 | 4 | -158 | -114 |  | 27% |
| control | horizon_extend | hard | 4 | 2 | +10 | +12 |  | 50% |
| control | horizon_extend | soft | 1 | 1 | -361 | -361 |  | 0% |
| control | news_exit | hard | 5 | 4 | -139 | -221 |  | 20% |
| control | news_exit | other | 2 | 2 | -537 | -537 |  | 0% |
| control | news_exit | soft | 2 | 2 | -323 | -323 |  | 50% |
| control | news_increase | hard | 26 | 6 | +31 | +86 | +0.57 | 58% |
| control | news_increase | other | 3 | 2 | +191 | +29 |  | 67% |
| control | news_increase | soft | 4 | 3 | +538 | +685 |  | 75% |
| control | news_reduce | hard | 9 | 5 | -415 | -261 | -1.87 | 22% |
| control | news_reduce | other | 1 | 1 | +639 | +639 |  | 100% |
| control | news_reduce | soft | 1 | 1 | +263 | +263 |  | 100% |
| control | stop | other | 1 | 1 | +529 | +529 |  | 100% |
| live | capacity | hard | 14 | 5 | +303 | +25 | +1.18 | 50% |
| live | capacity | other | 4 | 2 | +305 | +276 |  | 75% |
| live | entry | hard | 49 | 7 | -108 | -118 | -0.73 | 45% |
| live | entry | other | 18 | 4 | -95 | -85 |  | 39% |
| live | entry | soft | 17 | 4 | -8 | +50 |  | 53% |
| live | flip_close | hard | 3 | 3 | +537 | +414 |  | 100% |
| live | flip_close | other | 1 | 1 | -833 | -833 |  | 0% |
| live | horizon | hard | 10 | 4 | -334 | -76 |  | 50% |
| live | horizon | other | 8 | 4 | -391 | -402 |  | 25% |
| live | horizon | soft | 15 | 3 | -228 | -122 |  | 20% |
| live | horizon_extend | hard | 1 | 1 | -89 | -89 |  | 0% |
| live | horizon_extend | soft | 1 | 1 | -361 | -361 |  | 0% |
| live | news_exit | hard | 5 | 4 | -139 | -221 |  | 20% |
| live | news_exit | other | 2 | 2 | -537 | -537 |  | 0% |
| live | news_exit | soft | 1 | 1 | +40 | +40 |  | 100% |
| live | news_increase | hard | 19 | 6 | -25 | -175 | -0.27 | 47% |
| live | news_increase | other | 3 | 2 | +191 | +29 |  | 67% |
| live | news_increase | soft | 3 | 2 | +516 | +766 |  | 67% |
| live | news_reduce | hard | 9 | 5 | -221 | -248 | -1.29 | 33% |
| live | news_reduce | other | 1 | 1 | +639 | +639 |  | 100% |
| live | stop | other | 1 | 1 | +529 | +529 |  | 100% |
| not_entered | a3_soft | soft | 4 | 2 | +245 | +385 |  | 75% |
| not_entered | not_entered | hard | 23 | 4 | -163 | -254 |  | 39% |
| not_entered | not_entered | soft | 1 | 1 | -760 | -760 |  | 0% |
| not_entered | stale | hard | 2 | 2 | -511 | -511 |  | 0% |
| not_entered | stale | other | 4 | 4 | -474 | -317 |  | 50% |
| not_entered | stale | soft | 22 | 7 | -77 | -64 | -0.29 | 41% |

## 10 sessions after the decision

| book | decision | news | n | weeks | mean bp | median bp | t | share > 0 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| control | capacity | hard | 16 | 4 | -334 | -243 |  | 25% |
| control | capacity | other | 5 | 3 | +122 | -243 |  | 20% |
| control | capacity | soft | 1 | 1 | +192 | +192 |  | 100% |
| control | caps_rebalance | hard | 4 | 1 | -538 | -354 |  | 25% |
| control | entry | hard | 52 | 6 | -141 | -82 | -0.82 | 40% |
| control | entry | other | 16 | 3 | -294 | -313 |  | 25% |
| control | entry | soft | 19 | 5 | -29 | -104 | -0.09 | 42% |
| control | flip_close | hard | 3 | 2 | -277 | +17 |  | 67% |
| control | flip_close | other | 1 | 1 | -925 | -925 |  | 0% |
| control | horizon | hard | 13 | 3 | -294 | -86 |  | 31% |
| control | horizon | other | 7 | 3 | -380 | -277 |  | 14% |
| control | horizon | soft | 14 | 3 | -148 | -266 |  | 36% |
| control | horizon_extend | hard | 2 | 1 | -119 | -119 |  | 50% |
| control | horizon_extend | soft | 1 | 1 | +4 | +4 |  | 100% |
| control | news_exit | hard | 3 | 3 | -306 | -83 |  | 0% |
| control | news_exit | other | 2 | 2 | -434 | -434 |  | 0% |
| control | news_exit | soft | 1 | 1 | +435 | +435 |  | 100% |
| control | news_increase | hard | 21 | 4 | -440 | -221 |  | 29% |
| control | news_increase | other | 3 | 2 | +121 | +6 |  | 67% |
| control | news_increase | soft | 3 | 2 | +500 | +243 |  | 67% |
| control | news_reduce | hard | 8 | 4 | -445 | +67 |  | 62% |
| control | news_reduce | other | 1 | 1 | +1189 | +1189 |  | 100% |
| control | stop | other | 1 | 1 | +589 | +589 |  | 100% |
| live | capacity | hard | 9 | 4 | -116 | -327 |  | 33% |
| live | capacity | other | 4 | 2 | +231 | -166 |  | 25% |
| live | entry | hard | 42 | 6 | -111 | -82 | -0.56 | 38% |
| live | entry | other | 16 | 3 | -294 | -313 |  | 25% |
| live | entry | soft | 17 | 4 | -71 | -104 |  | 41% |
| live | flip_close | hard | 3 | 3 | -244 | +17 |  | 67% |
| live | flip_close | other | 1 | 1 | -925 | -925 |  | 0% |
| live | horizon | hard | 8 | 3 | -434 | -110 |  | 38% |
| live | horizon | other | 8 | 4 | -436 | -385 |  | 12% |
| live | horizon | soft | 15 | 3 | -147 | -224 |  | 33% |
| live | horizon_extend | hard | 1 | 1 | -411 | -411 |  | 0% |
| live | horizon_extend | soft | 1 | 1 | +4 | +4 |  | 100% |
| live | news_exit | hard | 3 | 3 | -306 | -83 |  | 0% |
| live | news_exit | other | 2 | 2 | -434 | -434 |  | 0% |
| live | news_exit | soft | 1 | 1 | +435 | +435 |  | 100% |
| live | news_increase | hard | 15 | 4 | -635 | -599 |  | 27% |
| live | news_increase | other | 3 | 2 | +121 | +6 |  | 67% |
| live | news_increase | soft | 3 | 2 | +500 | +243 |  | 67% |
| live | news_reduce | hard | 7 | 4 | -227 | +101 |  | 71% |
| live | news_reduce | other | 1 | 1 | +1189 | +1189 |  | 100% |
| live | stop | other | 1 | 1 | +589 | +589 |  | 100% |
| not_entered | a3_soft | soft | 3 | 1 | +92 | -111 |  | 33% |
| not_entered | not_entered | hard | 17 | 3 | -366 | -320 |  | 41% |
| not_entered | not_entered | soft | 1 | 1 | +219 | +219 |  | 100% |
| not_entered | stale | hard | 2 | 2 | -401 | -401 |  | 0% |
| not_entered | stale | other | 3 | 3 | -1869 | -2444 |  | 0% |
| not_entered | stale | soft | 19 | 6 | +218 | +192 | +0.81 | 68% |

## Does the desk's side match the news-day move?

Share of names whose side equals the sign of the residual move on the news session. Break-even for a follow-through trade: (2a - 1) x mu >= the round-trip cost.

| book | decision | news | agree / n | share | 95% interval |
|---|---|---|---:|---:|---|
| control | entry | hard | 45/71 | 63% | 52%-74% |
| control | entry | other | 12/19 | 63% | 41%-81% |
| control | entry | soft | 15/23 | 65% | 45%-81% |
| live | entry | hard | 33/53 | 62% | 49%-74% |
| live | entry | other | 12/19 | 63% | 41%-81% |
| live | entry | soft | 11/17 | 65% | 41%-83% |
| not_entered | a3_soft | soft | 5/7 | 71% | 36%-92% |
| not_entered | not_entered | hard | 19/27 | 70% | 52%-84% |
| not_entered | not_entered | other | 1/1 | 100% | 21%-100% |
| not_entered | not_entered | soft | 1/1 | 100% | 21%-100% |
| not_entered | stale | hard | 2/4 | 50% | 15%-85% |
| not_entered | stale | other | 3/6 | 50% | 19%-81% |
| not_entered | stale | soft | 16/25 | 64% | 45%-80% |

## Where the result comes from: residual return per session held

Per unit of position, side x (r - beta x r_SPY), bp per lot-session. 'before entry' is one value per lot: the move from the as-of close to the entry close (not P&L). Earnings sessions are split out only where one fell inside a holding (calendar recorded from the 2026-10-28 cohort).

| book | segment | split | lot-sessions | lots | weeks | mean bp | t |
|---|---|---|---:|---:|---:|---:|---:|
| control | before entry | all | 113 | 113 | 8 | -6.4 | -0.18 |
| control | before entry | long | 54 | 54 | 8 | -1.3 | -0.02 |
| control | before entry | short | 59 | 59 | 8 | -11.1 | -0.34 |
| control | 1-3 | all | 302 | 103 | 8 | +6.1 | +0.62 |
| control | 1-3 | long | 145 | 49 | 8 | +16.9 | +0.73 |
| control | 1-3 | short | 157 | 54 | 8 | -3.9 | -0.46 |
| control | 4-15 | all | 254 | 69 | 7 | -34.1 | -1.61 |
| control | 4-15 | earnings | 3 | 3 | 2 | +372.7 |  |
| control | 4-15 | other | 251 | 68 | 7 | -38.9 | -1.80 |
| control | 4-15 | long | 129 | 31 | 7 | -30.2 | -0.94 |
| control | 4-15 | short | 125 | 38 | 7 | -38.1 | -1.54 |
| control | 16+ | all | 10 | 2 | 2 | -75.0 |  |
| control | 16+ | long | 10 | 2 | 2 | -75.0 |  |
| live | before entry | all | 89 | 89 | 8 | -10.4 | -0.23 |
| live | before entry | long | 42 | 42 | 8 | -3.4 | -0.05 |
| live | before entry | short | 47 | 47 | 8 | -16.6 | -0.52 |
| live | 1-3 | all | 245 | 84 | 8 | +2.3 | +0.23 |
| live | 1-3 | long | 115 | 39 | 8 | +8.1 | +0.33 |
| live | 1-3 | short | 130 | 45 | 8 | -2.9 | -0.41 |
| live | 4-15 | all | 308 | 61 | 7 | -34.4 | -1.80 |
| live | 4-15 | earnings | 2 | 2 | 2 | +436.9 |  |
| live | 4-15 | other | 306 | 61 | 7 | -37.5 | -1.93 |
| live | 4-15 | long | 154 | 26 | 7 | -36.0 | -1.33 |
| live | 4-15 | short | 154 | 35 | 7 | -32.9 | -1.01 |
| live | 16+ | all | 30 | 6 | 3 | -12.5 |  |
| live | 16+ | long | 20 | 4 | 3 | -11.1 |  |
| live | 16+ | short | 10 | 2 | 2 | -15.4 |  |

## Entries by structural label and 'priced in' at entry

7B Amendment 2 exempts structural lots from B1, so a structural name enters even when its move since the news is already the typical full reaction (p >= 1). Measurement only, before any rule change.

| book | structural | priced in | h | n | weeks | mean bp | t | share > 0 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| control | False | False | 5 | 14 | 3 | +347 |  | 64% |
| control | False | False | 10 | 8 | 2 | +367 |  | 62% |
| control | False | True | 5 | 10 | 3 | -4 |  | 40% |
| control | False | True | 10 | 6 | 2 | +14 |  | 33% |
| control | True | False | 5 | 8 | 3 | +63 |  | 62% |
| control | True | False | 10 | 6 | 2 | -26 |  | 33% |
| control | True | True | 5 | 10 | 3 | +46 |  | 50% |
| control | True | True | 10 | 6 | 2 | +303 |  | 67% |
| live | False | False | 5 | 7 | 3 | +614 |  | 71% |
| live | False | False | 10 | 5 | 2 | +542 |  | 60% |
| live | False | True | 5 | 7 | 3 | +11 |  | 43% |
| live | False | True | 10 | 4 | 2 | +129 |  | 50% |
| live | True | False | 5 | 5 | 3 | +39 |  | 60% |
| live | True | False | 10 | 4 | 2 | -67 |  | 25% |
| live | True | True | 5 | 6 | 2 | -82 |  | 33% |
| live | True | True | 10 | 3 | 1 | +330 |  | 33% |

Rank IC of the desk's weights vs the next 5 sessions' residual return: mean -0.091 over 7 cohorts.
Rank IC of the desk's weights vs the next 10 sessions' residual return: mean -0.175 over 6 cohorts.
