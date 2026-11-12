# Branch D (trees, ensembles, stacking): interim report

4 configurations scored so far (2013-2019 walk-forward, 3 seeds); combinations still running.

| name | IC | t | positive years | decile net %/yr |
|---|---|---|---|---|
| hgb (boosted trees, rank target) | 0.0216 | 2.30 | 6/7 | +0.4 |
| et (extra trees, leaf 1000) | 0.0211 | 2.00 | 6/7 | +0.9 |
| rf (random forest, leaf 1000) | 0.0206 | 2.13 | 6/7 | +1.5 |
| ridge on the same 27 features | 0.0181 | 1.64 | 6/7 | -0.4 |

Interim best: hgb (model.py). All four are within noise of each other and of MASTER (0.0125); 2016 negative for all.
