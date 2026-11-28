# Literature and forum review: dynamic, adaptive, retrained volatility forecasting

Written 2026-11-28, before any out-of-sample data was read. No price data and no repository data were opened to
write it. The only purpose is to fix model choices for a pre-registered study from published defaults.

**Access labels** (on every factual claim):

* **[RD]** read directly: I opened the passage (PDF text or arXiv full text) and copied the number or wording.
* **[AB]** abstract only: I read the abstract or a repository record, not the body.
* **[SS]** search summary only: a search engine's summary. It is never cited as if the paper had been read.
* **[R]** reasoning: my own inference or design choice. It is not a literature finding.

Numbers marked [RD] are copied from the source text. Where I could not open a source, the claim is labelled [AB]
or [SS] and kept out of the parameter choices whenever possible.

---

## §1 Answer in brief

### 1.1 Recommended shortlist (9 specifications)

Notation: `RV_t` is the daily variance proxy for the target series. For stocks it is the SPY-hedged residual,
with earnings sessions masked. `RV^(H)_t` is the sum over the next H sessions. Direct forecasts regress the
H-session average, `(1/H)·Σ_{j=1..H} RV_{t+j}`, on information at t and multiply by H. "Rolling 1000, daily
refit" means the parameters are re-estimated every session on the last 1000 sessions. Every model gets the
**insanity filter** of Bollerslev–Patton–Quaedvlieg (2016): a forecast outside the range of the target observed in
the estimation window is replaced by that window's mean [RD].

| # | Name | Classes | Features (exact) | Estimation / window | Refit | Horizon method | Bias correction |
|---|------|---------|------------------|---------------------|-------|----------------|-----------------|
| S0 | Incumbent rule (benchmark) | all | max(EWMA span-60 std, 0.75 × 252-day std) of daily returns | none | daily update | flat: variance × H | none (σ√H as now) |
| S1 | RiskMetrics EWMA (literature baseline) | all | daily squared returns, λ = 0.94 | none | daily update | flat: variance × H | none |
| S2 | GJR-GARCH(1,1), Student-t | all | daily returns (close-to-close; residual returns for stocks) | QML, rolling 1000 | every 5 sessions, filter updated daily | iterated, closed-form sum of h-step variances | none (variance target) |
| S3 | HAR-RV by WLS | indices/ETFs, crypto, stocks with intraday bars | RV_d (1 day), RV_w (mean of 5), RV_m (mean of 22); crypto lags 1, 7, 30 days | WLS, weights 1/fitted OLS-HAR (Clements–Preve "WLS RV-HAR"), rolling 1000 | daily | direct, one regression per H | none (levels) |
| S4 | HARQ | same as S3 | S3 plus RQ^{1/2}_{t}·RV_d interaction (daily lag only, "HARQ") | OLS, rolling 1000 | daily | direct per H | none |
| S5 | Log-HAR | same as S3 | log RV_d, log RV_w, log RV_m | OLS on logs, rolling 1000 | daily | direct per H, on log of H-average | exp(fitted + s²/2), s² = residual variance of that regression |
| S6 | Pooled centred HExp-Gl (panel) | stocks (pooled cross-section); indices (pooled across the 9 indices) | EWMAs of RV with centre of mass 1, 5, 25, 125 days, minus the expanding long-run mean; plus a 5-day CoM EWMA of the market RV (SPY RV for stocks, global average for indices) | pooled OLS, common slopes, centred (no intercepts), expanding window, an asset enters after 252 sessions | daily | direct per H | none (levels) |
| S7 | Range-HAR (no intraday data) | international indices pre-intraday; any series without bars | HAR lags of the Parkinson log-range variance (H−L)²/(4 ln 2), plus squared close-to-open return | WLS as S3, rolling 1000 | daily | direct per H | none |
| S8 | Pooled gradient-boosted trees (ML challenger) | stocks (pooled), crypto (pooled across coins) | S3 HAR lags + S6 EWMA factors + market RV lags (1, 5, 22) + VIX level (stocks/indices only); no prices, no long raw-lag stacks | library defaults, no tuning on test data; trained on the development years only | annual retrain (each January), expanding | direct per H | trained on QLIKE-consistent target in levels |

Notes on the table:

* S0 and S1 are benchmarks. The study's claims are made against S0 (the fund's rule) and S1 (the literature
  baseline). [R]
* For **single stocks with daily OHLC only**, the hedged residual has no range: OHLC of the stock and of SPY do not
  give the high or low of `r − β·r_SPY` [R]. So S3–S5 and S7 need 5-minute bars of the stock *and* of SPY. Without
  them, only S0, S1, S2 and S6 (on daily squared residual returns as the RV proxy) can run. That limit belongs in
  the pre-registration as a typed coverage condition [R].
* For **H = 55**, the HAR lags stop at 22 sessions. The 125-day centre-of-mass factor in S6 is the literature's
  way to reach longer memory (Bollerslev et al. 2018 use CoM 1, 5, 25, 125 [RD]). No reviewed paper tests H = 55
  exactly; the closest are 50 days (Liu–Patton–Sheppard, horizons 1–50 [RD]) and "1 day to 3 months"
  (Patton–Sheppard 2015 [RD]). [R]
* Crypto days are UTC calendar days with 288 five-minute bars, weekends included, and HAR lags of 1, 7 and 30 days
  (Hu, Kuo, Härdle [RD]). Crypto horizons should be fixed in wall-clock terms: H_crypto = 1, 7, 31, 77 days for
  H = 1, 5, 22, 55 sessions [R].

### 1.2 Adaptive combination (pre-registered)

