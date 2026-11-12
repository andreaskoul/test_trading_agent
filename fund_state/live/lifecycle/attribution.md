# Decision ledger: what followed each decision

Updated 2026-11-12T01:12:11+00:00. Reporting only. y = the position side x the stock's residual return after the decision's close; for exits, y > 0 means the stock kept moving the position's way after we left. t is clustered by week. Small samples: read n before the mean.

## 5 sessions after the decision

| book | decision | news | n | weeks | mean bp | median bp | t | share > 0 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| control | capacity | hard | 5 | 2 | +380 | -149 |  | 40% |
| control | capacity | other | 5 | 3 | +196 | +46 |  | 60% |
| control | capacity | soft | 1 | 1 | -746 | -746 |  | 0% |
| control | entry | hard | 28 | 4 | -369 | -405 |  | 36% |
| control | entry | other | 16 | 3 | -152 | -85 |  | 38% |
| control | entry | soft | 17 | 4 | -8 | +50 |  | 53% |
| control | flip_close | hard | 1 | 1 | +979 | +979 |  | 100% |
| control | flip_close | other | 1 | 1 | -833 | -833 |  | 0% |
| control | horizon | hard | 9 | 2 | -444 | -187 |  | 33% |
| control | horizon | other | 7 | 3 | -370 | -314 |  | 29% |
| control | horizon | soft | 14 | 3 | -202 | -118 |  | 21% |
| control | horizon_extend | soft | 1 | 1 | -361 | -361 |  | 0% |
| control | news_exit | hard | 1 | 1 | -362 | -362 |  | 0% |
| control | news_exit | other | 2 | 2 | -537 | -537 |  | 0% |
| control | news_exit | soft | 1 | 1 | +40 | +40 |  | 100% |
| control | news_increase | hard | 15 | 4 | -35 | +143 |  | 67% |
| control | news_increase | other | 3 | 2 | +191 | +29 |  | 67% |
| control | news_increase | soft | 3 | 2 | +516 | +766 |  | 67% |
| control | news_reduce | hard | 6 | 3 | -365 | -323 |  | 33% |
| control | news_reduce | other | 1 | 1 | +639 | +639 |  | 100% |
| control | stop | other | 1 | 1 | +529 | +529 |  | 100% |
| live | capacity | hard | 5 | 2 | +380 | -149 |  | 40% |
| live | capacity | other | 4 | 2 | +305 | +276 |  | 75% |
| live | entry | hard | 26 | 4 | -332 | -322 |  | 38% |
| live | entry | other | 16 | 3 | -152 | -85 |  | 38% |
| live | entry | soft | 17 | 4 | -8 | +50 |  | 53% |
| live | flip_close | hard | 1 | 1 | +979 | +979 |  | 100% |
| live | flip_close | other | 1 | 1 | -833 | -833 |  | 0% |
| live | horizon | hard | 6 | 2 | -631 | -307 |  | 33% |
| live | horizon | other | 8 | 4 | -391 | -402 |  | 25% |
| live | horizon | soft | 15 | 3 | -228 | -122 |  | 20% |
| live | horizon_extend | soft | 1 | 1 | -361 | -361 |  | 0% |
| live | news_exit | hard | 1 | 1 | -362 | -362 |  | 0% |
| live | news_exit | other | 2 | 2 | -537 | -537 |  | 0% |
| live | news_exit | soft | 1 | 1 | +40 | +40 |  | 100% |
| live | news_increase | hard | 12 | 4 | -86 | +114 |  | 58% |
| live | news_increase | other | 3 | 2 | +191 | +29 |  | 67% |
| live | news_increase | soft | 3 | 2 | +516 | +766 |  | 67% |
| live | news_reduce | hard | 5 | 3 | -195 | -261 |  | 40% |
| live | news_reduce | other | 1 | 1 | +639 | +639 |  | 100% |
| live | stop | other | 1 | 1 | +529 | +529 |  | 100% |
| not_entered | not_entered | hard | 3 | 1 | -840 | -833 |  | 0% |
| not_entered | not_entered | soft | 1 | 1 | -760 | -760 |  | 0% |
| not_entered | stale | hard | 1 | 1 | -523 | -523 |  | 0% |
| not_entered | stale | other | 2 | 2 | -1293 | -1293 |  | 0% |
| not_entered | stale | soft | 14 | 4 | +260 | +70 |  | 57% |

