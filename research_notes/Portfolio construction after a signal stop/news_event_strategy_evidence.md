# News-driven and event-driven equity strategies in large caps: what is tradable for a next-day-plus, weekly-cohort trader

Scope note: 20 search/fetch calls. Primary sources were read where they were reachable: the arXiv HTML of Lopez-Lira & Tang v6 and of Kargarzadeh et al. 2026. Other items come from abstracts or index pages (RePEc, NBER, the Federal Reserve, publisher pages) and are marked as such. Some named papers could not be retrieved or verified this session: Womack 1996, Loh–Stulz 2011, Chordia et al. 2009, Tetlock 2007, the full Ke–Kelly–Xiu tables, and the full Chen–Kelly–Xiu tables. They are listed under Gaps rather than cited from memory.

Fund context used for the inferences: entry at Thursday close for a Wednesday desk; news lag p95 about 23 h; 4 bp round-trip cost; own soft-news result +3.7 ± 4.1 bp over 5 days for 2016–2026 (+11.4 bp holdout); SUE IC 0.051 → 0.025.

## 1. Hard vs soft news: effect sizes, decay speed, large vs small caps, after costs, next-day entry

### Takeaway
The literature agrees on the direction. Price moves on identified, fundamental ("hard") news continue. Moves on no news or stale news reverse. Story-like soft news is mostly priced at or before publication and then partly reverses. Almost all of the after-cost predictability from news text sits on day 0 or day +1 and is concentrated in small stocks. For large caps, published next-day news-sentiment strategies are wiped out by costs of about 10–20 bp round trip, and the best LLM signal's Sharpe ratio fell from 6.5 to 1.2 between 2021 and 2024.