1. **Primary combination: equal-weight average of the variance forecasts of S2–S8** (S0 and S1 excluded). Reason:
   the forecast-combination puzzle. Equal weights usually beat estimated weights, because estimating the weights
   adds error (Smith–Wallis 2009 [SS]). Stock–Watson (2004) found that the most successful combinations are the
   ones least sensitive to recent performance [SS]. Pollok (2022) finds an equal-weighted ensemble ranks first or
   second by Mincer–Zarnowitz R² but not by QLIKE [RD].
2. **Secondary combination: discounted inverse-QLIKE weights.**
   `w_{i,t} ∝ 1 / Σ_{s ≤ t−H} δ^{t−H−s} · QLIKE_{i,s}`. The half-life is 252 sessions, so
   δ = 0.5^{1/252} ≈ 0.99725. Burn-in is 252 scored forecasts, with equal weights before that. The δ value is
   [R]: Stock–Watson's discounted-MSFE scheme is [SS], and I did not see its δ values.
3. **Tertiary combination: fixed-share exponential weights** (Herbster–Warmuth 1998 [SS]).
   `w ∝ w·exp(−η·QLIKE)`, then each model gives share α to the others. η = 1/2, because for H = 1 the QLIKE loss
   `log h + y/h` is −2 × the Gaussian log-likelihood up to constants, so η = 1/2 is Bayesian averaging [R].
   α = 1/252 [R].
4. **Look-ahead rule (essential):** a forecast made at t for horizon H is scored only after t + H. The weights at t
   use only forecasts made at or before t − H [R].
5. **Not recommended as primary:** selecting a single model by the Model Confidence Set each period. It is a
   testing device, not a forecasting rule, and it adds the instability the combination puzzle warns about [R].

---

## §2 Model families and their out-of-sample evidence

### 2.1 GARCH family on daily returns (EWMA, GARCH, GJR, EGARCH)

* Hansen–Lunde (2005) compare 330 ARCH-type models with GARCH(1,1) out of sample. For exchange rates, nothing
  beats GARCH(1,1); for IBM, GARCH(1,1) is beaten by models with a leverage effect [AB]. The reality check "lacks
  power" to separate good and bad models [AB]. The paper also says that evaluating against squared returns
  "commonly led to a very poor out-of-sample performance", which was resolved by evaluating against intraday
  realized measures (Andersen–Bollerslev 1998) [RD].
* Kayaki–Lee (2026, arXiv 2609.06422) is a current head-to-head under QLIKE against a realized-variance target.
  The holdout is the last 30% of each sample, with expanding-window re-estimation every 250 days [RD]. HAR-RV has
  the lowest QLIKE in all six series. GARCH-family QLIKE on S&P 500: GARCH 0.377, GJR 0.357, EGARCH 0.335, HAR-RV
  0.245. On Bitcoin: GARCH 0.336, EGARCH 0.327, FIGARCH 0.312, HAR-RV 0.280 [RD]. EGARCH significantly beats
  GARCH on S&P 500 and Nikkei [RD]. The equity GARCH models use open-to-close returns from the Oxford-Man
  library [RD].
* RiskMetrics λ = 0.94 for daily data is the convention, and the `arch` library defaults to it [SS]. Its half-life
  is ln 0.5 / ln 0.94 ≈ 11.2 days [R, arithmetic]. One paper says the RiskMetrics values are "far from optimal" [SS].
  The fund's span-60 EWMA has α = 2/61, a half-life of about 20.8 days [R, arithmetic].
* Student-t innovations: Hansen–Lunde treat them as part of the model space [AB]. I found no reviewed OOS
  evidence that t versus normal changes variance-forecast QLIKE materially [R]. Keep t (QML-robust either way) [R].

### 2.2 HAR family

* **HAR-RV (Corsi 2009).** In Corsi's out-of-sample tables, models are "daily reestimated on a moving window of
  1000 observations" [RD]. HAR(3) matches ARFIMA at 1-day, 1-week and 2-week horizons for USD/CHF, S&P 500 futures
  and T-bond futures. Example: S&P 500 futures, 1-day in-sample R² of HAR(3) 0.707 against 0.648 for AR(1) [RD].
* **HARQ (Bollerslev–Patton–Quaedvlieg 2016).** The data are the S&P 500 and 27 DJIA stocks that traded
  continuously from 1997 to 2013, with a rolling window of 1000 days and daily re-estimation [RD]. OOS QLIKE ratios
  against HAR, individual stocks, rolling window (Avg) [RD]:
  * daily: HARQ 0.9902, SHAR 0.9902, HAR-J 1.0018, CHAR 0.9999;
  * weekly: HARQ 0.9309, HARQ-h 0.9873;
  * monthly: HARQ 0.9485, HARQ-F 0.9127, HARQ-h 0.8804.

  For the S&P 500 under QLIKE, the reality check for HARQ is not rejected (p = 0.871) [RD]. Under QLIKE, HARQ
  significantly beats all benchmarks for 30% of stocks at 5% and 37% at 10% [RD].
* **HAR-J, HAR-CJ, HAR-RS (semivariances).**
  * Patton–Sheppard (2015): future volatility relates more strongly to past negative semivariance. A simple model
    using this gives significantly better OOS forecasts from 1 day to 3 months. The forecasts use rolling WLS on
    1,004 observations (4 years), updated daily, with QLIKE loss [RD].
  * Bollerslev–Patton–Quaedvlieg: for individual stocks, CHAR, HAR-J and SHAR "perform only around as well as the
    standard HAR" at the daily horizon [RD]. At weekly and monthly horizons, "SHAR … offers small improvements"
    [RD].
  * Bollerslev et al. (2018): at the monthly horizon, jump and semivariance decompositions gave no better OOS
    forecasts [RD].
