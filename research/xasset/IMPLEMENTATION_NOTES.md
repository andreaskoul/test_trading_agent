# Cross-asset trend read: implementation notes (2026-11-25)

Code: `xasset_lib.py` (loaders, constructions, `PRE2003_GUARD`), `xasset_checks.py` (the §3 gate →
`CHECKS_XASSET.json`), `xasset_read.py` (§4–6; `--synthetic` dry run → `SYNTHETIC_XASSET.json`), `test_xasset.py`.
Registration: `PREREG_XASSET.md` (dd2a819). Where the registration leaves a point open, the simplest reading was
taken. Every item below is an **implementation choice, made before the read**. The items in part A were also made
before the gate (`xasset_checks.py run`) was first run. Nothing was tuned. No threshold, window or rule was changed
after a check statistic was seen.

## 0. How the 1962–2002 sleeve stays unread

* **One guard.** `PRE2003_GUARD` in `xasset_lib.py` is used by every loader of real non-equity data (`raw`) and by
  every return, signal, position or statistic series (`derived`).
  * Outside an authorised mode, `raw` keeps only dates on or after 2003-01-01. `derived` raises `Pre2003Error` on any
    earlier date and registers the series.
  * proxy.py's own mask (`validation_window`) stays on. Only `read()` and the synthetic run lift it.
* **Modes that can see pre-2003 data:**
  * `level_check()`: entered only from `pre2003_level_counts` (§3.2). It sees levels and returns counts only;
    `derived` still raises in this mode.
  * `coverage()`: entered only from `coverage_counts` (§3.4). Loaders return 1.0/NaN presence, never a value.
  * `read()`: entered only from `run_read`. It creates `READ_XASSET.lock` with `O_EXCL` before any data is loaded,
    and refuses if the lock exists.
  * `synthetic()`: real-data loaders raise.
* **Content contracts.** Range, typed-field and date contracts run inside the loaders, on all dates. They report
  pass/fail and a count; they never report a value.
* **Disclosures.** While I was inspecting file layouts, two header previews printed pre-2003 levels. No statistic
  was computed from them.
  * The first row of the BoE 1970 workbook (1970-01-31 short-maturity spot yields).
  * The first rows of files already disclosed in `FREE_DATA.md` §8: Bundesbank 10y 1972-09; SNB rendoblim 1988-01;
    SNB call money 1972-01; the MoF 1974-09-24 row.

  Two further ad-hoc looks were blocked by the session's permission system before they ran, and were not retried
  outside the guard:
  * a count of where the SNB range violation lies;
  * a look at raw Bund timestamps.

## A. The gate (§3)

1. **Second source for commodities (§3.1).** yfinance continuous futures (`XX=F`) where Yahoo lists the same
   contract (21 markets; mapping `xasset_lib.YF`). Files are fetched from 2003-01-01, so they hold no pre-2003 value.
   No commodity kept after §3.3 has a CHRIS-style mirror without also having a yfinance listing. A market with
   neither source cannot be validated: it is **dropped**, with the reason "no second source".
   * Affected: CANOLA, GASOIL, SUGAR_WHITE, COCOA_LDN, WHEAT_ICE, MILKWET, MILLWHEAT.
2. **Roll days in the second source (§3.1, on spent 2003+ data).** Yahoo has no contract label.
   * On each session, the Yahoo close is matched to the pysystemtrade contract (PRICE, CARRY or FORWARD, typed
     labels) whose settlement is nearest, if within 0.5% (the §3.2 tolerance). Otherwise it is unidentified.
   * A session is a roll day, and is excluded on **both** sides, unless the same contract is identified on it and on
     the previous common session.
   * Monthly returns compound the remaining common sessions. Both sides use the same sessions.
   * The pysystemtrade side is the registered construction (Δ back-adjusted / held price).
