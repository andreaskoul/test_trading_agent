# Risk measurement and peer-field signals: what held up

*2026-11-07. Pre-registration and amendments 1–13: `research/riskfield/PREREG.md` (each committed before the
statistics it governs). Results: `DEV_RESULT.md`, `OOS_RESULT.md` (one read), `DEV2_RESULT.md`, `POSTHOC.md`.
Nothing here trades. No 2026 data was read.*

## The answer

**One robust improvement: the books' beta.** It is measured from 30-minute returns and calibrated on past
outcomes, and it beats the fund's beta by a wide margin. It also makes hedged books measurably less noisy.

| Test (OOS 2020–2025, one read, Holm) | Result |
|---|---|
| **H-B1** beta forecast: intraday-calibrated (B1) vs the fund's (2/3 × 252-day daily OLS + 1/3) | error in next month's realised beta **−33%** (MSE 0.145 → 0.097), t 7.56, Holm p < 10⁻¹³ |
| **P1** hedge the weekly momentum and reversal books with B1 instead of the fund's beta | variance lower, t 2.42, Holm p 0.016; weekly sd 1.95% → 1.90% (momentum), 1.66% → 1.63% (reversal) |

* **Every OOS year improves.** 2020 −9%; 2021–2025 −29% to −42% (`POSTHOC.md`).
* **Where the gain comes from (descriptive):**
  * plain daily OLS is already 16% better than the fund's beta, because the fund shrinks too hard toward 1;
  * intraday measurement over 63 sessions adds about another 6 points;
  * blending 21- and 63-session intraday betas with the daily one gives the rest.

  The fitted blend is 0.33 × HF 21 + 0.27 × HF 63 + 0.39 × daily OLS, with almost no intercept.
* **Size of the change:** B1 differs from the fund's beta by ±0.21 (sd), and the 5th–95th percentiles span
  −0.32 to +0.33. That is enough to move a book's SPY hedge noticeably.
* **What it is not:** it is not an alpha. P1 lowers the hedged books' noise by about 2–3% in standard deviation;
  it does not raise expected return.

## News-shock contagion (rounds 3–5, the McKean–Vlasov idea as the owner meant it)

**The question:** does a news shock at one firm spread to firms like it?
* **Neighbours:** 10-K business-text similarity, or co-movement.
* **Shocks:** each firm's residual return on its news days: earnings (P8 events, 8-K Item 2.02) and unscheduled 8-Ks
  (typed item codes from SEC bulk submissions, 2010–2025).

