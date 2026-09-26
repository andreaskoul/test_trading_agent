# Protocol 3: cross-sectional FX, weekly

Committed before any signal is lined up against a return. Follows the
decision (2026-09-26) to move from single-asset direction to market-neutral
cross-sectional ranking. With 18 currencies, ranking them against each
other cancels the dollar's own trend, and the edge scales with breadth
rather than with one asset's drift.

## Universe (fixed)

18 currencies against USD that have both a Yahoo daily spot series from
2004 and an OECD 3-month interbank rate on FRED (`IR3TIB01{cc}M156N`), which
is needed for excess returns:

EUR, JPY, GBP, CHF, AUD, NZD, CAD, SEK, NOK, MXN, ZAR, PLN, HUF, CZK, KRW,
ILS, CLP, IDR.

Excluded before any analysis: TRY (rate series ends 2008), BRL, INR, COP,
SGD, THB, PHP, TWD (no OECD rate on FRED), CNY (managed), HKD/DKK (pegged).

## Returns

Weekly, Wednesday to Wednesday (London close as stamped by Yahoo). For
currency *c*, with *S* in USD per unit of *c*:

    excess_c,w = log(S_w / S_w-1) + (i_c − i_USD) / 52

using the OECD monthly rate of the current month (the accrual a forward
contract locks in at trade time; monthly averaging is an approximation).
A missing latest month is forward-filled.

**Bad-tick filter** (fixed now): a daily spot print is removed if it moves
more than 8% from both the previous and the next day's print in opposite
directions (a spike that reverts). Removed prints are logged.

## Execution and cost

The signal uses data up to the Wednesday close. Positions are set at the
Thursday close (one day of delay) and held to the following Thursday. P&L
uses Thursday-to-Thursday excess returns. Cost per unit of turnover,
per side: 1 bp for EUR JPY GBP CHF AUD NZD CAD SEK NOK; 3 bp for MXN PLN
HUF CZK ILS KRW; 6 bp for ZAR CLP IDR. Sensitivity at 0.5× and 2×.

Portfolio: rank weights. Each week the ranks are demeaned and scaled so
that sum |w| = 2 (one unit long, one unit short), which makes it dollar-neutral.
Holding H ∈ {1, 4} weeks via H overlapping weekly tranches.

## Signal availability

* Spot-based signals: Wednesday close.
* Rates for the carry *signal*: month *m*'s OECD value is used only from the
  first day of month *m + 2* (publication lag).

## Signals (trials: 8 × 2 holding periods = N = 16)

| id | score |
|---|---|
| carry | i_c − i_USD (lagged as above) |
| mom12 | excess return over weeks t−52 … t−4 (12-1) |
| mom3 | excess return over the last 13 weeks |
| mom1 | excess return over the last 4 weeks |
| rev1w | − last week's excess return |
| value | − 5-year change in log spot (nominal; no CPI adjustment) |
| combo | mean of the cross-sectional z-scores of carry, mom12 and value (no fitting) |
| ridge | ridge (α = 10) on the cross-sectional z-scores of the 6 base signals, predicting next week's cross-sectionally demeaned excess return; fitted on dev |

## Splits

| name | span |
|---|---|
| dev | 2004-01 → 2015-12; ridge uses purged 8-fold CV inside dev (purge 5 weeks) |
| holdout | 2016-01 → 2026-03-31; one pass |
| live | 2026-04 → : single check, only for a signal that passes holdout |

## Metrics

* Weekly net returns: annualised Sharpe (√52), HAC t (lags 4 + H), PSR,
  DSR with N = 16.
* Alpha against the dollar factor DOL (equal-weight mean of all 18 excess
  returns) with HAC t. Also reported against carry for non-carry signals.
* **Predictability: Fama–MacBeth.** Each week, regress next week's excess
  return on the cross-sectional rank of the signal (scaled to [−0.5, 0.5]).
  Report the mean slope with a Newey–West t over weeks (lags 4). This
  replaces the within-month IC, which Protocol 2 showed to be defective.

## Decision rule

Passes on holdout at base costs if Sharpe HAC t > 2, DSR > 0.95,
Fama–MacBeth t > 2 and alpha-vs-DOL t > 2. A pass gets one look at the live
window, then a pre-registered paper-trading spec.
