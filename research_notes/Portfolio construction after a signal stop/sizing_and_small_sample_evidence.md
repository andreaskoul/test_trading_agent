# Sizing by conviction and judging small-sample evidence: practice and literature, applied to the soft-news STOP

Fund facts used throughout (from the brief, not re-verified): 5-day trades in the news-day direction; holdout pooled
follow-through mu = +11.4 bp gross per trade, one-sided p = 0.0895 against a 4 bp hurdle; all data +3.7 +- 4.1 bp gross;
round-trip cost c = 4 bp; the desk's side matched the news-day direction on 7 of 12 live trades; break-even agreement
a* = (1 + c/mu)/2 = 0.675; about 38 locked reads so far, none passed.

Notes on method: SSRN and Wiley pages returned 403, so abstracts come from author-hosted PDFs or faithful mirrors (named
below). Everything under "Inferences" is my own arithmetic or reasoning. It is not a sourced claim.

---

## 1. Conviction weighting: how PMs scale size by confidence, and whether it adds value

### Takeaway
Quant practice turns a signal into size through a calibrated expected return, alpha = IC x sigma x z (Grinold). Size then
follows alpha/sigma^2 or alpha/sigma, and is capped (Carver: forecasts scaled to an average absolute value of 10 and
capped at +-20). The best evidence that conviction carries information is Cohen-Polk-Silli/Anton "Best Ideas": managers'
top-conviction holdings beat the market by 2.8-4.5% a year. But that conviction comes from managers who already have
proven skill. It does not make an unproven signal worth weighting.

