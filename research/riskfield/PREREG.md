# Risk measurement and peer-field signals: pre-registration

*Written 2026-11-07, before any statistic in this file was computed. Owner's brief: find statistically robust
improvements in risk measurement (volatility, beta), and alphas if any. Themes: local stationarity as regimes,
McKean–Vlasov (mean-field) interaction through an embedding space, and HAR in embedding space for news (the attached
case). Nothing here trades. 2026 data are not read: every loader filters to dates ≤ 2025-12-31.*

## 1. Idea in one paragraph

A McKean–Vlasov process lets each particle's drift and diffusion depend on the law of the population. Discretised
on a panel of stocks, it becomes an interacting system: stock *i*'s future volatility, beta or return depends on its own
past (HAR) and on a **field**, a kernel-weighted average of its neighbours' states. The kernel defines who the
neighbours are: the same GICS sector (baseline), similar 10-K business descriptions (a point-in-time text embedding),
or similar recent co-movement. "Local stationarity" enters in two ways: forecasting coefficients estimated with
exponential forgetting instead of an expanding window, and coefficients that switch with a market-variance regime.

## 2. Data (all filtered to ≤ 2025-12-31 at read)

* **Intraday bars:** the owner's Stock2Vec cache, `bars_20160101.parquet`: 30-minute bars for about 500 current S&P
  500 names plus SPY, from 2016. Regular session only (bars starting 09:30–15:30 ET, 13 bars). A name-day with
  fewer than 13 regular bars, or any 30-minute |log return| > 0.4, is an input defect and is missing. The universe is
  the current constituents (survivorship: disclosed; it matters little for risk targets, and the P tests compare
  hedges or weightings on the same names).
* **Daily closes, point-in-time members:** `.cache/quant_trials/sp500_close.parquet` and
  `data/raw/stocks/sp500_membership.csv` (as in `research/regime`), for the alpha tests.
* **10-K text:** the P8 EDGAR cache (`.cache/p8/edgar`), Item 1 (Business) via `research/p8/sections.py`.
* **Earnings dates:** `.cache/p8/events.parquet` (`t0`, the first reaction session).
* **News embeddings (31 names):** `.cache/quant_trials/text/<T>_dedup.npz` (per session: article count and the sum
  of 3072-dimensional article embeddings).

Coverage is checked against the expected names each day and reported.

## 3. Definitions

* **Realised variance** RV_{i,t} = Σ_{k=1..13} (log C_k − log C_{k−1})² + (log O_1 − log C_13,t−1)², where C_0 = O_1
  is the open of the 09:30 bar. **Realised quarticity** RQ = (13/3) Σ_k r_k⁴ (intraday returns).
* **HAR terms** (all at the close of t): d = log RV_t, w = log mean RV_{t−4..t}, m = log mean RV_{t−21..t}; the same
  three for SPY; E_h = 1 if an earnings reaction session falls in t+1..t+h (dates are scheduled in advance; realised
  dates are used — disclosed).
* **Kernels** over the names in the panel at t, excluding the name itself:
  * **sector:** equal weight on same-GICS-sector names;
  * **text:** the 10 names whose latest 10-K Item 1 (filed ≤ t−1 and within 550 days) is most similar to the name's
    (TF-IDF cosine; vocabulary and idf fitted on 10-Ks filed 2011–2015 only: lower-cased alphabetic tokens of ≥ 3
    letters, min_df 5, max_df 0.5, sublinear tf), weights ∝ cosine;
  * **co-movement:** the 10 names with the highest correlation of daily residual returns (against SPY, beta of
    t−1) over sessions t−251..t, positive correlations only, weights ∝ correlation.
