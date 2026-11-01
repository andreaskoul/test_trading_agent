# Rule A: soft-news entries (pooled holdout, read once)

Lock: 2026-11-01T18:42:56.189377+00:00 commit d6a40594e69ef0797f2054a88cb809a235f6bb06

KEEP iff the one-sided p of H0: mean <= 4 bp (the live round trip) is <= 0.10 and the desk's sides agree with the news-day move on >= 60% of its soft entries; otherwise STOP (PREREG_family_E.md rule A).

* Events: 8-K items 5.02/1.01, 2022-2025: 5722 (mean +11.0 bp); Finnhub soft shocks, 2026-05 .. 2026-10: 618 (mean 15.1 bp).
* Pooled mean of y (5 sessions after the fund's entry, in the news-day direction): **+11.4 bp**; p (H0: <= 4 bp) **0.0895** (cr1_week 0.0880, wild_week 0.0885, cr1_ind 0.0668, wild_ind 0.0684, cr1_two_way 0.0895).
* Desk agreement: 7/12 = 58%.
* Fund-time lag L = 1377 min (105 late-served articles).

**Decision: STOP.**
