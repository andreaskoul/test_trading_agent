# How multi-manager ("pod shop") and event-driven long/short PMs run small, concentrated equity books

Scope note on sources. The evidence base is uneven, and each source is labelled with its type:
- **[Practitioner]**: a named ex-pod person speaking on the record (Paleologo, Caughran).
- **[Press/explainer]**: secondary journalism or explainers.
- **[Anon newsletter]**: unattributed Substack content, which is plausible but unsourced. Treat it as anecdote.
- **[Study]**: an analytics vendor or a dataset.

Firms do not publish their PM risk limits. Every number below on pod limits is second-hand, and should be read as
"widely reported" rather than as a documented contract.

## 1. Typical pod structure: gross/net, names, position limits, factor neutrality, idio targets, drawdown stops, capital allocation

### Takeaway
A pod is a market-neutral (often also sector- and style-neutral) book. The PM is paid only for the idiosyncratic
residual. The pod sits inside a platform levered about 4–6x gross. It is governed by hard, mechanical drawdown
triggers, usually reported as about −5% (risk cut, often halved) and −7.5% to −10% (book unwound, PM out). Books are
far broader than 10 a side: a Tiger-style 10×15 book is said to become about 25×50 at a pod. Single names are capped
at a low single-digit % of gross.

### Cited Findings
**Leverage and net exposure**
- [Practitioner] Multi-manager funds run "400-600% gross leverage" at the platform level. Pod books turn over "5-10x
  per year". The target is "60-65%+ beta-neutralized idiosyncratic" return, with low correlation to the S&P 500 and to
  the GS hedge-fund VIP basket. The author is Brett Caughran (ex-Maverick, D.E. Shaw, Citadel, Two Sigma, Schonfeld;
  founder of Fundamental Edge). — [Caughran, "Beat the Pods: A 7-point recipe for single managers", LinkedIn/X, Sept
  2023](https://www.linkedin.com/pulse/beat-pods-7-point-recipe-single-managers-fundamental-edge);
  [X version](https://x.com/FundamentEdge/status/1700232675477618707)
- [Press/explainer] "A fund with $20bn in assets under management might have $100bn in capital to allocate to teams",
  with "some teams running, say, $200m and others managing billions." — [Byrne Hobart, "Multi-Manager/Pod/Hedge Fund
  101", Capital Gains (The Diff)](https://capitalgains.thediff.co/p/multimanagerpodhedge-fund-101)
- [Anon newsletter] Net-exposure bands are reported as typically −10% to +10% net, with beta-adjusted gross limits.
  — [Quant Enthusiasts, "Risk management inside a pod"](https://youngandcalculated.substack.com/p/risk-management-inside-a-pod-how)

**Number of names and per-name limits**
- [Practitioner] Moving from a Tiger cub to a pod, "a 10x15 (longs x shorts) Tiger portfolio needs to become something
  like 25x50". Caughran also describes "sizing triggers ahead of an event" on structural losers as something that
  "can scale across hundreds of potential ideas". This is a short-side breadth argument. — [Caughran, "Expanding my
  money making toolkit", X thread](https://x.com/FundamentEdge/status/1547619795952013313) (quoted in the search
  index; the X page itself is paywalled to fetchers)
- [Practitioner] Pod PMs cover about 250 stocks but "REALLY want to cover the most liquid 50". Names need enough daily
  volume that a position is 2–3% or less of ADV; "anything under $50m and certainly anything under $25m [ADV] starts
  to become very difficult". — [Caughran, "Beat the
  Pods"](https://www.linkedin.com/pulse/beat-pods-7-point-recipe-single-managers-fundamental-edge)
- [Anon newsletter] Single-name caps are "1% to 3% of gross book per name". Industry caps are 5–15% of gross per GICS
  industry. Liquidity is capped at 5–10% of 30-day ADV. Pod scale is "80 to 100 PMs each running $50m to $200m of
  gross capital" (sic, per platform). — [Quant
  Enthusiasts](https://youngandcalculated.substack.com/p/risk-management-inside-a-pod-how)
- [Press/explainer] "The typical coverage for an analyst at a pod shop is a few dozen stocks." — [Capital
  Gains](https://capitalgains.thediff.co/p/multimanagerpodhedge-fund-101)

**Factor neutrality**
- [Practitioner] "Platforms tend to run portfolios that have no market exposure whatsoever. And then they also tend to
  have controlled exposure in these more exotic factors." Speaker: Giuseppe "Gappy" Paleologo (ex-Citadel twice,
  Millennium head of enterprise risk, HRT head of risk; later head of quant research at Balyasny). The episode
  transcript misspells his name. — [Odd Lots, "How to Succeed at Multi-Strategy Hedge Funds", Bloomberg, 20 May 2024,
  transcript](https://podscripts.co/podcasts/odd-lots/how-to-succeed-at-multi-strategy-hedge-funds);
  [episode page](https://www.bloomberg.com/news/articles/2024-05-20/what-is-a-pod-shop-how-multi-strategy-hedge-funds-win)
- [Press/explainer] "The gentlest limitation is requiring portfolios to be beta neutral." Mandates "typically require a
  manager to balance their long and short positions on a risk-adjusted basis". The stricter versions neutralise style
  factors such as value, momentum and yield. — [Capital
  Gains](https://capitalgains.thediff.co/p/multimanagerpodhedge-fund-101)
- [Practitioner] Paleologo on Flirting with Models: PM coverage, factor hedging and internal alpha capture work
  together to maximise firm P&L. Factor hedging is organisationally and mathematically complex, and trading factor
  portfolios is "more expensive and dirtier" than a simple market hedge. — [Flirting with Models S7E11, 2 Sept
  2024](https://pocketcasts.com/podcasts/02f58c00-5b96-0136-606e-0b1b2a1cd099/0e8ebdb0-9cc2-46dd-9960-a7f8cafd5a04)
  (episode summary; I could not read a full transcript)

**Drawdown stops**
- [Press, eFinancialCareers] At Millennium, "if you lose 5% there, you'll usually get your capital allocation cut. If
  you lose 7.5% you'll be out." 15–20% of people leave each year, typically after being stopped out. — [eFinancialCareers,
  "How to get a job at Millennium"](https://www.efinancialcareers.com/news/2021/02/how-to-get-a-job-at-hedge-fund-millennium)
  (snippet via search; not fetched in full)
- [Press/explainer] "A mid-single digit percentage loss is enough to get a manager's allocation cut in half, and a
  high-single digit or 10% loss from peak is enough for them to be asked to leave." — [Capital
  Gains](https://capitalgains.thediff.co/p/multimanagerpodhedge-fund-101)
- [Anon newsletter] Millennium de-risks at about −5%; −7.5% to −10% means full wind-down. Citadel has "somewhat looser
  limits depending on pod and strategy". The triggers are "encoded in the risk system", and the PM is made to cut gross
  "mechanically" whatever their view of the thesis. — [Quant
  Enthusiasts](https://youngandcalculated.substack.com/p/risk-management-inside-a-pod-how);
  [same, "What senior PMs at multi-managers worry about"](https://youngandcalculated.substack.com/p/what-senior-pms-at-multi-managers)
- [Practitioner] About 20% of PMs "are let go or leave every year". "There are always stop losses, the ones that you
  know you have and the ones you don't know you have." — [Paleologo, Odd
  Lots](https://podscripts.co/podcasts/odd-lots/how-to-succeed-at-multi-strategy-hedge-funds)
- [Practitioner] The P&L profile wanted from a pod: "makes money 9-10 out of 12 months and limits losing months to
  under 100bps". Caughran also mentions capital-cut triggers near about 150 bp (context: monthly loss tolerance). —
  [Caughran, "Beat the Pods"](https://www.linkedin.com/pulse/beat-pods-7-point-recipe-single-managers-fundamental-edge)
- [Press] Example of speed: Bloomberg reported pods at BlueCrest and Millennium being closed quickly after the August
  2024 turmoil. — [BNN Bloomberg, 30 Aug 2024](https://www.bnnbloomberg.ca/investing/2024/08/30/bluecrest-millennium-pods-faced-quick-closure-after-turmoil/)
  (headline only; I could not retrieve the article text)

**Capital allocation**
- [Practitioner] A Sharpe/IR near 1 is roughly the survival bar: "If you have an information ratio of one and you are
  managing your left tail sufficiently wisely, you can survive." Successful PMs "do get more capital up to a point",
  and capacity is limited by market impact. — [Paleologo, Odd
  Lots](https://podscripts.co/podcasts/odd-lots/how-to-succeed-at-multi-strategy-hedge-funds)
- [Anon newsletter] Platforms reward Sharpe over raw return. "A single 3% monthly loss can eliminate gains from an
  entire year and trigger allocation review." — [Quant
  Enthusiasts](https://youngandcalculated.substack.com/p/what-senior-pms-at-multi-managers)

### Inferences
- The pod "unit" differs from the fund in three ways: (a) it is much broader (25–50 a side, versus about 10 here);
  (b) per-name caps are lower (1–3% of gross, versus about 10% of NAV here, which at 1.8x gross is about 5.5% of gross);
  (c) it is neutralised on sectors and styles, not just on market beta. A 10-a-side book with 10% name caps is closer
  to a Tiger-cub or single-manager event book than to a pod. Expected idiosyncratic volatility per unit of gross is
  therefore higher, and the drawdown stops pods use would be hit more often.
- The idio-share target (about 60–65%+ of return or variance) is a usable, documented-by-practitioner benchmark for
  this fund's book.

### Gaps
- Primary documentation of any firm's actual limits: none is public. All the 5% / 7.5% numbers are press or
  anonymous reports.
- Point72, Balyasny and ExodusPoint specific limits: I found no reliable specifics.
- Exact definitions of "% idio variance" thresholds used by platform risk teams: not found in open sources beyond the
  book (see section 5).

## 2. Fixed versus variable gross, and treatment of idle capital

### Takeaway
I found no open, on-the-record source that says pod PMs must keep gross at a fixed target. The documented mechanics
are all asymmetric:
- gross has a **ceiling** (the allocated capital or limit);
- gross is **cut mechanically** after drawdowns;
- capital is grown "up to a point" after good performance.

The book-level practice described by practitioners is to vary gross with idea quality and the catalyst calendar, not
to refill slots. Paleologo's framework favours targeting **constant dollar volatility** over constant GMV. That is
different from fixed slots.

### Cited Findings
- [Practitioner] Pod platforms show pro-cyclical de-grossing in volatility events, because the 400–600% leverage
  wrapper forces fast risk cuts. — [Caughran, "Beat the
  Pods"](https://www.linkedin.com/pulse/beat-pods-7-point-recipe-single-managers-fundamental-edge)
- [Anon newsletter] At the soft stop (about −5%) "risk gets cut by roughly half, and the PM keeps trading at reduced
  gross". — [Quant Enthusiasts, "How PMs actually get fired at multi-manager hedge
  funds"](https://youngandcalculated.substack.com/p/how-pms-actually-get-fired-at-multi) (search snippet)
- [Book, Paleologo 2021, table of contents and figure list; the chapter text was not accessible]
  - Chapter 6.6 is titled "Time-Series Risk-Based Portfolio Targeting".
  - Tables 6.5–6.6 compare the "Sharpe Ratio of unit-GMV and unit-dollar volatility scaling". The book tests
    holding gross constant against holding dollar volatility constant.
  - Figure 9.1 plots "Deployed Capital as a function of drawdown for Grossman-Zhou optimal" policy, i.e. deployed
    capital falling as drawdown deepens.
  - Section 2.7 says that on platforms "leverage decisions are the responsibility of the firm".

  — [Wiley reading sample, Paleologo, *Advanced Portfolio Management*
  (2021)](https://content.e-bookshelf.de/media/reading/L-17016607-93ad8eb52e.pdf)
- [Practitioner] From the same book's preface: "The output of your fundamental research changes continuously. The rules
  of your risk management process should not. They should be predictable, implementable, effective. These usually come
  in the form of limits: on your deployed capital, on your deployed portfolio risk… single-position maximum size". —
  [Paleologo 2021, §2.5, reading
  sample](https://content.e-bookshelf.de/media/reading/L-17016607-93ad8eb52e.pdf)
- [Practitioner/blog snippet] As pods compete harder, "opportunities are smaller", and "as anomalies become smaller,
  the bar should be higher for ideas in your portfolio". This argues for a quality bar rather than filling a quota. —
  [Caughran, "Beat the
  Pods"](https://www.linkedin.com/pulse/beat-pods-7-point-recipe-single-managers-fundamental-edge) (from search
  summary)

### Inferences
- The pod analogue of "keep 10 slots full" does not exist. The constraint is a risk budget: a gross ceiling, a vol or
  drawdown budget, and neutrality. The number of names is an output, not a target. Practitioners talk about the
  idea-quality bar rising as edges shrink, which implies leaving capital unused rather than lowering the bar.
- Unused gross in a pod has little cost to the PM, because the PM is judged on Sharpe and drawdown, not on capital
  usage. It has an opportunity cost to the platform, which may reallocate capital to other PMs over time. I found no
  source on a "use it or lose it" rule. That is a gap, but anecdotally such rules exist; this is unverified.
- Paleologo's unit-GMV against unit-dollar-vol comparison is the formal version of the fund's question. A
  constant-vol target lets gross float inversely to vol. It does not by itself let gross float with *opportunity
  count*. With a fixed per-name size and a variable count, gross floats with opportunity.

### Gaps
- No primary quote from a named pod PM saying "I run lower gross when I have fewer ideas" was retrievable. Wall Street
  Oasis threads returned 403 to the fetcher. The content of Paleologo's §6.6 and Table 6.5 (which method won) could not
  be read from a legitimate open source.
- Firm-level policy on minimum capital utilisation (any "use-it-or-lose-it" rule) is undocumented in what I found.

## 3. Event-driven and catalyst books: sizing around events, event types, holding periods, hit rate against slugging

### Takeaway
At pods, earnings are the dominant catalyst class. Print days are about 2% of trading days but carry about 20% of
idiosyncratic volatility, and a pod PM may spend about 40% of their time on earnings. Sizing is set by the expected
event move and positioning, with deliberate timing of entry. Across long/short equity, sustained hit rates above 50%
are rare; good managers live at about 50–55% and make their money on payoff (win/loss) and sizing.

### Cited Findings
- [Practitioner] "Print days are 2% of year's trading days but generate ~20% idiosyncratic volatility." Earnings season
  is "a critical catalyst event for MM portfolios" given the 9+/12 positive-month goal and the 400–600% gross
  wrapper. — [Caughran, "Beat the
  Pods"](https://www.linkedin.com/pulse/beat-pods-7-point-recipe-single-managers-fundamental-edge)
- [Practitioner] "At a Tiger-cub I spent ~10% of my time thinking/planning for earnings and as a pod PM I spent ~40%."
  — [Caughran thread, Thread Reader](https://threadreaderapp.com/thread/1552413316798025728.html)
- [Practitioner] Paleologo's list of fundamental PM catalysts: "Earning events and other catalysts like product
  launches, drug approvals, sell-side upgrades/downgrades are an important source of revenue for fundamental PMs".
  - On timing: "Positioning too early exposes the PM to unwanted risk in the days preceding the event."
  - PMs "may over-trade, either by opening and closing positions more aggressively than needed, or by adjusting too
    often the size of a position over the lifetime of the trade."
  - Appendix §11.9 is "Optimal Event Trading".

  — [Paleologo 2021, §2.4, reading
  sample](https://content.e-bookshelf.de/media/reading/L-17016607-93ad8eb52e.pdf)
- [Study] Essentia Analytics, 76 active equity portfolios over 3 years: only 18% of PMs made more value-adding than
  value-destroying decisions across stock picking, entry, sizing, scaling and exit. Payoff matters more than hit
  rate. — [Clare Flynn Levy, "Manager Selection: The Power of Payoff", CFA Institute Enterprising Investor, 21 Nov
  2022](https://rpc.cfainstitute.org/blogs/enterprising-investor/2022/manager-selection-the-power-of-payoff)
- [Study] Equity long/short managers:
  - The win/loss ratio was "almost 6x more variable" over time than the hit ratio.
  - "Very few managers are able to sustain meaningfully higher than 50% hit ratios over the long run."
  - "The ability to size winners larger than losers" is a disproportionate driver of returns.

  — [Resonanz Capital, "Decoding Manager Success: An Analysis of Equity Long/Short
  Returns"](https://resonanzcapital.com/insights/decoding-manager-success-an-analysis-of-equity-long/short-returns)
- [Study/anecdote, via search summary] Some equity hedge funds report hit ratios of 50–60%. One large manager credited
  a long record to a 51% hit ratio. One portfolio database averaged a 49.6% hit rate. — [Moneyfarm, "Hit ratios and
  skew"](https://blog.moneyfarm.com/en/?p=11872); [Vontobel, "Rich or
  right?"](https://am.vontobel.com/en/insights/rich-or-right) (from search summaries, not fetched in full; check
  before quoting)
- [Book] Paleologo's attribution splits idiosyncratic P&L into selection, sizing and timing. As summarised by a
  reviewer, PMs "excel primarily at stock selection, show moderate-to-negative sizing skill, and possess minimal timing
  ability". — [Chasing the Vig, book
  review](https://chasingthevig.substack.com/p/advanced-portfolio-management-book); formal version in [Paleologo,
  "Information Ratio = Selection × Breadth + Sizing", *Journal of Portfolio Management*
  49(8)](https://www.pm-research.com/content/iijpormgmt/49/8/71)

### Inferences
- Catalysts with a scheduled date and a measurable "expected move" (earnings, FDA dates, deal votes) are the core of
  pod event trading. Unscheduled "soft" news (launches, partnerships, management talk) appears in Paleologo's catalyst
  list only as a lesser category. That fits the fund's finding that soft news has about zero edge after costs.
- With hit rates near 50%, a 10-a-side book's edge rests on payoff and sizing. Paleologo's evidence that most PMs have
  zero or negative sizing skill argues against conviction-weighting beyond a simple rule.

### Gaps
- Number of catalyst trades per year per PM, and typical holding periods for pod event trades: not found in reliable
  open sources. The only proxy is 5–10x annual book turnover (Caughran), which implies average holding periods of about
  5–10 weeks.
- Hit rates specific to pod PMs (rather than to long/short funds generally): not found.
- Which event types pods avoid (for example binary biotech readouts and M&A rumours): no sourced statement found.

## 4. Risk practices relevant to a 10-a-side book: name stops, ETF hedges, crowding, earnings-gap limits

### Takeaway
Pods hedge market (and often sector and style) exposure. They enforce stops at the book level, and Paleologo argues
these stops are mandatory "explicit or implicit". They cap names as a % of gross and of ADV, and they treat earnings
prints as concentrated idio-risk events. Crowding is a recognised platform-level risk: pods "piling into the same
trades" has drawn regulator attention. I found no reliable open source for specific name-level stop-loss percentages
or earnings-gap limits.

### Cited Findings
- [Book] Chapter 9 ("Manage Your Losses") covers "How Stop-Loss Works", "Why a Stop-Loss Policy?" and "The Costs and
  Benefits of Stop-Loss". Figure 9.2 is "Impact of stop-loss on performance"; Figure 9.3 is "Relationship between
  efficiency of a strategy and stop-loss". Preface: "The Prime Directive… is to survive." — [Paleologo 2021, reading
  sample](https://content.e-bookshelf.de/media/reading/L-17016607-93ad8eb52e.pdf)
- [Press] Citadel and its peers piling into the same trades has drawn regulator notice (crowding among
  multi-managers). — [Financial Advisor magazine (Bloomberg syndication), "Citadel and its peers are piling into the
  same trades; regulators are taking
  notice"](https://www.fa-mag.com/news/citadel-and-its-peers-are-piling-into-the-same-trades--regulators-are-taking-notice-75584.html?page=2)
  (title and snippet only)
- [Practitioner] Paleologo on Flirting with Models: factor models explain only part of drawdowns. A large part comes
  from "higher-order" idiosyncratic-systematic components, which is crowding-like co-movement. — [Flirting with Models
  S7E11 summary](https://podwise.ai/episodes/1750714)
- [Anon newsletter] Name caps are 1–3% of gross. Industry caps are 5–15%. ADV caps are 5–10%. Drawdown-triggered gross
  cuts happen "regardless of the PM's view on whether… the thesis is intact" (no averaging down). — [Quant
  Enthusiasts](https://youngandcalculated.substack.com/p/risk-management-inside-a-pod-how)

### Inferences
- For a 10-a-side book, the binding risk is single-name gap risk on prints. With pods at about 25–50 names a side, an
  earnings gap on one name is about 2–4% of gross. Here it can be about 5–10% of NAV. A pod-style rule would be to
  size down or exit ahead of scheduled prints the desk did not select the trade for.
- The fund already has drawdown-like protections (Protocol 7B: no averaging down). These match pod practice.

### Gaps
- Specific name-level stop-loss levels (for example −X% from entry) at named platforms: not found.
- Earnings-gap exposure limits (for example the maximum % of book reporting in one week): not found.

## 5. Paleologo, *Advanced Portfolio Management* (Wiley, 2021): concrete guidance

### Takeaway
Paleologo's guidance comes in five parts:
- Hedge everything you have no edge in ("invest in your edge, and hedge the rest").
- Size by a simple rule rather than by a full mean-variance optimisation. Proportional and risk-parity-style rules beat
  mean-variance in his simulations.
- Cap factor risk with explicit limits: an idio-variance share, a market-exposure limit, and a single-stock limit set
  by coverage breadth.
- Analyse P&L into selection, sizing and timing.
- Use a stop-loss policy and keep turnover modest.

Concentration should depend on whether high-conviction ideas actually earn more. Most PMs' "conviction profitability
ratio" is 1 or less.

### Cited Findings
- [Book, TOC] Chapter 6, "Use Effective Heuristics for Alpha Sizing", covers Sharpe Ratio, Estimating Expected Returns,
  Risk-Based Sizing, Empirical Analysis of the Sizing Rules, From Ideas to Positions, and Time-Series Risk-Based
  Portfolio Targeting. Chapter 7.2, "Strategic Factor Risk Management", covers setting an upper limit on factor risk,
  on market exposure and on single-stock holdings. Appendix 11.4 is "Proportional-Rule Formulations"; 11.8 is
  "Hedging Formulations"; 11.9 is "Optimal Event Trading". — [Wiley reading
  sample](https://content.e-bookshelf.de/media/reading/L-17016607-93ad8eb52e.pdf);
  [Wiley-VCH product page](https://www.wiley-vch.de/de/fachgebiete/finanzen-wirtschaft-recht/advanced-portfolio-management-978-1-119-78979-6)
- [Book, via search-index excerpts; the chapter text was not read directly] The three sizing rules compared are:
  - **Proportional**: NMV ∝ α (conviction). Stock volatility does not enter the size.
  - **Risk parity**: NMV ∝ α/σ. One variant shrinks each stock's idio variance toward its sector average.
  - **Mean-variance**: NMV ∝ α/σ².

  Results reported: "realized Sharpe Ratio is consistently higher for risk parity and the proportional rule than for
  mean-variance". As signal dispersion rises, the proportional rule pulls ahead, risk parity degrades less, and
  mean-variance underperforms. — [Google Books record, Paleologo
  2021](https://books.google.com/books/about/Advanced_Portfolio_Management.html?id=-yk1EAAAQBAJ) (the excerpts surfaced
  through search; confirm against the book's §6.3–6.4 before quoting)
- [Book, list of tables and figures]
  - Table 7.3: "Risk-adjusted losses for keeping a percentage of idio variance below…". It sets a floor on the share
    of variance that is idiosyncratic.
  - Figure 7.1: "Relationship between percentage idio var and risk-adjusted performance".
  - Table 7.4: "Single-Stock Limit, based on coverage breadth and ratio between ret…". The single-name cap depends on
    how many stocks the PM covers.
  - Table 3.6: "Portfolio example, with increasing number of stocks".

  — [Wiley reading sample](https://content.e-bookshelf.de/media/reading/L-17016607-93ad8eb52e.pdf)
- [Review] Conviction Profitability Ratio: "The larger the ratio between realized returns for high-conviction stocks
  and low-conviction ones, the more concentrated the portfolio can be." Most PMs achieve a CPR of 1 or less; top
  performers rarely exceed 2. "Diversification [is] a skill multiplier." — [Chasing the Vig
  review](https://chasingthevig.substack.com/p/advanced-portfolio-management-book)
- [Practitioner, Odd Lots] Platforms run "no market exposure whatsoever" with controlled exotic-factor exposure. An IR
  near 1 with left-tail control is the survival bar. — [Odd Lots transcript, May
  2024](https://podscripts.co/podcasts/odd-lots/how-to-succeed-at-multi-strategy-hedge-funds)
- [Practitioner] Related Paleologo paper: "Information Ratio = Selection × Breadth + Sizing", *Journal of Portfolio
  Management* 49(8). It formalises IR as stock-selection skill times breadth, plus a sizing term. — [PM
  Research](https://www.pm-research.com/content/iijpormgmt/49/8/71)

### Inferences
- For this fund, Paleologo's framework points to five things:
  - Size each name by a simple rule (equal or proportional to expected return, or scaled by idio vol), not by an
    optimiser.
  - Hedge market and sector. The fund already uses SPY and sector ETFs, as owner policy.
  - Monitor the % of variance that is idiosyncratic, with an explicit floor.
  - Derive the single-name cap from breadth: fewer names imply a lower Sharpe ceiling, not a higher cap.
  - Test whether gross should be "unit-GMV" (fixed) or "unit-dollar-vol" (floating). This is his own framing of the
    fund's question.
- The CPR test is directly implementable on the fund's own records. If the desk's high-confidence picks do not earn
  more than its low-confidence picks (CPR ≤ 1), concentration (10% caps) is not justified.
- Breadth logic (IR ∝ selection × √breadth): cutting the soft-news class reduces breadth. Holding gross fixed by
  re-allocating the freed gross to the remaining names raises per-name concentration without raising selection skill.
  That is the trade-off the fund faces.

### Gaps
- Exact numeric recommendations in the book (for example the specific idio-variance floor, such as "≥ 70%"; the exact
  single-stock-limit formula; turnover targets; stop-loss parameters; which of unit-GMV or unit-vol won) could not be
  verified from a legitimate open copy. They should be read from the book itself (§6.3–6.6, §7.2, Ch. 9) before being
  cited as numbers.
