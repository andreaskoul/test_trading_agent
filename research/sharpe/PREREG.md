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

### Result of the read (2026-11-10, `RESULT.json`, three regions, 1993-06 .. 2025-12, 8,487 pooled days)

| | Policy band [0.7, 1.3] | Wide band [0, 1.5] |
|---|---|---|
| H1 ENS − buy and hold | +0.038, p 0.14: fails | +0.077, p 0.21: fails |
| H2 ENS − incumbent T200 | −0.032, p 0.96: fails (90% interval −0.063 .. −0.001) | −0.037, p 0.76: fails |
| H3 FS − ENS | −0.004, p 0.74: fails | +0.005, p 0.37: fails |

Mean Sharpe over the regions, policy band: T200 0.379, TSM 0.390, ENS 0.347, FS 0.343, buy and hold 0.309, VOL 0.283,
PANIC 0.316. Consequences as registered: **the incumbent stays; no adaptive re-weighting; no further exposure rule is
tested on the three regions.**

### Amendment 1 (2026-11-10, after the read above; before any statistic of H4): one replication of an exploratory lead

**The lead.** Among the six exploratory FS settings reported with the read, the fastest (η × 100, α = 1/63) had the
highest mean Sharpe in the wide band (0.524, against 0.497 for the best single rule, TSM, and 0.424 for T200). In the
policy band it showed nothing (0.380 against 0.379 for T200). Six settings were looked at, so this is a lead, not a
result.

**The test, once, on the United States file (1929 .. 2026-09), wide band only.** FS* = FS with η × 100 and α = 1/63.
That setting has not been run on the US file; the default FS has (Sharpe 0.612, below T200's 0.653 and TSM's 0.728).
* **H4a:** FS* has a higher Sharpe ratio than ENS.
* **H4b:** FS* has a higher Sharpe ratio than T200.
Same bootstrap (seed 20261110), one-sided, Holm across the two. Lock: `READ_US.lock`.

**Consequences.** Both pass: recorded as a candidate for the owner, with the note that it lives outside the
[0.7, 1.3] policy band. Either fails: fast adaptation is closed, on both samples.

### Result of Amendment 1 (2026-11-10, `RESULT_US.json`, United States 1929 .. 2026-09, wide band, read once)

| | Sharpe | % a year | Worst fall | Turnover a year |
|---|---:|---:|---:|---:|
| FS* (fast adaptive mix) | 0.729 | 14.6 | −49.6% | 23.6 |
| TSM (multi-horizon trend) | 0.728 | 13.2 | −41.5% | 14.6 |
| T200 (incumbent rule, wide band) | 0.653 | 13.5 | −47.8% | 8.3 |
| ENS | 0.634 | 12.3 | −53.0% | 8.0 |
| Buy and hold | 0.428 | 9.3 | −84.1% | 0.0 |

* H4a FS* − ENS: +0.096, p 0.012, passes Holm. H4b FS* − T200: +0.076, p 0.094, **fails**.
* By period, FS* against T200: 0.94 / 0.74 (1929–62), 0.90 / 0.75 (1963–99), **0.29 / 0.42 (2000–2026)**.

**Consequence as registered: fast adaptation is closed on both samples.** It did not beat the incumbent rule, it only
matched the plain multi-horizon trend rule with more trading, and it was the worst of the five since 2000.

### What this study leaves standing (descriptive, not tested)

* The 200-session rule beat buy and hold in two of three regions and on average (0.379 against 0.309, policy band),
  which agrees with the century result. It lagged in Japan.
* Volatility targeting and the panic switch lowered the Sharpe ratio outside the US.
* In the wide band the trend rules' Sharpe ratios and worst falls were better than in the policy band in Europe, Asia
  Pacific and the US, and worse in Japan. This was not a registered test. The band is the owner's policy.

### Amendment 2 (2026-11-10, before any code or statistic of H5–H6): neural exposure rules, walk-forward on the US century

**Why.** Owner (2026-11-10): keep searching for a strategy that beats S&P buy and hold; neural and deep networks are
welcome. Deep models were already tested here for stock selection (`research/quant_trials`: one of twelve passed).
They have not been tested for the core's exposure. The three regions are closed to further exposure rules by §6, so
the only sample is the US century, used walk-forward: every prediction comes from a model fitted on earlier data only.

**Literature** (search summaries or memory): networks trained directly on the Sharpe ratio of the resulting position
(Lim, Zohren, Roberts 2019, "deep momentum networks"; Zhang, Zohren, Roberts 2020).

**Models.** Output w = lo + (hi − lo)·sigmoid(f(x)), decided at the previous close.
* **MLP:** inputs at the close: the market's return over 1, 5, 21, 63, 126 and 252 sessions, each divided by
  σ63·√L; idx ÷ its 50- and 200-session averages − 1, divided by σ63·√50 and σ63·√200; log σ21; log(σ21 ÷ σ252);
  the fall from the 252-session high. Two hidden layers of 16 units, tanh.
