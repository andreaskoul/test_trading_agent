# Protocol 2: daily horizon, new information

Committed before any feature has been lined up against a return. Follows
from `reports/research/README.md`: on 4–26 hour horizons the 22 price and
macro features give gross edges of 0–1.3 bp against a 1.4 bp cost. Two
levers remain: a longer horizon (bigger moves for the same cost) and
information the hourly price doesn't already contain.

## Question

On daily gold, do positioning (CFTC), real rates, the dollar, or
time-series momentum predict returns out of sample, **net of cost and
beyond simply being long gold**?

## Data (scripts/daily/fetch_daily_data.py → data/raw/daily/)

| series | source | availability lag used |
|---|---|---|
| GC=F daily OHLC | Yahoo | close of day t |
| 10y real yield DFII10 | FRED | +1 business day |
| 10y breakeven T10YIE | FRED | +1 business day |
| VIX VIXCLS | FRED | +1 business day |
| dollar index DX-Y.NYB | Yahoo (daily, real time; FRED's broad index is published weekly with a lag) | +1 business day |
| COT managed-money long/short, open interest, gold 088691 | CFTC disaggregated futures | report Tuesday **+6 calendar days** (released Friday 15:30 ET; used from the following Monday) |

## Execution and cost

The signal uses information up to the close of day *t*. The position is set
at the close of *t+1* (one full day of implementation delay, deliberately
conservative) and earns close-to-close returns from then on. Positions are
in {−1, 0, +1} of unit notional. Holding H ∈ {1, 5} days: for H = 5 the
position is the mean of the last 5 daily signals (5 overlapping tranches).
Cost is **2 bp per unit of turnover** (|Δposition|), reported with
sensitivity at 1 and 4 bp.

## Splits

| name | span |
|---|---|
| dev | 2006-06-13 (start of disaggregated COT) → 2018-12-31; purged 8-fold CV (purge H + 1 days, embargo 5 days) |
| holdout | 2019-01-01 → 2026-03-31; one pass, models refit on all of dev |
| live | 2026-04-01 → : single final check, only for a rule that passes holdout |

The hourly study used 2023-07 → 2026-03 hourly prices with different
features and a different horizon. This daily question has not been run on
any of these data.

## Features (fixed)

`ret_5, ret_20, ret_60, ret_250` (log), `rv_20` (daily realised vol),
`dry_5, dry_20` (change in DFII10, pp), `dbe_5, dbe_20` (change in T10YIE),
`dxy_5, dxy_20` (log change), `vix_5, vix_20` (log change),
`cot_z` (managed-money net / OI, z-score over the trailing 156 weeks),
`cot_d4` (4-week change in managed-money net / OI).

## Rules (trials: 7 × 2 horizons = N = 14)

| id | signal |
|---|---|
| tsmom12 | sign(ret_250) (Moskowitz, Ooi & Pedersen 2012) |
| tsmom1 | sign(ret_20) |
| realrate | sign(−dry_20) |
| dollar | sign(−dxy_20) |
| cot | −sign(cot_z) if abs(cot_z) > 1 else 0 (crowding contrarian) |
| ridge | sign(ridge(α = 10) forecast of the H-day forward return) on all 15 features, standardised |
| gbm | sign(HistGradientBoosting(max_depth 3, 200 iters, lr 0.05) forecast), same inputs |

Benchmarks (not trials): always long, 500 coin-flip paths with the same
H smoothing.

## Metrics

* Daily net returns: annualised Sharpe, HAC t (lags = H + 5), PSR(0),
  DSR with N = 14 and the cross-trial Sharpe variance.
* **Alpha versus gold**: OLS of daily strategy return on the daily gold
  return, HAC t of the intercept. A long-biased rule in a gold bull market
  must not pass on beta alone.
* IC: monthly Spearman between the score and the H-day forward return; mean
  and HAC t over months.
* p-value against the coin-flip distribution.

## Decision rule

A rule passes if, on holdout at 2 bp: Sharpe HAC t > 2, **alpha HAC t > 2**,
DSR > 0.95 and IC t > 2. No pass means gold at a daily horizon is not
predictable from these sources, and the next step is the news-geometry
features, pre-registered separately. A pass gets one look at the live window
and a pre-registered paper-trading spec before any cron is re-enabled.