### Cited Findings
- **Grinold's bridge from score to alpha:** alpha_i = IC x sigma_i x z_i. sigma_i is residual volatility and z_i the
  standardised score. Source papers: Grinold (1994), "Alpha is Volatility Times IC Times Score", *JPM* 20(4):9-16; and
  Grinold (1989), "The Fundamental Law of Active Management", *JPM* 15(3):30-38, with IR = IC x sqrt(N). These citations
  are reproduced in [Ding & Martin / NYU, "The Fundamental Law of Active Management: Time Series..."](https://math.nyu.edu/inmemoriam/avellaneda/FundamentalLawFT.pdf).
- **Typical IC sizes:** "In real life it is small, often around 0.02 to 0.05". This is an educational secondary source,
  so treat it as practitioner convention — [Quant Memo, Grinold alpha formula](https://quantmemo.com/concepts/grinold-alpha-formula).
- **Warnings on the IC x sigma x z recipe** (practitioner blog, opinion):
  - "an assumption that the payoff scales with residual risk";
  - mixing a monthly IC with an annual omega "understates alpha by sqrt(12)";
  - "A 20-year realised IR carries an SE of about 0.24".

  Source: [RiskHub, Combining Alpha Signals with Risk Models](https://riskhub.org/blogs/combining-alpha-signals-with-risk-models).
- **Combining signals:** for uncorrelated signals the combined IC is about sqrt(sum w_j^2 IC_j^2). "if your signals are
  highly correlated ... the benefits of compounding evaporate" — [Quant Beckman, Signal independence](https://www.quantbeckman.com/p/what-is-the-best-way-to-turn-signals).
- **Carver's forecast scaling:**
  - Recipe: forecast scalar = 10 / (average absolute raw forecast), then "Cap the scaled forecast to fall within the
    interval [-20, 20]". Several signals are combined with weights, then multiplied by a forecast diversification
    multiplier (FDM) so the combined average stays at 10 — [QuantConnect replication of Carver](https://www.quantconnect.com/research/15875/futures-fast-trend-following-with-trend-strength);
    [QuantConnect, trend and carry](https://www.quantconnect.com/research/15989/futures-trend-following-and-carry-in-different-risk-regimes).
  - FDM = 1/sqrt(W H W'), where H is the correlation matrix of the forecasts — [Jirong Huang's notes on Carver](https://jironghuang.github.io/post/plans-for-trend-following-strategy-in-futures-using-binary-forecast).
  - Carver in his own words (podcast): "10 means it's the average size position ... I also cap that number at 20 ... to
    limit my sort of exposure to a single instrument's risk" — [Algo Advantage podcast 033, transcript](https://www.youtube.com/watch?v=udBUed_tSVs);
    [summary](https://algoadvantage.substack.com/p/033-rob-carver-the-comprehensive).
- **Best Ideas, evidence (Anton, Cohen & Polk; earlier Cohen, Polk & Silli 2010 draft):**
  - The abstract: managers' "Best ideas" "outperform the market, as well as the other stocks in those managers'
    portfolios, by approximately 2.8 to 4.5 percent per year, depending on the benchmark employed. The vast majority of
    the other stocks managers hold do not exhibit significant outperformance."
  - The best ideas of small hedge funds beat those of large funds "by a remarkable 15 percent per year".
  - Best ideas work best "in illiquid, growth, momentum stocks, or for funds that have outperformed in the past".

  Source: [Anton, Cohen & Polk, "Best Ideas", LSE PDF](https://personal.lse.ac.uk/polk/research/bestideas.pdf) and
  [HBS working paper 21-004 (June 2020)](https://www.hbs.edu/ris/Publication%20Files/21-004_f616ddeb-db44-495b-915a-0b5191d9ccf3.pdf).
- **A conflicting figure for the same study:** the 2009 draft (1991-2005 holdings) was summarised as "1% to 4% per
  quarter". More than 70% of best ideas belonged to a single manager. Treat this as superseded by the per-year figures in
  the published versions — [CXO Advisory summary](https://www.cxoadvisory.com/investing-expertise/best-ideas-of-mutual-fund-managers).
- **Overweights:** stocks heavily overweighted by active managers beat underweighted ones "by more than 7% per year"
  after factor adjustment (Jiang et al., cited second-hand) — [Or Cohen blog literature review](https://cohen-or.github.io/posts/best_ideas.html).
- **Industry vendor view (opinion, Alpha Theory, a firm that sells sizing software):** "a structured process beats ad
  hoc", with sizes built from "price targets, probability of hitting those targets, conviction" — [Alpha Theory, Position Sizing](https://www.alphatheory.com/blog/what-is-position-sizing).
- **Conviction buckets (opinion):** one practitioner write-up gives high 8-12%, medium 4-7% and low 1-3% "tracking
  position" (concentrated long-only context) — [JustJot, How to Size a Position](https://www.justjot.ai/n/investing-research-how-to-size-a-position).
- **Paleologo** argues sizing is a separate component of the IR. Article: "Information Ratio = Selection x Breadth +
  Sizing", *JPM* 49(8):71 (2023) — [PM Research](https://www.pm-research.com/content/iijpormgmt/49/8/71). Paywalled, so
  the content was not verified.

### Inferences
- **Sizing family.** Weighting by conviction is the same idea as mean-variance sizing, w ∝ alpha/sigma^2:
  - Grinold form: w ∝ IC x z / sigma.
  - Kelly for a single bet: f* = mu/sigma^2. Half-Kelly is the usual practitioner haircut.

  All of these are proportional to IC. For a signal whose net IC is about zero, every one of them gives a position of
  about zero. Weighting cannot rescue a signal with no net edge. It can only allocate a real edge better.
- **Best Ideas is about who has the edge.** The managers had multi-year records, and the effect is strongest for funds
  "that have outperformed in the past". The useful parallel for the fund is to grant conviction weight to the desk only
  after the desk's own record is shown to carry information. The STOP read says that has not happened.
- **Carver's cap.** The +-20 cap (2x the average) is the practitioner way to say "don't trust tails of a forecast more
  than twice the average". For a weak signal the matching move is to lower the scalar, not to lift the cap.
- **Combining the LLM desk with the mechanical news-day direction.** Write their ICs as IC_d and IC_n and their
  correlation as rho. The optimal linear combination then has
  IC_c^2 = (IC_d^2 + IC_n^2 - 2 rho IC_d IC_n)/(1 - rho^2). (This is the standard two-predictor R^2 identity, my
  derivation.)
  - If the desk is just a noisy copy of the news direction (rho high, IC_d <= IC_n), combining adds nothing.
  - Gating trades on agreement uses no weights. In the fund it also cuts breadth from about 12 to about 7 trades.

### Gaps
- I could not read Paleologo's sizing rules (proportional vs risk-parity vs mean-variance) in his books
  (*Advanced Portfolio Management*, 2021; *The Elements of Quantitative Investing*), nor the JPM 2023 article. The
  article is paywalled and no open summary turned up.
- Isichenko (*Quantitative Portfolio Management*, 2021) and Grinold & Kahn chapter text were not accessed directly.
- I found no peer-reviewed study of "analyst conviction lists" in this pass.
- The Kelly and half-Kelly growth/variance trade-off (half-Kelly gives about 75% of the growth rate at 25% of the
  variance) is a standard derivation. I did not find a primary source for it in this session.

---

## 2. Hit rate vs payoff: break-even formulas with costs, and the value of agreement

### Takeaway
Break-even hit rate with symmetric payoffs and cost c is p* = (1 + c/mu)/2. Practitioners use it as a feasibility
screen. For the fund it decides the question:
- At the holdout mean (11.4 bp), the desk needs a* = 0.675 agreement, and 7/12 gives only a 22% posterior chance of
  being above that.
- At the all-data mean (3.7 bp), c/mu > 1, so a* > 1. No agreement rate breaks even.

### Cited Findings
- **Small-sample hit rates (practitioner rules of thumb, opinion):**
  - "with only 20 trades, a win rate of 13/20 (65%) still has a p-value > 0.2" — [Trading Dude, Medium](https://medium.com/@trading.dude/how-many-trades-are-enough-a-guide-to-statistical-significance-in-backtesting-093c2eac6f05).
  - "Most real trading edges are 51/49 problems, not 70/30 ones ... A coin weighted 51/49 takes hundreds of flips to
    distinguish from fair" — [Arrow Algo](https://arrowalgo.com/backtest-sample-size).
- **Carver on combining** (secondary description of his method): continuous forecasts allow "gradual position building
  and reducing exposure ... lower trading costs compared to a discrete ... approach" — [Algo Advantage summary](https://algoadvantage.substack.com/p/033-rob-carver-the-comprehensive).
- **Edge vs cost, Robot Wealth (opinion):**
  - "Trading costs are guaranteed, while your trading edge is uncertain and difficult to measure" — [Robot Wealth, no-trade region](https://robotwealth.com/reduce-trading-costs-and-boost-profits-with-the-no-trade-region-strategy).
  - "The FX strategy started small because the edge is narrow relative to trading costs; only after proving itself live
    was the size increased" — [Better System Trader ep. 201, Kris Longmore](https://bettersystemtrader.com/201-getting-serious-about-part-time-trading-kris-longmore).

### Inferences
- **Derivation of a\*.** Let the desk take the news-day direction with probability a. Its expected gross P&L per trade
  is (2a - 1)mu. Net P&L is positive when (2a - 1)mu > c, that is a > (1 + c/mu)/2. With mu = 11.4 and c = 4 this gives
  a* = 0.675.
  - With the all-data mu = 3.7: c/mu = 1.08 and a* = 1.04, which is infeasible.
  - With a McLean-Pontiff-decayed mu (Section 5): mu = 8.4 bp gives a* = 0.74; mu = 4.8 bp gives a* = 0.92.
- **Beta posterior on agreement.** Prior Beta(1,1) plus 7 of 12 gives posterior Beta(8,6):
  - mean 0.571; 95% credible interval [0.316, 0.808];
  - P(a > 0.675) = 0.22; P(a > 0.5) = 0.71.

  Binomial test of 7/12 against 0.5: one-sided p = 0.39.
- **Trades needed to separate a = 0.675 from 0.5** (one-sided alpha = 0.05):
  - about 48 trades for 80% power;
  - about 22 trades for 50% power.

  At about 10 a side per week this is a few weeks of trades if agreement is logged per name. If trades cluster by
  cohort, the effective n is smaller.
- **What agreement does to the edge.** The relevant edge is mu x (2a - 1). At a = 7/12 this is 11.4 x 0.167 = 1.9 bp
  gross, below the 4 bp cost even on the holdout mean.

### Gaps
- I found no published study that measures the value of LLM-vs-mechanical "agreement" gating specifically.
- I found no peer-reviewed source stating the p* = (1 + c/mu)/2 identity. It is elementary algebra (shown above).

---

## 3. Near-zero net-edge signals: drop or keep at small weight; shrinkage

### Takeaway
Shrinkage puts the answer in a formula. The posterior mean edge is mu_hat x tau^2/(tau^2 + SE^2). With SE of about
5.5 bp and any plausible prior spread tau of 2-3 bp for a news follow-through effect, the shrunk gross edge is 1.3-2.6 bp,
below the 4 bp cost. Sizing proportional to the net shrunk alpha is then zero. "Small weight" is only justified when the
shrunk net alpha is positive. Practitioners who keep a small position do it to collect live evidence, and pay for it as
a research cost.

### Cited Findings
- **Harvey & Liu's view of marginal strategies** (*JPM*, Fall 2015, p. 12-13):
  - "The highest Sharpe ratios are only moderately penalized, while the marginal Sharpe ratios are heavily penalized ...
    The marginal Sharpe ratio strategies should be thrown out."
  - "the haircut is almost always more than and sometimes much larger than 50% when the annualized Sharpe ratio is less
    than 0.4 ... when the Sharpe ratio is greater than 1.0, the haircut is at most 25%."

  Source: [Harvey & Liu, "Backtesting", Duke PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF).
- **Grinold's formula is itself shrinkage.** Multiplying the score by IC (often 0.02-0.05) scales a raw score down to a
  modest expected return — [Quant Memo](https://quantmemo.com/concepts/grinold-alpha-formula).
- **"Start small" (practitioner opinion):** Robot Wealth sizes narrow-edge strategies small until they prove themselves
  live. It sizes down a strategy suspected of "hidden negative skew in live markets", and uses equal volatility weight as
  the default — [Better System Trader ep. 201](https://bettersystemtrader.com/201-getting-serious-about-part-time-trading-kris-longmore).
- **Carver on uncertainty:** he shows SR estimates with 60% confidence bands, assuming 20 years of data, because
  "Pre-cost returns are actually very hard to predict ... costs" are more predictable — [Carver, How fast should we trade?](https://qoppac.blogspot.com/2020/04/how-fast-should-we-trade.html).
  His "handcrafting" method adjusts weights for Sharpe-ratio uncertainty and data length — [Carver, New and improved Sharpe ratio adjustment](https://qoppac.blogspot.com/2019/12/new-and-improved-sharpe-ratio.html).

### Inferences
- **Normal-normal shrinkage on the holdout mean.** The SE comes from the p-value: (11.4 - 4)/z(0.9105) = 7.4/1.344,
  which is about 5.5 bp.

  | Prior sd tau | Shrink factor | Posterior gross mean | Net of 4 bp |
  |---|---|---|---|
  | 2 bp | 0.12 | 1.3 bp | -2.7 bp |
  | 3 bp | 0.23 | 2.6 bp | -1.4 bp |
  | 5 bp | 0.45 | 5.2 bp | +1.2 bp, before applying a* |

  Only a generous prior keeps the net positive. Even then, multiplying by (2a - 1) at a = 0.58 gives about 0.9 bp gross,
  below cost.
- **Using all the data** (+3.7 +- 4.1), the point estimate itself is below cost. No shrinkage is needed to conclude that
  the net edge is not positive.
- **The coherent "small weight" variant is an incubation sleeve**, sized as a research expense with a pre-registered end
  rule (Section 4). It is not alpha-proportional sizing. This fits the repo rule that records are pre-registered and
  append-only.

### Gaps
- I did not find a published "Bayesian posterior IC" calibration of prior tau for news-driven follow-through signals.
  The tau values above are illustrative.
- James-Stein applied across the 38 reads (shrinking all read estimates toward their grand mean) would be the natural
  extension. It needs the 38 estimates and SEs, which are not in the brief.

---

## 4. Small-sample decision rules: minimum samples, time to significance, Bayesian updating

### Takeaway
- Time to significance for a strategy is T = (t/SR)^2 years: about 16 years for SR 0.5 at t = 2, and 36 years at t = 3.
- Bailey & Lopez de Prado's Minimum Track Record Length (MinTRL) makes this longer for negative skew and fat tails.
- Retail rules of thumb (30, 100, 200-500 trades) are opinions with no statistical basis on their own. One source
  withdrew its own thresholds.

### Cited Findings
- **Probabilistic Sharpe Ratio (Bailey & Lopez de Prado 2012, *Journal of Risk*):**
  PSR(SR*) = Z[(SR_hat - SR*) sqrt(n - 1) / sqrt(1 - g3 SR_hat + (g4 - 1)/4 SR_hat^2)].
- **Minimum Track Record Length:**
  MinTRL = 1 + [1 - g3 SR + (g4 - 1)/4 SR^2] (Z_alpha/(SR - SR*))^2.

  "A longer track record will be required the smaller SR is, or the more negatively skewed returns are, or the greater
  the fat tails" — [Lopez de Prado, QWAFAFEW slides](http://boston.qwafafew.org/wp-content/uploads/sites/4/2017/01/Lopez_de_Prado_Sharpe.pdf);
  formula also in [QuantOracle PSR calculator](https://quantoracle.dev/probabilistic-sharpe-ratio-calculator).
- **Two-strategy version:** MinTRL_a(SR_b) = (V_a + V_b + V_ab)(z_{1-alpha}/SR_diff)^2 — [Portfolio Optimizer blog](https://portfoliooptimizer.io/blog/the-probabilistic-sharpe-ratio-hypothesis-testing-and-minimum-track-record-length-for-the-difference-of-sharpe-ratios).
- **SR 0.5 needs about 16 years:** "a Sharpe near 0.5 needs on the order of 16 years to reach a t-stat of 2" (secondary,
  LuxAlgo, via search snippet). This matches (2/0.5)^2 = 16.
- **Carver on track length:**
  - His book *Systematic Trading* "show[s] that it takes an unexpectedly long period of backtesting data to support a
    significant positive Sharpe ratio" (reader's summary; Carver's reply is on the page) — [qoppac, My Books](https://qoppac.blogspot.com/p/books.html).
  - On slow systems: "even with 100+ instruments and up to 50 years of data the number of unique data points is
    relatively small, so the results are unlikely to be statistically significant" — [qoppac 2022](https://qoppac.blogspot.com/2022).
- **Professional traders (Coates & Page, field data, 53 traders, 20 months of P&L):**
  - The traders' average Sharpe of 0.70 versus the market was "not significant (t-test, p = 0.13 ...)".
  - Beginners averaged 0.39; experienced traders 1.02.

  So 20 months could not separate a 0.7 Sharpe from the index — [Coates & Page, "A Note on Trader Sharpe Ratios", PLoS ONE](https://pmc.ncbi.nlm.nih.gov/articles/PMC2776986).
- **Rules of thumb (opinion, retail/practitioner):**
  - "Under 30 trades: ignore the metrics ... 30-100: a first impression ... 100-300: metrics begin to stabilise ...
    300+: a serious sample" — [Arrow Algo](https://arrowalgo.com/backtest-sample-size).
  - "between 500 and 1,000 trades" over 10 years; "100, 150 or 200 trades ... not enough" — [Breakout Trading Academy](https://breakouttradingacademy.com/how-much-sample-size-do-you-need-in-a-trading-strategy).
  - "Minimum of 30 trades ... Aim for 100+" — [Trading Dude](https://medium.com/@trading.dude/how-many-trades-are-enough-a-guide-to-statistical-significance-in-backtesting-093c2eac6f05).
  - A September 2026 correction withdrew earlier universal thresholds: "There is no universal number of trades that
    proves a strategy works ... depends on ... dependence, strategy selection, costs" — [Trader's Second Brain](https://traderssecondbrain.com/guides/how-many-trades-to-know-if-strategy-works).

### Inferences
- **Per-trade arithmetic for the soft-news effect**, assuming the holdout SE of about 5.5 bp scales as 1/sqrt(n):
  - If the true mu were the holdout 11.4 bp, beating the 4 bp hurdle at t = 2 would need about 2.2x the holdout sample.
    At t = 3 it would need about 5.0x.
  - If the true mu is the all-data 3.7 bp, no sample size passes a 4 bp hurdle.
  - The informative thing to collect is therefore not more of the same read. It is evidence on whether mu is nearer
    11.4 or 3.7. The gap between the holdout and all-data estimates is itself a warning about selection or regime.
- **Sequential, Bayesian practice for agreement.** Keep the Beta(8,6) posterior and update it per trade. Pre-register a
  stop or continue rule, for example:
  - "resume if P(a > a*) > 0.9";
  - "abandon if P(a > a*) < 0.05";
  - with a maximum n of about 50.

  This avoids repeated peeking at a fixed-n p-value. Thresholds should be written down before data arrive, in line with
  rule 14 in the repo.

### Gaps
- I could not reach Carver's exact table of years needed per SR, nor his blog reply text. Search snippets only.
- I found no rule of thumb on r/quant, Wilmott, QuantNet, Nuclear Phynance or Elite Trader within the tool budget. The
  forum-style figures above come from retail-trading blogs, which carry less authority.

---

## 5. Multiple testing: t > 3, haircut Sharpe, deflated Sharpe, PBO, post-publication decay

### Takeaway
After about 38 reads, one marginal p = 0.09 is less than chance would deliver:
- With 38 independent null reads, P(at least one p <= 0.0895) = 0.97.
- The expected number of such p-values is 3.4.
- Bonferroni needs z of about 3.0 (one-sided).

Harvey-Liu-Zhu's t > 3 hurdle, the haircut being nonlinear in the marginal case, and McLean-Pontiff decay of 26-58% all
point the same way. The STOP is consistent with the literature.

### Cited Findings
- **Harvey, Liu & Zhu ("...and the Cross-Section of Expected Returns", *RFS* 2016; NBER w20592):** a newly discovered
  factor "needs to clear a much higher hurdle, with a t-ratio greater than 3.0 ... most claimed research findings in
  financial economics are likely false" — [NBER w20592](https://www.nber.org/papers/w20592).
- **Harvey & Liu ("Backtesting", *JPM* Fall 2015, pp. 12-28):**
  - On the number of tests: "at least 316 factors have been tested". The method is: convert SR to t, adjust p with
    Bonferroni, Holm or BHY, convert back. "The percentage difference between the original Sharpe ratio and the new
    Sharpe ratio is the haircut."
  - Worked example: with 50 trials, "the haircut is almost 50% for the least profitable E/P strategy [SR 0.43], but only
    7.9% for the most profitable BAB strategy [SR 0.78]".
  - Citing Lopez de Prado: "only seven trials are needed to obtain a spurious two-year backtest that has an in-sample
    realized Sharpe ratio of more than 1.0, while the expected out-of-sample Sharpe ratio is zero."

  Source: [Duke PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF).
- **Harvey & Liu, secondary summary:** the haircut "depends on how many strategies were tested and how correlated they
  were" — [CME Group reprint/summary](https://cmegroup.com/education/alternative-investment-resource-center/research/backtesting.html);
  [Man Group summary](https://www.man.com/insights/backtesting).
- **Deflated Sharpe Ratio (Bailey & Lopez de Prado, *JPM* 2014).** Expected maximum SR after N independent trials under
  the null: E[max SR] ~ sqrt(V[SR]) x ((1 - gamma) Z^-1[1 - 1/N] + gamma Z^-1[1 - 1/(Ne)]), with gamma = 0.5772
  (Euler-Mascheroni). "DSR is a PSR where the rejection threshold is adjusted to reflect the multiplicity of trials ...
  its expected maximum is greater than zero, even if the true SR is zero." Appendix 3 covers non-independent trials.
  Python code is included — [Bailey & Lopez de Prado, DSR PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).
- **Probability of Backtest Overfitting (PBO):** "measures the relative performance of a particular backtest among a
  basket of strategies, using cross-validation techniques" (CSCV), as described in Harvey & Liu — [Duke PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF).
- **An illustration of mass testing (YouTube experiment, anecdotal):** "133,461 configurations ... How many clear the
  threshold? Zero. The highest deflated sharpe ratio was 12.5%" — [Algovibes](https://www.youtube.com/watch?v=o0INvuabn7I).
- **McLean & Pontiff ("Does Academic Research Destroy Stock Return Predictability?", *JF* 71(1), 2016):**
  - Abstract: "97 variables ... Portfolio returns are 26% lower out-of-sample and 58% lower post-publication. The
    out-of-sample decline is an upper bound estimate of data mining effects. We estimate a 32% (58% - 26%) lower return
    from publication-informed trading. Post-publication declines are greater for predictors with higher in-sample
    returns."
  - Monthly means: 0.582% in-sample, 0.402% out-of-sample pre-publication, 0.264% post-publication.

  Sources: [author PDF mirror](https://tevgeniou.github.io/EquityRiskFactors/bibliography/AcademicReviewFactor.pdf);
  [CFA Institute digest](https://rpc.cfainstitute.org/research/cfa-digest/2016/06/does-academic-research-destroy-stock-return-predictability-digest-summary);
  [ABFER abstract](https://www.abfer.org/component/edocman/main-annual-conference/does-academic-research-destroy-stock-return-predictability).
- **Conflict between versions of McLean-Pontiff:**
  - The 2013 working paper (82 characteristics) reported about 10% out-of-sample decay (not significant) and about 35%
    post-publication decay — [FMG/LSE 2013 draft](https://www.fmg.ac.uk/sites/default/files/2020-08/Jeffrey-Pontiff.pdf).
  - A later re-analysis (Chen & Zimmermann, arXiv 2209.13623, cited second-hand via search) puts the publication-bias
    share at about 12%.
  - Use the published 26%/58% figures, and note the range.

### Inferences
- **The programme of 38 reads, treated as independent nulls:**

  | Quantity | Value |
  |---|---|
  | P(min p <= 0.0895) | 1 - 0.9105^38 = 0.97 |
  | Expected count of p <= 0.09 | 3.4 |
  | Expected smallest p | about 1/39 = 0.026 |
  | Bonferroni one-sided z (alpha = 0.05/38) | 3.01 |
  | Expected max z (DSR formula, N = 38) | 2.17 |
  | Expected max z (DSR formula, N = 100) | 2.53 |

  The soft-news z of 1.34 against the hurdle is below the expected maximum of 38 pure-noise reads. The reads share data
  and hypotheses, so the effective N is below 38. That softens the penalty but cannot turn z = 1.34 into a pass.
- **Haircut logic.** Harvey-Liu's nonlinearity means a marginal result (t of about 1.3) is cut by far more than 50%.
  Formally, its multiple-testing-adjusted p is above 0.9, which leaves an adjusted SR of about zero.
- **McLean-Pontiff decay applied to the holdout:** 11.4 bp becomes 8.4 bp after a 26% cut, or 4.8 bp after a 58% cut.
  Net of 4 bp that is 4.4 bp or 0.8 bp, before the agreement factor. The 26% "out-of-sample" figure is the closest
  analogue to a pre-registered holdout. Post-publication decay applies only if the effect is publicly known
  (news-driven drift is).
- **Taking 38 reads with no pass at face value:**
  - The programme's base rate of true effects at its testing power is low.
  - In the Bayesian view, the prior for the next read should be lower, which raises the evidence a future read needs.
  - Pre-registration fixes the single-read error rate, not the programme-level false-discovery rate. That needs a
    programme-level alpha budget, or BHY across reads.

### Gaps
- I did not compute Harvey-Liu haircut tables exactly, since that needs the HLZ structural model.
- I did not compute PBO for the fund, since it needs the matrix of trial returns.
- The correlation structure of the 38 reads is unknown, so the effective N is unknown.

---

## 6. Forum and practitioner opinion: "is this edge real?", and sizing unproven signals

### Takeaway
Practitioner opinion converges on four points:
- demand an economic reason;
- test directly and simply;
- start small and scale only after live proof;
- remember that costs are certain and edges are not.

I found few verifiable quotes from the specific forums named (r/quant, Wilmott, Nuclear Phynance, Elite Trader) within
budget.

### Cited Findings (all opinion)
- **Robot Wealth (Kris Longmore):** "If you can't explain it, be suspicious ... Once you have a credible hypothesis,
  check if the data backs it up. Use simple analysis techniques to look as directly at the effect as possible" — [Robot Wealth, When your strategy works is it just dumb luck?](https://robotwealth.com/when-your-strategy-works-is-it-just-dumb-luck-how-to-stack-the-odds-in-your-favour).
- **Robot Wealth:** "Everything decays and eventually disappears in this game" — [Robot Wealth, Index of Strategies](https://robotwealth.com/index-of-strategies).
- **Robot Wealth sizing:** equal-volatility default; narrow-edge strategies "started small ... only after proving itself
  live was the size increased"; "Sizing too large ... Above a certain point, position size guarantees ruin regardless
  of edge" — [Better System Trader ep. 201](https://bettersystemtrader.com/201-getting-serious-about-part-time-trading-kris-longmore).
- **Carver:** forecast capped at 2x average; he prefers continuous forecasts to binary on/off decisions; he warns
  repeatedly that SR estimates have wide confidence intervals — [Algo Advantage 033](https://algoadvantage.substack.com/p/033-rob-carver-the-comprehensive); [qoppac 2020](https://qoppac.blogspot.com/2020/04/how-fast-should-we-trade.html).
- **LinkedIn comment on Carver's R^2/SR post (opinion):** "a statistically significant regression ... on past data
  implies that such statistical relationship and significance will hold in the future. Unfortunately that is absolutely
  not true" — [Carver post comments](https://www.linkedin.com/posts/robert-stuart-carver_r-squared-and-sharpe-ratio-activity-7390435812330401793-hIQD).
- **Retail guide (opinion):** "Treat small-sample results as hypotheses, not conclusions ... 'Without enough data, your
  backtest is a marketing deck — not evidence.'" — [Trading Dude](https://medium.com/@trading.dude/how-many-trades-are-enough-a-guide-to-statistical-significance-in-backtesting-093c2eac6f05).

### Inferences
- The consensus maps onto the fund's options:
  1. Keep the STOP for allocation.
  2. If the owner wants live evidence, run the soft-news rule as a tiny or paper incubation sleeve. Pre-register a
     Beta-posterior stop/continue rule on agreement (about 50 trades) and on net P&L, and treat its cost as research
     spend.
  3. Count it as read #39 in a programme-level error budget, not as a fresh single test.
- None of the sources supports conviction-weighting a signal whose all-data net edge is negative.

### Gaps
- I did not retrieve direct quotes from r/quant, Wilmott, QuantNet, Nuclear Phynance, Elite Trader, Quant
  StackExchange, or X/Twitter quants. The search engines surfaced retail blogs instead.
- A targeted follow-up could search site:reddit.com/r/quant ("incubation", "paper trade how long") and
  site:quant.stackexchange.com ("minimum number of trades").
