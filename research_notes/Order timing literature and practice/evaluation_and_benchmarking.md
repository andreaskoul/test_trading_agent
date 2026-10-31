# Evaluating and benchmarking execution quality and order timing (small, daily-rebalanced US large-cap equity book)

Notation used throughout: `side` = +1 buy, −1 sell; costs in basis points (bp) are positive when the execution hurt the
portfolio. `P_d` = decision price, `P_0` = arrival price (quote midpoint when the order reaches the market), `P_avg` =
average fill, `P_n` = price when the order ends or is cancelled, `P_close` = official closing (auction) price, `S` =
intended shares, `Σs_j` = filled shares.

## 1. Implementation shortfall (Perold; Wagner; Kissell) and its decomposition; computing it with a T−3 min provisional decision price and an official-close benchmark; charging cancelled residuals

### Takeaway
Implementation shortfall (IS) is the return of a "paper" portfolio traded at decision prices minus the return of the
real portfolio. Wagner's expanded form splits it into delay (P_0 − P_d), trading (P_avg − P_0) and opportunity cost
(P_n − P_0 on unfilled shares), plus fees. Perold charges unfilled shares at (P_n − P_d). "Slippage vs the official close"
is a different quantity: IS minus the decision-to-close drift. Both should be reported, and cancelled residuals must be
charged as opportunity cost on the *intended* notional, or failed fills drop out of the cost statistics.

