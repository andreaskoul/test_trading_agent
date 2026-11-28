# Dynamic, retrained volatility forecasts for stocks, indices and crypto — pre-registration (2026-11-28)

Committed before any **out-of-sample** forecast is computed.

**Disclosure of order.** This file was drafted before any forecast was evaluated, but it was committed only after a
first development read of three classes (crypto, ETFs, indices). That read ran on panels truncated at the
development end, so no out-of-sample datum existed during it. It revealed one design defect, fixed by Amendment 1
below. Those first results are kept as `DEV_VOL_pre_amendment1.json`. Every stock evaluation, the power table and
the out-of-sample read come after this commit. Owner's brief (2026-11-28): plan volatility forecasting with
models that adjust dynamically and are retrained; add indices and crypto beside the fund's stocks, from free sources;
consult the literature and practitioner forums; train and test on a good out-of-sample period. Research only:
nothing under `fund/` changes; any adoption is a separate protocol decision (CLAUDE.md rules 13 and 17).

Inputs, frozen at first use (rule 4): `LIT_VOL.md` (literature and forum review, this folder), `data.py`,
`features.py`, `DATA_MANIFEST.json` (sha256 of every raw and daily file), `COVERAGE.json`, `requirements.txt`
(pinned environment `~/.fund-runner/venv-vol`).

## 1. Why, and the decision it serves

The fund forecasts every position's volatility with one rule: σ = max(EWMA span 60 std, 0.75 × 252-session std)
of daily SPY-hedged residual returns, flat over the horizon (`fund/lifecycle.py:entry_vol`). That σ sets the stop
and target width W = σ√H for live horizons of 3–63 sessions (median ≈ 22), and Protocol 11 builds its normal-day
σ_d the same way. A better normal-day variance forecast calibrates every stop and every size scalar.

**Primary question.** For S&P 500 stocks, does the pre-registered equal-weight combination of the dynamic models
forecast the 22-session normal-day residual variance better than the fund's rule, out of sample?

**Secondary questions (measurement).** Which models are best, by class and horizon, for stocks, US index ETFs,
global equity indices and crypto; how much intraday data is worth; whether adaptive weights beat equal weights;
and whether the forecasts are calibrated in the units the fund uses (stop-hit rates, realised ÷ forecast).

## 2. Data (free sources; `data.py`)

| Class | Assets | Source | Daily variance proxy `rv` | From |
|---|---|---|---|---|
| Stocks | S&P 500 point-in-time members 2016–2026 plus same-CUSIP aliases (758 symbols) | Alpaca SIP bars, adjustment=all: 15-minute regular session + official daily bars | residual RV: Σ over 15-minute slots of (r − b·r_SPY)² + squared residual overnight return | 2016-01 |
| US index ETFs | SPY, QQQ, IWM, DIA | Alpaca SIP 5-minute + daily | 5-minute RV + squared overnight return | 2016-01 |
| Equity indices | S&P 500, Nasdaq-100, Russell 2000, Dow, FTSE 100, DAX, Nikkei 225, Euro Stoxx 50, Hang Seng | Yahoo daily OHLC | squared daily close-to-close log return (no free intraday history) | 1985–2007 |
| Crypto | BTC, ETH, BNB, LTC, ADA, XRP, DOGE, SOL (USDT pairs) | Binance Vision bulk 5-minute klines, every file checked against Binance's published sha256 | 5-minute RV of the UTC day (288 bars) | 2017-08 – 2020-08 |

* **Residual and beta (stocks)** exactly as the fund: e = r − b·r_SPY, b = 2/3 × lagged 252-session winsorised
  OLS beta + 1/3 (`fund/p11.py:residuals`). Intraday residuals use the same daily b on aligned 15-minute slots (SPY
  5-minute returns summed in threes).
* **Normal-day variance (stocks).** Report sessions ±1 are masked in features and targets, the σ_d of Protocol 11.
  Report dates: P8 SEC events to 2026-09-30, then the live Protocol 11 screens. ±1 absorbs the documented one-day
  SEC timestamp defect (DATA_USE, 2026-10-31).
* **Early closes.** Slots after 13:00 are dropped on the 22 NYSE early-close sessions. Alpaca serves post-market bars
  there, and the daily close is the 13:00 price (checked on 2016-11-25: daily close 190.02, 13:00 price 190.03,
  16:00 price 190.15).
