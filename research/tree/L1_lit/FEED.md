# L1 findings fed to each leaf (2026-11-13)

*What the coordinating session sent to each branch after the L1 review. A successor agent resuming a branch reads its
`STATE.json` and the section for its branch here. Every adopted variant is added to `plan` before it is scored.*

## Common to all leaves
* Development panel survivorship (verified): 241 of 738 ever-eligible names unpriced; 23.5% of eligible name-weeks
  without a target. Judge by paired differences against the declared control on the same rows; state it in REPORT.md.
* Seed noise (Qlib 20-seed benchmarks: ICIR ±0.05, IR up to ±0.46): re-score a nominated candidate with seeds 0-9.

## Q1_seqnet
* Per-stock trailing-63-session volatility scaling of return windows vs per-date z-score (Chen et al. 2026: centering
  price channels drove their gain; scale-only did not help). Expect possibly null.
* Missing-indicator channel vs NaN→0 (Bryzgalova-Lerner-Lettau-Pelger).

## Q2_xsattn
* MASTER/Qlib conventions: per-day ranked or z-scored label, listwise loss; RobustZScoreNorm + Fillna inputs.
* Module-vs-ablation pairs re-scored with seeds 0-9 before concluding.
* Chen-Pelger-Zhu: flexible models mainly fit small stocks; expect small effects on S&P 500 names.

## Q3_rankgbm
* Poh et al.'s ranking gains were against a weak MLP without costs; expect far less against squared-error trees.
* Huber loss (Gu-Kelly-Xiu: Huber versions perform better): keep lgb_huber.
* Native-NaN plus missing indicators for long-window features vs NaN→0; ranked Z vs clipped z-score.

## Q4_portfolio
* Net-of-cost objective (Jensen-Kelly-Malamud-Pedersen 2025): report turnover, gross and net for every row.
* Profit concentration (Avramov-Cheng-Metzker; Gu-Kelly-Xiu VW 1.35 vs EW 2.45 Sharpe): split net return by a size or
  volatility proxy and by high- vs low-volatility weeks.
* Volatility management: fix the estimator a priori or on 2013-2016; report 2017-2019 separately.
* Missing failed names and dropped delisting returns may bias the short leg and drawdowns; disclose.

## Leaves run by the coordinating session
* L3.1 read: Amendment 4 (unadjusted prices for eligibility; delisting-kept and size-tercile ICs reported).
* N4_news (not started): headlines only; sparse coverage (median 57 articles per name-year); missing-news weeks must be
  an explicit state (indicator), not a zero tone; score by paired increment over MASTER; report by size tercile.
* Queued: development-panel survivorship repair (Alpaca bars for the missing names, 2016 on).
