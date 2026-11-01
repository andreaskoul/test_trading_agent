# E3 pipeline check: Finnhub fit window 2025-11-01 – 2026-04-30 (descriptive; PREREG_family_E.md §4 E3)

Run 2026-11-01 (`family_e_soft.py check`, commit after cb543aa).

* **News.** 503 of 503 names, 839,173 articles, 2025-10-25 – 2026-10-31 (BRK.B, BF.B re-fetched, Amendment 5).
* **Shocks.** 3,539 (1,756 holdout). Labelled: all holdout shocks and a seeded sample of the fit window (3,000),
  plus the 27 shocks of BRK.B and BF.B: 3,027 shocks.
* **Classifier.** The fund's model, `deepseek/deepseek-v4.1-flash`, as registered (no free model qualified under
  Amendment 4: `E_SOFT_MODEL.json`). Valid labels 3,017; 10 missing after one retry (7 holdout, 3 fit). Cost $2.02.
* **Types.** analyst_revisions 729, other 494, macro_readthrough 382, partnership 340, dated_catalyst 207,
  legal_regulatory 174, earnings 158, product_launch 152, leadership 107, capital_return 102, mna_rumour 90,
  guidance 82. Hard share 0.30.
* **Fund-time lag L** = 1,377 min (95th percentile of the 105 late-served articles in the live news audit to date).
* **Fit window, soft shocks at the fund's entry:** n 444, mean y −29.5 bp, t −1.06 (week-clustered). Descriptive only:
  no decision uses it.
* **Content inspection** (CLAUDE.md rule 11): `E_SOFT_SAMPLE.md`, 50 random labels next to their first headlines.
