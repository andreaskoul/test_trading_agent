# Order timing around the US close and open: industry practice, market structure, exchange rules and Alpaca/IBKR mechanics (2020–2026)

Scope note: research as of 2026-10-30. All times are US Eastern. "bp" = basis points. Figures older than 2020 are flagged as such. Where sources conflict, both are given.

## 1. Exchange rules: closing and opening auctions (NYSE, Nasdaq, NYSE Arca/other NYSE venues, Cboe), official closing price, contingencies, recent rule changes

### Takeaway
On-close orders on the two listing markets lock at **3:50 p.m. (NYSE: entry, modify and cancel; Nasdaq: modify and cancel)**. Nasdaq still accepts new MOC orders until just before **3:55** and "late" LOC orders until just before **3:58**, re-priced if needed. Imbalance data starts at 3:50 on both. After 3:50 only offsetting interest gets in: NYSE floor-broker D-Orders (until 3:59:50) and Closing Offset orders, and Nasdaq IO orders (until 4:00). The official close is the primary listing market's auction print (one round lot or more). If the auction fails, a fixed industry contingency applies: an alternate exchange runs the close if the failure is declared by 3:00 p.m.; after 3:00 p.m. the official close is the VWAP of the last 5 minutes. I found no live Cboe auction that sets official closes for NYSE- or Nasdaq-listed stocks. Cboe Market Close only pre-matches MOC orders at the primary close.

### Cited Findings

