# Registered mathematical methods, assumptions and evaluation

Document date: 2026-11-20. All outputs are research-only, not new stock-return evidence. Base branch: research/tree-layer3. Independent branch: research/joint-state-sv-regimes-alpha-mpc-20261120. All experimental model classes below were specified *before* the user runs these fits on their local data. 2013–2019 is historically used development material. 2020–2026 was repeatedly read before and is intentionally excluded.

## A. Conditional covariance from intraday data

At weekly origin t, fit a loading matrix L_t by PCA on **past** 252 daily log returns. Freeze the loadings. Project each past 14-interval day's returns into factor increments g_(t,j,k) and factor realized variance RV_(t,j)=sum_k g²_(t,j,k). Residual stock panel E_t=R_t - F_t L_t'. The next-holding-period covariance forecast is

    Sigma_(t+1|t) = L_t H_(t+1|t) L_t' + D_(t+1|t).

D comes from POET-style adaptive soft thresholding of the orthogonal complement, tau = c sqrt(log(N)/T) times estimated residual standard deviations, then an explicitly PSD projection. This last PSD projection is numerically conservative but not identical to the original Fan–Liao–Mincheva estimator.

**HEAVY:** h_(t+1) = (1-a-b)mean(RV_past) + a RV_t + b h_t, constrained 0<=a,b, a+b<1; quasi-likelihood minimises mean(log(h_t)+RV_t/h_t). The predicted quantity is next-session *factor variance*, not five-day forward Sharpe.

**Realized GARCH:** log h_t = omega + beta log h_(t-1) + gamma log RV_(t-1), with stationary omega=(1-beta-gamma)*mean(log RV). Measurement log RV_t = xi + phi log h_t + tau*r_t/sqrt(h_t) + eps_t. Fit both return and realized-vol Gaussian quasi-likelihood together; future h_(t+1) is causal.

**Full Bayesian factor SV:** for each factor j, g_(j,t) follows latent AR(1) logvol `latent_t = phi latent_(t-1)+eta_t`, log variance `mu+latent_t`; Student-t(8) observation likelihood. NUTS posterior over (mu,phi,q,latent_1:T) and variance mixture moment E[exp(h_(t+1))|data<=t]. Optional ADVI approximation. Each individual factor's AR model ignores cross-factor volatility correlations; covariance dependence is captured only by factor loadings and residual D, not by a full multivariate volatility innovation covariance. This is an academically justified **diagonal-factor SV** prototype, not a fully coupled multivariate Bayesian SV model. To reach full Kastner-style dynamic loadings/joint latent factors, next step is joint factor SV in a larger dedicated statistical package.

Compare fixed portfolios' next-five-day realized variance proxy (SPY and equal-stock, **not MASTER**) via QLIKE; retain true timestamps and annual stress strata. Use 2018–19 development origins; 2020–26 is not selected. Forecasts must be checked for calibration and full posterior uncertainty before portfolio decisions.

## B. Latent market state

**Gaussian HMM:** hidden state z_t, transition T_ij, emission x_t|z_t=k ~ N(mu_k,diag(sigma²_k)); exact forward-backward EM on training history, then strictly forward filtering `pi_t ∝ emission(x_t)*T'pi_(t-1)`. Forecast states are filtered. Do not use full-sample smoothed states.

**HSMM:** explicit duration random variable D_k in {1,...,Dmax}, represented as augmented states (k,remaining_duration). Conditional transitions are deterministic within duration; at exit, transition to a new state with a learned categorical duration PMF. Baum–Welch on augmented chain estimates emissions, transitions and durations. This is *not* a sticky HMM; duration is explicit.

**BOCPD:** Adams–MacKay hazard h, Gaussian unknown mean and variance with Normal-Inverse-Gamma conjugate sufficient statistics, Student-t predictive likelihood, filtered run-length posterior. A cap on the run-length support is a documented approximation; it returns probabilistic change points, not a market-timing switch.

Input vector: same-day SPY log return, log realized SPY variance, log cross-section median realized variance, all known after that session. Fit HMM/HSMM using data through 2017, score 2018–19 online predictive log likelihood. BOCPD uses its own univariate SPY realized-volatility diagnostic, so its output is not directly comparable to HMM multivariate log score.

## C. MASTER conditional residual efficacy

Input is the original development panel `dev.npz`: future five-session residual `y5_i,t`, frozen MASTER score `s_i,t`, market factor return `rm_t` and PIT eligibility. For each Thursday t, regress future stock returns y5_i,t on the centred cross-sectional MASTER percentile rank, retain the OLS coefficient theta_t and its sampling variance u_t. The target **becomes available at t+5 sessions**, not at t. Fit time-series models ONLY on slopes whose maturity date is strictly before the next decision.

