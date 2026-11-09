# An adaptive market-exposure core: pre-registration

*Written 2026-11-10, before any code for this study exists. Owner's brief (2026-11-10): test for the highest Sharpe
ratio with a strategy that adapts to changing market regimes. Research only: nothing in the traded fund changes.
Market exposure is the owner's policy (CLAUDE.md rule 17); this is the one pre-registered test on long history that
the rule allows, and any change of policy is a separate owner decision.*

## 1. Why the core, and why a bounded search

With gross capped at 1.9× and the S&P core at 1.3×, the stock book carries about 0.22 of gross. The fund's result
is, to a first approximation, the core's. So the exposure rule is where a higher Sharpe ratio can come from.

"Search until something works" produces a strategy fitted to the past. This study therefore fixes a small family of
rules from the literature, with no fitted parameter, and reads it once on markets no exposure test in this project
has read. If it fails, the answer is that the incumbent stays.

## 2. Literature (search summaries or memory; papers not opened)

* Trend in the index: a 200-session average rule (the incumbent; passed this project's century test,
  `research/exposure`); time-series momentum over 1 to 12 months (Moskowitz, Ooi, Pedersen 2012).
* Volatility-managed exposure (Moreira and Muir 2017): in-sample gains, disputed out of sample (Cederburg et al. 2020).
  In `research/exposure` it missed the Holm bar (p 0.065) with the best drawdown.
* Panic state (Daniel and Moskowitz 2016): past-year return negative and volatility high.
* Combining rules: an equal-weight average of forecasts is hard to beat (the forecast-combination puzzle).
* Tracking a best rule that changes over time: the fixed-share forecaster (Herbster and Warmuth 1998), exponential
  weights with a small probability of switching, with a regret bound against the best sequence of experts.
* Sharpe comparison: stationary bootstrap of paired returns, as in `research/exposure`.

## 3. Data

* **Replication markets (the confirmatory sample):** Ken French daily developed-market factors for Europe, Japan and
  Asia Pacific ex Japan, 1990-07 .. 2025-12-31, in US dollars: market = Mkt-RF + RF, cash = RF.
* **United States (descriptive only):** Ken French daily market, 1926-07 .. 2026-09, the file used by
  `research/exposure`. That sample was read for P1–P3 and the incumbent is known to pass on it.
* **Disclosure.** `research/regime` used the three regional market series to define its panic state for a momentum
  test. No exposure rule was evaluated on them.

## 4. Rules: weight w on the market, the rest in cash, decided at the previous close

Let idx be the cumulative total-return index and σ21 the standard deviation of the last 21 daily returns × √252.
A score s in [0, 1] maps to w = w_min + s·(w_max − w_min).

| | Rule | Definition |
|---|---|---|
| T200 | incumbent | s = 1 if idx is above its 200-session average, else 0 |
| TSM | multi-horizon trend | s = the share of L in {21, 63, 126, 252} for which the market's return over the last L sessions exceeds cash's |
| VOL | volatility target | w = clip(16% ÷ σ21, w_min, w_max), daily |
| PANIC | panic switch | s = 0 if the 252-session return is negative and σ21 is above its median of the last 756 sessions, else 1 |
| **ENS** | equal-weight ensemble | the average of the four weights above |
| **FS** | fixed-share adaptive mix | experts: the four rules and constant 1×. Utility of expert k on day t: u = x − x², x its return in excess of cash, net of costs (risk aversion 2, under which a constant 1× is about optimal for the US long run, so gains must come from timing). Weights v ∝ exp(η·Σu), then v ← (1 − α)·v + α/5, α = 1/252, η = √(8·ln 5 / 252) ÷ 0.10 = 2.26 (the textbook rate for a 252-day regime and a 10% utility range). w = Σ v_k·w_k |
| BH | buy and hold | w = 1 |

* **Bands.** Policy band [0.7, 1.3] (the owner's), primary. Wide band [0, 1.5], secondary.
* **Financing and costs** as `research/exposure`: cash earns RF; the part above 1 pays RF + 1% a year; 2 bp a side on
  |Δw|; 10 bp as a sensitivity.
* The first evaluated day is the first on which every rule exists (about 1994-07 for the regions).

## 5. Tests (made once, on the three regions; `READ.lock`)

Statistic: the difference of annualised Sharpe ratios (excess of RF), averaged over the three regions. P-value: a
stationary bootstrap of days (mean block 20, 5,000 draws, seed 20261110), the same resampled days in all regions,
one-sided.

| | Claim |
|---|---|
| **H1** | ENS has a higher Sharpe ratio than buy and hold |
| **H2** | ENS has a higher Sharpe ratio than the incumbent T200 |
| **H3** | FS has a higher Sharpe ratio than ENS (adaptation adds something) |

Holm across H1–H3 in the policy band at family α = 0.05. The wide band is tested the same way as a separate family.

**Code check before the read.** On the US file, T200 in the policy band must reproduce the Sharpe ratio recorded in
`research/exposure/results.json` (`full.P3.sharpe` = 0.578) to two decimals. If it does not, the code is wrong and
the regions are not read.

**Reported, not tested:** every rule's return (% a year), volatility, Sharpe, worst fall and turnover in each region
and in the US; the same against a risk-matched buy and hold; results by decade; 10 bp costs; FS with η × 10 and
η × 100 and with α = 1/63 and 1/756, labelled exploratory.

## 6. Consequences, fixed now

* **H2 passes** in the policy band: propose to the owner that the core's rule become ENS, as a protocol, with a shadow
  period. **Fails:** the incumbent stays; no further exposure rule is tested on these samples.
* **H3 passes:** propose FS in place of ENS. **Fails:** no adaptive re-weighting; the conclusion is that the available
  history cannot tell the rules apart fast enough to switch between them.
* **H1 alone** (ENS beats buy and hold but not T200): recorded; no change.
* The wide band is information for the owner about what the [0.7, 1.3] policy costs or saves; it changes nothing by
  itself.

## 7. Not claimed

No claim about the stock book. No claim that a higher Sharpe ratio means a higher return than the S&P: at equal
exposure a timing rule can raise Sharpe and still lag in a long bull market.