**NYSE (Tape A, NYSE-listed) – close**
- MOC and LOC orders "can be entered, modified or canceled until 3:50 p.m." After 3:50 they can be entered "only on the contra-side of a MOC/LOC Significant Imbalance until 4:00 p.m." and "cannot be modified or canceled" (NYSE fact sheet, ©2024). — [NYSE Opening and Closing Auctions Fact Sheet](https://WWW.NYSE.COM/publicdocs/nyse/markets/nyse/NYSE_Opening_and_Closing_Auctions_Fact_Sheet.pdf)
- The older 2021 version of the closing fact sheet allowed more. Between 3:50 and 3:58, MOC/LOC/CO orders could be cancelled only for documented "legitimate errors". After 3:58, cancels were rejected and "requests to cancel must be called into the NYSE Trade Desk" under Rule 7.35B(j)(2)(B). — [NYSE Closing Process Fact Sheet (©2021)](https://www.nyse.com/publicdocs/nyse/NYSE_Auctions_Closing_Process_Fact_Sheet.pdf)
- Closing Offset (CO) orders:
  - limit orders only, with "no validation against any imbalance publication (any size, price or side allowed)";
  - they yield to all other closing interest and execute "only against the opposite side of an imbalance; never adds to an imbalance";
  - they "can only better the closing price" and follow the MOC/LOC cancel rules. — [NYSE Closing Process Fact Sheet](https://www.nyse.com/publicdocs/nyse/NYSE_Auctions_Closing_Process_Fact_Sheet.pdf)
- Closing D-Orders:
  - limit only and floor-broker only; they "exercise discretion in the Closing Auction to a designated undisplayed price";
  - they can be entered, modified or cancelled until 3:59:50 p.m., and are included in the published imbalance from 3:55 p.m. — [NYSE fact sheet 2024](https://WWW.NYSE.COM/publicdocs/nyse/markets/nyse/NYSE_Opening_and_Closing_Auctions_Fact_Sheet.pdf); [NYSE Closing Process Fact Sheet 2021](https://www.nyse.com/publicdocs/nyse/NYSE_Auctions_Closing_Process_Fact_Sheet.pdf); [NYSE "Getting to know D Orders"](https://www1.nyse.com/data-insights/getting-to-know-d-orders-a-unique-execution-tool-for-nyse-floor-brokers)
- Imbalance publication:
  - from 3:50 p.m., "every 1 second if different from the previous publication";
  - contents: paired quantity, unpaired quantity, total imbalance quantity, closing-only interest price, and continuous-book clearing price. — [NYSE fact sheet 2024](https://WWW.NYSE.COM/publicdocs/nyse/markets/nyse/NYSE_Opening_and_Closing_Auctions_Fact_Sheet.pdf)
  - Conflict: a search summary of NYSE's "Closing Auction Insider's Guide" said every five seconds. That is probably older material, and the 2024 fact sheet says 1 second. — [NYSE insiders guide](https://nyse.com/article/nyse-closing-auction-insiders-guide)
- NYSE "Holidays & Trading Hours" (Tape A): 3:50–4:00 p.m. is the "Closing Imbalance Period" and 4:00 p.m. the "Closing Auction". — [NYSE hours & calendars](https://www.nyse.com/markets/hours-calendars)
- The NYSE close is dominated by floor-broker D-Orders, which arrive very late. In September 2025 (NYSE-listed S&P 500 stocks), auction interest was "roughly 60%" D-Orders, about 20% MOC and about 20% LOC.
  - "Over 60% of D-Orders are submitted after 3:57:30 p.m."
  - The share of D-Orders entered in the final 10 seconds rose from 4.45% (Aug 2024) to 13.4% (Sep 2025).
  - Source: NYSE, 18 Nov 2025. — [NYSE: Closing Auction Timing Shifts and Marketability Trends](https://www.nyse.com/research/insights/nyse-closing-auction-timing-shifts-and-marketability-trends)
- BMLL (June 2025): D-Orders were 46% of NYSE closing-auction executed volume as of Aug 2024. 51% of D-Order insertions came in the final three minutes. — [BMLL "Into the Close"](https://www.bmlltech.com/news/market-insight/into-the-close-unpacking-u-s-closing-auction-dynamics-and-the-impact-of-the-russell-reconstitution)

**NYSE – open**
- Pillar gateways open at 6:30 a.m. Opening imbalance and paired-off information is disseminated "every 1 second… if changed" from 8:00 a.m. until the stock opens. — [NYSE fact sheet 2024](https://WWW.NYSE.COM/publicdocs/nyse/markets/nyse/NYSE_Opening_and_Closing_Auctions_Fact_Sheet.pdf)
- DMMs open each security from 9:30. A security that can open within 10% of its reference price can be opened algorithmically; outside that range it must be opened manually. Orders "can be entered and cancelled until the security is opened by the DMM, even if… after 9:30 a.m." So NYSE opens are not instantaneous. — [NYSE fact sheet 2024](https://WWW.NYSE.COM/publicdocs/nyse/markets/nyse/NYSE_Opening_and_Closing_Auctions_Fact_Sheet.pdf)
- Other NYSE Group equity venues (Arca, American, Texas) list on the same page:
  - a "9:29 a.m. – MOO/LOO Cancellation Cutoff";
  - a 9:29:55–9:30 core-open imbalance freeze;
  - a closing-auction imbalance freeze of 3:50–4:00 or 3:59–4:00, depending on the venue. — [NYSE hours & calendars](https://www.nyse.com/markets/hours-calendars)

**Nasdaq Closing Cross (current FAQ, ©2025)**
- Order cutoffs:
  - MOC orders "must be received prior to 3:55 p.m."
  - LOC orders received after 3:55 are accepted at their limit unless "more aggressive than the 3:50 p.m. or the 3:55 p.m. Reference Prices", in which case they are re-priced. LOC orders "must be received prior to 3:58 p.m." LOCs entered after 3:58 are not accepted, regardless of TIF.
  - "Orders can be modified or cancelled… for the closing cross prior to 3:50 p.m."
  - Source: [Nasdaq Opening and Closing Crosses FAQ](https://nasdaqtrader.com/content/productsservices/trading/crosses/openclose_faqs.pdf)
- NOII (Net Order Imbalance Indicator):
  - From 3:50 to 3:55, every 10 seconds: current reference price, paired shares, imbalance shares and imbalance side.
  - From 3:55 to 4:00, every second, adding the Near Indicative Clearing Price (on-close book plus continuous book) and the Far Indicative Clearing Price (on-close book only). — [Nasdaq FAQ](https://nasdaqtrader.com/content/productsservices/trading/crosses/openclose_faqs.pdf); [Nasdaq Closing Cross FAQ (2019)](https://www.nasdaqtrader.com/content/productsservices/Trading/ClosingCrossfaq.pdf)
- IO (Imbalance-Only) orders are priced liquidity that only offsets on-close imbalances. They are re-priced to the Nasdaq best bid/ask before the cross. The 2019 FAQ allows entry "until 4:00 p.m." — [Nasdaq Closing Cross FAQ 2019](https://www.nasdaqtrader.com/content/productsservices/Trading/ClosingCrossfaq.pdf)
- Cross price rule: (1) maximise shares executed; (2) minimise the imbalance; (3) minimise the distance from the Nasdaq inside midpoint. The price must fall within a threshold of the greater of $0.50 or 10% of the QBBO midpoint beyond the bid/offer. Only interest on the Nasdaq book participates ("Only interest on the Nasdaq book is eligible"). — [Nasdaq FAQ](https://nasdaqtrader.com/content/productsservices/trading/crosses/openclose_faqs.pdf)
- Official close (NOCP): "The Closing Cross sets the Nasdaq Official Closing Price (NOCP). If a stock does not have a closing cross, the last regular way last-sale eligible trade reported prior to 4:00 p.m. is used." Nasdaq does not guarantee MOC fills. — [Nasdaq FAQ](https://nasdaqtrader.com/content/productsservices/trading/crosses/openclose_faqs.pdf); see also [Nasdaq Rulebook Equity 4](https://listingcenter.nasdaq.com/rulebook/nasdaq/rules/Nasdaq%20Equity%204)
- Rule history (dates matter):
  - Before 2018, MOC/LOC cutoff was 3:50.
  - Approved Oct 2018: MOC/LOC entry until 3:55, and late LOCs until 3:58 with re-pricing. — [Federal Register 2018-10-25](https://www.federalregister.gov/documents/2018/10/25/2018-23277/self-regulatory-organizations-the-nasdaq-stock-market-llc-order-approving-proposed-rule-change-as)
  - About a year later (Nov 2019), Nasdaq froze modify/cancel at 3:50, kept entry open to 3:55, and added the early 3:50 NOII every 10 seconds. RBC: "Clients that require the flexibility to cancel their orders in the last 10 minutes should avoid the Nasdaq close." — [RBC "Nasdaq – Early Look MOC"](https://www.rbccm.com/assets/rbccm/docs/housing-market/Nasdaq_Close.pdf)
- LULD and halt crosses near the close:
  - 2021: Nasdaq stopped extending the LULD Closing Cross past 4:00. If a stock is paused at the close, the cross runs at 4:00 within benchmark prices and unexecuted MOC/LOC/IO orders are cancelled. — [Federal Register 2021-06-03](https://www.federalregister.gov/documents/2021/06/03/2021-11693/self-regulatory-organizations-the-nasdaq-stock-market-llc-notice-of-filing-of-amendment-no-1-and)
  - Approved Feb 2025: halt-cross price protections and a "Hybrid Closing Cross" for trading halts at or after 3:50 p.m. Nasdaq noted MarketWatch's policy of "not scheduling any reopening of a security past 3:30 p.m." — [Federal Register 2025-02-10](https://www.federalregister.gov/documents/2025/02/10/2025-02386/self-regulatory-organizations-the-nasdaq-stock-market-llc-order-granting-approval-of-a-proposed-rule)
- Scale: the cross launched in April 2004. It averages "330 million shares representing $25.6B traded each day" (undated product page). — [Nasdaq Closing Cross page](https://www.nasdaq.com/products/north-american-markets/nasdaq-stock-market/closing-cross)
  - 2019 figure (older): "Almost 10% of Nasdaq's average daily volume occurs in the closing auction." — [Nasdaq Closing Cross FAQ 2019](https://www.nasdaqtrader.com/content/productsservices/Trading/ClosingCrossfaq.pdf)

**Nasdaq Opening Cross**
- NOII starts at 9:25: every 10 seconds from 9:25 to 9:28, then every second from 9:28 to 9:30 with near/far prices.
- MOO orders must be received before 9:28. LOO orders can be entered until 9:29:30, with late LOO re-pricing after 9:28.
- "Market Orders placed after 9:28 a.m. will be held until the market opens and will not participate in the Opening Cross."
- The NOOP is the cross price, or else the first last-sale eligible trade at or after 9:30. — [Nasdaq FAQ](https://nasdaqtrader.com/content/productsservices/trading/crosses/openclose_faqs.pdf)

**Cboe and other venues**
- Cboe Market Close (CMC), live from 6 March 2020:
  - MOC orders are "pre-matched with other MOC orders at 3:49 p.m. ET" (the original approval said 3:35) and executed at the primary market's official close;
  - unmatched shares can be routed to the primary auctions;
  - if no official close arrives by 8:00 p.m., matched shares are cancelled. — [Cboe Market Close page](https://www.cboe.com/us/equities/trading/offerings/cboe_market_close); [Cboe approval release (PR Newswire, Jan 2020)](https://www.prnewswire.com/news-releases/cboe-receives-final-regulatory-approval-for-cboe-market-close-300991321.html)
- Cboe BZX runs closing auctions for its own BZX-listed securities. SR-CboeBZX-2025-086 revised LOC pricing between 3:55 and 3:59, late-LOC pricing, and entry/cancel times for those listings. — [SR-CboeBZX-2025-086](https://cdn.cboe.com/resources/regulation/rule_filings/approved/2025/SR-CboeBZX-2025-086.pdf)
- The SEC approved (July 2026) a BZX rule letting it delay its opening auction "under certain market conditions". — [Federal Register 2026-07-28](https://www.federalregister.gov/documents/2026/07/28/2026-15175/self-regulatory-organizations-cboe-bzx-exchange-inc-notice-of-filing-of-amendment-no-1-and-order)
- TXSE filed in Sept 2026 to run opening and closing auctions in non-listed (UTP) securities "while preserving the primary listing market's official opening and closing prices". The filing notes the SEC has already allowed NYSE Arca to run auctions in designated UTP securities as a resiliency backup. — [SR-TXSE-2026-025](https://www.txse.com/filings/sr-txse-2026-025-proposal-to-offer-opening-and-closing-auctions-in-utp-securities.pdf)
- NYSE Arca Rule 1.1, official closing price: the closing-auction price, if one round lot or more trades; otherwise the most recent consolidated last-sale eligible trade during Core Trading Hours. Contingency hierarchy:
  - inability determined at or before 3:00 p.m.: a designated alternate exchange's official close;
  - after 3:00 p.m.: the "VWAP of the consolidated last-sale eligible prices of the last five minutes of trading". — [NYSE Arca Rule 1.1](https://www.nyse.com/publicdocs/nyse/regulation/nyse-arca/NYSE_Arca_Rule_1.1.pdf)

**Industry closing-auction contingency (all listing exchanges)**
- "If the Exchange determines at or before 3:00 p.m. that it is unable to conduct a Closing Auction… the Exchange will designate an alternate exchange… If… after 3:00 p.m.… the Official Closing Price… will be the VWAP of the consolidated last-sale eligible prices of the last five minutes of trading."
- Joint tests:
  - Nov 4 and Dec 9, 2023 (Cboe BZX, Nasdaq, NYSE, NYSE American, NYSE Arca);
  - Nov 16 and Dec 14, 2024. In the Nov 2024 test, NYSE Arca ran the closing cross for Cboe- and Nasdaq-listed test symbols, and Cboe EDGX routed ROOC orders to Arca;
  - Nov 15 and Dec 13, 2025 (now including NYSE Texas).
  - For BZX, "ARCA is Alternate Exchange".
  - Sources: [Cboe test notice 2023](https://cdn.cboe.com/resources/schedule_update/2023/Cboe-Equities-Contingent-Closing-Auction-Joint-Test.pdf); [Cboe test notice 2024](https://cdn.cboe.com/resources/schedule_update/2024/Cboe-Equities-Contingent-Closing-Auction-Joint-Test.pdf); [Nasdaq ETA 2025-79](https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2025-79); [Nasdaq ETA 2025-98](https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2025-98); [Cboe closing contingency procedures](https://www.cboe.com/document/tech-spec/content/technical-specifications/cboe-titanium-u.s.-equities-auction-process/auction-contingency-plans/closing-contingency-procedures)

**Half-days**
- 2026 early closes at 1:00 p.m.: Friday Nov 27, 2026 and Thursday Dec 24, 2026. — [NYSE hours & calendars](https://www.nyse.com/markets/hours-calendars)

### Inferences
- A decision made at close−3 min (3:57) is too late for MOC on either listing market:
  - NYSE MOC/LOC entry closes at 3:50 (later only to offset a regulatory imbalance);
  - Nasdaq MOC entry closes at 3:55;
  - only Nasdaq late LOC (to 3:58, capped at the 3:50/3:55 reference prices) and floor/offset order types remain after that.
  - To use the auction, a decision has to exist by about 3:49 (see Alpaca's own 3:50 cutoff in §5).
- Because NYSE D-Orders (around 60% of NYSE S&P 500 auction interest) arrive mostly after 3:57:30, the published 3:50–3:57 imbalance is an incomplete guide to the final NYSE print. The final price can move in the last seconds after a close−60 s market order has already filled.
- The contingency rule means that on a failed-auction day the "official close" used for scoring may be a 5-minute VWAP. A market order at close−60 s sits inside that window, so slippage against that benchmark could actually be smaller than on a normal day.

### Gaps
- I could not find an authoritative current document giving NYSE and Nasdaq MOC/LOC cutoffs on 1:00 p.m. half-days. Practitioner usage implies about 12:50 / 12:55, but this is **unverified**.
- I found no evidence of an approved or live Cboe closing auction that sets official closing prices for NYSE- or Nasdaq-listed stocks. CMC is a pre-match at the primary close. If the brief's "Cboe closing auction for NYSE/Nasdaq-listed securities" refers to a 2025–26 proposal, I could not locate it.
- I did not retrieve the current NYSE Rule 7.35B text, so I could not confirm whether NYSE still allows legitimate-error MOC/LOC cancels between 3:50 and 3:58 (the 2021 sheet allows it; the 2024 sheet just says "cannot be modified or canceled").

## 2. Market-structure data: closing-auction share, last-minutes share, passive investing, index-rebalance and expiry days

### Takeaway
The US closing auction grew from about **3% of daily volume in 2010 to about 7.5% in 2018, about 9–10% in 2019–2024, and 12–13% in 2025**. Instinet measured **15.4% in December 2025**, a month with quad witching and index rebalances. About **a third of S&P 500 trading happens in the final 10 minutes** (BestEx, 2024). Rebalance and expiry days push the auction to about 20% of daily volume, or more for index-change names. The academic consensus is that the growth is driven by passive and ETF ownership.

### Cited Findings
- Older figures, flagged:
  - Bogousslavsky & Muravyev (Journal of Financial Markets, 2023): auction volume was 7.48% of daily dollar volume in 2018, up from 3.11% in 2010, about $15.2bn traded daily in 2018.
  - The share of volume from 3:30 to 3:55 fell from 2010 to 2018, so "volume migrates… to the last five minutes".
  - A 1% rise in passive mutual-fund ownership goes with a 3.7% rise in auction turnover but only 0.6% in 3:55–4:00 turnover.
  - Source: [Bogousslavsky & Muravyev, "Who trades at the close?"](https://www.sciencedirect.com/science/article/abs/pii/S1386418123000502)
- Pre-2020, flagged: US closing auctions "reached about 10% of daily volume in 2019… more than tripled from 3% in 2010", citing Jegadeesh & Wu (2022). — [Bender, Clapham & Schwemmlein, EFMA 2023](https://www.efmaefm.org/0EFMAMEETINGS/EFMA%20ANNUAL%20MEETINGS/2023-UK/papers/EFMA%202023_stage-4455_question-Full%20Paper_id-228.pdf)
  - Conflict: France's AMF (Oct 2019) cited a "12%-14% level seen in the United States". The definition is probably different (index constituents or a specific month). — [AMF 2019](https://www.amf-france.org/sites/institutionnel/files/2020-02/growing-importance-of-the-closing-auction-in-share-trading-volumes.pdf)
- 2024 (BMLL, published June 2025):
  - On a typical 2024 day exchanges matched about $50bn in the closing auction, "roughly 9% of total daily trading volume", and about 20% on index-rebalance or option-expiry days.
  - Russell reconstitution day (28 Jun 2024): overall volume was 65% above the June average and final-30-minute volume 220% above it. NYSE traded $275bn and Nasdaq $103bn at the close. For major Russell additions the auction was 34% of daily notional.
  - NYSE Arca ETF auctions are about 2% of ETF volume, against 9% for equities.
  - Source: [BMLL "Into the Close"](https://www.bmlltech.com/news/market-insight/into-the-close-unpacking-u-s-closing-auction-dynamics-and-the-impact-of-the-russell-reconstitution)
- 2018–2025 time series (Instinet data via State Street IM, Jan 2026). US closing-auction share of daily volume, with the open auction about 1% throughout:

  | Period | Close auction | Open auction | Last two hours (ex-auction) |
  |---|---|---|---|
  | Average since Jan 2018 | 8.40% | 0.97% | 37.33% |
  | Average since Jan 2019 | 9.24% | — | — |
  | Trailing 1 year to Dec 2025 | 12.11% | — | — |
  | Q4 2025 | 13.10% | — | 35.11% |
  | December 2025 | 15.39% | 0.93% | 33.85% |

  For comparison, Developed Europe's close was 34.82% in December 2025. — [State Street IM, "Closing time" (Jan 2026)](https://www.ssga.com/us/en/institutional/insights/how-passive-investing-reshaping-microstructure)
- "About a third of all S&P 500 stock trades are now executed in the final 10 minutes of the session, according to data compiled by BestEx Research" (Bloomberg, 29 Apr 2024). BestEx adds that this is "up from 27% in 2021". — [Bloomberg 2024-04-29](https://www.bloomberg.com/news/articles/2024-04-29/stocks-trade-for-390-minutes-a-day-increasingly-only-10-matter); [BestEx Research LinkedIn post](https://www.linkedin.com/posts/bestex-research-group_stocks-trade-for-390-minutes-a-day-increasingly-activity-7190729625159757826-VdEI)
- NYSE closing-auction size:
  - Q1 2026: average 605.5m shares (about $43bn) per day. Record day 20 Mar 2026 (quarterly expiry and index rebalance): 3.57bn shares, $230.5bn.
  - About 18m shares a day (about 3.3% of executed volume) go unfilled for lack of contra liquidity, more than 6.3% in non-Russell-1000 names.
  - Source: NYSE, 8 Apr 2026. — [NYSE "Behind the record volumes"](https://www.nyse.com/research/insights/behind-the-record-volumes-a-hidden-opportunity)
- 2025: "Three of the largest closing auctions in NYSE history occurred in 2025, setting a new single day auction record of over $205BN". — [ICE 2025 records release](https://ir.theice.com/press/news-details/2026/ICE-Announces-2025-Records-Across-Its-Global-Derivative-and-NYSE-Equity--NYSE-Options-Markets/default.aspx)
- Market-wide context for 2025 (Cboe):
  - US equity ADV 17.6bn shares (+44.6% y/y) and ADNV $1.1trn (+43.3%);
  - peak 30.98bn shares on 9 Apr 2025;
  - off-exchange (TRF) 50.6% of consolidated volume. — [Cboe 2025 US Equities Year in Review](https://www.cboe.com/insights/posts/2025-u-s-equities-year-in-review)
- Drivers. State Street IM: index funds and ETFs strike NAV at closing prices, so MOC is "the dominant mechanism for end-of-day execution". Active managers follow because "trading earlier often means crossing wider spreads", which further amplifies MOC volume. Passive AUM passed active AUM in 2024. — [State Street IM](https://www.ssga.com/us/en/institutional/insights/how-passive-investing-reshaping-microstructure)

### Inferences
- For a ~$2.6k order in an S&P 500 name, the auction (around $43bn a day on NYSE alone) and the last 10 minutes of continuous trading are both vastly deep. The account's own price impact is negligible in either venue. The choice between them is about which **benchmark** the fill lands on (official close vs a pre-close quote), not about liquidity.
- Quarterly expiry/rebalance days (third Friday of Mar/Jun/Sep/Dec), the Russell reconstitution (late June) and month-end are when the close moves most relative to the last pre-close quote. A pre-close market order is most likely to diverge from the official close on those days.

### Gaps
- I found no public year-by-year series of closing-auction share restricted to **S&P 500 constituents** for 2020–2025. Instinet/State Street gives all-US shares; BestEx's "third in last 10 minutes" is S&P 500 but a single point.
- Goldman Sachs, JPMorgan, BofA, Bernstein, Virtu and Bloomberg Intelligence close-share reports are client-only. State Street cites a BofA close research refresh (June 2024) that I could not access.

## 3. Broker/TCA and academic research on execution timing and the close (impact, spreads, price pressure and reversal)

### Takeaway
For non-micro-cap stocks, **price impact is lower in the closing auction than in continuous trading, and opening auctions are expensive** (Goyal-Jegadeesh-Wu, JFQA 2026). BestEx finds **the final hour is consistently the cheapest time** to execute a fixed-size order. Closing prices typically sit at the pre-close bid or ask. Auction-driven deviations mostly revert overnight; practitioners such as BestEx describe this as a small liquidity premium. A separate "end-of-day reversal" in the last 30 minutes exists and is attributed to retail and short-seller behaviour.

### Cited Findings
- Goyal, Jegadeesh & Wu (JFQA 2026; draft Dec 2025):
  - "Closing auctions account for about 10% of daily trading volume." Price impact "is lower in closing auctions than in the continuous market for all stocks except Nasdaq micro-caps. Opening auctions are illiquid."
  - Large stocks, price impact at 0.5% / 5% of ADV:

    | Large stocks | Closing auction | Continuous market |
    |---|---|---|
    | NYSE | 3.2 / 10.1 bp | 6.4 / 20.2 bp |
    | Nasdaq | 7.2 / 22.7 bp | 8.3 / 26.3 bp |

  - Closing-auction impact for non-micro-caps is smaller than AQR's real institutional trades (Frazzini et al. 2018).
  - Annualised trading costs for long/short anomaly portfolios placed in the cheaper mechanism are 17–41 bp (9–21 bp excluding micro-caps). — [Cambridge Core (JFQA)](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/price-impact-in-closing-auctions-opening-auctions-and-continuous-markets-a-benchmark-for-cost-of-trading-on-anomalies/0F72910A79C5B42CF6E85F55164CE846); [JFQA preprint PDF](https://jfqa.org/wp-content/uploads/2026/01/25551_Price_Impact.pdf)
- Bogousslavsky & Muravyev (2023):
  - "closing prices typically match pre-close bid or ask prices, and price impact is lower than during continuous trading";
  - "Auction price deviations revert quickly and almost completely, on average";
  - price reversal suggests auction volume is "driven to a significant extent by uninformed trading". — [Journal of Financial Markets 2023](https://www.sciencedirect.com/science/article/abs/pii/S1386418123000502)
- NYSE quantitative research, Part 1 (Choey Li, 22 Aug 2023), Russell 1000 orders of about 2.4% of closing ADV:
  - immediate impact about 0.34× the daily average spread when entered at 15:55–15:56, and about 0.4× at 15:59–16:00;
  - subsequent price drift 0.6–1.7× the daily average spread;
  - "inflection" sizes beyond which impact becomes large and persistent: about 0.47%, 0.86% and 1.18% of closing ADV in the last three minutes. — [NYSE Closing Auction research Part 1](https://nyse.com/data-insights/closing-auction-immediate-market-impact-price-drift-and-transaction-cost-of-trading)
- NYSE Part 2 (17 Oct 2023): auction orders that **offset** the published imbalance earn a gain (positive VWAC) against the reference price at entry. Orders that **join** the imbalance side lose, across the S&P 1500 (average −$0.03 to +$0.01 per minute of entry). — [NYSE Closing Auction research Part 2](https://www.nyse.com/data-insights/closing-auction-immediate-market-impact-price-drift-and-transaction-cost-of-trading-part-2)
- BestEx Research, "The Time of Day Effect" (14 Jul 2025): holding participation rate and order size constant, "executing the same order in the final hour of the trading session is consistently less costly than executing it earlier in the day". The illustration uses Russell 2000 constituents, 1% of daily volume at 15% participation. — [BestEx Time of Day Effect](https://www.bestexresearch.com/insights/the-time-of-day-effect-a-breakthrough-in-trading-cost-optimization)
- BestEx CEO Hitesh Mittal (via Bloomberg, Apr 2024): overnight reversion of closing-auction flow "is part of normal market function". Passive funds may pay fractionally more at the close, but far less ("way, way less") than liquidity providers would charge for that size earlier in the day. — [BestEx LinkedIn summary of Bloomberg piece](https://www.linkedin.com/posts/bestex-research-group_stocks-trade-for-390-minutes-a-day-increasingly-activity-7190729625159757826-VdEI)
- Opposing view, European data: with about one third of volume in the close, there are "significant distortions of the closing price with 23% of the closing auction return being systematically reversed". This is Europe, not the US. — [Bender, Clapham & Schwemmlein, EFMA 2023](https://www.efmaefm.org/0EFMAMEETINGS/EFMA%20ANNUAL%20MEETINGS/2023-UK/papers/EFMA%202023_stage-4455_question-Full%20Paper_id-228.pdf)
- End-of-day reversal (Baltussen, Da & Soebhag, 2024/25): "Individual stocks experience sharp intraday return reversals in the cross-section during the last 30 minutes", mainly "positive price pressure on intraday losers". The authors say it is not explained by liquidity or gamma hedging and is driven by retail attention-buying and short-seller risk management. — [OptionMetrics abstract page](https://optionmetrics.com/research/a-soebhag-g-baltussen-and-z-da-end-of-day-reversal); [Erasmus University news, Jun 2025](https://www.eur.nl/en/news/end-day-reversal-pattern-second-place-quantpedia-awards-2025)
  - Conflict: an Alpha Architect summary attributes the effect to institutional and index flows with next-day reversal, which contradicts the authors' abstract. Prefer the abstract. — [Alpha Architect](https://alphaarchitect.com/end-of-trading)
- State Street IM: "spreads compress sharply in the final minutes compared to the open". On heavy-MOC days the auction can shift from "price-revealing" to "price-forming", and "the closing price can end up materially above or below the last traded price just minutes before the auction". — [State Street IM](https://www.ssga.com/us/en/institutional/insights/how-passive-investing-reshaping-microstructure)

### Inferences
- If the official close usually equals the pre-close bid or ask (Bogousslavsky-Muravyev), a market order at close−60 s pays roughly a half-spread plus any 60-second drift and the auction "jump" against the official close.
  - The signed average should be near zero, because the jump can go either way and the buy/sell mix is balanced.
  - The absolute deviation should be a few bp for liquid large caps.
  - The fund's measured median signed +0.4 bp and median |slippage| 4.4 bp fit this picture. The p90 of 14 bp is plausibly driven by imbalance-heavy days (expiries, rebalances) and late D-Order flow.
- The NYSE work implies that **joining** a heavy imbalance is costly and **offsetting** it pays. A pre-close market order cannot condition on the final imbalance. A strategy that read the 3:50–3:55 imbalance could choose its side relative to it, but only if orders reach the exchange by the cutoffs.

### Gaps
- I found no public, recent (2020–2026) measurement of quoted or effective spreads **minute by minute in the last minutes** for S&P 500 names. The NYSE results are expressed in multiples of "daily average spread" without bp levels.
- I could not retrieve Virtu/ITG, Abel Noser, Goldman, JPM or Morgan Stanley close-timing TCA notes, or Kissell's close-benchmark work: paywalled or client-only.

## 4. What systematic funds and index managers do: decision time, trade time, benchmarks

### Takeaway
Large quant managers such as AQR have generally **formed target portfolios on the prior close and traded the next day with patient algorithms**. They measure implementation shortfall against the decision-time (prior) close and market impact against the start-of-trading price (the open). Index funds trade **at the close via MOC**, because NAV and tracking error are struck on closing prices. "Close-aware" algorithms start in the continuous market before the auction and size into it. The standard benchmarks are arrival or implementation shortfall, VWAP, and close.

### Cited Findings
- AQR, Frazzini, Israel & Moskowitz, "Trading Costs" (2018):
  - Data: $1.7trn of live trades, 21 developed markets, Aug 1998–Jun 2016.
  - "The theoretical price is defined as the closing price at the time the strategy's desired holdings and trades are generated, which is typically the prior day's closing price. The start price is similarly defined as the first recorded price at the time the strategy begins trading… (e.g., current day's opening price)." Trades from long-term signals "are completed 99.9% of the time".
  - Costs: mean market impact 9.97 bp, mean implementation shortfall 11.02 bp (medians 6.18 / 8.63; value-weighted 15.14 / 16.06). Large-cap trades average 8.90 bp of impact against 18.95 bp for small caps.
  - Sources: [Trading Costs PDF (Yale-hosted)](https://spinup-000d1a-wp-offload-media.s3.amazonaws.com/faculty/wp-content/uploads/sites/3/2021/08/Trading-Cost.pdf); [SSRN abstract](https://papers.ssrn.com/abstract=3229719); [AQR page](https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs)
- The 2012 precursor ("Trading Costs of Asset Pricing Anomalies", 1998–2011, about $1trn, 19 markets) uses the same convention: benchmark "prior day's closing price" for implementation shortfall, "current day's opening price" for market impact. — [Trading Costs of Asset Pricing Anomalies (NYU-hosted)](https://pages.stern.nyu.edu/~afrazzin/pdf/Trading%20Cost%20of%20Asset%20Pricing%20Anomalies%20-%20Frazzini,%20Israel%20and%20Moskowitz.pdf)
- How AQR executes (Yale Insights): "Researchers and portfolio managers decide what to trade… but an algorithm decides how to achieve that goal in the cheapest way possible, all monitored by human traders". Moskowitz on patience: "If you have to trade immediately, you're going to pay a high price." — [Yale Insights](https://insights.som.yale.edu/insights/how-big-investors-avoid-market-predators-and-keep-trading-costs-low)
- Goyal-Jegadeesh-Wu note that the institutional samples in Frazzini et al. and similar studies "comprised orders executed only in the continuous market". Their own anomaly cost benchmark assumes trades are "strategically" placed in the cheaper of closing auction or continuous market. — [JFQA 2026](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/price-impact-in-closing-auctions-opening-auctions-and-continuous-markets-a-benchmark-for-cost-of-trading-on-anomalies/0F72910A79C5B42CF6E85F55164CE846)
- Index funds and ETFs: "structurally incentivized to execute trades at the closing auction because official net asset values (NAVs) are calculated using closing prices". Practitioner tactics include "staggering executions into the close using close-aware algorithms", pre-trade analytics and order sizing, and human intervention for less-liquid names. — [State Street IM, Jan 2026](https://www.ssga.com/us/en/institutional/insights/how-passive-investing-reshaping-microstructure)
- How a close algorithm decides when to start (BestEx, described for futures settlement but the same logic as equity close algos): it determines "an appropriate start time based on the order's size relative to expected… window volume", working ahead of the window to limit impact. — [BestEx TASClose article (Apr 2026)](https://www.bestexresearch.com/insights/optimizing-settlement-execution-benefiting-from-trade-at-settlement-tas-liquidity-streamlining-multi-leg-execution)
- Benchmarks in current broker practice. BestEx markets "IS Zero", a low-urgency implementation-shortfall algorithm, measured against VWAP "on Arrival Price Benchmark" (2024–2025). Arrival/IS and VWAP are the standard comparison pair. — [BestEx articles index](https://www.bestexresearch.com/insight/articles)
- Bogousslavsky-Muravyev: active mutual-fund ownership is associated more with pre-auction volume than with auction volume, and passive ownership the reverse. This fits active managers working orders before or into the close and passive managers using the auction. — [Journal of Financial Markets 2023](https://www.sciencedirect.com/science/article/abs/pii/S1386418123000502)

### Inferences
- "Decide at close−3 min, trade at close−60 s, score against the official close" is a hybrid. It is closer to an index fund's close benchmark than to AQR's next-day implementation. Institutional analogues that achieve a close benchmark either (a) commit to MOC by the cutoff or (b) use a close-aware algorithm that starts minutes earlier and sends the residual to the auction.
- With a decision only 3 minutes before the close, (a) is impossible. Option (b) reduces to what the fund already does: pre-close continuous trading.
- A tracking error of a few bp against the close is small next to AQR-scale implementation shortfall (around 10 bp mean). For a ~$100k book trading ~$2.6k orders, the close benchmark is achievable within single-digit bp at the median.

### Gaps
- I found no public description from Two Sigma, Man, Robeco or Research Affiliates of exactly when they generate signals relative to the close (for example using 15:45 data) or of imbalance-aware MOC logic. That information appears to be proprietary.
- I found no public Kissell text online that could be cited for close-benchmark practice.

## 5. Retail/small-account APIs: Alpaca (cls/opg, cutoffs, routing, paper simulation) and Interactive Brokers

### Takeaway
Alpaca's docs say `cls` orders are MOC/LOC routed to the primary exchange's closing auction, and **rejected if submitted after 3:50 p.m.** (up to 7:00 p.m.); `opg` orders are rejected from 9:28 a.m. Alpaca **paper trading does not simulate auctions**. `opg`/`cls` orders fill like market orders at the current NBBO quote. Paper also adds random partial fills ("10% of the time") and ignores displayed size, impact and price improvement. One Alpaca forum reply (June 2026) says MOC is "not generally supported in live trading unless one has chosen the elite smart router". That conflicts with the general docs and needs confirming with Alpaca. IBKR follows exchange cutoffs: NYSE 15:50, Nasdaq MOC 15:55, Nasdaq LOC 15:58.

### Cited Findings

**Alpaca: order rules (live)**
- `cls`: "eligible to execute only in the market closing auction. Any unfilled orders after the close will be cancelled. CLS orders submitted after 3:50pm but before 7:00pm ET will be rejected. CLS orders submitted after 7:00pm will be queued and routed to the following day's closing auction."
- `opg`: "OPG orders submitted after 9:28am but before 7:00pm ET will be rejected."
- "On open/on close orders are routed to the primary exchange. Such orders do not necessarily execute exactly at 9:30am / 4:00pm ET but execute per the exchange's auction rules." — [Alpaca docs: Placing Orders](https://docs.alpaca.markets/us/docs/orders-at-alpaca); [Alpaca docs (alt URL)](https://docs.alpaca.markets/docs/orders-at-alpaca)
- `day` orders are valid 9:30–4:00 by default. "If unfilled after the closing auction, it is automatically canceled." — [Alpaca docs](https://docs.alpaca.markets/docs/orders-at-alpaca)
- Other restrictions:
  - fractional orders support only `day`;
  - extended hours accepts only limit orders with `day`/`gtc`. — [Alpaca docs](https://docs.alpaca.markets/docs/orders-at-alpaca)
- Order handling standards: market and limit orders are "protected on the primary exchange opening print". Retail orders go "to market makers who will route orders on your behalf to the primary market opening auction".
  - Example: a market order entered between 9:28:01 and 9:29:59 on a Nasdaq stock would not get the NOOP, "since Nasdaq has a cutoff of 9:28".
  - The docs describe **no equivalent protection for the closing print** for ordinary market orders. — [Alpaca docs: Placing Orders](https://docs.alpaca.markets/us/docs/orders-at-alpaca)

**Alpaca: Elite Smart Router and DMA Gateway**
- The Elite page lists "MOO / LOO" and "MOC / LOC" under "Premium Order Types" with VWAP, TWAP, IOC and DMA.
  - Elite Smart Router requires a $30,000 deposit (additional benefits at $100,000).
  - Pricing: $0.0040/share all-in, or $0.0025–$0.0005/share tiered.
  - The page does not state explicitly whether MOC/LOC are Elite-only. — [Alpaca Elite](https://alpaca.markets/elite)
- DMA Gateway (launched 21 Aug 2025, Elite only, via DASH Financial Technologies) "only supports market and limit orders and Time in Force (TIF) = day. If you wish to use MOO/MOC… you cannot specify advanced_instructions". `advanced_instructions` "will be accepted for paper trading; however, the order will not be simulated in the paper environment". — [Alpaca docs: DMA Gateway / Advanced Order Types](https://docs.alpaca.markets/us/docs/alpaca-elite-smart-router); [Alpaca blog 2025-08-21](https://alpaca.markets/blog/alpaca-launches-direct-market-access-gateway-and-advanced-order-types-for-elite-smart-router)

**Alpaca: paper-trading simulation**
- From the docs:
  - "all orders submitted in paper trading will be matched against the best available current market price (NBBO)";
  - "they will receive partial fills for a random size 10% of the time";
  - "Your order quantity is not checked against the NBBO quantities".
  - Paper does **not** simulate market impact, information leakage, latency slippage, queue position, price improvement, regulatory fees or dividends (borrow fees "Coming Soon"). — [Alpaca docs: Paper Trading](https://docs.alpaca.markets/docs/paper-trading)
- Alpaca staff (Dan Whitnable) on the forum:
  - paper `opg`/`cls` orders "are simply treated like all other orders… they will get random partial fills… and… fill at the current quote… They do not fill at the open or close price as one would see in actual live trading" (2024);
  - "In paper simulations, fills are at the SIP full market NBBO quote prices (ie buys fill at the ask and sells fill at the bid). In live trading, orders generally fill at the quote prices but sometimes can be a bit better";
  - MOO in paper is "simulated as regular market orders… In live trading MOO orders fill at the listing exchange opening auction price". — [Forum: partial fills on OPG](https://forum.alpaca.markets/t/recently-seeing-partial-fills-on-market-opg-order-s-p500-stocks/13906); [Forum: paid account paper fills](https://forum.alpaca.markets/t/does-a-paid-account-give-more-accurate-paper-market-fills/14303); [Forum: MOO worse than open](https://forum.alpaca.markets/t/market-on-open-order-gives-me-a-worse-price-than-daily-open/14856); [Forum: opening and closing prices in paper](https://forum.alpaca.markets/t/opening-and-closing-market-prices-in-paper-trading/11664)
- Forum thread, June 2026 — paper `cls` symptoms identical to the fund's 2026-10-01 incident:
  - A user submitted `type=market, time_in_force=cls` orders around 15:40. They partially filled at about 19:59:55Z and the remainder went `expired` at 20:00–20:02Z (for example TQQQ 30 of 492, GLD 40 of 71). The same logic on live filled 100%.
  - The reply (author not shown in the extract, consistent with Alpaca staff) said paper treats `cls` "simply like market orders placed at the close… They will not fill at the actual end of day auction price", and that "MOC orders are not generally supported in live trading unless one has chosen the elite smart router order handling".
  - The user's own live MOC orders filling 100% partly contradicts that statement. — [Forum: Paper MOC orders partially fill](https://forum.alpaca.markets/t/paper-moc-orders-partially-fill-remainder-expires-same-setup-on-live-works/19155)
- Older paper complaints (2021): 7 of 45 S&P 500 OPG orders never filled and 5 filled partially, with about $12k per position. — [Forum feature request: Accurate OPG and CLS prices for paper](https://forum.alpaca.markets/t/accurate-opg-and-cls-prices-for-paper-trading/3762)
- Live `cls`/`opg` fill at the listing-exchange auction price. Alpaca's `auctions` market-data endpoint returns auction prints per exchange, with condition codes like "O"/"Q" for the open. — [Forum: OPG orders not filled at open price (live)](https://forum.alpaca.markets/t/opg-orders-not-filled-at-open-price-live-trading/14672)
- Daily-bar "Open"/"Close" from Alpaca and most vendors is derived from consolidated trades, not necessarily the official auction price. "most data providers, including Alpaca, report the 'Open' as simply the first trade of the day". — [Forum: Open/Close in historical trades](https://forum.alpaca.markets/t/open-close-in-historical-trades/8089)
- User claim, unverified: heavy LOO/LOC use led Alpaca to reclassify the account as "professional" and charge $0.004/share. — [Forum: LOC not executed](https://forum.alpaca.markets/t/why-did-my-limit-order-on-close-cls-not-execute/9929)

**Interactive Brokers**
- MOC orders: "All MOC orders must be received at NYSE markets by 15:50 ET, unless entered to offset a published imbalance". NYSE prohibits cancelling or reducing MOC/LOC after 15:50. "Smart routed Limit on close orders are designed to be routed to, and execute on the Primary Listing Exchange." — [IBKR Order Types](https://www.interactivebrokers.com/en/trading/ordertypes.php)
- LOC orders: "must be received at Island [Nasdaq] by 15:58:00… but may not be canceled or modified after 15:50". A separate IBKR lesson says Nasdaq LOC "cannot be cancelled or modified after 3:55 pm ET", and that Nasdaq stops accepting MOC at 3:55 and NYSE at 3:50.
  - These two IBKR pages conflict on the Nasdaq LOC cancel time. Nasdaq's own FAQ says 3:50. — [IBKR Order Types](https://www.interactivebrokers.com/en/trading/ordertypes.php); [IBKR Desktop LOC lesson](https://www.interactivebrokers.com/campus/trading-lessons/ibkr-desktop-limit-on-close); [IBKR Desktop MOC lesson](https://www.interactivebrokers.com/campus/trading-lessons/ibkr-desktop-market-on-close-order)
- Outdated IBKR content (flag): a 15:45 LOC restriction on expiration days, and a staff comment citing a 3:40 NYSE cutoff. Neither matches the current NYSE fact sheets. — [IBKR Order Types](https://www.interactivebrokers.com/en/trading/ordertypes.php); [IBKR LOC lesson comments](https://www.interactivebrokers.com/campus/trading-lessons/ibkr-desktop-limit-on-close)

### Inferences
- Alpaca's single 3:50 `cls` cutoff is stricter than Nasdaq's exchange rules (MOC to 3:55, LOC to 3:58). Even in live trading, a decision formed after 3:50 cannot use `cls` at Alpaca.
- The paper engine fills `cls` against the quote in the final seconds and then expires residuals. That explains the 2026-10-01 pattern: partial fills at 15:59:55–58 and expiries after.
- Paper fills at the NBBO with no impact, so paper slippage is a **lower bound** on live slippage for marketable orders. Live fills "sometimes can be a bit better" (price improvement from wholesalers) but are exposed to real queue and latency.
- For a ~$2.6k order, real displayed size at the inside quote of an S&P 500 name almost always covers the order, so the paper and live gap from size should be small.
- Ordinary Alpaca market orders are routed to market makers. Unlike `cls`, a `day` market order still working at 4:00 p.m. is not described as being sent to the primary closing auction. Unfilled residuals would most likely be cancelled after the close rather than printed at the official close.

### Gaps
- Whether a standard (non-Elite) Alpaca live account can send `cls` orders today is unresolved: the docs imply yes, and a June 2026 forum reply says "not generally supported" without Elite. Ask Alpaca support for a written answer.
- I found no published quantitative comparison of Alpaca paper vs live fills for market orders near the close.
- I did not find Alpaca's current order-routing (Rule 606) venue list or any statement of how market orders received in the final seconds are handled by its wholesalers.

## 6. Risks of market orders in the final minute, and professional fallbacks

### Takeaway
For S&P 500 (Tier 1) names, LULD bands **double to 10% from 3:35 to 4:00 p.m.**, so a single-stock pause in the last minutes needs an extreme move. Market-wide circuit breakers (Levels 1 and 2) **cannot halt trading after 3:25 p.m.**; Level 3 halts for the rest of the day. Real incidents include the NYSE opening-auction failure of 24 Jan 2023 (SEC fined NYSE $9m in March 2026) and the Nasdaq FIX/RASH order-entry issue of 13 Dec 2023. Exchanges have a tested contingency: an alternate exchange runs the close, or a 5-minute VWAP becomes the official close. Professional fallbacks are close-aware algorithms that start earlier, or relying on the contingency close.

### Cited Findings
- LULD:
  - Tier 1 (S&P 500, Russell 1000, some ETPs) uses a 5% band above $3; Tier 2 uses 10%. A "Limit State" not resolved in 15 seconds becomes a 5-minute pause.
  - "Price bands double between 3:35–4:00 p.m. ET for Tier 1 and lower-priced Tier 2 stocks" (FINRA, Nov 2024). — [FINRA "Guardrails for Market Volatility"](https://www.finra.org/investors/insights/guardrails-market-volatility); [LULD Plan site](https://www.luldplan.com)
  - LULD Amendment 18 (effective 24 Feb 2020) removed doubling from 9:30–9:45 for all securities and from 3:35–4:00 for Tier 2 above $3. Tier 1 keeps doubled bands into the close. — [Cboe LULD FAQ (Amendment 18)](https://www.cboe.com/document/tech-spec/document/technical-specifications/cboe-limit-updown-faq)
- Market-wide circuit breakers: an S&P 500 fall of 7% (Level 1) or 13% (Level 2) halts trading for 15 minutes only if it happens before 3:25 p.m. A 20% fall (Level 3) halts for the day at any time. — [FINRA](https://www.finra.org/investors/insights/guardrails-market-volatility)
- Pause at the close on Nasdaq: the LULD Closing Cross runs at 4:00 (no extension since 2021) at a price within benchmarks. Unexecuted MOC/LOC/IO orders are cancelled. For halts at or after 3:50, a "Hybrid Closing Cross" applies (approved 2025). — [Federal Register 2021-06-03](https://www.federalregister.gov/documents/2021/06/03/2021-11693/self-regulatory-organizations-the-nasdaq-stock-market-llc-notice-of-filing-of-amendment-no-1-and); [Federal Register 2025-02-10](https://www.federalregister.gov/documents/2025/02/10/2025-02386/self-regulatory-organizations-the-nasdaq-stock-market-llc-order-granting-approval-of-a-proposed-rule)
- NYSE, 24 Jan 2023:
  - A disaster-recovery system was left running overnight after maintenance. Pillar treated the day as a continuation, sent "zero quotes", and NYSE "failed to run opening auctions for over 2,800 securities" (2,824). This caused LULD pauses in 84 securities.
  - About 4,341 trades in 251 symbols were busted, and NYSE paid over $5.77m to member firms.
  - NYSE "was unaware of the full scope of the issues… for nearly 90 minutes after the opening".
  - The SEC settled charges on 6 Mar 2026 with a $9m penalty. — [SEC administrative proceeding 34-104934](https://www.sec.gov/enforcement-litigation/administrative-proceedings/34-104934-s); [InvestmentNews on $9m penalty](https://www.investmentnews.com/equities/sec-hits-nyse-with-9m-penalty-over-2023-opening-auction-failure/265580); [The Stack](https://www.thestack.technology/nyse-trades-cancelled-disaster-recovery-error); [Reuters 2023-01-24](https://www.reuters.com/markets/us/some-nyse-listed-stocks-briefly-halted-trading-after-market-open-2023-01-24)
- Nasdaq, 13 Dec 2023: an issue with "certain FIX/RASH order entry ports" from about 2:30 p.m. caused inaccurate and delayed execution reports, and some orders were cancelled. The affected ports were closed for the rest of the day. The "closing cross was completed". — [Fortune/Bloomberg 2023-12-13](https://fortune.com/2023/12/13/nasdaq-error-affects-trades)
- NYSE data feed, 12 Aug 2019 (older): a glitch delayed end-of-day values of the Dow and the S&P 500 until late evening. — [WSJ 2019-08-13](https://www.wsj.com/articles/some-stock-prices-delayed-as-glitch-hits-nyse-run-data-feed-11565654989)
- Contingency closing price: an alternate exchange runs the close if the problem is declared at or before 3:00 p.m.; otherwise the official close is the 5-minute VWAP of consolidated last-sale eligible trades. Exchanges run joint tests every November and December. — [Nasdaq ETA 2025-98](https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2025-98); [Cboe closing contingency procedures](https://www.cboe.com/document/tech-spec/content/technical-specifications/cboe-titanium-u.s.-equities-auction-process/auction-contingency-plans/closing-contingency-procedures)
- Lack of liquidity in the auction is real at the margin: about 3.3% of NYSE auction volume goes unfilled, and one auction in seven has at least 5% untapped liquidity (mostly small and mid caps). — [NYSE Apr 2026](https://www.nyse.com/research/insights/behind-the-record-volumes-a-hidden-opportunity)
- Late-session volatility: on rebalance days the close can land "materially above or below the last traded price just minutes before the auction". — [State Street IM](https://www.ssga.com/us/en/institutional/insights/how-passive-investing-reshaping-microstructure)
- Cross-sectional reversals concentrate in the last 30 minutes. — [OptionMetrics / Baltussen-Da-Soebhag](https://optionmetrics.com/research/a-soebhag-g-baltussen-and-z-da-end-of-day-reversal)
- Half-days: 1:00 p.m. closes on 27 Nov 2026 and 24 Dec 2026. A schedule pinned to 4:00 p.m. would miss the session. — [NYSE hours & calendars](https://www.nyse.com/markets/hours-calendars)
- Fallbacks used by professionals:
  - Index managers use "close-aware algorithms" that stagger executions into the close, pre-trade analytics, and "human intervention" for illiquid names. — [State Street IM](https://www.ssga.com/us/en/institutional/insights/how-passive-investing-reshaping-microstructure)
  - Close algorithms choose a start time from order size relative to expected volume in the window. — [BestEx TASClose](https://www.bestexresearch.com/insights/optimizing-settlement-execution-benefiting-from-trade-at-settlement-tas-liquidity-streamlining-multi-leg-execution)
  - NYSE notes floor brokers shifting D-Order entry to the final 10 seconds. — [NYSE Nov 2025](https://www.nyse.com/research/insights/nyse-closing-auction-timing-shifts-and-marketability-trends)

### Inferences
- Main failure modes for an "orders at close−60 s, retry every 10 s until close−10 s" design:
  1. A stock in an LULD pause or halt at 3:59. The order cannot fill in continuous trading, and Alpaca's retail routing does not place `day` market orders into the primary's paused or hybrid closing cross. The result is an unfilled residual, which the design already cancels.
  2. An exchange or broker order-entry outage in the last minute, as in Nasdaq's 13 Dec 2023 FIX issue. No retry window is left.
  3. Half-days, if the schedule is keyed to 16:00.
  4. Rebalance and expiry days, when the official close jumps away from the last quote. These drive the tail (p90) of the slippage distribution, not the median.
- Starting earlier (for example close−5 to close−2 min) widens the retry window and shrinks outage risk. The cost is more drift between fill and close, typically a few bp for large caps based on the 60-second evidence above. That trade-off can be measured on the existing 139 fills by simulating earlier fill times against quotes.

### Gaps
- I found no documented case of a **Nasdaq closing cross** failing or being delayed in 2020–2026. The incidents found involved order entry (Nasdaq, Dec 2023), the NYSE open (Jan 2023) and NYSE data dissemination (2019, before the period).
- I found no statistics on the frequency of LULD pauses in Tier 1 stocks during 3:35–4:00 since the 2020 Amendment 18.
- I found no data on how Alpaca or its wholesalers handle `day` market orders that are still working at 4:00:00. Ask Alpaca.