* **Field** of a variable x under kernel K: F_K(x)_i = Σ_j K_ij x_j.
* **Volatility targets:** y_h = log mean RV_{t+1..t+h}, h ∈ {5, 22}. Primary h = 5 (the books' holding week).

## 4. Forecasting protocol (risk)

Pooled panel OLS of y_h on the model's regressors, refitted on the first session of each month on all rows whose
target window ended before that session. The variance forecast is F = exp(ŷ + s²/2), with s² the fit's residual
variance. Loss: **QLIKE**, L = RV̄/F − log(RV̄/F) − 1 on the realised mean variance RV̄ over t+1..t+h.
Comparison statistic: the daily cross-sectional mean of L_benchmark − L_candidate, its mean, and a Newey–West t with
h + 5 lags (positive = the candidate is better). Rows are compared on the common sample, where every regressor of both
models exists.

Models:
* **M0:** own d, w, m; SPY d, w, m; E_h.
* **MS (benchmark for R1–R5):** M0 + sector fields of w and m.

| Test | Candidate | Benchmark | Idea |
|---|---|---|---|
| R1 | MS + text fields of w and m | MS | McKean–Vlasov field through business-text embedding |
| R2 | MS + co-movement fields of w and m | MS | the same through co-movement |
| R3 | MS with exponentially weighted least squares, half-life 252 sessions | MS (expanding) | local stationarity |
| R4 | MS + d × (√RQ_t / RV_t − its fit-sample mean) | MS | HARQ: trust a noisy day less (Bollerslev, Patton & Quaedvlieg 2016) |
| R5 | MS with every coefficient interacted with a high-variance state | MS | regime-switching coefficients |

R5's state: SPY's m above the 80th percentile of its own values over sessions t−755..t−1 (needs 252 sessions of
history; before that, the state is 0).

Reported, not tested: M0 vs a RiskMetrics EWMA (λ = 0.94, daily close-to-close returns), MS vs M0.

## 5. Beta

**Target:** the realised beta over sessions t+1..t+21 from 14 returns a day (the 13 intraday returns and the
overnight return), Σ r_i r_m / Σ r_m², with SPY as the market. Weekly decisions (Thursdays). Loss: squared error.
Statistic: as in §4, on the weekly cross-sectional mean loss difference, with 5 Newey–West lags.

* **B0:** the fund's beta: 2/3 × OLS beta over 252 daily returns (returns winsorised to [min(−2r_m, 4r_m),
  max(−2r_m, 4r_m)]) + 1/3.
* **B1:** a pooled calibration (refitted monthly as in §4, on decisions whose target ended) of the target on
  (1, high-frequency beta over t−20..t, high-frequency beta over t−62..t, the OLS daily beta over 252 sessions).
