# Protocol 4: cross-sectional US large caps, weekly

Committed before any stock price has been downloaded.

## Universe

Point-in-time S&P 500 membership from `fja05680/sp500`
(`S&P 500 Historical Components & Changes (Updated).csv`, pinned in
`data/raw/stocks/`): on each date, a stock is eligible only if it was an
index member on that date. Prices are Yahoo adjusted closes (splits and
dividends), tickers mapped to Yahoo form (`.` → `-`).

**Survivorship.** Members that were later delisted or acquired are often
missing from Yahoo, and recycled tickers can point at a different company.
Rules, fixed now:
* A member-date is usable only if Yahoo has a price for that ticker within
  the membership spell. A ticker whose Yahoo history starts more than 30
  days after its spell starts is used only from its Yahoo start.
* Coverage (usable / members) is reported for every week. Headline results
  use all weeks. A robustness run keeps only weeks with coverage ≥ 90%.
* Direction of the bias, stated in advance: missing names are
  disproportionately firms that later failed or were bought. Losers are
  under-represented on the short side of momentum-style signals, so the
  bias is **against** momentum and **in favour of** reversal and low-risk
  signals. Reversal and low-vol results must be read with that in mind.

## Execution, costs, portfolio

Wednesday close signal, Thursday close execution, Thursday-to-Thursday
returns, holding H ∈ {1, 4} weeks (overlapping tranches). Rank weights,
demeaned, sum |w| = 2 (dollar-neutral). Cost **5 bp per side** per unit of
turnover, with sensitivity at 2.5 and 10 bp.

## Signals (7 × 2 holding periods = N = 14)

| id | score |
|---|---|
| mom12_1 | return from week t−52 to t−4 (Jegadeesh & Titman 1993) |
| rev1m | − return over the last 4 weeks (Jegadeesh 1990) |
| rev1w | − last week's return |
| lowvol | − 60-trading-day volatility of daily returns |
| high52 | price / 52-week high (George & Hwang 2004) |
| combo | mean cross-sectional z of mom12_1, rev1m, lowvol |
| ridge | ridge (α = 10) on the z-scores of the 5 base signals, target next week's cross-sectionally demeaned return, pooled; fitted on dev with purged 8-fold CV (purge 5 weeks) |

## Splits

dev 2004-01 → 2015-12; holdout 2016-01 → 2026-03-31; live 2026-04 →
kept for one check of a passing signal.

## Metrics

* Weekly net returns: Sharpe, HAC t (lags 4 + H), PSR, DSR (N = 14).
* Fama–MacBeth slope on the cross-sectional rank (scaled to [−0.5, 0.5]),
  Newey–West t (lags 4).
* Alpha against the equal-weight universe return (the market leg a
  dollar-neutral book still carries through beta), HAC t.
* **Secondary, not a pass criterion:** alpha against Fama–French 5 factors +
  momentum (Ken French daily factors, compounded to Thursday weeks), to show
  whether a signal is anything more than a known factor.

## Pass rule

On holdout at 5 bp: Sharpe HAC t > 2, DSR > 0.95, FM t > 2, alpha vs
equal-weight market t > 2.