* **15 minutes for stocks** is a data budget, not a preference. Alpaca pages hold about 2,500 bars including
  extended hours, so 5-minute bars for 758 names would need about 11 hours at the 200-per-minute limit. The four
  ETFs are at 5 minutes. A coarser grid adds sampling noise to rv, which lowers power but does not bias QLIKE
  rankings (Patton 2011: QLIKE is robust to a noisy, conditionally unbiased proxy).
* **Validity.** A day's rv is missing when fewer than 90% of the expected slots exist. Coverage is checked against
  the expected calendar (CLAUDE.md rule 3); counts are in `COVERAGE.json`.
* **Rejected source.** The Oxford-Man realised library (5-minute RV of 31 indices) is discontinued and its mirrors
  end in mid-2022, before the out-of-sample window. A proxy that changes at the start of the test would confound it.

## 3. Targets and horizons

* y_H(t) = H × mean(rv over the valid days t+1..t+H), valid when ≥ 80% of the H days are valid (masked days are
  invalid for stocks). Horizons: **H = 1, 5, 22, 55 sessions**; crypto in calendar days **1, 7, 31, 77** (the same
  wall-clock spans; `LIT_VOL.md` §1.1).
* A robustness target y_H^r2 uses squared close-to-close (residual) returns, the fund's own proxy.
* Every row carries end_H, the date its target window closes. A model refit on date τ trains only on rows with
  end_H < τ. Contract tests `test_vol.py` check the window, the validity rule, no look-ahead in any feature and the
  masking, and each has a planted fault it must reject. All 9 pass; both mutations tried were caught.

## 4. Models (from `LIT_VOL.md` §1.1; literature defaults, nothing tuned on test data)

Common rules:
* **Insanity filter** (Bollerslev–Patton–Quaedvlieg 2016): a forecast outside the range of the target in its
  estimation window is replaced by that window's mean. **Made one-sided by Amendment 1** (low or non-positive
  forecasts only).
* **Windows.** "Rolling 1000" means expanding from a minimum of 500 usable rows, then rolling over the last 1,000.
  This deviates from a strict 1,000 because the stock and ETF data start in 2016: a strict window would put the
  first forecast in late 2020 and leave about one development year.
* HAR lags are 1, 5 and 22 sessions; for crypto, 1, 7 and 30 days.

| # | Model | Classes | Estimation, window, refit | Horizon |
|---|---|---|---|---|
| S0 | **Fund rule** (benchmark): max(EWMA span 60 std, 0.75 × 252-session std)² of daily returns (residual, report days dropped, for stocks) | all | none, daily | flat: × H |
| S1 | RiskMetrics EWMA, λ = 0.94, of squared daily returns | all | none, daily | flat |
| S2 | GJR-GARCH(1,1), Student-t, daily returns (stocks: residual, report days dropped from the series) | all | QML (`arch` 7), rolling 1000, refit every 5 sessions, filtered daily with fixed parameters | iterated closed form, persistence α + γ/2 + β |
| S3 | HAR-RV by WLS: OLS first, then weights 1/ŷ²_OLS (Clements–Preve 2021) | stocks, ETFs, crypto | rolling 1000, daily | direct, one regression per H, target the H-average |
| S4 | HARQ: S3 regressors plus √RQ_d·RV_d (Bollerslev–Patton–Quaedvlieg 2016) | stocks, ETFs, crypto | OLS, rolling 1000, daily | direct |
| S5 | Log-HAR, back-transformed exp(fit + s²/2) | stocks, ETFs, crypto | OLS on logs, rolling 1000, daily | direct |
| S6 | Pooled centred HExpGl (Bollerslev, Hood, Huss, Pedersen 2018): EWMAs of rv, centres of mass 1, 5, 25, 125 sessions, minus the asset's expanding long-run mean, plus a 5-session-CoM EWMA of the market rv (SPY's for stocks; the cross-index mean for indices). Common slopes, no intercepts | stocks, indices | pooled OLS, expanding; an asset enters after 252 sessions; daily | direct |
| S7 | Range-HAR: HAR lags of the Parkinson variance (H−L)²/(4 ln 2), plus the squared close-to-open return, WLS as S3 | indices, ETFs | rolling 1000, daily | direct |
| S8 | Pooled gradient-boosted trees, scikit-learn `HistGradientBoostingRegressor` with library defaults, loss = gamma deviance (= 2 × QLIKE, so the conditional-mean target is consistent), `random_state` 20261128. Features: S3 lags, S6 EWMA factors, market rv lags 1/5/22, log VIX (stocks) | stocks, crypto | expanding, retrained each January | direct |
| C1 | **Equal-weight combination** of the class's S2–S8 variance forecasts (**primary**; forecast-combination puzzle) | all | — | — |
| C2 | Discounted inverse-QLIKE weights, half-life 252 sessions, 252 scored forecasts of burn-in (equal weights before) | all | weights at t use only forecasts made at or before t − H | — |
| C3 | Fixed-share exponential weights (Herbster–Warmuth), η = 1/2, α = 1/252 | all | same look-ahead rule | — |

