# How far the validated pieces go when sized greedily (descriptive)

*2026-11-10. Owner: "aim much higher, be greedy." This is arithmetic on predictions that were already scored
(`research/quant_trials`, MASTER 5-day, the one model of twelve that passed its pre-registered S&P 500 read). No new
hypothesis is tested and nothing here is a confirmation. Same simulator as `strategies.py` on the
`research/quant-transformers` branch: weekly Thursday decisions, top and bottom deciles, beta-hedged, on top of the
1.3×/0.7× 200-session core, margin at the 3-month bill + 2.43%. Only the book's gross and the cost per side vary.*

S0 = plain deciles (the least chosen variant). 2013–2025, S&P buy and hold 14.6% a year.

| Book gross | Cost a side | % a year | Volatility | Sharpe | Worst fall | 2013–19 % a year (S&P 14.2) | 2020–25 % a year (S&P 15.0) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 (core only) | 5 bp | 15.6 | 17.1 | 0.88 | −29% | 15.1 | 16.1 |
| 0.6 (fits the 1.9 limit) | 5 bp | 17.6 | 18.5 | 0.92 | −30% | 14.2 | 21.7 |
| 1.0 | 5 bp | 18.8 | 20.1 | 0.91 | −31% | 13.5 | 25.3 |
| 2.0 | 5 bp | 21.2 | 26.0 | 0.83 | −32% | 11.4 | 33.8 |
| 3.0 | 5 bp | 22.8 | 33.2 | 0.74 | −37% | 8.9 | 41.3 |
| 0.6 | 1 bp | 19.4 | 18.5 | 1.01 | −30% | 15.8 | 23.7 |
| 1.0 | 1 bp | 21.7 | 20.1 | 1.04 | −30% | 16.1 | 28.7 |
| 2.0 | 1 bp | 27.3 | 26.0 | 1.02 | −31% | 16.6 | 41.0 |
| 3.0 | 1 bp | 32.0 | 33.2 | 0.97 | −33% | 16.6 | 52.8 |

The book alone has a Sharpe of 0.38 at 5 bp (−0.16 in 2013–19, 0.77 in 2020–25) and 0.66 at 1 bp.

## Reading

* **Sharpe peaks at a book gross of about 1 and falls beyond it.** More gross buys return with volatility, not
  efficiency.
* **Everything above the core depends on two things that are not established:** the real cost per side (the fund's
  measured paper cost is 0.9 bp, but paper fills carry no market impact), and whether 2020–25 repeats. At 5 bp the
  book lost money in 2013–19, and at a gross of 3 the fund would have earned 8.9% a year against the S&P's 14.2%.
* A book gross above 0.6 does not fit under the account's 1.9 limit with the core at 1.3. It needs either a core held
  with less capital or a different margin regime. Both are the owner's policy.
* The forward paper book of this model has run since 2026-10-29; its first checkpoint is at 26 weeks.

## Reproduce

From the `quant-tf` worktree: `strategies.backtest(d, pred_master_h5, 5, "S0", 2013..2025, rf, vol)` with
`GROSS_SIDE` = half the book gross and `COST` = the cost per side.