## 10 sessions after the decision

| book | decision | news | n | weeks | mean bp | median bp | t | share > 0 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| control | capacity | hard | 4 | 1 | -886 | -876 |  | 0% |
| control | capacity | other | 4 | 2 | +231 | -166 |  | 25% |
| control | entry | hard | 14 | 3 | -613 | -456 |  | 21% |
| control | entry | other | 16 | 3 | -294 | -313 |  | 25% |
| control | entry | soft | 16 | 3 | -84 | -122 |  | 38% |
| control | flip_close | hard | 1 | 1 | -1208 | -1208 |  | 0% |
| control | flip_close | other | 1 | 1 | -925 | -925 |  | 0% |
| control | horizon | hard | 2 | 1 | -2077 | -2077 |  | 0% |
| control | horizon | other | 6 | 2 | -223 | -233 |  | 17% |
| control | horizon | soft | 14 | 3 | -148 | -266 |  | 36% |
| control | horizon_extend | soft | 1 | 1 | +4 | +4 |  | 100% |
| control | news_exit | hard | 1 | 1 | -83 | -83 |  | 0% |
| control | news_exit | other | 1 | 1 | -821 | -821 |  | 0% |
| control | news_exit | soft | 1 | 1 | +435 | +435 |  | 100% |
| control | news_increase | hard | 9 | 3 | -1120 | -857 |  | 0% |
| control | news_increase | other | 3 | 2 | +121 | +6 |  | 67% |
| control | news_increase | soft | 3 | 2 | +500 | +243 |  | 67% |
| control | news_reduce | hard | 2 | 2 | -506 | -506 |  | 50% |
| control | news_reduce | other | 1 | 1 | +1189 | +1189 |  | 100% |
| control | stop | other | 1 | 1 | +589 | +589 |  | 100% |
| live | capacity | hard | 4 | 1 | -886 | -876 |  | 0% |
| live | capacity | other | 4 | 2 | +231 | -166 |  | 25% |
| live | entry | hard | 14 | 3 | -613 | -456 |  | 21% |
| live | entry | other | 16 | 3 | -294 | -313 |  | 25% |
| live | entry | soft | 16 | 3 | -84 | -122 |  | 38% |
| live | flip_close | hard | 1 | 1 | -1208 | -1208 |  | 0% |
| live | flip_close | other | 1 | 1 | -925 | -925 |  | 0% |
| live | horizon | hard | 2 | 1 | -2077 | -2077 |  | 0% |
| live | horizon | other | 6 | 2 | -223 | -233 |  | 17% |
| live | horizon | soft | 14 | 3 | -148 | -266 |  | 36% |
| live | horizon_extend | soft | 1 | 1 | +4 | +4 |  | 100% |
| live | news_exit | hard | 1 | 1 | -83 | -83 |  | 0% |
| live | news_exit | other | 1 | 1 | -821 | -821 |  | 0% |
| live | news_exit | soft | 1 | 1 | +435 | +435 |  | 100% |
| live | news_increase | hard | 9 | 3 | -1120 | -857 |  | 0% |
| live | news_increase | other | 3 | 2 | +121 | +6 |  | 67% |
| live | news_increase | soft | 3 | 2 | +500 | +243 |  | 67% |
| live | news_reduce | hard | 2 | 2 | -506 | -506 |  | 50% |
| live | news_reduce | other | 1 | 1 | +1189 | +1189 |  | 100% |
| live | stop | other | 1 | 1 | +589 | +589 |  | 100% |
| not_entered | not_entered | soft | 1 | 1 | +219 | +219 |  | 100% |
| not_entered | stale | other | 2 | 2 | -2675 | -2675 |  | 0% |
| not_entered | stale | soft | 11 | 3 | +460 | +296 |  | 73% |

## Does the desk's side match the news-day move?

