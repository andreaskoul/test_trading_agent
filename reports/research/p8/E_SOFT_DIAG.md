# Rule A: post-read diagnostics (descriptive; the decision is E_SOFT_READ.md)

Read: 2026-11-01T18:42:56.189377+00:00 commit d6a40594e69ef0797f2054a88cb809a235f6bb06. Rows rebuilt with the read's own functions. Standard errors clustered by week (CR1).

## 1. The registered holdout, by source and slice

| sample | n | mean bp | se | t (week) | median | 1-99% winsorised | share > 0 | sd bp |
|---|---|---|---|---|---|---|---|---|
| pooled holdout | 6340 | +11.4 | 5.4 | +2.09 | +8.8 | +8.7 | 0.514 | 428 |
| 8-K 2022-25 | 5722 | +11.0 | 5.3 | +2.08 | +8.5 | +7.5 | 0.514 | 410 |
| Finnhub 2026-05..10 | 618 | +15.1 | 27.5 | +0.55 | +18.3 | +17.7 | 0.516 | 569 |
| 8-K item 5.02 | 3918 | +6.3 | 6.6 | +0.96 | +7.9 | +3.4 | 0.515 | 404 |
| 8-K item 1.01 | 1848 | +21.8 | 8.7 | +2.52 | +12.0 | +16.6 | 0.511 | 419 |
| 8-K 2022 | 1432 | -1.0 | 9.8 | -0.10 | +6.5 | -3.3 | 0.509 | 392 |
| 8-K 2023 | 1404 | +29.2 | 10.3 | +2.84 | +20.5 | +25.5 | 0.536 | 386 |
| 8-K 2024 | 1384 | +19.3 | 10.9 | +1.78 | +10.8 | +11.7 | 0.517 | 437 |
| 8-K 2025 | 1502 | -2.3 | 10.4 | -0.22 | -3.3 | -2.9 | 0.495 | 420 |
| Finnhub leadership | 58 | -105.2 | 65.0 | -1.62 | -31.6 | -104.9 | 0.466 | 487 |
| Finnhub macro_readthrough | 154 | +21.8 | 39.5 | +0.55 | +10.2 | +24.3 | 0.506 | 580 |
| Finnhub mna_rumour | 41 | -19.6 | 78.7 | -0.25 | +5.8 | -28.4 | 0.512 | 449 |
| Finnhub other | 176 | +55.3 | 34.6 | +1.60 | +74.8 | +56.7 | 0.551 | 516 |
| Finnhub partnership | 87 | +83.5 | 64.5 | +1.30 | +48.9 | +80.5 | 0.563 | 553 |
| Finnhub product_launch | 102 | -40.7 | 83.3 | -0.49 | -115.3 | -41.8 | 0.461 | 718 |
| Finnhub, L = 0 (no serving lag) | 618 | +7.3 | 31.2 | +0.23 | +19.3 | +7.3 | 0.513 | 584 |

## 2. Fit windows (nothing was selected on them for E3)

| sample | n | mean bp | se | t (week) | median | 1-99% winsorised | share > 0 | sd bp |
|---|---|---|---|---|---|---|---|---|
| 8-K 2016-21 | 7076 | -1.2 | 6.1 | -0.19 | +0.8 | +0.4 | 0.502 | 455 |
| Finnhub 2025-11..2026-04 | 444 | -29.5 | 27.9 | -1.06 | +7.2 | -31.1 | 0.509 | 529 |
| 8-K 2016-25 (fit + holdout) | 12798 | +4.3 | 4.1 | +1.03 | +4.3 | +4.3 | 0.507 | 435 |
| Finnhub 2025-11..2026-10 | 1062 | -3.6 | 19.8 | -0.18 | +14.9 | -3.1 | 0.513 | 553 |
| all E3 rows | 13860 | +3.7 | 4.1 | +0.89 | +4.7 | +3.4 | 0.508 | 445 |

## 3. Desk agreement

7/12; rows written to the JSON.

## 4. Judgement (post-read; the registered decision stands: STOP)

**The rule passed its return leg narrowly, and stopped on a 12-trade agreement count.** The judgement below asks
whether STOP is right on the basis that matters to the fund: the desk's own profit and loss on a soft entry after costs.

1. **What the fund earns is not what the test measured.** The test measures follow-through in the direction of the
   news-day move, d. The desk trades its own side. If the desk agrees with d with probability a, and agreeing or not is
   unrelated to the size of the move, its expected gross result per soft trade is (2a − 1)μ. That covers the round
   trip c = 4 bp only when a ≥ a* = (1 + c/μ)/2.
   * At the holdout μ = 11.4 bp, a* = 0.675. The registered 60% bar was below the break-even point. At a = 0.60 the desk
     would make 2.3 bp gross, under its cost.
   * At the observed 7/12, the desk makes about 1.9 bp gross per trade. With a uniform prior, P(a ≥ 0.675 | 7/12) = 0.22.
   * The 95% Wilson interval for a is [0.32, 0.81]. So the agreement leg is decided by noise; the economics are not.
2. **The holdout's +11.4 bp is at the hurdle once all the evidence is used.**
   * E3 chose nothing on its fit windows, so fit and holdout are exchangeable samples of one rule.
   * The 8-K estimate moved from −1.2 ± 6.1 bp (2016–21) to +11.0 ± 5.3 bp (2022–25). The difference is z = 1.5: it is
     not a contradiction, but it is not stable either.
   * Pooled, 8-K events over 2016–25 give +4.3 ± 4.1 bp, and all E3 rows give +3.7 ± 4.1 bp. That is −0.3 bp net of
     cost, with a 95% interval of [−8.3, +7.7] bp per trade.
3. **The holdout effect is concentrated in two years.** By year: 2022 −1.0, 2023 +29.2, 2024 +19.3, 2025 −2.3 bp. The
   heterogeneity statistic is Q = 6.8 on 3 degrees of freedom, p = 0.08. Item 1.01 (+21.8, t 2.5) against item 5.02
   (+6.3, t 1.0) is one slice among about 16 examined here. A largest t of 2.5 among 16 is what noise produces.
4. **The source the desk actually trades is uninformative.** Finnhub soft bursts: +15.1 bp, 95% interval [−39, +69].
   The pooled mean gives the 8-K events 90% of the weight, and the desk does not trade 8-K items 5.02 and 1.01.
5. **The weight of evidence is weak.**
   * One-sided p = 0.0895 bounds the Bayes factor for an effect at 1/(−e·p·ln p) = 1.7.
   * Across the programme's roughly 38 reads, about 3.8 results with p ≤ 0.10 are expected under the null.
   * The middle of the distribution is not driven by tails: median +8.8 bp, winsorised mean +8.7 bp. The directional
     skew is small (51.4% positive).

**Conclusion.** STOP is right, for a sturdier reason than the rule records. Soft news on large caps, at the fund's
entry time, has follow-through about equal to its cost (+3.7 ± 4.1 bp gross against 4 bp). The desk's side agrees with
it too rarely to capture even the holdout figure. This also corrects the earlier claim, from thin evidence, that
soft-news entries are strongly negative: they are about zero after costs. That still means variance and turnover
without expected return.

**Lessons for the next pre-registrations (design only; no re-read):**
* derive any applicability bar from break-even, a* = (1 + c/μ)/2, not from a round number;
* weight a pooled estimand toward the inputs the live decision uses;
* when a rule selects nothing on its fit window, register the fit-plus-holdout estimate as a co-primary statistic;
* require a minimum count before a condition can bind (for example n ≥ 40, which puts the standard error of a share at
  ≤ 0.08).
