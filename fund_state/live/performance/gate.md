# Go-live gate (live)

**CONTINUE (2 weeks scored; next look at 13 weeks).**

Protocol 7B (lifecycle book with the 7B rules) from 2026-10-28: the clock restarted; the Protocol 6 record (2026-09-30 to 2026-10-07) and the Protocol 7 record (2026-10-14 to 2026-10-21) stay in weekly_books.csv. Protocol 7B vs the weekly book (c0_weekly): 2 weeks, mean -0.023%/wk, NW t (lag 4) nan

No look yet. The rows below are running values and change no decision.

| item | value | rule |
|---|---:|---|
| weeks scored since first live book (2026-10-28) | 2 | looks at 13 / 26 / 39 / 52 |
| fund excess return, mean %/wk | -1.035 | after 5 bp/side and cash |
| NW t (lags 2) | nan | GO if ≥ 4.05 at this look; STOP if ≤ −2 |
| fund − quant NW t | -2.02 | STOP if ≤ −2 |
| analyst-score slope NW t | -1.93 | adjusted version: STOP if ≤ −2 |
| decisions on time | 100% | ≥ 90% |
| weeks fully executed | 100% | ≥ 90% |
| median abs slippage vs close | 5.8 bp | ≤ 10 bp |
| signed cost vs close, value-weighted (lifecycle fills: 196, 23 sessions) | -0.87 bp (95% upper +1.10) | reported; the registered model cost is 5 bp/side |
| risk halt | no | 10% drawdown or 5% weekly loss on broker NAV |

Broker (paper) NAV 96,162 vs 100,000 at the start of its history; model fund net cumulative -4.63%.

Horizon-end review (Amendment 8): 19 reviews, 2 extended, 17 exited (exit rules {'2': 8, '1': 7, '5': 1, '3': 1}). Closed extensions 1: P&L after the horizon $-88 vs $0 for exiting at it, after costs; open extensions marked $-73. Switch-off test at 50 reviews (19 so far).

**Protocol 9 (from 2026-11-16), 1 sessions.** Fidelity BREACH (|account − model composite| ≤ 30 bp a month). No alpha verdict on the core (PROTOCOL_fund.md).

| line | return |
|---|---:|
| account | +225.7%/yr (+0.47%) |
| SPY buy-and-hold | -92.4%/yr (-1.01%) |
| risk-matched SPY (1.3×) | -96.6%/yr (-1.33%) |
| fidelity by month, bp | 2026-11 +173 |
