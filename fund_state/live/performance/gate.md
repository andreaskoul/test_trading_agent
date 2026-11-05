# Go-live gate (live)

**CONTINUE (2 weeks scored; next look at 13 weeks).**

Protocol 7 (lifecycle book) from 2026-10-14: the clock restarted; the Protocol 6 record (2026-09-30 to 2026-10-07) stays in weekly_books.csv. Protocol 7 vs the weekly book (c0_weekly): 2 weeks, mean +0.228%/wk, NW t (lag 4) nan

No look yet. The rows below are running values and change no decision.

| item | value | rule |
|---|---:|---|
| weeks scored since first live book (2026-10-14) | 2 | looks at 13 / 26 / 39 / 52 |
| fund excess return, mean %/wk | 0.027 | after 5 bp/side and cash |
| NW t (lags 2) | nan | GO if ≥ 4.05 at this look; STOP if ≤ −2 |
| fund − quant NW t | -2.02 | STOP if ≤ −2 |
| analyst-score slope NW t | -3.72 | adjusted version: STOP if ≤ −2 |
| decisions on time | 100% | ≥ 90% |
| weeks fully executed | 100% | ≥ 90% |
| median abs slippage vs close | 5.2 bp | ≤ 10 bp |
| signed cost vs close, value-weighted (lifecycle fills: 129, 13 sessions) | +0.98 bp (95% upper +2.12) | reported; the registered model cost is 5 bp/side |
| risk halt | no | 10% drawdown or 5% weekly loss on broker NAV |

Broker (paper) NAV 96,233 vs 100,000 at the start of its history; model fund net cumulative -2.73%.

Horizon-end review (Amendment 8): 15 reviews, 1 extended, 14 exited (exit rules {'1': 6, '2': 6, '5': 1, '3': 1}). Closed extensions 1: P&L after the horizon $-88 vs $0 for exiting at it, after costs; open extensions marked $0. Switch-off test at 50 reviews (15 so far).
