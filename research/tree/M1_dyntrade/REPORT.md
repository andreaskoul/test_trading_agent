# Branch M1: dynamic trading with costs (Garleanu-Pedersen 2013)

*Saved by the coordinating session from the agent's hand-back (its file write was refused).*

Portfolio rules on frozen scores: MASTER 5-day and D's 4-horizon trees (`base_hgb_multihorizon.npy`). 2013-2019,
353 weeks; 9 constructions x 2 bases = 18 rows in `RESULTS.jsonl`. Own simulator reproduces harness.decile_net
(-1.72 vs -1.73 %/yr MASTER; 1.08 vs 1.08 trees). Paired = weekly net minus the decile book's, %/yr (t, unadjusted).

| construction | MASTER net %/yr | Sharpe | turn/wk | paired (t) | trees net %/yr | Sharpe | turn/wk | paired (t) |
|---|---|---|---|---|---|---|---|---|
| deciles (phase 1) | -1.72 | -0.26 | 53% | - | +1.08 | 0.16 | 45% | - |
| rank smoothing, half-life 1 wk | -1.37 | -0.19 | 32% | +0.35 (0.3) | +2.37 | 0.35 | 24% | +1.30 (1.5) |
| no-trade band 10/20% (model.py) | -0.23 | -0.04 | 38% | +1.49 (2.5) | +2.29 | 0.36 | 26% | +1.21 (2.3) |
| mean-variance aim, diagonal | -0.61 | -0.15 | 39% | +1.11 (0.9) | +1.08 | 0.24 | 29% | 0.00 (0.0) |
| GP to decile aim, rate "ref" | -1.51 | -0.26 | 18% | +0.21 (0.2) | +1.60 | 0.25 | 23% | +0.52 (0.8) |
| GP to mean-variance diagonal, "ref" | -0.25 | -0.06 | 12% | +1.47 (0.9) | +1.77 | 0.38 | 13% | +0.69 (0.6) |
| GP to mean-variance Ledoit-Wolf, "ref" | -1.28 | -0.71 | 14% | n/c | +0.27 | 0.18 | 18% | n/c |
| GP to decile aim, "fixed point" | +0.36 | 0.06 | 5% | +2.08 (1.0) | +1.59 | 0.26 | 12% | +0.51 (0.5) |
| GP to mean-variance diagonal, "fixed point" | +0.79 | 0.16 | 3% | +2.51 (1.1) | +2.04 | 0.43 | 7% | +0.96 (0.8) |

Trade rate tau = (-r + sqrt(r^2 + 4r))/2, r = risk aversion / cost; aim scaled by g = 1/(1 + phi tau / r), phi = 1 -
weekly rank autocorrelation (MASTER 0.32, trees 0.19); re-estimated weekly on past weeks; IC shrunk to a 0.02 prior.

* Only the no-trade band beats deciles on both bases with paired t above 2 (one fixed width, best of 9: discount).
* Garleanu-Pedersen gains +0.2 to +2.5 %/yr, none with t above 1.2. Ledoit-Wolf mean-variance aims lose.
* MASTER's gross decile spread on 2013-2019 is only 1.03 %/yr, so no construction makes it positive net by more than
  noise. Its positive GP rows come from trading almost nothing in 2017-19.
* Carry the band and GP mean-variance diagonal "ref" into the S&P 400 confirmation as construction rules.