### Cited Findings
- Perold (1988) originally defined IS as "Return/profits on a paper portfolio – Return/profits on actual portfolio". The
  paper and actual portfolios hold the same securities at all times. Trades in the paper portfolio are assumed made at
  benchmark prices; trades in the actual portfolio are made at real market prices. Perold's IS includes explicit costs
  (commissions, taxes), implicit costs (spread/price impact relative to benchmark prices), opportunity costs ("the
  penalty associated with not completing intended trades") and delay ("failure to accomplish the trade immediately").
  As practised today it is "usually computed at the level of the order (not the overall portfolio)." — [Hasbrouck, NYU
  Stern class notes, ch. 8 (2015)](https://pages.stern.nyu.edu/~jhasbrou/Teaching/POST%202015%20Fall/classNotes/STPPTradingCosts.pdf)
- Full citation: Perold, A. F. (1988), "The implementation shortfall: paper vs. reality", *Journal of Portfolio
  Management* 14 (Spring), 4–9. ITG's Mittal: "a portfolio manager looks at the prevailing prices (decision prices)…
  execution prices may be different from the decision prices." — [Mittal (ITG), "Implementation Shortfall – One
  Objective, Many Algorithms"](https://www.cis.upenn.edu/~mkearns/finread/impshort.pdf)
- Formulas, as documented in the open-source `blotter` R package (which cites Kissell's *The Science of Algorithmic
  Trading and Portfolio Management* and Perold 1988) — [braverock/blotter impShortfall.R](https://github.com/braverock/blotter/blob/master/R/impShortfall.R):
  - Complete execution: `IS = S·P_avg − S·P_d + fees`.
  - Perold with opportunity cost: `IS = Σs_j·(P_avg − P_d) + (S − Σs_j)·(P_n − P_d) + fees`; opportunity cost =
    `(S − Σs_j)·(P_n − P_d)`, "the cost of not executing a portion of the originally allocated shares… due to limit price
    constraints or a lack of liquidity."
  - Wagner's expanded IS: `S·(P_0 − P_d) + Σs_j·(P_avg − P_0) + (S − Σs_j)·(P_n − P_0) + fees` = delay + trading +
    opportunity + fees. `P_0` = "price when trading begins (ideally Arrival Price, defined as the mid-price at order
    arrival, alternatively Last Price at order arrival or… first transaction price)"; `P_n` = price at the end of trading.
  - "Market Activity IS" drops the delay term: `Σs_j·(P_avg − P_0) + (S − Σs_j)·(P_n − P_0) + fees`.
- Kissell Research Group's IS framework has four components: fixed cost ("not dependent upon the implementation
  strategy"); delay cost ("the loss in investment value between the time the managers make the investment decision and
  the order releases to the market"); execution cost ("the difference between the execution price and the stock price at
  the time the order releases to the market"); opportunity cost ("the foregone profit or loss resulting from not being
  able to execute the order to completion within the allotted time period"). Exact formulas are not published on the
  page ("contact the Kissell Research Group"). — [MathWorks Datafeed Toolbox, Post-trade analysis metrics definitions](https://www.mathworks.com/help/datafeed/post-trade-analysis-metrics-definitions.html)
- Lineage: Wagner and Edwards (1993, *FAJ*, "Best execution") extended Perold with price impact, timing cost and
  opportunity cost. Kissell (2006, *Journal of Trading*) extended Wagner further. — [American University of Kuwait abstract, "Implementation Shortfall in Transaction Cost Analysis: A Further Extension"](https://mypure.auk.edu.kw/en/publications/implementation-shortfall-in-transaction-cost-analysis-a-further-e)
- Benchmark costs that are *not* IS: an SEC-submitted study defines `Prior Close Cost = Side·(P_E − P_PriorClose)/P`,
  `VWAP Cost = Side·(P_E − VWAP)/P` and `Close Cost = Side·(P_E − P_Close)/P`. It says it does not call its measure IS
  because it "do[es] not consider the opportunity cost of unfilled orders" and excludes explicit costs. — [SEC comment file s72903-14 (mutual-fund trading-cost study)](https://www.sec.gov/files/rules/concept/s72903/s72903-14.pdf)
- Sign and aggregation convention used in a public 2025 TCA: slippage (bp) = (average price − benchmark)/benchmark, with
  the sign flipped for sells so that positive = unfavourable, aggregated across parent orders weighted by notional. A
  "spread-normalised" variant divides by the time-weighted average spread for the symbol that day. — [Proof Trading, "Public-facing TCA: Results for 2025 Data"](https://prooftrading.com/docs/tca-2025-full-year.pdf)
- Opportunity cost captures adverse selection: orders that fail to execute tend to be the ones the market moved away
  from, while the paper portfolio owns both. — [BS Capital Markets, "The Implementation Shortfall: Where Paper Trading Meets Real Trading"](https://www.bscapitalmarkets.com/the-implementation-shortfall-where-paper-trading-meets-real-trading.html)
- Terminology trap: in *pre-trade* ITG usage, "opportunity cost" means timing risk ("the standard deviation of the trading
  cost"), not the post-trade cost of unfilled shares. — [Mittal (ITG)](https://www.cis.upenn.edu/~mkearns/finread/impshort.pdf)
- A "market-adjusted" IS removes the stock's beta-driven market move to isolate trading skill (secondary, educational
  source). — [Ryan O'Connell, CFA, "Implementation Shortfall: Perold Framework"](https://ryanoconnellfinance.com/implementation-shortfall/)

### Inferences
- **Mapping to a T−3 min decision and a T−60 s market order.** Take `P_d` = the provisional price used in the decision
  at T−3 min (best: the NBBO midpoint at that time, not a last trade). Take `P_0` = the NBBO midpoint when the order is
  submitted at T−60 s, and `P_avg` = the fill. Then, per order and in bp of intended notional `S·P_d`:
  - delay = side·(P_0 − P_d)/P_d — the 2-minute drift between deciding and sending;
  - trading = side·(Σs_j/S)·(P_avg − P_0)/P_d — spread paid plus impact plus latency;
  - opportunity = side·((S − Σs_j)/S)·(P_n − P_0)/P_d;
  - plus fees.
- **Relation to slippage vs the close.** `side·(P_avg − P_close)/P_close ≈ IS_filled − side·(P_close − P_d)/P_d`.
  Slippage vs the close therefore equals the IS of the filled part minus the decision-to-close drift.
  - Slippage vs the close measures how closely live trading matches a backtest that fills at the close.
  - IS vs P_d measures the economic cost of implementing the decision.
  - The gap, (P_close − P_d), is zero-mean only if decisions are uncorrelated with the last 3 minutes of price moves.
    Barrier-triggered exits (stop/target) are exactly the case where that may fail, so it is worth reporting separately
    by trigger type.
- **Cancelled or unfilled residuals.**
  - Follow Perold/Wagner: charge `(S − Σs_j)·(P_n − P_d)`, with P_n = the official close of the decision day (the price
    the paper book is marked at).
  - If the residual is re-sent the next day, treat the carried shares as Kissell-style delay against the original P_d
    rather than resetting the benchmark.
  - Express IS on intended, not filled, notional; otherwise a week with 70% fills can show *better* slippage than a fully
    filled week.
  - Report fill rate and opportunity cost next to trading cost. A fill-rate gate (e.g. "≥90% of weeks fully filled") does
    not price the missing fills by itself.
- For a long/short book with a beta hedge, market-adjusted IS (subtracting β·market move over the same interval) removes
  most of the common market drift between T−3 min and the close. That noise is otherwise shared across all fills of the
  day.

### Gaps
- Perold's original 1988 text and Kissell's exact multi-day "revised benchmark" delay formula (Kissell 2006, *J. Trading*)
  were not retrieved from primary sources (paywalled). The formulas above come from the `blotter` documentation, which
  cites Kissell's book.
- Found no published standard specifically for "decision on a provisional pre-close price, benchmarked to the official
  close". The mapping above is derived from the general definitions.

## 2. Benchmark choice: arrival vs VWAP vs close vs decision price; how close-benchmarking hides costs; benchmark gaming; TCA practice and Rule 605/606 metrics

### Takeaway
Pre-trade benchmarks (decision or arrival) cannot be influenced by the trader, but they are noisy. Intraday benchmarks
(VWAP, close) are quieter but can be satisfied mechanically or gamed:
- An order filled in the closing auction has zero slippage to the close by construction, while its impact and the
  auction's implicit spread are still real costs against a pre-trade benchmark.
- Regulatory metrics (SEC Rule 605) measure against the NBBO midpoint at order receipt: effective spread, percentage
  effective spread, E/Q and realized spread. Amended reporting began 1 Aug 2026.

### Cited Findings
- ITG (Nov 2012, "Trading Around the Close"):
  - "suppose instead that traders tried to minimize slippage relative to the closing price rather than to a pre-trade
    benchmark. In this case, submitting large quantities to the closing auction will, by design, have zero slippage, as
    the execution price will always equal the closing price benchmark. But… trading large quantities at the close will
    tend to move prices adversely (following the imbalance publication) and will lead to implicit spread costs in the
    auction itself."
  - For rebalance trades ITG recommends minimising IS "as these are consistent with 'buying low and selling high'".
  - For close-benchmarked flow, a trader "has no upside from trading between 3:45 and 4 PM because the price impact of
    any imbalance has already occurred… Trading during this period would only result in increased spread costs and
    market impact." (2012; NYSE imbalance publication was then 3:45 pm.)
  - [ITG, "Trading Around the Close" (07 Nov 2012), hosted copy](https://ptacts.uspto.gov/ptacts/public-informations/petitions/1519335/download-documents?artifactId=sHrUVQMi0N7XVM_lDc_wXNqYL4jCaW5Y6jb7itY5YOo9-lizK3df2Ew)
- Proof Trading's 2025 public TCA:
  - "We view slippage vs. arrival as an uncorrupted metric, in the sense that our own trading decisions in handling the
    order do not affect the arrival price. However, slippage vs. arrival is notoriously noisy."
  - "The Close algo is exhibiting very little slippage compared to the closing price, which is as designed" (reported as
    ≈1 bp vs close).
  - Its VWAP algo shows slippage vs arrival "closer to 10 bps than to 0 or 20 bps", about 2× the average spread.
  - [Proof Trading, TCA 2025 full year](https://prooftrading.com/docs/tca-2025-full-year.pdf)
- "Multiple evidences from the industry show that VWAP executions are expensive if measured vs. the arrival price" and
  "VWAP can be gamed by aggressively front-loading the order." — [Markov (2019), "Bayesian Trading Cost Analysis and Ranking of Broker Algorithms", arXiv:1904.01566](https://ar5iv.labs.arxiv.org/html/1904.01566)
- VWAP algorithms hit VWAP "even if there are significant stock price moves during the day, either due to market impacts
  of the trading, or due to the stock's volatility". Arrival-price benchmarking exposes impact when trading in size
  quickly. — [Mittal (ITG)](https://www.cis.upenn.edu/~mkearns/finread/impshort.pdf)
- For systematic strategies, arrival price is the natural benchmark "because strategies are backtested under the
  assumption that trades are executed at the price exactly when the trading signal is generated." — [Talos, "Execution Insights Through TCA: Benchmarks and Slippage"](https://www.talos.com/insights/execution-insights-through-transaction-cost-analysis-tca-benchmarks-and-slippage)
- Common equity TCA benchmarks are arrival price, VWAP, the open and the close. — [Northern Trust (2026), "Trade execution benchmarks"](https://www.northerntrust.com/united-kingdom/insights-research/2026/asset-servicing/its/trade-execution-benchmarks)
- The closing print as a benchmark is noisy relative to the quote (Bogousslavsky & Muravyev, NYSE/Nasdaq common stocks,
  2010–2018, i.e. pre-2020 data) —
  [Bogousslavsky & Muravyev, AEA 2021 working paper](https://www.aeaweb.org/conference/2021/preliminary/paper/H9T4hef7);
  [published, *J. Financial Markets* 66 (2023) 100852](https://www.sciencedirect.com/science/article/abs/pii/S1386418123000502):
  - Absolute auction-price deviation from the 4 pm midquote averages 8.12 bp (20.6 bp small stocks, 2.66 bp large stocks).
  - Average half-spread is 7.56 bp and price impact 0.55 bp; for large stocks 1.47 bp and 1.19 bp.
  - The auction price equals the pre-close bid or ask in 68.5% of cases.
  - Deviations are positively skewed: >0.26%, >0.63% and >1.95% on 5%, 1% and 0.1% of stock-days.
  - Large ETFs (SPY, QQQ, sector ETFs) average 3.63 bp, with a 99th percentile of 16.32 bp.
  - Deviations "revert by half shortly after the close and fully overnight".
- **SEC Rule 605 definitions (amended 2024)** — [Federal Register, 89 FR 26428 (15 Apr 2024)](https://www.federalregister.gov/documents/2024/04/15/2024-05556/disclosure-of-order-execution-information);
  [SEC press release 2024-32](https://www.sec.gov/news/press-release/2024-32):
  - Average effective spread (Rule 600(b)(8)): share-weighted average of `2·(P_exec − midpoint_NBBO at order receipt)`
    for buys and `2·(midpoint − P_exec)` for sells. Midpoint-or-better limit orders are measured from when they become
    executable.
  - New "average percentage effective spread" = effective spread ÷ midpoint.
  - New metrics: E/Q (average effective ÷ average quoted spread), size-improvement statistics, and price improvement
    relative to the best displayed price including odd lots.
  - Realized spreads are reported at horizons from under 100 µs to 5 minutes.
- Rule 605 amendments: effective 14 Jun 2024. The compliance date was moved from 14 Dec 2025 to **1 Aug 2026**. A further
  SEC exemptive order (1 Apr 2026) modified related exemptions. — [SEC Release 34-104147](https://www.sec.gov/rules-regulations/2025/09/disclosure-order-execution-information);
  [SEC Release 34-105136](https://www.sec.gov/files/rules/exorders/2026/34-105136.pdf)

### Inferences
- For a book whose backtest fills at the close, report three numbers per fill:
  - IS vs decision price — economic cost;
  - slippage vs arrival midpoint — what the order handling controls;
  - slippage vs official close — backtest fidelity.
- A low close-slippage figure alone shows only that live trading matches the backtest's fill assumption. It does not show
  that execution is cheap relative to the decision.
- Close-benchmark noise for large caps is of the same order as the costs being measured: average |close − 4 pm mid| ≈
  2.7 bp, with occasional tails of tens of bp. A T−60 s continuous-market order adds about one minute of price drift on
  top. A median |slippage| of a few bp against the close is therefore largely benchmark noise, not cost. The signed mean,
  not the absolute value, is what estimates cost.
- **Rule 605-style self-measurement.** For each fill, compute
  - effective spread = 2·side·(P_fill − mid at submission);
  - E/Q = effective spread ÷ quoted spread at submission;
  - realized spread at +1 min and at the close (the close horizon gives "slippage vs close" a microstructure
    interpretation).
  These separate spread paid from post-trade drift.
- **Benchmark gaming in a self-run fund.** The main risk is choosing or changing the benchmark after seeing outcomes. TCA
  benchmarks belong in the pre-registration, with their exact timestamps (decision snapshot, submission, close).
- Rule 606 (order-routing disclosure) was not researched in depth here. Rule 605 is the execution-quality report.

### Gaps
- Abel Noser, Virtu (ITG's successor) and BestEx Research TCA guides were not retrieved directly. Practitioner claims about
  close-benchmark gaming here rely on ITG (2012), Proof (2025) and Markov (2019).
- FINRA/SEC Rule 606 specifics were not retrieved.

## 3. Paper vs live: broker paper-engine differences (Alpaca, IBKR), evidence on paper-to-live gaps, live costs for small orders in S&P 500 names (effective spreads 2023–2026; last-minute spreads)

### Takeaway
Broker paper engines fill marketable orders at the current NBBO bid or ask. They do not simulate impact, latency
slippage, queue position, price improvement, fees or the closing auction:
- Alpaca paper MOC/MOO orders fill like market orders at the quote, not at the auction price.
- IBKR states its simulated fills are "in no way… indicative" of live fills.

For ~$2.6k orders in S&P 500 names, live cost is dominated by half the effective spread. Recent quoted spreads are about
1 bp for the largest names, ~2.5 bp for the top 10, ~3.7 bp for the top 100 and ~4.5 bp across the S&P 500; spreads are
narrowest near the close. Price improvement can push effective spreads below quoted. No study quantifying
paper-to-live slippage gaps was found.

### Cited Findings
- **Alpaca paper trading** — [Alpaca docs, "Paper Trading" (updated 2026-07-07)](https://docs.alpaca.markets/docs/paper-trading):
  - Orders are "matched against the best available current market price (NBBO)".
  - "When orders are eligible to be filled, they will receive partial fills for a random size 10% of the time."
  - "Your order quantity is not checked against the NBBO quantities… you can… receive a fill for an order that is much
    larger than the actual available liquidity."
  - Not simulated: market impact, information leakage, "price slippage due to latency", queue position (non-marketable
    limits), price improvement, regulatory fees, dividends.
  - "even small amounts of real money can often provide insight into issues not seen in a simulation environment."
- **Alpaca auctions in paper** (staff, Jan 2023): paper fills market orders "at the current quote. Buy orders are filled
  at the ask price while Sell orders fill at bid price". MOO/MOC are not differentiated: "paper trading doesn't simulate
  those types of orders well… That is just a limitation of paper trading." — [Alpaca forum, "Opening and closing market prices in paper trading"](https://forum.alpaca.markets/t/opening-and-closing-market-prices-in-paper-trading/11664)
- **Alpaca paper MOC** (staff, Jun 2026): "Paper trading treats these simply like market orders placed at the close. They
  will fill at the current bid exactly like any other market order. They will not fill at the actual end of day auction
  price." Paper accounts introduce partial fills more often than live. The user reported the same live MOC orders filled
  100%. — [Alpaca forum, "Paper MOC orders partially fill…"](https://forum.alpaca.markets/t/paper-moc-orders-partially-fill-remainder-expires-same-setup-on-live-works/19155)
- **IBKR paper trading** — [IBKR Knowledge Base art. 252 (updated 11 Nov 2024)](https://www.ibkr.info/article/252):
  - "A paper trading account is a simulated account trading in a simulated market… We are simulating not only the
    trader's functionality and the market, but also the role of the exchange… While these fills may or may not be within
    the bounds of the live market at the time, in no way is it indicative of what would happen in the real market."
  - Search-engine summaries of IBKR's glossary page (HTTP 403, *not verified directly*) state that IBKR paper does not
    support VWAP, Auction, RFQ and Pegged-to-Market orders, simulates fills from the top of book, and rejects the remainder
    of a partially executed exchange-directed market order. — [IBKR Campus glossary (unverified)](https://www.interactivebrokers.com/campus/wp-json/wp/v2/glossary-terms/179994)
- **S&P 500 spreads, 2024** — [Nasdaq (Phil Mackintosh), "Sampling the S&P 500 to Minimize Spreads", 30 May 2024](https://www.nasdaq.com/articles/sampling-sp-500-minimize-spreads):
  - MSFT and AAPL are around 1 bp.
  - The 10 largest stocks give a portfolio spread close to 2.5 bp; the 100 largest about 3.7 bp; the whole S&P 500 "just
    over 4.5 bps".
  - TSLA stands out as wider.
  - Separately, S&P 500 futures spreads are ~1 bp versus >4 bp for the stock portfolio. — [Nasdaq, "Looking for Futures Arbitrage in the Stock Tape"](https://www.nasdaq.com/articles/looking-futures-arbitrage-stock-tape)
- **Intraday spread pattern (Cboe):** using the average bp spread by minute for all S&P 500 names, "Spreads throughout the
  day are downward sloping and are typically widest at the open… continue to decrease until the close. However, there is
  usually a small increase in spreads at 3:50 p.m." Transactions per second rise 50–75% at 3:50 pm, and the end-of-day
  spike coincides with "the narrowest quoted spreads of the day". — [Cboe Insights, "The Impact Closing Auctions Have on Volumes"](https://www.cboe.com/insights/posts/the-impact-closing-auctions-have-on-volumes)
- **Older evidence (1990s–2000s, flagged):** intraday spread patterns differed by market structure. Nasdaq spreads
  narrowed near the close, while NYSE specialist spreads were U-shaped; time-of-day cost differences were up to ~3 bp. —
  [HKUST, "Market Structure and the Intraday Pattern of Bid-Ask Spreads for NASDAQ Securities"](https://researchportal.hkust.edu.hk/en/publications/market-structure-and-the-intraday-pattern-of-bid-ask-spreads-for-/)
- **Effective vs quoted for retail-size orders** (*unverified*: search-engine snippet only; the Citadel Securities PDF
  returned HTTP 403): for S&P 500 stocks, market orders under $250 notional in Aug 2026 showed an average effective spread
  of 0.0157% (1.6 bp) against an average quoted spread of 0.0718%. — [Citadel Securities execution-quality summary, Aug 2026 (unverified)](https://www.citadelsecurities.com/wp-content/uploads/sites/2/2026/09/CDRG202608.pdf)
- **Institutional live costs (AQR, Frazzini–Israel–Moskowitz "Trading Costs")** — [SSRN 3229719](https://papers.ssrn.com/abstract=3229719);
  numbers as summarised by [Swedroe, ETF.com](https://www.etf.com/sections/index-investor-corner/swedroe-trading-cost-truths):
  - Sample: $1.7 trn of live trades, Aug 1998–Jun 2016, 21 developed markets, ~10,000 stocks.
  - Average bid-ask spread at order arrival 21.33 bp (global, including small caps).
  - Market impact: mean "just under 9 bps", median "just more than 6 bps", value-weighted mean "just more than 15 bps".
  - About 85% of impact is permanent; only 1.26 bp reverses within 24 h.
  - Caveat: pre-2020 sample and institutional-size orders.
- The closing auction matches large volume cheaply: "closing prices typically match pre-close bid or ask prices, and price
  impact is lower than during continuous trading." — [Bogousslavsky & Muravyev, JFM 2023](https://www.sciencedirect.com/science/article/abs/pii/S1386418123000502).
  A JFQA paper likewise finds price-impact trading costs "significantly smaller" in closing auctions than in continuous
  markets. — [SSRN 4300417, "Price Impact: Continuous Trading, Closing Auctions, and Opening Auctions"](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID4300417_code2427035.pdf?abstractid=4300417&mirid=1);
  [JFQA version](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/price-impact-in-closing-auctions-opening-auctions-and-continuous-markets-a-benchmark-for-cost-of-trading-on-anomalies/0F72910A79C5B42CF6E85F55164CE846)

### Inferences
- **What paper misses, and in which direction.** A marketable order sent at T−60 s is filled in paper at the NBBO side at
  receipt. Live, the same order would face:
  - latency slippage — not simulated, could be either sign, but adverse on average when quotes are moving;
  - possible price improvement — not simulated, favourable;
  - regulatory fees on sells — not simulated;
  - SmartRouter or venue effects.
  Market impact for a $2.6k order in an S&P 500 name is negligible relative to depth.
- **Net expectation.** Paper vs-close slippage for small large-cap orders is probably a reasonable, perhaps slightly
  conservative, estimate of live spread cost. It is *not* a test of auction or MOC behaviour, latency or partial-fill
  handling. A small live pilot is the only direct test, as Alpaca itself suggests.
- **Live cost estimate for small orders.** Expected signed cost vs the 4 pm midpoint ≈ half the effective spread:
  - ~0.5–1.5 bp for mega-caps;
  - ~2 bp across the top 100;
  - a few bp for the least liquid S&P 500 names (using Nasdaq's 2024 quoted figures; effective spreads are typically at
    or below quoted for small marketable orders).
  On top of this comes the T−60 s → close drift, which is zero-mean but noisy. A 5 bp per side assumption is above this
  central estimate for most S&P 500 names.
- After the MOC/LOC cutoffs (see section 6), a T−60 s order is necessarily a continuous-market order, not an auction
  order. Paper and live then use the same mechanism, apart from latency, price improvement and partial fills.

### Gaps
- Found no academic or practitioner study that measures paper-vs-live slippage gaps for Alpaca or IBKR.
- Could not verify current (2025–2026) *effective* spreads (as opposed to quoted) for S&P 500 names from a primary source;
  the Citadel 605 summary was blocked.
- No primary source found quantifying spreads specifically in the last 60 seconds before 4:00 pm in 2023–2026. Cboe
  reports the minute-by-minute shape but the excerpt gives no bp values.
- IBKR's paper-trading order-type limitations could not be verified from a primary page.

## 4. Statistical power: fills/days needed to detect 1–5 bp cost differences given ~10 bp per-fill dispersion; testing whether 5 bp/side is conservative; median vs notional-weighted mean

### Takeaway
Practitioners call arrival-based slippage "notoriously noisy" and "unstable" at modest sample sizes. Cost distributions
are skewed and fat-tailed, and mean, median and value-weighted mean can differ by 2.5×.

With per-fill σ ≈ 8–10 bp:
- testing whether mean cost is below 5 bp/side needs only tens of fills;
- detecting a 2 bp difference needs about 200 independent fills (one-sample) or about 400 per arm (two-sample);
- detecting 1 bp needs 800–1,600.

Because P&L adds up in means, test the signed, notional-weighted mean cost, not the median of |slippage|.

### Cited Findings
- "slippage vs. arrival is notoriously noisy." On metric stability: "For our current sample sizes and usage patterns,
  most of these metrics remain unstable." Proof reports results rounded to coarse bins ("nearest 10 bps", "nearest
  2∗spread") or as "unstable". — [Proof Trading TCA 2025](https://prooftrading.com/docs/tca-2025-full-year.pdf)
- "The mean implementation shortfall is small relative to the variance". Distributions are fat-tailed and skewed, and
  sample sizes shrink quickly when slicing by algorithm. Markov recommends hierarchical, partially pooled Bayesian models
  with asymmetric-Laplace likelihoods over MLE. — [Markov (2019), arXiv:1904.01566](https://ar5iv.labs.arxiv.org/html/1904.01566)
- In AQR's live data, the statistic changes the answer: impact mean ≈ 9 bp, median ≈ 6 bp, value-weighted mean ≈ 15 bp
  ("trading costs are positively skewed by more expensive trades"). — [Swedroe/ETF.com summary of Frazzini–Israel–Moskowitz](https://www.etf.com/sections/index-investor-corner/swedroe-trading-cost-truths)
- Closing-price deviations are positively skewed: usually near the midquote, occasionally deviating by tens of bp. —
  [Bogousslavsky & Muravyev (AEA 2021 version)](https://www.aeaweb.org/conference/2021/preliminary/paper/H9T4hef7)
- Notional-weighted aggregation is standard in a public broker TCA. — [Proof Trading TCA 2025](https://prooftrading.com/docs/tca-2025-full-year.pdf)

### Inferences
All formulas are standard; the inputs are illustrative.
- **Back out σ from reported quantiles.**
  - If per-fill slippage were normal: σ ≈ median|x| / 0.674 and σ ≈ p90|x| / 1.645. With median|x| = 4.4 bp and
    p90|x| = 14 bp these give σ ≈ 6.5 bp and σ ≈ 8.5 bp. The mismatch indicates fat tails.
  - Use σ ≈ 8–10 bp, or better, the bootstrap SE.
  - Standard error of the mean with n = 139: σ/√n ≈ 0.7–0.85 bp, so a 95% CI is about ±1.4–1.7 bp *if fills are
    independent*.
- **Clustering by day.** Fills on the same day share the T−60 s → close market move and the closing-auction drift. With m
  fills per day and intra-day correlation ρ, the effective sample is n / (1 + (m − 1)ρ). For a long/short book the common
  market term partly cancels between buys and sells. Use a day-block bootstrap, or cluster-robust SEs by day.
- **Is 5 bp/side conservative?**
  - Test H0: mean signed cost per side ≥ 5 bp against H1: < 5 bp, using the notional-weighted mean of
    side·(P_fill − P_close)/P_close (or of IS vs decision price).
  - Reject when the one-sided 95% upper bound, mean + 1.645·SE, falls below 5 bp.
  - With a mean near 0–1 bp and SE ≈ 0.8 bp, the upper bound is about 1.5–2.5 bp, so 5 bp is clearly conservative
    *relative to the close, in paper*.
  - Sample needed when the true cost is c: n ≈ ((z_α + z_β)·σ / (5 − c))². For c = 2 bp, σ = 10 bp, α = 5% one-sided,
    80% power: n ≈ (2.49 × 10 / 3)² ≈ 69 fills.
  - Report |slippage| separately as a dispersion/risk metric; it is not a cost.
- **Detecting a cost difference δ** (e.g. paper vs live, or two execution times), at 80% power and α = 5% two-sided:
  - One-sample (a paired difference per fill, or a mean vs a fixed value): n ≈ (2.8·σ/δ)². With σ = 10 bp this gives
    δ = 5 → 31, δ = 2 → 196, δ = 1 → 784.
  - Two independent samples: double each figure per arm.
  - Inflate further by the day-clustering design effect.
- **Robust statistics.**
  - Median and Hodges–Lehmann estimators are robust but estimate the "typical" fill. Expected P&L drag is the
    notional-weighted mean, which tails dominate.
  - Report median, 10% trimmed mean, notional-weighted mean and bootstrap CIs together. Treat a large gap between them as
    a signal of tail events (halts, wide-spread names, partial fills) that need individual inspection.
  - Spread-normalised slippage (cost ÷ quoted spread at submission), as Proof uses, reduces cross-sectional
    heteroskedasticity and raises power.

### Gaps
- Found no published TCA source giving explicit sample-size tables for small-order equity TCA. The figures above are
  derived from textbook power formulas, not cited from a study.
- Intra-day correlation of close-slippage across fills is not documented in the sources found.

## 5. Timing luck: rebalance timing luck (Hoffstein, Sibears & Faber; Newfound), dispersion from choosing the close vs other times, measuring a 1-day signal-delay cost with paired shadow books, and the sample length needed

### Takeaway
Rebalance timing luck is the dispersion between otherwise identical portfolios that differ only in when they trade. It
is large: often >100 bp/yr for concentrated, high-turnover strategies, and it does not mean-revert. It grows with
turnover and with how different the holdings could be, and shrinks with rebalance frequency. Paired shadow books
(entering at prior close vs next open vs actual) are the right design for measuring delay cost. Inference needs the
daily *difference* series, with autocorrelation-robust SEs, and typically years of data to resolve 1–2 bp/day effects.

### Cited Findings
- **Newfound (Aug 2013):** 21 copies of a 10-month moving-average SPY strategy, each rebalancing every 21 trading days and
  offset by one day (signals executed at next open, no costs).
  - Total returns ranged from 462.89% to 717.14%.
  - Moving the rebalance from day 19 to day 20 changed max drawdown from 19.03% to 30.22% and annualised return from
    11.33% to 10.51%.
  - Tranching 1/21 of capital per day gave 10.98% annualised with the 19.03% max drawdown and nearly identical turnover.
  - [Newfound, "The Luck of the Rebalance Timing"](https://blog.thinknewfound.com/2013/08/the-luck-of-the-rebalance-timing/)
- **Hoffstein, Sibears & Faber (Oct 2018), "Rebalance Timing Luck: The Difference Between Hired and Fired":** timing luck
  is "the standard deviation in returns between identically managed investment portfolios that are rebalanced on
  different dates (sub-indexes)". —
  [pm-research abstract](https://www.pm-research.com/highwire_display/entity_view/node/18572/content_tabs);
  [Newfound research page](https://www.thinknewfound.com/rebalance-timing-luck);
  [CXO Advisory summary](https://www.cxoadvisory.com/calendar-effects/rebalance-timing-noise/)
  - Ex ante expected returns of the sub-indexes are identical; realised differences "are not expected to mean-revert".
    Equal-weighting the sub-indexes minimises the effect.
  - Example: a 60/40 portfolio rebalanced annually, 1922–2018, returned 8.27% (October rebalance) vs 8.49% (May), more
    than 20% difference in terminal wealth; 0.36% standard deviation of 12-month rolling returns across the 12 monthly
    variants.
- **Hoffstein, Faber & Braun (2020), "Rebalance Timing Luck: The (Dumb) Luck of Smart Beta":**
  - Factor indices show timing luck "often exceeding 100 basis points annualized".
  - Timing luck L depends on T (turnover), F (rebalances per year) and S ("the volatility of a long/short portfolio that
    captures the difference of what a strategy is currently invested in versus what it could be invested in"). Higher
    turnover means more luck, more frequent rebalancing less, and a less constrained universe more.
  - 100-stock portfolios rebalanced semi-annually show timing luck of 1–4%/yr.
  - The 95% CI for dispersion between two identically managed books is ±2·√2·L. Examples: a 100-stock momentum book
    rebalanced semi-annually (L = 4.4%) gives ±12.4%; a 400-stock quarterly low-vol book (L = 0.5%) gives ±1.4%.
  - Replicated S&P 500 style indices (2000–2019) show best-to-worst schedule spreads of 100, 192, 25 and 106 bp/yr.
  - [SSRN 3673910](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3673910);
    [Newfound blog, "The Dumb (Timing) Luck of Smart Beta"](https://blog.thinknewfound.com/2019/11/the-dumb-timing-luck-of-smart-beta/);
    [Panoptica summary](https://www.panoptica.com/rebalance-timing-luck-the-dumb-timing-luck-of-smart-beta-by-hoffstein-faber-and-braun)
- An annually rebalanced S&P 500 systematic value portfolio returned between 9.6% and 12.2% annualised depending only on
  the rebalance month. — [Newfound (Jul 2019), "Timing Luck and Systematic Value"](https://blog.thinknewfound.com/2019/07/timing-luck-and-systematic-value/)
- Option-based strategies: three-month put-spread collars differing only in roll schedule show annualised tracking error
  above 400 bp between implementations. — [Newfound research page](https://www.thinknewfound.com/rebalance-timing-luck)
- **Confounders for close vs next-open comparisons.**
  - Closing-auction deviations revert by half shortly after the close and fully overnight, so a "next open" entry
    mechanically differs from a "close" entry by the closing-print noise. — [Bogousslavsky & Muravyev](https://www.aeaweb.org/conference/2021/preliminary/paper/H9T4hef7)
  - Overnight and intraday index returns differ systematically (the "overnight drift" literature). — [Boyarchenko, Larsen & Whelan, NY Fed Staff Report 917](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf)

### Inferences
- With daily rebalancing (F ≈ 252), *rebalance-date* luck is small. The analogous risk is *intraday execution-time* luck:
  which minute or auction is used. Its magnitude is set by turnover × the volatility of the traded names over the delay
  window.
- **Paired shadow books** (identical decisions; entry at prior close, actual close−60 s, next open, next close) are
  Hoffstein's "sub-indexes":
  - delay cost = mean of the daily return differences D_t = R_actual,t − R_delayed,t;
  - timing luck = std(D_t).
  - Estimate the mean with Newey–West or a block bootstrap, because overlapping holdings make D_t autocorrelated.
- **Sample length.** Days needed N ≈ ((z_{α/2} + z_β)·σ_D / δ)².
  - Illustrative only: if σ_D = 20 bp/day of NAV and the true delay cost is δ = 2 bp/day, N ≈ (2.8 × 10)² ≈ 784 trading
    days, about 3 years.
  - With δ = 5 bp/day, N ≈ 125 days.
  - Because σ_D scales with daily turnover, a low-turnover book has small σ_D but also small δ; the ratio δ/σ_D (≈ per-day
    information ratio of the delay) is what matters.
  - A one-day delay of a news signal can have a large δ in the first days after news (alpha decay). Conditioning D_t on
    new-entry days rather than all days raises power.
- **Decompose a next-open shadow** into:
  - (a) the overnight return on the new trades;
  - (b) open-auction vs close-auction spread and impact;
  - (c) closing-print reversal.
  Only (a) is "signal delay"; (b) and (c) are microstructure effects of a few bp each for large caps.

### Gaps
- The exact algebraic form of the Hoffstein timing-luck approximation (L as a function of T, F, S) is shown as an image in
  the Newfound posts and was not retrieved as text. Only the variables and qualitative dependence are confirmed.
- Found no published study that measures 1-day signal-delay costs for news-driven daily equity books with paired shadow
  portfolios and reports the sample length needed.

## 6. Decision-on-provisional-price error: pre-close prices (15:45, 15:57) as close proxies; how often threshold decisions flip; how practitioners handle the "look-ahead at the close"

### Takeaway
US closing mechanics force any decision that wants to trade *at* the official close to be made on pre-close information:
- NYSE MOC cutoff is 3:50 pm. Nasdaq stops accepting MOC orders at 3:55 pm and LOC at 3:58 pm, with imbalance data from
  3:50 pm.
- The indicative close and the midpoint converge in roughly the last 2–3 minutes.
- The official close then deviates from the 4 pm midpoint by ~2.7 bp on average for large stocks, with fat tails.

Found no literature that measures how often threshold decisions flip between a pre-close proxy and the close; it must be
measured directly. Backtests that both compute the signal on the close and fill at the same close contain look-ahead,
unless the backtest models a pre-close decision snapshot.

### Cited Findings
- **Nasdaq Closing Cross timetable:** MOC, LOC and Imbalance-Only orders are accepted before 3:50 pm. At 3:50 pm early
  dissemination begins; orders are still accepted but "may not be canceled or modified". At 3:55 pm Nasdaq "stops
  accepting MOC orders". LOC orders are accepted until 3:58 pm and IO orders until 4:00 pm. NOII is disseminated every
  10 s from 3:50 to 3:55. At 4:00 pm the cross sets the Nasdaq Official Closing Price at the price that maximises matched
  shares. — [Nasdaq Closing Cross FAQ](https://www.nasdaqtrader.com/content/productsservices/Trading/ClosingCrossfaq.pdf)
- **NYSE:** MOC orders must be submitted by about 3:50 pm ET (secondary sources). — [Stockember](https://www.stockember.com/learn/market-on-close-order);
  [Tickeron](https://tickeron.com/trading-investing-101/what-is-a-market-on-close-order).
  NYSE disseminated closing information from 3:45 pm until it switched to 3:50 pm on 1 Apr 2019. Nasdaq used 3:50 pm,
  except 3:55 pm between 29 Oct 2018 and 15 Apr 2019. — [JFQA, "Price Impact in Closing Auctions…" footnotes](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/price-impact-in-closing-auctions-opening-auctions-and-continuous-markets-a-benchmark-for-cost-of-trading-on-anomalies/0F72910A79C5B42CF6E85F55164CE846).
  The same paper's figures show price impact near zero until imbalance dissemination, a jump right after it, and a
  terminal spike at 4:00 for micro-caps.
- **Convergence into the close (BMLL, Russell reconstitution 2024):** "On Nasdaq, we observe clear price convergence
  between 3:57 and 3:58. In the final minute, the indicative closing price and midpoint converge… On NYSE… more volatility
  and the final price convergence appears to be slower." In 2024 the closing auction averaged ~$50 bn/day, about 9% of
  daily volume, and about 20% on rebalance or expiry days. — [BMLL, "Into the Close"](https://www.bmlltech.com/news/market-insight/into-the-close-unpacking-u-s-closing-auction-dynamics-and-the-impact-of-the-russell-reconstitution)
- **Last-minutes volume and timing:**
  - 3:55–4:00 pm accounts for 6.96% of daily volume, versus 10.90% for 3:30–3:55 pm.
  - The median time between the close of continuous trading and the auction print is 7 seconds.
  - The jump from 4 pm midquote to auction price averages 2.66 bp for large stocks and 3.63 bp for large ETFs (99th
    percentile 16.32 bp), on 2010–2018 data.
  - [Bogousslavsky & Muravyev (AEA 2021 version)](https://www.aeaweb.org/conference/2021/preliminary/paper/H9T4hef7)
- **Backtest engines:** QuantConnect LEAN fills `MarketOnCloseOrder` at "the official closing auction price" and warns
  "You won't know the fill price of the order until after the market closes." — [QuantConnect docs, Market On Close Orders](https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/order-types/market-on-close-orders)
- **Practitioner guidance on close look-ahead:**
  - "Unless an intrabar model supplies information available before the close, a signal using a bar's closing value
    cannot also receive that same closing price as an instantaneous fill." — [BotSpot](https://botspot.trade/guides/look-ahead-bias-and-data-leakage)
  - "Buying at the exact close may also be optimistic unless the process explains how the decision and order could occur
    at that price… write down five timestamps: when the raw data became available, when the derived value could be
    calculated, when the signal became final, when the order could be submitted, and the earliest plausible execution."
    — [TradeLab](https://trytradelab.com/blog/look-ahead-bias-backtesting)
  - Using today's close is not automatically look-ahead; it is if the trade is assumed before the close is known. "A
    realistic backtest would either execute using a market-on-close order or enter the trade on the next available bar."
    — [Algorier](https://algorier.com/blog/look-ahead-bias-in-backtesting)
  - The classic form of look-ahead is "a signal from a bar's close that trades at that same close". — [ABC Trading Group](https://www.abctradinggroup.com/look-ahead-bias)
  - A worked backtest shows trading at the same day's close outperforms trading at the next open. — [TEJ](https://www.tejwin.com/en/insight/what-is-the-look-ahead-bias)

### Inferences
- **A simple flip model.** Let X = (proxy-based signal − threshold) at T−3 min and Δ = the change in the signal from T−3
  min to the official close. The decision flips when sign(X) ≠ sign(X + Δ). For small Δ: P(flip) ≈ f_X(0)·E|Δ|, where
  f_X(0) is the density of X at the threshold.
  - Barrier rules on residual returns have most of their mass far from the barrier on most days, so flips are rare but
    concentrated on days when a name sits near its stop or target.
  - E|Δ| for a large-cap residual over 3 minutes ≈ daily residual σ × √(3/390), plus closing-print noise (~2–3 bp).
  - This should be *measured*: log for every day and name the decision under the provisional price and under the official
    close. Report the flip rate and the P&L of flipped decisions.
- **Backtest consistency.** If live decisions use T−3 min prices but backtests and shadow books decide *and* fill on the
  official close, the backtest has a small look-ahead advantage: it knows the last 3 minutes and the closing print when
  deciding. Two ways to remove it:
  - (a) Decide in backtests on a pre-close snapshot (a 15:57 bar) and fill at the official close, which mirrors live.
  - (b) Decide on close t and fill at the close (or open) of t+1. This is the delayed shadow.
  The difference between (a) and a decide-on-close backtest estimates the look-ahead bias directly.
- **No MOC or LOC is possible at T−60 s on either listing exchange.** A T−60 s market order is a continuous-market trade.
  Its gap to the official close is the 60-second drift plus the auction deviation, a noise floor of a few bp per fill for
  large caps.

### Gaps
- Found no academic or practitioner study that quantifies decision-flip rates between 15:45/15:50/15:57 proxies and the
  official close for threshold strategies.
- Found no 2020–2026 statistics on the distribution of (close − 15:57 price) for S&P 500 names. The Bogousslavsky &
  Muravyev figures cover only midquote→auction (2010–2018).

## 7. Backtest realism for close execution: warnings about assuming fills at the close (close look-ahead, closing-print noise, adjusted closes)

### Takeaway
Assuming fills at the official close is the most achievable daily-bar assumption: the closing auction is deep, its price
impact is lower than in continuous trading, and live MOC orders get the print. But:
- the close is a noisy, transient price that reverts overnight;
- MOC requires committing before the 3:50/3:55 pm cutoffs, so same-close decisions are look-ahead;
- broker paper engines do not reproduce auction fills.

A 5 bp/side charge covers large-cap spread costs but not decision-proxy error or closing-print noise. Those are
timing/information effects, not costs.

### Cited Findings
- Closing auctions grew from 3.1% (2010) to 7.5% (2018) of daily volume. They are driven by ETF and passive ownership and
  institutional rebalancing, contribute little to price discovery, and closing prices "often deviate from closing quote
  midpoints, but the deviations revert by half shortly after the close and fully overnight." — [Bogousslavsky & Muravyev (AEA 2021 version)](https://www.aeaweb.org/conference/2021/preliminary/paper/H9T4hef7);
  [JFM 2023](https://www.sciencedirect.com/science/article/abs/pii/S1386418123000502)
- The concern that closing prices carry institutional price pressure is the subject of "Should We Use Closing Prices?
  Institutional Price Pressure at the Close" (title and abstract snippet only). — [ResearchGate](https://www.researchgate.net/publication/337559124_Should_We_Use_Closing_Prices_Institutional_Price_Pressure_at_the_Close)
- Q2 2024: closing auctions matched $55.5 bn/day, 9.44% of US notional (a record); the NYSE closing auction was 10.52% of
  NYSE-listed volume. On Russell reconstitution day (28 Jun 2024), over 34% of daily notional printed in the closing
  auction. — [BMLL](https://www.bmlltech.com/news/market-insight/into-the-close-unpacking-u-s-closing-auction-dynamics-and-the-impact-of-the-russell-reconstitution)
- Paper engines (Alpaca) fill "MOC" at the current bid/ask, not the auction price. — [Alpaca forum (2026)](https://forum.alpaca.markets/t/paper-moc-orders-partially-fill-remainder-expires-same-setup-on-live-works/19155).
  Backtest engines such as LEAN fill MOC at the official auction price. — [QuantConnect](https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/order-types/market-on-close-orders).
  Paper, backtest and live can therefore each use a different "close".
- Same-close signal-and-fill is the classic look-ahead form. — [ABC Trading Group](https://www.abctradinggroup.com/look-ahead-bias);
  [BotSpot](https://botspot.trade/guides/look-ahead-bias-and-data-leakage);
  [TradeLab](https://trytradelab.com/blog/look-ahead-bias-backtesting)
- AQR's live-trade data show average market impact of ~9 bp (mean), ~6 bp (median) and ~15 bp (value-weighted) for
  institutional trades, mostly permanent. — [Swedroe/ETF.com](https://www.etf.com/sections/index-investor-corner/swedroe-trading-cost-truths)

### Inferences
- **Fidelity hierarchy for a daily close-marked book:**
  - official close (backtest)
  - ≈ live MOC (same print, but decision must precede the cutoff)
  - ≠ paper "MOC" (NBBO at submission)
  - ≈ paper/live T−60 s market order (NBBO at submission; differs from close by drift + auction deviation).
- Measured slippage vs the close for a T−60 s order is therefore the cost of *not* being in the auction, plus spread. Its
  signed mean should be close to half the large-cap spread.
- **Cost assumption.** 5 bp/side is above the half-spread of nearly all S&P 500 names for small orders (top-100 average
  spread ~3.7 bp → half-spread ~1.9 bp). It is conservative as a *spread/impact* charge. It does not cover:
  - (i) decision-on-proxy flips;
  - (ii) the closing-print reversal, which affects how close-marked P&L compares with next-day performance;
  - (iii) opportunity cost of unfilled orders.
  Those need their own measurement (sections 1, 5, 6).
- **Closing-print reversal.** Because the closing print reverts overnight, books marked at the official close carry small
  transient mark-to-market noise, of order the 2–3 bp large-cap deviation per name on traded days. For a long/short book
  this is mostly diversified away, but it inflates the daily variance of paired-book comparisons.

### Gaps
- Found no source with specific evidence on adjusted-close pitfalls (back-adjusted prices distorting percentage thresholds
  or barrier levels) or on "survivorship of the closing print" (halted or missing official closes; vendor last-trade vs
  primary-listing official close). These remain unverified concerns.
- Found no 2020–2026 replication of the Bogousslavsky & Muravyev closing-deviation statistics. Their numbers are
  2010–2018 and should be flagged as older.