* **WLS estimation (Clements–Preve 2021).** "WLS-HAR … achieves up to a 24% reduction in QLIKE loss compared to the
  OLS-HAR, and up to a 21% reduction compared to the OLS-HARQ" [RD]. The data are three stock indices (SPX, DJI,
  DAX), with a 1000-day rolling window; recursive-window results are consistent [RD]. They find "little evidence in
  favour of non-linear HAR models, such as the log-HAR" over WLS-HAR [SS; matches the abstract]. Their weights
  include 1/fitted value of the OLS HAR ("WLS RV-HAR") [RD].
* **Log-HAR.** Christensen–Siggaard–Veliyev find LogHAR "remains ahead of the HAR pack" at the weekly and monthly
  horizons in their large information set. "The main driver behind the LogHAR model is its ability to handle
  outliers" [RD].

### 2.3 Realized GARCH, HEAVY, score-driven, MIDAS, regime switching

* **Realized GARCH (Hansen–Huang–Shek 2012).** The sample is 29 assets (DJIA stocks and SPY). In-sample runs
  2002–2007; out of sample is "the eight months" of 2008 [RD]. They report "substantial improvements in the
  log-likelihood" over GARCH(1,1) in and out of sample, and strong support for the leverage function [RD]. The
  measure is a Parzen realized kernel [RD]. They estimate that open-to-close volatility "is about 75% of daily
  volatility" [RD]. The OOS window is short and the loss is likelihood, not QLIKE on RV [R].
* **HEAVY (Shephard–Sheppard 2010).** These are "direct models of daily asset return volatility based on realized
  measures", with "momentum and mean reversion effects", and they "adjust quickly to structural breaks" [RD,
  abstract of the working paper]. I did not extract OOS loss numbers [R].
* **Score-driven / GAS.** The search found no primary OOS comparison against HAR under QLIKE. Secondary sources are
  mixed: in one student thesis EGARCH beats t-GAS under MSE and QLIKE [SS]. No recommendation; not shortlisted [R].
