# Cross-asset information flow, contagion and nonlinear dependence: literature for an amendment to the 1962–2002 read (2026-11-25)

**Status.** A literature memo, not a test. **No project data were read or computed for it**: no file of the 1962–2002
Treasury, currency, non-US bond or commodity data was opened, and no US-equity statistic was computed. The power
figures in §6 are design arithmetic on effect sizes taken from the literature (formulas in §8). The memo informs an
amendment to `PREREG_XASSET.md`; it is not that amendment. Research only: nothing under `fund/` changes.

**Two things the reader should know first.**
1. The literature search was cut short in one place: **Elicit did not run** (the account's plan has no API access).
   Every Elicit-indexed source was searched through the web instead. Several PDFs were blocked (§9). Most finance
   claims below are therefore `search-summary`, not readings.
2. **Most of the published cross-asset predictability evidence was estimated inside 1962–2002.** The oil and
   industry-lead papers that were read directly use 1973–2003 and 1972–2001. By `PREREG_XASSET.md` §1, those years
   cannot form the prior for this read. For the hypotheses those papers support, the read would largely re-read a
   sample the field has already mined, with different instruments.

Access labels (as the brief asked, plus two used in this folder):
* `read-directly`: the passage itself was seen (alphaXiv page text, or text extracted with `pypdf` from a PDF a fetch
  saved);
* `fetch-extract`: a fetch tool returned verbatim sentences from the page; the full page was not seen;
* `abstract-only`: only the abstract or landing page was read;
* `search-summary`: only a search engine's summary was seen;
* `repository`: from files on this branch;
* `reasoning`: my inference; no source states it.

Machine-readable version: `LIT_FLOW.json`.

---

## 1. Answer in brief

* **Linear Granger regressions are the right primary tool at about 490 months.** For jointly Gaussian processes,
  transfer entropy is exactly half the Granger statistic, so the nonlinear measure has nothing extra to find
  (Barnett-Barrett-Seth 2009, `read-directly`).
  * At this sample size, the plug-in transfer-entropy bias under the null is larger than the whole signal of a
    plausible predictor: 0.0125 bits (3 bins, one lag, N = 480) against 0.0072 bits for a linear predictor with
    R² = 1% (§5.1, `reasoning` from two read sources).
* **The cross-asset effects with an economic prior are small and mostly in-window.**
  * Oil changes predict US equity negatively: slope −0.086, t −3.57 over 355 months from 1973-10 (Driesprong-
    Jacobsen-Maat working paper, `read-directly`). That implies an in-sample R² of about 3.5% (`reasoning`).
  * Metals and petroleum industry returns lead the market by one to two months over 1972–2001 (Hong-Torous-Valkanov
    working paper, `read-directly`).
  * Past bond returns predict equity returns positively across 20 countries, 1980–2016 (Pitkäjärvi-Suominen-
    Vaittinen 2020, `search-summary`).
  * The out-of-sample and post-publication record for such predictors is poor in general. Goyal-Welch-Zafirov (2024)
    find that more than a third of the post-2008 predictors fail even in-sample, and half of the rest fail
    out-of-sample (`search-summary`).
* **"Contagion" in correlation tests is mostly a volatility artefact.** The unadjusted correlation rises with the
  source market's variance: ρ = ρ* √(1+δ)/√(1+δρ*²). After the adjustment, little contagion remains in the 1987,
  1994 and 1997 crises (Forbes-Rigobon, NBER WP 7267, `read-directly`). This holds only if there is no endogeneity
  and no omitted common shock (their footnote 7, `read-directly`).
* **Daily cross-market tests in these data are dominated by closing-time asynchrony.** H.10 currency rates are New
  York noon rates (`fetch-extract`). The equity close is 16:00 ET. The futures files carry an undeclared settlement
  time (`repository`: `FREE_DATA.md` §2). The resulting bias runs from equity to the other series, not into equity
  (§5.4).
* **Proposed family (§7): six hypotheses.** Three linear Granger regressions at monthly horizon (bonds to equity,
  energy to equity, commodity currencies to commodities); one Gram-matrix state hypothesis (cross-asset absorption
  ratio); one kernel (HSIC) test of nonlinear information beyond the linear model, at weekly horizon; one quantile
  (lower-tail) Granger test.
  * Expected power at plausible effects (R² 0.5–1%) is 0.3–0.7 at the 5% level and 0.05–0.3 at the programme level
    0.10/40.
  * The read is therefore registered as a **precision estimate**, as `PREREG_XASSET.md` already is for the trend
    sleeve.

## 2. Measuring information flow and connectedness

| Method | What it measures | Inference, sample needs | Access |
|---|---|---|---|
| Linear Granger (VAR) | Reduction in one-step prediction error from the other series' past | F = ln(var restricted / var unrestricted); asymptotically χ² under the null and non-central χ² under the alternative | `read-directly` (Barnett-Barrett-Seth 2009, eq. 8 and text, p. 4) |
| Transfer entropy, TE (Schreiber 2000) | Kullback-Leibler deviation from the generalized Markov property p(iₙ₊₁ \| iₙ⁽ᵏ⁾) = p(iₙ₊₁ \| iₙ⁽ᵏ⁾, jₙ⁽ˡ⁾) | Coarse-graining or kernel estimation; the examples use 10⁴–10⁵ points; "for small r, the curves deflect down to zero due to the finite sample size" | `read-directly` (arXiv nlin/0001042, eq. 4 and Fig. 4 text) |
| TE = Granger / 2 for Gaussian processes | F(Y→X\|Z) = 2 T(Y→X\|Z) | "under Gaussian assumptions there is nothing extra to account for by nonlinear extensions to G-causality". No general asymptotic distribution is known for TE, so "significance testing for transfer entropy estimates is likely to be hard" | `read-directly` (arXiv 0910.4514, eq. 13, pp. 6–8) |
| Finite-sample TE bias | Under the null, the plug-in TE is positive in expectation: ≈ C^l(C^k − 1)(C − 1)/(2N), with C bins, lags k and l, N points | The standard estimator stays far above zero at T = 100 (normalised ≈ 0.35) and is still visibly biased at T = 1000 (≈ 0.05). A "reduced" combinatorial TE corrects it. Permutation tests need a level choice | `read-directly` (Kirkley, arXiv 2506.16215 v3, eq. S34, Figs. 2–3 text) |
| Effective TE (Marschinski-Kantz 2002) | TE minus the TE from a shuffled source, for small samples; applied to one-minute Dow Jones and DAX data | Shuffling keeps the source's marginal distribution but destroys its time structure | `search-summary` |
| Nonlinear Granger: Hiemstra-Jones 1994 → Diks-Panchenko 2006 | Correlation-integral test of conditional independence | The Hiemstra-Jones test over-rejects; "the reject rate tends to 1 when sample size increases". Diks-Panchenko replace it with an average of local dependence measures, with the bandwidth shrinking with n. Their stated bandwidth rule could not be read (PDF blocked) | `read-directly` for the over-rejection (Bai et al., arXiv 1701.03992, p. 1, citing Diks-Panchenko 2005); `search-summary` for the 2006 abstract |
| Kernel Granger (Marinazzo-Pellicoro-Stramaglia 2008) | Linear Granger in the feature space of a kernel: the target is projected on the range of the N×N **Gram matrix** Kᵢⱼ = k(Xᵢ, Xⱼ). Polynomial or Gaussian kernels | Overfitting is controlled by keeping only the eigenvectors of the enlarged space whose correlation with the target passes a Bonferroni-corrected t test. The critical coupling and noise levels scale as N^(−0.5) in their maps | `read-directly` (arXiv 0711.2643, eqs. 2–5, Fig. 2) |
| HSIC and kernel independence tests for time series | Dependence between two processes measured in an RKHS | The i.i.d. permutation bootstrap gives false positives on dependent data. A consistent procedure exists for random processes (Chwialkowski-Gretton 2014), and a wild bootstrap for degenerate kernel tests on time series (Chwialkowski-Sejdinovic-Gretton 2014) | `search-summary` |
| Signature kernels (Király-Oberhauser 2019) | A kernel on sequences built from a kernel on the state space; its features are ordered sample cross-moments | No time-series inference procedure was found in what loaded | `search-summary` |
| Mutual information | Symmetric; no direction | Time-delayed MI "does not explicitly distinguish information that is actually exchanged from that due to the response to a common input signal or history" | `read-directly` (Schreiber 2000, p. 1) |
| Copulas, tail dependence | Joint tail behaviour | Longin-Solnik (2001): correlation rises in bear markets, not in bull markets, and earlier findings suffered from "a spurious relationship between correlation and volatility" (monthly data, five largest markets) | `search-summary` |
| Diebold-Yilmaz spillover (2009, 2012, 2014) | Shares of the generalized forecast-error variance decomposition of a VAR, order-invariant (Pesaran-Shin) | 2012: daily US stock, bond, FX and commodity volatilities, 1999–2010. Cross-market spillovers were limited until 2007 and rose with the crisis. This is a descriptive measure of the forecast-error decomposition, not a return-predictability test | `search-summary` |
| Frequency connectedness (Baruník-Křehlík 2018) | The spectral representation of the variance decomposition, giving short-, medium- and long-cycle connectedness | Weekly, monthly and longer connections that aggregate measures hide | `search-summary` (arXiv 1507.01729) |
| Quantile connectedness (Ando-Greenwood-Nimmo-Shin 2022) | Quantile VAR with common factors | Credit-risk shocks among 17 sovereigns, 2006–2017, propagate much more strongly in both tails than at the mean or median | `search-summary` |
| Wavelet coherence | Time-frequency co-movement (Rua-Nunes 2009: Germany, Japan, UK, US) | The significance procedure was not reached | `search-summary` |
| PCMCI (Runge et al. 2019) | Condition selection (PC₁), then a momentary conditional-independence test with linear (ParCorr), GPDC or CMI tests | Controls false positives under autocorrelation where FullCI, bivariate Granger and permutation tests on autocorrelated data do not (Suppl. S3.3). The worked example has T = 468 months: a lag-2 partial correlation of about 0.10, p ≈ 0.036. Nonlinear tests were evaluated at T = 250 (GPDC) and 500 (CMI); "theoretical power levels for finite samples ... are mostly impossible, especially for nonlinear associations" | `read-directly` (arXiv 1702.07007 v2, pp. 3, 7–9, 22) |
| Convergent cross mapping (Sugihara 2012) | Cross-map skill from shadow manifolds of deterministic dynamics | Convergence is bounded "by observational error, process noise, and data length". Later work: CCM fails under synchronisation and intermediate coupling, and its correlations fall linearly with added noise | `search-summary` (Sugihara supplement; Mønster et al. 2016) |
| Neural Granger (Tank et al. 2021) | Component MLPs and LSTMs with group-lasso penalties on input weights | Evaluated by AUROC over a sweep of the penalty, which ranks links and has no size control or p-value. VAR(1) with coefficients 0.1: AUROC 91.6 at T = 250 and 98.4 at T = 1000 (cMLP); Lorenz-96 F = 40: 84.0 at T = 250 | `read-directly` (arXiv 1802.05842 v2, Tables 1–2, §6) |
| Random forests, boosted trees, reservoir computing for lead-lag | — | **Not searched in this run** | — |
| Random-feature ("complex") market timing (Kelly-Malamud-Zhou 2024) | Ridgeless regression on random Fourier features of the 15 Welch-Goyal predictors | Nagel (2025): the gain is a mechanical volatility-timed momentum effect, not learned nonlinearity | `search-summary` |
| Absorption ratio (Kritzman-Li-Page-Rigobon 2011) | Share of variance explained by a fixed number of principal components of the **asset-by-asset covariance (Gram) matrix** | Most significant US drawdowns were preceded by spikes; prices fell on average after spikes and rose after sharp declines. In-sample association, from the authors' own firms | `search-summary` |
| Granger-causality networks (Billio-Getmansky-Lo-Pelizzon 2012) | Principal components and pairwise Granger networks of monthly returns of hedge funds, banks, brokers and insurers | Connectedness rose over the 2000s; the measures "seem to have predictive power" for the 2007–09 crisis | `search-summary` |
| CoVaR (Adrian-Brunnermeier 2016), DCC (Engle 2002) | Tail co-movement of the system given an institution in distress; GARCH-type time-varying correlation | Descriptive and risk-measurement tools; CoVaR is "a statistical tail dependency measure" | `search-summary` |

## 3. Contagion versus interdependence

* **The bias** (Forbes-Rigobon, NBER WP 7267, pp. 11–12, `read-directly` from the text layer). Let δ be the relative
  increase in the variance of the source market x in the turmoil period. Then the conditional correlation is
  ρ = ρ* √(1+δ)/√(1+δρ*²), so "estimated correlation coefficients will be biased upward during periods of market
  turmoil". The adjusted (unconditional) coefficient is ρ* = ρ / √(1 + δ[1 − ρ²]).
* **Conditions.** "These assumptions are critical ... If endogeneity or aggregate unobservable shocks exist, then
  the Gauss-Markov assumptions are not satisfied and the adjustment" fails (footnote 7, `read-directly`; the OCR
  reads "Causs-Markov").
  * Both conditions are doubtful for cross-asset pairs that share a macro shock (for example the oil and inflation
    shocks of 1973–74 and 1979–80) (`reasoning`).
