# Shadow `quant` book ("Price factors, whole S&P 500") vs SPY buy-and-hold, 1997–2026

Ad-hoc research run, 2026-10-21. It is not pre-registered and feeds no decision. Script: `fund/backtest_quant.py`.

## Method

Every Wednesday from 1997-01-01 to 2026-10-14 (1,555 weeks), the book is rebuilt as it would have run live then:

* Universe: point-in-time S&P 500 members (`data/raw/stocks/sp500_membership.csv`) that have a Yahoo price.
* Model: the five `screen.py` signals as z-scores, then `artefacts/llm/ridge_stocks.json`.
* Book: `pm_risk.py`'s top/bottom 10 at 10%, sector net ≤ 30%, dollar net ≤ 10% of gross, then SPY to zero hedge beta.
* Marking: `shadow_ledger.py`'s rules (entry the session after Wednesday, exit on or after as-of + 8 days, 5 bp per side
  on the weight change, cash 0%).

There is also a walk-forward variant. It refits the ridge every January (alpha 10) on the weeks already closed and
starts in 2001. Sharpe is measured over Yahoo's 13-week T-bill (^IRX), because FRED refused the download.

Validation: the rebuilt books for 2026-10-07 and 2026-10-14 match the live `fund-data` books exactly (20/20 names, SPY
hedge to 3 decimals). For 2026-09-30, the first live week, 15/20 names match.

## Results (frozen ridge, $100k)

| Span | SPY | Quant book | Quant + T-bills | SPY + quant |
|---|---|---|---|---|
| 1997-01 → 2026-10, CAGR | 10.1% | −1.3% | 1.0% | 6.8% |
| Sharpe / max DD | 0.51 / −54% | 0.04 / −82% | 0.11 / −80% | 0.30 / −79% |
| 1997–2003, before fit window | 7.7% | 5.4% | 9.4% | 11.4% |
| 2004 → 2026-03, fit window (in-sample) | 10.2% | −3.6% | −1.9% | 4.4% |
| 2016 → 2026-10, coverage ≥ 76% | 15.5% | 2.4% | 4.8% | 16.5% |
| 2026-04 → 2026-10, after fit (29 wks, total) | +18.5% | +5.8% | +8.0% | +25.5% |
| Walk-forward 2001 → 2026-10, CAGR | 9.0% | −4.7% | −3.0% | 2.5% |

* **Realized beta 0.61, against a target of 0.** The long leg's beta is 1.64 and the short leg's 0.64. The SPY hedge
  averages −0.27 of NAV. The hedge beta (Welch winsorised, shrunk ⅓ toward 1) understates the high-volatility names
  the ridge favours. This is reported as a gap against the stated policy; it is not a tuning proposal (CLAUDE.md 17).
* **Alpha after removing beta:** +6.0%/yr gross (t = 1.1) and −2.1%/yr net (t = −0.4). Costs are about 8%/yr, from
  turnover of about 160× NAV a year.
* **Volatility:** 31%/yr, against SPY's 17%.

## Limits

* Survivorship: Yahoo lacks most delisted names. Coverage of the point-in-time index is 39% in 1997, 76% in 2016 and
  98% in 2026. The years before 2016 probably flatter the long leg.
* 28 tickers are excluded by name, either reused by another company or carrying bad prints (`REUSED` in the script).
* Sectors are today's GICS labels.
