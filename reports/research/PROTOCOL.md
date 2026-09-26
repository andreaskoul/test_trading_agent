# Research protocol: is there a tradable signal before we retrain the RL?

Written and committed **before** any of the results below exist. Anything
not listed here that gets run later is reported as exploratory and does not
count towards a pass.

## Question

With the project's 22 features, on 60m gold, under realistic execution
(`src/env/fills.py`, bracket fills, the cron's cost model), does any simple
model beat a coin flip out of sample? If nothing simple does, retraining
168 PPO/GRPO policies on the same inputs is not justified. The RL has to
beat the best baseline on the same test, not zero.

## Data (causal rebuild)

* Features from `build_features`, 22-column extended schema,
  warmup = z-window = 1638 bars.
* Macro closes lagged one day to availability (VIX, DGS10, broad dollar
  from FRED; S&P 500 **daily closes** from Yahoo, because the old cache
  used monthly *averages* stamped on the 1st of the month for 2012-2015,
  which is up to a month of look-ahead).
* Regime posterior: HMM forward filter, not the smoother.
* Volatility quantile for costs: expanding rank.
* OHLC passed through for fills.

## Splits

| name | span | role |
|---|---|---|
| dev | 2012-05 → 2022-03, XAUUSD spot | model fitting, purged 8-fold CV (contiguous folds, purge = horizon + 32 bars each side) |
| holdout | 2023-01 → 2026-03-31, GC futures | one evaluation per model, refit on all of dev |
| live | 2026-04-01 → | untouched here. Already looked at once to diagnose the pipeline, so it is only used as a final single check for a model that passes holdout |

## Target and execution

For every bar *i* and side *d* in {long, short}: net return of a bracket
trade signalled on the close of *i* (entry `open[i+1]`, TP 1.5·ATR,
SL 0.75·ATR, stop first on ties, gaps at the open), cost = 2·0.5 bp spread
+ 2·0.3 bp·max(0.1, vol_q). Two horizons are pre-registered:

* **H = 4 bars** (the current setup)
* **H = 26 bars** (≈ one trading day; the H = 4 setup times out on half of
  all trades, so most of the cost is paid on noise)

## Models (the trial set, N = 12)

Each model outputs a side (long / short / flat) per bar. It is traded
sequentially, one position at a time, entries only when flat.

| id | rule | fitted on |
|---|---|---|
| tod | per UTC hour, the side with the higher mean net outcome in the fitting data; flat if that mean ≤ 0 | dev fold |
| mom | side = sign(ret_50) | none |
| rev | side = −sign(ret_5) | none |
| trend | side = sign(ema_200_dist) | none |
| ridge | ridge (α = 10) predicts long and short net outcome; take the larger if > 0 | dev fold |
| gbm | HistGradientBoosting (max_depth 3, 200 iters, lr 0.05) same targets | dev fold |

6 rules × 2 horizons = **12 trials**. No hyperparameter search; these values
are fixed now. Benchmarks (not trials): coin flip, always long, always short.

## Metrics

1. **Predictability**, independent of any trading rule: monthly Spearman IC
   between model score (predicted long − short) and realised long − short
   gross outcome. Mean IC, HAC t over months.
2. **Tradability**: per-trade net mean (bp), HAC t (5 lags), per-trade
   Sharpe, PSR(0), DSR with N = 12 and the cross-trial Sharpe variance, and
   the difference versus the coin flip under the same rules.

## Decision rule

A model **passes** only if, on holdout, all four hold: net mean > 0,
HAC t > 2, DSR > 0.95, IC HAC t > 2.

* **No pass** → do not retrain the RL on these inputs. Report and propose
  changes to the inputs or the horizon, not the learner.
* **One or more pass** → retrain a reduced RL set under bracket fills
  (compute here: 2 CPUs) and require it to beat the best passing baseline on
  holdout. Then one look at the live window.