* **What survives.** With the adjustment, the incidence of contagion "falls dramatically" in the 1987, 1994 and 1997
  episodes; co-movement was already high, which the authors call interdependence (`read-directly`, pp. 1–2).
  * Corsetti et al. and Bartram-Wang argue that the adjustment is biased towards finding interdependence
    (`search-summary`, via a 2020 arXiv paper; not verified).
  * Longin-Solnik: correlation is tied to the trend of the market, not to its volatility (`search-summary`).
* **For this read** (`reasoning`):
  * A contagion test of "equity–X correlation in the core's worst months" needs a Forbes-Rigobon adjustment, or it
    will report the volatility artefact.
  * 1962–2002 contains only a handful of equity crisis episodes (1973–74, 1987, 1998, 2000–02). Any crisis-
    correlation test has a handful of effective observations, so it belongs in the diagnostics, not the
    hypothesis family. `PREREG_XASSET.md` §6 already reports the correlation in the core's worst 10% of months.

## 4. Economic evidence of cross-asset predictability into equities

| Claim | Sample | Size of effect | Out-of-sample, post-publication | Access |
|---|---|---|---|---|
| Oil price changes predict stock returns negatively: 12 of 18 developed markets and the world index | Monthly, 1973-10 .. 2003-04 (355 months), Arab Light | US slope −0.086 (t −3.57, White SE); world −0.081 (t −2.90). "a decrease of the oil price of ten percent in the US will double the expected return on the stock market in the next month". With world market returns added as a regressor, only 5 developed markets stay significant, and the US is not among them | A half-sample trading test is "still ... in sample" (their words). No post-2003 subsample test was found in what loaded | `read-directly` (ERIM WP ERS-2003-082, pp. 2, 8–9, 11, Table I) |
| Industries lead the market by up to two months (metal and petroleum negatively); the market leads few industries | Monthly, 1972-01 .. 2001-12, 34 industries | Metal: coefficient −0.106; a 2-sd shock moves next month's market by 1.39%, "roughly 32% of market volatility". That implies R² ≈ (0.32/2)² ≈ 2.6% (`reasoning`) | Robustness by split sample (not read in full) | `read-directly` (Hong-Torous-Valkanov, "Gradual Diffusion of Information and Cross-Asset Return Predictability", WP of 2002-11-13, pp. 1, 13–14; published JFE 2007, `search-summary`) |
| Industrial-metal returns predict stock returns: negative in expansions, positive in recessions | Not read | 1 sd of metal return: about −1.5% next month in expansions, +0.5% in recessions | Not read | `search-summary` (Jacobsen-Marshall-Visaltanachoti, *Mgmt Sci* 2019) |
| Past bond returns predict equity positively; past equity returns predict bonds negatively | 20 countries; earliest series 1980-01, all end 2016-12 | Cross-asset TSMOM Sharpe "45% higher" than standard TSMOM. Coefficients not read | Not read | `search-summary` (Pitkäjärvi-Suominen-Vaittinen, JFE 2020) |
| US returns lead non-US returns, not the reverse (gradual diffusion) | Monthly, 1980:02 .. 2010:12, 11 countries | Out-of-sample gains concentrated in recessions | In- and out-of-sample | `search-summary` (Rapach-Strauss-Zhou, JF 2013) |
| Commodity-currency exchange rates predict commodity prices; the reverse is less robust | Not read | — | Out-of-sample, against several benchmarks | `search-summary` (Chen-Rogoff-Rossi, QJE 2010) |
| Baltic Dry Index growth predicts global stock and commodity returns | — | — | Patchy after the crisis (press column) | `search-summary` (Bakshi-Panayotov-Skoulakis 2011 WP) |
| Carry trades crash: negatively skewed, and unwinding rises with the VIX | — | — | — | `search-summary` (Brunnermeier-Nagel-Pedersen 2008) |
| Gradual information diffusion as the mechanism | Theory: Hong-Stein (1999), **not searched**; HTV and RSZ give it as their interpretation | — | — | `read-directly` (HTV abstract) |
| The equity-premium predictors of the literature do not beat the historical mean out-of-sample | 17 variables, through 2005 | — | "not a single one would have helped a real-world investor" | `search-summary` (Welch-Goyal 2008) |
| Sign restrictions rescue small but economically meaningful out-of-sample R² | — | — | — | `search-summary` (Campbell-Thompson 2008) |
| The 2022 update | 29 variables from 26 post-2008 papers + the original 17, to 2021 | > 1/3 not significant even in-sample; of the rest, half poor out-of-sample; "a small number" still work | — | `search-summary` (Goyal-Welch-Zafirov, RFS 2024) |
| Post-publication decay of anomaly returns | — | 26% lower out-of-sample, 58% lower post-publication | — | `repository` (`LIT_PRIOR.md` §1.5, read there from McLean-Pontiff 2016) |

