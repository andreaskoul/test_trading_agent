# News desk: Phase 0 cost probe

<!-- findings -->
## Findings (written 2026-10-16, after the probe; no source list is frozen yet)

**1. Money is not the constraint.**
- The suggested set costs about **$58/month with the model's default reasoning, or $8/month with reasoning off**. That covers tagging plus an upper-bound ledger, which assumes every firm named that day gets 3 ledger passes.
- Everything except GDELT GKG costs $64 / $10 a month.
- At the fund model's live price ($0.036 / $0.684 per million input / output tokens), **output tokens are ~90% of the bill**.

**2. Reasoning tokens are the cost lever.** On the same 10 Benzinga items:
- default: 7,662 output tokens (7,085 of them reasoning), 40 s;
- `reasoning: {enabled: false}`: 842 output tokens, 3.4 s, with the same tickers tagged.

That is about 9× cheaper and 12× faster. Before the desk adopts it for tagging, it needs a quality check on about 200 items against the node contract. The 3-pass ledger could keep reasoning on: with reasoning it costs about $1.1/day for ~225 firms a day.

**3. YouTube captions are the binding constraint, not cost.**
- The caption endpoint blocked this Mac's IP (`IpBlocked`) after **21** transcripts, spaced 2.5 s apart.
- yt-dlp subtitles then returned 429, and the channels' RSS feeds returned 404.
- **Audio downloads kept working** (6 of 65 got a 403). So the dependable free route is audio + local mlx-whisper, which runs at **~17× real time** on the M4.
- Daily load: suggested set about **150 compute-minutes/day and ~90 downloads/day**; everything ~195 min/day and ~115 downloads/day.
- A caption route at low volume (with a cap per run and longer gaps) may be usable as a cheaper first try, but it can't be relied on.
- The household IP may get YouTube's "confirm you're not a bot" check while this runs.

**4. Podcasts are cheap.**
- Odd Lots, Bloomberg Surveillance, Columbia Energy Exchange and Acquired publish their own transcripts in their RSS feeds, so they need no whisper.
- GS Exchanges, GS The Markets, MS Thoughts on the Market, Capital Allocators and Behind the Balance Sheet need whisper, but only about 2 compute-minutes a day in total.

**5. GDELT: not worth it for this desk.**
- The DOC API refused this IP every time (429, even a single request hours apart). The context archive's GDELT themes run into the same limit.
- The raw GKG files download fine. But they carry **~115,000 English articles a day (~450 MB/day)**, and the firm "hits" are mostly incidental mentions: "Delta flight", "Breaking Bad", Facebook in non-business stories.
- GKG alone would cost $41–298/month in LLM calls for mostly noise.
- Recommendation: leave it out of the LLM path. If wanted later, use it only for deterministic counts and tone, under its own amendment.

**6. Benzinga via Alpaca is the backbone.**
- 1,011 items/day naming **433 distinct firms** over the 2 days, at the lowest cost per firm hit ($0.0003).
- Finnhub general news adds little: 46 items/day naming 10 firms.
- Official and trade feeds are cheap but thin: ~5 firm hits/day across Federal Register, openFDA, USAspending and trade press.

**7. Early sign that spoken content repeats the wires** (firm level, 2 days, ~3 sampled uploads per channel). Firms named that Benzinga and Finnhub had not named:
- video: only **7** (AFG, CEG, F, KBH, LOW, NYT, TRMB);
- podcasts: **8**;
- official and trade: 13.

The pre-registered N3 test measures novelty properly, at the event level. This only says not to expect much.

**8. Channels to drop, whatever the budget:**
- Defense & Aerospace Report: no uploads since 2022.
- Business Breakdowns: no recent uploads on either the channel or the feed.
- Bloomberg New Economy: 9 uploads/day and 470 min/day of airtime, but 0 firm hits in its sample.
- a16z: its only sampled video failed to download, so it is unmeasured.
- Fierce Biotech/Pharma: 403 to scripts.
- DoD daily contract notice: 403 to scripts, so contract awards come from USAspending, which lags.

