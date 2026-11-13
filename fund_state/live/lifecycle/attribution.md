# Decision ledger: what followed each decision

Updated 2026-11-13T01:12:44+00:00. Reporting only. y = the position side x the stock's residual return after the decision's close; for exits, y > 0 means the stock kept moving the position's way after we left. t is clustered by week. Small samples: read n before the mean.

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
| control | horizon | hard | 9 | 2 | -444 | -187 |  | 33% |
| control | horizon | other | 7 | 3 | -370 | -314 |  | 29% |
| control | horizon | soft | 14 | 3 | -202 | -118 |  | 21% |
| control | horizon_extend | soft | 1 | 1 | -361 | -361 |  | 0% |
| control | news_exit | hard | 2 | 2 | -448 | -448 |  | 0% |
| control | news_exit | other | 2 | 2 | -537 | -537 |  | 0% |
| control | news_exit | soft | 1 | 1 | +40 | +40 |  | 100% |
| control | news_increase | hard | 15 | 4 | -35 | +143 |  | 67% |
| control | news_increase | other | 3 | 2 | +191 | +29 |  | 67% |
| control | news_increase | soft | 3 | 2 | +516 | +766 |  | 67% |
| control | news_reduce | hard | 6 | 3 | -365 | -323 |  | 33% |
| control | news_reduce | other | 1 | 1 | +639 | +639 |  | 100% |
| control | stop | other | 1 | 1 | +529 | +529 |  | 100% |
| live | capacity | hard | 7 | 3 | +612 | +506 |  | 57% |
| live | capacity | other | 4 | 2 | +305 | +276 |  | 75% |
| live | entry | hard | 36 | 5 | -151 | -120 | -0.75 | 42% |
| live | entry | other | 16 | 3 | -152 | -85 |  | 38% |
| live | entry | soft | 17 | 4 | -8 | +50 |  | 53% |
| live | flip_close | hard | 2 | 2 | +697 | +697 |  | 100% |
| live | flip_close | other | 1 | 1 | -833 | -833 |  | 0% |
| live | horizon | hard | 6 | 2 | -631 | -307 |  | 33% |
| live | horizon | other | 8 | 4 | -391 | -402 |  | 25% |
| live | horizon | soft | 15 | 3 | -228 | -122 |  | 20% |
| live | horizon_extend | soft | 1 | 1 | -361 | -361 |  | 0% |
| live | news_exit | hard | 2 | 2 | -448 | -448 |  | 0% |
| live | news_exit | other | 2 | 2 | -537 | -537 |  | 0% |
| live | news_exit | soft | 1 | 1 | +40 | +40 |  | 100% |
| live | news_increase | hard | 12 | 4 | -86 | +114 |  | 58% |
| live | news_increase | other | 3 | 2 | +191 | +29 |  | 67% |
| live | news_increase | soft | 3 | 2 | +516 | +766 |  | 67% |
| live | news_reduce | hard | 5 | 3 | -195 | -261 |  | 40% |
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
| control | horizon | hard | 2 | 1 | -2077 | -2077 |  | 0% |
| control | horizon | other | 7 | 3 | -380 | -277 |  | 14% |
| control | horizon | soft | 14 | 3 | -148 | -266 |  | 36% |
| control | horizon_extend | soft | 1 | 1 | +4 | +4 |  | 100% |
| control | news_exit | hard | 1 | 1 | -83 | -83 |  | 0% |
| control | news_exit | other | 2 | 2 | -434 | -434 |  | 0% |
| control | news_exit | soft | 1 | 1 | +435 | +435 |  | 100% |
| control | news_increase | hard | 9 | 3 | -1120 | -857 |  | 0% |
| control | news_increase | other | 3 | 2 | +121 | +6 |  | 67% |
| control | news_increase | soft | 3 | 2 | +500 | +243 |  | 67% |
| control | news_reduce | hard | 2 | 2 | -506 | -506 |  | 50% |
| control | news_reduce | other | 1 | 1 | +1189 | +1189 |  | 100% |
| control | stop | other | 1 | 1 | +589 | +589 |  | 100% |
| live | capacity | hard | 5 | 2 | -656 | -388 |  | 20% |
| live | capacity | other | 4 | 2 | +231 | -166 |  | 25% |
| live | entry | hard | 26 | 4 | -330 | -211 |  | 35% |
| live | entry | other | 16 | 3 | -294 | -313 |  | 25% |
| live | entry | soft | 17 | 4 | -71 | -104 |  | 41% |
| live | flip_close | hard | 1 | 1 | -1208 | -1208 |  | 0% |
| live | flip_close | other | 1 | 1 | -925 | -925 |  | 0% |
| live | horizon | hard | 2 | 1 | -2077 | -2077 |  | 0% |
| live | horizon | other | 7 | 3 | -380 | -277 |  | 14% |
| live | horizon | soft | 14 | 3 | -148 | -266 |  | 36% |
| live | horizon_extend | soft | 1 | 1 | +4 | +4 |  | 100% |
| live | news_exit | hard | 1 | 1 | -83 | -83 |  | 0% |
| live | news_exit | other | 2 | 2 | -434 | -434 |  | 0% |
| live | news_exit | soft | 1 | 1 | +435 | +435 |  | 100% |
| live | news_increase | hard | 9 | 3 | -1120 | -857 |  | 0% |
| live | news_increase | other | 3 | 2 | +121 | +6 |  | 67% |
| live | news_increase | soft | 3 | 2 | +500 | +243 |  | 67% |
| live | news_reduce | hard | 2 | 2 | -506 | -506 |  | 50% |
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
| control | 1-3 | all | 213 | 73 | 6 | +5.9 | +0.45 |
| control | 1-3 | long | 103 | 35 | 6 | +13.5 | +0.46 |
| control | 1-3 | short | 110 | 38 | 6 | -1.2 | -0.29 |
| control | 4-15 | all | 178 | 50 | 5 | -49.1 | -1.81 |
| control | 4-15 | earnings | 1 | 1 | 1 | +908.3 |  |
| control | 4-15 | other | 177 | 50 | 5 | -54.5 | -1.97 |
| control | 4-15 | long | 93 | 23 | 5 | -39.8 | -0.89 |
| control | 4-15 | short | 85 | 27 | 5 | -59.2 | -2.73 |
| live | before entry | all | 75 | 75 | 6 | -36.2 | -0.74 |
| live | before entry | long | 35 | 35 | 6 | -34.3 | -0.45 |
| live | before entry | short | 40 | 40 | 6 | -37.9 | -1.15 |
| live | 1-3 | all | 201 | 69 | 6 | +0.8 | +0.07 |
| live | 1-3 | long | 94 | 32 | 6 | +5.4 | +0.21 |
| live | 1-3 | short | 107 | 37 | 6 | -3.3 | -0.69 |
| live | 4-15 | all | 191 | 50 | 5 | -44.5 | -1.80 |
| live | 4-15 | earnings | 1 | 1 | 1 | +908.3 |  |
| live | 4-15 | other | 190 | 50 | 5 | -49.6 | -2.02 |
| live | 4-15 | long | 99 | 21 | 5 | -36.1 | -0.83 |
| live | 4-15 | short | 92 | 29 | 5 | -53.6 | -2.75 |

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