**What the table implies for priors** (`reasoning`):
* The in-sample effect sizes that were read are R² ≈ 2.5–3.5% a month (oil, metal).
* A 58% post-publication decline in the slope cuts R² by a factor of about 0.42² ≈ 0.18, to about 0.5–0.6%.
* The forward-relevant effect is therefore R² ≈ 0.5%, and the in-window effect up to about 3%.
* A predictor with R² = 1% would raise the US equity Sharpe ratio from about 0.42 to 0.55 a year under unconstrained
  optimal timing (§8 identity). The core cannot time without limit (1.3×/0.7× bounds), so the gain at the fund is
  smaller.

## 5. Statistical pitfalls at this sample size

### 5.1 How many observations nonlinear estimators need

* **Transfer entropy and mutual information.** Put two read sources together (`reasoning`):
  * The null bias of the plug-in TE with C bins and k = l = 1 is ≈ C(C − 1)²/(2N) (Kirkley eq. S34):
    * C = 3, N = 480: **0.0125 bits**;
    * C = 2, N = 480: 0.0021 bits;
    * C = 3, N = 10,000: 0.0006 bits.
  * A linear predictor with R² carries a Gaussian TE of −ln(1 − R²)/2 nats (Barnett-Barrett-Seth eq. 13):
    * R² = 1%: **0.0072 bits**;
    * R² = 0.5%: 0.0036 bits;
    * a daily R² of 0.1%: 0.0007 bits.
  * Binning can only lower the TE of the binned variables, by the data-processing inequality (`reasoning`).
  * At 480 months, the bias of a 3-bin TE is larger than the whole signal of a plausible predictor. A permutation
    null removes the bias in expectation, but the estimator's spread is of the same order (`reasoning`), so the
    test has little power.
  * At 10,000 days the two are comparable. A daily test is possible only if the closing-time problem (§5.4) is
    solved.
