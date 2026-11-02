# What hard news earns at the fund's speed (precision estimate, run once)

Lock: 2026-11-02T13:36:51.595816+00:00 commit b4ff0dc88f803b1b695ed25775c0582d41b2ea5c. Pre-registration: `reports/research/PREREG_hard_news.md`. bp per event, y = d x residual sum after the fund's entry close; [95% interval]. w_E = 0.75 (12 earnings/guidance vs 4 other hard views). Hurdles: h_L 4 bp, h_R 10 bp.

| H | E: earnings releases | E placebo | O: 8-K hard items | O: Finnhub hard | O pooled | pooled (w) | pooled placebo | event − placebo | Finnhub earnings news |
|---|---|---|---|---|---|---|---|---|---|
| 5 | +0.0 [-7.1, +7.2] (n 15443) | -4.1 [-13.9, +5.7] (n 15414) | +10.7 [-22.4, +43.8] (n 650) | -17.3 [-56.3, +21.7] (n 666) | -1.0 [-26.3, +24.2] (n 1316) | -0.3 [-8.5, +8.0] | -7.7 [-19.9, +4.5] | +7.4 [-7.3, +22.2] | +1.6 [-69.6, +72.8] (n 230) |
| 10 | +5.1 [-4.0, +14.1] (n 15438) | -7.7 [-22.9, +7.5] (n 15410) | +18.1 [-32.0, +68.2] (n 648) | -25.8 [-85.7, +34.0] (n 651) | -0.0 [-38.4, +38.4] (n 1299) | +3.8 [-8.0, +15.5] | -7.7 [-24.2, +8.8] | +11.5 [-8.7, +31.8] | -71.3 [-163.9, +21.3] (n 228) |
| 15 | +4.9 [-5.4, +15.2] (n 15427) | -5.4 [-21.2, +10.4] (n 15408) | +24.2 [-39.1, +87.5] (n 647) | -29.0 [-122.7, +64.7] (n 629) | +7.5 [-44.9, +60.0] (n 1276) | +5.6 [-9.7, +20.8] | -11.2 [-30.4, +7.9] | +16.8 [-7.7, +41.2] | -75.5 [-190.1, +39.0] (n 226) |
| 20 | +0.4 [-12.1, +12.9] (n 15424) | -8.1 [-24.0, +7.8] (n 15391) | +35.7 [-42.7, +114.2] (n 645) | -9.1 [-108.1, +89.9] (n 607) | +18.4 [-43.0, +79.9] (n 1252) | +4.9 [-13.1, +22.9] | -8.3 [-28.7, +12.1] | +13.2 [-14.0, +40.4] | -35.9 [-149.4, +77.6] (n 221) |

**By side (d), H = 10:** E up +4.1 [-17.1, +25.4] (n 7736); E down +6.0 [-12.3, +24.2] (n 7702); O up -10.4 [-59.3, +38.6] (n 652); O down +2.6 [-62.0, +67.2] (n 647)
**E tail, sessions 16–20:** -4.5 [-11.4, +2.5] (n 15424) → no change.

**Decision (primary, pooled H = 10): MEASURE.**

## Reading (post-run; the registered decision stands: MEASURE)

* **Precision as planned.**
  * Earnings: ±9 bp at H = 10 on 15,438 events.
  * Pooled: ±11.7 bp.
  * The question is answered to within about one round-trip cost of zero. It cannot be narrowed much further with
    this data.
* **Best estimate: hard news at the fund's speed is about break-even before the desk's own side.**
  * Pooled: +3.8 bp per 10-session trade against a 4 bp live cost. P(μ > 4) ≈ 0.49 and P(μ > 10) ≈ 0.15.
  * Earnings alone: +5.1 bp, which is +1.1 net at live cost and −4.9 at the registered 10 bp.
  * Same names on random days in the same month: −7.7 bp, a weekly reversal. So news days beat ordinary days by
    +11.5 bp [−8.7, +31.8]. That suggests a news-specific effect, but it is not significant.
* **On the desk's P&L basis** (`E_SOFT_DIAG.md` §4), the edge is (2a − 1)·μ.
  * The live hard entries agree with the news-day move 18/26 = 69% (decision ledger, Wilson [50%, 83%]).
  * That gives +1.4 bp gross per trade, −2.6 bp net at the live cost.
  * At μ = 3.8 no agreement rate breaks even (a\* = 1.03). At the upper bound μ = 15.5, a\* = 0.63, so a positive
    edge is not ruled out.
* **Timing.**
  * Earnings rise to about +5 bp by session 10–15 and are back to +0.4 bp at session 20.
  * The tail, sessions 16–20, is −4.5 [−11.4, +2.5]: negative but not below zero with confidence, so no cap (the
    registered rule).
  * This agrees with the gap study's sign after session 15.
* **Sides are symmetric:** up +4.1, down +6.0 bp.
* **Other hard news** (8-K items, Finnhub hard) is too noisy to say anything: ±38 bp.
* **Finnhub earnings news that is not the release** (previews, recaps): −71 bp [−164, +21], descriptive. It points
  towards reversal, consistent with stale news, but is not significant.

**What this means.** After the soft-news stop, the whole live book trades an activity whose expected edge, at the
fund's speed and on its own side, is within about a cost of zero. Costs are certain and the edge is not. That strengthens
two cases: cutting turnover (holding longer instead of re-entering, and no-trade bands), and putting effort into
components with a source the market does not see in time, which today means R5. It does not justify stopping hard
news. The interval allows up to +15 bp, and MEASURE keeps the decision ledger collecting the desk's own evidence.
