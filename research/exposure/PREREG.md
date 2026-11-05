# Pre-registration: market exposure policies on a century of daily data

Written 2026-11-04, before any code for this study exists.

**Owner decision (2026-11-04).** The owner asked for this study ("Run it", in reply to the report
`reports/Why we lag a leveraged trend strategy.md` §6, item 4). Until now, CLAUDE.md rule 17 has kept market
exposure a stated policy that is never tested.
* This study is **research only**: it changes nothing in the traded fund, its sleeve, or CLAUDE.md.
* Any change of policy that follows from it is a separate owner decision, as a new protocol.

## Data
* **The market:** Ken French's daily US market return (CRSP value-weighted, all NYSE/AMEX/Nasdaq stocks, dividends
  included) = Mkt-RF + RF, from 1926-07-01 to 2026-09-30.
* **Cash:** French's daily one-month T-bill return (RF).
* **Modern check:** SPY daily total return (Alpaca adjusted closes), 2016-03-01 → 2026-11-03. RF after 2026-09 is
  carried forward from its last value.

**Disclosures.**
* This history is not fresh for the literature: Moreira and Muir used 1926–2015.
* In this project, the owner's sleeve was looked at descriptively on 2018–25 ("the sleeve alone lagged the
  risk-matched S&P").
* The read is therefore confirmatory for this project, not for the world.

## Policies: weight w on the market, the rest in cash
Each is decided from information up to the previous close.

| | Policy | Rule |
|---|---|---|
| P0 | **constant 1.0×** (the null; buy-and-hold) | w = 1 |
| P1 | constant leverage for a 16% volatility | w = min(1.5, 16% ÷ σ_long), with σ_long the expanding-window daily volatility of all past data (≥ 1 year), annualised; reset monthly |
| P2 | volatility-managed (Moreira–Muir, by volatility) | w = min(1.5, 16% ÷ σ_m), with σ_m the realised volatility of the previous calendar month's daily returns, annualised; set on the first session of each month |
| P3 | **the owner's sleeve** | w = 1.3 if the market index (cumulative total return) closed above its 200-session average at the previous close, else 0.7 |

**Financing and costs.**
* Cash earns RF.
* The borrowed part (w > 1) pays RF + 1% a year, as a broker margin rate would.
* Trading costs are 2 bp per side on |Δw|, with 10 bp as a sensitivity.
* The 16% target and the 1.5 cap are fixed here, not tuned. 16% is close to the market's long-run volatility, so
  P1 and P2 average about 1×.

## Tests (made once, full sample 1926-07 → 2026-09)
**For each of P1, P2 and P3 against P0, two conditions:**
1. **Sharpe ratio** (excess of RF, daily, √252) **higher than P0's.**
   * Stationary bootstrap of the paired daily returns (mean block 20 days, 5,000 draws, seed 20261104), one-sided.
   * **Holm correction over the three comparisons**, at family α = 0.05 (roughly t ≥ 2 after correction).
2. **Maximum drawdown no worse than P0's.**

A policy **PASSES** only if both hold.

**Expectation, written in the report beforehand:** volatility targeting passes on drawdown and roughly ties on Sharpe;
the 200-day sleeve does not beat a constant risk-matched exposure.

## Reported beside the test (descriptive)
* Return in % a year, volatility, Sharpe, maximum drawdown, the worst 12 months, and average and maximum leverage.
* A **risk-matched P0**: a constant weight giving P0 the candidate's volatility, financed the same way. This answers
  "is the extra return just extra exposure?"
* **Sub-periods:** 1926–1962, 1963–1999, 2000–2026.
* **Costs at 10 bp per side.**
* **Modern check** on SPY, 2016-03 → 2026-11: P0–P3, for comparison with the replica and intraday tests in the
  report.