* **Kernel and conditional-independence tests.**
  * Runge et al. evaluate GPDC at T = 250 and CMI at T = 500 with strong simulated couplings. They state that
    finite-sample power for nonlinear tests "is mostly impossible" to derive theoretically (`read-directly`).
  * Their linear worked example is the closest analogue to our monthly case: T = 468 months, effect partial
    correlation 0.10, p ≈ 0.036, i.e. at the edge of the 5% level (`read-directly`).
* **Neural Granger.** Its evaluations rank links by AUROC; there is no size-controlled test (`read-directly`). It
  cannot give the null distribution a one-shot read needs without a separate permutation design.
* **CCM** assumes deterministic dynamics that noise destroys (`search-summary`). Return series are dominated by noise
  (`reasoning`). **CCM is unsuitable here.**
* **Plain statement** (`reasoning`): at about 490 monthly observations, nonlinear estimators (TE, MI, CMI, CCM,
  neural Granger) will not have useful power against alternatives the size of the published linear effects. Any
  alternative with a linear component is detected better by the linear test. A kernel test is worth running only
  as an **omnibus check for nonlinear information beyond the linear model**, at the highest frequency the timing
  allows (weekly, §7 H5), with power estimated by simulation before the read.

### 5.2 Nonstationarity and regime shifts