* **MIDAS.**
  * Bollerslev et al. (2018) implement beta-lag MIDAS with k = 50 and θ1 = 1, following Ghysels–Santa-Clara–
    Valkanov (2006) [RD]. The remaining tuning parameter θ2 was chosen by a full-sample grid search, so "our
    subsequent predictive MIDAS analysis is not truly out-of-sample" [RD], with common θ2 = 6.50 [RD].
  * Clements, Galvão and Kim (2008, as cited there) find HAR's parameterisation generally beats a freely
    parameterised MIDAS OOS [RD, citation inside Bollerslev et al.].
  * MIDAS is not shortlisted. HExp (S6) covers the "smooth lag" idea without a tuning parameter [RD: "do not
    depend on any unknown tuning parameters"].
* **Regime switching (MS-GARCH).** Ardia, Bluteau, Boudt and Catania (2018) find MS-GARCH gives more accurate VaR,
  ES and left-tail forecasts than single-regime GARCH at 1, 5 and 10 days [SS; publisher abstract wording]. The
  evaluation is of tail risk, not variance under QLIKE [R]. Not shortlisted [R].

### 2.4 Panel / pooled models and the common market component

* **Bollerslev, Hood, Huss, Pedersen (2018), "Risk everywhere".** "Centre" the model by subtracting the expanding
  long-run mean so that slopes can be shared across assets. Estimate on an expanding window. An asset enters after
  1 full year [RD].
  * Monthly (20-day) OOS R², equities [RD]:
    * individual estimation: static 2.9%, 21-day sum of daily squared returns 8.1%, 21-day RV 25.6%, HAR 41.2%,
      MIDAS 41.9%, HExp 48.3%, HExpGl 51.6%;
    * asset-class panel: HAR 45.8%, HExp 50.7%, HExpGl 53.8%;
    * mega panel: HAR 47.0%, HExpGl 53.3%.
  * The assets are futures across four classes, not single stocks [RD]. The R² is MSE-based; the DM tests use
    "standardized (by the mean of the realized variation) squared error losses" [RD].
  * HExp gives smoother forecasts. The variance of daily forecast changes is 2.11·10⁻⁴ for HAR against 1.37·10⁻⁴
    for HExp, and the first-order autocorrelation of changes is −0.21 against −0.01 [RD]. That matters for stop
    churn [R].
* **Zhang, Zhang, Cucuringu, Qian (2024 JFEC; arXiv v2 2023).** The data are the 100 most liquid S&P 500 stocks,
  2011-07 to 2021-06, tested 2015-07 to 2021-06, with annual retraining [RD]. Daily (1-day) QLIKE [RD]:
  * HAR-D: Single 0.190, Universal (pooled) 0.190, Augmented (pooled plus market RV) 0.180;
  * OLS Augmented 0.178;
  * MLP Augmented 0.180, LSTM Augmented 0.182.

  "Linear models slightly outperform MLPs and LSTMs at the 1-day horizon" [RD]. So pooling alone did not help
  HAR-D daily, but adding the market RV cut QLIKE by about 5% [RD numbers; R ratio].
* **Audrino–Chassot (2024, arXiv 2406.08041).** Pooled OLS HAR is in the 95% MCS for only 11.6% of 1,445 stocks
  under QLIKE, against 73.1% for single-stock WLS HAR (no VIX) [RD]. "The benefits of pooling … may diminish when
  the VIX is included" [RD]. The pooling results disagree across papers; S6 is kept as a pre-registered test of
  pooling, not as an expected winner [R].
* **Christensen et al.** tried forecasting index volatility from constituents' volatilities and found no gain
  "once we controlled for past market-wide volatility" [RD].

### 2.5 Range-based estimators (no intraday data)

* Patton (2011, working paper 2006): under his DGP, the range-based proxy has about one-fifth of the MSE of the
  daily squared return. It "yields an MSE comparable to the MSE of realised volatilities constructed using 2 to 3
  hour returns" [RD].
* Clements–Preve: HAR models on the log range LR = (1/(4 log 2))·(H−L)² "can often produce forecasts of similar
  quality to those based on RV" [RD].
* Yang–Zhang (2000) is drift-independent and handles opening jumps. Parkinson and Rogers–Satchell ignore opening
  jumps and underestimate the variance [SS].
* The default range feature is Parkinson plus the squared close-to-open return (S7). Parkinson is the estimator
  with a published HAR forecasting test (Clements–Preve) [R].

### 2.6 Machine learning versus HAR

* **Christensen–Siggaard–Veliyev (2023 JFEC; arXiv 2601.13014).** The data are 29 DJIA stocks, 2001–2017, with
  a fixed 70/10/20 train/validation/test split (847 test days). The neural network uses fixed weights "found once"
  [RD]. They evaluate by **MSE**; I found no QLIKE table in the versions I read [RD: Tables 2–13 are relative MSE].
  1-day, HAR information set: NN relative MSE 0.954–0.990 against HAR, RF 1.020, GB 1.054 [RD]. At longer horizons
  with many covariates there is "a 40% or more improvement … partly driven by a deterioration in performance for
  some HAR models" [RD].
* **Audrino–Chassot (2024).** The data are 1,445 stocks. Training is 2016–2020, validation 2021, and the test is
  **2022-01 to 2023-11** [RD]. "ML models fail to surpass the linear benchmark set by HAR when utilizing a refined
  fitting approach" [RD]. QLIKE MCS inclusion (no VIX): HAR-WLS 73.1%, RF 25.4%, GBT 22.8%, FFNN 14.6% [RD]. The
  HAR needs daily re-estimation and a 2.5–4 year window, and studies with poor HAR fitting schemes "tend to find
  that ML models outperform" [RD].
* **Pollok (2022, arXiv 2506.07928).** All S&P 500 firms, 1993–2019, daily walk-forward [RD]. HAR (250-observation
  rolling) has the lowest QLIKE: 0.2591 per average firm, against 0.3448 for LASSO and 0.6449 for a rolling-SD
  benchmark [RD].
* **Rahimikia–Poon.** Limit-order-book and news features: "ML outperforms all HAR models … on 90% of the
  out-of-sample period" for 23 NASDAQ stocks [SS]. They need order-book data that the study does not have [R].
* **Bucci (2020).** Not opened [—].
* **Verdict for pre-registration [R]:** with only RV and market information, a well-fitted HAR is a strong
  benchmark, and ML gains under QLIKE are small or negative at the daily horizon. ML may gain at 22+ sessions
  (Christensen et al., MSE only). S8 is therefore a single, untuned, pooled challenger.

### 2.7 Implied volatility (VIX)

* Audrino–Chassot: adding the VIX raises MCS inclusion for every non-pooled HAR (HAR-OLS QLIKE 22.1% → 38.6%)
  [RD].
* Christensen et al.: implied volatility is among the top predictors, ranked higher by RF and NN than by linear
  models [RD].
* For residual (market-hedged) stock variance, the VIX is a market quantity. Its value for idiosyncratic variance
  is an open empirical question in this design [R].
* No free implied-volatility data were identified for international indices or crypto in this review [R].

---

## §3 Adaptivity and retraining

* **Window length.**
  * The common default is a 1000-session rolling window (Corsi [RD], BPQ [RD], Clements–Preve [RD]).
  * Patton–Sheppard use 1,004 sessions [RD].
  * Audrino–Chassot's heatmap for 1,445 stocks (2016–2021) shows larger windows lowering RMSE, with the optimum
    around 2.5–4 years. They chose 630 days [RD].
  * Bollerslev et al. use expanding windows [RD].
  * Hu–Kuo–Härdle (Bitcoin) use 90-day rolling windows refit daily [RD]. That is far shorter than the equity
    defaults and is not adopted, for uniformity and less estimation noise [R].
  * **Default: rolling 1000 sessions for single-asset regressions; expanding for the pooled centred panel (S6).**
    [R, from RD defaults]
* **Refit frequency.**
  * Audrino–Chassot: "substantial deterioration … when the model is not re-estimated daily, even when the
    re-estimation frequency is relatively high, e.g., every two or five days" (rolling HAR) [RD].
  * Zhang et al. (expanding window): HAR-D refit weekly, monthly or yearly gives near-identical QLIKE (1-day
    Single 0.188 / 0.189 / 0.190) [RD].
  * The two disagree. The difference fits Audrino–Chassot's note that the starting window matters less under
    expanding windows [RD], but their claim that stride "remains crucial" even under expanding windows [RD]
    contradicts Zhang's table [R].
  * **Default: daily refit for all OLS/WLS models; weekly (5 sessions) for MLE models (S2), with the filter
    updated daily; annual for ML (S8).** [R]
* **Time-varying parameters.** Hu–Kuo–Härdle find HAR coefficients "evolving systematically" for Bitcoin [RD].
  Rolling re-estimation is the literature's standard way to allow this [R].
* **Online combination and the puzzle.** See §1.2. Smith–Wallis [SS], Stock–Watson 2004 [SS], and Claeskens et al.
  2015 (estimated "optimal" weights can have higher variance than equal weights) [SS]. Pollok: the simple average
  is top-two by MZ R² but loses on QLIKE to HAR [RD].
* **MCS-based selection.** Used in the literature for ranking, not as a live selector (Clements–Preve,
  Audrino–Chassot, Zhang et al., all [RD]). See §1.2.5.

---

## §4 Multi-step horizons

* **Direct versus iterated.**
  * Bollerslev et al.: "even minor model misspecifications tend to be amplified in iterated volatility forecasts,
    and, as a result, the direct forecasts … are often superior in practice" (citing Andersen et al. 2003,
    Ghysels et al. 2009, Sizova 2011) [RD].
  * BPQ and Clements–Preve use direct projection for 5 and 22 days [RD].
  * Marcellino–Stock–Watson (2006, 170 US macro series): iterated forecasts typically win, more so at longer
    horizons and with long lags [SS]. This is a disagreement between the macro and volatility literatures.
  * **Default: direct for regression models (S3–S8); iterated closed form for GARCH (S2) and flat for EWMA
    (S0, S1).** [R]
