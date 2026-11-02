# Practitioner forum and community views on running a small L/S equity book after a signal stop

Scope: opinions from forums, Q&A sites, practitioner blogs and social posts, not academic papers. Everything below is
**opinion**. Credibility tags used on every item:
- **[named practitioner]**: identifiable person with a public track record (e.g. Rob Carver, ex-AHL; Kris Longmore, Robot Wealth; Kris Abdelmessih, ex-options market maker; Giuseppe Paleologo, Balyasny head of quant research).
- **[WSO-certified]**: Wall Street Oasis "Certified Hedge Fund Professional" badge. WSO checks this; the person is still anonymous.
- **[anonymous]**: Reddit, Hacker News or Elite Trader handle with no verification.
- **[vendor]**: a firm that sells position-sizing or analytics software, so it has a commercial interest.

Access caveat: Reddit blocked automated page fetches (Tavily extract failed). An alternate-route attempt was refused by
this session's permission policy and was not pursued. **All Reddit quotes below are search-engine snippets, not
full threads**, and are marked "(snippet)". The thread context, the author handle and sometimes the exact date could
not be checked. Dates for Reddit snippets are approximate where the thread ID was the only clue. Wilmott, QuantNet and
Nuclear Phynance searches returned nothing relevant on these questions.

## Q1. After dropping a signal: refill to fixed names/gross, or run lower gross / hold cash?

### Takeaway
No forum thread found addresses "a signal was switched off; do we refill?" directly. The practitioners who speak about
gross say it is an **output of risk (volatility, factor limits) and of the ideas available, not a fixed target**. Pod
PMs cut gross when vol is high. A multi-strategy partner says gross is a function of portfolio vol and is cut when
signals are "average". Retail and trader forums repeat "cash is a position" / "don't force trades" as folk wisdom. One
LLM-agent builder warns of the opposite failure: an LLM decision-maker is biased towards holding too much cash.