**9. The prefilter needed a fix.** Firm names that are everyday words (Target, Post, Gap, News Corp, Bill, Block, Nasdaq, Visa…) were matching "price target", "news" and so on: 702 of 1,293 text hits at first. They now need a company suffix ("Target Corp") or ticker evidence (cashtag, exchange tag, Benzinga symbols). This is tested in `fund/tests/test_news_desk.py`. Share classes (GOOG/GOOGL) still double-count until the CIK collapse.

**Recommended set for the owner to confirm** (≈ $60/month with reasoning on, ≈ $8–10 off; ~2.5 h/day of whisper on the Mac):
- Benzinga, Finnhub general, Federal Register, openFDA, USAspending, trade press minus Fierce.
- Tier a minus Bloomberg New Economy and the Colossus channel.
- Tier b minus Defense & Aerospace Report.
- The transcript-publishing podcasts (Odd Lots, Surveillance, Columbia, Acquired), plus GS Exchanges and MS Thoughts on the Market.
- Tier c archive-only (no LLM), as planned.
- No GDELT.

**Owner decision, 2026-10-16:** cap of $50–60/month, because this is a trial that has to beat the S&P and the other benchmarks within about 6 months. The v1 list is in `data/raw/news/sources.json`:
- **Active:** 17 YouTube channels, 6 podcasts and 9 RSS feeds, plus Benzinga, Finnhub general, Federal Register, openFDA and USAspending.
- **Archive-only:** the 8 macro channels.
- **Dropped:** 4 YouTube channels, 4 podcasts (GS The Markets, Capital Allocators and Behind the Balance Sheet for low firm yield; Business Breakdowns for being silent), 3 feeds, and GDELT.
- **LLM settings:**
  - tagging runs with reasoning **off** (~$3/month);
  - the 3-pass ledger runs with reasoning **on** (~$34/month at the upper bound);
  - if reasoning-off tags miss the node contract (precision ≥ 0.9 on 200 owner-checked tags), tagging falls back to reasoning on (~$58/month), which still fits the cap.
- **Hard stop:** $1.80 of LLM spend per UTC day.
- **Whisper:** capped at 180 compute-minutes a day.
<!-- /findings -->
Window: Tue 13 – Wed 14 Oct 2026 (UTC), fetched from 2026-10-15T21:06 UTC. Model deepseek/deepseek-v4.1-flash; price $0.150 / $0.600 per million input / output tokens (openrouter /api/v1/models).

**How to read.** `_d` = per day. Text and official sources: the 2-day total / 2. openFDA lags, so its rate is over 45 days; GDELT GKG is sampled (one 15-minute file every 3 h) and scaled by the time it covers. Video and podcasts: volumes (`items_d`, `air_min_d` = minutes of airtime per day) come from the uploads listing / feed (the 2-day window when a channel had at least 3 uploads in it, else the last 30 days for video and 60 for podcasts); ~3 uploads per channel were transcribed and their tokens are scaled by airtime. `pre_tok` = tokens of items or transcript windows (±90 s) that name a universe firm or a sector/theme keyword. `usd_d` = tagging (map) + ledger cost; ledger is an upper bound (every named firm gets the 3-pass ledger). `whisper_min_d` = Mac compute minutes per day if the airtime goes through local whisper (0 where the feed publishes its own transcript). `usd_per_firm_hit` = cost per (item, firm) mention.

## Totals by set