**Model set per class** (the combinations average the class's S2–S8 members):

| Class | Models | C1 = equal-weight mean of |
|---|---|---|
| Stocks | S0 S1 S2 S3 S4 S5 S6 S8 | S2 S3 S4 S5 S6 S8 |
| US index ETFs | S0 S1 S2 S3 S4 S5 S7 | S2 S3 S4 S5 S7 |
| Equity indices | S0 S1 S2 S6 S7 | S2 S6 S7 |
| Crypto | S0 S1 S2 S3 S4 S5 S8 | S2 S3 S4 S5 S8 |

* S7 on the ETFs is a deliberate measurement: range-based against 5-minute RV on the same assets prices the
  intraday data.
* Stock origins are members at t and not masked at t.

Implementation notes, fixed now:
* **WLS weights (S3).** Each row's weight is 1/ŷ², with ŷ the rolling-OLS fitted value at that row's own origin
  (information up to that row only; the H-average of the row's weekly rv before 500 rows exist). This makes the
  daily refits exact and cheap. Clements–Preve's two-step in-window weights would need a separate weighted fit for
  every window.
* **Pooled models across calendars (S6, C2, C3).** These run on the class's union calendar. Losses are scored on the
  date their target closes, and discounting counts days of that calendar.
* **S2 return series.** S2 has a constant mean. For stocks the report days are removed from the return series, as
  S0 does: the recursion runs over normal days only. An origin on a dropped day uses the last normal day's state.
* LightGBM was the memo's named library; it cannot load here (no ARM OpenMP runtime). `HistGradientBoosting` is the
  same histogram-boosted-trees algorithm.
* S2 is refit every 5 sessions because of the compute budget (about 333,000 fits for the stocks). The memo records
  disagreement in the literature on whether refit frequency matters (`LIT_VOL.md` §3).
* S0 and S1 are benchmarks and are not in the combinations.

## 5. Samples: development, then one out-of-sample read

| Class | Training starts | Development evaluation (open) | **Out of sample (one locked read)** |
|---|---|---|---|
| Stocks, ETFs | 2016-01 (+ warm-up) | 2019-01-02 – 2021-12-31 | **2022-01-03 – 2026-11-27** |
| Indices | 1985 – 2007 | 1995-01-02 – 2021-12-31 | **2022-01-03 – 2026-11-27** |
| Crypto | 2017-08 | 2019-07-01 – 2021-12-31 | **2022-01-01 – 2026-11-27** |

* The out-of-sample window is common to all classes. It spans 2022's bear market and crypto collapse, the 2023 calm,
  August 2024, April 2025 and November 2026. Models keep retraining through it on their schedules; that is the
  "dynamic" part being tested.
* A forecast at origin t enters only if its target closes by 2026-11-27.
* **The development read is open.** It verifies the implementation (failure controls, calibration sanity) and
  computes power (§7). A bug fix, or a design defect it reveals, is changed only by a dated amendment before the
  lock that states the development evidence it used.
* **Development ends early for any origin whose target would close after the development end**, so the out-of-sample
  window's data are never read in development.
* **What has been read before (DATA_USE ledger):**
  * Stock returns 2022–2025 were read by about 36 return hypotheses.
  * Variance forecasts on the 2020–2025 stock panel were read once (event risk E1: EWMA against the event-inclusive
    variance).
  * One literature result (Audrino–Chassot, test window 2022-01 – 2023-11) lies inside this window and favours WLS-HAR.
  * Indices were read as returns for exposure rules; crypto has never been read here.
  * **2026-01-02 – 2026-11-27 is fresh for every class** and is reported as its own sub-window.

## 6. Loss, tests and verdicts

* **Loss:** QLIKE(y, ŷ) = y/ŷ − log(y/ŷ) − 1, on variance levels. For y = 0 (daily squared returns), the equivalent
  differential form y/ŷ + log ŷ is used, which differs only by a term in y.
* **Common sample:** within a class and horizon, every model is scored on the same (asset, origin) pairs.
* **Panel Diebold–Mariano:** the daily cross-sectional mean loss differential d_t = L̄_S0,t − L̄_m,t, with
  Newey–West lag max(2H, n^{1/3}).
* **Model Confidence Set:** 90%, range statistic, stationary block bootstrap with block length max(5, H), 1,000
  draws, seed 20261128 (`arch.bootstrap.MCS`).
* **Calibration:** mean realised ÷ mean forecast; Mincer–Zarnowitz slope and intercept (diagnostic).
* **Economic, descriptive:**
  * Stocks: the stop-hit rate of random-direction positions with barrier −2W, W = √ŷ_22, on windows without a
    report session, against the theoretical 2Φ(−(2 + 0.5826/√H)).
  * All classes: risk-targeting tracking, the dispersion of realised ÷ forecast volatility of vol-scaled returns.

**Primary hypothesis (one test, stocks, H = 22):** H₀: E[d_t] ≤ 0 for C1 against S0.
* **Supported** only if all three hold:
  * the one-sided p ≤ 0.10/N with N = 44 (the programme's running count plus this read), i.e. p ≤ 0.0023;
  * C1's out-of-sample realised ÷ forecast lies in [0.9, 1.1];
  * C1's stop-hit rate is within 1 point of theory.
* **Rejected:** the 90% upper bound of the QLIKE gain is below 1% of S0's mean QLIKE.
* **Inconclusive:** otherwise.

A supported result is a *proposal* to use C1 for σ_d under a new protocol. It changes nothing by itself.

**Secondary families (measurement, not counted in N):**
* For every class × horizon, every model against S0 and against S1: Diebold–Mariano with Holm within the family.
* The MCS membership.
* The r² robustness target.
* The 2026-only sub-window.
* Indices and crypto are not traded (rule 17); their results are research.

## 7. Power, before the read (DESIGN_RULES rule 3)

From the development read only:
* the standard deviation of d_t for C1 against S0 at H = 22 for stocks, with Newey–West at the registered lag;
* the power of the primary test over the out-of-sample day count, at δ = the smaller of half the development gain
  and 5% of S0's development mean QLIKE.

If P < 0.5, the primary becomes a precision estimate (rule 6) with the same verdict classes. The power table is
committed with the development results before the lock.

## 8. The read

`evaluate.py read` refuses to run unless all of these hold:
* this file, the code and `DEV_VOL.json` (development results and power) are committed and unchanged;
* `test_vol.py` passes;
* `READ_VOL.lock` does not exist.

It then writes the lock and computes every out-of-sample number once. It writes `RESULT_VOL.json` and
`RESULT_VOL.md` whatever they show. A DATA_USE ledger row is added with the lock.

## Amendment 1 (2026-11-28, before the lock; informed by the development read): a one-sided insanity filter

**What the development read showed** (ETFs, 2019–2021; `DEV_VOL_pre_amendment1.json`; diagnostic
`diag_filter.py`):
* The upper side of the insanity filter replaces a forecast above the window's maximum target with the window mean.
  It bound on 77 of 11,889 WLS-HAR forecasts at H = 5 (0.6%) and 137 of 11,685 at H = 22 (1.2%). Those rows are
  March 2020, when every 1,000-row window held only 2016–2019.
* It replaced correct crisis forecasts with calm means:
  * WLS-HAR (S3) QLIKE 0.695 against 0.269 without the upper side at H = 5; 1.514 against 0.761 at H = 22;
  * realised ÷ forecast 1.20 against 1.00 at H = 5.
* The stock and ETF windows are the most exposed, because their data start in 2016 and the first crisis inside
  them is the one being forecast.

**Change (every model, S3–S8).** A forecast that is non-finite, non-positive or below the window's minimum target is
replaced by the window mean. **Forecasts above the window's maximum are kept.**

The upper side exists to stop explosive HARQ forecasts. Explosive *positive* forecasts here follow large realised
variance and are the correct reaction to a crisis; a wrong-signed HARQ term yields a negative or very small forecast,
which the lower side still catches (reasoning).

**Effect on the claims.** The change uses development data, so the out-of-sample read tests the amended
specification. The out-of-sample data have not been read by anything.

## 9. Not claimed

* Not a test of the fund with new stops or sizes. The stop-hit calibration is descriptive; trading changes are a
  separate protocol.
* Not tradable for indices or crypto: research measurement only.
* No novelty: every model is from the literature (`LIT_VOL.md`). Its access labels state how far each source was
  read; several key papers were read as working papers.
* Forum evidence (`LIT_VOL.md` §7) was thin. Reddit and QuantNet refused automated requests, and Wilmott's search
  returned nothing. It informs pitfalls, not choices.
