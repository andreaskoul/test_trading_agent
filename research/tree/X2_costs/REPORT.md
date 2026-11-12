# Branch X2: return after trading costs

Base: branch D's boosted trees (27 price features; code copied into `lib.py`). 11 configurations scored, all logged in
`RESULTS.jsonl` (2013-2019 walk-forward, 3 seeds). Net = top-minus-bottom decile spread, 0.5 a side, after 5 bp a side
on names replaced. Gross, cost and turnover are diagnostics from `run.py` with the harness's own definitions.

| configuration | IC | t | yrs + | gross %/yr | cost %/yr | replaced /wk | net %/yr | net Sharpe |
|---|---|---|---|---|---|---|---|---|
| c1b base, 5-session target only | 0.0216 | 2.30 | 6/7 | 2.75 | 2.37 | 46% | +0.38 | 0.05 |
| c1 base, 3/5/10/20-session targets (D's best, reproduced) | 0.0236 | 2.41 | 6/7 | 3.36 | 2.33 | 45% | +1.04 | 0.15 |
| **c2a base + rank smoothing, half-life 1 week** | 0.0234 | 2.31 | 6/7 | 4.01 | 1.27 | 24% | **+2.74** | **0.40** |
| c9 base + smoothing, half-life 2 weeks | 0.0220 | 2.12 | 6/7 | 2.55 | 0.86 | 17% | +1.68 | 0.25 |
| c2b base + smoothing, half-life 3 weeks | 0.0211 | 2.00 | 6/7 | 2.47 | 0.68 | 13% | +1.79 | 0.27 |
| c3 10- and 20-session targets only | 0.0213 | 2.39 | 6/7 | 3.31 | 1.87 | 36% | +1.44 | 0.23 |
| c4 blend 5/10/20, weights 1:2:3 | 0.0217 | 2.39 | 6/7 | 2.77 | 1.86 | 36% | +0.90 | 0.14 |
| c5 5/10/20 without 1- and 5-session reversal features | 0.0214 | 2.36 | 6/7 | 3.17 | 1.97 | 38% | +1.21 | 0.18 |
| c6 5-session target charged 10 bp on a decile change | 0.0222 | 2.28 | 6/7 | 4.08 | 2.31 | 44% | +1.78 | 0.25 |
| c7 c2a + no-trade band (5 rank points) | 0.0232 | 2.28 | 6/7 | 2.91 | 0.97 | 19% | +1.94 | 0.29 |
| c8 c3 + smoothing, half-life 1 week | 0.0209 | 2.26 | 6/7 | 2.77 | 1.08 | 21% | +1.68 | 0.27 |

**Best (model.py): c2a.** Equal-weight ranks of the 3/5/10/20-session models, then each stock's rank exponentially
smoothed over the current and 12 preceding Thursdays, half-life 1 week. 2016 is the negative IC year in every row.

**What the evidence supports.**
* Turnover is controllable. Smoothing or a band cuts the share of each decile replaced from 45% to 13-24% a week,
  so costs fall from 2.3%/yr to 0.7-1.3%/yr. IC is unchanged at half-life 1 and falls about 0.002 at half-life 3.
* Costs took 69% of the gross spread in the base (2.33 of 3.36) and take 32% in c2a (1.27 of 4.01); across the five
  smoothed or banded rows they take 28-39%.
* Slower targets and dropping fast features cut turnover only to 36-38%: the model itself changes little; the
  post-processing of scores does the work. The cost-charged target (c6) leaves turnover at 44%: 10 bp is too small.

**Noise, stated plainly.**
* The standard error of a net Sharpe over 7 years is about 0.38. The best row (0.40) is one standard error from zero,
  and no row differs from any other by more than one standard error. It is also the best of 11.
* c2a's gross spread (4.01) is above the base's (3.36); smoothing has no reason to raise a gross spread, and its
  neighbours (half-life 2, the band) show 2.5-2.9. Part of c2a's lead is luck. c6 shows the scale: a near no-op change
  to the target moved the gross spread by 1.3%/yr.
* The robust saving is the cost line, about 1.0-1.6%/yr. A fair expectation for a smoothed book is a net spread of
  1.5-2%/yr at Sharpe 0.25-0.3 on this sample, not 0.40. That is not a tradeable return on its own.
* The 12 lookback weeks before each year's first prediction are training rows (scored in-sample; no future data).
