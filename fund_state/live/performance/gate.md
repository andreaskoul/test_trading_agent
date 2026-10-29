# Go-live gate (live)

**CONTINUE (1 weeks scored; next look at 13 weeks).**

Protocol 7 (lifecycle book) from 2026-10-14: the clock restarted; the Protocol 6 record (2026-09-30 to 2026-10-07) stays in weekly_books.csv. Protocol 7 vs the weekly book (c0_weekly): 1 weeks, mean -1.228%/wk, NW t (lag 4) nan

No look yet. The rows below are running values and change no decision.

| item | value | rule |
|---|---:|---|
| weeks scored since first live book (2026-10-14) | 1 | looks at 13 / 26 / 39 / 52 |
| fund excess return, mean %/wk | -1.068 | after 5 bp/side and cash |
| NW t (lags 2) | nan | GO if ≥ 4.05 at this look; STOP if ≤ −2 |
| fund − quant NW t | -0.74 | STOP if ≤ −2 |
| analyst-score slope NW t | -15.61 | adjusted version: STOP if ≤ −2 |
| decisions on time | 100% | ≥ 90% |
| weeks fully executed | 0% | ≥ 90% |
| median abs slippage vs close | 4.4 bp | ≤ 10 bp |
| risk halt | no | 10% drawdown or 5% weekly loss on broker NAV |

Broker (paper) NAV 97,729 vs 100,000 at the start of its history; model fund net cumulative -3.88%.

Horizon-end review (Amendment 8): 7 reviews, 0 extended, 7 exited (exit rules {'1': 3, '2': 3, '5': 1}). Closed extensions 0: P&L after the horizon $0 vs $0 for exiting at it, after costs; open extensions marked $0. Switch-off test at 50 reviews (7 so far).