### Cited Findings
- Pod PM (Oct 2026 AMA): vol "is not something I target, but it's an output of our ideas… if vol is simply too high… I'll find ways to reduce it by **reducing gross**, sizing down volatile positions, sometimes even sizing up risk reducing positions. Risk definitely will call me out when vol is too high and yes that's often at the most inopportune times." **[WSO-certified PM]** — [WSO "Q&A: I'm a Pod PM", Oct 2026](https://www.wallstreetoasis.com/forum/hedge-fund/im-a-pod-pm-ask-me-anything)
- Same PM: when factor exposure gets outsized, "sometimes that's **cutting low conviction names** that add to that specific exposure or sizing up medium conviction names that reduce the exposure." So in his practice, dropping names to cut gross is normal; refilling is not automatic. **[WSO-certified PM]** — [same thread](https://www.wallstreetoasis.com/forum/hedge-fund/im-a-pod-pm-ask-me-anything)
- Self-described multi-strategy hedge fund partner (r/SecurityAnalysis IAmA, c. 2016): "Gross exposure is a function of portfolio vol. When vol spikes, we cut exposure. When there is an uptrend, we are net long." A second snippet from the same thread: "Our alpha signals are very average at bets. When the market is flat we will reduce…" (snippet cut off there). **[anonymous; unverified "partner"] (snippet)** — [r/SecurityAnalysis IAmA](https://www.reddit.com/r/SecurityAnalysis/comments/47yrup/iama_partner_with_a_multi_strategy_hedge_fund)
- A senior quant recalls pressure the other way, toward *adding* size: "If an intelligent PM sees through this and refuses to increase size, CIO's alpha capture book steps in and increases that pod's size." This shows platforms can push capital deployment regardless of the PM's view of the edge. **[anonymous] (snippet)** — [r/quant "How did you survive the 2018-2020 quant winter?"](https://www.reddit.com/r/quant/comments/1r1utpr/senior_quants_how_did_you_survive_the_20182020)
- Elite Trader "Top 50 Trading Quotes" compilation (2026). Under Bill Lipschutz's "If most traders would learn to sit on their hands 50 percent of the time, they would make a lot more money", the poster adds: "Pitch: **Cash is a position.** Action: Filter your trades aggressively. If it's not perfect, pass." Under Jim Rogers: "Trade less, but trade bigger when the setup is perfect." **[anonymous compiler of famous-trader quotes; aimed at discretionary traders]** — [Elite Trader, Top 50 Trading Quotes](https://www.elitetrader.com/et/threads/top-50-trading-quotes.388762)
- Elite Trader beginners' list: "The market doesn't pay you for activity. It pays you for good decisions… more trades… Usually it equals more commissions and more mistakes." **[anonymous]** — [Elite Trader, 10 Biggest Mistakes](https://www.elitetrader.com/et/threads/the-10-biggest-mistakes-new-traders-make-and-how-to-avoid-them.390339)
- An LLM-agent trading builder (2026): "Another big one from my experience is the **bias to inaction** in a scenario with risk. This means a model without structure around it will bias to **keeping too much cash**." **[anonymous HN]** — [Hacker News, Multi-Agents LLM Financial Trading Framework, ~Sep 2026](https://news.ycombinator.com/item?id=49605822)
- Rob Carver's systems size each position in proportion to forecast strength and drop rules whose costs exceed his "speed limit". Gross therefore floats with the signal; it is never refilled to a target. **[named practitioner]** — [qoppac, "My trading system", Dec 2021](https://qoppac.blogspot.com/2021/12/my-trading-system.html)

### Inferences
- The professional sources (pod PM, multi-strategy partner, Carver) treat gross as **risk- and signal-determined**. None of them describes refilling a book to a fixed name count after losing an alpha source. This matches the academic and pod-shop notes in this folder: lower gross, keep each name's risk the same.
- The "cash is a position" material is discretionary-trader folk wisdom: widely repeated, with no evidence attached. It is consistent with the pros, not independent support for them.
- The HN warning applies directly to an LLM-picked book. If an LLM desk is allowed to "hold cash", its bias to inaction could quietly lower gross for reasons that are not edge. A mechanical rule (e.g. "a slot with no qualifying idea stays empty") is better than leaving it to the model's discretion.

### Gaps
- No thread found that asks "we switched off a signal: refill or not?" for a systematic L/S book.
- Searches for "variable gross" in Wilmott, QuantNet or Nuclear Phynance returned nothing relevant.
- Full Reddit threads (including the IAmA) could not be read, so the partner's full answer is unknown.

## Q2. Position sizing: equal vs conviction vs vol/risk-parity; names per side; per-name caps

### Takeaway
Pod-level practitioners describe sizing as conviction plus volatility plus portfolio fit, under hard vol and factor
limits from the risk team. They describe books of **dozens to 150 names**, because "the only way to sufficiently reduce
volatility is by having a sufficient number of positions." One pod PM admits his top-5 conviction names return about
the same as his median name. Vendor data says the median manager adds roughly 2%/yr through sizing versus equal
weight, but over 40% of managers lose by sizing. Paleologo stresses that the role of sizing depends on book
structure. Nobody in these sources recommends ~10 names a side for a market-neutral book.

### Cited Findings
- Number of names in a pod: "**120-150 names**. All MM books have target volatility and factor risk limits set by the risk team. Max volatility depends on the MM, but is generally **5-7%**. And the only way to sufficiently reduce volatility is by having a sufficient number of positions." Another reply: "Team I was on had **30-40 per subsector**, >5 subsector books." A WSO-certified PM in the thread cites "my lived experience at MLP and now P72." **[anonymous (first two) / WSO-certified]** — [WSO "Number of positions held by a PM in L/S pod?", Dec 2024](https://www.wallstreetoasis.com/forum/hedge-fund/number-of-positions-held-by-a-pm-in-ls-pod)
- Pod PM on sizing: "Mostly my gut to be honest. For sizing it's a combination of **conviction, risk asymmetry, volatility, and how it fits into the portfolio**." **[WSO-certified PM]** — [WSO Pod PM Q&A, Oct 2026](https://www.wallstreetoasis.com/forum/hedge-fund/im-a-pod-pm-ask-me-anything)
- Same PM on conviction: "I honestly haven't had great success in my top 5 ideas at a given time (ie the **top 5 positions in our book return on a % basis in line with the median name**)." He also says his book is "fairly diversified and I would guess I take less name specific concentration than average." **[WSO-certified PM]** — [same thread](https://www.wallstreetoasis.com/forum/hedge-fund/im-a-pod-pm-ask-me-anything)
- Paleologo: "1. Sizing has a very different role when your portfolio is made of 2-3 positions a time, held for year(s). 2. Determining skill is harder when all your wealth comes from making 20 big bets in your entire career." **[named practitioner; X post; date not visible, the post ID suggests about April 2025]** — [X @__paleologo](https://x.com/__paleologo/status/1908487439879975360)
- Quant StackExchange answer on standard construction: rank the stocks, then set "Positions in the portfolio… **proportional to the cross-sectionally de-meaned rank**… normalised so that the total dollar amount of the long and short sides… are equal to some target." Or use top/bottom terciles, "equal weighted, cap weighted or some other weighting scheme" within each. **[anonymous SE answerer]** — [Quant SE Q54391](https://quant.stackexchange.com/questions/54391/any-portfolio-models-not-based-on-asset-return-moments)
- Novus (2016) on 2010–2015 manager holdings: "**57.5%** of our HFU managers outperformed equally-weighted versions of themselves, and **41% underperformed**… for those that do make money, sizing decisions add an average of 2.77% a year… Managers that underperform equal weight versions lost an average of 1.56% per year." **[vendor]** — [Novus, "The Skill of Prediction: Hedge Fund Position Sizing", May 2016](https://www.novus.com/blog/skill-prediction-hedge-fund-position-sizing)
- Alpha Theory (2025): "The median actual portfolio outperforms an equally weighted version by **+2.0%**." It also says equal weight "often performs better than most would guess because periodic rebalancing naturally takes profits from winners." **[vendor; sells sizing software]** — [Alpha Theory, Ultimate Guide to Position Sizing pt 1, Mar 2025](https://www.alphatheory.com/blog/the-ultimate-guide-to-position-sizing---part-1-sizing-matters-but-how-much); [Alpha Theory, "What is position sizing", Nov 2025](https://www.alphatheory.com/blog/what-is-position-sizing)
- WSO "Personal account: how to size a trade" (2025): one reply says "As Druck said, you have to **press the bet**… I'd err on sizing big." Another reply advises scaling in as conviction grows and sizing smaller when an asset is volatile or illiquid. **[anonymous; discretionary personal-account context]** — [WSO, Apr 2025](https://www.wallstreetoasis.com/forum/hedge-fund/personal-account-how-to-size-a-trade)
- Brian DeChesare (Mergers & Inquisitions), describing L/S structures: "A group with 100 positions and holding periods of weeks or months will be much more like 'trading,' while one with 10 positions and multi-year holding periods will be much more like long-term investing." At multi-managers, L/S "is more about getting quarters right." **[named industry-training writer, not a PM]** — [M&I, Long/Short Equity guide, Apr 2022](https://mergersandinquisitions.com/long-short-equity)
- Kris Abdelmessih (Moontower) on edge and sizing: "if you size your bets appropriately you can survive to realize that… margin in the long run. **Small edges are pure gold if you get enough chances.**" **[named practitioner]** — [Moontower Primer #3, "The Nature of Edge"](https://moontower.substack.com/p/primer-3-the-nature-of-edge)

### Inferences
- In these sources, a weekly-turnover book of short-holding-period trades (the M&I "trading" end) runs **many** names. ~10 names a side is at the concentrated end. The WSO view that vol targets force breadth argues against concentrating further when ideas are scarce.
- The evidence that conviction weighting adds value is mixed and comes mostly from vendors. The anecdote that "top 5 = median" and the 41% of managers who lose by sizing suggest that, for an LLM-picked book with unproven conviction calibration, equal-risk or equal-weight is the safer default. That is an inference, not a forum consensus.
- Nobody discussed explicit per-name caps for a 10-name side. Pod practice is to impose vol and factor limits at book level.

### Gaps
- No forum source on per-name caps for a ~10-per-side market-neutral book.
- No forum discussion of inverse-vol versus equal-dollar weighting specifically for large-cap S&P names.

## Q3. Is a small edge (a few bp/trade, hit rate 52–58%) real and worth trading after costs?

### Takeaway
Practitioners agree that **costs are certain and edge is uncertain**, so a small edge needs either many independent
bets or a cost budget that is a small fraction of expected return. Carver gives the only explicit rule of thumb: a
"speed limit" on costs measured in Sharpe units. Abdelmessih quantifies how many trials a small edge needs. Forum
voices are blunt about backtest leakage and multiple testing: "999 out of 1000 winning models" come from look-ahead
bias, and "You cannot backtest LLMs."

### Cited Findings
- Carver's cost "speed limit": he excludes "any rules which a particular instrument can't trade because the costs exceed my 'speed limit' of **0.01 SR units**" per trade. In replies: "In the book… I suggest a maximum of **0.13 SR per year**." He reports his own costs as "1.06% a year: well below my speed limit (1.06 / 25 = 0.042 SR units)." **[named practitioner]** — [qoppac, "My trading system", Dec 2021, post plus comment of 2 Dec 2021](https://qoppac.blogspot.com/2021/12/my-trading-system.html)
- Carver on how much data significance needs: "It's rare to have enough data for any one instrument to be able to say with any statistical significance that this trading rule is better than the other one. We often need **decades of data**… But if you have 30 instruments with 10 years of data each, then that's three centuries worth." **[named practitioner]** — [qoppac, "Optimising weights with costs", 2016](https://qoppac.blogspot.com/2016/05/optimising-weights-with-costs.html)
- Carver on a published optimal-window result: "isn't statistically significant- all the account curves shown are indistinguishable from each other and from noise." **[named practitioner; blog comment, Jan 2017]** — [qoppac, 2015 post comments](https://qoppac.blogspot.com/2015/10/a-little-demonstration-of-portfolio.html)
- Kris Abdelmessih: "If you have a 1% edge on a coin flip… you need **nearly 7000 trials to be 95% sure** you are profitable. That's over 25 trades a day for a year. What if you had a 5% edge? With only 1 trade per day, you'd be 95% sure." **[named practitioner]** — [Moontower Primer #3](https://moontower.substack.com/p/primer-3-the-nature-of-edge)
- Kris Longmore (Robot Wealth): "**Trading costs are guaranteed, while your trading edge is uncertain** and difficult to measure… your edge is uncertain – not only do you usually not know how big it is, you also don't know if it even exists anymore." **[named practitioner]** — [Robot Wealth, No-Trade Region, Jun 2025](https://robotwealth.com/reduce-trading-costs-and-boost-profits-with-the-no-trade-region-strategy)
- r/algotrading (2025–26) on a tested edge: "It's statistically real. But it's small, and **after costs there isn't much left**. Knowing when to stop testing is part of the method." **[anonymous] (snippet; thread not identified)** — [r/algotrading](https://www.reddit.com/r/algotrading)
- Same theme: "If your true effective cost is even **4-5 bps round trip**, the live edge can go to zero or negative while the backtest still looks fine." **[anonymous] (snippet)** — [u/PapersWithBacktest, Reddit](https://www.reddit.com/user/PapersWithBacktest)
- r/algotrading: "signal accuracy ≠ edge, costs matter more than you think." **[anonymous] (snippet)** — [r/algotrading "From live trading bot → disciplined quant system"](https://www.reddit.com/r/algotrading/comments/1qi4if6/from_live_trading_bot_disciplined_quant_system)
- r/quant on a claimed signal: "**I see a machine, not an edge.** What is your alpha, because not a single thing that you have written on this thread indicates there is one." **[anonymous] (snippet)** — [r/quant "What to do with alpha signal but no capital"](https://www.reddit.com/r/quant/comments/1wv3j22/what_to_do_with_alpha_signal_but_no_capital_to)
- Hacker News (Mar 2026), someone running LLM agents over academic strategies: "**999 out of 1000 winning models do so because of look-ahead bias**… one didn't convert the time zone from UTC to EST, so five hours of future knowledge got baked into the model." **[anonymous HN]** — [HN "Ask HN: What Are You Working On? (March 2026)"](https://news.ycombinator.com/item?id=47303111)
- Hacker News (~Dec 2025) on LLM trading tests: "**You cannot backtest LLMs. You can only 'live' test them going forward.**" (Model training data contains the future.) A reply in another thread: "The problem is the bots may have some of the backtest data already in their training." **[anonymous HN]** — [HN "We gave 5 LLMs $100K to trade stocks"](https://news.ycombinator.com/item?id=46154491); [HN Sep 2026](https://news.ycombinator.com/item?id=49686380)
- Quant StackExchange, asked "how many live trades… to have a high confidence that I have not overfitted": the answer refuses a fixed number. Significance belongs to the estimation step, and "answers would be of the 'the more, the better' type." **[anonymous SE answerer, Jun 2018]** — [Quant SE Q40357](https://quant.stackexchange.com/questions/40357/for-a-trading-strategy-how-many-trades-have-to-occur-for-statistical-significanc)
- Elite Trader: "I finally found my edge… a 69% win ratio. However, I had to fail and fail over and over… I had 2 years worth of trades journaled… **over 1000 trades** to analyze." This shows forum practice judging edge by raw trade count, without correcting for multiple testing. **[anonymous; discretionary]** — [Elite Trader "Define Edge" p.2, 2022](https://www.elitetrader.com/et/threads/define-edge.365108/page-2)
- Medallion is described as "looking for **very, very small profits that are very, very certain** on positions over quite short timescales." **[anonymous] (snippet)** — [r/quant "The Mystery behind Jim Simons' Medallion Fund"](https://www.reddit.com/r/quant/comments/1qzc7pk/the_mystery_behind_jim_simons_medallion_fund)

### Inferences
- Applying Abdelmessih's arithmetic to this fund (my calculation, not his): a net edge of ~4 bp per name-week against a single-name weekly residual sd of ~300–400 bp is an edge/sd of ~0.01. Detecting it at 95% needs on the order of (1.96/0.011)² ≈ 30,000 *independent* name-weeks. ~20 names × 52 weeks ≈ 1,000 a year, and names in a weekly cohort are correlated. A few-bp edge therefore cannot be confirmed from live data within a horizon that matters. Forum consensus ("after costs there isn't much left") agrees with switching off a class with about zero net edge.
- Carver's 0.13 SR/year cost cap implies that, at 40–68× NAV annual turnover and 1–2 bp per side, costs alone are roughly 0.8–2.7% of NAV a year. The book's expected gross Sharpe must be large relative to that cost. (The conversion to Sharpe units depends on book vol, which is not given here.)
- The HN points on look-ahead and LLM training contamination support the fund's existing pre-registered, live-only reads of LLM desks.

### Gaps
- No forum source found with an explicit "edge must be ≥ k × round-trip cost" multiple for equities. Carver's speed limit (futures-derived) is the closest.
- No practitioner forum discussion found on deflated Sharpe or multiple-testing corrections specifically; the forum treatment is informal.

## Q4. Turnover and trading-cost discipline for weekly or short-horizon books

### Takeaway
The named practitioners converge on **buffering / no-trade regions**: trade only when the current position is outside
a band around the target, and trade only to the band's edge when costs are proportional. They also favour smoothing
positions and filtering executions. Robot Wealth reports that the buffer "nearly always" improves after-cost
performance, with as little as a tenth of the trading. Carver warns that very fast signals rarely survive costs.

### Cited Findings
- Carver on buffering ("position inertia"): "I only trade if my current position is outside of a buffer around the idealised position. So if the idealised position moves a small amount, **we don't bother trading**." **[named practitioner]** — [qoppac, "Fast but not furious", Feb 2023](https://qoppac.blogspot.com/2023/02/fast-but-not-furious-do-fast-trading.html)
- Carver (blog comment): "Mostly (1), but I also buffering on the final position which reduces turnover." In the post: "There are other ways to reduce costs, such as **smoothing your position or using buffering**." **[named practitioner]** — [qoppac, "How fast should we trade?", Apr 2020; comment Oct 2022](https://qoppac.blogspot.com/2020/04/how-fast-should-we-trade.html)
- Carver (podcast, Nov 2025): "with buffering essentially you only trade if your position's further away from the optimal position and with smoothing you basically take something like a moving average of what your position wants to be." On execution: "only execute those that have moved in your favor. So if you're buying only execute if the price has dropped between the last closing price." **[named practitioner; YouTube transcript]** — [Systematic Investor Ep. 375](https://www.youtube.com/watch?v=iTGmh_UripE)
- Carver on very short signals: "if you're trying to pick up really short trends, you've got just a few days, which by the way is probably not a good idea, because **it doesn't tend to make money after costs**." **[named practitioner; futures context]** — [ReSolve podcast "Uncertainty Principles"](https://investresolve.com/podcasts/rob-carver-uncertainty-principles)
- Kris Longmore: the no-trade region "**nearly always improves after-cost performance**… And it does so with **only one-tenth of the trading** of the baseline strategy!" "If your costs are only a function of size, you would **trade to the edge of the barrier** instead" (rather than to target). On sizing the band, he notes others double the theoretical value: "personally, I might add, say 25-50%." **[named practitioner]** — [Robot Wealth, Jun 2025](https://robotwealth.com/reduce-trading-costs-and-boost-profits-with-the-no-trade-region-strategy)
- Longmore on choosing the buffer: "you can set it to target a certain portfolio turnover. Or, you can find the value that optimises the Sharpe ratio of a backtest that includes costs." Goal: "do only the **minimum amount of trading required to harness the edge**." **[named practitioner]** — [Robot Wealth, Feb 2024](https://robotwealth.com/a-simple-effective-way-to-manage-turnover-and-not-get-killed-by-costs)
- HN commenter on rebalancing frequency: "I suspect **costs would eat up many of the benefits of rebalancing** at this timescale." **[anonymous HN]** — [HN "Exploring the limits of LLMs as quant traders"](https://news.ycombinator.com/item?id=45976832)
- Alpha Theory describes funds giving each position "a drift range / band" and trading only when weight crosses the band (Ensemble Capital example: trim after "about 15 - 30% outperformance"). **[vendor / long-only manager]** — [TSOH on Ensemble's process, May 2023](https://thescienceofhitting.com/p/position-sizing)

### Inferences
- For a book with weekly cohorts, the forum consensus points to: (a) don't sell a name that is still in the new cohort's target just to reset its weight; (b) let held names that remain eligible carry over ("hold winners longer" emerges from the band rather than from a discretionary call); (c) set the band by a turnover target fixed in advance, rather than by optimising after-cost Sharpe in-sample. Point (c) is the fund's pre-registration discipline, not a forum view.
- Carver's warning about horizons of "just a few days" is futures-specific, but it matches the fund's own finding that the news class netted about zero.

### Gaps
- No forum thread specifically on weekly single-stock L/S buffers in large caps at 1–2 bp costs. All the named examples are futures, crypto or long-only.

## Q5. News/event trading in large caps when news arrives hours to a day late; LLM sentiment; "priced in"

### Takeaway
Forum opinion is overwhelmingly sceptical that a slow retail or small fund can profit from **public** news in large caps
by trading its direction. "Prices should be quickly reflecting the news." "Entering at score ≥ 7 is probably buying
after the good news is already priced in." "Nearly everything… is being done within latency limits you are priced out
of." The minority view is that edge lies in implementation details or proprietary inputs, not in reading public
headlines. LLM-sentiment threads add specific warnings about look-ahead and training contamination.

### Cited Findings
- r/algotrading (Jul 2026), "My 7 news-sentiment strategies are all losing to a plain XBI benchmark". A reply in the snippet: "Entering at score >= 7 is probably **buying after the good news is already priced in**." The thread title asks whether "LLM news-sentiment [is] salvageable as a signal, or priced-in…". **[anonymous] (snippet)** — [r/algotrading, Jul 2026](https://www.reddit.com/r/algotrading/comments/1ublsph/my_7_newssentiment_strategies_are_all_losing_to_a)
- r/algotrading, "Sentiment based trading on news headlines" (~Feb 2024): "…[won't] help, given **prices should be quickly reflecting the news**." **[anonymous] (snippet; wording cut by the snippet)** — [r/algotrading](https://www.reddit.com/r/algotrading/comments/1aovcid/sentiment_based_trading_on_news_headlines)
- r/algotrading, "LLMs for trading" (~Apr 2025): "I wouldn't use LLM's for trading. They aren't meant for it. There are specific machine learning tools that are designed specially for this." **[anonymous] (snippet)** — [r/algotrading](https://www.reddit.com/r/algotrading/comments/1k1s8q9/llms_for_trading)
- r/algotrading, "Sentiment Driven Strategies" (~Dec 2025): "Most important is using sentiment to look at past trend and build in your **'trade halt'** should the sentiment go off the allowable range." This suggests sentiment as a regime or risk filter rather than a directional signal. **[anonymous] (snippet)** — [r/algotrading](https://www.reddit.com/r/algotrading/comments/1pmuyb4/sentiment_driven_strategies)
- HN (Apr 2018): "Quant trading is harder than people assume - really, really, hard. **Nearly everything you can think of has already been done, and is being done within latency limits you are priced out of as a retail guy.**" A reply disagrees: "not all Quant Trading requires or is being done at low latency." Another: "The edge is found usually in the details of the implementation of a strategy." **[anonymous HN]** — [HN item 16843079](https://news.ycombinator.com/item?id=16843079)
- HN (2025): "At the end of the day it all comes down to input data. There are a lot of things you can do to collect **proprietary data** to give you an edge." A reply says this is "directly counter to what most HFT quants say." **[anonymous HN]** — [HN item 45976832](https://news.ycombinator.com/item?id=45976832)
- HN (Sep 2026), from someone building a trading product: "It's not LLMs trading btw. **LLMs are not reliable for generating trading signals.** We use statistical and ML trading strategies." **[anonymous HN; commercial interest]** — [HN item 49686380](https://news.ycombinator.com/item?id=49686380)
- HN (Sep 2026) on LLM agent frameworks: "markets are zero sum, and if you're using a public model that everyone else also has access to, you… will destroy each other's 'agentic' edge." **[anonymous HN; hostile tone]** — [HN item 49605822](https://news.ycombinator.com/item?id=49605822)
- HN (2022) on retail algo platforms: "Generating alpha is incredibly incredibly hard… The adverse selection here is really really high: if you could generate alpha, you would find some capital from a big multi-manager." **[anonymous HN]** — [HN item 31117255](https://news.ycombinator.com/item?id=31117255)
- r/quant (Paleologo AMA context): Paleologo says on Odd Lots that "somebody else's factor is my alpha and vice versa." Well-known exposures are "priced return" you are paid for bearing risk, not alpha. **[named practitioner; podcast transcript]** — [Odd Lots, Paleologo](https://www.youtube.com/watch?v=ZBIDhQJnVCk)
- Multi-manager L/S framing: the work "is more about **getting quarters right** so the fund can profit right after earnings are announced." Event edge at pods comes from being right *before* the print, not from reacting after. **[named industry-training writer]** — [M&I, Apr 2022](https://mergersandinquisitions.com/long-short-equity)
- Retail framing of earnings reactions: "Now earnings come out and **within seconds** algorithms, social media, and retail traders all react at once." **[anonymous] (snippet)** — [r/ValueInvesting](https://www.reddit.com/r/ValueInvesting/comments/1tqqbl7/when_stocks_start_jumping_3040_in_one_day_history)

### Inferences
- Forum views agree with the academic note in this folder (news_event_strategy_evidence.md) that the first reaction to public large-cap news is gone within seconds to minutes. Any residual edge for a desk receiving news hours to a day late would have to come from **drift or under-reaction on harder-to-parse information**, not from headline direction. No forum source provides evidence that such drift is tradable after 1–2 bp costs.
- The recurring advice for retail LLM-sentiment work (sentiment as a risk filter or "trade halt", proprietary inputs, implementation details) suggests that if any news-derived use survives, it is more likely as a **filter on other ideas or on gross** than as a stand-alone directional class. This is an inference from scattered opinions.
- The "priced in" comment on a ≥7 score threshold describes exactly the risk of an LLM desk that scores already-reported good news highly.

### Gaps
- No credible practitioner (named or verified) in the forums found who reports *profitably* trading public large-cap news with a delay of hours to a day.
- Full Reddit threads could not be read, so any dissenting replies in the XBI or headline threads are unseen.
- No Elite Trader or Wilmott thread found that specifically discusses news latency for daily or weekly holding periods.
