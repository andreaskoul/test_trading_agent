# Let stopped soft-news capital sit idle

*1 November 2026. This report draws on six research notes in
[`research_notes/Portfolio construction after a signal stop/`](../research_notes/Portfolio%20construction%20after%20a%20signal%20stop/),
the earlier [pipeline review](Fund%20pipeline%20against%20research%20and%20forums.md), and the rule A record
([read](research/p8/E_SOFT_READ.md), [diagnostics](research/p8/E_SOFT_DIAG.md)). "Amendment 3" means **Protocol 7B
Amendment 3**, the live-book consequence of Family E rule A. It is not Family E's own Amendment 3 on Finnhub timing.
Returns are % of NAV per year unless marked as bp per trade. "bp per trade" means bp per unit of position weight over
the 5-session test window. Derivations of my own are marked as such.*

**Recommendation: leave the freed weight uninvested.** Every framework that addresses the question gives the same
answer:

* Grinold–Kahn mean-variance sizing: a name with zero alpha gets zero weight, and the other names' optimal sizes do not
  change.
* The fundamental law with a transfer coefficient.
* Kelly sizing when the edge itself is estimated with error.
* Pod platforms and named systematic traders, as far as they are documented.

All of them treat gross exposure and the number of names as **outputs** of the signal and the risk budget. None treats
them as targets to refill.

**The fund's sizing rule already works this way.** A name's weight is score × confidence / 20 of NAV, and empty slots
are not filled, so Amendment 3 needs no rescaling. It does need one sentence it currently lacks: a soft view opens,
extends, enlarges and flips nothing.

**STOP is right, for a sturdier reason than the one recorded.** The desk's expected gross P&L on a soft entry is
(2a − 1)μ, where a is how often the desk trades in the news-day direction and μ is the follow-through in that
direction. A round trip of cost has to come out of that.

* The result is negative in every evidence scenario except the one the data reject: a desk that always follows the
  news-day direction, combined with the holdout mean.
* At the registered 5 bp per side, soft entries cost about **0.8–1.2% a year**, mostly through turnover.

**The read was weak on both legs.**

* The return leg used the live 4 bp round trip instead of the 10 bp the fund is scored at. It had 80% power only for
  effects near 15 bp, and it put 90% of its weight on 8-K items the desk does not trade.
* The agreement leg used a 60% bar, below the 67.5% break-even, on 12 trades. Twelve trades cannot tell either number
  from a coin.

**What should come next is not another soft-news read.** Forward data would need about **76,000 trades** to confirm a
4 bp edge. The next read should be on hard news, designed with the lessons below. After the stop, hard news is the
whole book, and at the fund's latency it is unproven.

## Zero alpha means zero weight, and the surviving names keep their size

### What the theory says