3. **Pre-2003 level check (§3.2).** "Both hold the same contract" is decided from the calendar, never from prices,
   so that the count cannot be made to agree by construction.
   * The mirror is taken to hold the Quandl CHRIS #1 contract: the nearest contract of pysystemtrade's
     `PricedRollCycle` not yet expired.
   * Expiry is the 1st of the contract month plus `ExpiryOffset` days (typed `rollconfig.csv` fields).
   * The pysystemtrade price compared is the column (PRICE, CARRY or FORWARD) whose contract label equals that
     contract.
   * Sessions within ±5 calendar days of any inferred expiry are roll days and are excluded.
   * Counts: per market and decade, the common sessions, the same-contract sessions, and the sessions agreeing within
     0.5%. A market with fewer than 95% agreeing is dropped.
   * A market without a mirror file, or with no same-contract pre-2003 session, is recorded as "not applicable" and
     is not dropped on this ground.
   * The same counts for 2003–2019 (spent) are reported alongside as a diagnostic only.
4. **Splices and variants (§3.3).**
   * GASOILINE (RBOB with unleaded inside) is excluded.
   * Single-month hold cycles in the shipped `rollconfig.csv` are excluded. The registered "December-only" rule covers
     CORN, WHEAT and CRUDE_W (Z). SOYBEAN (X, November-only) has the same defect, a deferred contract that is not
     MOP's front, so it is excluded too.
   * Minis and micros are never used: each market is its full-size file.
   * US rate futures, STIRs (Euribor, Fed funds, SOFR) and pysystemtrade FX futures are outside the registered
     universe.
5. **Currencies.**
   * JPY: H.10 spot, with the BoJ collateralised overnight call rate (end of month, typed in the series name) against
     the OECD US 3m rate; checked against FXY.
   * CHF: H.10 spot with SNB call money (tomorrow-next, `1TGT`); checked against FXF.
   * DEM: BIS WS_XRU Germany daily (euro units; USD per unit = 1 / value) with the OECD German 3m rate; checked
     against the euro proxy (proxy.py EUR, validated against FXE).
   * GBP, AUD, CAD and the US 5y and 10y are re-run through `proxy.run_validation()`, and must reproduce
     `VALIDATE.json` exactly.
   * NOK, SEK and DKK have no registered comparator. They use the same construction as the validated currencies and
     enter "where covered".
6. **Non-US bonds.**
   * The 10-year maturity everywhere, matching the 10-year futures they are checked against:
     * UK: BoE GLC spot curve, used as the par yield;
     * DE: Bundesbank Svensson;
     * JP: MoF par yields, month-end sampled;
     * CA: StatCan benchmark (last Wednesday, indexed to the month end);
     * CH: SNB Confederation.
   * Financing is the local short rate: OECD 3m (UK, DE), BoJ call (JP), StatCan 3m T-bill (CA), SNB call (CH).
   * Construction: `proxy.treasury_excess` with monthly = True.
   * Comparator: the pysystemtrade future's monthly excess return (Δ back-adjusted / held price, compounded).
     BUND was not in `FREE_MANIFEST.json`. It was fetched from the same pinned commit (`bbf5cf8`) and frozen in
     `XASSET_MANIFEST.json`.
7. **Plausible-range contracts.** Short rates use proxy.py's rate range [−2%, 60%]; yields use [−2%, 25%].
   * A first draft used [−3%, 25%] for SNB call money and flagged one value. The draft was replaced by the project's
     existing rate contract before any check statistic. Under that contract the series still fails (1 value outside
     [−2%, 60%]). It is an **input defect**, so CHF and the Swiss bond proxy (financed at SNB call money) cannot be
     built as registered and are dropped.
8. **pysystemtrade intraday rows.** Recent years carry several stamps per date. The date's last stamp is taken as its
   observation. Stamps must strictly increase.
9. **Coverage contract (§3.4)**, on presence only:
   * a month counts if every level input of the market has a valid month-end observation (a rate for the month in
     which the period starts, for currencies);
   * a market fails if fewer than 95% of the expected month-ends, from its first complete month to 2002-12, are
     present;
   * a market with no pre-2003 month passes the gate but cannot enter the read.
10. **Minimum overlap for a §3.1 statistic:** 37 common months on 2003+. Below that the check is not evaluable and
    the market is dropped ("not validated").
11. **Gate status.** "pass" means every registered check was evaluated, the frozen files verified, the core
    reproduced `RESULT_CAPITAL.json` to 1e-6, the VALIDATE reruns matched, and each asset class keeps at least one
    market. Markets that fail are dropped and recorded; that does not fail the gate. `xasset_checks.py` exits
    non-zero if the gate cannot be evaluated.
    * Wording fixed after the first run, with no rule changed: an evaluated gate that misses the last condition is
      labelled "fail" (exit 1), not "cannot be evaluated" (exit 2). The rerun reproduced the first run's markets,
      level counts and coverage exactly.