* **The sample spans several regimes** (`reasoning`):
  * Bretton Woods (no floating currency before 1972–73);
  * the oil shocks (1973–74, 1979–80);
  * the 1979–82 monetary regime;
  * the 1987 crash;
  * the late-1990s fall in the stock-bond correlation.
* Commodity breadth is thin before 1975 (`repository`: `FREE_DATA.md` §4: 1 to 3 markets in 1970, 24 by 1975 in
  free A).
* Goyal-Welch-Zafirov's survivors are few (`search-summary`). Coefficient instability is the rule.
* **Registration consequences** (`reasoning`):
  * report every statistic by decade;
  * treat the 1962–1972 years (bonds only) separately;
  * do not select a subperiod after the read.

### 5.3 Overlapping horizons and persistent predictors

* With persistent regressors, estimators at different horizons are "almost perfectly correlated" under the null:
  99% between 1- and 2-year dividend-yield regressions (Boudoukh-Richardson-Whitelaw 2008, `search-summary`).
* Long-horizon regressions have a small-sample bias linear in J/T (Boudoukh-Israel-Richardson 2021, `search-summary`;
  Stambaugh 1999 only as a bibliographic record).
* **Registration consequences** (`reasoning`):
  * one non-overlapping monthly target;
  * a 12-month predictor is allowed, but its persistence and its innovation correlation with equity must be kept
    in the null (a restricted-model residual bootstrap with paired blocks, §7);
  * do not add horizons as if they were independent tests.

### 5.4 Asynchronous closes (decisive for daily data)

* **Stamps in these data:**
  * H.10 currencies are "noon buying rates in New York" (`fetch-extract`, federalreserve.gov H.10 About page);
  * the time of day of the H.15 yields was not established (`reasoning`: treat it as a typed defect);
  * pysystemtrade futures carry a 23:00 stamp, and their settlement time is not declared (`repository`:
    `FREE_DATA.md` §2 defect 4);
  * US equity closes at 16:00 ET.
* **The direction of the bias** (`reasoning`):
  * The currency return for day t+1 (noon t to noon t+1) contains the 12:00–16:00 window of day t, which is also in
    day t's equity return. Mechanically, equity "leads" currencies by a day.
  * In the direction that matters to the fund (other assets → equity), the other asset's day-t return ends before
    the equity day t+1 begins. That creates no overlap, hence no spurious lead into equity.
  * But it gives no clean test either. Information between the other asset's stamp and 16:00 is already in the
    day-t equity return, so the one-day "lead" understates a true lead or reverses its timing.
* **Registration consequences** (`reasoning`):
  * Daily or weekly tests skip one full day between the predictor window and the equity target window. The weekly
    test in H5 does this.
  * The daily correlation of the equity return on day t with the currency return on day t+1 is a **failure
    control**. Because of the 12:00–16:00 overlap, it must be nonzero (one-sided at 5%) with the same sign as the
    same-day equity–currency correlation, if the stamps are as described. If it is not, the stamps are not what the
    memo assumes, and the weekly hypothesis H5 is void. Only currencies qualify, because only their stamp is known.
* Burns-Engle-Mezrich (1998) model asynchronous correlation with a vector moving average (`search-summary`). Scholes-
  Williams (1977) and Lo-MacKinlay (1990) are the classical references; the search returned nothing on the latter.

### 5.5 Multiple testing and data snooping

* White's Reality Check (2000), Hansen's SPA (2005) and Romano-Wolf's stepwise tests (2005) control the family-wise
  error over a set of strategies using the joint bootstrap (`search-summary`).
* The programme threshold is 0.10/N, with N recounted from `DATA_USE.md` (`repository`: `SCOPE.md` §4; N was 38 on
  2026-11-02).
* **Registration consequences** (`reasoning`):
  * a fixed family of six;
  * Holm (or Romano-Wolf on the joint bootstrap) at family level 0.10;
  * all six added to N;
  * the programme-level p reported beside each result.

### 5.6 Gram matrices of asset returns

* A sample correlation matrix of n assets over a window of w days is noise-dominated when n/w is not small
  (`reasoning`; random-matrix results on this, such as Laloux et al. 1999, were **not searched**).
* With about 40 markets, a 63-day window gives n/w ≈ 0.6.
* **Registration consequence:** the absorption ratio in H4 is computed on four or five asset-class composites, not
  on 40 markets.

## 6. Power at our sample sizes (design arithmetic, §8)

One-sided power of a predictive-regression slope test, normal approximation, nc = √(T R²/(1 − R²)):