| Speed | Test | Result |
|---|---|---|
| Next week | C1–C3 (returns), C4 (volatility) | nothing (development t −0.94 to −0.51) |
| Next day | D1–D3 | nothing (+0.2 bp per sd, t ≤ 0.68) |
| Same day (descriptive) | neighbours' earnings shocks vs a non-reporter's residual | **9.8 bp per sd, t 24.9**: the contagion is real |
| **Within the day** (10:00 → close, after a neighbour's out-of-hours earnings) | **I1, text neighbours** | **passes OOS: 2.68 bp per sd, t 2.66, Holm p 0.004**; development 2.15 bp, t 1.69 |
| | I2, co-movement neighbours | failed development (−0.3 bp); OOS +2.4 bp, t 2.15 (reported only) |

**Reading:** contagion of news shocks through business-similarity space is real, but the market prices it fast.
* **Within the session:** most of it is in the price by 10:00. What remains drifts in over the rest of the day,
  and only with text neighbours, not co-movement neighbours: an embedding effect, not a correlation effect.
* **Size:** the top-minus-bottom-decile spread is about 8 bp per earnings-season day. That is below a 10 bp intraday
  round trip at the fund's 5 bp-per-side cost assumption, so as a stand-alone intraday book it does not pay.
* **Its use is order timing.** On earnings-season days, a planned buy of a stock whose text neighbours just gapped
  up is better sent early (at the open, not at T−60 s), and a planned sell later. The fund's orders currently go at
  the close, so this needs an order-timing protocol.
* **By year (descriptive):** positive in 5 of the 6 OOS years (2023 negative).
* **Days that also fail:** unscheduled 8-K days carry little news. Their average move is only 12% above days without
  news.

## Everything else that was tested

| Idea | Development | OOS | Verdict |
|---|---|---|---|
| R1 volatility: McKean–Vlasov field through 10-K text neighbours | t −0.53 | — | no |
| R2 volatility: field through co-movement neighbours | t 2.39 | h5 t 2.24, but **h22 worse** | no (registered: both horizons) |
| R3 local stationarity: exponentially weighted HAR (1-year half-life) | t −0.63 | — | no |
| R4 HARQ (trust noisy days less) | t −0.73 | — | no |
| R5 regime-switching HAR coefficients | t −1.33 | — | no |
| R6 signed jump variation (round 2) | t 0.78 | — | no |
| N1 news unusualness in embedding space, 31 names (the attached case) | t −1.00 (placebo 0.88) | — | no |
| H-B2 beta prior from text neighbours | t 0.76 | — | no |
| H-B3 downside semibeta (round 2) | t −1.42 | — | no |
| A1 text-peer momentum | t −0.93 | — | no |
| A2 / A3 drift toward the neighbours' mean (text / co-movement) | t 2.46 / 3.33, **net losses** | — | no |
| A2B / A3B the same, banded to cut turnover | A3B net +0.5% a year | A3B t 1.23, net −0.6% a year | no |
| A4B realised skewness, banded (round 2) | t 1.45, net −0.25% a year | — | no |
| P2 inverse-forecast-volatility weights within legs | — | Sharpe −0.17 vs −0.09 | no |

**Reading the misses:**

* **Mean-field drift is real but too small to trade.** The co-movement and text neighbours carry real information
  about where a stock's residual return converges (development t 3.3). It is too small to survive 5 bp costs on
  weekly turnover in S&P 500 names, and it did not survive the OOS read.
* **Local stationarity did not pay.** Forgetting old data, or switching coefficients by regime, made volatility
  forecasts worse. A pooled HAR on a long, expanding window was the best: the cross-section supplies the stability.
* **Text embeddings define good neighbourhoods** (HD → LOW, DAL → UAL, JPM → GS), but sectors already capture what
  they add to volatility and beta.
* **News unusualness** gave nothing beyond the article count on 31 names, as the attached case's critique 4
  anticipated.
* **Reported, not tested:** the pooled HAR beats a RiskMetrics EWMA by a wide margin (development t 7.45 at 5 days).
  Sector fields add a little (t 2.31).

## Disclosures

* **Survivorship:** the intraday bars cover the current S&P 500 constituents only. For the beta targets this
  matters little, and P1 compares hedges on the same weights.
* **Text coverage:** 430 of 500 names have a 10-K vector. The rest are names whose CIK changed (XOM, BLK, DIS) or
  whose Item 1 extraction failed (C, COP). They were left out, not guessed.
* **Seen before the read:** A2B and A3B were added after the A2 and A3 development books were seen (Amendment 2).
  P1 and P2 were run once on development data before the read (Amendment 3).
* **2020–2025 has been read before:** earlier studies read these years for other signals. Round 2's development
  failed, so its OOS read was not spent.

## The search for something tradeable (rounds 6–9, Amendments 9–13)

**Owner:** "don't stop the research until you find something tradeable". Tradeable means at the fund's speed:
weekly or daily decisions with entry at the close, at the fund's costs.

| Round | Data | Idea | Development (OOS) | Verdict |
|---|---|---|---|---|
| 6 | P8 earnings events (SUE, CAR) | 20-session earnings-drift book on Thursdays | 13 bp per sd, t 1.22; book +0.2% a year | no |
| 6 | the same + 10-K text neighbours | peers' surprises this season as a fundamental field | −1.1 bp, t −0.07 | no |
| 6 | the same | earnings-announcement premium | −1 bp | no |
| 7 | **SEC Insider Transactions Data Sets** 2010–2025 (1.94M open-market trades, new) | net purchase ratio; opportunistic insiders (Cohen, Malloy & Pomorski); text-neighbour insider field | \|t\| ≤ 0.84, books lose | no: about 25 net-buying names a week in the S&P 500 |
| 8 | daily closes, text and co-movement baskets | Avellaneda–Lee OU stat-arb against the neighbour mean field (their parameters) | at 5 bp: −1.1 to −1.8% a year; gross +1.1 to +1.5 bp a day per position | no |
| 8 at measured costs (Amendment 12) | the same, 2 bp a side (the fund's measured paper cost is 0.9 bp) | the same, and the weekly co-movement gap book | **OOS 2020–25: +1.0 to +1.9% a year, Sharpe 0.24–0.46, t ≤ 0.96** | no: positive, not significant; 2020 +14%, 2022 −6% |
| 9 | the same + the 8-K/earnings calendar | trade only liquidity excursions: no entry after the name's own news (S4) or its neighbours' earnings (S5) | S4 net 0.55 vs 0.45 bp a day for S3, t 1.17 | no (below the 1.5 gate) |

**What the dynamics look like:**
* **Information is priced in hours.** For large caps this holds for the name's own earnings, its neighbours' news
  and insiders' trades alike.
* **The only persistent force is liquidity reversion toward the peer mean.** It is about 1–1.5 bp a day per position
  before costs and robust in sign. At measured costs it is +1–2% a year with a Sharpe below 0.5. Filtering out news
  moves helps, as the logic says, but not enough to be significant.
* **Survivorship:** the reversion results carry the close panel's survivorship (Amendment 13), which flatters them.

**Data defect found:**
* the yfinance close panel behind `research/regime` and this study covers 68.6% of S&P 500 member-days in 2012,
  87.2% in 2020 and 97.1% in 2025;
* P8's Alpaca closes cover 98–100% from 2016;
* future cross-sectional work should use the Alpaca panel.

**Already tradeable from this programme and the regime study:**
* **the momentum panic switch:** passed in the US and an international replication; forward books from 2026-11-12;
* **the intraday-calibrated beta:** passed; forward records from 2026-11-12. It improves every hedge but adds no
  return;
* **the intraday news contagion (I1):** passed; about 8 bp, an order-timing use only.

## Forward beta records (set up; Amendments 5 and 5a)

From Thursday 2026-11-12, the Friday S&P job records both betas for every member (`forward.py`). The bars are
30-minute SIP bars from Alpaca, cached across weeks and split-adjusted. The job scores both betas 21 sessions later
against the realised beta, with the AI ensemble book's leftover beta under each hedge. Section 6 of the assessment
page shows them. No verdict before 26 scored weeks.

## Operational meaning (owner's decision)

The fund's books hedge with the 2/3 + 1/3 daily beta. B1 is a better hedge ratio.
* **Live, it needs:**
  * 30-minute bars for the names each week (Alpaca market data);
  * a monthly refit of the three blend coefficients.
* **How to adopt it:** the traded fund is frozen, so this is a new protocol or a research-book amendment.
* **The natural first step:** forward-record B0 and B1 each week next to the realised beta, like the panic-switch
  books.