* **Aggregation.** The target is the H-session sum. Regress the H-average and multiply by H. Overlapping targets
  need Newey–West standard errors in any coefficient inference: BPQ use lags 10 (h = 5) and 44 (h = 22), i.e. 2h
  [RD]; Bollerslev et al. note the same [RD].
* **Log-model bias correction.**
  * Clements–Preve (from Proietti–Lütkepohl 2013): the log-HAR forecast is exp(fitted + s²_u/2) [RD].
  * Duan smearing (the sample mean of exp(residuals)) is the non-parametric alternative [R; Duan 1983 not opened].
  * **Default: exp(s²/2) with s² the in-window residual variance; smearing as a pre-declared sensitivity only.**
    [R]
  * A Quant SE answer (0 votes) states the same back-transform and warns that exp(log-forecast) is "closer to a
    conditional median" [RD].
* **Volatility versus variance.** Bollerslev et al.: "[E_t(RV)]^{1/2} is an upward-biased forecast of future
  volatility" (Taylor expansion E√X ≈ √E X − Var X/8 …) [RD]. The fund uses W = σ√H for stop widths, so the study
  should report the variance forecast. Converting to σ is a separate, stated step [R].

---

## §5 Evaluation methodology

* **QLIKE versus MSE (Patton 2011).**
  * "Only the MSE and the QLIKE loss functions lead to h* = E[σ̂²] = σ²" among the common losses [RD].
  * MSE is the only robust loss that depends solely on the forecast error, and QLIKE the only one that depends
    solely on the standardised error σ̂²/h [RD].
  * The robust homogeneous family nests MSE (b = 0) and QLIKE (b = −2) [RD].
  * MSE-log, MSE-SD and MSE-prop are non-robust and give distorted rankings with noisy proxies [RD].
  * QLIKE has the most power in DM tests (Patton–Sheppard 2009, as cited by Zhang et al.) [RD citation].
  * **Default: QLIKE on the variance level is the primary loss, `y/h − log(y/h) − 1`; MSE on the variance level is
    secondary.** Evaluating log forecasts directly in QLIKE is a pitfall: they must be back-transformed [RD
    forum; R].
* **Proxy noise.**
  * The daily squared return has conditional MSE 2σ⁴, against 2σ⁴/m for an RV with m intraday returns [RD,
    Patton].
  * QLIKE stays consistent with a noisy but conditionally unbiased proxy, but the test power falls [RD, R]. For
    stocks with daily data only, the H = 1 comparison will have low power, and H = 22/55 sums are less noisy [R].