* **CNN:** input: the last 126 daily returns divided by σ63 (as known the day before each), clipped to ±5.
  Conv(1→8, k 5), ReLU, Conv(8→8, k 5, stride 2), ReLU, average-pool to 4, linear 32→16, ReLU, linear 16→1.
* **Training, fixed now:** loss = −Sharpe of the net excess return w·(r − rf) − 1%·max(w − 1, 0)/252 − 2 bp·|Δw| on
  the training days in order (full batch); Adam, learning rate 0.001, weight decay 0.0001; at most 500 steps;
  validation = the last 20% of the fitting window, checked every 10 steps, stop after 5 checks without improvement,
  keep the best. Five seeds (0–4); the rule is the mean of the five weights.
* **Walk-forward:** refit at the start of 1950 and every five years after, on all earlier data; each fit predicts the
  next five years. Out-of-sample span: 1950-01 .. 2026-09.

**Tests (once; `READ_NN.lock`), policy band [0.7, 1.3]:**
* **H5:** the MLP rule has a higher Sharpe ratio than the incumbent T200 over the out-of-sample span.
* **H6:** the CNN rule has a higher Sharpe ratio than T200.
Stationary bootstrap as §5 (seed 20261110), one-sided. **Holm across the two at family α = 0.01**, not 0.05, because
this is at least the sixth exposure hypothesis read on this century in this project.

**Reported:** each rule against buy and hold; the wide band; 1950–1999 and 2000–2026; turnover; 10 bp costs.

**Consequences.** A pass: a candidate for the owner, which could only be confirmed on forward data. Both fail: neural
exposure rules are closed on the US century.

### Amendment 3 (2026-11-10, before any code or statistic of C1–C6): placing the long/short positions and limiting falls

**Why.** Owner (2026-11-10): research more advanced algorithms and econometrics to reduce drawdown and to place
long/short positions better. The only validated stock-level signal is the MASTER 5-day score
(`research/quant_trials`). Its plain decile book lost money in 2013–19 at 5 bp and loads on momentum.

**Status of the evidence, stated before running.** These predictions were scored and seen in October. Everything
below is therefore development on a seen sample, not a confirmation; that project's rule (the traded variant is
chosen on forward weeks only) is unchanged. A construction that passes here earns a forward paper book, nothing more.

**Literature** (search summaries or memory): sector- and characteristic-neutral ranking (standard practice; momentum
crashes, Daniel and Moskowitz 2016); shrinkage covariance for optimised weights (Ledoit and Wolf 2004); volatility
targeting (Moreira and Muir 2017); optimal investment under a drawdown constraint (Grossman and Zhou 1993).

**Common frame** (the simulator of `strategies.py`): Thursday decisions, 2013–2025, book gross 1.0 (0.5 a side),
beta-hedged with SPY, on top of the 1.3×/0.7× 200-session core, 5 bp a side on all turnover, margin at the bill
+ 2.43%. **Baseline S0:** top and bottom deciles of the score, equal weights.

| | Construction | Definition, fixed now |
|---|---|---|
| C1 | sector-neutral deciles | top and bottom 10% within each GICS sector (sectors with fewer than 10 eligible names, or none known, pooled) |
| C2 | characteristic-neutral score | each week, the residual of the z-scored score on the panel's five z-scored price characteristics, beta and sector dummies; then deciles |
| C3 | covariance-optimised weights | w ∝ Σ⁻¹z, Σ the Ledoit–Wolf covariance of the last 252 daily returns of eligible names with at least 200 of them; positive weights scaled to 0.5, negative to −0.5 |
| C4 | panic switch on the book | S0, but no book in a week when SPY's 252-session return is negative and its 21-session volatility is above its median of the last 780 sessions |
| C5 | volatility-targeted book | S0 scaled by min(1.5, 10% ÷ the unscaled book's volatility over its last 13 weeks) |
| C6 | drawdown control on the whole fund | core and book both multiplied by clip(1 − D ÷ 0.25, 0, 1), D the fall of the controlled fund from its 52-week high at the previous decision |

**Tests (one run).** For each of C1–C6: the Sharpe ratio of the whole fund (core + book) minus S0's; stationary
bootstrap of paired weekly returns (mean block 4 weeks, 5,000 draws, seed 20261110), one-sided; Holm across the six at
α = 0.05. **Reported for each:** % a year, volatility, worst fall, return ÷ worst fall, the book's own Sharpe,
turnover, 2013–19 and 2020–25 separately, and the same at 1 bp.

**Consequences.** A construction that passes: propose one forward paper book with it (research only). None passes:
the plain deciles stay. A combination of several constructions may be reported, labelled exploratory.
