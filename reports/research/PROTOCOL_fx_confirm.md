# Protocol 3b: confirming two FX findings on untouched 1990–2003 data

Committed after Protocol 3's run and before any 1990–2003 data has been
downloaded.

## Why

Protocol 3 (dev 2004–15, holdout 2016–26) produced two patterns that were
not the registered hypotheses, or failed only the deflation hurdle:

1. **Short-term cross-sectional reversal.** Registered as momentum, `mom1`
   was strongly *negative* in both samples (H = 1: dev t −2.9, holdout
   t −3.3; Fama–MacBeth t −1.9 / −2.1). `mom3` was negative too. Reading it as
   reversal is post hoc.
2. **Carry.** Holdout Sharpe 0.75, t 2.5, alpha-vs-DOL t 2.7, FM t 2.5.
   It failed only DSR (0.16), because the 16-trial Sharpe dispersion was
   large. Dev (2004–15, including 2008) was flat.

Both deserve a test on data none of the work has touched.

## Data

1990-01 → 2003-12. Fed H.10 noon rates (FRED) for the currencies that
existed and have OECD 3-month rates: JPY, GBP, CHF, AUD, NZD, CAD, SEK,
NOK, DKK (`DEXDNUS`, European proxy before the euro), ZAR, KRW (from
1991), MXN (from 1997, when its rate series starts). A currency enters once
both spot and rate exist.

Everything else is identical to Protocol 3: Wednesday signals, Thursday
execution, excess returns with OECD accrual, carry signal lagged 2 months,
rank weights with sum |w| = 2. Costs are **doubled** from Protocol 3 (1990s
spreads were wider): 2 bp G10 and DKK, 6 bp MXN and KRW, 12 bp ZAR.

## Hypotheses (N = 3, one-sided)

| id | score | H |
|---|---|---|
| rev1m-1 | −(excess return over the last 4 weeks) | 1 |
| rev1m-4 | same | 4 |
| carry-4 | i_c − i_USD | 4 |

## Pass rule

Bonferroni over 3 one-sided tests at 5%: **HAC t > 2.13 and Fama–MacBeth
t > 2.13**. Sharpe, alpha vs DOL, and cost sensitivity are reported. If
reversal confirms, it goes to a paper-trading spec. If it doesn't, the
2004–26 pattern is recorded as unconfirmed.
