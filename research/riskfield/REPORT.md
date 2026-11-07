# Risk measurement and peer-field signals: what held up

*2026-11-07. Pre-registration and amendments 1–4: `research/riskfield/PREREG.md` (each committed before the
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

## Operational meaning (owner's decision)

The fund's books hedge with the 2/3 + 1/3 daily beta. B1 is a better hedge ratio.
* **Live, it needs:**
  * 30-minute bars for the names each week (Alpaca market data);
  * a monthly refit of the three blend coefficients.
* **How to adopt it:** the traded fund is frozen, so this is a new protocol or a research-book amendment.
* **The natural first step:** forward-record B0 and B1 each week next to the realised beta, like the panic-switch
  books.
