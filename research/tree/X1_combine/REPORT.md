# Branch X1: combine the round-1 winners

*Written by the coordinating session from the agent's hand-back (the agent's file write was refused by its harness).*

10 configurations scored (plus one re-run of the best from model.py), development sample 2013-2019, walk-forward,
3 seeds, 353 weeks. Standard error of a mean IC is about 0.01: every difference here is inside noise.

| # | configuration | IC | t | yrs>0 | decile net %/yr | Sharpe |
|---|---|---:|---:|---:|---:|---:|
| 1a | D trees, D inputs, 4 horizons (baseline) | 0.0236 | 2.41 | 6/7 | +1.0 | 0.15 |
| 1b | C Fama-MacBeth ridge (baseline) | 0.0209 | 2.29 | 6/7 | -0.3 | -0.04 |
| 2 | D trees on C's features, 5 sessions | 0.0088 | 0.89 | 5/7 | -2.7 | -0.39 |
| 3 | trees + ridge + MLP on C's features | 0.0203 | 2.12 | 6/7 | -0.7 | -0.11 |
| 4 | as 3, each learner on 4 horizons | 0.0243 | 2.53 | 6/7 | -0.3 | -0.04 |
| 5 | 4 + panic overlay | 0.0261 | 2.74 | 6/7 | +0.7 | 0.12 |
| 6 | 1a + 1b, equal weight | 0.0254 | 2.63 | 6/7 | +0.3 | 0.05 |
| 6p | 6 + panic overlay | 0.0277 | 2.90 | 7/7 | +1.3 | 0.20 |
| 7p | 6p with the ridge on 4 horizons | 0.0272 | 2.84 | 6/7 | +1.3 | 0.20 |
| 8p | 7p + MLP on C's features, 4 horizons | 0.0282 | 2.91 | 6/7 | +1.1 | 0.18 |

* The agent preferred 6p as simpler; the registered finalist rule (highest t) selects 8p.
* The panic overlay acts in 17 of 353 weeks, mostly 2016; branch E found it on this sample, so its gain is in-sample.
* Trees do badly on C's features (0.0088): the tree result depends on D's inputs.
* Multi-horizon targets helped the three-learner average (+0.004); the MLP adds nothing measurable.
* Net of 5 bp a side the decile spread is at most +1.3% a year (Sharpe 0.20).
