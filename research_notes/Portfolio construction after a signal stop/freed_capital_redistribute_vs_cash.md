# Freed risk after a signal class is switched off: redistribute ("fill the slots") or leave it uninvested (lower gross)?

Context assumed throughout: SPY-hedged, about zero-beta long/short overlay on S&P 500 names, about 10 names a side, weekly LLM news-desk cohorts, 5-day holds, annual turnover 40–68x NAV, live cost about 1–2 bp per side (about 4 bp round trip). Soft-news entries (about 37–45% of events) were stopped. Their best estimate is +3.7 ± 4.1 bp gross per 5-day trade, so about −0.3 ± 4.1 bp net (t ≈ −0.07). Hard-news entries are unproven.

Source note: this session's web access reached abstracts, reviews, blog posts and curriculum summaries. It did not reach the full texts of Grinold-Kahn, Qian-Hua-Sorensen, Isichenko, Paleologo or Kan-Zhou. Everything under **Inferences** is my own algebra on standard formulas, labelled as such, with assumptions stated. Recalled results I could not verify this session are under **Gaps** and not stated as fact.

---

## 1. Grinold-Kahn: optimal active weights, optimal active risk, and what happens when fewer signals have alpha

### Takeaway
In the Grinold-Kahn mean-variance framework, a name with zero alpha gets zero active weight. Optimal active risk is ψ* = IR/(2λ), so when the information ratio falls, optimal risk (and so gross) falls too. Holding active risk constant by scaling up the remaining names amounts to quietly lowering risk aversion just when the evidence has weakened. The framework never targets "number of names" or "gross"; both are outputs.

