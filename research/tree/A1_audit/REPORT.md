# A1 audit: inputs whose availability depends on survival to today (2026-11-14)

*Read-only audit by a branch agent; saved by the coordinating session because agents' REPORT.md writes are
refused. An in-project reading by a separate AI session, not an outside review. All ICs are on spent periods
(2013-2025). Labels: [code] read in code, [comp] computed, [reas] reasoning. Check scripts: `a1.py`, `a2.py` (this
directory) plus two inline runs not saved.*

## Headline findings

1. **The broad universe is not survivorship-free; it carries the reverse bias.** [code + comp]
   * The rule (Amendment 1; `panel_broad.py:54-58`; `h7_build.py:312-318`) excludes, in every year 2017-2025, the
     850 S&P 500 panel names and the 346 current S&P 400 members: both lists fixed with hindsight.
   * Under a point-in-time version (top 1,500 by dollar volume, excluding only names that were S&P 500 members at t),
     the excluded names are 28.9% of the top 1,500 each week.
   * Being excluded predicts 5-day forward returns: IC +0.0281 (t 9.36, 455 weeks). Current S&P 400 members alone
     +0.0187 (t 6.45); S&P 500-panel names while not yet members +0.0184 (t 9.83).
   * So the scored universe removes names that later joined an index (future winners). The effect on rank IC has no
     known sign; book return levels are probably biased down [reas].
   * Affected: the L3.1 read (step 13), H7_DECOMP's pooled broad book (Sharpe 0.79 at 5 bp, 0.37 at 14 bp,
     2017-2026), the H7 broad side for 2017-2025 history. Q4/Q6 use the S&P 500 development panel [code, coordinator
     check], not the broad panel. PREREG called the universe "survivorship-free".
2. **Broad-universe attrition looks incomplete in some years.** [comp; cause reas] Share of names eligible on a
   year's first Thursday whose last bar falls in that year: 2017 0.1%, 2018 1.9%, 2019 6.1%, 2020 5.0%, 2021 6.2%,
   2022 4.9%, 2023 0.3%, 2024 0.1%. Near zero in 2017, 2023, 2024 is implausible for 1,500 liquid names (rate not
   verified). Likely causes: delisted names missing from Alpaca's inactive list; the 59 dropped `*_DELISTED` symbols;
   recycled symbols.
3. **The S&P 400 IPCA pass (M2) cannot be told apart from survivorship.** [comp + reas] Reproduced: IC 0.0183,
   t 2.17, 332 names/week. Holm margin: p 0.0149 vs 0.0167, so t must stay above about 2.13, i.e. an IC inflation of
   about 0.0004 would flip it. On the S&P 500 columns 2019-25 the same cached predictions score 0.0130 (t 1.22,
   point-in-time eligible) vs 0.0142 (t 1.32, current members only): survivor restriction adds +0.0012, about 3× the
   margin. The S&P 400 panel conditions harder on survival (all 346 scored names trade to Dec 2025; leavers absent).
   Verdict: valid under its registered test, not robust to survivorship.
4. **`construct.py` S0 uses neither `sec` nor `grp`** [code] (`:65`, `:73` only in C1/C2; S0 at `:92`). All fund-side
   simulations (OOS_RETURNS, COMBO_CHECK, H7 fund side, H7_DECOMP fund side) are unaffected through sectors.

## Availability-indicator ICs (Spearman of a 0/1 indicator with y5, NW t, 4 lags) [comp]

| Indicator | Dev 2013-19 (353 wk) | Holdout 2020-25 (303 wk) |
|---|---|---|
| in `sp500_current.csv` | +0.0287 (t 5.01) | +0.0266 (t 5.29) |
| in `gics.json` | +0.0149 (t 3.85) | +0.0208 (t 5.13) |
| events sector known | +0.0138 (t 4.03) | +0.0177 (t 4.78) |
| intraday bars available, 2016-19 | +0.0255 (t 3.20) | n/a |
| 10-K peer vector available (M5) | +0.0085 (t 2.46) | n/a |
| XBRL any field / revenue_0 | +0.0004 / +0.0059 (t 1.62) | any −0.0024 |
| `sue` available | +0.0002 | −0.0015 |
| FINRA volume available | −0.0009 | n/a |
| ticker in `decay_earnings_events` | +0.0023 (t 0.93) | n/a |

XBRL/events availability is near zero because almost all no-CIK names are already unpriced: the survivorship sits in
the price gap, not in XBRL coverage. MASTER takes no membership input [code].

## Classification (a leak into a prediction or the scored set; b bias disclosed; c bias undisclosed; d harmless)

* **c, material:** broad-universe exclusion (finding 1); broad delist coverage by year (finding 2); broad ETF flags
  (only currently listed ETFs flagged, so dead ETFs remain as "stocks"; probably small); quant_trials
  `sector_neutral_ic` "unknown" group; p8 residuals (sector-ETF residual only for current-list names); regime SECMOM
  sectors; qshadow 2018-25 backfill (research shadow only).
* **a, undisclosed, no claimed gain affected:** sharpe C1/C2 "Unknown" group; M5 peer features (no vector → 0);
  quant_trials TFT static sector, Chronos-2/Timestral sector grouping.
* **a, disclosed:** Q7 GICS features (gain already attributed to the leak); Q8 'NA' group (its IC cost may partly be
  removed NA-level information).
* **b:** S&P 500 price panel (23.5% eligible name-weeks unpriced 2013-19, 7.6% 2020-25); S&P 400 panel (M2/M4/X1ref;
  cost to the pass undisclosed until now); N3 intraday; p8 families; eventrisk; riskfield.
* **d:** S0 fund construction; N1 fundamentals; N1 sue; M6; FINRA; Q7 announcement masks; MASTER; live fund desks
  (`screen.py`, `r5.py` use current lists only forward).

## Ranked fixes (from the audit)

1. Broad universe: dated correction of "survivorship-free"; future builds exclude only by membership at t; drop
   exactly the already-read (name, week) pairs rather than names in every year; recompute the pooled book
   descriptively on that universe.
2. M2 pass: annotate "Holm margin ≈ 0.0004 IC; survivor restriction adds +0.0012 on the S&P 500 analogue; not
   robust"; the point-in-time forward book decides.
3. Broad data completeness: count delistings per year against SEC Form 25; check the 59 `*_DELISTED` symbols against
   the 2017/2023/2024 gaps.
4. A survivorship contract for any new input: availability-indicator IC on dev, reject if |t| ≥ 2; no "NA/Unknown"
   groups that are a function of current-list membership; point-in-time SEC `sic` for sectors.
5. Disclosure footnotes (no reruns) for the class-a/c items above.

## Checked and unaffected (beyond disclosed price-panel survivorship)

OOS_RETURNS, COMBO_CHECK, fund side of H7_RESULT/H7_DECOMP; phase-1 finalists and branches A-E, X1-X5, M1-M4 dev,
Q1-Q6 (price and FINRA inputs only); N1; N2; M6; quant_trials MASTER; eventrisk passes; live fund desks.
