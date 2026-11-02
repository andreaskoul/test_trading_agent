# Turnover discipline for a short-horizon long/short equity book (no-trade bands, hold-while-edge rules, cost-aware rebalancing)

Context assumed throughout: SPY-hedged long/short overlay on S&P 500 names, ~10 names a side, weekly cohorts from an LLM
news desk, horizons 3–25 sessions (median hold ~4 sessions), annual one-sided turnover 40–68x NAV, live cost ~1–2 bp
per side, registered 5 bp per side, so cost drag ≈ turnover × cost per side ≈ 40 × 4 bp = 1.6% to 68 × 5 bp = 3.4% a
year. Turnover split: entries ~45%, horizon exits ~18%, hedge ~17.5% (remaining ~19.5% unspecified). No signal has
proven net alpha.

Labels used below: **[Evidence]** = peer-reviewed or measured result; **[Theory]** = derived result in a model;
**[Opinion]** = practitioner view; **[Inference]** = my own derivation or application to this fund, not sourced.

---

## 1. Gârleanu & Pedersen (2013): trade partially toward an "aim portfolio"

### Takeaway
With quadratic trading costs and signals that decay at different speeds, the optimal policy is (1) trade a fixed fraction
toward an aim portfolio each period and (2) build the aim by down-weighting each signal by its alpha-decay speed. In
their commodity test, this beat the best static cost-aware rule by ~25% in net Sharpe (0.58 vs 0.46), while the
cost-blind Markowitz portfolio had a net Sharpe of −9.8.