## B. The read (§4–6)

1. **Monthly returns.**
   * US Treasuries and currencies: proxy.py's monthly constructions (as validated).
   * Commodities: daily pysystemtrade excess returns, compounded within calendar months. A return over a data gap is
     kept.
   * Non-US bonds: monthly constructions.
   * A missing differential drops that month for that market (typed defect).
2. **σ̂.**
   * Daily markets: `ewm(com=60).var()` of daily excess returns (EWMA-demeaned, as MOP), × 261, at the last session of
     the month. The daily series are proxy.py's daily constructions and pysystemtrade's daily returns.
   * Non-US bonds (month-end only): the rolling sd of monthly returns over up to 36 months × √12. At least 13 months
     are needed, so that the registered entry rule (13 months of returns) applies to every market.
3. **Signal and entry.**
   * Signal: the sign of the compounded return over the past 12 months, which must be consecutive.
   * A market's first position is at the end of the month in which it has 13 monthly returns. Each position is held
     over the next month.
   * Equal weights within each class are over the markets with a position at t and a return in t+1. The return's
     existence is data availability, not information.
4. **Vol scaling.**
   * Scale: 10% / (sd of the past 36 months of the unscaled gross sleeve × √12), from month 37 of the sleeve.
   * The AR and all regressions use the **unscaled** sleeve. This is the reading under which the registration's
     "the AR does not depend on that last scale" is exactly true. The §6 allocation uses the scaled sleeve.
5. **Costs.**
   * Charge: rate × |w_t − w_{t−1}| on the final notional weights, with entries from and exits to zero counted. No
     drift adjustment.
   * When: charged in the month the new position is held. The rate is that of the trade date's year.
   * Rates:
     * bonds: 0.06% to 1992, 0.02% 1993–2002;
     * currencies and commodities: 0.18% and 0.06%.
   * Sensitivity: 2× costs.
6. **Core.**
   * `capital.item1_long()` on the frozen French file, checked against `RESULT_CAPITAL.json` to 1e-6.
   * Monthly excess return: the compounded arm-M-under-R return minus the compounded T-bill, per calendar month,
     1962–2002.
7. **Regression.**
   * OLS of the monthly sleeve excess on the core excess (or the core and the US 10y proxy).
   * σ(ε) = √(SSR / (T − k)).
   * AR = α / σ(ε) × √12.
   * SE(AR) = Newey–West(6, Bartlett, no small-sample factor) SE(α) / σ(ε) × √12.
8. **Bootstrap.**
   * Stationary bootstrap (Politis–Romano, geometric blocks, mean 12) of the paired monthly rows.
   * One set of 10,000 index draws from `numpy.random.default_rng(20261125)` is shared by all specifications on the
     same months.
   * The interval is the 5th and 95th percentiles.
9. **Verdict.**
   * Supported: the 90% lower bound > 0 at registered costs against both benchmarks.
   * Rejected: the 90% upper bound < 0.15 against the core at registered costs. The core is the quantity of §1.
   * Inconclusive otherwise.
10. **Posterior.**
    * Prior: N(0.48, 0.20²).
    * Normal–normal update with the primary AR and its Newey–West SE (registered costs, against the core).
    * The forward planning AR is 0.555 × the posterior mean, with sd 0.555 × the posterior sd.
11. **Diagnostics.** Each is a rebuilt sleeve, reported as AR and Newey–West SE, with no bootstrap:
    * rates only (US and non-US bonds);
    * rates and currencies over 1972-01..2002-12;
    * commodities only;
    * the primary sleeve by decade.
12. **Cross-market correlation.** The mean pairwise Pearson correlation of the markets' unweighted trend returns
    (position × return), using pairs with at least 24 overlapping months. It is reported overall and by class pair,
    next to ρ = 0.1 and MOP Table 4.
13. **Worst months.** The sleeve–core correlation over the months in which the core's excess return is at or below
    its 10th percentile.