### Cited Findings
**Identified (hard) news vs. no news (S&P 500, so large caps)**
- Boudoukh, Feldman, Kogan & Richardson, "Information, trading, and volatility: Evidence from firm-specific news", *Review of Financial Studies* 32(3), March 2019. Textual analysis that identifies fundamental news explains 49.6% of overnight idiosyncratic volatility, against 12.4% during trading hours. **"Conditional on extreme moves, stock price reversals occur on no news days, while identified news days show an opposite effect, namely a strong degree of continuation."** — [HUJI CRIS record](https://cris.huji.ac.il/en/publications/information-trading-and-volatility-evidence-from-firm-specific-ne/)
- The earlier NBER version (w18725, "Which News Moves Stock Prices? A Textual Analysis") covers all S&P 500 firms, 2000–2009. The Dow Jones Newswire carried more than 1.9 million stories, but only about half were classifiable as relevant events. Volatility on identified-news days is more than twice that of other days. — [NBER w18725](https://www.nber.org/papers/w18725); [NBER Digest summary](https://www.nber.org/digest/jun13/which-news-moves-stock-prices)

**News vs. no-news momentum and reversal**
- Chan (2003), "Stock price reaction to news and no-news: drift and reversal after headlines", *JFE* 70(2): 223–260. Monthly horizon. There is strong drift after bad news, and reversal after extreme moves without public news. **"These patterns are mainly seen in smaller, more illiquid stocks."** (Sample of about 1980–2000, from headline data; the exact years were not re-verified this session.) — [abstract via SUFE newsletter](https://academicnewsletter.sufe.edu.cn/info/357702); [RePEc/related listing](https://ideas.repec.org/a/eme/rafpps/v7y2008i1p102-115.html)

**Stale news (Tetlock 2011)**
- Tetlock, "All the News That's Fit to Reprint: Do Investors React to Stale Information?", *RFS* 24(5): 1481–1512, 2011.
  - Staleness is defined as textual similarity to the previous 10 stories about the same firm.
  - Returns respond less to stale news.
  - The day-of-stale-news return negatively predicts the next week's return.
  - The reversal is larger where individual-investor trading is above average.
  - [RePEc](https://ideas.repec.org/a/oup/rfinst/v24y2011i5p1481-1512.html); [SUFE abstract](https://academicnewsletter.sufe.edu.cn/info/354725)

**Tetlock–Saar-Tsechansky–Macskassy (2008, "More than words"), as summarised by CXO Advisory**
- News sentiment predicts next-day returns: 21.1% annualised for a daily-rebalanced long-positive / short-negative portfolio built from Dow Jones News Service stories, S&P 500 firms, 1980–2004.
- **"transaction costs eliminate profitability."**
- This is a secondary summary; the original paper was not opened.
- [CXO Advisory](https://www.cxoadvisory.com/sentiment-indicators/financial-news-sentiment-predicts-stock-returns/)

**Heston & Sinha, "News vs. Sentiment: Predicting Stock Returns from News Stories"** (FEDS 2016-048; *FAJ* 73(3), 2017)
- Data: more than 900,000 stories, scored with the Thomson Reuters neural-network sentiment.
- **Daily news predicts returns for only 1–2 days; weekly-aggregated news predicts returns for about a quarter.**
- Asymmetry: positive news is priced within about a week or two. Negative news has a long delayed reaction, up to about 13 weeks, much of it around the next earnings announcement.
- [Federal Reserve FEDS page](https://www.federalreserve.gov/econres/feds/news-versus-sentiment-predicting-stock-returns-from-news-stories.htm); [PDF](https://www.federalreserve.gov/econresdata/feds/2016/files/2016048pap.pdf)

**Lopez-Lira & Tang, "Can ChatGPT Forecast Stock Price Movements? Return Predictability and Large Language Models"** (arXiv 2304.07619, v6; read in full)
- *Sample:* October 2021 – May 2024, headlines for 4,123 US stocks, all after the model's training cutoff.
- *Initial reaction (overnight news):* GPT-4 positive vs negative portfolios move +1.27% and −1.79%, with a 93.3% directional hit rate. The regression coefficient is 1.326 (t = 31.1).
- *Drift after the initial reaction (overnight news):* 0.34% per day long-short, Sharpe 2.97.
  - The short leg carries most of it: 0.26% per day (Sharpe 2.01) against 0.08% per day (Sharpe 0.78) for the long leg.
  - The drift coefficient is 0.161 (t = 6.80), so moving from a negative to a positive score is worth about 32 bp.
- *Size:* the base drift coefficient is 0.087 (t = 4.09). The small-stock interaction (below the 10th NYSE percentile) adds 0.404 (t = 4.75). The paper says the small-stock coefficient is "more than four times" the coefficient for the rest of the sample. My inference: non-small stocks give about 17 bp per day for a full negative-to-positive swing, before costs.
- *Costs:* cumulative return is above 300% at 5 bp round trip and above 100% at 10 bp. **The strategy is unprofitable at 20 bp round trip.**
- *Decay with LLM adoption:* annualised Sharpe was 6.54 in 2021Q4, 3.68 in 2022, 2.33 in 2023 and 1.22 in Jan–May 2024.
- *By topic:*

  | Topic | Initial reaction × GPT | Drift × GPT | Significance |
  |---|---|---|---|
  | Earnings reports | 336.7 bp | **−4.7 bp** | not significant |
  | Clinical trials | 308.5 bp | −11.4 bp | not significant |
  | Insider transactions | 71.4 bp | 26.3 bp | significant |
  | Dividend announcements | 45.5 bp | 22.3 bp | significant |
  | Healthcare conferences | 103.5 bp | 34.2 bp | significant |

  So hard, salient events such as earnings are priced at once. Drift survives in low-attention, lower-salience categories.
- [arXiv HTML v6](https://arxiv.org/html/2304.07619v6); [abstract](https://arxiv.org/abs/2304.07619v5)

**Chen, Kelly & Xiu, "Expected Returns and Large Language Models"** (2022 working paper)
- LLM embeddings (ChatGPT, LLaMA) of news text beat technical signals and simpler NLP in predicting returns.
- Covers 16 international markets and 13 languages.
- "A trading strategy that exploits fresh news in the form of news alerts leads to even higher Sharpe ratios."
- The precise Sharpe ratios, horizons and size splits were not retrieved this session.
- [Wharton Jacobs Levy discussion slides (S. Z. Li)](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2024/09/ExpectedReturnAndLLM_Discussion_SophiaZhengziLi_NoPause.pdf); [Kelly slides](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2024/09/Kelly-WhartonJL.pdf); [seminar listing](https://acem.sjtu.edu.cn/academic/82735.html)

**Ke, Kelly & Xiu, "Predicting Returns with Text Data"** (SESTM, NBER w26186)
- Supervised sentiment model built on the Dow Jones Newswires feed. Its out-of-sample portfolios give "excellent risk-adjusted out-of-sample returns".
- The day-0 / day-1 / day-2 decay table and the size splits were not retrieved this session; see Gaps.
- [NBER w26186](https://www.nber.org/papers/w26186); [NSF PAR copy](https://par.nsf.gov/servlets/purl/10289824)

**Kargarzadeh, Khaledian, Parvini, Ghatak & Khaledian, "Buy the Rumor, Sell the News: When Is News Priced In?"** (arXiv 2608.14014, Aug 2026; AI4F 2026 workshop, not peer-reviewed)
This is the closest published analogue to the fund's soft-news test.
- *Data:* 2023–2026; 4.57 million articles on about 3,000 US stocks; 1.68 million stock-day events; 364,405 neutral events as controls.
- *Classifier:* gpt-5-mini teacher distilled into DistilRoBERTa, with 95% fidelity to the teacher.
- *Timing:* articles after 16:00 New York time roll to the next trading day.
- *Headline result:* **the cumulative move in the news direction by the close of the publication day is 2.84× its value 20 days later.** Most of the move sits before or at publication.
- *By category* (day 0 / days 1–5 / days 6–20; the "adjusted" figure is the paper's benchmark-adjusted number, whose exact definition was not confirmed):
  - Earnings: +0.42% / −0.04% / −0.05% (adjusted +0.22%, significant)
  - Guidance: +0.56% / −0.02% / −0.09% (adjusted +0.13%)
  - Analyst action: +0.22% / −0.05% / −0.13% (adjusted +0.10%)
  - Legal/regulatory: +0.19% / **+0.11%** / **+0.29%** (adjusted −0.08%)
  - Capital returns: +0.06% / −0.01% / −0.14% (adjusted +0.35%, significant)
  - **Product launch: +0.03% / −0.22% / −0.73% (adjusted −0.18%)**
  - **Macro read-through: +0.05% / −0.22% / −0.76% (adjusted −0.34%, significant reversal)**
  - **Leadership/governance: +0.08% / −0.10% / −0.51% (adjusted −0.18%)**
  - **M&A deal: +0.04% / −0.23% / −0.46% (adjusted −0.05%)**
- *Paper's summary:* quantified fundamentals (earnings, dividends, guidance, analyst actions) keep drifting for weeks. Story-driven news (launches, macro commentary, leadership) reverses.
- *Statistics:* p-values come from a date bootstrap with 5,000 draws.
- *Size:* stocks are split by dollar volume into terciles. The fetch did not return the per-tercile numbers.
- *Costs:* modelled only as 5–20 bp per side scenarios.
- [arXiv abstract](https://arxiv.org/abs/2608.14014); [HTML](https://arxiv.org/html/2608.14014)

### Inferences
- The fund's soft-news categories are the ones Kargarzadeh et al. label "story-driven": product launch, partnership, leadership, macro read-through and M&A rumour. In that independent 2023–26 sample, these reverse on average after day 0. The fund's own +3.7 ± 4.1 bp follow-through, concentrated in 2023–24, therefore does not contradict the literature. If anything it is more favourable than the literature, which predicts about zero or a reversal.
- Hard, quantified news (earnings, guidance, analyst actions) is where continuation is documented: Boudoukh et al. continuation, Heston–Sinha weekly news, and Kargarzadeh "adjusted" drift. But the gross numbers per event are small after day 0, at about 10–35 bp over 20 days. In Lopez-Lira & Tang the drift after earnings headlines is about zero (−4.7 bp, not significant).
- Next-day entry is the binding constraint. Every LLM and dictionary paper that reports large economic effects measures them from the first tradable moment after publication (the next open, or day 0 / day 1). With a p95 lag of about 23 h and entry at Thursday close, the fund trades at roughly day +1 to day +2 relative to publication. Heston–Sinha and the Lopez-Lira Sharpe decay put most of the daily-news signal outside that window.
- The one documented exception that fits a weekly cadence is **aggregating news over a week** (Heston–Sinha: weekly news predicts for about a quarter) and the **slow incorporation of negative news** (Heston–Sinha, Chan 2003, and the Lopez-Lira short-leg dominance). That points to short-side, negative, hard news as the most promising residual, though Chan says this is mainly a small-cap effect.

### Gaps
- Tetlock (2007, *JF* "Giving Content to Investor Sentiment") market-level results were not re-fetched. The firm-level and cost result for Tetlock et al. (2008) comes only from the CXO secondary summary.
- Ke–Kelly–Xiu: the exact day-0/1/2 Sharpe decay and the large-cap split were not retrieved. From memory (unverified), the paper reports that most predictability is on days 0–1 and is stronger in small stocks. Treat this as unconfirmed.
- Chen–Kelly–Xiu: the exact Sharpe ratios and their split by size and horizon were not retrieved.
- Kargarzadeh et al.: the dollar-volume tercile results (large-cap only) and the exact definition of "adjusted" are unknown. It is an unrefereed workshop paper.
- No source found reports news-text strategies restricted to the S&P 500 after 2015 with costs, apart from the CXO summary of Tetlock et al. (1980–2004) and Lopez-Lira's non-small coefficient.

## 2. Event-specific drift in large caps: PEAD, M&A rumours, CEO turnover (8-K 5.02), material agreements (8-K 1.01), analyst revisions, product launches

### Takeaway
PEAD in large caps has been about zero since around 2006, according to Martineau. M&A rumours reverse, by about twice the initial pop, over the following three quarters. CEO-turnover announcements carry small announcement returns of about 25–50 bp, with no documented post-event drift in large caps. 8-K items as a group show some drift, but with no large-cap or post-2015 split found. For product launches and leadership news the only recent evidence points to reversal.

### Cited Findings
**PEAD**
- Martineau, "Rest in Peace Post-Earnings Announcement Drift", *Critical Finance Review* 11(3–4): 613–646, 2022. **"For large stocks, PEAD have been non-existent since 2006 but has only disappeared recently for microcap stocks."** Prices now fully reflect the earnings surprise on the announcement day. The paper attributes the change to faster arbitrage and HFT after the 2005 regulation (Reg NMS). — [RePEc](https://ideas.repec.org/a/now/jnlcfr/104.00000122.html); [CFR PDF](https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf); [SocArXiv](https://ideas.repec.org/p/osf/socarx/z7k3p.html)
- UCLA Anderson Review, "Is post-earnings announcement drift a thing again?" — a counterpoint article; its content was not opened, so its claims are not reported here. — [Anderson Review](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/)
- Lopez-Lira & Tang (2021–24 headlines): drift after earnings headlines is −4.7 bp, not significant. — [arXiv](https://arxiv.org/html/2304.07619v6)

**M&A rumours**
- Literature summary (the EFMA 2008 paper and a 1999–2018 rumour sample): rumours produce significantly positive announcement reactions. **Returns over the next three quarters are significantly negative and about twice the size of the announcement effect**, so prices end below their pre-rumour level. False rumours cause the largest overreaction. — [Columbia CLS Blue Sky, "The M&A rumor productivity dip" (2021)](https://clsbluesky.law.columbia.edu/2021/03/17/the-ma-rumor-productivity-dip); [Spyrou et al., EFMA 2008](https://www.efmaefm.org/0EFMAMEETINGS/EFMA%20ANNUAL%20MEETINGS/2008-Athens/papers/Spyrou.pdf); [RePEc, Applied Economics Letters 2013](https://ideas.repec.org/a/taf/apeclt/v20y2013i6p520-524.html)
- Kargarzadeh et al. (2026): M&A deal news shows −0.23% on days 1–5 and −0.46% on days 6–20 after a +0.04% day 0. For rumour-flagged events, "directional returns concentrate around the rumor event", with little extra movement at later linked non-rumour events. — [arXiv](https://arxiv.org/html/2608.14014)

**CEO turnover (8-K Item 5.02)**
- Announcement abnormal returns are typically 25–50 bp for all changes and 1–3% for some subsamples (forced turnover, outside successor).
  - An outsider named after a performance-related forced resignation earns more than +2%.
  - An internal promotion at a poorly performing firm loses about 1% on the day.
  - Before forced turnover there is a run-up of about 6% abnormal over the prior month (anticipation).
  - Sample: US, 1979–1995.
  - [NY Fed Staff Report 166](https://www.newyorkfed.org/research/staff_reports/sr166.pdf); [CXO Advisory summary](https://cxoadvisory.com/fundamental-valuation/stock-price-impacts-of-management-changes)
- Kargarzadeh et al.: leadership/governance news gives +0.08% on day 0, then −0.10% on days 1–5 and −0.51% on days 6–20, i.e. a reversal. — [arXiv](https://arxiv.org/html/2608.14014)

**8-K items, including 1.01 (material agreements)**
- An NYU/SSRN study of 8-Ks after the 2004 item reform finds that all items carry abnormal volume and volatility around the event and the filing dates, and **"some items have significant return drift in the expected direction for up to 90 days after the SEC filings"**. The drift is larger in subsamples with no periodic filing within 90 days. Which items drift, and the size split, were not extracted. — [NYU archive, SSRN-id1126816](https://archive.nyu.edu/bitstream/2451/27579/2/SSRN-id1126816.pdf)
- An LDA-topic event study of 8-K text finds that market reactions differ by topic. — [arXiv 1805.03308](https://arxiv.org/pdf/1805.03308)

**Anomalies and news days**
- Engelberg, McLean & Pontiff, "Anomalies and News", *JF* 73(5): 1971–2001, 2018. Across 97 anomalies, **returns are 50% higher on corporate news days and 6× higher on earnings-announcement days**, which the authors read as biased expectations being corrected when news arrives. The user's attribution to "Engelberg–Reed–Ringgenberg" is a different paper: Bowles, Reed, Ringgenberg & Thornock, "Anomaly Time". — [RePEc](https://ideas.repec.org/a/bla/jfinan/v73y2018i5p1971-2001.html); [Engelberg PDF](https://rady.ucsd.edu/faculty/directory/engelberg/pub/portfolios/ANOMALIES_NEWS.pdf)

**Lower-salience events (insider trades, dividends)**
- Lopez-Lira & Tang find significant drift of +26.3 bp after insider-transaction headlines, +22.3 bp after dividend headlines and +34.2 bp after healthcare-conference headlines, against no drift for earnings. — [arXiv](https://arxiv.org/html/2304.07619v6)
- RavenPack markets an insider-transaction signal conditioned on 3-month news sentiment (vendor claim). — [EACCNY member news](https://eaccny.com/news/member-news/ravenpack-insider-trading-strategies-enhanced-by-news-sentiment-data/)

### Inferences
- The fund's SUE failure in large caps (IC 0.051 fitted → 0.025 holdout) is what Martineau predicts. There is no reason to expect a revival for S&P 500 names.
- M&A rumours are a reversal class, not a follow-through class. Including them in a follow-through rule plausibly dragged the fund's soft-news mean toward zero. This is a hypothesis for any new pre-registered protocol, not a fix to the spent read.
- 8-K 5.02 (CEO change): the documented effect is an announcement-day move and pre-event anticipation, with no post-event drift. 8-K 1.01: no item-level, large-cap, post-2015 drift evidence was found.
- The categories with documented post-headline drift are low salience: insider trades, dividends and small conferences. They are not the high-salience hard news (earnings, guidance) that the fund's live entries now emphasise.

### Gaps
- The following were not retrieved this session, so no numbers are cited:
  - Womack (1996), on post-recommendation drift, especially for downgrades.
  - Loh & Stulz (2011), "When are analyst recommendation changes influential?".
  - Chordia, Goyal, Sadka, Sadka & Shivakumar (2009), "Liquidity and the post-earnings-announcement drift".
- No post-2015 large-cap study of drift after 8-K 1.01 or 5.02 was found.
- No academic study isolating "product launch" announcement drift in large caps was found, beyond the Kargarzadeh category result.
- Partnership and alliance announcements: no source found this session.

## 3. Speed of price discovery in large caps: minutes vs days; overnight vs intraday

### Takeaway
In large caps, hard news is priced within the trading day, mostly overnight or at the open. Underreaction for "several days" is documented with high-frequency news identification (Jiang–Li–Wang 2021), but the abstract does not give the large-cap, after-cost magnitudes. Bloomberg's own research says large caps leave "less chance to capture anything after a day".

### Cited Findings
- Boudoukh et al. (2019): identified fundamental news explains 49.6% of overnight idiosyncratic volatility, against 12.4% intraday. News arrival and price formation are concentrated overnight, i.e. outside trading hours. — [HUJI CRIS](https://cris.huji.ac.il/en/publications/information-trading-and-volatility-evidence-from-firm-specific-ne/)
- Jiang, Li & Wang, "Pervasive Underreaction: Evidence from High-Frequency Data", *JFE* 141(2): 573–599, 2021.
  - Method: daily returns are decomposed with high-frequency data into news-driven and non-news components.
  - **"Prices tend to drift in the same direction as the initial market response for several days after the news arrival without reversals. A trading strategy exploiting the return drift generates high abnormal returns and remains profitable after transaction costs."**
  - Drift is stronger when investors are distracted, and is helped by analysts' slow updating of expectations.
  - The bp magnitudes and the size split were not retrievable (SSRN returned 403).
  - [SSRN 2679614](https://papers.ssrn.com/abstract=2679614); [RePEc](https://ideas.repec.org:443/a/eee/jfinec/v141y2021i2p573-599.html)
- Martineau (2022): for large stocks, the earnings surprise is fully priced on announcement day from 2006. — [CFR PDF](https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf)
- Kargarzadeh et al. (2026): the move by the close of the publication day is 2.84× the 20-day cumulative move. "The move sits before and at publication." — [arXiv](https://arxiv.org/html/2608.14014)
- Bloomberg (vendor practitioner blog, opinion and in-house research): **"For large cap stocks, the market is very efficient with less chance to capture anything after a day"**. Small caps take longer to digest information. — [Bloomberg Professional blog](https://www.bloomberg.com/professional/blog/can-get-edge-trading-news-sentiment-data); [Tech at Bloomberg](https://www.bloomberg.com/company/stories/finding-novel-ways-trade-sentiment-data)
- Heston & Sinha: the daily-news signal lasts 1–2 days. — [FEDS PDF](https://www.federalreserve.gov/econresdata/feds/2016/files/2016048pap.pdf)

### Inferences
- With a p95 news lag of about 23 h, plus Wednesday-desk to Thursday-close entry, the fund enters after the window in which large-cap hard news is priced. The only after-cost drift claim at multi-day horizons is Jiang–Li–Wang's "several days, profitable after costs". It is pooled across sizes and assumes the trader can identify news-driven returns from intraday data at publication time, which this desk cannot.
- A 2.84 ratio of day-0 to day-20 move means that, on average, the day-0 move is partly given back. Any rule that "follows the news-day direction" from day +1 is fighting reversal unless it filters for a class that continues.

### Gaps
- Large-cap-specific half-lives in minutes for news reactions (e.g. HFT event studies around newswire timestamps) were not retrieved.
- Jiang–Li–Wang: the drift in bp per day, the after-cost returns and the large-cap subsample are unconfirmed.

## 4. How event-driven and news PMs filter events, and what vendors and forums say survives costs

### Takeaway
The filters that recur are:
- **novelty** (non-stale; Tetlock 2011 and the vendor "event novelty" scores);
- **relevance** (the firm is the subject; Boudoukh et al.'s "identified" events);
- **hard and quantified over story-driven** (Kargarzadeh 2026);
- **surprise relative to expectations**;
- **direction**, where negative news is slower (Heston–Sinha, Chan).

Vendor claims of large-cap robustness are mostly crisis-period or in-house. Independent summaries say costs remove large-cap next-day news-sentiment profits. Forum-level practitioner evidence was thin in this search.

### Cited Findings
- *Novelty and staleness:* Tetlock (2011) finds that stale news (high similarity to the last 10 stories) reverses within a week, especially where retail trading is heavy. — [RePEc](https://ideas.repec.org/a/oup/rfinst/v24y2011i5p1481-1512.html)
- *Relevance and identification:* only about half of 1.9 million Dow Jones stories on S&P 500 firms were classifiable as relevant events. Continuation is confined to identified-event days. — [NBER Digest](https://www.nber.org/digest/jun13/which-news-moves-stock-prices); [HUJI CRIS](https://cris.huji.ac.il/en/publications/information-trading-and-volatility-evidence-from-firm-specific-ne/)
- *RavenPack (vendor claims, not independently verified):*
  - A long-short US large-cap strategy on extreme positive vs negative sentiment delivered information ratios of 2.6–2.8 during the Global Financial Crisis.
  - Signals "continued to be successful for up to a month ahead" in some white papers.
  - Signal decay is "much slower" for small caps.
  - [Finadium summary](https://finadium.com/?p=106487); [EACCNY member news (COVID-period sentiment)](https://eaccny.com/news/member-news/ravenpack-sentiment-data-outperforms-during-coronavirus-crisis/); [Nordot, small-caps](https://nordot.app/681884679869138017)
- *Bloomberg (vendor):* the edge in large caps is mostly within a day; small caps are slower. — [Bloomberg blog](https://www.bloomberg.com/professional/blog/can-get-edge-trading-news-sentiment-data)
- *Independent summary:* "transaction costs eliminate profitability" of next-day S&P 500 news-sentiment trading (Tetlock et al. 2008 data). — [CXO Advisory](https://www.cxoadvisory.com/sentiment-indicators/financial-news-sentiment-predicts-stock-returns/)
- *LLM edge decay (academic):* Sharpe 6.54 → 1.22 from 2021Q4 to 2024H1; break-even round-trip cost under 20 bp. — [arXiv](https://arxiv.org/html/2304.07619v6)
- *Rumour and type filter:* rumour-flagged moves concentrate at the rumour; story-driven categories reverse. — [arXiv 2608.14014](https://arxiv.org/html/2608.14014)

### Inferences
- In descending order of support, a practitioner-style filter set for this desk would be:
  1. typed, identified, firm-specific events only;
  2. non-stale, by similarity to the firm's recent stories;
  3. quantified fundamentals with a measurable surprise;
  4. a negative-news (short-side) emphasis;
  5. exclusion of rumours and story-driven categories from any continuation rule. M&A rumours may belong in a reversal rule instead.
- The vendor large-cap numbers (IR 2.6–2.8) come from the 2008–09 crisis and are vendor marketing. They should not be read as a post-2015 large-cap after-cost estimate.

### Gaps
- **Forum evidence was thin.** The searches did not surface usable threads from r/quant, r/algotrading, QuantNet, Nuclear Phynance, Elite Trader, Quant StackExchange, X or Substack with concrete numbers. No forum opinion is cited.
- Man Group, AQR and Refinitiv MarketPsych notes were not retrieved. AQR's page for Frazzini's "The Disposition Effect and the Under-Reaction to News" appeared in results but was not opened: [AQR](https://www.aqr.com/Insights/Research/Journal-Article/The-Disposition-Effect-and-the-UnderReaction-to-News).
- The Loughran–McDonald textual-analysis surveys were not retrieved.
- No RavenPack white paper with explicit post-2015, S&P 500-only, next-day-plus-entry, after-cost numbers was found.

## 5. Implication: is there any news class where a next-day-plus, weekly-cohort large-cap trader has a documented after-cost edge?

### Takeaway
The documented evidence does not show a robust one. Effects that survive into day +1 or later in large caps are a few tens of bp gross per event at best, shrinking over time, and similar to a 4–20 bp round-trip cost. Only a few candidates have some support, each weak:
1. negative hard news, short side (slow incorporation);
2. weekly-aggregated news tone at a quarterly horizon (Heston–Sinha);
3. low-salience events such as insider transactions and dividends;
4. reversal, not continuation, after story-driven soft news, stale news and M&A rumours.

### Cited Findings
- *Next-day news-sentiment trading:*
  - Large caps: unprofitable after costs in S&P 500 data, 1980–2004. — [CXO](https://www.cxoadvisory.com/sentiment-indicators/financial-news-sentiment-predicts-stock-returns/)
  - LLM version: break-even below 20 bp round trip, with Sharpe decaying to 1.22 by 2024 (all sizes). — [arXiv](https://arxiv.org/html/2304.07619v6)
- *PEAD in large caps:* absent since 2006. — [CFR](https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf)
- *Soft, story-driven news:* reverses (launch −0.73%, macro −0.76%, leadership −0.51% over days 6–20; 2023–26). — [arXiv 2608.14014](https://arxiv.org/html/2608.14014)
- *M&A rumours:* reverse at about 2× the initial pop over three quarters. — [CLS Blue Sky](https://clsbluesky.law.columbia.edu/2021/03/17/the-ma-rumor-productivity-dip)
- *Stale news:* reverses within a week. — [RePEc](https://ideas.repec.org/a/oup/rfinst/v24y2011i5p1481-1512.html)
- *Weekly news:* predicts for about a quarter, and bad news is slow (up to about 13 weeks). — [FEDS](https://www.federalreserve.gov/econres/feds/news-versus-sentiment-predicting-stock-returns-from-news-stories.htm)
- *Identified-news continuation:* documented in the S&P 500, 2000–09. — [NBER](https://www.nber.org/papers/w18725)
- *Multi-day drift after high-frequency-identified news:* claimed to survive costs (all sizes; magnitudes unverified). — [SSRN](https://papers.ssrn.com/abstract=2679614)

### Inferences
- **The fund's own result is in line with the literature.** Soft-news follow-through of +3.7 ± 4.1 bp per 5 days against a 4 bp cost is about what the evidence predicts: zero or reversal for story-driven news, with any gross residual eaten by costs.
- **The remaining live "hard news" entries are not obviously better at the fund's entry lag.** Earnings and guidance are priced on day 0 in large caps (Martineau; Lopez-Lira's −4.7 bp earnings drift). The Kargarzadeh "adjusted" continuation for earnings, at about +22 bp over 20 days, is the only positive number, and it is from an unrefereed 2026 paper with unknown large-cap results.
- **Legal/regulatory is the one hard category in Kargarzadeh with positive raw post-day-0 follow-through:** +11 bp on days 1–5 and +29 bp on days 6–20. Its adjusted value, however, is −8 bp. This is a hypothesis worth pre-registering, not evidence.
- **A shape that fits a weekly cohort better** (hypotheses for a new protocol, not tested here):
  - weekly-aggregated, novelty-filtered news tone with a 1–3 month holding period;
  - a short-side tilt on negative hard news;
  - a contrarian rule on story-driven soft news and M&A rumours.
- **Expected size:** given the decay evidence, any edge would be a few bp per week per name. It would need low turnover to clear a 4 bp round trip.
- Every effect-size claim above should be read with three caveats:
  - few studies report large-cap-only, post-2015, after-cost results;
  - the strongest positive numbers (Lopez-Lira's Sharpe of about 3, RavenPack's IR of 2.6–2.8) come from small-cap-heavy or crisis samples, or from day-0/1 entry;
  - LLM-era decay shows such edges shrinking.

### Gaps
- No study found tests a Thursday-close entry, about 1–2 trading days after publication, on S&P 500 names after 2015 with costs. That is exactly the fund's configuration, so the fund's own records are the most relevant evidence.
- Analyst-revision drift in large caps after 2015 (Womack, Loh–Stulz follow-ups): not retrieved.
- Jiang–Li–Wang large-cap magnitudes: not retrieved.
