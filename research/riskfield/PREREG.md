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