| Case | T | R² 0.25% | 0.5% | 1% | 2% | 3.5% |
|---|---:|---|---|---|---|---|
| H1 bonds → equity (1963–2002) | 480 | 0.29 / 0.15 / 0.04 | 0.46 / 0.28 / 0.10 | 0.71 / 0.53 / 0.27 | 0.93 / 0.84 / 0.63 | 0.99 / 0.98 / 0.91 |
| H2 energy → equity (1981–2002) | 264 | 0.20 / 0.09 / 0.02 | 0.31 / 0.16 / 0.05 | 0.50 / 0.31 / 0.12 | 0.75 / 0.58 / 0.31 | 0.93 / 0.83 / 0.61 |
| H3 currencies → commodities (1974–2002) | 348 | 0.24 / 0.12 / 0.03 | 0.37 / 0.21 / 0.07 | 0.59 / 0.40 / 0.18 | 0.85 / 0.70 / 0.44 | 0.97 / 0.92 / 0.77 |

Each cell reads: 5% level / family Holm first step (0.10/6) / programme (0.10/40). For daily data (T = 10,000),
R² = 0.05% gives 0.72 / 0.54 / 0.28.

H4, the absorption-ratio spike: a mean difference with monthly σ = 4.4% (`reasoning`) and 48 or 77 spike months out
of 480:

| Next-month difference | n₁ = 48 | n₁ = 77 |
|---|---|---|
| 0.5% | 0.18 / 0.08 / 0.02 | 0.23 / 0.11 / 0.03 |
| 1.0% | 0.44 / 0.26 / 0.09 | 0.57 / 0.38 / 0.16 |
| 1.5% | 0.72 / 0.54 / 0.29 | 0.86 / 0.73 / 0.47 |

These are computed at T = 480. H4's actual window (1977–2002, T ≈ 312) with 48 spike months gives 0.18 / 0.08 / 0.02,
0.42 / 0.25 / 0.09 and 0.70 / 0.52 / 0.26 for the three rows.

**Reading** (`reasoning`):
* At the forward-relevant effect (R² ≈ 0.5%), no hypothesis reaches design rule 3's P ≥ 0.5 at the programme level.
* At the in-window published sizes (R² 2.5–3.5%), H1 and H2 would. But those sizes come from the same years, so a
  "pass" there is largely a replication of mined evidence.
* H5 (kernel) and H6 (quantile) have no closed-form power. Each must be calibrated by simulation before the read,
  on synthetic data only (§7).
* The family is therefore a **precision estimate** (design rule 6), with the verdict classes of `PREREG_XASSET.md`
  §6.

## 7. Proposed family for the 1962–2002 read (labelled reasoning; for the owner to rule on)

**Scope ruling the owner must make first** (`repository` + `reasoning`):
* H1, H2, H4 and H6 test **exposure-timing information for the US-equity core** on a target series (US equity
  1962–2002) that the project has already used for exposure-rule reads: `SCOPE.md` S2 and S3, and the adaptive-core
  US read.
* The predictors are unread; the target is spent.
* By CLAUDE.md rule 17, anything that would change the core's exposure is the owner's strategic policy: it may be
  tested once, pre-registered, on long history.
* These four hypotheses are therefore research on a possible future exposure rule, registered once, never tuned.
  H3 concerns a second (commodity) book.

**Common design** (all hypotheses):
* Target months 1963-01 .. 2002-12, with markets entering as in `PREREG_XASSET.md` §2.
* Equity: the French US market excess return, as in `PREREG_XASSET.md` §5.
* Control set Zₜ = {the equity excess return in month t; the core's state at the end of month t (above or below the
  200-session average)}. Each hypothesis therefore asks for information *beyond what the core already knows*.
