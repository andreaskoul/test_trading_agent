# Pre-registration: what hard news earns at the fund's speed (a precision estimate)

Written 2026-11-02, before any statistic below has been computed. It follows `DESIGN_RULES.md` (signed by the owner
when #134 merged on 2026-11-02). It is a **precision estimate** (rule 6), not an admission read, so it does not add to N.

## The question

After 7B Amendment 3 the live book trades only hard news: earnings, guidance and capital returns, plus anything the
desk labels `hard` (a figure, a signed deal, a ruling). No hard-news component has passed a test at the fund's
latency:
* information time plus the Finnhub serving lag;
* the Wednesday desk;
* entry at the Thursday close.

**Does a hard-news position, held in the direction of the news-day move, earn more than its cost from the fund's
entry?**

## What has been seen (disclosed)

* **The gap study** (`technicals_backtest.md`, 8,924 news-gap events, all news types, 2012–2025), from the Thursday
  entry close, side = gap direction: +7 bp at 5 sessions, +9 bp at 10, −6 bp at 20 (t −2.1). For 2012–2021 alone:
  −14 bp at 20 (t −3.6). It was not split by hard and soft news.
* **Family E's E2** (hard 8-K items, 2022–2025, h 10): +54.8 bp, p 0.18, n 221. **E1** used the earnings surprise (SUE),
  not the news-day direction.
* **The Finnhub labels** (`.cache/p8/soft_labels.jsonl`) were read only for counts. No return of a hard shock has been
  computed.
* **Event counts** (no returns):
  * earnings 8-K 2.02 releases, S&P 500, live-API times: 9,903 (2016–21) and 7,370 (2022–25);
  * hard 8-K items 2.01/2.05/2.06/4.02: 788;
  * hard Finnhub shocks: 939 (380 fit-window, 559 holdout).

Nothing below is chosen on any of this. The horizons, cells, weights and rule are fixed here.

## Cells

1. **Earnings releases (E).**
   * Events: S&P 500 8-K item 2.02 filings, 2016–2025, with live-API acceptance times (Family E Amendment 1).
   * The news session t0 is set by the 15:40 ET rule (`family_e.t0_info`).
2. **Other hard news (O).**
   * Hard 8-K items 2.01, 2.05, 2.06 and 4.02, 2016–2025, not within ±2 sessions of a 2.02 filing (as E2), one per
     name per 5 sessions.
   * Plus Finnhub shocks 2025-11-01 – 2026-10-31 whose label is hard, or whose type is capital_return. Shocks typed
     earnings or guidance (hard or not) are excluded from O. They are news about results that is not the release
     itself, since bursts within ±2 sessions of a 2.02 filing are already excluded. They are reported on their own
     line, descriptive only.
   * Each Finnhub shock's placebo excludes sessions within 5 of any of the name's shocks or 2.02 filings. Its
     information time is 12:00 ET plus L, as for its event.
   * The two sources are pooled within O with inverse-variance weights.

## The statistic

* **d** = sign of the stock's residual (r − β·r_SPY, β estimated before t0) on the news session. Zero moves are
  dropped.
* **Entry** = the fund's entry for news known at the information time (`family_e.fund_entry`): the Thursday close
  after the first Wednesday 22:00 UTC cutoff at or after it. Information time is:
  * for 8-K filings, the acceptance time;
  * for Finnhub shocks, the first article's publish time plus L = 1,377 min, frozen from `E_SOFT_READ.json`.
* **y_H** = d × the sum of the residual over the H sessions after the entry close.
  * **Primary: H = 10.** Secondary: H = 5 and H = 20, and the tail y_20 − y_15 (sessions 16–20).
* **Placebo.**
  * Each event gets one placebo: the same name, on a session drawn at random (seed 0) from the same calendar month.
    The session is at least 5 sessions away from any of the name's 8-K 2.02 or hard 8-K filings.
  * Information time is 12:00 ET on that session. The placebo's d and y are computed as for an event.
  * The placebo measures the drift that follows any day's move, such as weekly reversal.
* **Standard errors.**
  * Per cell, the largest of the CR1 week, CR1 industry and Cameron–Gelbach–Miller week × industry variances (as
    `inference.mean_test`).
  * Pooled: μ_w = w_E μ_E + w_O μ_O, with SE_w = √(w_E² SE_E² + w_O² SE_O²).
* **Weights (rule 5).** w_E is the share of the live desk's hard views typed earnings or guidance, over every
  labelled cohort from 2026-10-28 to the last cohort before the run (`lifecycle.json`). w_O = 1 − w_E.

## Expected precision (rule 3 and rule 6)

Assumptions:
* σ_5 ≈ 430 bp per event, from E3's 5-session y, so σ_10 ≈ 610 bp;
* D ≈ 1.2.

| cell | n (approx.) | SE at H = 10 | 95% half-width |
|---|---:|---:|---:|
| E | 17,000 | 5 bp | ±10 bp |
| O | 1,400 | 20 bp | ±40 bp |
| pooled (w_E ≈ 0.75) | | 6 bp | ±12 bp |

A pass/fail admission read would need power ≥ 0.5 against h_L = 4 bp at p ≤ 0.0026 (z 2.79). That needs
δ ≥ 4 + 2.79 × 6 ≈ 21 bp. Half of the gap study's +9 bp at H = 10 is far below that, so this is a precision estimate.

## Decision rule (primary: pooled μ_w at H = 10; h_L = 4 bp, h_R = 10 bp)

* **Upper 95% bound < h_L** → **LIMIT.** I propose a 7B amendment that halves hard-news entry weights and caps
  hard-news horizons at 10 sessions. The owner decides.
* **Lower 95% bound > h_R, and the lower bound of the event-minus-placebo difference > 0** → **PROPOSE** a powered
  admission read on new data from 2026-11.
* **Otherwise** → **MEASURE.** No change; the decision ledger keeps measuring.

**Secondary rules, each judged on its own:**
* **Tail.** If cell E's 16–20 tail has an upper 95% bound < 0, I propose capping hard-news holds at 15 sessions. The
  live rules allow 20–63; see the ledger's segment table.
* **Side.** Results for d > 0 and d < 0 are reported for each cell, descriptive only.

## Records

* Code: `research/p8/hard_news.py`, committed before it is run.
* Run: `python3 research/p8/hard_news.py run`, once; the lock is `reports/research/p8/HARD_NEWS.lock`.
* Output: `HARD_NEWS.json` and `.md`.
* `DATA_USE.md` gets a row. N is unchanged.
