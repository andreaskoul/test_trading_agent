# Go-live gate (live)

**HALTED: a risk stop fired (see fund_state/live/HALT). Review, then resume by hand.**

Protocol 7B (lifecycle book with the 7B rules) from 2026-10-28: the clock restarted; the Protocol 6 record (2026-09-30 to 2026-10-07) and the Protocol 7 record (2026-10-14 to 2026-10-21) stay in weekly_books.csv. Protocol 7B vs the weekly book (c0_weekly): 3 weeks, mean +0.006%/wk, NW t (lag 4) 0.03

No look yet. The rows below are running values and change no decision.

| item | value | rule |
|---|---:|---|
| weeks scored since first live book (2026-10-28) | 3 | looks at 13 / 26 / 39 / 52 |
| fund excess return, mean %/wk | -0.648 | after 5 bp/side and cash |
| NW t (lags 2) | -0.87 | GO if ≥ 4.05 at this look; STOP if ≤ −2 |
| fund − quant NW t | -0.83 | STOP if ≤ −2 |
| analyst-score slope NW t | -1.88 | adjusted version: STOP if ≤ −2 |
| decisions on time | 100% | ≥ 90% |
| weeks fully executed | 100% | ≥ 90% |
| median abs slippage vs close | 6.3 bp | ≤ 10 bp |
| signed cost vs close, value-weighted (lifecycle fills: 260, 28 sessions) | +1.73 bp (95% upper +5.96) | reported; the registered model cost is 5 bp/side |
| risk halt | yes | 10% drawdown or 5% weekly loss on broker NAV |

Broker (paper) NAV 90,285 vs 100,000 at the start of its history; model fund net cumulative -4.43%.

Horizon-end review (Amendment 8): 23 reviews, 3 extended, 20 exited (exit rules {'2': 9, '1': 8, '5': 1, '3': 1, 'slot': 1}). Closed extensions 2: P&L after the horizon $-223 vs $0 for exiting at it, after costs; open extensions marked $0. Switch-off test at 50 reviews (23 so far).

**Protocol 9 (from 2026-11-16), 6 sessions.** Fidelity BREACH (|account − model composite| ≤ 30 bp a month). No alpha verdict on the core (PROTOCOL_fund.md).

| line | return |
|---|---:|
| account | -91.4%/yr (-5.67%) |
| SPY buy-and-hold | -95.7%/yr (-7.23%) |
| risk-matched SPY (1.0×) | -95.7%/yr (-7.23%) |
| fidelity by month, bp | 2026-11 +591 |