### Cited Findings
- **[Theory] Model.** Returns r_{t+1} = B f_t + u_{t+1}. Signals mean-revert: Δf_{t+1} = −Φ f_t + ε_{t+1}. Trading cost is
  quadratic, ½ Δx' Λ Δx, with Λ = λΣ in the main case. Abstract: "the optimal strategy is characterized by two
  principles: (1) aim in front of the target, and (2) trade partially toward the current aim." — [Gârleanu & Pedersen,
  "Dynamic Trading with Predictable Returns and Transaction Costs", *Journal of Finance* 68(6), Dec 2013, pp. 2309–2340](https://w4.stern.nyu.edu/facdir/lpederse/papers/DynamicTrading.pdf)
- **[Theory] Trading rule (Prop. 2, eqs. 7, 9, 10).** The optimal portfolio is x_t = (1 − a/λ) x_{t−1} + (a/λ) aim_t. The
  trading rate a/λ < 1 is:
  a = [ −(γ(1−ρ) + λρ) + √( (γ(1−ρ) + λρ)² + 4γλ(1−ρ)² ) ] / [ 2(1−ρ) ]
  Here γ is risk aversion, λ is the cost scale and ρ is the discount rate. "The trading rate is decreasing in transaction
  costs (λ) and increasing in risk aversion (γ)." The rate is a fixed fraction: it does not depend on the current
  portfolio. A larger γ "can also be viewed as a smaller investor, for whom transaction costs play a smaller role". — [GP 2013](https://w4.stern.nyu.edu/facdir/lpederse/papers/DynamicTrading.pdf)
- **[Theory] Aim portfolio (Prop. 4, eq. 15).** With diagonal decay Φ = diag(φ_k), the aim is
  aim_t = (γΣ)^{-1} B ( f_1t/(1 + φ_1 a/γ), …, f_Kt/(1 + φ_K a/γ) )'.
  So each signal is shrunk by 1/(1 + φ_k a/γ). A persistent factor is scaled down less than a fast one, and the gap
  grows with transaction costs. — [GP 2013](https://w4.stern.nyu.edu/facdir/lpederse/papers/DynamicTrading.pdf)
- **[Theory] Position homing in (Prop. 5).** Under the optimal rule, the current portfolio is an exponentially weighted
  average of past aim portfolios. — [GP 2013](https://w4.stern.nyu.edu/facdir/lpederse/papers/DynamicTrading.pdf)
- **[Theory] Impulse response.** After a signal shock, the optimal position "increases more slowly to minimize trading
  costs". It may end up larger than the cost-free position because it is also reduced more slowly. — [GP 2013](https://w4.stern.nyu.edu/facdir/lpederse/papers/DynamicTrading.pdf)
- **[Evidence] Commodity futures test.**
  * Signals: 5-day, 12-month and 5-year past returns. Daily decay rates were 0.2519, 0.0034 and 0.0010, which are
    half-lives of 2.4, 206 and 700 days.
  * Calibration: price impact of 0.10% for trading 1.59% of daily volume (from Engle, Ferstenberg & Russell 2008).
  * Table II, base costs (gross SR → net SR): Markowitz 0.83 → −9.84; dynamic optimisation 0.62 → 0.58; best static
    rule (2–3% of the way toward Markowitz each day) → 0.46.
  * High costs: dynamic 0.53 net; best static 0.39 (2%).
  * Why it wins: the dynamic rule "gives less weight to the 5-day signal because of its fast alpha decay". A static
    rule "either incurs large trading costs due to its 'fleeting' target … or trades so slowly that it is difficult to
    capture the return."
  — [GP 2013, Table II and Section IV](https://w4.stern.nyu.edu/facdir/lpederse/papers/DynamicTrading.pdf)
- **[Theory] Related work.** Multi-period optimisation with alpha decay is also treated by:
  * Grinold, "Dynamic portfolio analysis" (JPM 2007) and "Signal weighting" (JPM 2010);
  * Qian, Sorensen & Hua, "Information horizon, portfolio turnover, and optimal alpha models" (JPM 2007);
  * Sneddon, "The tortoise and the hare" (JoI 2008).

  Grinold, Qian et al. and Sneddon "each solve a static auxiliary problem that trades-off signal strength and time decay
  to determine the signal weights", then feed those weights to a single-period optimiser. — [Axioma, "Multi-period
  portfolio optimization with alpha decay" (draft), optimization-online](https://optimization-online.org/wp-content/uploads/2015/02/4785.pdf)
- **[Evidence/practitioner] Israelov & Katz (FAJ 2011), "To Trade or Not to Trade?".** Rule: go ahead with a trade only
  if the short-term and long-term parts of the composite alpha agree on its direction; otherwise cancel it. They report
  promising results on realistic and simulated examples. — [Axioma draft summary](https://optimization-online.org/wp-content/uploads/2015/02/4785.pdf)
- **[Theory] Information horizon.** Signals with a short information horizon (e.g. one-month reversal) "cause high
  turnover because their exposures must be constantly adjusted". Slow signals let lagged portfolios keep earning. — [Qian, Sorensen & Hua, JPM 2007](https://gyanresearch.wdfiles.com/local--files/alpha/JPM_FA_07_Qian.pdf)

### Inferences
- **[Inference] Worked numbers, ρ ≈ 0.** With a daily discount rate near zero, a/λ = (−r + √(r² + 4r))/2, where r = γ/λ
  (≈ √r for small r). Converting half-life h (sessions) to decay: φ = 1 − 2^(−1/h); h = 4 gives φ ≈ 0.159, h = 10 gives
  φ ≈ 0.067. Results:

  | r = γ/λ | trading rate a/λ | aim/Markowitz, h = 4 | aim/Markowitz, h = 10 |
  |---|---|---|---|
  | 0.01 | 0.095 | 0.40 | 0.61 |
  | 0.04 | 0.18 | 0.58 | 0.77 |
  | 0.25 | 0.39 | 0.80 | 0.91 |

  Lesson for a news book with ~4-session holds: any fast-decaying component should be shrunk hard relative to slower
  components, more so as costs rise.
- **[Inference] Where the GP model fits this fund, and where it does not.**
  * GP assumes quadratic (impact) costs and continuous weights.
  * At 1–2 bp per side on S&P 500 names at paper size, costs are essentially linear (spread plus commission). With
    linear costs the optimal policy is a no-trade band (Section 2), not partial trading.
  * What does transfer is the aim-portfolio idea: if the desk produces several horizons or signal types, weight each by
    1/(1 + φ·const), giving the longer-lived ones more weight. This is a weighting rule, so it does not alter any
    pre-registered signal definition.
- **[Inference] Discrete slots.** "Trade partially toward the aim" in a fixed-slot book of 10 names a side works out as
  roughly:
  * staged entry, e.g. ½ slot on signal and ½ on the next cohort's confirmation;
  * staged exit.

  This raises the ticket count but not linear cost, because cost scales with |Δw|. It only helps if the signal is
  persistent across cohorts.

### Gaps
- I did not find a published implementation of GP for single-stock event or news books, or turnover and net-Sharpe
  numbers for equities. GP's own test is on 15 commodity futures.
- I could not retrieve Grinold's "Signal weighting" (2010) text. Its exact weighting formula is not quoted here.

---

## 2. No-trade regions and bands (Leland, Constantinides, Davis–Norman; Carver buffering; practical band rules)

### Takeaway
With proportional (linear) costs, the optimal policy is a no-trade band around the target. When the position leaves the
band, trade only back to the nearest edge, not to the target. Band width scales with the cube root of cost, so even tiny
costs justify sizeable bands. In practice, a buffer of about 10% of an average position (Carver) or a backtest-chosen
band cut turnover by roughly 5–30% at little cost to gross return.

### Cited Findings
- **[Theory] Davis & Norman (1990).** With proportional costs, "the optimal policy consists of an inaction region and a
  return to the closer boundary when rebalancing". Abel & Eberly (1996): "even tiny transaction costs lead to
  non-trivial inaction regions", and the region's size is "proportional to the cube-root of the price wedge for small
  wedges, which makes its derivative with respect to the wedge infinite". The sS inventory model (Arrow et al. 1951) is
  the original source of the idea. — [Novy-Marx & Velikov, NBER WP 20721, fn. 6](https://www.nber.org/papers/w20721.pdf)
- **[Theory] Asymptotics.** Janeček & Shreve (2004) expand the value function in powers of λ^{1/3}, where λ is the
  proportional cost, and give asymptotics for the no-trade boundary. — [Janeček & Shreve, *Finance and Stochastics* 8,
  181–206 (2004)](https://link.springer.com/article/10.1007/s00780-003-0113-4). Shreve & Soner (1994) note that no-trade
  regions scale with ε^{1/3}. — [Asymptotic Methods for Transaction Costs, *Risks* 12(4):64 (MDPI)](https://www.mdpi.com/2227-9091/12/4/64)
- **[Opinion/practice] Carver's buffering ("position inertia" in *Systematic Trading*).** Carver only trades "if my
  current position is outside of a buffer around the idealised position". He uses one width for all instruments, "10%
  of an average position", though "in theory it should be wider for expensive instruments and narrower for cheaper
  instruments". — [Carver, "Fast but not furious", qoppac, Feb 2023](https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html).
  In a comment: "Theoretically the optimal buffer size depends only on costs … I use a constant buffer size purely to
  make life simpler." — [qoppac comments, Apr 2017](https://qoppac.blogspot.com/2016/01/correlations-weights-multipliers.html)
- **[Evidence, own backtest] Carver's measured effect.**
  * Buffering cuts turnover by "about a 5% reduction for ewmac4 and more like 30% for the very slowest momentum rule".
  * Separately: "something we think has a turnover of over 60 (ewmac4) will actually end up with a turnover of more like
    50 after buffering. That is a 17% reduction."
  * Summary: "Buffering in a static system reduces turnover, and thus costs, by 17% on a very fast strategy."
  * Dynamic optimisation with an instrument-specific cost penalty is "more efficient reducing costs by around a third".

  — [qoppac, Feb 2023](https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html). (The 5% and 17%
  figures for ewmac4 do not reconcile in the post. The 17% is probably at portfolio level, after volatility scaling. Treat
  the range as 5–30%.)
- **[Opinion/practice] Buffers inside an optimiser.** Carver found his dynamic optimisation was trading more than he
  thought until he added position buffering, applied to tracking error: if tracking error is outside the buffer, "we'll
  trade … to bring our tracking error down to the buffered level (='trading to the edge of the buffer')". — [Carver, "Mr
  Greedy and the Tale of the Minimum Tracking Error Variance – Part two", qoppac, Nov 2021](https://qoppac.blogspot.com/2021/11/mr-greedy-and-tale-of-minimum-tracking.html)
- **[Opinion/practice] Robot Wealth.** Its no-trade buffer is chosen by maximising backtested after-cost Sharpe. A
  `trade_buffer` of 0.04 was optimal in a crypto stat-arb backtest and "quite stable across a decent range". The advice
  is to "pick a value a little higher than 0.04 to mitigate the risk that your out-of-sample performance will be
  worse". — [Robot Wealth, "A Simple, Effective Way to Manage Turnover and Not Get Killed by Costs"](https://robotwealth.com/a-simple-effective-way-to-manage-turnover-and-not-get-killed-by-costs)

### Inferences
- **[Inference] Band rule for one name.**
  * Let w* be the target weight (one slot, e.g. 1/10 of a side's gross) and w the current weight.
  * Trade only if |w* − w| > b·w_slot. If so, trade to w* ∓ b·w_slot (the nearest band edge), not to w*.
  * Suggested b = 0.10–0.25 of a slot. Carver's 10% is the floor; the cube-root law says a 5x cost difference (1 vs
    5 bp) implies a band only ~1.7x wider (5^{1/3}).
  * This applies to resizing and drift trades, not to entries and exits. For a fixed-slot book, resizes are probably a
    small part of the unspecified ~19.5%.
- **[Inference] Entries and exits.** For these, the band analogue is the rank or score hysteresis in Section 3: a buy
  zone and a wider hold zone.

### Gaps
- No primary-source text was retrieved for Leland (2000) or Constantinides (1986). Their results are known here only
  through the Davis–Norman and asymptotic literature cited above.
- Carver's figures come from his futures trend system (turnover in "average positions per year"). I found no measured
  buffering result for event-driven single-stock books.

---

## 3. Hold-while-edge-exceeds-cost: alpha decay, holding periods, and entries versus residual alpha

### Takeaway
The most effective documented single mitigation is hysteresis, not optimisation: buy only names in an extreme band, but
keep holding them while they stay in a wider band. Novy-Marx & Velikov found this the "single most effective simple cost
mitigation strategy". It cut one-sided monthly turnover from ~90% to ~55% for high-turnover anomalies and roughly
doubled net returns for the post-earnings drift and short-term combination strategies (PEAD itself: 0.26 → 0.35%/month,
or ~3.1 → 4.2% a year). For exit decisions, the cost to compare against is the round trip saved by not exiting and
re-entering, not the exit cost alone.

### Cited Findings
- **[Evidence] Novy-Marx & Velikov: the buy/hold spread.** Under an sS rule, "we only buy (sell short) stocks when they
  get into the top (bottom) 10%, and hold them by restricting sales … only for stocks that leave the top (bottom) 20%."
  The rule works "by holding (not selling) close substitutes to the stocks you would have bought, since there is not much
  of a difference in expected returns between stocks in the 75–80% range … and those in the 80–85% range." As the spread
  widens, "turnover and transactions costs reduction is even more dramatic, resulting in increasing net spreads and
  Sharpe ratios." — [Novy-Marx & Velikov, NBER WP 20721 (published RFS 29(1), 2016)](https://www.nber.org/papers/w20721.pdf)
- **[Evidence] NMV Tables (basic → buy/hold).** Columns: gross %/month, one-sided monthly turnover %, cost %/month, net
  %/month, with t-stat where reported. Annual figures are ×12. — [NMV WP 20721](https://www.nber.org/papers/w20721.pdf)

  | Strategy | Rule | Gross | Turnover | Cost | Net (t) | Net %/yr |
  |---|---|---|---|---|---|---|
  | PEAD (SUE) | basic | 0.72 | 35.1 | 0.46 | 0.26 | 3.1 |
  | PEAD (SUE) | 10/20 | 0.66 | 24.4 | 0.32 | 0.35 (2.26) | 4.2 |
  | PEAD (CAR3) | basic | 0.91 | 34.7 | 0.57 | 0.34 | 4.1 |
  | PEAD (CAR3) | 10/20 | 0.82 | 28.9 | 0.47 | 0.35 | 4.2 |
  | High-frequency combo | basic | 1.61 | 91.0 | 1.45 | 0.16 (1.11) | 1.9 |
  | High-frequency combo | 10/50 | 1.18 | 53.6 | 0.83 | 0.35 (2.83) | 4.2 |
  | Industry rel. reversals (low vol) | basic | 1.25 | 94.0 | 1.06 | 0.19 (1.41) | 2.3 |
  | Industry rel. reversals (low vol) | 10/50 | 0.95 | 58.8 | 0.67 | 0.28 (2.41) | 3.4 |
  | Short-run reversals | basic | 0.37 | 90.9 | 1.65 | −1.28 | −15.4 |
  | Short-run reversals | 10/50 | 0.28 | 57.1 | 1.00 | −0.72 | −8.6 |

  Short-run reversals stay negative: hysteresis cannot rescue a signal whose gross edge is below cost.
- **[Evidence] NMV, other results.**
  * "Most of the anomalies … with one-sided monthly turnover lower than 50% continue to generate statistically
    significant net spreads … Few of the strategies with higher turnover do."
  * Costs cut realised spreads by more than 1% of monthly one-sided turnover (round trip > 50 bp for value-weighted
    strategies; costs are Hasbrouck effective spreads, 1926–2013 cross-section).
  * Combining all three mitigations (cheap-stock universe, staggered rebalancing, buy/hold spread) cut turnover by 60% and
    costs by 59% on average, but "generally do[es] not improve on the single mitigation technique of the buy/hold
    spread", except for very high-turnover strategies.
  * The buy/hold spread is "largely absent from the academic literature though frequently employed in practice (e.g.,
    Dimensional Fund Advisors … MSCI has several indices that use it)."

  — [NMV WP 20721](https://www.nber.org/papers/w20721.pdf)
- **[Theory] Alpha half-life.** IC(h) = IC₀ e^{−λh}, with half-life t½ = ln 2/λ. "If you hold a position with decaying
  alpha, the marginal alpha you still earn shrinks each day, so there is an optimal holding period past which the
  position is no longer worth its risk and cost." — [Quant Memo, "Alpha Decay"](https://quantmemo.com/concepts/alpha-decay)
  (secondary explainer; it cites Grinold & Kahn and GP 2013).
- **[Evidence] Kakushadze & Tulchinsky.** In 4,000 real-life US equity alphas with holding periods of 0.7–19 trading
  days, returns showed no statistically significant dependence on turnover. Cost per share scaled as C ~ 1/T, and
  returns scaled with volatility as R ~ V^X, with X ≈ 0.8–0.85 for holding periods up to 10 days. — [Kakushadze &
  Tulchinsky, "Performance v. Turnover: A Story by 4,000 Alphas", *J. Investment Strategies* 5(2):75–89 (2016), arXiv
  1509.08110](https://arxiv.org/abs/1509.08110)
- **[Theory] Alpha decay in one asset.** In a one-asset MDP where lagged signals also predict returns, the gain from a
  cost-aware policy over the naive one is small when the lagged predictive coefficient ρ₁ ≪ ρ₀ (alpha concentrated in the
  first period). It is larger when ρ₁ is comparable to ρ₀. — [Ma & Smith, "On the Effect of Alpha Decay and Transaction
  Costs on the Multi-period Optimal Trading Strategy", arXiv 2502.04284](https://arxiv.org/html/2502.04284v1)

### Inferences
- **[Inference] Correct "hold versus exit" algebra for a book that will eventually exit anyway.**
  * Setup: expected alpha per session at age t is α(t) = α₀e^{−κt}, with κ = ln 2/h; cost per side is c. Remaining
    expected alpha from age t is A(t) = (α₀/κ)e^{−κt}. Total at entry is A(0) = 1.44·h·α₀.
  * *Exit, no replacement.* The exit cost c is paid now or later, so it is not a reason to exit. Hold while marginal
    alpha α(t) exceeds the marginal risk charge (and the slot's opportunity value). The rule "exit when remaining alpha <
    exit cost" double-counts c.
  * *Swap A for candidate B.* Exiting A now and entering B adds one round trip relative to holding A: B's entry plus B's
    eventual exit, since A's exit is paid either way. Swap only if A_B(0) − A_A(t) > 2c + m, where m is a margin for
    estimation error.
  * *Renewal.* If A's horizon expires and the next cohort re-signals the same name and side, exiting and re-entering
    costs 2c for nothing. Hold through and reset the horizon. This is the NMV buy/hold spread applied in time rather than
    across the cross-section.
- **[Inference] Entry gate.** Enter only if A(0) = 1.44·h·α₀ ≥ k·2c. Here k = 2–3 is opinion (Section 5) and is
  consistent with Carver's rule of spending at most ⅓ of pre-cost Sharpe on costs (k = 3).
  * At registered 5 bp per side: 2c = 10 bp, so require 20–30 bp expected gross edge per position over its life.
  * At live 1–2 bp: 2c = 2–4 bp, so require 4–12 bp.
  * With h = 4 sessions, the 5 bp case needs α₀ ≥ 3.5–5.2 bp per session at entry.
- **[Inference] Hold zone for this desk (NMV analogue).**
  * Buy zone: open a new position only if the desk's score or conviction is in its top band (e.g. top-k of the cohort's
    ranked names).
  * Hold zone: at horizon expiry, keep the position if the latest desk read on the name has the same sign and clears a
    looser threshold (e.g. top-2k or "still positive").
  * Proposed widths: NMV's 10/20 for mid-turnover and 10/50 for high-turnover. For a ~4-session-hold book, start at a
    hold threshold about 2x looser than entry.
  * Savings: each renewal saves 2c × slot weight. If a fraction q of the ~18% "horizon exit" turnover is followed by a
    same-name same-side re-entry within one cohort, the saving is ≈ 2 × q × 0.18 × annual turnover × c. Example: q = ⅓,
    turnover 54x, c = 5 bp gives ≈ 0.32% a year (≈ 0.10% a year at c = 1.5 bp).
- **[Inference] Combine new entries with residual alpha.** At each cohort, rank candidates together with existing
  holdings, scoring existing holdings by remaining A(t) plus a 2c incumbency bonus (the cost of replacing them). Fill
  slots from the top. This ranking implements the swap rule above. Israelov–Katz's agreement filter is a cheap variant:
  cancel a trade if the slower read on the name points the other way.

### Gaps
- No measured alpha-decay curve for LLM news signals on S&P 500 names was found. The book's own realised IC by session
  age would be needed to set h. NMV's PEAD rows are the closest published analogue: a monthly event-driven drift, much
  slower than ~4 sessions.
- I did not obtain Isichenko (2021) *Quantitative Portfolio Management* text on turnover and alpha decay, so nothing from
  it is quoted.
- Grinold & Kahn's specific holding-period formula was not retrieved.

---

## 4. Netting and crossing: hedge legs, SPY netting, hedge bands for beta drift

### Takeaway
I found no peer-reviewed source on hedge bands for single-stock books. The band and netting theory in Sections 1–2
carries over directly: net all same-day changes into one SPY order, and rebalance the hedge only when net beta leaves a
band. The hedge is ~17.5% of turnover, so cutting it is a large lever.

### Cited Findings
- **[Theory]** The no-trade-band result applies to any position with proportional costs, including the hedge position
  as a function of book beta. Band width scales with cost^{1/3}. — [Janeček & Shreve 2004](https://link.springer.com/article/10.1007/s00780-003-0113-4);
  [NMV fn. 6 on Davis–Norman / Abel–Eberly](https://www.nber.org/papers/w20721.pdf)
- **[Opinion/practice]** Carver buffers on portfolio tracking error and trades only "to the edge of the buffer". This is
  the portfolio-level analogue of a beta band. — [qoppac, Nov 2021](https://qoppac.blogspot.com/2021/11/mr-greedy-and-tale-of-minimum-tracking.html)
- **[Evidence]** Large-cap trading costs at an institutional manager were low: mean market impact just under 9 bp (median
  ~6 bp) across $1.7 trillion of live trades in 21 developed markets, 1998–2016. Large caps ~9 bp versus ~19 bp for
  small caps; cost rises with trade size at a decreasing (concave) rate. — [Frazzini, Israel & Moskowitz, "Trading
  Costs", SSRN 3229719 (2018)](https://papers.ssrn.com/abstract=3229719). Figures are via secondary summaries
  ([Institutional Investor](https://www.institutionalinvestor.com/article/b19hkzljqkhyw0/AQR-Investor-Worries-Over-Trading-Costs-May-Be-Overblown);
  [Yale Insights](https://insights.som.yale.edu/insights/how-big-investors-avoid-market-predators-and-keep-trading-costs-low));
  the primary text was not opened.

### Inferences
- **[Inference] Netting.**
  * Compute the target SPY position once per decision time from the post-trade book: H* = −β_book·NAV_gross (or the
    policy's stated net-exposure target).
  * Send one net SPY order. Do not attach a separate SPY hedge to each entry or exit, because simultaneous long entries
    and short exits cancel in SPY.
  * If hedge legs are currently booked per position, netting alone removes the offsetting part of the 17.5%.
- **[Inference] Hedge band.**
  * Rebalance SPY only when |β_net − β_policy| > b_β (in NAV-beta units), then trade back to the edge.
  * Starting value: b_β = 0.05–0.10 of NAV, chosen like Robot Wealth's buffer (maximise after-cost Sharpe in replay, then
    widen slightly).
  * With ~10 names a side, one entry or exit moves beta by roughly one slot weight × that stock's beta. A band of one
    slot means single-name churn rarely triggers a hedge trade.
- **[Inference] Discipline caveat.** The policy instruments (SPY, net exposure) are the owner's stated strategy. A
  hedge band changes *when* the hedge trades, not the exposure target. It still needs a CHANGELOG line that answers
  "could this change a decision?", because the band permits small temporary deviations of net beta.
- **[Inference] Internal crossing.** Internal crossing of opposite single-name orders (one cohort buying a name another
  is selling) is a form of netting. Aggregate target weights per name across cohorts before generating orders.

### Gaps
- No academic or practitioner source with measured results for beta-drift hedge bands was found.
- No source was retrieved for SPY's actual effective spread; the registered 5 bp may overstate the hedge leg's true
  cost.

---

## 5. Empirical size of the benefit, and practitioner rules of thumb

### Takeaway
Hysteresis and cost-aware rules typically recover a large share of the cost drag and can turn insignificant strategies
significant. They cannot rescue a signal whose gross edge is below cost. Practitioner rules cluster at "edge must
clearly exceed cost" and "spend no more than ⅓ of gross Sharpe on costs" (i.e. about 3x).

### Cited Findings
- **[Evidence]** NMV: the buy/hold spread is the single most effective simple mitigation. Turnover falls from ~90% to
  ~54–59% a month for high-turnover strategies, and the combined approach cuts costs 59% on average (see the table in
  Section 3). — [NMV WP 20721](https://www.nber.org/papers/w20721.pdf)
- **[Evidence]** GP: cost-aware dynamic trading raises net Sharpe from 0.46 (best static) to 0.58, and from −9.84 for
  cost-blind trading. — [GP 2013 Table II](https://w4.stern.nyu.edu/facdir/lpederse/papers/DynamicTrading.pdf)
- **[Evidence]** Frazzini–Israel–Moskowitz: actual institutional costs are "an order of magnitude smaller than previous
  studies suggest", which means academic cost estimates such as NMV's Hasbrouck spreads overstate costs for large-cap,
  algorithmically executed trades. — [FIM SSRN 3229719, via summaries](https://papers.ssrn.com/abstract=3229719)
- **[Evidence]** Kakushadze–Tulchinsky: across 4,000 alphas held 0.7–19 days, return does not depend significantly on
  turnover. — [arXiv 1509.08110](https://arxiv.org/abs/1509.08110)
- **[Evidence/theory, cost-aware optimisation]**
  * DeMiguel, Martin-Utrera, Nogales & Uppal (RFS 2020, 33(5):2180–2222): transaction costs increase the number of
    jointly significant characteristics, and combining more characteristics reduces turnover, giving "superior
    out-of-sample performance net of transaction costs". — [summary in "Markowitz portfolios under transaction costs" (UZH, 2025)](https://www.econ.uzh.ch/dam/jcr:cd9c657f-16d3-4155-872d-e5ebae7557ac/qref_2025.pdf)
  * Olivares-Nadal & DeMiguel show that a p-norm turnover penalty κ‖Λ(w − w₀)‖_p^p in mean-variance is equivalent to
    robust optimisation, and calibrate it to 50 bp proportional costs. — [Olivares-Nadal & DeMiguel, *Operations Research*](https://lbsresearch.london.edu/id/eprint/920/1/VDM%20Robust%20Perspective%20on%20Transaction%20Costs.pdf)
- **[Opinion] Carver's "speed limit".** "I don't want to allocate more than third of my expected pre-cost Sharpe Ratio
  towards trading costs … a maximum of around 0.13 or 0.10 SR annual units to be spent on costs", because realistic
  per-instrument Sharpe is ≤ 0.30–0.40. — [qoppac, Feb 2023](https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html)
- **[Opinion] Robot Wealth on switching.** "We need the expected return increase to be significantly bigger than our
  trading costs because we've got errors in our estimates … You always want to give yourself some wiggle room." — [Robot
  Wealth, "A general approach for exploiting statistical arbitrage alphas"](https://robotwealth.com/a-general-approach-for-exploiting-statistical-arbitrage-alphas)
- **[Opinion] Optimal entry and exit thresholds for an Ornstein–Uhlenbeck spread (Bertram).** These rise with
  transaction costs ("the more it costs to trade the larger the deviation has to be to enter a trade"). — [r/algotrading
  post implementing Bertram](https://www.reddit.com/r/algotrading/comments/kmw1qa/optimal_statistical_arbitrage_trading_research)

### Inferences
- **[Inference] Size of the prize for this fund.** Saving = Δturnover × c.

  | Turnover cut | c = 5 bp (registered) | c = 1.5 bp (live) |
  |---|---|---|
  | 17% (Carver's static buffer) | 0.34–0.58% a year | 0.10–0.17% a year |
  | ~35–40% (NMV-style hysteresis) | 0.7–1.4% a year | — |

  This is meaningful against a 1.6–3.4% a year drag. But it is only alpha if a signal with positive gross edge exists.
  With no proven net-alpha signal, turnover discipline mainly lowers the hurdle for the next signal.
- **[Inference] Starting parameters for a 10-name-a-side weekly book (to be pre-registered and tested on replay).**
  1. Entry gate: expected gross edge over the holding life ≥ 3 × round-trip cost at the registered rate (≥ 30 bp at
     5 bp per side). Live cost would allow ≥ 2x, but the registered rate governs.
  2. Renewal / hold zone: at horizon expiry, hold and reset the horizon if the latest read has the same sign and clears
     a hold threshold about 2x looser than entry (NMV 10/20 analogue).
  3. Swap rule: replace an incumbent only if candidate edge − incumbent remaining edge > 2c + margin.
  4. Resize buffer: no resizing unless |Δw| > 20% of a slot; trade to the band edge.
  5. Hedge: one netted SPY order per decision time, band b_β ≈ 0.05–0.10 NAV-beta, trade to the edge.
  6. Signal weighting: if multiple horizons or types exist, shrink each by 1/(1 + φ_k·const), using GP's aim formula,
     so faster-decaying components get less weight.
- **[Inference] Discipline.** Items 1–3 and 6 change which trades happen, so for the frozen fund they are a new protocol
  or a pre-registered research amendment, not an operational fix. Item 5 (netting) is closest to operational, but the
  band portion can still change decisions.

### Gaps
- No forum source (r/quant, Wilmott, QuantNet, Nuclear Phynance, Elite Trader, Quant StackExchange, X) with a citable,
  specific "edge must be 2–3x cost" quote, or with typical turnover figures for weekly-rebalanced stat-arb or event
  books, was retrieved in this pass. The 2–3x rule is supported here only by Carver's ⅓-of-Sharpe speed limit and Robot
  Wealth's "significantly bigger" remark.
- AQR practitioner notes beyond GP and FIM were not retrieved.
- Lopez de Prado's material on bet sizing and turnover was not retrieved.
- The FIM primary paper text was not accessible (SSRN fetch failed). Its figures come from secondary summaries, so
  verify them before citing them in a decision document.