Costs are shown as *reasoning on / reasoning off* (the model's default spends ~90% of its output on reasoning tokens; see Calibration). Ledger = 3 passes for every firm named that day (upper bound: only firms with a card would get one). Whisper = Mac compute minutes/day if all video airtime goes through local whisper; YouTube fetches/day = transcripts or audio downloads per day.

| set | items/day | airtime min/day | prefiltered tokens/day | firm hits/day | firms/day | tagging $/day | ledger $/day | **$/month** | whisper min/day | YouTube fetches/day |
|---|---|---|---|---|---|---|---|---|---|---|
| lean: Benzinga + Finnhub + official + trade press + CNBC/Bloomberg TV/Yahoo | 1,292 | 1,154 | 244,206 | 1,139 | 224 | 0.54 / 0.11 | 1.13 / 0.30 | **51 / 12** | 74 | 58 |
| suggested: lean + all of tiers a, b + Odd Lots, GS Exchanges, MS Thoughts | 1,325 | 2,391 | 390,774 | 1,235 | 226 | 0.74 / 0.16 | 1.18 / 0.34 | **58 / 15** | 152 | 88 |
| everything except GDELT GKG | 1,354 | 3,096 | 513,463 | 1,403 | 229 | 0.93 / 0.20 | 1.24 / 0.40 | **66 / 18** | 194 | 115 |
| GDELT GKG alone (add-on) | 114,600 | 0 | 1,874,214 | 23,772 | 142 | 8.27 / 1.40 | 1.38 / 0.86 | **293 / 69** | 0 | 0 |
| everything incl. GDELT GKG | 115,954 | 3,096 | 2,387,677 | 25,175 | 272 | 9.20 / 1.60 | 2.17 / 1.17 | **346 / 84** | 194 | 115 |

## Totals by tier

| tier   |   items_d |   air_min_d |        raw_tok_d |        pre_tok_d |   firm_hits_d |   usd_d |   whisper_min_d |
|:-------|----------:|------------:|-----------------:|-----------------:|--------------:|--------:|----------------:|
| a      |      75   |      1981.9 | 409181           | 308688           |         353.6 |     0.5 |           127.8 |
| b      |      13.5 |       374.8 |  67265.6         |  55501.7         |          37.6 |     0.1 |            23.6 |
| c      |      27   |       633.2 | 143800           | 107897           |         157.1 |     0.2 |            40.8 |
| d      |     181.2 |       105.9 |  41965.5         |  21669.6         |          24.5 |     0   |             1.9 |
| text   |  115657   |         0   |      8.80207e+06 |      1.89392e+06 |       24602.5 |     9.2 |             0   |

## Per source / channel / show (sorted by $/day)

| source      | grp                                                 | tier   | mode   |   fetched |   items_d |   air_min_d |   raw_tok_d |   pre_tok_d |   map_in_d |   firm_hits_d |   unique_firms |   usd_d |   usd_month |   usd_per_firm_hit | captions           |   whisper_min_d |
|:------------|:----------------------------------------------------|:-------|:-------|----------:|----------:|------------:|------------:|------------:|-----------:|--------------:|---------------:|--------:|------------:|-------------------:|:-------------------|----------------:|
| gdelt_gkg   | gdelt_gkg                                           | text   | window |     19100 |  114600   |         0   |     8765754 |     1874214 |    3678901 |       23772   |            283 |   9     |      273.61 |             0.0004 |                    |             0   |
| youtube     | Bloomberg Television                                | a      | window |         3 |      25   |       683.7 |      174104 |      123542 |     155271 |          71   |              3 |   0.228 |        6.92 |             0.0032 | whisper:2, error:1 |            44.1 |
| alpaca      | alpaca                                              | text   | window |      2022 |    1011   |         0   |       34698 |       19233 |      62731 |         825   |            433 |   0.212 |        6.44 |             0.0003 |                    |             0   |
| youtube     | Bloomberg Podcasts (Odd Lots, Surveillance)         | c      | window |         3 |      19   |       311   |       75452 |       66555 |     109732 |         105.2 |              5 |   0.146 |        4.42 |             0.0014 | whisper:3          |            20.1 |
| youtube     | Yahoo Finance                                       | a      | window |         3 |      10.5 |       306.2 |       66607 |       64808 |      84087 |         155.4 |             18 |   0.097 |        2.96 |             0.0006 | whisper:3          |            19.7 |
| youtube     | CNBC Television                                     | a      | window |         3 |      22   |       164   |       39393 |       33091 |      57703 |          71.8 |              4 |   0.075 |        2.29 |             0.001  | whisper:3          |            10.6 |
| youtube     | FreightWaves                                        | b      | window |         3 |       9.5 |       230.9 |       47704 |       38826 |      46864 |          12.1 |              3 |   0.051 |        1.54 |             0.0042 | whisper:3          |            14.9 |
| youtube     | TBPN                                                | a      | rate30 |         1 |       2   |       177.7 |       43191 |       31261 |      37142 |          26.7 |              3 |   0.047 |        1.44 |             0.0018 | whisper:1          |            11.5 |
| youtube     | Bloomberg New Economy                               | a      | window |         3 |       9   |       472.9 |       47845 |       31328 |      47592 |           0   |              0 |   0.045 |        1.36 |           nan      | whisper:3          |            30.5 |
| youtube     | Excess Returns                                      | c      | rate30 |         1 |       1.5 |        83.8 |       18050 |       14660 |      18888 |          20.9 |              5 |   0.029 |        0.89 |             0.0014 | whisper:1          |             5.4 |
| youtube     | SemiAnalysis                                        | b      | rate30 |         1 |       0.9 |        27.4 |        6294 |        6294 |      15467 |          13.3 |              1 |   0.026 |        0.79 |             0.002  | whisper:1          |             1.8 |
| youtube     | 20VC                                                | a      | rate30 |         1 |       0.9 |        66   |       15368 |       12287 |      14465 |          16.5 |              5 |   0.018 |        0.55 |             0.0011 | whisper:1          |             4.3 |
| youtube     | Monetary Matters                                    | c      | rate30 |         1 |       0.7 |        47.2 |        9815 |        8766 |      10322 |          11.8 |              5 |   0.013 |        0.39 |             0.0011 | whisper:1          |             3   |
| podcast     | Bloomberg Surveillance                              | d      | window |         3 |       1.7 |        48.3 |       11232 |       10503 |      12268 |           8.5 |             13 |   0.012 |        0.37 |             0.0014 | feed:3             |             0   |
| youtube     | MacroVoices                                         | c      | rate30 |         3 |       0.9 |        50.8 |       10522 |        8662 |      10828 |           0.9 |              1 |   0.012 |        0.36 |             0.013  | whisper:3          |             3.3 |
| youtube     | Goldman Sachs                                       | a      | rate30 |         1 |       1.2 |        21.3 |        3381 |        2355 |       3984 |           2.4 |              2 |   0.009 |        0.28 |             0.0038 | whisper:1          |             1.4 |
| fedreg      | fedreg                                              | d      | window |       229 |     114.5 |         0   |       13038 |        2260 |       3331 |           5   |              8 |   0.009 |        0.27 |             0.0018 |                    |             0   |
| youtube     | Invest Like The Best                                | a      | rate30 |         1 |       0.5 |        24.9 |        5603 |        4236 |       5491 |           3.7 |              3 |   0.009 |        0.26 |             0.0023 | whisper:1          |             1.6 |
| youtube     | TechTechPotato                                      | b      | rate30 |         1 |       0.8 |        23.4 |        4847 |        3930 |       5110 |           8.2 |              7 |   0.008 |        0.24 |             0.001  | whisper:1          |             1.5 |
| youtube     | The Compound                                        | c      | window |         3 |       2   |        34.5 |        7356 |        2928 |       5085 |          11   |              6 |   0.007 |        0.21 |             0.0006 | whisper:2, error:1 |             2.2 |
| youtube     | Eurodollar University                               | c      | rate30 |         1 |       1.5 |        34   |        6816 |        2503 |       3660 |           3.4 |              2 |   0.007 |        0.21 |             0.0021 | whisper:1          |             2.2 |
| youtube     | Morgan Stanley                                      | a      | window |         3 |       3   |        27.2 |        5536 |        2093 |       3995 |           2.8 |              1 |   0.006 |        0.18 |             0.0021 | whisper:3          |             1.8 |
| finnhub     | finnhub                                             | text   | window |        92 |      46   |         0   |        1616 |         474 |       1473 |           5.5 |             10 |   0.005 |        0.14 |             0.0009 |                    |             0   |
| podcast     | Columbia Energy Exchange                            | b      | rate60 |         3 |       0.2 |         9.2 |        4480 |        4002 |       4592 |           0.7 |              5 |   0.004 |        0.12 |             0.006  | feed:3             |             0   |
| youtube     | Dwarkesh Patel                                      | a      | rate30 |         3 |       0.4 |        19.2 |        4041 |        1251 |       1856 |           0.9 |              1 |   0.004 |        0.11 |             0.0041 | whisper:2, error:1 |             1.2 |
| podcast     | Odd Lots                                            | d      | rate60 |         3 |       0.5 |        24.1 |        5457 |        2275 |       2932 |           1.2 |              9 |   0.004 |        0.11 |             0.0029 | feed:3             |             0   |
| youtube     | Norges Bank Investment Management (In Good Company) | a      | rate30 |         3 |       0.3 |        15.5 |        3432 |        1791 |       2401 |           1.5 |              5 |   0.004 |        0.11 |             0.0023 | whisper:3          |             1   |
| youtube     | Real Vision                                         | c      | rate30 |         3 |       0.9 |        47.1 |       10810 |        2189 |       2987 |           1.2 |              1 |   0.003 |        0.1  |             0.0028 | whisper:2, error:1 |             3   |
| youtube     | Forward Guidance                                    | c      | rate30 |         1 |       0.3 |        15.3 |        3323 |         599 |       1125 |           0.8 |              1 |   0.003 |        0.09 |             0.0037 | whisper:1          |             1   |
| youtube     | Asianometry                                         | b      | rate30 |         1 |       0.5 |        11.7 |        2177 |        1467 |       1861 |           1.8 |              3 |   0.003 |        0.08 |             0.0016 | whisper:1          |             0.8 |
| podcast     | Capital Allocators                                  | d      | rate60 |         1 |       0.3 |        14.5 |        2837 |         967 |       1497 |           1.4 |              2 |   0.002 |        0.07 |             0.0017 | whisper:1          |             0.9 |
| usaspending | usaspending                                         | d      | window |        64 |      32   |         0   |        2290 |         301 |        591 |           2   |              3 |   0.002 |        0.07 |             0.0012 |                    |             0   |
| podcast     | Morgan Stanley Thoughts on the Market               | d      | window |         1 |       0.7 |         4.8 |        1057 |         852 |       1284 |           0.6 |              1 |   0.002 |        0.06 |             0.0034 | whisper:1          |             0.3 |
| podcast     | Goldman Sachs Exchanges                             | d      | rate60 |         1 |       0.2 |         5.3 |         915 |         692 |       1131 |           0.6 |              2 |   0.002 |        0.06 |             0.0033 | whisper:1          |             0.3 |
| youtube     | Patrick Boyle                                       | c      | rate30 |         3 |       0.3 |         9.5 |        1656 |        1034 |       1410 |           1.9 |              9 |   0.002 |        0.06 |             0.001  | whisper:3          |             0.6 |
| podcast     | Acquired                                            | d      | rate60 |         3 |       0   |         3.6 |        2712 |        2690 |       2787 |           0.9 |             38 |   0.002 |        0.05 |             0.0019 | feed:3             |             0   |
| youtube     | Munro Live                                          | b      | rate30 |         3 |       0.4 |         8.5 |        1764 |         983 |       1430 |           1.6 |              5 |   0.002 |        0.05 |             0.001  | whisper:3          |             0.5 |
| podcast     | Behind the Balance Sheet                            | d      | rate60 |         1 |       0   |         3.8 |         802 |         450 |        729 |           0.4 |              2 |   0.001 |        0.04 |             0.0033 | whisper:1          |             0.2 |
| openfda     | openFDA enforcement                                 | d      | window |        93 |       2.1 |         0   |         204 |         204 |        355 |           0.1 |              5 |   0.001 |        0.04 |             0.0109 |                    |             0   |
| rss         | Supply Chain Dive                                   | d      | window |         5 |       2.5 |         0   |          98 |          79 |        238 |           1.5 |              3 |   0.001 |        0.03 |             0.0007 |                    |             0   |
| rss         | Utility Dive                                        | d      | window |         6 |       3   |         0   |         168 |          93 |        215 |           0   |              0 |   0.001 |        0.02 |           nan      |                    |             0   |
| youtube     | Bg2 Pod                                             | a      | rate30 |         3 |       0   |         3.3 |         679 |         647 |        756 |           0.9 |             10 |   0.001 |        0.02 |             0.0007 | whisper:2, error:1 |             0.2 |
| rss         | Retail Dive                                         | d      | window |         8 |       4   |         0   |         156 |          36 |        116 |           0.5 |              1 |   0.001 |        0.02 |             0.0011 |                    |             0   |
| podcast     | Goldman Sachs The Markets                           | d      | rate60 |         1 |       0.1 |         1.5 |         326 |         182 |        278 |           0.1 |              1 |   0     |        0.01 |             0.0034 | whisper:1          |             0.1 |
| openfda     | openFDA approvals                                   | d      | window |       479 |      10.6 |         0   |         235 |          12 |         53 |           0.6 |              9 |   0     |        0.01 |             0.0006 |                    |             0   |
| rss         | FDA press releases                                  | d      | window |         2 |       1   |         0   |          54 |          16 |         52 |           0   |              0 |   0     |        0.01 |           nan      |                    |             0   |
| rss         | EE Times                                            | d      | window |         5 |       2.5 |         0   |         155 |          35 |         76 |           1   |              2 |   0     |        0.01 |             0.0003 |                    |             0   |
| rss         | Construction Dive                                   | d      | window |         7 |       3.5 |         0   |         152 |          22 |         61 |           0   |              0 |   0     |        0.01 |           nan      |                    |             0   |
| rss         | DoD contracts                                       | d      | window |         2 |       1   |         0   |          33 |           0 |          0 |           0   |              0 |   0     |        0    |           nan      |                    |             0   |
| podcast     | Business Breakdowns                                 | d      | rate60 |         1 |       0   |         0   |           0 |           0 |          0 |           0   |              8 |   0     |        0    |           nan      | whisper:1          |             0   |
| rss         | Fed press releases                                  | d      | window |         1 |       0.5 |         0   |          26 |           0 |          0 |           0   |              0 |   0     |        0    |           nan      |                    |             0   |
| rss         | Skift                                               | d      | window |         1 |       0.5 |         0   |          20 |           0 |          0 |           0   |              0 |   0     |        0    |           nan      |                    |             0   |
| youtube     | Defense & Aerospace Report                          | b      | rate30 |         3 |       0   |         0   |           0 |           0 |          0 |           0   |              1 |   0     |        0    |           nan      | whisper:3          |             0   |
| youtube     | Business Breakdowns (Colossus)                      | a      | rate30 |         3 |       0   |         0   |           0 |           0 |          0 |           0   |             17 |   0     |        0    |           nan      | whisper:3          |             0   |
| youtube     | a16z                                                | b      | rate30 |         1 |       1.3 |        63.7 |           0 |           0 |          0 |           0   |              0 |   0     |        0    |           nan      | error:1            |             4.1 |

## Calibration

~20 real tagging calls per source kind through common.llm (default settings): provider-counted input tokens vs the tiktoken proxy (`ratio`), and output tokens per unit (item or transcript window).

| kind | calls | ok | units | input ratio | output tokens / unit |
|---|---|---|---|---|---|
| text | 2 | 2 | 20 | 1.064 | 568.9 |
| podcast | 10 | 10 | 20 | 1.016 | 2043.7 |
| official | 2 | 2 | 20 | 1.017 | 932.2 |
| trade | 2 | 2 | 19 | 1.085 | 845.6 |
| video | 10 | 10 | 20 | 0.991 | 2625.4 |

Side test, same 10 Benzinga items: reasoning on = 844 in / 7,662 out (7,085 reasoning), 40 s; `reasoning: {enabled: false}` = 819 in / 842 out, 3.4 s; the same 10 items tagged with the same tickers.

Whisper real-time factor on this Mac: 15.5× (audio seconds per compute second).

## Source status (fetch manifests)

- **youtube**: {'ok': True, 'items': 65, 'seconds': 4195}
- **rss**: {'ok': False, 'items': 37, 'seconds': 10, 'note': 'failed ["Fierce Biotech: <HTTPError 403: \'Forbidden\'>", "Fierce Pharma: <HTTPError 403: \'Forbidden\'>"]'}
- **fedreg**: {'ok': True, 'items': 229, 'seconds': 0}
- **openfda**: {'ok': True, 'items': 572, 'seconds': 6}
- **usaspending**: {'ok': True, 'items': 64, 'seconds': 1}
- **alpaca**: {'ok': True, 'items': 2022, 'seconds': 40}
- **finnhub**: {'ok': True, 'items': 98, 'seconds': 32}
- **gdelt_gkg**: {'ok': True, 'items': 19100, 'seconds': 24}
- **podcasts**: {'ok': True, 'items': 18, 'seconds': 430}
- **gdelt**: {'ok': False, 'items': 0, 'seconds': 574, 'note': 'failed slices 4: ["business 13 00: <HTTPError 429: \'Too Many Requests\'>", "supply 14 00: <HTTPError 429: \'Too Many Requests\'>"]'}
