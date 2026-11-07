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

(none yet)