Share of names whose side equals the sign of the residual move on the news session. Break-even for a follow-through trade: (2a - 1) x mu >= the round-trip cost.

| book | decision | news | agree / n | share | 95% interval |
|---|---|---|---:|---:|---|
| control | entry | hard | 25/40 | 62% | 47%-76% |
| control | entry | other | 10/16 | 62% | 39%-82% |
| control | entry | soft | 11/17 | 65% | 41%-83% |
| live | entry | hard | 23/36 | 64% | 48%-78% |
| live | entry | other | 10/16 | 62% | 39%-82% |
| live | entry | soft | 11/17 | 65% | 41%-83% |
| not_entered | a3_soft | soft | 2/3 | 67% | 21%-94% |
| not_entered | not_entered | hard | 13/23 | 57% | 37%-74% |
| not_entered | not_entered | soft | 1/1 | 100% | 21%-100% |
| not_entered | stale | hard | 1/2 | 50% | 9%-91% |
| not_entered | stale | other | 1/3 | 33% | 6%-79% |
| not_entered | stale | soft | 10/19 | 53% | 32%-73% |

## Where the result comes from: residual return per session held

Per unit of position, side x (r - beta x r_SPY), bp per lot-session. 'before entry' is one value per lot: the move from the as-of close to the entry close (not P&L). Earnings sessions are split out only where one fell inside a holding (calendar recorded from the 2026-10-28 cohort).

| book | segment | split | lot-sessions | lots | weeks | mean bp | t |
|---|---|---|---:|---:|---:|---:|---:|
| control | before entry | all | 73 | 73 | 5 | -43.4 | -0.87 |
| control | before entry | long | 35 | 35 | 5 | -25.7 | -0.33 |
| control | before entry | short | 38 | 38 | 5 | -59.8 | -1.98 |
| control | 1-3 | all | 213 | 73 | 6 | +5.9 | +0.45 |
| control | 1-3 | long | 103 | 35 | 6 | +13.5 | +0.46 |
| control | 1-3 | short | 110 | 38 | 6 | -1.2 | -0.29 |
| control | 4-15 | all | 161 | 50 | 5 | -56.3 | -2.05 |
| control | 4-15 | earnings | 1 | 1 | 1 | +908.3 |  |
| control | 4-15 | other | 160 | 50 | 5 | -62.3 | -2.27 |
| control | 4-15 | long | 84 | 23 | 5 | -42.0 | -0.85 |
| control | 4-15 | short | 77 | 27 | 5 | -72.0 | -4.60 |
| live | before entry | all | 69 | 69 | 5 | -39.5 | -0.73 |
| live | before entry | long | 32 | 32 | 5 | -24.7 | -0.29 |
| live | before entry | short | 37 | 37 | 5 | -52.2 | -1.60 |
| live | 1-3 | all | 201 | 69 | 6 | +0.8 | +0.07 |
| live | 1-3 | long | 94 | 32 | 6 | +5.4 | +0.21 |
| live | 1-3 | short | 107 | 37 | 6 | -3.3 | -0.69 |
| live | 4-15 | all | 174 | 50 | 5 | -50.0 | -1.91 |
| live | 4-15 | earnings | 1 | 1 | 1 | +908.3 |  |
| live | 4-15 | other | 173 | 50 | 5 | -55.5 | -2.19 |
| live | 4-15 | long | 91 | 21 | 5 | -34.2 | -0.71 |
| live | 4-15 | short | 83 | 29 | 5 | -67.3 | -2.80 |

## Entries by structural label and 'priced in' at entry

7B Amendment 2 exempts structural lots from B1, so a structural name enters even when its move since the news is already the typical full reaction (p >= 1). Measurement only, before any rule change.

| book | structural | priced in | h | n | weeks | mean bp | t | share > 0 |
|---|---|---|---:|---:|---:|---:|---:|---:|

Rank IC of the desk's weights vs the next 5 sessions' residual return: mean -0.195 over 4 cohorts.
Rank IC of the desk's weights vs the next 10 sessions' residual return: mean -0.337 over 3 cohorts.