**Constant benchmark:** precision-weighted mean theta. **Gaussian empirical Bayes/Kalman:** theta_t=mu+phi(theta_(t-1)-mu)+eta_t; observed weekly slope theta_hat_t~N(theta_t,u_t). Estimate phi and state variance by maximising the filter likelihood; store posterior means and variances. **Full Bayesian:** PyMC AR latent state and Normal likelihood with known u_t, posterior draws with credible intervals. **Bayesian regression:** theta_t=beta0+beta'z_t, Normal prior shrinkage on conditional coefficients, posterior covariance from closed-form linear algebra. **Nonlinear MoE:** gate probabilities softmax(g(z_t)), expert-specific linear responses to z_t; deep neural gate, 3 expert states, AdamW, chronological 80/20 early stopping, seed ensemble. State predictors z_t include lagged market momentum, vol, level and return magnitude. Noise weights account for weekly sampling variance; one observation per decision week avoids stock-level pseudo-replication.

The `dev.npz` y5 label is supplied by the existing harness; we do not independently certify upstream corporate-action lineage, nor use the defective modern CIK map. The Gaussian prior/shrinkage is not a proof of sign-stable conditional alpha. Model families are scored on strictly later 2017–19 weekly slopes using MSE, predictive Gaussian negative log density, by-year performance and effective time observations. Model comparisons require paired serial-dependence adjustment and multiple-testing inventory before a conditional alpha can be admitted into actual fund weights. Nothing here optimises 2020–25.

## D. Scenario MPC and governance

At a single development origin, build an n-name joint five-session mean vector from the frozen MASTER rank and causal posterior theta. Build covariance from one selected **previously defined risk estimator** using only intraday data before that origin; draw multivariate Student-t paths with reproducible seed. Solve an H-step convex CVaR stochastic objective in CVXPY with each step's decision variables w_h and SPY hedge -beta'w_h:

    max   mean_s sum_h netReturn(s,h,w_h)
          - lambda * CVaR_tau(negative summed netReturn)
          - kappa * sum_h w_h' Sigma_uncertainty w_h
          - gamma * sum_h w_h' Sigma_scenario,h w_h

where netReturn includes forecast stocks + SPY core, 5bp stock and SPY turnover, cash funding and borrow. Constraints include `||w_h||_1 + |s_core - beta'w_h| <= max(1.9, baseline_gross)`, per-stock caps, beta and dollar neutrality bands, optional sector constraints. Default conservative financing segregates **stock** short proceeds. First-step weights are a **diagnostic forecast**, never a live target, and sample covariance scenario errors are not empirical improvements. The historical soft cap is *not* the same as the live 1.9 hard gross guard; any genuine future paired NAV experiment must select and lock one identical exposure policy for both arms.

## E. Advancement ladder

1. Schema/causality and unit tests (E0).
2. Model-quality improvement over the best appropriate benchmark, with development-only walk-forward and uncertainty (risk QLIKE, state predictive log score, alpha slope MSE/log score), not raw fund PnL (E1).
3. Externally verified execution-cost/financing contract, calibrated error distributions and a **frozen matched-capital** fund backtest on already-used history (descriptive E2 only).
4. Independently registered Protocol-9 fund forward shadow, and completed paired net-NAV observations, no Interim peeks or overlap with H9 broad-book 104-week lock (E3/4).
5. Only after human-owner approval, tightly risk-limited live implementation (E5).

No arbitrary computational cap. Method selection and hyperparameters must use only chronological development folds; the model family inventory must include the previously searched 162+ candidates. No model whose real-data fit has not run should be reported as validated on the fund.

## Primary mathematical literature

Fan, Liao, Mincheva (2013) POET; Shephard/Sheppard (2010) HEAVY; Hansen/Huang/Shek (2012) realized GARCH; Kastner (2019) Bayesian factor stochastic volatility; Guidolin/Timmermann (2007) regime portfolio allocation; Adams/MacKay (2007) Bayesian online changepoint detection; Chen/Pelger/Zhu (2024) nonlinear conditional asset pricing; Gu/Kelly/Xiu (2021) conditional autoencoder; Gârleanu/Pedersen (2013) dynamic trading with costs; Boyd et al. (2017) multi-period convex portfolio optimisation; Mohajerin Esfahani/Kuhn (2018) Wasserstein ambiguity.

## F. Paired model comparison governance

The evaluation CLI `compare pairs forecasts only on identical dates and target labels. For each fixed-date loss difference d_t=loss_(benchmark,t)-loss_(challenger,t) it reports mean gain and a Newey-West HAC standard error with four weekly lags. A pilot with <8 matched origins reports `INSUFFICIENT_TIME_ORIGINS_FOR_INFERENCE and **no t-statistic**, never a success. It also reports per-calendar-year gains, discloses the historical 162+ trial family, and performs **no automatic winner selection**. The HMM and HSMM are scored on the same multivariate filtered predictive log density; BOCPD uses a different univariate risk target and is not compared numerically to those models. A candidate is not admitted to trading from either mean QLIKE improvements or alpha slope MSE alone.