* Null distribution: the **restricted-model residual bootstrap**:
  * fit the model under H₀;
  * resample the joint vector (restricted residual, the predictor's own monthly innovations) in stationary blocks
    (mean 12 months), which keeps the contemporaneous correlation and the persistence (§5.3);
  * rebuild the predictor;
  * 10,000 draws, seed 20261125.
* Reported beside each test, not decisive: the recursive out-of-sample R² from 1980-01 with Campbell-Thompson sign
  restrictions, by decade.
* Multiplicity: Holm across H1–H6 at family level 0.10; the programme-level p also reported; N += 6.
* Verdict per hypothesis:
  * **supported**: Holm-adjusted p ≤ 0.10 and out-of-sample R² > 0;
  * **rejected**: the 90% upper bound of the implied R² is below 0.25%, the value at which the timed Sharpe moves by
    about 0.03 a year (§8);
  * **inconclusive**: otherwise.
* Posterior: shrink towards an out-of-window prior of R² ≈ 0.5% (§4).

| # | Hypothesis, exact statistic | Horizon, sample, T | Null and its distribution | Expected power | Why linear or nonlinear |
|---|---|---|---|---|---|
| **H1** | **Bonds → equity.** OLS of r^e_{t+1} on [1, Zₜ, x₁ₜ]; x₁ₜ = 12-month excess return of the US 10-year proxy (`proxy.py`). Statistic: t of the x₁ coefficient, one-sided (+), the sign from Pitkäjärvi et al. | Monthly; 1963–2002; T ≈ 480 | H₀: β = 0; residual bootstrap as above | R² 0.5%: 0.46 (5%), 0.10 (programme); R² 1%: 0.71, 0.27 | The prior is a sign and a slow-rebalancing mechanism; nothing suggests a nonlinear form. Linear is the most powerful. The lookback in Pitkäjärvi et al. was not read, so 12 months is chosen to match the sleeve's signal and must be registered as a choice |
| **H2** | **Energy → equity.** As H1, with x₂ₜ = last month's excess return of the equal-weight energy futures composite (heating oil from 1980, WTI from 1988, gasoil, Brent where present; `FREE_DATA.md` §2). One-sided (−) | Monthly; 1981–2002; T ≈ 264 | As H1 | In-window published size (R² ≈ 3.5%): 0.93 / 0.61. Forward size (0.5%): 0.31 / 0.05 | Linear (Driesprong et al. use a linear lagged regression). **Labelled a replication**: the years overlap their 1973–2003 sample, so this read contributes instrument (futures vs spot) and core-conditional evidence, not independent discovery |
| **H3** | **Commodity currencies → commodities** (second book). OLS of the next-month equal-weight commodity futures excess return on [1, its own month-t return, x₃ₜ]; x₃ₜ = equal-weight month-t excess return (spot + carry) of AUD and CAD against USD. One-sided (+) | Monthly; 1974–2002; T ≈ 348 | As H1, with the commodity composite as target | R² 1%: 0.59 / 0.18 | Linear (Chen-Rogoff-Rossi, `search-summary`; their horizon, likely quarterly, was not read). Relevant to the commodity leg of the trend sleeve, not to the core |
| **H4** | **Gram-matrix state → equity.** AR_t = largest-eigenvalue share of the correlation matrix of daily returns of 5 composites (US equity, US 10-year, currency basket, commodity composite, gold). Built from 1976, when all exist. Spike_t = 1 if (AR over 15 days − AR over 252 days) / sd over 252 days ≥ 1 at the end of month t. Statistic: coefficient of Spike_t in the H1-form regression, one-sided (−) | Built daily, read monthly; 1977–2002; T ≈ 312 | As H1, with the daily composites resampled in blocks and AR rebuilt in each draw | 1%/month with 48 spike months at T ≈ 312: 0.42 (5%) / 0.09 (programme) | Nonlinear by construction (a threshold on a second-moment state). The prior (Kritzman et al., `search-summary`) is outside the window but concerns equity sectors, not asset classes: the cross-asset version is an extrapolation. The 15/252-day form is our registered choice; their exact definition was not read |
| **H5** | **Nonlinear information beyond linear (kernel).** Weekly: target the equity excess return Thursday close → next Thursday close; predictors the week to the preceding Wednesday, so a full day is skipped (§5.4). Xₜ = (10-year, currency basket, commodity composite weekly returns). Fit the linear model on [Zₜ, Xₜ]. Statistic: HSIC between the linear residual and Xₜ, Gaussian kernels, median-heuristic bandwidth fixed at registration | Weekly; 1974–2002; T ≈ 1,500 | H₀: residual independent of Xₜ. **Wild bootstrap** for time series (Chwialkowski-Sejdinovic-Gretton), not an i.i.d. permutation, which over-rejects under dependence (§2) | **Unknown; estimated by simulation before the read**, on synthetic data matched in T and autocorrelation. Expected low (`reasoning`) | The only nonlinear test kept. It is an omnibus check of whether anything beyond linear exists. It runs at weekly frequency because monthly T is too small (§5.1). Transfer entropy (effective, 3 bins) and Marinazzo's filtered kernel-Granger index are reported beside it as descriptions, not tests |
| **H6** | **Tail flow (quantile Granger).** Quantile regression at τ = 0.10 of r^e_{t+1} on [1, Zₜ, x₁ₜ, x₂ₜ, x_FX,t] (one-month returns). Statistic: the rank-score (or Wald) test that the three cross-asset slopes are jointly 0 | Monthly; 1981–2002 (energy from 1981), and 1974–2002 without energy, as one registered fallback; T ≈ 264 / 348 | As H1, with the restricted quantile model | Not closed-form; simulation before the read. Expected below the mean-regression power at equal effect (`reasoning`) | Nonlinear in distribution, linear in parameters: the only "contagion" form that predicts drawdowns rather than describing them. Prior: tail connectedness (Ando et al., `search-summary`) |

**Diagnostics, outside the family** (not counted in N, `reasoning`):
* the daily failure control of §5.4;
* Forbes-Rigobon-adjusted correlations of equity with each composite, in the core's worst 10% of months against the
  rest;
* the Diebold-Yilmaz total and directional spillover, and the Baruník-Křehlík frequency bands (1–5, 5–20 and over
  20 days) on daily composites by decade;
* the reverse directions of H1 and H3.

**What the family deliberately leaves out** (`reasoning`):
* *US → international* (Rapach-Strauss-Zhou): the wrong direction for a fund that trades the US.
* *Industrial metals*: copper starts in 1995 in the free data (`FREE_DATA.md` §2).
* *Neural Granger, CCM, PCMCI-CMI*: no power or no size control at these sample sizes (§5.1).
* *Credit*: not in the data list.
* *A daily-frequency family*: blocked by the undeclared futures settlement times and H.15 stamps until they are
  documented.

## 8. Formulas behind the numbers

`lit_flow_power.py` (this folder) reads no data. Its output is stored verbatim in `LIT_FLOW.json` → `power_design`,
and §5 and §6 copy from it, rounded as the script rounds.

```
power (one-sided)       = Phi( sqrt(T R2 / (1 - R2)) - z ),  z = 1.645 (5%), 2.128 (0.10/6), 2.807 (0.10/40)
power (mean difference) = Phi( d / (sigma sqrt(1/n1 + 1/n2)) - z ),  sigma = 4.4%/month (reasoning)
TE null bias (bits)     = C (C-1)^2 / (2N)            [Kirkley eq. S34 with k = l = 1]
Gaussian TE (bits)      = -ln(1 - R2) / 2 / ln 2      [Barnett-Barrett-Seth eq. 13]
timed Sharpe (monthly)  = sqrt( (S^2 + R2) / (1 - R2) ),  S = 0.42/sqrt(12)  (reasoning: an identity for an
                          unconstrained mean-variance timer; not read from Campbell-Thompson)
```

## 9. Search and access log

```
Query: alphaXiv discover "transfer entropy / Granger / kernel Granger / nonlinear Granger / financial markets";
       "PCMCI / neural Granger / convergent cross mapping / causal discovery"   Date: 2026-11-25
Opened (read-directly): Schreiber nlin/0001042; Marinazzo et al. 0711.2643; Barnett et al. 0910.4514; Tank et al.
        1802.05842; Runge et al. 1702.07007 (by ID; the title lookup failed); Kirkley 2506.16215; Bai et al. 1701.03992
Blocked: none in alphaXiv; the discover tool surfaced mostly 2023-2026 papers, not the seminal ones
Stopped: no
```

```
Query: Elicit search_papers (four queries: nonlinear Granger; Forbes-Rigobon; Driesprong; Diebold-Yilmaz)   Date: 2026-11-25
Opened: none
Blocked: all four (api_access_denied: the account's plan has no Elicit API access)
Stopped: yes (connector unavailable). Elicit-indexed literature was searched through the web instead
```

```
Query: web searches (about 30) on the finance papers of §3-§5   Date: 2026-11-25
Opened (read-directly via pypdf of fetched PDFs): Hong-Torous-Valkanov WP (escholarship qt6x49x543);
        Driesprong-Jacobsen-Maat WP (repub.eur.nl/pub/1017, ERS 082); Forbes-Rigobon NBER w7267 (OCR text layer)
Opened (fetch-extract): Fed H.10 About page; repub.eur.nl/pub/1017 landing abstract
Search summaries only: Pitkäjärvi et al.; Rapach-Strauss-Zhou; Chen-Rogoff-Rossi; Jacobsen-Marshall-Visaltanachoti;
        Bakshi et al.; Welch-Goyal; Campbell-Thompson; Goyal-Welch-Zafirov; Diks-Panchenko 2006 abstract;
        Diebold-Yilmaz 2012; Baruník-Křehlík; Ando et al.; Kritzman et al.; Billio et al.; Adrian-Brunnermeier;
        Engle; Chwialkowski-Gretton; Chwialkowski-Sejdinovic-Gretton; Király-Oberhauser; Sugihara supplement;
        Mønster et al.; Marschinski-Kantz; Longin-Solnik; Rua-Nunes; White; Hansen; Romano-Wolf;
        Boudoukh-Richardson-Whitelaw; Boudoukh-Israel-Richardson; Kelly-Malamud-Zhou; Nagel; Brunnermeier-Nagel-Pedersen;
        Burns-Engle-Mezrich
Blocked: core.ac.uk/download/18510526.pdf (403); alphaarchitect.com Pitkäjärvi summary (403);
         lem.sssup.it Diks-Panchenko PDF (TLS certificate error; an insecure retry was refused by the session's
         permission check and not attempted again)
Nothing returned: Boyer-Gibson-Loretan 1999; Lo-MacKinlay 1990; Diebold-Yilmaz 2014; the Lustig-Roussanov-Verdelhan
         dollar factor; post-2003 out-of-sample tests of the oil effect; the Diks-Panchenko bandwidth constants
Not searched: Hong-Stein 1999; Patton copulas; random forests, boosted trees and reservoir computing for lead-lag;
         Laloux et al. random-matrix theory; Clark-West; Inoue-Kilian; Hodrick 1992; Zhang et al. KCI test
Stopped: no (budget allowed the above; the gaps are listed, not filled)
```

## 10. Not claimed

* No statistic of any project series was computed or seen. Every power figure is arithmetic on assumed effect sizes.
* No claim that any hypothesis will be supported. No claim that nonlinear dependence is absent: only that, at these
  sample sizes, the tests listed have little power against effects of the published size.
* `search-summary` rows are not readings. Their numbers (Sharpe "45% higher", "−1.5%", the sample windows) must be
  copied from the papers before they enter a registration.
* The Diks-Panchenko bandwidth rule, the Kritzman spike definition, Pitkäjärvi et al.'s lookback and Chen-Rogoff-
  Rossi's horizon were **not read**. §7 fixes our own choices in their place, and the registration must say so.
* No claim of novelty for the family. Searches of alphaXiv and the web found no earlier test of this exact set;
  Elicit could not be searched.