* **B2:** B1 + the text field of the 63-session high-frequency beta (the neighbours' law as a prior).

| Test | Candidate | Benchmark |
|---|---|---|
| H-B1 | B1 | B0 |
| H-B2 | B2 | B1 |

## 6. Alpha (McKean–Vlasov drift)

Weekly decisions on Thursdays, point-in-time S&P 500 members, residual returns e (beta of t−1, as
`research/regime`). Books are entered at close t+1 and held to close t+6, long the top decile and short the bottom,
50% a side, beta-hedged with SPY, 5 bp per unit of one-sided turnover (`research/regime` arithmetic).

| Test | Signal (predicted sign +) | Idea |
|---|---|---|
| A1 | text field of Σ_{t−20..t} e | text-peer momentum (Hoberg & Phillips 2018, as a kernel) |
| A2 | text field of Σ_{t−4..t} e − own Σ_{t−4..t} e | convergence to the neighbours' mean: drift κ(m − x) |
| A3 | as A2 with the co-movement kernel | the same through co-movement |

Statistic: the pooled slope of the next-week residual return Σ_{t+2..t+6} e on the week's cross-sectional z-score of
the signal, with week fixed effects and a Driscoll–Kraay t (5 lags), as `research/regime/intl.py: dk_t`. A name
needs a text vector at t for A1 and A2.

## 7. News in embedding space (the attached case), 31 names

* **Baseline NB:** MS restricted to the 31 names + log(1 + article count at t) + 5-session EW mean of
  log(1 + count) + a news-day dummy.
* **N1:** NB + unusualness, u_t = 1 − cos(today's mean article embedding, the mean embedding over the name's news in
  sessions t−63..t−1), 0 on no-news days, plus its 5-session EW mean.
* Same QLIKE protocol, h = 5.
* **Placebo (reported):** u shuffled across names within each day. The gain should vanish.
* **Caveat:** the encoder was trained after much of the sample (look-ahead in the encoder). A pass is read as
  incremental prediction, not causality.

## 8. Consequences for the books (the "orders" question)

Run only for the winners, by mechanical rule:
* the best risk model = the passing R candidate with the largest OOS h = 5 gain, else MS;
* the best beta = B2 if it passes, else B1 if H-B1 passes, else B0.

On the bars universe, using the 12-1 momentum decile book and the 1-week reversal decile book (weekly, as §6):

| Test | Comparison | Statistic |
|---|---|---|
| P1 | hedge with the best beta vs B0 | the mean over books and weeks of (hedged return under B0)² − (hedged return under the best beta)², Newey–West t (5 lags); positive = less variance |
| P2 | inverse-forecast-volatility weights within each leg (best risk model, h = 5) vs equal weights, same names and hedge | the Sharpe difference averaged over the two books, Jobson–Korkie–Memmel t |

## 9. Splits, gates, reads

* **Development:** risk, beta and news targets ending 2017-01-03 .. 2019-12-31 (fits start in 2016); alpha decisions
  2011-06 .. 2019-12.
* **Development gate** (a test goes forward as a finalist): the predicted direction with t ≥ 1.5 at the primary
  target. For risk tests, the mean gain at h = 22 must also be ≥ 0. For alpha, the net weekly book mean must also be
  > 0.
* **Out of sample:** 2020-01-01 .. 2025-12-31, **one read** of all finalists (`OOS_READ.lock`), one-sided p, Holm
  across all finalists of §§4–7 together. **P1 and P2** are a second family, read in the same run, Holm across 2.
* **Verdict for a pass:** Holm p < 0.05 and a positive mean gain at both horizons (risk), or a positive net book mean
  (alpha).
* **Changes:** any change after this file is committed is a dated amendment below, written before the statistic it
  governs is computed.

## Amendments

### Amendment 1 (2026-11-07, before any statistic): implementation details

1. **Kernels** are rebuilt at each month's first session τ from information to τ−1:
   * text: each name's latest 10-K Item 1 filed ≤ τ−1 and within 550 days;
   * co-movement, risk and beta tests: residuals from an in-window OLS on SPY over sessions τ−252..τ−1;
   * co-movement, alpha tests: the panel's residuals e over the same sessions, among names eligible at τ−1.

   Co-movement needs ≥ 200 finite sessions. This is stricter than per-session rebuilding: nothing after τ−1 is used.
2. **Validity:**
   * w needs ≥ 4 of its 5 sessions and m ≥ 17 of its 22;
   * a target needs ≥ ⌈0.8h⌉ valid sessions;
   * half-day sessions fail the 13-bar rule for nearly every name.
3. **Fields:** a field is missing when less than half its kernel weight has data at t. The row then leaves that
   comparison.
4. **Daily returns** of the bar names (B0, the OLS input of B1, co-movement, EWMA) are the sum of the day's 14 log
   returns, which is the close-to-close return.
5. **R4** uses the regressor d × q. Centring q on the fit-sample mean only shifts d's coefficient, so the forecasts
   are identical.
6. **Fits** need ≥ 200 sessions of ended targets. An origin is scored only when its whole target window lies inside
   the period:
   * development: origins from 2017-01-03, with targets ending ≤ 2019-12-31;
   * OOS: origins from 2020-01-02, with targets ending ≤ 2025-12-31.
7. **Text neighbours:**
   * universe: names of the bar universe (risk, beta) or of the point-in-time close panel (alpha) that have a vector;
   * the ticker → CIK map is P8's `ciks.json`;
   * the 10-K vocabulary is fitted on Item 1 sections of ≥ 2,000 characters.
8. **Alpha rows:**
   * a name needs eligibility at t, a close at t+1, and ≥ 18 finite residuals in t−20..t;
   * A1 and A2 also need a text vector;
   * the first week's turnover is 1.
9. **News:**
   * "5-session EW mean" = EWMA with span 5 (α = 1/3);
   * news features exist from each name's first news session;
   * placebo shuffle seed 7.

### Amendment 2 (2026-11-07, after the development results of §§4–7 and before any statistic of A2B or A3B, and before any OOS read)

**Development results:**
* Finalists: R2 and H-B1.
* A2 and A3 had the predicted slope (DK t 2.46 and 3.33), but their weekly decile books lost money net of costs. The
  books turn over most of their names each week.

**Two cost-aware variants are added**, with the same signals as A2 and A3. Each book enters at the top or bottom
decile and keeps a name while it stays in its top or bottom 30% (`research/regime/regime.py: banded`, as regime H12).
* **A2B:** banded book on the A2 signal.
* **A3B:** banded book on the A3 signal.

**Statistic:** the signal slope with the DK t, as for A2 and A3 (it is unchanged by banding).

**Gate and verdict:** as in §9, on the banded book's net mean.

**Disclosures:**
* These variants were chosen after the A2 and A3 development books were seen.
* They join the Holm family if they pass the gate.
* A2 and A3 themselves stay failed.

### Amendment 3 (2026-11-07, after the development results, before the OOS read)

1. **Development finalists** (`DEV_RESULT.md`): **R2, H-B1, A3B**.
   * A2B: −0.67% a year net, fails.
   * The development run was repeated after Amendment 2 to add A2B and A3B; every earlier number reproduced exactly.
2. **P2 statistic:** the Jobson–Korkie–Memmel test on the equal-weight average of the two books' weekly net returns
   (inverse-volatility weights against equal weights). **P1:** the mean over the two books of the squared-return
   difference, as §8.
3. **Disclosed, development data only:** to check the code path before the one-shot read, P1 and P2 were run once
   on the development weeks with R2 and B1.
   * P1: weekly sd fell from 1.117% to 1.100% (MOM) and from 0.821% to 0.799% (REV), t 2.15.
   * P2: Sharpe −0.07 against +0.02, t −1.39.

   Nothing was changed after seeing these.

### Amendment 4 (2026-11-07, after the round-1 OOS read; before any statistic of round 2): round 2

**Round 1** (`OOS_RESULT.md`):
* passes: H-B1 and P1;
* fails: R2, A3B and P2.

**Round 2** adds three ideas. Each uses the intraday data, and each is read **once** on 2020–2025 with its own lock
(`OOS2_READ.lock`), Holm across round 2's finalists.

**Disclosure:** 2020–2025 has now been read by round 1. Round 2's signals were not part of it.

| Test | Candidate | Benchmark | Statistic and predicted sign |
|---|---|---|---|
| R6 | MS + signed jump share j_t = (RS⁺_t − RS⁻_t)/RV_t and its 5-session mean | MS | QLIKE as §4 (Patton & Sheppard 2015) |
| H-B3 | B1 + (downside semibeta − beta), both over t−62..t | B1 | squared error as §5 |
| A4B | banded decile book on −RSkew | — | signal slope DK t as §6, predicted + |

**Definitions:**
* RS⁺ and RS⁻ are the sums of squared positive and negative returns among the day's 14 returns.
* Downside semibeta = Σ r_i r_m 1{r_m < 0} / Σ r_m² 1{r_m < 0}, over the same 14 returns a day.
* RSkew = √65 Σ r³ / (Σ r²)^{3/2} over the 65 intraday returns of sessions t−4..t (overnight excluded; Amaya,
  Christoffersen, Jacobs & Vasquez 2015). Low skewness is predicted to outperform.
* A4B's universe is the point-in-time members that are also in the bar universe. That universe holds current
  constituents only; the survivorship is disclosed. Its band is as A2B.

**Development periods:**
* risk and beta: as §9;
* A4B: decisions 2016-02-01 .. 2019-12-31, a short window that is disclosed.

**Gates and verdicts** are as §9 (A4B: net banded mean > 0).

### Amendment 5 (2026-11-07): forward beta records (never traded)

**From Thursday 2026-11-12,** `forward.py weekly` runs after the forward S&P books in the Friday job. It records,
for every point-in-time S&P 500 member:
* **B0:** the fund's beta, the one the S&P books hedge with;
* **B1:** coefficients frozen in `FROZEN_B1.json`, fitted on 2016–2025 decisions;
* B1's inputs.

**Data source:** 30-minute bars from Alpaca (SIP feed, adjustment "all", regular session), the source of the
research data.

**Ledger:** 21 sessions later, `forward.py ledger` scores both betas against the realised beta from 30-minute
returns, together with the AI ensemble book's residual beta under each hedge. Rows are frozen at first computation.

**Quality gate:** below 90% intraday coverage of members, the job fails loudly, after saving.

**No verdict before 26 scored weeks.** The record exists to confirm live what the OOS read showed: B1's mean
squared error below B0's. Using B1 in any book is the owner's decision under a new protocol.

### Amendment 6 (2026-11-07, before any statistic of round 3): contagion of news-derived shocks (McKean–Vlasov)

**The owner's intent:** the mean-field idea is about how news shocks spread through neighbours, not about any move
spreading. A1 used neighbours' moves on every day and failed. Round 3 uses only their moves on **news days**.

**News days** (`shocks.py`, typed fields only):
* earnings: P8 `events.parquet` t0, or an 8-K with Item 2.02;
* unscheduled: any other 8-K (not 8-K/A) with an item outside {9.01, 2.02, 5.07}.

The reaction session is the acceptance date, or the next session if acceptance is at or after 16:00 ET.

**Shock of name j at session τ:** the residual return e_{j,τ} on a news day of j, and 0 otherwise.

| Test | Signal at Thursday t (predicted sign) | Idea |
|---|---|---|
| C1 | text field of Σ_{τ=t−4..t} shock_j,τ (all news) (+) | neighbours' news diffuses slowly into i (Cohen & Frazzini 2008; Hoberg & Phillips 2018) |
| C2 | as C1 with the co-movement kernel (+) | the same through co-movement |
| C3 | as C1, unscheduled news only (+) | contagion of unscheduled shocks |
| C4 | MS + text field of Σ_{τ=t−4..t} \|shock_j,τ\| (all news), for volatility (QLIKE, h = 5 primary) | volatility contagion of neighbours' news |

**Books and statistic:**
* C1–C3: banded decile books from the start (Amendment 2's band). Statistic: the signal slope with the DK t, as §6.
  Verdict: banded net mean > 0.
* C4: as §4. Its kernel and fields are those of the bar universe; shocks are the bar names' residuals against SPY,
  with the beta of t−1 from the daily OLS of §5.

**Development:**
* C1–C3: decisions 2011-06 .. 2019-12;
* C4: as §9.

The gates are as §9. **OOS:** 2020–2025, one read (`OOS3_READ.lock`), Holm across round 3's finalists.

**Disclosure:** 2020–2025 has been read by rounds 1 and 2 for other signals.

### Amendment 5a (2026-11-07, before the first forward record): bars adjustment in the forward records

Alpaca returns about 370 bars a page, so the full 63-session window for 500 names takes about 2,800 requests. The
forward records therefore **cache bars across weeks**.

**Adjustment:** the cached bars are **split-adjusted only**. Dividend adjustment re-prices history at every
ex-date, and that would break a cache. A name whose overlap closes changed (a split) is fetched afresh over the
whole window.

**Effect of the change:** the research bars were adjusted for dividends too. The difference is the dividend drop on
about four overnight returns a year. That drop is negligible for a beta.

### Amendment 7 (2026-11-07, after round 3's development and before any statistic of round 4): fast contagion (order timing)

**Round 3** (`DEV3_RESULT.md`): no finalists. Neighbours' news-day shocks did not predict the next week's residual
returns or volatility (C1–C4, DK t −0.94 to −0.51). Information transfer between peers is fast in the literature:
peers react within a day. Round 4 therefore tests the next day.

| Test | Signal at session t (predicted sign) | Target |
|---|---|---|
| D1 | text field of shock_j,t (news day of j at t: its residual return e_{j,t}; all news) (+) | e_{i,t+1} |
| D2 | as D1 with the co-movement kernel (+) | e_{i,t+1} |
| D3 | as D1, earnings days only (+) | e_{i,t+1} |

**Data and universe:** the news days, kernels and residuals of round 3, on every session (not only Thursdays),
for point-in-time members with a close at t+1. D1 and D3 also need a text vector.

**Statistic:** the pooled slope of e_{i,t+1} on the session's cross-sectional z-score of the signal, with session
fixed effects and a Driscoll–Kraay t (5 lags).

**Reading:** this is an **order-timing** signal (the fund sends orders at T−60 s), not a stand-alone book.

**Reported (not tested):**
* the slope in bp per standard deviation;
* the same slope for e_{i,t+2} (one day skipped);
* the gross and net (5 bp) daily decile book.

**Splits:**
* development: sessions 2011-06-01 .. 2019-12-31; gate t ≥ 1.5;
* OOS: sessions 2020-01-02 .. 2025-12-30, one read (`OOS4_READ.lock`);
* Holm across round 4's finalists; pass = Holm p < 0.05 with a positive slope.

### Amendment 8 (2026-11-07, after round 4's development and before any statistic of round 5): intraday contagion

**Round 4** (`DEV4_RESULT.md`): no finalists. Next-day drift was +0.16 to +0.21 bp per sd (t ≤ 0.68).

**Descriptive** (development years, not a test): on the same day, the text neighbours' earnings shocks move a
non-reporting stock's residual by 9.8 bp per sd (DK t 24.9). The contagion is real but completes within the
session.

**Round 5 asks:** after a neighbour's earnings gap is known at 10:00, does the stock keep adjusting until the close?
Data: the 30-minute bars (current constituents, 2016–2025; survivorship disclosed).

**Definitions:**
* **Shock of j at session t:** j has an earnings reaction session at t (P8 `events.parquet` t0) announced outside
  trading hours (accepted before 09:30 ET on t, or after 16:00 ET before t). The shock is j's residual return from
  the previous close to 10:00 (the overnight return plus the 09:30 bar), net of β_j × SPY over the same interval.
  β is the daily OLS of §5 at t−1.
* **Target:** i's residual return from 10:00 to the close (bars 10:00–15:30), net of β_i × SPY, for names i with no
  earnings reaction at t.

| Test | Signal at 10:00 of session t (predicted sign) |
|---|---|
| I1 | text field of the neighbours' shocks (+) |
| I2 | co-movement field of the neighbours' shocks (+) |

**Rows:** name-sessions where at least one kernel neighbour has a shock.

**Statistic:** the pooled slope of the target on the session's cross-sectional z-score of the signal, with session
fixed effects and a DK t (5 lags).

**Reported:**
* bp per sd;
* the top-minus-bottom-decile spread in bp, against an intraday round trip of 10 bp.

**Splits:**
* development: sessions 2016-02-01 .. 2019-12-31; gate t ≥ 1.5 and a positive slope;
* OOS: 2020-01-02 .. 2025-12-31, one read (`OOS5_READ.lock`);
* Holm across the finalists; pass = Holm p < 0.05 with a positive slope.

### Amendment 9 (2026-11-07, after round 5's OOS read and before any statistic of round 6): a tradeable earnings-drift book with a fundamental field

**Owner (2026-11-07):** "don't stop the research until you find something tradeable … investigate with other
available data". Tradeable means at the fund's speed: decisions on Thursdays, entry at the close of t+1, 5 bp a
side.

**Prior evidence:** P8's descriptive decay curves (`reports/research/p8/decay_earnings.md`, fit sample 2012–2021)
put earnings information in the S&P 500 at about 20 sessions. The SUE top-minus-bottom quintile earns +57 bp
over t0+2..t0+21; then it fades. **2022–2025 has never been read for earnings drift.** This round's OOS is
therefore **2022-01-01 .. 2025-12-31**. Development is 2012–2021, which P8 has already seen descriptively
(disclosed).

**Events:** P8 `events.parquet` (S&P 500 point in time). Each event carries:
* SUE: seasonal random walk, winsorised at ±10;
* CAR = Σ e over t0−1..t0+1.

**Decision t (Thursday):**
* **Events:** those with t0+1 ≤ t and t0 ≥ t−5. The whole reaction is known at the close of t.
* **Composite:** z(SUE) + z(CAR), z-scored across the week's events.
* **Field F:** the cosine-weighted mean SUE of the name's text neighbours (§3 kernel, built at the month's first
  session) whose reaction session t0_j lies in [t−62, t]. Weights are renormalised over neighbours with an event;
  F is missing when there is none.
* **Target D20:** Σ e over sessions t+2..t+21, the 20 sessions after entry at close t+1.

| Test | Statistic (predicted sign) | Idea |
|---|---|---|
| E1 | pooled slope of D20 on the week's z(composite), week fixed effects, DK t (5 lags) (+) | earnings drift (Bernard & Thomas 1989; Chan, Jegadeesh & Lakonishok 1996) |
| E2 | in the pooled regression of D20 on [z(composite), z(F)], the coefficient on z(F), DK t (+) | McKean–Vlasov fundamental field: peers' surprises this season carry information about the name that the market prices slowly |
| E4 | mean residual return of the reaction session, e_{i,t0} (+) | the earnings-announcement premium (Frazzini & Lamont 2007; Savor & Wilson 2016). Trade: buy at close t0−1, sell at close t0 |

**Rows:**
* E1 and E2: events with z-scores, in weeks with ≥ 10 events. E2 also needs F.
* E4: every event in the period. Its DK t clusters by week.

**Book (E1, reported with the test; also E2's book on z(composite) + z(F)):**
* each week, a cohort goes long the top third of events by signal and short the bottom third, equal weight, 50% a
  side, beta-hedged with SPY using the fund's beta;
* each cohort is held 20 sessions; four overlapping cohorts are averaged, each at 1/4 weight;
* costs: 5 bp a side at entry and at exit;
* reported: net % a year and Sharpe.

**Verdicts:**
* E1, E2: pass = Holm p < 0.05 with the book's net mean > 0.
* E4: pass = Holm p < 0.05 with mean e_{t0} > 10 bp, the round trip.

**Gates (development 2012–2021):** t ≥ 1.5 in the predicted direction, and for E1/E2 a net book mean > 0.

**OOS:** 2022–2025, one read (`OOS6_READ.lock`), Holm across round 6's finalists.

**Replication, if anything passes:** the S&P 400 (P8 events and closes, current list, survivorship disclosed),
2022–2025, one read (`REP6_READ.lock`).

### Amendment 10 (2026-11-07, after round 6's development and before any statistic that uses insider data): insider trading and its field

**Round 6** (`DEV6_RESULT.md`, development 2012–2021): no finalists.
* E1, earnings drift at the Thursday cadence: 13 bp per sd, t 1.22; book +0.16% a year.
* E2, the field: −1.1 bp, t −0.07.
* E4, announcement premium: −1 bp.

So the OOS6 read is not spent. In large caps, price and earnings information is priced within days.

**Round 7 uses information the market is known to price slowly:** insiders' open-market trades, from the SEC
Insider Transactions Data Sets 2010–2025 (`insider.py`).
* Typed fields only: TRANS_CODE P (purchase) or S (sale), from Forms 4 and 5. Amendments are dropped.
* The signal date is FILING_DATE; a filing counts at decision t if FILING_DATE ≤ the session before t.
* Issuer CIK → ticker via P8's `ciks.json`. A ticker without a CIK has no insider data, and its signals are 0.

**Signals at Thursday t,** over filings in the last 63 sessions:

| Test | Signal (predicted sign +) | Idea |
|---|---|---|
| N1 | (insiders with purchases − insiders with sales) / (insiders with purchases + insiders with sales); 0 if none | net purchase ratio (Lakonishok & Lee 2001) |
| N2 | opportunistic insiders with purchases − opportunistic insiders with sales | opportunistic trades (Cohen, Malloy & Pomorski 2012) |
| N3 | text field of N1 (§3 kernel; neighbours without trades count as 0) | McKean–Vlasov: peer insiders' information about the industry |

**Opportunistic insiders (N2):** an insider is classified at the start of each calendar year y. The insider needs
at least one P or S trade in each of y−3, y−2 and y−1.
* **Routine:** traded in the same calendar month in all three years.
* **Opportunistic:** every other classified insider.
* **Unclassified insiders** are not counted, as in Cohen, Malloy & Pomorski.

**Target and statistic:** as round 6. D20 = Σ e over t+2..t+21. The pooled slope on the week's cross-sectional
z-score of the signal, with week fixed effects and a DK t (5 lags).
* Reported: the same slope for D60 (t+2..t+61).

**Rows:** point-in-time S&P 500 members at t with closes at t and t+1. N3 also needs a text vector.

**Book:**
* N1, N2: long names with a positive signal, short names with a negative signal, equal weight, 50% a side;
* N3: top and bottom deciles;
* all books are beta-hedged with SPY, held 20 sessions in four overlapping cohorts, at 5 bp a side.

**Splits:**
* development: decisions 2013-01 .. 2019-12 (N2 needs three years of history);
* OOS: 2020-01 .. 2025-12, one read (`OOS7_READ.lock`); 2020–2025 has been read by rounds 1–5 for other signals.

**Gates:** t ≥ 1.5 and a positive net book mean. **Verdict:** Holm p < 0.05 with a positive net book.

**Replication, if anything passes:** the S&P 400 current list 2020–2025 (P8 closes; survivorship disclosed), one
read (`REP7_READ.lock`).

### Amendment 11 (2026-11-07, after round 7's development and before any statistic of round 8): mean-field statistical arbitrage

**Round 7** (`DEV7_RESULT.md`, development 2013–2019): no finalists. Insider net purchases, opportunistic insiders
and their text field: |t| ≤ 0.84 at 20 sessions; every book lost money. In S&P 500 names, insider purchases
are rare: about 25 net-buying names a week.

**The force that keeps appearing** is the pull of a stock toward its neighbours. A3's weekly gap convergence had a
gross slope of t 3.33 in development, but its book traded every name every week. **Round 8** models the residual
against the neighbour basket as a locally stationary OU process. It trades only far excursions of fast-reverting
residuals: the statistical arbitrage of Avellaneda & Lee (2010), with their parameters unchanged (paper §§4–5
and Appendix). Here the factor is the **mean field of the 10-K text neighbours** instead of a sector ETF.

**The rules, decided daily at close t, for point-in-time S&P 500 members:**
1. **Basket return** r_B,i: the §3 text-kernel weighted mean of the neighbours' daily returns. The kernel is built
   at the month's first session; weights are renormalised over neighbours with a return that day.
2. **Regression:** over sessions t−59..t, regress r_i = β0 + β·r_B,i + ε. Then X_k = Σ_{j ≤ k} ε_j.
3. **OU fit:** the AR(1) X_{n+1} = a + b·X_n + ζ gives κ = −252·ln b, m = a/(1−b), σ_eq = √(Var ζ/(1−b²)).
4. **Filter:** only names with **κ > 252/30** (b < 0.9672) and 0 < b may open a position. This is the local
   stationarity regime: fast mean reversion.
5. **s-score:** s = −(m − ⟨m⟩)/σ_eq, where ⟨m⟩ is the mean of m over the names that pass the filter that day.
6. **Signals:**
   * open long if s < −1.25 and open short if s > +1.25;
   * close a short when s < +0.75 and close a long when s > −0.50.
7. **Position:** $1 of the stock against β (fixed at entry) dollars of the basket.
8. **Costs:** 5 bp a side on the stock and on the basket notional, at entry and at exit.
9. **Book:** the daily return is the mean over open positions of the position's net P&L, on committed capital.

| Test | Basket | Execution |
|---|---|---|
| S1 | text neighbours | signal at close t, trade at close t+1 (the research books' convention) |
| S2 | text neighbours | trade at close t. The fund sends orders at T−60 s, using prices a minute before the close; this approximates that |
| S3 | co-movement neighbours (§3, residual correlation) | close t+1 |

**Statistic:** the mean daily net book return, with a Newey–West t (10 lags) (+).

**Reported:**
* net % a year;
* Sharpe;
* trades a year;
* the average holding period;
* positions open on an average day.

**Splits:**
* development: sessions 2011-06-01 .. 2019-12-31; gate t ≥ 1.5 with a positive net mean;
* OOS: 2020-01-02 .. 2025-12-30, one read (`OOS8_READ.lock`); Holm across round 8's finalists;
* pass = Holm p < 0.05 with a positive net mean.

**Replication, if anything passes:** the S&P 400 current list (P8 closes, 2016–2025; survivorship disclosed), one
read (`REP8_READ.lock`).

### Amendment 12 (2026-11-07, after round 8's development at 5 bp and before any OOS read of round 8): the measured cost level

**Round 8 at 5 bp a side** (`DEV8_RESULT.md`): no finalists. S1 nets −0.72 bp a day per position, with about
2,840 trades a year held about 11 days. The costs come to about 1.8 bp a day per position, so the strategy is
positive before costs.

The neighbour-reversion signals have repeatedly been positive gross and negative net at 5 bp a side (A2, A3, A3B,
S1–S3). The fund's **measured** costs are 0.8 bp slippage and 0.08 bp fees per side (118 Alpaca paper fills,
1–22 October 2026; `fund/CHANGELOG.md`, 2026-10-23). Easy-to-borrow shorts cost nothing.

**Pre-registered cost level: 2 bp a side,** about twice the measured cost, to allow for live slippage. The level
comes from the fund's fills, not from these results.

**Disclosed:** the development results at 5 bp are known, so a development gate at 2 bp is predictable and is
not evidence. **The only test is the one OOS read.**

| Test | Strategy, at 2 bp a side on every traded notional (stock and basket legs) |
|---|---|
| S1c | S1 (text basket, trade at close t+1) |
| S2c | S2 (text basket, trade at close t) |
| S3c | S3 (co-movement basket, close t+1) |
| A3c | A3 (weekly co-movement gap, decile book, §6; never read OOS) |

**OOS:** 2020–2025 (`OOS8_READ.lock`), one read, Holm across the four. Pass = Holm p < 0.05 with a positive net
mean. Reported: the gross mean, the net at 5 bp, and returns by year.

**Replication, for a pass:**
* **S-tests:** the S&P 400 current list (P8 daily closes 2016–2025; survivorship disclosed); kernels and the same
  rules at 2 bp; one read (`REP8_READ.lock`).
* **A3c:** that replication is not possible (the bar universe is S&P 500 only); it is reported as such.

**Before any money:** a pass is a paper candidate, recorded forward like the beta records.
