# Academic evidence on how fast news is priced in US large caps, and what it implies for signal-to-trade delay

Scope note: US equities unless flagged. "EW" = equal-weighted, "VW" = value-weighted, "L-S" = long-short, "bps" = basis points. Derived numbers that are my own arithmetic on a source's table are marked "(computed)". Sample periods are given wherever the source states them.

## 1. How quickly are firm-specific news and earnings priced in large caps?

### Takeaway
For large, liquid US stocks the bulk of the price response to firm news happens within seconds to minutes. Earnings news is about 70% priced within 5 minutes of an after-hours release. After the publication day, large caps show little or no further drift: about 11 bps on the first day after news, and post-earnings drift has been statistically absent for all but microcaps since about 2006. Slower drift survives mainly in small and illiquid stocks, after negative news, and (in one 2023–26 study) after hard, quantified fundamental news.

### Cited Findings
**Seconds to minutes (intraday studies)**
- CNBC Morning/Midday Call analyst segments (1990s): prices respond within seconds of the first mention, and positive reports are fully incorporated within one minute. Trading intensity doubles in the first minute. Only traders who execute within 15 seconds earn small but significant profits on positive Midday Call reports. — [Busse & Green 2002, JFE (RePEc abstract)](https://ideas.repec.org/a/eee/jfinec/v65y2002i3p415-437.html)
- Earnings, 50 most liquid S&P 100 stocks, 2008–2020, tick data:
  - After-hours announcements trigger a price jump with probability above 90%.
  - About 70% of the post-announcement price is discovered within 5 minutes, and Hasbrouck information share puts 60–80% in the first 5 minutes.
  - The price-contribution curve is "essentially flat" from the end of the announcement day through next-day pre-market to the 9:30 open.
  - On announcement days, 80.07% of price discovery occurs in the 4:00–6:30pm after-hours segment.
  - [Christensen, Timmermann & Veliyev, arXiv 2601.08962](https://arxiv.org/abs/2601.08962)
- Same paper, trading on the earnings surprise:
  - Mean return per trade is 1.80% at the first post-announcement trade price, 1.50% at midquote and 0.72% paying the actual spread.
  - A 5-second delay cuts it to 0.41%, and longer delays are insignificant.
  - In 2016–2020, returns are insignificant once spreads are paid and slightly negative with latency delays. Before 2016, profits survived a 10-second delay.
  - [Christensen et al., arXiv 2601.08962](https://arxiv.org/abs/2601.08962)
- More than 95% of US firms announce earnings outside regular hours. Grégoire & Martineau report 99.1% for S&P 1500 firms in 2011–2015, cited in [Christensen et al.](https://arxiv.org/abs/2601.08962). After-hours price discovery happens mostly through quote changes rather than trades, so trade-price returns understate the speed of the reaction. — [Grégoire & Martineau 2022, JAR (SSRN)](https://papers.ssrn.com/abstract=3060094)
- News analytics (machine-readable news) speed up the price and volume response to articles. Inaccurate analytics cause small distortions that are corrected quickly, and HFTs use analytics for directional trading on firm news. — [von Beschwitz, Keim & Massa 2020, RAPS](https://ideas.repec.org/a/oup/rasset/v10y2020i1p122-178..html)

**Days (daily-frequency text studies)**
- Dow Jones Newswires, out of sample 2004–2017 ([Ke, Kelly & Xiu, NBER w26186](https://www.nber.org/system/files/working_papers/w26186/w26186.pdf)):
  - Big stocks (above the NYSE median): the price response is 11 bps on the first day after news and is complete after one day; the day-2 effect is insignificant.
  - Small stocks: 52 bps in the first 15 minutes, about 5 times larger, and 3 days to full incorporation.
  - Low-volatility stocks: 12 bps in the first 15 minutes, fully priced after one day.
  - High-volatility stocks: 59 bps, fully priced after 3 days.
- Same paper, by news type:
  - Fresh news: a 39 bps one-day response measured from 15 minutes after arrival to the next open, and 4 days to full incorporation.
  - Stale news (similar to the prior week's articles): 23 bps and 2 days.
  - The long-short portfolio is "essentially fully incorporated into prices by the start of Day +3". The long leg takes 2 days and the short leg 3.
- GPT-4 scores on RavenPack headlines (Oct 2021–May 2024):
  - News is absorbed in about two days. The long-short return is 34 bps on day 0 (open to close) and 19 bps on day +1 for overnight news, with nothing afterwards.
  - Large caps (top size tercile) show no drift after negative news, while small caps keep drifting. The authors read this as "large-cap markets adjust efficiently".
  - [Lopez-Lira & Tang, arXiv 2304.07619 v6 (Oct 2025), forthcoming/published JFE](https://arxiv.org/abs/2304.07619)
- Thomson Reuters neural-net sentiment, 2003–2010, 900k stories ([Heston & Sinha, FEDS 2016-048 / FAJ 2017](https://www.federalreserve.gov/econresdata/feds/2016/files/2016048pap.pdf)):
  - Daily long-short quintile excess returns: day 0 = 1.99%, day +1 = 0.17%, day +2 = 0.04%, day +3 = 0.02%, day +4 = 0.04%, then roughly zero.
  - Day −1 is already 0.50%, so prices move ahead of the story.
  - "Daily news predicts stock returns for only 1 to 2 days."
- Newswire articles largely restate known information. The "Day −1" infeasible strategy (sentiment against the return before publication) has a Sharpe ratio of 5.88, against 10.78 for day 0 and 4.29 for the implementable day +1. — [Ke, Kelly & Xiu](https://www.nber.org/system/files/working_papers/w26186/w26186.pdf)
- 4.57M articles on about 3,000 US stocks, 2023–2026, LLM-tagged ([Kargarzadeh et al., arXiv 2608.14014, AI4F '26 workshop paper](https://arxiv.org/abs/2608.14014)):
  - Pooled over signed events, the running abnormal return in the news direction is +0.579% by the close of the publication day and +0.204% at day +20 (ratio 2.84).
  - The ratio is 1.06 for earnings, 1.08 for guidance and 1.20 for analyst actions, so the move "was finished, or more than finished, when publication day ended".
  - Non-peer-reviewed, industry authors, single-beta benchmark, daily closes only.

**Is post-earnings-announcement drift (PEAD) dead?**
- 1984–2019 ([Martineau, "Rest in Peace PEAD", Critical Finance Review](https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf)):
  - For stocks above the NYSE 20th percentile, analyst-surprise rank does not predict BHAR[2,60] after 2005. Coefficients are −0.001 (2006–10), 0.000 (2011–15) and −0.002 (2016–19), against 0.003 in 1984–90.
  - For microcaps, drift disappears only in 2016–19.
  - Announcement-window response (BHAR[0,1]) per surprise decile rose from 0.002 to 0.012, with R² up from 1.7% to 11.7%.
  - The slope of BHAR[0,60] on BHAR[0,1] for all-but-microcaps fell from about 1.6 to "almost one", so announcement-day prices are about a martingale.
  - Since 2011 the only suggestive drift is in microcaps at days 2–5.
- Counter-claims: Dickerson, Julliard & Mueller (JFE, in press) and Hirshleifer, Peng & Wang (RFS 2025) report PEAD alive, but their samples include microcaps. Subrahmanyam's 2025 replication gives t = 2.18 with all stocks and t = 1.43 excluding microcaps. — [UCLA Anderson Review summary](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/)
- Analyst recommendation changes: post-revision drift is not significantly different from zero in 2003–2010, the algorithmic-trading era. — [Altinkilic, Hansen & Ye 2016, JFE](https://ideas.repec.org:443/a/eee/jfinec/v119y2016i2p371-398.html)
- Partial counterpoint, 2023–2026, mixed sizes: placebo-adjusted drift over days +6..+20 is still positive for quantified fundamental news. It is +0.22% for earnings, +0.13% for guidance, +0.10% for analyst actions and +0.35% for capital returns, all significant, but "thin relative to plausible costs". — [Kargarzadeh et al., arXiv 2608.14014](https://arxiv.org/abs/2608.14014)
- Text-based drift around later earnings: news that is not priced on publication shows up mostly around the next earnings announcement. The earnings-week long-short cumulates 5.57% (t = 2.66) over 13 weeks, against 0.25% (n.s.) pre-earnings. — [Heston & Sinha](https://www.federalreserve.gov/econresdata/feds/2016/files/2016048pap.pdf)

### Inferences
- Approximate shares of the move, for large-cap firm news in post-2005 data:
  - **Within minutes:** the majority, about 60–80% for earnings and essentially all for broadcast analyst opinions.
  - **By the close of the event day:** more than 90%. The Heston–Sinha day-0 move is 1.99% against about 0.31% over days 1–5 combined, so about 87% for all stocks; large caps are faster (computed).
  - **Day +1:** a small residual, about 11 bps for above-median stocks in Ke, Kelly & Xiu.
  - **By day +5:** essentially complete, except for negative and quantified fundamental news.
- No source gives these shares specifically for S&P 500 names, LLM signals and post-2020 together. The figures above combine studies.
- Overnight news is half or more of news flow: 82% of Lopez-Lira & Tang's headlines are outside 9am–4pm, and Ke, Kelly & Xiu report article counts peaking just before the open and the close. For large caps it is largely priced by the next open, because after-hours and pre-market quotes absorb it. A same-day close entry is therefore never "early" for overnight news. It is late by one full session.

### Gaps
- The full text of Jiang, Li & Wang (JFE 2021) was not accessible, so their large-cap and post-2010 breakdowns are unverified. Section 3 uses working-paper numbers.
- I did not obtain the size-tercile drift magnitudes in Lopez-Lira & Tang's Online Appendix F.6, nor Busse & Green's speed for negative reports.
- No study found measures fraction-of-move at minute, close, day +1 and day +5 for S&P 500 constituents in 2020–2026 with LLM-scored news.

## 2. Text and LLM news signals: execution assumptions, decay with a one-day delay, size concentration and costs

### Takeaway
Almost every headline result trades within hours of the news: at the next open for overnight news, or at the same 4pm close using news timestamped up to 4pm, which assumes zero latency. Daily-rebalanced long-short performance falls steeply from equal- to value-weighting (Sharpe ratios roughly 3–4 fall to 0.5–1.3) and with a one-day delay. Out-of-sample S&P 500 results are weak, and LLM headline-strategy Sharpe ratios fell sharply over 2021–2024. Weekly-aggregated news is the exception: it predicts returns for up to 13 weeks.

### Cited Findings
**Paper-by-paper execution conventions**

| Study (data, sample) | News cutoff → trade | Key performance | Size / large-cap evidence | Costs | Source |
|---|---|---|---|---|---|
| Tetlock, Saar-Tsechansky & Macskassy 2008 (WSJ + DJNS, S&P 500 firms, 1980–2004) | Prior trading day's stories, held 1 day | DJNS quartile L-S abnormal return about 10.1 bps/day (WSJ much weaker); prices "briefly underreact" to negative words | Universe is S&P 500 | Not verified | [Columbia abstract](https://business.columbia.edu/faculty/research/more-words-quantifying-language-measure-firms-fundamentals); 10.1 bp figure via [Wang et al. "Wisdom of Crowds"](https://www.bhwang.com/pdf/wisdom-of-crowds.pdf) (secondary) |
| Heston & Sinha 2016/17 (TR NewsScope, 2003–2010) | Daily quintiles formed on day 0; weekly deciles on week 0 | Daily: day +1 = 0.17%, day +2 = 0.04%. Weekly: week 0 = 3.75%, week 1 = 0.32%, week 2 = 0.20%, week 3 = 0.26%, week 13 = 0.21% (significant) | Results survive size and momentum adjustment; firms with multiple stories per week tend to be larger | None | [FEDS PDF](https://www.federalreserve.gov/econresdata/feds/2016/files/2016048pap.pdf) |
| Ke, Kelly & Xiu 2019 (DJ Newswires; out of sample Feb 2004–Jul 2017) | Trade at the open only; news from 9:00–9:30am excluded to force at least 30 minutes of delay; open-to-open holding | Top/bottom 50 L-S: EW Sharpe 4.29, 33 bps/day; VW Sharpe 1.33, 10 bps/day; daily turnover about 94% | Big stocks: 11 bps, done in 1 day | None in base case | [NBER w26186](https://www.nber.org/system/files/working_papers/w26186/w26186.pdf) |
| Lopez-Lira & Tang (GPT-4, RavenPack headlines, Oct 2021–May 2024) | News before 9am → enter at the open, exit at the close. After 4pm → next open to next close. Intraday news → enter 15 minutes later, or at the close and exit at the next close | Overnight news: L-S 34 bps/day, Sharpe 2.97 (EW), about 700% cumulative before costs. Intraday news, close to close: 0.50%/day, Sharpe 2.63 (EW) | VW Sharpe: overnight 0.56, intraday 1.28. "Heavily concentrated in smaller stocks." No drift in the top tercile after negative news | Round trip 5 bps: above 300% cumulative; 10 bps: above 100%; 20 bps: unprofitable. Turnover about 190%/day. Intraday close-to-close VW Sharpe 0.09 at 10 bps and −1.11 at 20 bps | [arXiv 2304.07619](https://arxiv.org/abs/2304.07619) |
| Glasserman & Lin 2023 (GPT-3.5; scraped headlines with median cap $2.6bn, and Thomson Reuters S&P 500 headlines with median cap $56.7bn) | 4pm–6am news → next open to next close. 6am–4pm news → buy at the 4pm close, sell at the next close | Out of sample (Oct 2021–Dec 2022) L-S alpha: scraped 18.8 bps/day (t = 2.84); **S&P 500 headlines 3.8 bps/day (t = 0.92, not significant)** | GPT is more "distracted" (worse) on large firms; anonymizing helps most for S&P 500 names | Ignored | [arXiv 2309.17322](https://arxiv.org/abs/2309.17322) |
| Chen, Kelly & Xiu, "Expected Returns and LLMs" (16 markets, 13 languages; US subset) | Per the discussant: news from 9am t−1 to 9am t predicts the 9am-to-9am return | Net Sharpe about 1.5 assuming daily costs of 10 bps (large) and 20 bps (small). The discussant warns large-cap predictability may be front-loaded in the first minutes after 9am | Significantly lower L-S for large stocks (discussant slide) | 10/20 bps | [SSRN 4416687](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416687); [Li discussion](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2024/09/ExpectedReturnAndLLM_Discussion_SophiaZhengziLi_NoPause.pdf) |
| He, Lv, Manela & Wu 2025, ChronoBERT/ChronoGPT (DJ Newswires, 2008–Jul 2023) | Headlines from 4pm t−1 to 4pm t → close-to-close return on t+1 (implicitly a 4pm close entry) | EW decile H-L Sharpe 4.80 (ChronoBERT), 4.92 (ChronoGPT), 4.90 (Llama 3.1); about 61–66%/yr. Lookahead bias is "modest" | EW only. "Steep decline in return predictability over the first two days", converging by days 3–6 | None | [arXiv 2502.21206](https://arxiv.org/abs/2502.21206) |
| Kirtac & Germano 2024 (OPT, BERT, FinBERT; 965k US articles, 2010–2023) | Not verified | L-S Sharpe 3.05 after 10 bps; +355% Aug 2021–Jul 2023 | Not verified | 10 bps | [Finance Research Letters](https://www.sciencedirect.com/science/article/pii/S1544612324002575) |
| Kirtac 2026, MFAST (Refinitiv, 2010–Jan 2026; out of sample Jun 2024–Jan 2026) | News before 9:30 → that day's open. News at or after 9:30, after close or on weekends → next trading day. Also a one-full-day-delay robustness test | VW L-S net Sharpe 2.85 (LLaMA-3), 0.34%/day, 5 bps costs, 10% volume-participation cap | Coefficients rise from high- to low-liquidity stocks | 5 bps | [arXiv 2609.23703](https://arxiv.org/abs/2609.23703) (R&R at an engineering journal, single author. The VW Sharpe is unusually high against the rest of this literature; treat with caution) |
| Didisheim, Kelly, Pourmohammadi & Tian 2026, "Inefficient pricing of news" (6M+ articles on US firms) | Not stated in the column | Out-of-sample L-S on the "pure news" residual: Sharpe about 3.1. About 60% of the inefficiency is underreaction, 40% overreaction | n/a | n/a | [CEPR/VoxEU column](https://cepr.org/voxeu/columns/inefficient-pricing-news) |

**Decay with a one-day delay**
- Ke, Kelly & Xiu, EW long-short with infeasible same-day timing versus implementable next-day timing ([NBER w26186](https://www.nber.org/system/files/working_papers/w26186/w26186.pdf)):
  - Day 0 is 93 bps/day (Sharpe 10.78), against 33 bps/day for day +1 (Sharpe 4.29).
  - The day +1 return is 26% of day 0 + day +1 (computed).
- Lopez-Lira & Tang, overnight news ([arXiv 2304.07619](https://arxiv.org/abs/2304.07619)):
  - Initial reaction 3.06% (prior close to open), drift 0.34% (open to close day 0), then 0.19% on day +1.
  - Delaying entry from the open to the close of day 0 gives up 34 of about 53 bps of tradable drift, about 64% (computed).
  - The tradable drift after the open is about 15% of the total move (computed).
- Lopez-Lira & Tang, intraday news, regression of returns on the GPT-4 score in three windows ([arXiv 2304.07619](https://arxiv.org/abs/2304.07619)):
  - 1–15 min: 0.027 (n.s.); 15 min to close: 0.189 (t = 5.1); next-day close to close: 0.116 (t = 2.3).
  - The event-time figure shows 32 bps for the rest of the news day and 30 bps the day after, then nothing.
- Heston & Sinha ([FEDS PDF](https://www.federalreserve.gov/econresdata/feds/2016/files/2016048pap.pdf)):
  - Daily-formed signal: day +1 is 0.17% of about 0.30% cumulated over days 1–5, so skipping one day loses about 57% of post-publication drift (computed).
  - Weekly signal: week 1 (0.32%) is about 15% of the about 2.15% summed over weeks 1–13 (computed; Figure 2's plotted cumulative appears lower, about 1.4–1.6%, so treat the 2.15% as an upper bound).
- Decay over calendar time, Lopez-Lira & Tang ([arXiv 2304.07619](https://arxiv.org/abs/2304.07619)):
  - The annualized Sharpe ratio of the overnight-news strategy fell from 6.54 (2021Q4) to 3.68 (2022), 2.33 (2023) and 1.22 (Jan–May 2024).
  - The intraday close-to-close strategy becomes insignificant in Jan–May 2024.
  - The authors link the decline to LLM adoption.
- Lookahead bias: Glasserman & Lin find in-sample "distraction" from company knowledge outweighs lookahead bias, especially for larger companies ([arXiv 2309.17322](https://arxiv.org/abs/2309.17322)). He et al. find chronologically consistent models match Llama 3.1, so lookahead bias is modest for embedding-based news prediction ([arXiv 2502.21206](https://arxiv.org/abs/2502.21206)).
- Positive news is priced within about one week, while negative news predicts low returns for up to 13 weekly lags (significant at lags 1–6 and 10). The authors attribute this to short-sale constraints. — [Heston & Sinha](https://www.federalreserve.gov/econresdata/feds/2016/files/2016048pap.pdf)

### Inferences
- Every high-Sharpe result above uses (a) daily rebalancing with near-100% daily turnover, (b) entry within minutes to hours of the news, and (c) equal weighting that loads on small caps. A 10-name-per-side S&P 500 book differs on all three. The closest analogues are the VW and S&P 500 cuts:
  - Ke, Kelly & Xiu VW: 10 bps/day.
  - Lopez-Lira & Tang VW Sharpe: 0.56 for overnight news, 1.28 for intraday news, and about 0.1 at 10 bps for intraday news.
  - Glasserman & Lin S&P 500 alpha: 3.8 bps/day, not significant.
  - These suggest little daily-frequency edge in large caps after the day of the news.
- Academic "close entry" designs, such as He et al. and Glasserman & Lin, count news up to 4:00pm as tradable at the 4:00pm close, so they assume zero latency. Ke, Kelly & Xiu, by contrast, impose a deliberate gap of at least 30 minutes. A 20-minute pre-close news cutoff with a trade 60 seconds before the close is more conservative than the zero-latency designs and close to Ke, Kelly & Xiu's buffer.
- With the decay rates above, a one-day delay costs a daily-horizon text signal roughly 25–65% of its implementable drift (computed range across the three studies). For a weekly-aggregated signal it costs at most a fraction of week 1, i.e. under about 15% of 13-week drift, assuming week-1 drift is spread across days. Daily-signal front-loading suggests it is not evenly spread, so the true figure is plausibly 5–15% (inference, not measured).

### Gaps
- I could not access the full text of Chen, Kelly & Xiu, so their US-only day-by-day decay, large- versus small-cap split and exact timing are known only from discussant slides.
- The execution timing of Kirtac & Germano 2024 is unverified. Kirtac 2026's one-day-delay robustness numbers were not in the retrieved pages.
- No LLM paper found reports results specifically for "decide at close−3min, trade at close−60s, S&P 500 only, multi-day holding".
- Tetlock et al. 2008's own cost and timing details were not verified from the primary text; only a secondary citation of 10.1 bps/day was found.

## 3. Overnight versus intraday: news after the close or before the open, open gap versus next session

### Takeaway
News released outside trading hours is mostly priced in the opening gap: about 85% of the total move in the LLM headline data, and nearly all earnings news for liquid stocks before the next open. Any remaining news-driven continuation accrues disproportionately overnight, close to open. For momentum, earnings momentum and news momentum it is often concentrated there, with intraday sessions flat or reversing. Inattention (Friday, busy announcement days) shifts the response from immediate to delayed.

### Cited Findings
- Lopez-Lira & Tang, overnight news (82% of headlines, defined as released before 9am or after 4pm) ([arXiv 2304.07619](https://arxiv.org/abs/2304.07619)):
  - The initial reaction from the prior close to the open is 3.06% L-S (hit rate 93%). The drift from open to close is 0.34% (hit rate 58%).
  - The open gap therefore carries about 90% of the same-day move, or about 85% including day +1 (computed).
  - Intraday news: the reaction from the prior close to 15 minutes after release is 4.44%, against 0.50% close to close the next day.
- News-driven price jumps ("news momentum"), RavenPack plus TAQ, working-paper version of Jiang, Li & Wang ([SSRN 2667658 WP via Villanova](https://www.villanova.edu/dam/villanova/VSB/assets/marc/marc2018/SSRN-id2667658.pdf)):
  - After overnight news, the strategy's cumulative drift is 25 bps at 3:30pm on day t, dips to 17 bps at the 4:00pm close, jumps to 59 bps at the open of day t+1, and reaches 104 bps by the close of t+4.
  - So about 40% of the 5-day drift (42 of 104 bps) occurs in the first overnight gap after the news day (computed).
  - The VW strategy earns 11.7 bps/day gross against 8.3 bps/day of costs, about 8.6%/yr net.
  - The published version reports "prices tend to drift in the same direction as the initial market response for several days after the news arrival without reversals", stronger when investors are distracted ([Jiang, Li & Wang 2021, JFE (RePEc)](https://ideas.repec.org/a/eee/jfinec/v141y2021i2p573-599.html)).
  - A 2000–2019 replication cited by a discussant: EW 34%/yr, VW 25%/yr ([Li discussion slides](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2024/09/ExpectedReturnAndLLM_Discussion_SophiaZhengziLi_NoPause.pdf)).
- Overnight/intraday split, 1993–2013, VW deciles excluding stocks under $5 and the bottom NYSE size quintile; "open" = VWAP from 9:30–10:00 ([Lou, Polk & Skouras 2019, JFE](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf)):
  - Momentum (CAPM alpha per month): overnight 0.98% (t = 3.84), intraday −0.02%.
  - Earnings-surprise momentum (SUE): overnight 0.56% (t = 3.20), intraday 0.21% (n.s.).
  - Industry momentum: overnight 1.07%, intraday −0.63%.
  - Short-term (one-month) reversal: overnight 0.93%, intraday −1.05%.
  - Value, profitability, investment and low-volatility premia: all intraday, with opposite-signed overnight returns.
  - "Essentially all of the abnormal returns on momentum and short-term reversal strategies occur overnight", and this "is not driven by news".
  - For the largest stocks (top 1% of the NYSE), "essentially all" of the risk premium is earned overnight.
  - The overnight-minus-intraday momentum spread is stronger for large stocks.
- For S&P 500 stocks since 2000, overnight returns exceed intraday returns by 2.75 bps/day (about 7.2%/yr). News-topic exposures explain a large part of the gap and of over-to-intraday reversal patterns. — [Glasserman, Krstovski, Laliberte & Mamaysky, arXiv 2507.04481](https://arxiv.org/abs/2507.04481)
- Buying at the open, 1996–2008, 3,000 largest US stocks ([CXO summary](https://www.cxoadvisory.com/calendar-effects/the-lure-of-trading-at-the-open/); [Berkman, Koch, Tuttle & Zhang 2012, JFQA](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/paying-attention-overnight-returns-and-the-hidden-cost-of-buying-at-the-open/F9AAD159B512C651F09D5D52011D88E0)):
  - On average, +0.10% overnight and −0.07% intraday reversal.
  - High retail attention with low institutional ownership: +0.2 to +0.3% overnight, then −0.2 to −0.4% intraday.
  - Hard to value or arbitrage: +0.4 to +0.6% overnight, then −0.4 to −0.7%.
  - The implicit cost of buying high-attention stocks near the open frequently exceeds the effective half-spread.
  - The effect weakens after decimalization (2001) and the spread of algorithmic trading (2005).
- Friday earnings announcements have a 15% lower immediate response and a 70% higher delayed response than other weekdays. — [DellaVigna & Pollet 2009, JF (NBER WP)](https://www.nber.org/papers/w11683)
- When more firms announce earnings on the same day, the immediate reaction is weaker and drift stronger. A PEAD strategy is unprofitable for announcements on days with little competing news. — [Hirshleifer, Lim & Teoh 2009, JF (MPRA)](https://mpra.ub.uni-muenchen.de/3110/)
- Contrary evidence for the most liquid stocks: during earnings season, information spillover dominates the distraction effect. — [Christensen et al.](https://arxiv.org/abs/2601.08962)
- In the 2023–26 LLM-tagged sample, articles published during market hours fall on days that move 1.18× the stock's normal absolute move, against 1.05× for overnight publications. — [Kargarzadeh et al.](https://arxiv.org/abs/2608.14014)

### Inferences
- For after-close and pre-open news on S&P 500 names, the next open is already late for the main move. Of the remaining drift, a material share is realised in the overnight gap(s) after the news day, as in the news-momentum path (17→59 bps) and Lou, Polk & Skouras.
- This means the cost of a roughly 24-hour delay comes mainly from missing the first overnight gap (e.g. Wednesday close to Thursday open). Thursday's intraday session has historically added little and, for momentum-like and attention-grabbing longs, has tended to reverse.
- Hypotheses for the shadow books, from Lou, Polk & Skouras and Berkman et al. These are not direct tests of a news book:
  - Wednesday close (notional) minus Thursday open captures the Wednesday-night gap, which should be positive for continuation signals.
  - Thursday open minus Thursday close captures Thursday's intraday return, which is often flat or negative for momentum-type longs. It may be positive for news-momentum signals, given the drift up to 3:30pm in the working paper.
  - So a Thursday-open entry is not necessarily better than a Thursday-close entry. The size and sign of Thursday-open minus Thursday-close is an empirical question the shadow books can answer.
- DellaVigna & Pollet and Hirshleifer, Lim & Teoh both say that low-attention timing (Fridays, busy days) leaves more for later. A weekly Thursday-close cohort that picks up Friday-evening or heavy-earnings-day news a week late is in the regime where delayed response is largest. That evidence is pre-2006 and partly small-cap driven.

### Gaps
- No study found decomposes the overnight versus next-session split for LLM-scored news restricted to S&P 500 stocks after 2020.
- The Jiang, Li & Wang intraday path numbers come from the working paper, not the JFE version, and are not split by size.
- Lou, Polk & Skouras end in 2013. More recent overnight/intraday splits for news momentum (Barardehi, Bogousslavsky & Muravyev, cited in [Glasserman et al.](https://arxiv.org/abs/2507.04481)) were not read.

## 4. Delay-cost evidence: alpha decay, implementation delay, trading costs

### Takeaway
How much a delay costs depends on the signal's decay rate. For news and earnings signals at the seconds-to-days scale, delays of seconds (earnings) or one day (daily text signals) remove a large share of the edge. For slow signals (institutional fundamental views, weekly-aggregated news, most anomalies) a one-day delay is minor, and trading costs dominate. In the modern era, net post-publication anomaly returns average about 4 bps/month.

### Cited Findings
- **Seconds.** On earnings, the edge disappears with delays beyond 5 seconds. In 2016–2020 there is no significant profit after spreads at all. — [Christensen et al.](https://arxiv.org/abs/2601.08962)
- **Seconds.** On CNBC reports, profits accrue only to trades within 15 seconds. — [Busse & Green](https://ideas.repec.org/a/eee/jfinec/v65y2002i3p415-437.html)
- **One day (daily text signals):**
  - Ke, Kelly & Xiu: implementable day +1 is 33 bps/day against an infeasible day 0 of 93 bps (EW). The long-short is fully incorporated by the start of day +3; for big stocks, after day +1. ([NBER w26186](https://www.nber.org/system/files/working_papers/w26186/w26186.pdf))
  - Lopez-Lira & Tang: 34 bps on day 0 after the open, 19 bps on day +1, then zero. ([arXiv 2304.07619](https://arxiv.org/abs/2304.07619))
  - He et al.: steep decline over the first two days, converged by days 3–6. ([arXiv 2502.21206](https://arxiv.org/abs/2502.21206))
- **Weeks.** Weekly-aggregated sentiment predicts weekly returns for 13 weeks: 0.32%, 0.20%, 0.26% in weeks 1–3 and 0.21% in week 13. — [Heston & Sinha](https://www.federalreserve.gov/econresdata/feds/2016/files/2016048pap.pdf)
- **Months.** Stocks bought by institutional managers earn alpha that "declines gradually over twelve months". Managers keep buying in small increments while alpha persists, with trade size proportional to remaining mispricing. Competition lowers alpha only in the first 3–6 months. — [Di Mascio, Lines & Naik, "Alpha decay" (LBS)](https://www.london.edu/faculty-and-research/academic-research/a/alpha-decay-and-strategic-trading); [PDF](https://jhfinance.web.unc.edu/wp-content/uploads/sites/12369/2016/02/Alpha-Decay.pdf)
- **Costs versus gross alpha:**
  - Chen & Velikov: net of effective spreads, post-publication effects and the post-2000s trading-technology era, the average anomaly's expected return is 4 bps/month. The strongest anomalies net at most about 10 bps, and combinations about 20 bps. ([FEDS/JFQA](https://www.federalreserve.gov/econres/feds/zeroing-in-on-the-expected-returns-of-anomalies.htm))
  - Frazzini, Israel & Moskowitz: actual institutional trading costs, from $1.7 trillion of AQR live executions over 1998–2016 in 21 markets, are "an order of magnitude smaller" than earlier academic estimates. ([SSRN 3229719](https://papers.ssrn.com/abstract=3229719))
  - News strategies with costs: Lopez-Lira & Tang break even at about 20 bps round trip with about 190%/day turnover. Partial rebalancing (25%) cuts turnover to about 46%/day and keeps Sharpe 1.34 at 10 bps against 1.29 for full rebalancing. ([arXiv 2304.07619](https://arxiv.org/abs/2304.07619)) News momentum VW: 11.7 bps/day gross against 8.3 bps/day costs. ([Jiang, Li & Wang WP](https://www.villanova.edu/dam/villanova/VSB/assets/marc/marc2018/SSRN-id2667658.pdf)) Chen, Kelly & Xiu: net Sharpe about 1.5 at 10/20 bps. ([Li discussion](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2024/09/ExpectedReturnAndLLM_Discussion_SophiaZhengziLi_NoPause.pdf))
- **2023–26 calendar-time test** (enter at the close of day +5, exit at the close of day +20, beta-hedged, equal-weighted) ([Kargarzadeh et al.](https://arxiv.org/abs/2608.14014)):
  - Following legal and regulatory news direction earns Sharpe 0.66 gross, 0.12 at 10 bps per side and −0.43 at 20 bps.
  - Fading small-cap launch and partnership news earns Sharpe 1.35, but this is identical to shorting any covered small cap. "The news direction adds nothing."
  - The residual alphas, such as +0.22% per earnings event over 15 days, are "real but thin relative to plausible costs".

### Inferences
- Approximate half-lives (computed, rough):
  - Earnings and broadcast analyst news, liquid large caps: seconds to minutes.
  - Daily text-sentiment drift after the news day: about 0.5 day (Heston–Sinha, day +2/day +1 = 0.24) to about 1.2 days (Lopez-Lira & Tang, day +1/day 0 drift = 0.56); about 1 day for big stocks (Ke, Kelly & Xiu).
  - Weekly-aggregated news: half of the 13-week cumulative drift is reached around weeks 5–6.
  - Institutional fundamental views: months.
- A one-day delay is therefore expensive for daily-horizon news alpha and cheap for weekly or multi-week alpha. For a large-cap book holding 3–20+ days, what decides whether the delay matters is whether the event type has multi-week drift in large caps at all. Section 5 suggests it does only for quantified fundamental news, and weakly.
- Costs for a 10-name-per-side S&P 500 book that trades at the closing auction and holds 5–15 days are far lower per unit of time than the daily-turnover academic strategies, so the 5–20 bps round-trip break-evens above are not directly comparable. The relevant comparison is the expected drift per event (e.g. +0.10% to +0.22% over days +6..+20 for analyst and earnings news in 2023–26) against one round trip of cost.

### Gaps
- Novy-Marx & Velikov (2016), Korajczyk & Sadka (2004) and Frazzini, Israel & Moskowitz's numeric cost and capacity results were not retrieved. Only the qualitative FIM claim is cited.
- I found no academic paper that directly estimates "cost of a one-day implementation delay" across many signals with a shared methodology. The figures above are assembled from event-time decay curves.

## 5. Short-term reversal around news versus no-news days: does a close entry after a news day buy an overshoot?

### Takeaway
Extreme moves on days without identifiable news tend to reverse. Moves on days with identified, especially fundamental or quantified, news tend to continue. For soft or attention-driven news (product launches, partnerships, leadership, macro read-throughs, promotional wire releases, M&A rumours), recent 2023–26 evidence shows a give-back over the following one to four weeks. Buying at the close of such a news day buys an overshoot. Buying at the close of an earnings, guidance or analyst-action day generally does not.

### Cited Findings
- Monthly returns: strong drift after bad-news headlines, less after good news, and reversal after extreme moves without public news. These effects are mainly in smaller, illiquid stocks. — [Chan 2003, JFE (abstract)](https://academicnewsletter.sufe.edu.cn/info/357702)
- S&P 500, 2000–2009, Dow Jones newswire with 14 event categories: conditional on extreme moves, reversals occur on no-news days and identified-news days show "a strong degree of continuation". Volatility on identified-news days is more than twice that of other days. — [Boudoukh, Feldman, Kogan & Richardson, NBER w18725](https://www.nber.org/papers/w18725); [NBER Digest](https://www.nber.org/digest/jun13/which-news-moves-stock-prices)
- Returns unexplained by cash-flow news, measured from analyst forecast revisions, are more likely to reverse. An "enhanced" reversal strategy that strips out cash-flow news earns four times the risk-adjusted return of standard reversal. — [Da, Liu & Schaumburg 2014, Management Science](https://pubsonline.informs.org/doi/fpi/10.1287/mnsc.2013.1766); [NY Fed SR513](https://newyorkfed.org/medialibrary/media/research/staff_reports/sr513.html)
- News-driven jumps drift "without reversals". — [Jiang, Li & Wang 2021](https://ideas.repec.org/a/eee/jfinec/v141y2021i2p573-599.html)
- Stale news is fully priced within 2 days, while fresh news takes 4 days. — [Ke, Kelly & Xiu](https://www.nber.org/system/files/working_papers/w26186/w26186.pdf)
- Tetlock (2011) finds overreaction to stale news (cited in [Heston & Sinha](https://www.federalreserve.gov/econresdata/feds/2016/files/2016048pap.pdf); primary not read).
- Markets underreact to topics with negative tone and dense numbers: negative guidance, clinical-trial readouts, recalls, aircraft orders. They overreact to ambiguous or very high-attention topics: bailouts, intraday price-swing coverage, corporate COVID responses. — [Didisheim et al. 2026, CEPR column](https://cepr.org/voxeu/columns/inefficient-pricing-news)
- 2023–2026, about 3,000 US stocks, placebo-adjusted drift over days +6..+20 in the news direction ([Kargarzadeh et al., arXiv 2608.14014](https://arxiv.org/abs/2608.14014)):
  - **Continuation:** capital returns +0.35%, earnings +0.22%, guidance +0.13%, analyst actions +0.10%.
  - **Reversal:** macro read-throughs −0.34%, product launches −0.18%, leadership −0.18%, competition −0.17%.
  - **Not significant:** legal and regulatory −0.08% (p = 0.22), M&A deals −0.05%, partnerships −0.08%.
  - Raw (unadjusted) days +1..+5: launches −0.22%, macro −0.22%, M&A deals −0.23%.
  - Press-wire releases reverse −0.19% adjusted. Quantified articles show no drift; unquantified ones reverse −0.12%.
  - Without a placebo, a background drift (neutral-coverage large caps −0.34% over the following month) masquerades as "good news reverses, bad news continues".
- M&A rumours, same source ([arXiv 2608.14014](https://arxiv.org/abs/2608.14014)):
  - Rumour day +0.24%, then −0.32% into confirmation, −0.10% on the confirming news and −0.37% after it.
  - Across all rumour-flagged events, the rumour day gives +0.36%, with nothing added between rumour and confirmation and +0.01% on confirmation day.
- High-attention stocks rise overnight and reverse intraday. — [Berkman et al. 2012 via CXO](https://www.cxoadvisory.com/calendar-effects/the-lure-of-trading-at-the-open/)

### Inferences
- The evidence supports conditioning the holding period on event type more than on news sentiment strength:
  - Quantified fundamental events (earnings, guidance, analyst) are the only categories with continuation in recent data, small in large caps.
  - Soft and promotional categories (product, partnership, leadership, macro, M&A rumour) on average reverse over days 1–20. A long in the news direction entered at that day's close is, on average, buying an overshoot. This is consistent with a short holding period for such events, or with no position.
- Legal and regulatory news shows no significant adjusted drift in 2023–26, so a 7-day hold has no clear support in that sample. The raw drift (+0.29%) looks like continuation only because of the background drift.
- Caveat: the per-tag evidence comes mostly from a single 2023–26 workshop paper with a single-beta benchmark and mixed-size universe. Its large-cap-only per-tag drift is not reported in the retrieved pages.

### Gaps
- The large-cap-only (S&P 500) version of the per-tag drift table was not available.
- Ahern & Sosyura on M&A rumours and Fedyk & Hodson on old news were not read.
- I found no paper that directly tests "entry at the close of the news day" against "entry one day later" by event type.

## 6. Closing-price entry after daytime news versus next-day entry

### Takeaway
For news released during the session, entering at the same close still captures a measurable residual. In Lopez-Lira & Tang, the next-day close-to-close return after intraday news is about 40% of the post-15-minute drift, and in news-momentum data about 85% of the 5-day drift arrives after the news-day close. The residual is concentrated in small caps and has decayed sharply since 2022. Next-day entry (next open or next close) loses the first overnight gap, the largest single piece of what remains.

### Cited Findings
- Intraday news (Lopez-Lira & Tang, [arXiv 2304.07619](https://arxiv.org/abs/2304.07619)):
  - Score coefficients: 0.189 (t = 5.1) from 15 minutes after release to the close, and 0.116 (t = 2.3) from the close to the next close.
  - Same-day close entry therefore captures about 38% of the post-15-minute drift (computed). The event-time plot shows about 32 bps for the rest of the day and about 30 bps the next day, then zero.
  - Close-to-close EW Sharpe is 2.63 (0.50%/day) and VW 1.28 (0.18%/day). At 10 bps, VW falls to 0.09.
  - Close-to-close Sharpe is "significantly positive in 2022 and 2023, but becomes insignificant in January–May 2024".
  - The same-day 15-minute-to-close drift "is impractical to implement" because position sizing cannot anticipate how many intraday news events will arrive.
- Overnight news then a close entry (Jiang, Li & Wang WP, [Villanova PDF](https://www.villanova.edu/dam/villanova/VSB/assets/marc/marc2018/SSRN-id2667658.pdf)):
  - Drift is 17 bps at the day-t close, then 59 bps at the t+1 open and 104 bps at the t+4 close.
  - A close-of-day-t entry still captures about 84% of the 5-day drift (computed). This is a decile sort on price-measured news returns in an all-size universe.
- Designs that count news to 4pm and trade the 4pm close (He et al.; Glasserman & Lin) report the highest Sharpe ratios but assume zero processing latency. Glasserman & Lin's S&P 500 headline version had insignificant out-of-sample alpha (3.8 bps/day, t = 0.92). — [arXiv 2502.21206](https://arxiv.org/abs/2502.21206); [arXiv 2309.17322](https://arxiv.org/abs/2309.17322)
- Ke, Kelly & Xiu chose to trade only at the open and exclude news from the 30 minutes before the open. Their reasons: most funds cannot continuously trade intraday news, and the gap gives "time to calculate their positions". — [NBER w26186](https://www.nber.org/system/files/working_papers/w26186/w26186.pdf)
- Opening-auction and closing-auction trades are priced in call auctions with no bid-ask spread, so Lopez-Lira & Tang model costs as fixed round-trip bps. — [arXiv 2304.07619](https://arxiv.org/abs/2304.07619)
- A weekly LLM filing-signal allocation on 10 Dow stocks, 2023–2025, uses information to the last close of the week and trades at the next week's open with 10 bps costs. Adding one- or four-week delivery delays did not systematically hurt returns. Filtering signals older than 8 weeks gave the LLM policy its best net return (18.43%/yr at a 4-week delay against 17.6% for equal-weight). — [Song & Xiang, arXiv 2610.30564](https://arxiv.org/abs/2610.30564) (small, weak evidence; slow-moving SEC-filing signals)

### Inferences
- The setup "news to close−20min, trade at close−60s" sits between the zero-latency 4pm-close academic convention and Ke, Kelly & Xiu's 30-minute buffer. For daytime news it captures the same-day close residual that the literature finds is the largest tradable piece after the first minutes. The cost of the 20-minute buffer is that news in the last 20 minutes waits about 24 hours. Ke, Kelly & Xiu show news counts peak near the open and the close, so that window is not negligible.
- For news that waits about 24 hours (after close−20min, or after the Wednesday 22:00 UTC cutoff), the evidence predicts:
  - **Large caps, daily-type news:** most residual drift is lost. Day +1 is the bulk of the residual for big stocks, and the first overnight gap carries much of it.
  - **Earnings, guidance and analyst events:** little extra cost if multi-week drift exists. It is contested for large caps (Martineau; Altinkilic et al.) and small but positive in 2023–26 (Kargarzadeh et al.).
  - **Soft-news events:** possibly a benefit. Entering a day later lets part of the overshoot reverse, but the evidence that delayed entry improves outcomes is indirect.
- The three shadow books (Wednesday-close notional, Thursday open, Thursday close) map onto the decomposition the literature uses: the overnight gap versus the intraday session. Given the year-by-year decay in Lopez-Lira & Tang and Christensen et al., any measured delay cost will likely be smaller than pre-2020 studies imply. Detecting it with 10 names a side needs many weeks of data.

### Gaps
- No study found tests the "Wednesday close signal, Thursday close entry" weekly cohort design, or a close−20min cutoff, for S&P 500 names. The mapping above is by analogy.
- Size-split, post-2022 close-entry results for intraday news (Lopez-Lira & Tang, Online Appendix F) were not retrieved.