* **Panel Diebold–Mariano.**
  * Zhang et al. follow Gu–Kelly–Xiu: they average the loss differential across stocks each date,
    `d_t = (1/N) Σ_i [L_i^a − L_i^b]`, and run a DM test on d_t [RD].
  * Kayaki–Lee use a Newey–West/Bartlett variance with lag ⌊n^{1/3}⌋ [RD].
  * **Default: cross-sectional mean d_t with Newey–West lag = max(2H, ⌊n^{1/3}⌋) for overlapping H-sums.** [R,
    using BPQ's 2h [RD]]
* **Model Confidence Set (Hansen–Lunde–Nason 2011).**
  * Tmax,M and TR,M statistics, with elimination of the model with the largest standardised excess loss [RD].
  * Block bootstrap; their simulations use B = 1,000 and block length 2 [RD]. Clements–Preve report 90% MCS [RD];
    Audrino–Chassot use 95% [RD]. BPQ's reality check uses a stationary bootstrap with average block 5 and 999
    resamples [RD].
  * **Default: 90% MCS, TR statistic, B = 1,000, block length max(5, H).** [R]
* **Mincer–Zarnowitz.** Regress the realized value on the forecast; unbiasedness means intercept 0 and slope 1;
  report HAC standard errors [RD, Pollok]. Diagnostic only [R].
* **Economic evaluation.**
  * Bollerslev et al.'s realized utility, read directly [RD]:
    `UoW = (1/T) Σ [8%·√RV_{t+1}/√F_t − 4%·RV_{t+1}/F_t]`.
    * The assumptions are SR = 0.4, γ = 2 and a 20% volatility target, so a perfect forecast gives 4%.
    * HExpGl is worth about 48 bp/yr against a static model, 19 bp/yr against a daily-data model, and 8 bp/yr
      against 21-day RV.
  * Audrino–Chassot and Zhang et al. report the same measure; for example, a lasso user "would be willing to pay
    8.7 basis points" to switch to HAR-WLS [RD].
  * **Stop-hit calibration** [R]: for each forecast, record whether the cumulative residual return over H crossed
    ±k·√F (k fixed from the fund's rule). Compare the hit rate with the rate the incumbent's distribution implies
    and with the S0 rate.
  * **Risk-targeting tracking error** [R]: the standard deviation of realised/targeted volatility across
    positions sized by each forecast.
* **Insanity filter.** Applied to all models, including benchmarks (BPQ) [RD]. It trims fewer than 0.1% of
  forecasts there [RD].

---

## §6 Data specifics

* **5-minute RV.**
  * Liu–Patton–Sheppard compare about 400 estimators on 31 assets in 5 classes over 11 years. With 5-min RV as the
    benchmark, there is "little evidence that it is outperformed". Benchmark-free tests find "some evidence" that
    sophisticated measures win. For forecasting, "5-minute or 15-minute truncated RV provides the best performance
    on average" [RD, Liu's 2015 Duke dissertation chapter, the working version of the JoE paper].
  * 1-minute subsampled RV and 1–5-second realized kernels/MSRV are among the few that beat 5-min RV on accuracy
    [RD].
  * **Default: 5-min calendar-time RV; 5-min truncated RV as a pre-declared alternative feature, threshold as in
    Corsi et al. 2010 (three local standard deviations).** [RD threshold wording "three"; details R]
* **Overnight returns (equities).**
  * Realized GARCH estimates open-to-close at about 75% of daily volatility [RD].
  * Ahoniemi–Lanne (2013): for the S&P 500, an RV that optimally includes overnight information fits better; for
    individual stocks, leaving overnight out fits better, and the treatment changes OOS rankings [AB].
  * Hansen–Lunde (2005) give optimal weights combining RV and the squared overnight return [AB; the weights were
    not read, and the PDF I fetched was a different Hansen–Lunde paper].
  * The study's target is close-to-close residual variance, so **default: RV_day = RV_open-to-close +
    (close-to-open residual return)²**, unweighted. Hansen–Lunde weights are not used, because their exact form
    was not read [R].
* **Crypto 24/7.**
  * Day = UTC calendar day, 288 five-minute bars, no weekend removal ("many non-institutional investors also trade
    during non-business days") [RD, Hu–Kuo–Härdle].
  * Kayaki–Lee fill missing minutes with the previous close, which contributes zero return [RD]. That biases RV
    down on gap days [R]; the study should instead treat a day with fewer than a pre-set share of its 288 bars as
    an `input_defect` [R].
  * Data source sensitivity: Bitfinex prices "de-coupled" from other exchanges, and GARCH calibration is
    "surprisingly sensitive to the data source" (Alexander–Dakos 2020) [SS; the figshare PDF returned an empty
    file].
  * Bitwise (2019): about 95% of reported volume on unregulated exchanges is "fake or non-economic" [SS]. I did
    **not** confirm which exchanges Bitwise classed as real; nothing here establishes that Binance data are clean
    [—].
  * Binance quotes are in USDT, not USD [R].
  * Hu–Kuo–Härdle find a consecutive-jump problem that biases bipower-variation jump estimates in Bitcoin [RD].
* **Jump-robust measures.**
  * Bipower variation [RD, Hu–Kuo–Härdle definition]; MedRV "designed to handle outliers or incorrectly entered
    price data" [RD, LPS].
  * For forecasting, truncated RV did best in LPS [RD]. For Bitcoin at h = 1, plain HAR beats jump and signed
    variants; at h = 30, signed and jump variants win (QLIKE 0.626–0.690 against 0.730) [RD].
  * Not shortlisted separately, to stay within 9 specs [R].
* **Survivorship.** BPQ use DJIA stocks "that traded continuously from the start to the end of our sample" [RD];
  Christensen et al. use DJIA constituents [RD]. These are survivor samples. The study's point-in-time membership
  avoids this [R].

---

## §7 Practitioner and mathematician forums

| Forum | Access | What was found |
|-------|--------|----------------|
| Quant StackExchange | WebFetch refused the domain; Stack Exchange API worked | Q31367 (question 5 votes): QLIKE must be applied on the variance scale; back-transform log forecasts; exp(m + s²/2) under log-normality; exp(m) "closer to a conditional median" (answer, 0 votes) [RD]. Q83842: practitioners' fast/slow EWMA half-lives of "ten to fifteen" and "sixty to ninety" trading days (answer, 1 vote) [RD]. Q14575: about 132 days is too little data for HAR/Realized GARCH/HEAVY (accepted, 1 vote) [RD]. Q54329: "EWMA and GARCH are good methods"; an implied/realized premium of "something like 1.07x" (1 vote) [RD]. Q8056 (18 votes): taxonomy only, no evidence [RD]. |
| Cross Validated | API worked | Q225877 (answer 5 votes): MSE rankings are "dominated by a small number of large observations"; QLIKE is robust in the right tail but "not particularly robust in the left tail" [RD]. Q492442 (10 votes): evaluate full predictive densities with proper scoring rules; variance itself is not directly elicitable without the first moment (answer, 7 votes) [RD]. |
| Wilmott | site reachable; search returned "0 matches" for every query, including "GARCH forecast" | treated as a **failed search** (probably needs a login), not "no result" |
| Nuclear Phynance | connection failed (no HTTP response) | blocked |
| QuantNet | HTTP 403 | blocked |
| r/quant | HTTP 403; web search returned no Reddit threads | blocked |
| MathOverflow | API worked; 1 irrelevant result | no relevant content |

**What practitioners say, and where they disagree with the literature** [R, from the rows above]:

* The forum evidence is thin and low-voted. It agrees with Patton on loss scale and back-transform.
* The practitioners' 60–90-day slow half-life is far longer than RiskMetrics' 11 days. The fund's span-60 sits
  between the two.
* No forum thread gave OOS numbers. The academic disagreements are larger than any forum disagreement:
  * ML versus HAR (Christensen et al. and Zhang et al. against Audrino–Chassot and Pollok);
  * pooling (Bollerslev et al. against Audrino–Chassot);
  * refit stride (Audrino–Chassot against Zhang et al.).

**Common mistakes found in the sources (all [RD]):**

* MIDAS tuning on the full sample (Bollerslev et al. admit it is "not truly out-of-sample").
* HAR baselines handicapped by a 250-day refit stride (Audrino–Chassot on Zhang et al.).
* Survivor samples (BPQ).
* Neural networks with fixed weights compared against HAR models that roll (Christensen et al.).
* QLIKE computed on exp(log forecast) without bias correction. Zhang et al. and Audrino–Chassot define QLIKE with
  exp(RV) of log RV; whether they apply a correction is not stated in the passages read.

---

## §8 Expected effect sizes

Ratios are model loss / benchmark loss; below 1 means the model is better. "Daily", "weekly" and "monthly" are
1, 5 and 22 sessions unless stated.

| Comparison | Asset / sample | Horizon | Metric | Effect | Access |
|-----------|----------------|---------|--------|--------|--------|
| HAR-RV vs GARCH(1,1) (returns) | S&P 500 / FTSE / DAX / Nikkei / KOSPI, 2000–2018, last 30% | 1 | QLIKE | 0.245/0.377 = 0.65; 0.90; 0.79; 0.79; 0.66 | RD |
| HAR-RV vs GARCH(1,1) | Bitcoin, Bitstamp 1-min RV, 2012–2025 | 1 | QLIKE | 0.280/0.336 = 0.83 | RD |
| HAR-RV vs EGARCH (best GARCH on S&P) | S&P 500 | 1 | QLIKE | 0.245/0.335 = 0.73 | RD |
| HAR vs rolling SD² (daily returns) | all S&P 500 firms 1993–2019 | 1 | QLIKE | 0.2591/0.6449 = 0.40 | RD |
| HExp / HAR vs 21-day daily-squared-return sum | equity futures, 1990s–2010s | 20 | OOS R² (MSE) | 48.3% / 41.2% vs 8.1% | RD |
| HExpGl vs static / daily / 21-day RV | multi-asset futures | 20 | realized utility | +48 / +19 / +8 bp per year | RD |
| WLS-HAR vs OLS-HAR | SPX, DJI, DAX | 1–22 | QLIKE | up to −24% | RD |
| HARQ vs HAR | 27 DJIA stocks 2001–2013 | 1 / 5 / 22 | QLIKE | 0.990 / 0.931 / 0.949 (HARQ-h 0.880 at 22) | RD |
| SHAR vs HAR | same | 1 / 5 / 22 | QLIKE | 0.990 / 0.982 / 0.991 | RD |
| Pooled+market RV vs single HAR | top-100 S&P 500 stocks 2015–2021 | 1 | QLIKE | 0.180/0.190 = 0.95 | RD |
| NN vs HAR (HAR inputs only) | 29 DJIA stocks 2001–2017 | 1 | MSE | 0.954–0.990 | RD |
| ML (trees/NN) vs HAR, many covariates | same | 22 | MSE | "40% or more" on several occasions, partly from HAR deterioration | RD |
| ML vs HAR-WLS | 1,445 US stocks, test 2022-01–2023-11 | 1 | QLIKE MCS inclusion | HAR-WLS 73% vs RF 25%, GBT 23%, NN 15% | RD |
| Signed/jump HAR vs HAR | Bitcoin 2017–2020, 90-day rolling | 1 / 7 / 30 days | QLIKE | 1.02–1.33 / 0.95–1.04 / 0.86–0.95 | RD |
| Realized GARCH vs GARCH | 29 DJIA/SPY, 2008 (8 months) | 1 | log-likelihood | "substantial" | RD, no QLIKE number |

**For power-setting [R]:**

* Against the incumbent, which is EWMA- and long-window-based on daily returns, RV-based models (where bars exist)
  should be expected to cut QLIKE by roughly 15–60%. The range comes from the return-based versus RV-based rows.
* Among RV-based models, refinements (HARQ, WLS, log, pooling, ML) should be expected to move QLIKE by about 1–10%.
* For **single-stock residual variance with daily data only**, no reviewed paper reports numbers. Gains should be
  expected to be smaller, because the proxy is a squared daily residual (Patton's 2σ⁴ proxy MSE).
* Power calculations should use the smaller end: 1–5% QLIKE differences, tested on the cross-sectional mean loss
  differential with HAC errors.

---

## §9 Search and access log (all on 2026-11-28)

**Web searches (WebSearch, standard mode):**

1. "Liu Patton Sheppard Does anything beat 5-minute RV pdf": spam results only. Re-searched with the exact title,
   which found ORA, Duke and econpapers records.
2. "Christensen Siggaard Veliyev A machine learning approach to volatility forecasting HAR QLIKE": arXiv
   2601.13014 and the CREATES WP.
3. "Bollerslev Hood Huss Pedersen Risk everywhere …": pure.au.dk PDF.
4. "Patton 2011 Volatility forecast comparison using imperfect volatility proxies QLIKE robust": NBER WP.
5. "Bollerslev Patton Quaedvlieg 2016 Exploiting the errors HARQ pdf": Maastricht author manuscript.
6. "Corsi 2009 A simple approximate long-memory model …": WU Vienna copy. The unige link was a different paper.
7. "Clements Preve A practical guide to harnessing the HAR …": GARP-hosted working paper.
8. "Zhang Zhang Cucuringu Qian …": arXiv 2202.08962.
9. "Hansen Huang Shek 2012 Realized GARCH …": CREATES WP rp10_13.
10. "Shephard Sheppard 2010 HEAVY …": Nuffield WP.
11. "Hansen Lunde 2005 Does anything beat a GARCH(1,1) …": Bauer-hosted PDF.
12. "Bitcoin realized volatility HAR … Binance … QLIKE GARCH": arXiv 1912.05228, 2609.06422.
13. "Hansen Lunde 2005 realized variance for the whole day …": records only. The Stern PDF was a different paper.
14. "forecast combination puzzle Smith Wallis 2009 …": summaries only.
15. "quant.stackexchange HAR vs GARCH …": no SE threads; found arXiv 2406.08041 and 2506.07928.
16. "quant.stackexchange QLIKE vs MSE …": no SE threads.
17. "EWMA half-life … 0.94 RiskMetrics forum": summaries only.
18. "reddit r/quant volatility forecasting …": no Reddit threads.
19. "Alexander Dakos 2020 …": records; the figshare PDF fetch returned HTTP 202 with an empty body.
20. "Ardia Bluteau Boudt Catania 2018 …": records/abstract.
21. "Marcellino Stock Watson 2006 …": records/abstract.
22. "Patton Sheppard 2015 Good volatility bad volatility …": Duke WP PDF.
23. "Bitwise 2019 … Binance": news summaries; Binance not named in the results.
24. "combining volatility forecasts … Becker Clements": secondary only; the paper was not found.
25. "Hansen Lunde Nason 2011 Model Confidence Set …": Hansen's site PDF.
26. "Ahoniemi Lanne Overnight stock returns and realized volatility": abstract (econpapers).
27. "Stock Watson 2004 combination forecasts discounted MSFE …": abstract; δ values not found.
28. "Rahimikia Poon …": thesis abstract and arXiv record.
29. "Yang Zhang 2000 …": summaries.
30. "Herbster Warmuth 1998 Tracking the best expert …": secondary descriptions.
31. "score-driven GAS … out-of-sample …": theses and secondary sources only.

**Sources actually opened (full text, read directly):**

* Bollerslev et al. 2018 (pure.au.dk, 45 pages; one page failed text extraction).
* Christensen–Siggaard–Veliyev (arXiv 2601.13014 via alphaXiv; CREATES WP 2021-03 via local text extraction).
* Bollerslev–Patton–Quaedvlieg 2016 (author manuscript).
* Patton 2006 working paper of the 2011 JoE paper.
* Liu 2015 Duke dissertation, chapter 2 (= Liu–Patton–Sheppard).
* Corsi 2009 (WU Vienna copy of the JFEC article).
* Clements–Preve 2019 working paper (GARP-hosted).
* Zhang et al. arXiv v2.
* Audrino–Chassot arXiv 2406.08041 v1.
* Pollok arXiv 2506.07928 v2.
* Hu–Kuo–Härdle arXiv 1912.05228 v3.
* Kayaki–Lee arXiv 2609.06422 v1.
* Hansen–Huang–Shek CREATES WP 2010-13.
* Shephard–Sheppard 2009 WP (abstract and front pages).
* Hansen–Lunde 2005 GARCH paper (Bauer copy; introduction).
* Patton–Sheppard 2011 WP.
* Hansen–Lunde–Nason 2011 (Hansen's site).

**Blocked, paywalled or failed:**

* quant.stackexchange.com via WebFetch (tool refusal). I used the public Stack Exchange API instead.
* reddit.com (403), quantnet.com (403), nuclearphynance.com (no response).
* Wilmott search: 0 matches for every query. Treated as failed.
* Alexander–Dakos figshare PDF: empty response.
* Hansen–Lunde 2005 "whole day" paper: the full text was not obtained.
* Journal versions on ScienceDirect, OUP and Wiley were not accessed (paywalled). Working-paper versions were used
  instead and may differ from the published text.
* WebFetch could not parse three PDFs (Risk Everywhere, Patton, Clements–Preve). Their saved binaries were
  extracted locally with pypdf.

**Not opened (stopped early on these):** Bucci 2020; Rahimikia–Poon full text; Creal–Koopman–Lucas and Harvey
(score-driven); Ghysels–Santa-Clara–Valkanov 2006; RiskMetrics Technical Document 1996; Becker–Clements 2008;
Stock–Watson 2004 full text; Smith–Wallis 2009 full text; Duan 1983; Ardia et al. full text; Bitwise report text.
The review was otherwise completed within the time budget.

---

## §10 Not claimed

* No claim that any shortlisted model will beat the incumbent on the study's data. §8 numbers come from other
  samples, other targets (mostly total, not hedged-residual, variance) and mostly other periods.
* No claim of novelty for any specification. All are published models or literature defaults. The parameter
  choices marked [R] (weekly GARCH refits, the δ half-life of 252, the fixed-share η and α, the crypto horizon
  mapping, the NW lag rule, the MCS block length, unweighted overnight addition) are my design choices, not
  literature findings.
* No claim about the cleanliness of Binance data. The only exchange-quality evidence here is [SS] or [—].
* No claim that QLIKE results for log-models in Zhang et al. and Audrino–Chassot include a bias correction.
* **Information-leakage note:** Audrino–Chassot's test window (2022-01 to 2023-11) lies inside this study's planned
  out-of-sample period. Their ranking (well-fitted WLS-HAR beats ML) has been read, and it supports S3. The same
  recommendation also follows from Clements–Preve (pre-2019 sample) and BPQ (pre-2014), which is why it was kept.
  The pre-registration should disclose this exposure.
* No claim that equal weighting is optimal; only that it is the literature's most robust default.
* No price data, repository data or fund records were read. No commit was made. No file other than this memo was
  written in the repository. Intermediate PDF text extracts are in the session scratchpad only.