### Cited Findings
- The optimal level of residual (active) risk is ω* = IR/(2λ), with IR the information ratio and λ residual risk aversion. Value added is VA(P) = α_P − λ·ω_P². "The optimal level of residual risk increases if there are more opportunities and less residual risk aversion." — [AnalystNotes, CFA study note on optimal residual risk](https://analystnotes.com/cfa-study-notes-calculate-the-optimal-level-of-residual-risk-to-assume-for-given-levels-of-manager-ability-and-investor-risk-aversion.html); [open-exam-prep, CFA L2 Active Portfolio Management](https://open-exam-prep.com/study-guides/cfa-level2/portfolio-management/active-portfolio-management); [AnalystPrep, Fundamental Law (TC, IC, breadth, active-risk aggressiveness)](https://analystprep.com/study-notes/cfa-level-2/state-and-interpret-the-fundamental-law-of-active-portfolio-management-including-its-component-terms-transfer-coefficient-information-coefficient-breadth-and-active-risk-aggressiveness/)
- The generalised fundamental law is E(R_A) = TC · IC · √BR · σ_A, i.e. IR = TC·IC·√BR. The transfer coefficient (TC) is "a simple scaling factor" that measures how far constraints stop forecasts from turning into active weights. — [Clarke, de Silva & Thorley (2002), FAJ 58(5):48–66, CFA Institute abstract](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/portfolio-constraints-and-the-fundamental-law-of-active-management); [RePEc listing](https://ideas.repec.org/a/taf/ufajxx/v58y2002i5p48-66.html)

### Inferences (my derivations from the cited formulas)
- **Optimal weights.** Maximising α'h − λ h'Σh gives h* = Σ⁻¹α / (2λ). With a diagonal residual covariance this is h_i* = α_i / (2λ ω_i²). If the soft-news α_i are set to 0, those names get h_i* = 0. The optimiser does not hand their slots to other names; nothing in the objective rewards a fixed count.
- **Optimal risk and value added.** The squared IR is α'Σ⁻¹α = Σ_i (α_i/ω_i)², which is additive across independent bets. Then ψ* = IR/(2λ) and VA* = IR²/(4λ).
  - Remove a fraction f of the alpha-bearing bets (equal per-bet IR): IR_new = IR·√(1−f). Optimal active risk falls by the same √(1−f), and VA* falls by (1−f).
  - Example: f = 0.40 gives √0.6 = 0.775, so about 77% of the old risk and about 60% of the old value added.
  - If the stopped bets truly had zero alpha (the result here), IR is unchanged and ψ* is unchanged. The positions that carried ψ were the hard-news ones all along, so their sizes should not change.
- **Variable vs constant tracking error.** Fixing a target tracking error ψ_target and rescaling alphas until the optimiser hits it implies λ_implied = IR/(2ψ_target). If IR is cut (or is unknown) and ψ_target stays put, λ_implied falls in proportion: the manager takes the same risk per unit of a weaker or less certain edge. That is "filling the slots" by another name.
- **Breadth and the fundamental law.** Breadth counts only independent bets with skill: IR² ≈ IC_h²·BR_h + IC_s²·BR_s. With IC_s = 0, soft-news breadth adds nothing to IR. Keeping those bets (or using their slots for zero-skill trades) adds variance without adding to the numerator. The fundamental law therefore implies scaling total active risk down in proportion to the lost √(IC²·BR). It does not imply concentrating the same risk in fewer names.
- **Overlay vs long-only.** In a hedged overlay, "uninvested" means zero active weight and zero gross, and costs nothing. In a long-only benchmarked book, "uninvested" means holding the benchmark weight, not cash. Holding cash would add an unintended negative-beta active bet. The Grinold-Kahn answer (zero active weight) is the same in both cases; only the implementation differs.

### Gaps
- I could not access the full Grinold & Kahn (2nd ed., 2000) text this session to quote chapter and page on "aggressiveness" and alpha scaling (α = Volatility · IC · score). The formula is standard but not quoted here from the primary source.

---

## 2. Transfer coefficient, forced full investment and constant-gross / fixed-count constraints

### Takeaway
Clarke, de Silva & Thorley show that constraints that stop weights from matching forecasts (long-only, concentration limits, and by extension a "must hold N names" or "constant gross" rule) cut the realised IR multiplicatively through TC. Empirically TC is about 0.3–0.8 for constrained portfolios. Filling slots with zero-forecast names is a constraint of this kind.

### Cited Findings
- Constraints "such as no short sales and limits on security concentration impede the transfer of information into optimal portfolio positions and decrease the expected value added". An unconstrained portfolio has TC = 1. TC explains "why performance in practice is only a fraction (0.3 to 0.8) of what is predicted by the original form of the fundamental law." — [Clarke, de Silva & Thorley (2002), FAJ, CFA Institute abstract](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/portfolio-constraints-and-the-fundamental-law-of-active-management)
- IC measures the strength of the forecasting signal; TC measures "the degree to which the signal is transferred into active portfolio weights." — [same abstract via RePEc](https://ideas.repec.org/a/taf/ufajxx/v58y2002i5p48-66.html)
- Clarke, de Silva & Thorley later extended the attribution framework ("Performance attribution and the fundamental law", FAJ 2005). — [CFA Institute listing](https://rpc.cfainstitute.org/research/financial-analysts-journal/2005/performance-attribution-and-the-fundamental-law); [RePEc](https://ideas.repec.org/a/taf/ufajxx/v61y2005i5p70-83.html)

### Inferences (my derivations)
- **TC of a "fill the slots" book.** TC = corr(risk-adjusted forecasts α_i/ω_i, risk-adjusted weights h_i·ω_i). Suppose the risk-weighted positions split into 60% hard-news names (nonzero forecast) and 40% filled with zero-forecast names of equal risk.
  - The forecast vector is zero on 40% of the risk, but the weight vector is not.
  - If the filler weights are uncorrelated with the hard-news forecasts, TC ≈ √(0.6) ≈ 0.77.
  - So the generalised law prices the filler at roughly a 23% IR haircut before costs.
- **Long-only vs long/short.** The large TC losses in the CdST work come from the long-only (no-short) constraint, which a long/short overlay does not have. A self-imposed constant-gross or fixed-count rule brings back a smaller but similar loss of efficiency.

### Gaps
- I could not open the CdST 2002 full text (JOIM / FAJ PDFs returned 404), so I have no table values of TC for specific gross or leverage constraints (for example their 130/30-type results in later work). The "0.3–0.8" range is from the abstract.
- I found no primary paper titled "the cost of being fully invested" that quantifies this for long/short books specifically.

---

## 3. Qian-Hua-Sorensen, Isichenko, Paleologo: sizing under alpha uncertainty, cash vs full investment, zero-alpha "slot fillers"

### Takeaway
Of these authors, I could verify only Paleologo's views, through a secondary review. Most PMs' high-conviction names do not beat their low-conviction names by much ("Conviction Profitability Ratio" usually ≤ 1, at most about 2). Diversification "is not a skill: it is a skill multiplier." Survival is the prime directive. Both points argue against upsizing the unproven remaining names. Isichenko's book has sections on forecast uncertainty in optimisation, but I could not read them.

### Cited Findings
- Paleologo's Conviction Profitability Ratio (realised return of high- vs low-conviction names): "for most PM's it is one or less, and … even the best PM's dont exceed 2." — [Chasing the Vig, review of Paleologo, *Advanced Portfolio Management* (Wiley 2021)](https://chasingthevig.substack.com/p/advanced-portfolio-management-book)
- Paleologo's decomposition is "Idiosyncratic PnL = selection PnL + sizing PnL + timing PnL". PMs have "at best very little timing skill, moderately-positive-to-moderately-negative sizing skill, and primarily selection skills." — [same review](https://chasingthevig.substack.com/p/advanced-portfolio-management-book)
- "The power of diversification is great. It is not a skill: it is a skill multiplier." Also: "The Prime Directive, in almost everything, is to survive." — [same review, quoting Paleologo](https://chasingthevig.substack.com/p/advanced-portfolio-management-book)
- Isichenko, *Quantitative Portfolio Management: The Art and Science of Statistical Arbitrage* (Wiley 2021) has §4.9 "Forecast uncertainty and alpha risk" and §6.8 "Portfolio optimization with forecast uncertainty". — [O'Reilly listing / ToC](https://oreilly.com/library/view/quantitative-portfolio-management/9781119821328)
- Paleologo, *The Elements of Quantitative Investing* (Wiley 2024/25) covers mean-variance optimal portfolios and trading in factor space. — [ex libris listing](https://www.exlibris.ch/de/buecher-buch/english-books/giuseppe-a-paleologo/the-elements-of-quantitative-investing/id/9781394265459)

### Inferences
- **Diversification multiplies skill; it does not create it.** Paleologo's "skill multiplier" framing implies that adding zero-alpha names multiplies zero. Filler names raise variance and cost and add no skill to multiply.
- **Upsizing the survivors is a sizing bet.** A CPR ≤ 1 for most PMs implies that concentrating freed capital into the remaining names is a sizing bet. Typical managers show little sizing skill, and here the remaining (hard-news) signal has no validated selection skill either.
- **Uncertain alpha acts like extra variance.** Treating alpha uncertainty as extra variance (the generic approach in "optimisation with forecast uncertainty") means the effective risk denominator is Σ + Var(α̂). This shrinks all weights toward zero and shrinks most where the forecast is least certain. See §4.

### Gaps
- **Qian, Hua & Sorensen**, *Quantitative Equity Portfolio Management* (Chapman & Hall 2007): no source reached this session. My recollection, unverified here, is that they argue realised IR ≈ mean(IC)/std(IC), i.e. that IC volatility over time limits the √breadth benefit. This should be checked against the book (ch. 4–5) before it is cited.
- I could not read the contents of Isichenko §§4.9 and 6.8 or Paleologo's sizing chapters (no open text). I found no direct quote from either on "cash vs forced full investment".
- No Paleologo X/blog post on "variable gross" was retrieved.

---

## 4. Kelly and fractional Kelly under estimation error: the optimal bet when edge ≈ 0 ± wide

### Takeaway
Every source agrees that parameter uncertainty shrinks the optimal bet below plug-in Kelly. When the estimated net edge is about zero with a standard error far larger than the mean (here t ≈ −0.07 net), the shrunken optimal stake is about zero. For a weak but positive and uncertain edge, half Kelly or a lower SR assumption is the practitioner default.

### Cited Findings
- **Baker & McHale (2013).** Kelly "ignores uncertainty in the probability of winning … the size of the bet should be shrunk in the presence of parameter uncertainty". Shrunken-Kelly rules beat raw Kelly in simulation and in tennis-betting data, and they give a "back of envelope" shrinkage factor. — [Baker & McHale (2013), *Decision Analysis* 10(3):189–199, RePEc](https://ideas.repec.org/a/inm/ordeca/v10y2013i3p189-199.html); [Salford repository](https://salford-repository.worktribe.com/output/1410355/optimal-betting-under-parameter-uncertainty-improving-the-kelly-criterion); [INFORMS](https://pubsonline.informs.org/doi/fpi/10.1287/deca.2013.0271)
- A follow-up study summarises Baker-McHale: with a Beta posterior on the win probability, "full Kelly where there is any uncertainty is not optimal". — [Kelly betting on horse races with uncertainty in probability estimates (arXiv 1701.02814)](https://arxiv.org/pdf/1701.02814)
- **Carver.** "Optimal risk target = Expected Sharpe Ratio" (Gaussian Kelly). "Most people think the Kelly formula is too aggressive. A better rule of thumb is to use half the optimal risk target." He suggests a new trader start by assuming SR 0.24 (risk target 12%) and scale up only after several profitable years. He runs at 25%. — [Carver, "How much risk should we take?", qoppac blog, Mar 2020](https://qoppac.blogspot.com/2020/03/how-much-risk-should-we-take.html)
- **Carver on Sharpe-ratio estimation error.** A 95% range for an estimated *relative* SR spans about 0.5 SR units. For US stocks vs bonds it is −0.16 to 0.36, which he calls "a huge degree of estimation error: our estimates of Sharpe Ratio are effectively worthless". (Search-snippet quote; see also his posts on optimisation under uncertainty.) — [Carver, "Portfolio optimisation, uncertainty, bootstrapping…", qoppac, Dec 2023](https://qoppac.blogspot.com/2023/12/portfolio-optimisation-uncertainty.html)
- **Half-Kelly trade-off.** A 0.5× Kelly multiplier keeps about 75% of maximum growth and cuts the variance of growth by about 75%. Half Kelly is "partly a hedge against your own overconfidence in the inputs." — [Wikipedia, Kelly criterion](https://en.wikipedia.org/wiki/Kelly_criterion); [MetricGate, Kelly optimal fraction](https://metricgate.com/docs/kelly-criterion-optimal-fraction/). (Secondary sources; the 75%/75% figure follows from growth g(k·f*) = (2k − k²)·g(f*).)
- **Kan & Zhou (2007).** Estimation risk "completely alters the theoretical recommendation of a two-fund portfolio". Holding the riskless asset plus the *sample* tangency portfolio is never optimal. A rule that combines riskless, sample-tangency and sample-GMV portfolios dominates it. — [Kan & Zhou (2007), JFQA 42(3):621–656, RePEc](https://ideas.repec.org/a/cup/jfinqa/v42y2007i03p621-656_00.html); [Cambridge abstract](https://resolve.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/optimal-portfolio-choice-with-parameter-uncertainty/A0E9F31F3B3E0873109AD8B2C8563393)

### Inferences (my derivations; Gaussian, one-period approximations)
- **Kelly with an uncertain mean.**
  - Plug-in Kelly fraction: f* = μ/σ².
  - If μ is unknown with posterior mean m and variance s², then E[growth] ≈ f·m − ½f²(σ² + s²), so f* ≈ m/(σ² + s²).
  - For a 5-day trade, σ_trade (several hundred bp of idio vol) far exceeds s (4 bp). Here the sign and size of m matter far more than the s² term: m_net ≈ −0.3 bp gives f* ≤ 0, i.e. no position.
- **Shrinking the plug-in bet.** The factor k that minimises expected squared error of k·f̂ around the true f is k* = μ²/(μ² + Var(μ̂)) ≈ t²/(1 + t²) (the same form as Baker-McHale-type shrinkage).
  - Soft news, gross (t = 3.7/4.1 = 0.90): k ≈ 0.45.
  - Soft news, net of 4 bp (t ≈ −0.07): k ≈ 0.005, and the sign is negative, so the optimal stake is 0.
  - Hard news, unvalidated: no estimate of t exists. A sceptical prior centred near zero gives k near 0. The case for keeping the hard-news book at its current small size is "learn by doing / produce data", not a growth-optimal one.
- **The decision is about leverage, not reallocation.** Moving the soft-news capital into the hard-news names raises their Kelly fraction with no new evidence about their edge. Under every Kelly-with-uncertainty variant above, the right change in total risk when the opportunity set shrinks is down, not flat.

### Gaps
- I could not verify the exact Kan-Zhou (2007) closed form for the optimal scaling of the sample tangency portfolio. My recollection is a factor of the form c* = [(T−N−2)/T]·θ²/(θ² + N/T), i.e. invest less in the risky portfolio when the true squared Sharpe θ² is small relative to N/T. It should be checked in the paper before use.
- I did not retrieve a primary MacLean-Thorp-Ziemba fractional-Kelly source this session (e.g. MacLean, Thorp & Ziemba, *The Kelly Capital Growth Investment Criterion*, World Scientific 2011).
- I found no DeMiguel-Garlappi-Uppal (2009) "1/N" numbers this session.

---

## 5. Practitioner and forum views: fixed names and gross, or variable gross ("only trade when you have edge")?

### Takeaway
I found little citable forum discussion in this session; searches of Reddit, Wilmott, QuantNet, Nuclear Phynance and Elite Trader returned no usable threads. What I did find leans toward letting gross float with the signal. In Carver's forecast-scaled systems, a zero forecast means a zero position. Gross exposure is a risk lever to monitor, not a fixed target. Treat this as weak evidence.

### Cited Findings
- **Carver.** Position size depends on "forecast confidence (forecast scaling)" and portfolio size. "Bigger portfolios mean proportionally less risk per position — if you have two positions on, you should have roughly half the average risk per position." (Search-snippet summary of his start-here page.) Positions scale with the forecast, so a zero forecast means no position. — [Carver, "Systematic trading: start here", qoppac](https://qoppac.blogspot.com/p/systematic-trading-start-here.html)
- **Industry framing (secondary).** "A fund with 0% net exposure but 400% gross exposure carries far more risk than a fund with 0% net and 100% gross." Market-neutral funds typically run about 150–300% gross. Managers "need to carefully monitor and potentially adjust gross exposure levels". (Opinion / secondary industry explainer.) — [AlphaMaven, market-neutral strategy explainer](https://alpha-maven.com/learn/market-neutral-strategy); [AIMA Canada, Equity Market-Neutral Strategy paper (2006)](https://www.hillsdaleinv.com/uploads/Equity_Market-Neutral_Strategy,_Author,_AIMA_Canada_Strategy_Paper_Series,_June_2006,_Pages_1-11.pdf)
- A hedge-fund news item reports a systematic equity manager changing gross (to 98%) while keeping net neutral, i.e. gross is varied in practice. — [Hedgeweek, Quantology](https://www.hedgeweek.com/systematic-equity-fund-quantologys-market-signals-are-strongly-positive-despite/)

### Inferences
- **Carver's sizing rule.** In Carver's framework the total risk target is set by Kelly/half-Kelly on the system's expected SR. Each instrument's share scales with its forecast. Dropping a rule (signal) that had no edge should not raise the risk of the remaining rules. Raising it would only be justified if the combined forecast's expected SR rose, which removing a zero-SR component does not do (apart from small diversification effects).
- **Pod-shop practice (not sourced).** Pod-shop style books often have a fixed GMV allocation from the risk desk. There, "leaving it uninvested" is felt as under-using capital. That is a business constraint (capital charge, payout on P&L), not a portfolio-theory argument, and it does not apply to a paper-traded research overlay.

### Gaps
- No primary forum quotes (r/quant, Wilmott, QuantNet, NP, Elite Trader, Quant.SE, X) were retrieved; the opinions there are unverified.
- No Robot Wealth, Giller, AQR, Man or Robeco note specific to "variable gross after a signal is dropped" was found this session.

---

## 6. Concentration vs breadth for a small book (about 10 names a side)

### Takeaway
At 10 names a side, idiosyncratic risk dominates. Moving to about 6 names a side at the old per-name size cuts idio volatility. Redistributing the same gross into 6 names a side raises idio volatility by about 29% (√(20/12)) and raises single-name event risk by two-thirds per name, with no evidence that the edge improves. Campbell et al. show that the number of stocks needed to diversify has risen over time.

### Cited Findings
- Firm-level variance more than doubled from 1962 to 1997 while market and industry variance stayed stable. Correlations fell, and "the number of stocks needed to achieve a given level of diversification increased". There was only a modest rise in the volatility of a typical 50-stock portfolio but "a much more dramatic increase in a typical two-stock portfolio". — [Campbell, Lettau, Malkiel & Xu (2001), J. Finance 56(1); NBER WP 7590](https://www.nber.org/papers/w7590.pdf); [NBER Digest summary](https://www.nber.org/digest/jun00/individual-stocks-have-become-more-volatile); [author PDF](https://personal.utdallas.edu/~yexiaoxu/clmx1_44.pdf)
- "Gross leverage amplifies the impact of stock selection errors on both sides, even when the portfolio appears market-neutral." (Secondary explainer.) — [AlphaMaven](https://alpha-maven.com/learn/market-neutral-strategy)

### Inferences (worked numbers)
Assumptions (mine, for illustration): annualised idio vol per S&P 500 name ω = 25%; idio returns independent; equal weights; base book gross 100% of NAV over 20 names (5% each); 40% of names (8) are soft-news. Idio vol of the book = ω·w·√N.

| Option | Names | Weight/name | Gross | Idio vol (annual) | Expected alpha | IR vs Option A |
|---|---|---|---|---|---|---|
| Base (before stop) | 20 | 5.0% | 100% | 0.25·0.05·√20 = **5.6%** | from 12 hard + 8 soft names | n/a |
| A: leave uninvested | 12 | 5.0% | 60% | 0.25·0.05·√12 = **4.3%** | 12·w·a | 1 |
| B: fill slots with zero-alpha names | 20 | 5.0% | 100% | **5.6%** | 12·w·a − extra costs | √(12/20) = **0.77**, minus costs |
| C: redistribute to survivors | 12 | 8.33% | 100% | 0.25·0.0833·√12 = **7.2%** | 20·w·a (×1.67) | 1 before costs; risk ×1.67 |

- **Option B** is strictly dominated: the same mean, √(20/12) = 1.29× the variance-driven risk, and more cost.
- **Option C** has the same IR as A (scale invariance). It is purely a decision to lever an unproven signal by 1.67×. Under §4 that is justified only if the hard-news Kelly fraction is above current exposure, which has not been shown.
- **Cost arithmetic.** If 40–68x NAV is one-way traded notional per year at 1–2 bp per side, annual cost is about 0.4%–1.4% of NAV.
  - If about 40% of trades were soft-news trades with about zero net edge, removing them (Option A) saves about 0.16%–0.54% of NAV per year.
  - Option B spends that cost again on new zero-edge fills.
  - Option C keeps the same cost per unit gross, so cost scales with the higher gross.
  - Per trade: 3.7 bp gross vs 4 bp round trip gives about −0.3 bp net.
- **Hedge interaction.** With a SPY hedge, lower gross means a smaller hedge notional and lower hedge trading. Net beta stays about 0 under all options. Only idio and factor risk changes.

### Gaps
- No direct estimate of current (2020s) per-name idio vol for S&P 500 constituents was retrieved; the 25% figure is an illustrative assumption.
- No source quantified diversification curves specifically for 10-a-side long/short books.