**Grinold–Kahn.** In the mean-variance framework, value added is α_P − λω_P² and the optimal residual risk is
**ω\* = IR/(2λ)** ([AnalystNotes, CFA study note](https://analystnotes.com/cfa-study-notes-calculate-the-optimal-level-of-residual-risk-to-assume-for-given-levels-of-manager-ability-and-investor-risk-aversion.html)).
My derivation from that formula: maximising α′h − λh′Σh gives h\* = Σ⁻¹α/(2λ). With independent residuals this is
h_i = α_i/(2λω_i²), and the squared information ratio is additive across independent bets: IR² = Σ(α_i/ω_i)².

**What follows if soft-news alphas are zero:**

* Their weights are zero.
* IR, the optimal total risk ψ\* and every hard-news weight are unchanged.
* The optimiser hands the vacated slots to nobody, because nothing in the objective rewards a fixed count.

**What follows if the stopped bets had some skill:** removing a fraction f of equally skilled bets lowers optimal risk
by √(1 − f). Theory never says to hold total risk constant when the opportunity set shrinks. A manager who keeps a
fixed tracking-error target anyway is implicitly lowering risk aversion: λ_implied = IR/(2ψ_target). The manager takes
the same risk on less edge.

**Transfer coefficient.** Clarke, de Silva and Thorley extend the fundamental law to IR = TC·IC·√BR. They show that
constraints which stop forecasts from becoming weights cut realised performance to **0.3–0.8 of what the law
predicts** ([Clarke, de Silva & Thorley 2002, FAJ](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/portfolio-constraints-and-the-fundamental-law-of-active-management)).
A rule that every slot must be filled is such a constraint. My derivation: if 40% of a book's risk sits in names with a
zero forecast, uncorrelated with the real forecasts, then TC ≈ √0.6 ≈ 0.77. That is a 23% cut in IR before the extra
costs.

**Kelly with an estimated edge.** Baker and McHale show that Kelly sizing "ignores uncertainty in the probability of
winning" and that "the size of the bet should be shrunk in the presence of parameter uncertainty"
([Baker & McHale 2013, Decision Analysis](https://ideas.repec.org/a/inm/ordeca/v10y2013i3p189-199.html)). Kan and Zhou
find that estimation risk "completely alters" the two-fund recommendation: holding the riskless asset plus the
*sample* tangency portfolio is never optimal
([Kan & Zhou 2007, JFQA](https://ideas.repec.org/a/cup/jfinqa/v42y2007i03p621-656_00.html)). Rob Carver sets the
risk target equal to the expected Sharpe ratio. He recommends half of it, and calls Sharpe estimates with a 95% range
of −0.16 to 0.36 "effectively worthless"
([Carver, risk target](https://qoppac.blogspot.com/2020/03/how-much-risk-should-we-take.html);
[Carver, estimation error](https://qoppac.blogspot.com/2023/12/portfolio-optimisation-uncertainty.html)).

Applied to soft news (my derivations, Gaussian, one period):

* With an uncertain mean m of variance s², growth is maximised at f\* ≈ m/(σ² + s²). Net of a 4 bp round trip,
  m ≈ −0.3 bp, so **f\* ≤ 0**: no position.
* The factor that shrinks a plug-in bet to minimise squared error is k = t²/(1 + t²). It is **0.45** on the gross
  estimate (t = 3.7/4.1 = 0.90) and **0** on the net estimate (t ≈ −0.07, wrong sign).
* Half-Kelly keeps 75% of the maximum growth rate at 25% of the variance, because g(k·f\*) = (2k − k²)·g(f\*).

**Redistribution is a leverage decision, not a reallocation.** Scaling the surviving hard-news positions by 1/(1 − f)
leaves IR unchanged before costs. It multiplies risk and costs by 1/(1 − f). It does not speed up learning either: a
book's t-statistic is SR·√T, which does not depend on leverage.

It would also lever a signal that has not been validated:

* Family E's earnings-continuation module had an IC of 0.025 (p 0.24) and was −19 bp net at the 20 bp stress cost.
* The hard 8-K module showed +54.8 bp at p 0.18 on only 221 events.

Neither passed ([validation read](research/p8/E_VALIDATION.md)). With a sceptical prior on the hard-news edge, Kelly
under estimation error says current sizes are already at or above the optimum. It does not say to scale up.

### Three ways to use the freed weight

The table below is illustrative. Assumptions: 20 names at 5% of NAV each; 8 of them are soft; idiosyncratic volatility
is 30% a year per name. The 30% is my conversion of the E3 per-event 5-session standard deviation of about 445 bp
(445 × √(252/5) ≈ 32%) ([diagnostics](research/p8/E_SOFT_DIAG.md)).

| Option | Names | Weight per name | Stock gross | Idiosyncratic volatility | IR relative to A | Verdict |
|---|---|---|---|---|---|---|
| Before the stop | 20 | 5.0% | 100% | 0.30·0.05·√20 = **6.7%** | — | — |
| **A: leave uninvested** | 12 | 5.0% | 60% | 0.30·0.05·√12 = **5.2%** | 1 | consistent with all frameworks above |
| B: fill slots with lower-ranked or zero-forecast names | 20 | 5.0% | 100% | 6.7% | ≈ 0.77 before costs | dominated: more variance and more cost, no more mean |
| C: scale up the survivors | 12 | 8.3% | 100% | 0.30·0.083·√12 = **8.7%** | 1 before costs, lower after | a 1.67× leverage bet on an unproven signal |

Campbell, Lettau, Malkiel and Xu show that firm-level variance has grown, so more names are needed for the same
diversification. The volatility of a typical two-stock portfolio rose far more than that of a 50-stock portfolio
([Campbell et al. 2001, NBER w7590](https://www.nber.org/papers/w7590.pdf)). Option C goes in the wrong direction on
that axis too.

### What the fund already does, and the two places weight moves without a decision

**By construction, the stop leaves capital idle.** The weekly book enters only non-zero scores, at most 10 a side, each
at score × confidence / 20 of NAV, and "there is no ridge fill: a week with few views is a small book"
([PROTOCOL_fund.md](research/PROTOCOL_fund.md)). The position-lifecycle engine (`fund/lifecycle.py`) takes those
weights as candidates. Every one of its caps can only shrink weights:

* sector net is shrunk pro rata;
* the heavy leg is shrunk under the dollar-net cap;
* gross including SPY is scaled down to 1.8.

Idle capital earns the T-bill, so its excess return in the scoring is exactly zero. The SPY hedge shrinks
mechanically with the stock book's beta. The owner's sleeve is untouched, as policy requires.

**Two channels move weight anyway**, and both should be logged rather than changed:

1. **Fewer capacity exits.** With fewer new entries competing for the 10 slots a side, fewer carried positions are
   closed for capacity. This moves weight forward in time, not upward in size. It agrees with the hold-while-edge logic
   in the turnover section below: each churn avoided saves a round trip.
2. **Dollar-net shrinkage.** If the suppressed soft names fall mostly on one side, the dollar-net cap (≤ 10% of stock
   gross) shrinks the opposite leg pro rata. Gross then falls by more than the soft share.

**Soft positions are a larger share of entries than of holdings** (my inference). Soft positions live 3–5 sessions.
Hard positions live up to 25 sessions, and structural ones up to 63. So soft positions are a much smaller share of
**held** gross than their roughly half share of **entries**. The stop is mainly a cut in turnover, and only secondarily
a cut in gross.

**One gap needs closing before the merge.** Rule A says cohorts "do not enter" soft names
([PREREG_family_E.md §5](research/PREREG_family_E.md)). The lifecycle's re-selection rules let a view on a name
already held do three things:

* a new same-side event extends the horizon and raises the weight to max(old, new);
* an opposite view closes the position;
* an opposite view opens a new position on the other side.

Each of these spends a trading cost. If the triggering view is soft, the stop's own evidence says it buys nothing. The
amendment text should therefore say that **a soft view is treated as no view: no entry, no extension, no increase and
no flip.** That also matches the earlier review's verdict to "hold through soft adverse news". It needs to be written
before any 7B outcome is examined.

## Conviction weighting needs a record the desk does not yet have

**Every standard sizing rule is proportional to skill.**

* Grinold's bridge from score to expected return is α = IC × σ × z
  ([Ding & Martin, NYU](https://math.nyu.edu/inmemoriam/avellaneda/FundamentalLawFT.pdf)).
* Mean-variance (α/σ²), risk parity (α/σ), proportional (α) and Kelly (μ/σ²) all scale with IC.

So weighting by conviction cannot rescue a signal whose net IC is about zero. It can only allocate a real edge better.

**The best evidence that conviction pays comes from managers with proven skill.** Managers' "best ideas" beat the
market by **2.8–4.5% a year**, and beat the rest of their own portfolios, most of which "do not exhibit significant
outperformance". The effect is strongest "for funds that have outperformed in the past"
([Anton, Cohen & Polk, "Best Ideas"](https://personal.lse.ac.uk/polk/research/bestideas.pdf)). Skill was established
first; conviction weighting came after.

**Most professionals show no sizing skill.** Paleologo's conviction profitability ratio compares the realised return of
high-conviction names with low-conviction ones. It is **1 or less for most PMs, and the best rarely exceed 2**. PMs
have "primarily selection skills" and "moderately-positive-to-moderately-negative sizing skill"
([Chasing the Vig review of Paleologo 2021](https://chasingthevig.substack.com/p/advanced-portfolio-management-book)).
Other data point the same way:

* Over 3 years and 76 active equity portfolios, only **18%** of PMs made more value-adding than value-destroying
  decisions across picking, entry, sizing, scaling and exit
  ([Essentia, CFA Institute](https://rpc.cfainstitute.org/blogs/enterprising-investor/2022/manager-selection-the-power-of-payoff)).
* Among equity long/short managers, "very few … sustain meaningfully higher than 50% hit ratios". The win/loss ratio
  is about 6× more variable than the hit ratio
  ([Resonanz Capital](https://resonanzcapital.com/insights/decoding-manager-success-an-analysis-of-equity-long/short-returns)).

Payoff and sizing do the work, and most managers are not good at sizing.

**Vendor data is mixed and self-interested.** Novus found 57.5% of managers beat equal-weighted versions of themselves
and 41% lost to them ([Novus](https://www.novus.com/blog/skill-prediction-hedge-fund-position-sizing)). Alpha Theory
puts the median gain from sizing at +2.0% ([Alpha Theory](https://www.alphatheory.com/blog/the-ultimate-guide-to-position-sizing---part-1-sizing-matters-but-how-much)).
Both firms sell sizing software.

**For the fund:** names are capped at 10% of NAV, which is about 5.5% of gross at 1.8×. Pods cap names at 1–3% of
gross (section 4). Score × confidence sizing is a concentrated conviction bet, and the desk's conviction ratio has
never been measured.

**Shrinkage puts the "drop or keep small" question in numbers.** Take the holdout mean of 11.4 bp with standard error
5.4 bp, and a prior centred on zero with spread τ (my calculation):

| Prior spread τ | Shrink factor τ²/(τ² + SE²) | Posterior gross | Net of 4 bp | Desk's capture at a = 7/12 |
|---|---|---|---|---|
| 2 bp | 0.12 | 1.4 bp | −2.6 bp | 0.2 bp gross |
| 3 bp | 0.24 | 2.7 bp | −1.3 bp | 0.4 bp gross |
| 5 bp | 0.46 | 5.3 bp | +1.3 bp | 0.9 bp gross |

Only a generous prior keeps the net positive. Even then the desk's share, (2a − 1) × 5.3 bp, is below cost. Harvey
and Liu say the same in testing terms: "marginal Sharpe ratios are heavily penalized … The marginal Sharpe ratio
strategies should be thrown out"
([Harvey & Liu, "Backtesting"](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)).

**Practitioners keep a small position only to learn, and pay for it as research.** Robot Wealth's narrow-edge strategy
"started small … only after proving itself live was the size increased"
([Better System Trader ep. 201](https://bettersystemtrader.com/201-getting-serious-about-part-time-trading-kris-longmore)).
The fund gets that learning free: rule A keeps every suppressed entry as a counterfactual row. The P8 plan's
go-live rule D already encodes the right sizing:

* each module enters at **half its validation IC**;
* ψ = IR₀/(2λ);
* the book starts at **ψ/2**.

That is Grinold–Kahn plus half-Kelly. Keep it.

## The stop is a turnover cut worth about 1% a year at the registered cost

### What soft entries are worth to the desk

In the earlier review, the book's new-entry notional was about **26× NAV a year**, and about half of the 63 entries to
30 October were soft or "other". That puts soft-entry notional G_s at about **13× NAV a year** (10–14× on the 37–52%
range of soft shares). This is a small-sample estimate. The annual contribution of soft entries is

$$\text{contribution} \;=\; G_s\big[(2a-1)\mu - k\big]$$

where k is the round-trip cost. Hedge trades are excluded, so every negative row below is understated.

| μ (bp, news-day direction) | Desk agreement a | Desk gross (bp) | Net at live k = 2–4 bp | Net at registered k = 10 bp | %/yr at live k | %/yr at registered k |
|---|---|---|---|---|---|---|
| 11.4 (holdout) | 1 (always follows) | 11.4 | +7.4 to +9.4 | +1.4 | +0.96 to +1.22 | +0.18 |
| 11.4 (holdout) | 7/12 (observed) | 1.9 | −0.1 to −2.1 | −8.1 | −0.01 to −0.27 | **−1.05** |
| 3.7 (all data) | 1 | 3.7 | −0.3 to +1.7 | −6.3 | −0.04 to +0.22 | **−0.82** |
| 3.7 (all data) | 7/12 | 0.6 | −1.4 to −3.4 | −9.4 | −0.18 to −0.44 | **−1.22** |

**Only the first row pays.** It needs both the holdout mean to be true and a desk that always trades the news-day
direction, and the evidence rejects both. Even a mechanical "always follow the news day" rule (row 3) breaks even at
live cost and loses **0.8% a year at the cost the fund is scored on**.

**Soft lots are also a large share of turnover** (my estimate). New entries are about 45% of one-way turnover, and soft
positions exit within days. So soft entries plus their exits are roughly **40% of the book's 40–68× NAV turnover**,
about 20–26× NAV a year. That is **1.0–1.3% a year at 5 bp per side**, or 0.3–0.4% at 1.5 bp per side.

**This corrects the earlier review.** It put soft news at −20 to −44 bp per unit of weight, from a 2023–26 workshop
paper. The fund's own 13,860 events say the gross follow-through is about +3.7 bp. **The case for the stop is cost and
variance, not negative drift.**

### What the turnover literature says

**Gârleanu and Pedersen.** With quadratic costs and decaying signals, the optimal policy is to "aim in front of the
target" and "trade partially toward the current aim". It down-weights fast-decaying signals. In their commodity test
it reached a net Sharpe of **0.58**, against **0.46** for the best static rule and **−9.84** for cost-blind Markowitz
([Gârleanu & Pedersen 2013, JF](https://w4.stern.nyu.edu/facdir/lpederse/papers/DynamicTrading.pdf)).

**No-trade bands.** At the fund's paper size, costs are linear, not quadratic. With linear costs the optimum is a
no-trade band whose width scales with the **cube root** of cost
([Janeček & Shreve 2004](https://link.springer.com/article/10.1007/s00780-003-0113-4)). Carver's buffer of 10% of an
average position cut turnover by **5–30%**, about 17% on a fast system
([Carver, "Fast but not furious"](https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html)).

**Buy/hold spreads.** Novy-Marx and Velikov find the buy/hold spread the "single most effective simple cost mitigation
strategy": buy in the top decile, hold until the name leaves a wider band
([NBER w20721](https://www.nber.org/papers/w20721.pdf)).

* For post-earnings drift it lifted net returns from 0.26% to **0.35% a month**.
* For short-run reversals, a signal whose gross edge is below its cost, it moved net returns from −1.28% to only
  **−0.72% a month**.

**Hysteresis cannot rescue a signal that does not cover its cost. That is soft news here, so stopping beats banding.**

**Hold-while-edge, done correctly** (my algebra on these sources):

* An exit cost is paid sooner or later, so it is never a reason to exit.
* Swap an incumbent for a candidate only if the candidate's edge minus the incumbent's remaining edge exceeds one extra
  round trip plus a margin.
* When a horizon expires and the same name is re-signalled on the same side, hold through. That saves a full round
  trip.

**Entry gate.** Practitioners want lifetime edge well above cost. Carver spends at most a third of pre-cost Sharpe on
costs ([Carver](https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html)). Robot Wealth wants
the expected gain "significantly bigger than our trading costs"
([Robot Wealth](https://robotwealth.com/a-general-approach-for-exploiting-statistical-arbitrage-alphas)). At the
registered 10 bp round trip, that means **20–30 bp of expected edge** per position. Soft news delivers a tenth of that.

**These belong to the next protocol, not to Amendment 3.** Renewal hold-through, one netted SPY order with a beta band,
and an entry gate all change decisions. The frozen book already has a 25% no-trade band on cap-driven rebalances.

## Pods run 25–150 names, 1–3% caps and gross as an output

**All the numbers in this section are second-hand.** Firms do not publish PM limits.

**Book shape.**

* Brett Caughran (ex-Citadel, D.E. Shaw, Two Sigma): platforms run **400–600% gross**, books turn over **5–10× a
  year**, and returns target **60–65%+ idiosyncratic**. A Tiger-style 10×15 book "needs to become something like 25×50"
  at a pod ([Caughran, "Beat the Pods"](https://www.linkedin.com/pulse/beat-pods-7-point-recipe-single-managers-fundamental-edge)).
* An anonymous newsletter reports single-name caps of **1–3% of gross**, industry caps of 5–15%, and liquidity caps of
  5–10% of ADV ([Quant Enthusiasts](https://youngandcalculated.substack.com/p/risk-management-inside-a-pod-how)).
* WSO posters describe **120–150 names** under volatility targets of **5–7%**, because "the only way to sufficiently
  reduce volatility is by having a sufficient number of positions"
  ([WSO](https://www.wallstreetoasis.com/forum/hedge-fund/number-of-positions-held-by-a-pm-in-ls-pod)).

**Drawdown rules.**

* At Millennium, "if you lose 5% … you'll usually get your capital allocation cut. If you lose 7.5% you'll be out"
  ([eFinancialCareers](https://www.efinancialcareers.com/news/2021/02/how-to-get-a-job-at-hedge-fund-millennium),
  search snippet).
* A mid-single-digit loss halves an allocation ([Capital Gains](https://capitalgains.thediff.co/p/multimanagerpodhedge-fund-101)).
* Paleologo: an IR of about 1 "with left-tail control" is the survival bar, and about 20% of PMs leave each year
  ([Odd Lots transcript](https://podscripts.co/podcasts/odd-lots/how-to-succeed-at-multi-strategy-hedge-funds)).

**Idle capital: no documented source says a pod must refill gross after losing ideas.** The documented mechanics are
all asymmetric: a ceiling on gross, mechanical cuts after drawdowns, and more capital "up to a point" after success.

* Paleologo's book compares unit-GMV with unit-dollar-volatility targeting (§6.6). It plots deployed capital falling
  as drawdown deepens, and says leverage decisions on platforms "are the responsibility of the firm"
  ([Wiley reading sample](https://content.e-bookshelf.de/media/reading/L-17016607-93ad8eb52e.pdf)).
* Caughran: "as anomalies become smaller, the bar should be higher for ideas in your portfolio".
* An anonymous r/quant snippet describes the opposite pressure: a CIO's alpha-capture book "increases that pod's size"
  when a PM refuses to ([r/quant](https://www.reddit.com/r/quant/comments/1r1utpr/senior_quants_how_did_you_survive_the_20182020)).
  That is a business incentive around capital charges and payouts, not portfolio theory, and a paper overlay has
  neither.

**Event books.** Earnings dominate pod catalysts. Print days are "2% of year's trading days but generate ~20%
idiosyncratic volatility" ([Caughran](https://www.linkedin.com/pulse/beat-pods-7-point-recipe-single-managers-fundamental-edge)).
Paleologo lists product launches among catalysts. He warns that PMs "over-trade", and that "positioning too early
exposes the PM to unwanted risk"
([reading sample](https://content.e-bookshelf.de/media/reading/L-17016607-93ad8eb52e.pdf)). Pod event edge comes from
being right **before** the print ([Mergers & Inquisitions](https://mergersandinquisitions.com/long-short-equity)).
For the fund, that is R5's job, not the weekly news desk's.

**For the fund:** 10 names a side at up to 10% of NAV is a Tiger-cub concentration run on an LLM's unproven selection.
After the stop it will hold fewer names. The pod lesson is not to raise the cap to compensate. Breadth comes only from
more independent views with skill. A book-level drawdown de-grossing rule is a reasonable next-protocol idea, and it is
the owner's policy call. It is not part of Amendment 3.

## Rule A was decided by noise on one leg and generosity on the other

The same evidence gives different verdicts depending on the basis it is judged on:

| Basis | Estimate (bp) | Hurdle (bp) | z | One-sided p | Reading |
|---|---|---|---|---|---|
| Registered read: pooled holdout, live round trip | 11.4 ± 5.4 | 4 | 1.37 | 0.085–0.09 | return leg passes |
| Holdout at the registered round trip | 11.4 ± 5.4 | 10 | 0.26 | 0.40 | fails |
| All E3 events (fit + holdout), live | 3.7 ± 4.1 | 4 | −0.07 | 0.53 | fails |
| Finnhub only (the desk's actual input) | 15.1 ± 27.5 | 4 | 0.40 | 0.34 | uninformative |
| The desk's capture at a = 7/12, holdout μ | 1.9 | 4 | — | — | below cost |

**1. The hurdle was generous.** The read tested against the live 4 bp round trip. The fund is scored at 5 bp per side,
a 10 bp round trip, and the go-live gate reads scored returns. The live figure is defensible economics, but the
registered cost is the basis on which the book is judged. Reads should report both.

**2. The test had little power where it mattered.** With a 5.4 bp standard error and a one-sided 10% test, 80% power
needed **μ ≥ 15.5 bp**. Between 4 and 10 bp, the economically relevant range, passing was close to a coin flip. A pass
would also have been weak evidence: at p = 0.0895 the Bayes factor is at most **1.7** ([diagnostics](research/p8/E_SOFT_DIAG.md)).

**3. The thing estimated was not the thing traded.**

* 90% of the weight sat on 8-K items 5.02 (officer changes) and 1.01 (material agreements). These are filings with
  legal force, which the classifier's own definition of "hard" ("a reported or official fact with numbers or legal
  force") arguably covers.
* The desk trades Finnhub stories, and there the estimate is ±27.5 bp.

The proxy describes neither the desk's input nor its label.

**4. Holdout and fit disagree, and the holdout is driven by two years.** E3 chose nothing on its fit windows, so pooling
fit and holdout is statistically legitimate.

* The 8-K estimate moved from −1.2 bp (2016–21) to +11.0 bp (2022–25), a difference with z = 1.5.
* By year: 2023 gave +29.2 bp and 2024 +19.3, against −1.0 in 2022 and −2.3 in 2025 (heterogeneity Q = 6.8,
  p = 0.08).
* McLean and Pontiff find returns **26% lower out of sample and 58% lower after publication**
  ([McLean & Pontiff 2016](https://tevgeniou.github.io/EquityRiskFactors/bibliography/AcademicReviewFactor.pdf)). That
  takes 11.4 bp to 8.4 or 4.8 bp.

*Steelman:* if 2022 onward is the relevant regime, the holdout is the right estimate. Against that, 2025's −2.3 bp
contradicts a durable new regime. And LLM-era news edges are shrinking, not growing (next section).

**5. The agreement leg was both miscalibrated and underpowered.**

* The 60% bar sits below the break-even a\* = (1 + c/μ)/2 = **0.675**, and a\* = 0.94 at the registered cost.
* For 7 of 12 agreements, the Wilson interval is **[0.32, 0.81]**. With a uniform prior, P(a > 0.675) = **0.22** and
  P(a > 0.5) = 0.71. The binomial p against a coin is 0.39.
* Separating a = 0.675 from 0.5 with 80% power at one-sided 5% needs **51 trades** (exact binomial).
* The (2a − 1)μ formula also assumes that disagreeing trades lose exactly μ, whatever the size of the move. If the
  desk's 5 disagreements were informed fades, its P&L could beat the formula. If its agreements cluster on small moves,
  its P&L is worse. Five trades cannot tell which.

**The direct measure is out of reach.** Measuring desk-side P&L per soft trade directly would need about **76,000
trades** to confirm a 4 bp net edge at a 445 bp standard deviation (one-sided 5%, 80% power). At roughly 400 soft
entries a year, that is about 190 years.

**6. The programme has run many reads.** About 38 locked reads have been run, with none passing.

* The deflated-Sharpe expected maximum z under the null is **2.17 for 38 independent trials** and **2.53 for 100**
  ([Bailey & López de Prado](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)). Rule A's z of 1.37 is below
  what pure noise produces as a maximum.
* Harvey, Liu and Zhu ask new factors to clear **t > 3** ([NBER w20592](https://www.nber.org/papers/w20592)).
  Bonferroni at 38 reads needs z = 3.01.
* Zero passes is informative in itself (illustrative, because the reads differ in α and share data). If every read
  sat exactly at its null boundary with nominal α = 0.10, P(no passes) = 0.9³⁸ = **1.8%**. At α = 0.05 it is 14%.
  So the tested effects mostly sit **below** their cost hurdles, not at them. The programme's base rate of true,
  tradable effects is low, and the next read deserves a lower prior.

**Verdict: STOP is right on every basis.** The reason actually recorded, agreement of 58% < 60%, is the weakest of
them.

## The news literature expected near-zero soft follow-through, and hard news is not safe either

**Soft news on the hard–soft split.** The literature agrees on the direction of the split. Moves on identified
fundamental news in S&P 500 stocks continue, while moves without news reverse
([Boudoukh et al., NBER w18725](https://www.nber.org/papers/w18725)). Stale news reverses within a week
([Tetlock 2011](https://ideas.repec.org/a/oup/rfinst/v24y2011i5p1481-1512.html)). For story-driven categories, a 2023–26
LLM-labelled study finds reversal after the publication day
([Kargarzadeh et al. 2026, arXiv 2608.14014](https://arxiv.org/html/2608.14014); a workshop paper, not peer-reviewed):

* product launches: −0.22% on days 1–5 and −0.73% on days 6–20;
* macro read-throughs: −0.22% and −0.76%;
* leadership: −0.10% and −0.51%.

The other soft classes look the same:

* M&A rumours reverse by about **twice the initial pop** over three quarters
  ([CLS Blue Sky](https://clsbluesky.law.columbia.edu/2021/03/17/the-ma-rumor-productivity-dip)).
* CEO-change announcements move prices 25–50 bp on the day, with no documented drift afterwards
  ([NY Fed SR 166](https://www.newyorkfed.org/research/staff_reports/sr166.pdf); 1979–95 sample).

**The fund's +3.7 bp is better than this literature predicted, not worse.** The supposed soft-news loss was always the
weakest number in the earlier review.

**Speed: large caps price news within a day.**

* Daily news predicts returns for 1–2 days. Weekly-aggregated news predicts for about a quarter, and negative news is
  slow, up to about 13 weeks ([Heston & Sinha, FEDS 2016-048](https://www.federalreserve.gov/econres/feds/news-versus-sentiment-predicting-stock-returns-from-news-stories.htm)).
* Bloomberg's research: "For large cap stocks … less chance to capture anything after a day"
  ([Bloomberg](https://www.bloomberg.com/professional/blog/can-get-edge-trading-news-sentiment-data)).
* Next-day S&P 500 news-sentiment trading made 21% a year gross, but "transaction costs eliminate profitability"
  ([CXO summary of Tetlock et al. 2008](https://www.cxoadvisory.com/sentiment-indicators/financial-news-sentiment-predicts-stock-returns/)).
* The headline LLM study, Lopez-Lira and Tang, shows decay as LLMs spread
  ([arXiv 2304.07619](https://arxiv.org/html/2304.07619v6)):
  * its Sharpe ratio fell from **6.54 (2021Q4) to 1.22 (2024)**;
  * it loses money at 20 bp round trip;
  * the drift after earnings headlines is **−4.7 bp**, not significant;
  * drift survives only in low-salience categories: insider trades +26.3 bp, dividends +22.3 bp.

**Hard news has some support, all of it weak at the fund's latency.**

* Martineau finds post-earnings drift in large stocks "non-existent since 2006"
  ([Martineau 2022](https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf)).
* Jiang, Li and Wang find drift "for several days … profitable after transaction costs", but the magnitude for large
  caps could not be verified ([SSRN 2679614](https://papers.ssrn.com/abstract=2679614)).
* Anomaly returns are 50% higher on news days ([Engelberg, McLean & Pontiff 2018](https://ideas.repec.org/a/bla/jfinan/v73y2018i5p1971-2001.html)).
* The fund's own hard 8-K module showed +54.8 bp at a 10-session horizon on 221 events (p 0.18). That is the largest
  point estimate in the family, and also the least powered.

**For a slow trader, the shapes with any support are:**

* weekly-aggregated tone with holds of one to three months;
* a short tilt on negative hard news;
* low-salience events.

None has been tested at the fund's Thursday-close entry, about 23 hours after the news.

## What forums and practitioners add, and how little of it is evidence

The material below is **opinion**. It agrees with the evidence above. It is not independent proof of it.

| Claim | Who | Type | Weakness |
|---|---|---|---|
| Volatility "is an output of our ideas"; he cuts gross and "low conviction names" | Pod PM, Oct 2026 AMA ([WSO](https://www.wallstreetoasis.com/forum/hedge-fund/im-a-pod-pm-ask-me-anything)) | WSO-certified, anonymous | One person; one thread |
| His top 5 positions "return … in line with the median name" | Same | Anecdote | Self-report, no data |
| "Gross exposure is a function of portfolio vol"; reduce when signals are "very average" | Self-described multi-strategy partner ([r/SecurityAnalysis](https://www.reddit.com/r/SecurityAnalysis/comments/47yrup/iama_partner_with_a_multi_strategy_hedge_fund)) | Anonymous | Search snippet only, cut off mid-sentence; identity unverified |
| Position size follows forecast strength; gross is never refilled | Rob Carver ([qoppac](https://qoppac.blogspot.com/2021/12/my-trading-system.html)) | Named practitioner | Futures, not single stocks |
| "Trading costs are guaranteed, while your trading edge is uncertain" | Kris Longmore ([Robot Wealth](https://robotwealth.com/reduce-trading-costs-and-boost-profits-with-the-no-trade-region-strategy)) | Named practitioner | Crypto and FX examples |
| A 1% coin-flip edge needs "nearly 7000 trials to be 95% sure" | Kris Abdelmessih ([Moontower](https://moontower.substack.com/p/primer-3-the-nature-of-edge)) | Named practitioner | Illustrative arithmetic |
| "4-5 bps round trip" can turn a live edge to zero | Reddit user ([u/PapersWithBacktest](https://www.reddit.com/user/PapersWithBacktest)) | Anonymous | Snippet; thread unidentified |
| Score ≥ 7 entries are "buying after the good news is already priced in" | r/algotrading ([thread](https://www.reddit.com/r/algotrading/comments/1ublsph/my_7_newssentiment_strategies_are_all_losing_to_a)) | Anonymous | Snippet; replies unseen |
| An LLM decision-maker biases "to keeping too much cash" | HN ([item 49605822](https://news.ycombinator.com/item?id=49605822)) | Anonymous builder | One anecdote |
| "You cannot backtest LLMs" | HN ([item 46154491](https://news.ycombinator.com/item?id=46154491)) | Anonymous | Opinion, though well-founded |
| "Cash is a position … If it's not perfect, pass" | Elite Trader ([list](https://www.elitetrader.com/et/threads/top-50-trading-quotes.388762)) | Folk wisdom | Discretionary context |

**How weak are these sources?**

* **Reddit:** every quote is a search-engine snippet, because page fetches were blocked. Context, handles and some
  dates are unchecked.
* **Other forums:** Wilmott, QuantNet and Nuclear Phynance returned nothing relevant.
* **Pod limits:** all second-hand, from press snippets, an anonymous Substack and WSO posters.
* **Paleologo's book:** seen only through its table of contents, a reading sample and a review. His comparison of
  sizing rules (proportional and risk-parity beating mean-variance) comes from search excerpts and is unverified.
* **Books not read:** Grinold–Kahn, Isichenko and Qian–Hua–Sorensen were not accessed; their formulas are standard but
  unquoted. Kan–Zhou's closed-form scaling is unverified, so it is not used.
* **Other secondary sources:** Frazzini–Israel–Moskowitz cost figures come from summaries. Kargarzadeh et al. is not
  refereed.
* **Vendors:** Novus and Alpha Theory sell what they measure.

**The one forum warning that cuts the other way** is the HN point about LLM inaction. The fund's stop is mechanical,
so it does not apply here. But gross should be logged, so that a shrinking book is always explained by rules, never by
the model's reluctance.

## Recommendations for Amendment 3

| # | Decision | Recommendation | Basis | Change class |
|---|---|---|---|---|
| 1 | Apply STOP | Merge as registered, effective from the as-of 2026-11-04 desk together with 7B Amendment 2. Merge today (a weekend) or Mon/Tue 2–3 Nov 02:00–15:30 UTC; the owner merges `main` | Rule A; CLAUDE.md rules 14–15 | Pre-registered amendment; CHANGELOG: "yes, changes decisions, mechanically" |
| 2 | Freed weight | **Leave uninvested.** Do not rescale hard positions, refill from lower ranks or the ridge, or change caps | Grinold–Kahn, TC, Kelly, pod practice | None needed; the existing rule already does this |
| 3 | Soft views on held names | A soft view opens, extends, enlarges and flips nothing | Each of these pays a cost with no edge | Write into the amendment text before the merge |
| 4 | Contract test | On a recorded cohort, removing the soft names leaves every hard name's weight identical, except where the sector or dollar-net caps bind | CLAUDE.md rule 12 | Test |
| 5 | Logging | Per cohort: stock gross, names per side, suppressed names with their would-be weights, capacity exits avoided, cap-induced shrinkage | Makes the two implicit channels visible | Operational |
| 6 | Counterfactual rows | Descriptive only. No forward path to re-admission: about 76,000 trades are needed. **Close the soft-news follow-through question; no re-read** | Power arithmetic | None |
| 7 | Sizing | No change in the frozen book. Pre-register a conviction-ratio read (high vs low score × confidence) for the mid-April 2027 judgement | Paleologo; Best Ideas | Pre-registration |
| 8 | Turnover | Next protocol: hold through on same-name, same-side renewal; one netted SPY order with a beta band; entry gate ≥ 2–3× the registered round trip | Gârleanu–Pedersen, Novy-Marx–Velikov, Carver | Next protocol |
| 9 | Next read | The hard-news analogue of E3 at the fund's timing, built with the design lessons below | Hard news is now the whole book, and unproven | Pre-registration |
| 10 | Fading soft news | Not now. The fund's own 5-session data shows no reversal (+3.7 bp). The literature puts reversal at days 6–20, in one unrefereed paper. Longer horizons on E3 rows are partly seen through their first 5 sessions | Own data; Kargarzadeh | Rule B only, low priority |
| 11 | Programme | An explicit programme-level error budget (BHY across reads, or alpha spending). No read whose minimum detectable effect exceeds about twice its cost hurdle | DSR, HLZ, zero passes in 38 | Pre-registration policy |

**Design lessons for item 9.** These extend the diagnostics' own list:

1. Report the hurdle at **both** the live and the registered cost.
2. Derive any agreement bar from break-even, (1 + c/μ)/2, and let it bind only at **n ≥ 40–50**.
3. Weight the pooled estimand toward the sources the desk actually trades.
4. Make the fit-plus-holdout estimate co-primary whenever the fit window selects nothing.
5. State the minimum detectable effect before the lock.

**If hard news then fails the same way,** the honest reading is that the weekly LLM news overlay has no demonstrated
edge at its latency. It should then run at the smallest gross that still produces measurement data. The research
effort should go to the reaction term, which only pre-release forecasting (R5) addresses. That is the owner's
strategic call, and it is outside Amendment 3.

## Conclusion

**"Redistribute or leave uninvested" turns out to be the wrong frame for this fund.** The book is sized by signal, not
by slot, so the stop shrinks it automatically. The only real redistribution happens through time: carried positions
lose fewer capacity fights. The question that matters is what the remaining book is for. It now holds only hard-news
positions, and neither the fund's own reads nor the large-cap literature has shown those to beat their cost at a
23-hour lag. Removing a zero-edge, high-turnover component raises the book's after-cost Sharpe whatever the hard-news
edge is. It does not create an edge. Scaling the survivors up would add to that uncertainty.

**The deeper lesson is about how reads are designed.** Rule A reached the right answer by the wrong route:

* a bar below break-even;
* a 12-trade count;
* a hurdle below the scoring cost;
* a proxy sample the desk does not trade.

The diagnostics caught all four after the fact. With about 38 reads and no passes, the programme's binding constraint
is no longer data or compute. It is statistical power per read and the number of reads. Few well-powered, break-even
derived tests on what the desk actually trades are now worth more than many quick ones, and the cheapest tests to keep
running are the ones that only measure, such as counterfactual rows and logging.