14. **Constrained contribution (§6).** This is in-sample and descriptive.
    * Fund: the core (weight 1, its policy weight) + w_t × the 10%-vol sleeve (net of registered costs).
    * w* is the unconstrained Sharpe-maximising weight on the sleeve, given the core at 1, clipped at ≥ 0. In each
      month, w_t = min(w*, cap_t).
    * Exposure rule (i): e_t + w_t·N_t ≤ 1.9, where e_t is the core's exposure at the month's first session and N_t
      is the sleeve's gross notional.
    * Exposure rule (ii) has three limits:
      * e_t + w_t·Σ|n_i|σ̂_i/σ̂_mkt ≤ 1.9;
      * 3·(e_tσ̂_mkt + w_tΣ|n_i|σ̂_i)/√12 ≤ 0.25 (all legs adverse at 3 sd);
      * e_t + w_t·N_t ≤ 6.
    * σ̂_mkt is the same EWMA estimator on the French daily market.
    * Reported: the core and fund Sharpe ratios, their difference, w*, the mean w_t, the share of months capped, and
      the largest notional under (ii).
15. **The synthetic dry run** (`--synthetic`) runs the same `run_all` → sleeve, cost, regression, bootstrap and
    verdict code on generated data. No real file is opened and no lock is written.
    * The generated data:
      * business-day random walks for 1962–2002;
      * 12 markets (bonds 4, of which 2 month-end-only; currencies 4; commodities 4);
      * a core built by capital.py's 200-day rule on an independent random-walk index.
    * The planted trend adds, each month, κ·sign(past 12-month return)·(monthly sd) to the drift. κ = 0.3/12 is
      chosen so that the sleeve's gross AR is 0.3.
    * A null world has κ = 0.
    * The "true" AR of each world is the mean over 100 independent same-design replications (seeds 1001–1100), net of
      costs and gross. The dry-run estimate uses seed 20261125. Both worlds share that seed's noise draws, so their
      errors are correlated.
16. **Currency leg start.** Currency data are used from 1972-01 (the §2 table's "From 1972"), whatever a source's
    first date. Otherwise DEM (BIS spot with the OECD rates from 1964) would enter under the Bretton Woods pegs, where
    σ̂ ≈ 0 and positions explode. Other legs start at their data.
17. **Room for amended tests.** `ADDITIONAL_TESTS` in `xasset_read.py` takes functions `f(panel)` registered by a
    later dated amendment. Each reads the same guarded panel (monthly and daily returns per market, the core, the US
    10y) inside the same lock, without touching the primary path. It is empty now.

## C. What the gate found (first run, fda0b87; rerun identical)

* **Gate: fail.** No commodity survives, so A11 is not met, and `xasset_read.py` refuses to run. Nothing was re-scoped.
* **Pass:**
  * US5 and US10;
  * GBP, AUD, CAD (VALIDATE reproduced exactly);
  * JPY with the BoJ call rate against FXY: ρ 0.995, bias +0.15%/yr, agreement 100%;
  * DEM against the euro proxy: ρ 0.984, bias −0.07%/yr, agreement 97.6%;
  * NOK, SEK and DKK (no comparator registered).
* **Fail:**
  * CHF and the Swiss bond: the SNB call-money range defect.
  * The UK bond: bias −1.37%/yr.
  * DE: bias −1.06%/yr and agreement 86.9%.
  * JP: ρ 0.932, TE 0.47, agreement 86.0%.
  * CA: ρ 0.927, TE 0.42.
  * All 28 commodities:
    * 7 have no second source;
    * 16 of the 21 compared with yfinance fail §3.1 (most often bias above 1%/yr or a switch difference above 0.5
      a year);
    * every market with a mirror and pre-2003 overlap fails §3.2: 6–40% agreement, with SILVER 93.5%, COPPER
      89.8% and PLAT 75% (on 8 sessions) the closest.
* **Diagnostic on spent 2003–2019 levels**, added after the run; it decides nothing (`CHECKS_XASSET.json`,
  `diagnostic_mirror_convention_spent_2003_2019`).
  * The mirror is within 0.5% of pysystemtrade's *held* contract on 33–91% of sessions, and within 0.01% on only
    7–58%.
  * So the two free sources disagree on levels even where returns may be read. The mirror also more often carries the
    held contract than the nearest-expiry contract that choice A3 assumed.
  * The §3.2 drops therefore reflect both the sources' disagreement and the A3 calendar. Separating the two needs a
    new, dated rule. That is the owner's decision; it is not taken here.
