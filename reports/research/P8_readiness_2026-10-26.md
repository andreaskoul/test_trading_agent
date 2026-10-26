# Protocol 8 readiness: what the tests can and cannot decide (2026-10-26)

Written before any Protocol 8 test was run, and before any P8 feature was computed on validation or sealed data
(PREREG_thesis_tree.md, Amendment 2's disclosure still holds). Nothing here changes the pre-registration. Section 6
lists the changes the owner can still make, before results, as a dated amendment.

Owner's question (2026-10-26): Protocol 7's weaknesses are visible now, so why wait for February? What is missing?

## 0. Summary

1. **The decision rule has almost no power.**
   * A monthly long–short signal needs a true annual Sharpe of about **2.0** for a 50% chance to pass validation
     and the sealed read.
   * At Sharpe 1.0, already an excellent post-publication anomaly, the pass rate is 7%.
   * The binding constraint is the 9-month sealed read, not the calendar.
   * The false-positive rate actually spent is about 0.25% per family, against the nominal 5%.
2. **Waiting for February is needed only for the LLM thesis desk (R3).**
   * The deterministic family H, the risk model H6 and the decay curves H8 use history and can run now.
   * The pre-registration already allows a P8 book without the LLM ("R3 fails and H passes → a deterministic network
     and filings book").
3. **Data gaps that bias results, measured:**
   * price coverage of S&P 500 member-days is 69% (2012) rising to 97% (2025) in the cached yfinance panel;
   * GICS is taken as of today;
   * the sector ETFs XLC and XLRE start mid-sample;
   * TNIC ends in 2023, exactly where the validation sample is split for the stability check;
   * quarterly EPS for Q4 must be derived.
4. **Under-specified parts of §8 (the horizon mechanics).** The "fixed margin" has no value, and the Q4 forecast
   model is not defined. If no H signal passes, H8 gives no half-life, so P8 has no horizon model.

## 1. Power of the decision rule (§2, §6)

**Model.** Monthly long–short returns are i.i.d. with mean μ and standard deviation σ. The monthly Sharpe is
SR_m = μ/σ = S/√12, where S is the annual Sharpe. Over T months, the mean's t-statistic is approximately N(δ, 1)
with δ = SR_m·√T. Newey–West with lag 3 changes the variance little when returns are serially uncorrelated.

**The registered rule** for one H signal tested as a monthly portfolio:
* validation, T = 48 months (2022–25): one-sided p < 0.05/7 at Holm's first step (the most lenient step);
* both halves (24 + 24 months) have the right sign;
* sealed, T = 9 months (Jan–Sep 2026): p < 0.05/k, Holm among k survivors (best case k = 1);
* the net long–short spread is > 0 on the deciding sample.

Write h₁, h₂ ~ N(SR_m√24, 1) for the halves' t-statistics. The validation t-statistic is (h₁ + h₂)/√2, and the
sealed one is t_s ~ N(SR_m·3, 1), independent of both. Then

P(pass) = P((h₁+h₂)/√2 > z_{1−0.05/7}, h₁ > 0, h₂ > 0) · P(t_s > z_{0.95})

computed exactly by Monte Carlo (200,000 draws; `power.py` below):

| true annual Sharpe | P(pass validation) | P(pass validation and sealed) |
|---|---|---|
| 0.25 | 0.026 | 0.002 |
| 0.50 | 0.073 | 0.008 |
| 0.75 | 0.170 | 0.027 |
| 1.00 | 0.326 | 0.071 |
| 1.50 | 0.708 | 0.259 |
| 2.00 | 0.938 | 0.501 |

**The sealed read alone.** Ignoring validation, 80% power in 9 months needs
SR_m ≥ (z_{0.95} + z_{0.80})/√9 = (1.645 + 0.842)/3 = 0.829, an annual Sharpe of 2.87. No published
cross-sectional anomaly has that Sharpe after publication.

**What Sharpe to expect.** By the fundamental law, the information ratio per period is IR ≈ IC·√N_eff.
* With a monthly rank IC of 0.02 (typical of published anomalies after decay; McLean–Pontiff find returns fall
  about 58% after publication) and N_eff ≈ 100 effectively independent names out of 500, SR_m ≈ 0.2, so S ≈ 0.7.
* The registered rule passes such a signal about 2–3% of the time. A null passes 0.04% of the time.
* So the expected verdict is "nothing passes" whether or not the signals work. That is the same failure the desk
  review found for Protocol 7's gate (8% power at Sharpe 0.5).

**Event-level tests do better** (H1 sympathy reversal, H3b inventory bullwhip, H4 geopolitical drift).
* The t-statistic of a slope is ≈ ρ·√(n/DE), where ρ is the signal–target correlation and
  DE = 1 + (m−1)·ICC is the Kish design effect for clusters of size m with intra-cluster correlation ICC.
* For 80% power at one-sided 0.05/7:

  | events n | cluster size | ICC | n_eff | ρ needed |
  |---|---|---|---|---|
  | 4,800 | 15 | 0.05 | 2,824 | 0.062 |
  | 4,800 | 15 | 0.15 | 1,548 | 0.084 |
  | 1,200 | 15 | 0.10 | 500 | 0.147 |

  Correlations of 0.06–0.08 are plausible for event reactions. The cost is the 9-month sealed read: its n is about
  a fifth of the validation n, so a signal at ρ* has a sealed power of about 0.35–0.45.

**R3, the LLM desk.** The pre-registration's own arithmetic (n = 900, centred hit rate 0.55, t = 3.0 per season)
assumes independent reports. Surprises are correlated within industry and season:

| hit rate | DE = 1 | DE = 2 | DE = 3 |
|---|---|---|---|
| 0.52 | 1.20 | 0.85 | 0.69 |
| 0.55 | 3.00 | 2.12 | 1.73 |
| 0.58 | 4.80 | 3.39 | 2.77 |

(t-statistic per season.) With DE ≈ 2 and a hit rate of 0.55, two seasons give t ≈ 3.0 pooled. That is enough, but
only if the true hit rate is ≥ 0.55, an optimistic prior for predicting the sign of the earnings surprise.

## 2. Data gaps, measured or verified

| # | gap | evidence | effect | fix |
|---|---|---|---|---|
| D1 | **S&P 500 survivorship in prices.** The cached yfinance panel (`sp500_close.parquet`, 2009–2025) has prices for 606 of the 814 index members since 2012. | Member-day coverage: 68.5% (2012), 73% (2015), 81% (2018), 88% (2021), 90% (2022), 95% (2024), 96.6% (2025). | Missing names are disproportionately acquired (positive returns into announcement) or failed. Bias in a long–short spread: E[r ∣ observed] − E[r] = −Cov(r, 1{missing})/P(observed). Its sign depends on how the signal correlates with exit, so it is not controlled by a long–short design. | (a) Many "missing" names are ticker changes or download failures, not delistings: BK, AVB, CMA, CASY, CTRA, and BLL (now BALL). (b) Alpaca's SIP bars include delisted symbols from 2016-01-04 to their last day: ATVI to 2023-10-13, CELG to 2019-11-20, SIVB to 2023-03-09 (all checked). Done (`research/p8/prices.py`): with ticker changes resolved by CUSIP through Alpaca's corporate actions (BLL→BALL, ANTM→ELV, JEC→J, …), coverage is 98.4% (2016), 99.4–100% (2018–25), and 99.8–100% across validation. 2012–15 (fit only) stays at 69–74% and is reported (`reports/research/p8/D1_coverage.md`). |
| D2 | **Delisting returns.** | Not in any free source. | The last traded price is used. For S&P 500 cash acquisitions the error is small; for failures (rare in the index) the final loss is understated (Shumway 1997). | Report the count of names that leave by delisting, per year. |
| D3 | **GICS as of today** (`sp500_current.csv`, `chains.json`). | GICS was restructured on 2018-09-28 (Communication Services created; GOOGL, META, NFLX, DIS and others moved) and in March 2023 (V, MA, PYPL to Financials). | Season × sector fixed effects, sector residuals and funnel stages all use a 2026 classification on 2012–2025 data. That is look-ahead in the fixed effects, and the 2018 move changes the sector ETF a name is residualised on. | Point-in-time GICS is not free. Either map backwards with the published 2018 and 2023 changes, or state the bias and report a "GICS 2017 sectors" robustness row. |
| D4 | **Sector ETFs for e** (§1). | XLRE starts 2015-10, XLC starts 2018-06. | e is undefined for Real Estate before 2015-10 and Communication Services before 2018-06, inside fit (both exist for all of validation). | Before inception, use the pre-2018 parent ETF (XLK/XLY for Communication Services, XLF for Real Estate) and flag the rows. |
| D5 | **SUE history.** | XBRL begins with periods after June 2009 for large accelerated filers and 2011 for the rest. SUE needs EPS back to q−12, with ≥ 6 of 8 differences. | The first SUE is about 2011Q4 for large caps and about 2014 for smaller filers. S&P 400 fit-period SUE is thin. | Count firm-quarters with SUE per year before any test. |
| D6 | **Q4 EPS.** | 10-Ks report the fiscal year, not Q4. | Q4 = FY − (Q1+Q2+Q3) is wrong for diluted EPS when the share count changes. | Use net income and diluted shares (Q4 NI / Q4 average diluted shares); flag the derived rows. |
| D7 | **TNIC ends in 2023.** | Hoberg–Phillips data covers 1989–2023 (plan). 2024–26 peers come from own embeddings (S1). | The stability check splits validation into 2022–23 and 2024–25, exactly at the change of peer method. A sign change between halves cannot be told apart from the method change (H1, H2b). | Report H1 and H2b on both peer methods over 2022–23, where both exist. |
| D8 | **Text corpus.** | `eloukas/edgar-corpus` has 10-K sections 1993–2020, not 10-Qs. | H5 (Lazy Prices) on 10-Q MD&A needs the EDGAR parse for every year. | Parse 10-Qs from EDGAR HTML for 2010+; validate on 50 filings as §1 requires. |
| D9 | **S&P 400 membership.** | Current list only (2026-10-14). | Survivorship for the whole S&P 400 arm, stated in §1. It biases toward firms that stayed mid-cap or survived, and away from those that were promoted, demoted or failed. | Wikipedia's change log can rebuild a partial point-in-time list; report coverage. |
| D10 | **Replication checks.** | Cohen–Frazzini 1981–2004 needs 10-K customer disclosures (EDGAR full text only from 1993–96) and delisted returns (CRSP, not free). | The "replicate the published sign" gate cannot be run on its published period with free data. | Replicate on 1997–2011 with the text available, survivorship stated; or replace the gate by the placebo checks already registered. |

## 3. Under-specified parts of §8

1. **"Round-trip cost + a fixed margin."** The margin has no value. With α_t decaying exponentially,
   α_t = α₀·2^(−t/τ), the holding time is t* = τ·log₂(α₀/(c + margin)). So the margin directly sets the
   horizon. It must be fixed before any α is estimated, or it becomes a free parameter tuned by the results.
2. **The Q4 forecast** ("thesis ⊕ deterministic signals, residualised … shrunk") has no registered functional
   form, shrinkage target or weights.
3. **Half-lives exist only for passing signals.** H8 fits decay "for each passing signal and, for LLM evidence,
   each event type". If no H signal passes, and R3 cannot be read until ≥ 2 seasons, P8 has no α_t, no τ and so
   no horizon.
4. **Mechanical expiry** ("8 weeks with no supporting evidence and α below the hurdle") is consistent with 2.
   It is the only horizon rule that does not depend on test results.

## 4. The horizon question (structural vs event theses)

The owner's claim is that some theses need more than a month. It is a statement about the shape of IC(h), the
correlation between a signal at t and the residual return over (t, t+h]:
* An event-driven signal has IC(h) that peaks early and flattens: the information is priced in days.
* A structural signal has IC(h) still rising at h = 40–120 sessions: the information diffuses slowly (Hong–Stein
  1999; Cohen–Frazzini 2008).

H8 estimates exactly this, for h ∈ {1, 5, 10, 20, 40, 60, 90, 120}, on fit data. It needs no forward season and
no LLM, so it can be run now. It is the direct test of the owner's hypothesis, and it should come before any
change to holding periods.

**The fund's evidence so far** (technicals backtest, 8,924 news-gap events, 2012–25): no drift to 20 sessions, then
reversal for longs at 30–60 sessions (t −2.4 to −2.8). That is evidence against holding longer when the view is
the gap direction. It is not evidence about filings-based or cross-firm signals, which is what family H tests.

## 5. Other gaps

* **Program-level multiplicity.** The research programme has run the technicals tests (5), the quant trials,
  the transformer arms (12, one pass: MASTER h5, Holm p 0.013) and now H (7). Each family controls its own
  error rate; nothing controls the total. Report the trial ledger's count (Amendment 2 §1) with every result.
* **Costs for the S&P 400.** 10 bp round trip is the measured S&P 500 paper cost (0.8 bp slippage at the
  close). Mid-cap spreads are wider. The net long–short spread should also be shown at 20 and 40 bp for the
  S&P 400.
* **Borrow.** Alpaca's easy-to-borrow list is current, not historical. Short legs on hard-to-borrow S&P 400
  names are not tradable in practice. Report the short leg with today's ETB filter as a robustness row.

## 6. Changes the owner can still make before results (each needs a dated amendment)

Computed with the same model (P(pass validation and sealed); null = per-signal false positive):

| annual Sharpe | registered | sealed: right sign only | pooled 57-month test | sealed sign + validation 2017–25 (108 months) |
|---|---|---|---|---|
| 0.50 | 0.008 | 0.049 | 0.086 | 0.114 |
| 0.75 | 0.028 | 0.127 | 0.204 | 0.312 |
| 1.00 | 0.070 | 0.263 | 0.389 | 0.570 |
| 1.50 | 0.257 | 0.639 | 0.789 | 0.885 |
| null | 0.0004 | 0.0038 | 0.0069 | ≈ 0.004 |

1. **The sealed read checks the sign, not significance.** Validation keeps Holm. The holdout must not reverse.
   Power rises about 4×, and the false-positive rate per signal stays below 0.4%.
2. **A longer validation sample** (2017–25) needs fit to end in 2016, which leaves 2012–16 for fitting half-lives
   (5 years; XBRL makes earlier years thin). It is the largest gain for monthly signals.
3. **Prefer event-level primaries** where the hypothesis allows it (H1, H3b, H4 already are). They have
   thousands of observations instead of 48 months.
4. **Fix §8's margin** and the Q4 functional form now (section 3).
5. **Fix the data gaps** D1, D3, D4 and D7 by rule, before results.

None of these changes a hypothesis or its direction. They change how much evidence a true effect needs to pass.
Choosing among them is the owner's decision. Once any validation statistic has been computed, they can no longer be
made.

## Appendix: `power.py`

The Monte Carlo and closed forms above are in `reports/research/p8_power.py` (seed 7, 200,000 draws).
