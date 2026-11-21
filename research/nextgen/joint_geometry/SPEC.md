# Geometry-aware quantitative research — mathematical specification

**Registered 21 November 2026, PR stacked on research/joint-state-sv-regimes-alpha-mpc-20261120.** Research-only, not an alpha approval or strategy backtest. These models are deliberately **alternatives** to the existing Euclidean linear risk, HMM, alpha and MPC methods, retained for matched scoring. No historical net-portfolio return effect has been measured by this branch.

## Why a manifold is appropriate — and where it is not

Stock/factor covariance estimates belong to the cone of symmetric positive-definite (SPD) matrices, not an unconstrained Euclidean vector space. Evolving rank-k factor directions belong to the Grassmann quotient Gr(k,n): a factor-loading matrix U and UQ, Q orthogonal, encode the **same subspace**. Filtered regime distributions belong to the probability simplex, equipped with Fisher–Rao information geometry. Market-state observations may occupy a nonlinear low-dimensional set; **diffusion maps** provide inductive nonlinear coordinates. A neural network or manifold metric does not automatically imply a better forecast. Test the relevant statistical target.

### G1. Intrinsic covariance dynamics, positive-definite outputs

For A,B in SPD(k), define

- Log-Euclidean metric: `d_LE(A,B) = ||log A - log B||_F`;
- Affine-invariant metric: `d_AI(A,B) = ||log(A^{-1/2} B A^{-1/2})||_F`;
- Bures–Wasserstein distance: `d_BW²(A,B) = tr A + tr B − 2 tr((A^{1/2} B A^{1/2})^{1/2})`.

Intrinsic Fréchet forecast of future covariance `Σ_hat` under metric `d` is the minimizer of `Σ_t w_t d²(Σ_t, Σ)` over known pre-decision covariances, with fixed exponential recency weights `2^{−age/8}`. We implement Log-Euclidean (closed form), AIRM (Karcher iterative matrix logarithm) and Bures–Wasserstein barycentres, plus geodesics and fixed-basis arithmetic and EWMA baselines. `d_AI` is congruence invariant; `d_LE` is not. All covariance maps use an eigenvalue floor and reject nonconvergence rather than returning an asymmetric/indefinite matrix.

We construct **one common PCA factor subspace** U from intraday data ending **before 2016-07-01** (default), then keep U fixed for all 2017–2019 scored origins. Daily 14-bin realized factor covariance is `R_t = Σ_{b=1}^{14} (Uᵀ r_{t,b})(Uᵀ r_{t,b})ᵀ`. The forecast input for Thursday origin `t` contains only sessions `<= t−1` to avoid contamination from the closing auction; the target is the mean realized covariance over `t+1..t+5`. This intentionally skips day t's not-yet-finished return and sacrifices some recency for executable information timing. The same U is essential: separately rotating PCA coordinates each week makes matrix distances meaningless without parallel transport/Procrustes alignment.

Competing **same-target** baselines are fixed-factor sample covariance, covariance EWMA (`λ=.94`), HEAVY and realized GARCH for factor variances with causal correlation coupling, plus arithmetic Fréchet mean. These directly reuse algorithms from PR #188; unlike earlier portfolio-level QLIKE, their scores target the same factor covariance and dates as manifold methods.

**SPDNet-inspired nonlinear model:** parameterize a semiorthogonal `W=QR(W_raw)` (Stiefel), map each input SPD covariance `A -> WᵀAW`, apply eigenvalue rectification (ReEig), matrix log (LogEig), and a regularised GELU network to forecast the full future log-SPD matrix; convert back with matrix exponential. Train only on targets maturing by 2017-12-31; choose epoch using a chronological **training-only** validation tail, not the 2018–19 period. Multiple pre-fixed seeds (11,17,23) may be averaged in tangent space. This is an implementable geometric neural estimator, not a full implementation of every batch-normalisation feature of Huang–Van Gool's original SPDNet.

### G2. Changing factor subspaces / nonlinear state coordinates

For semiorthogonal bases U_t and U_s, the Grassmann principal angles are `θ_i = arccos σ_i(U_tᵀU_s)`, with intrinsic distance `d_Gr(U_t,U_s)=sqrt(Σ_i θ_i²)`. This is invariant to sign flips and orthogonal rotations within each factor space. Compute rolling factor-subspace drift using **past-only** 100- and shifted 21-session windows, then use it as an observed risk-state feature, not a new trading signal.

**Diffusion maps:** on pre-evaluation SPD observations `A_i`, build positive-semidefinite Gaussian kernel in log-SPD Hilbert space `K_ij = exp(-||log A_i-log A_j||² / 2σ²)`. Density-normalize `K_ij/(q_i q_j)^α`, α=1, obtain the Markov operator and its diffusion eigenfunctions. Remove the trivial λ=1 constant mode. The out-of-sample Nyström coordinate for new observation x is `φ_l(x)=λ_l^{-1} Σ_i P(x,i) φ_l(A_i)` (diffusion time 1 by default). **All** training points, bandwidth, density estimates and eigenspaces are frozen before evaluation; do not fit a transductive UMAP/t-SNE embedding on both training and future observations.

**Regime models:** (i) Gaussian HMM on diffusion coordinates plus factor-volatility trace, (ii) the same with Grassmann drift, (iii) an intrinsic soft AIRM centroid model with a Markov transition fitted on prior states. State scores use *filtered* posteriors only, not retrospective Viterbi/smoothed labels. The AIRM model's radial soft assignments do **not** constitute a properly normalised SPD likelihood; compare regimes on their common **next-five-session factor-portfolio QLIKE** relative to a frozen training-risk mean, NOT Gaussian predictive log density across incompatible embeddings. Scores, latent-state permutations and distribution shifts are reported separately.

### G3. Conditional MASTER-alpha reliability on geometric states

Keep all frozen existing MASTER scores/ranks/eligibility and the original five-session hedged residual-return targets. For each Thursday compute a single weekly cross-sectional rank-slope `y_t` with measurement variance `v_t`; stock names are **not independent time observations**. The underlying five-session label is available for fitting only after its maturity date `<` the next decision. Market features and covariance state use only data through `t−1` (conservative pre-close cutoff). The resulting historical training universe is limited to the overlap of MASTER 2013–19 development and the 2016–19 intraday panel; no current CIK mapping is used.

Alternative conditional-efficacy models:

1. **Log-SPD Gaussian process:** `θ(A) ~ GP(m,σ² exp(-d_LE(A,A')²/(2ℓ²)))`, heteroskedastic Gaussian observation noise based on the weekly slope measurement variance. Estimate ℓ from **past training data only**; train a chronologically updated posterior of efficacy, not an on/off switch.
2. **Nonlinear diffusion GP:** use the inductive diffusion embedding as the input to an RBF kernel; add ridge and posterior uncertainty. It is a nonlinear change of state coordinates, distinct from a plain regression on volatility.
3. **Manifold + macro GP:** append known lagged market characteristics to tangent features; kernels remain positive semidefinite by construction.
4. **Fisher–Rao regime-probability GP:** fit a HMM in *training-only* diffusion coordinates and update filtered probabilities. On simplex probabilities p, define the square-root map `ψ(p)=sqrt(p)`, Fisher–Rao distance `d_FR(p,q)=2 arccos(Σ_k sqrt(p_kq_k))`, and the **positive-definite Hellinger chordal kernel** `exp(-||ψ(p)-ψ(q)||²/(2ℓ²))`. Mix that kernel with log-SPD RBF. Do **not** naively use a Gaussian of squared Fisher geodesic distance: it need not be Mercer on the sphere.
5. **Diffusion-gated neural mixture-of-experts:** inductive diffusion features plus lagged market observables feed the existing regularised PyTorch soft gating network, with chronological early stopping and multiple seeds.

Training is **expanding, chronologically causal** within already reused development 2018–19; at each origin only completed targets are admitted. All controls and variants are counted as model trials. The primary alpha outcome is weekly slope squared error and paired conditional forecast improvement, NOT pretend backtest Sharpe. Do not infer a good alpha-timing policy from low predictive loss alone.

### G4. Geometry-aware robust posterior control

Use only past covariance snapshots in the **same** factor basis to construct an SPD ambiguity set via affine, Log-Euclidean or Bures geodesics from Fréchet centres toward observed risk-stress matrices. Each candidate Σ_j is SPD. Factor loading B and nonnegative asset idiosyncratic covariance D lift models into stock+SPY covariance `B Σ_j Bᵀ + D`. Sample Student-t scenarios from the SPD mixture, matching target 5-session covariance (scaled by df adjustment).

CVXPY receding-horizon policy chooses stock book weights `w_h` and SPY beta hedge `h_h=-βᵀw_h`, preserving the trend core s. It solves:

`max E(model net fund PnL) - λ_CVaR CVaR_{95%}(−cumulative net PnL) - λ_Σ Σ_h q_h`

with robust epigraph constraints `q_h >= (Bᵀ[w_h; s+h_h])ᵀΣ_j(Bᵀ[w_h;s+h_h]) + [w_h;s+h_h]ᵀD[w_h;s+h_h]` for **every** j. Include stock/SPY absolute turnover, borrow and margin financing under net-debit or segregated short proceeds, gross `|s−βᵀw|+||w||₁`, sector/name/beta constraints where provided and core exposure. Result is only a candidate first decision and *model-predicted* utility—not historical P&L. The historical soft gross exception `max(1.9,baseline_gross)` is used explicitly in this diagnostic; it is not equivalent to a live hard 1.9 cap. A proper live comparison must use the **same approved cap** for both arms.

## Evaluation and evidence standards

- **0. Source:** all cache SHA256 values, dates, shapes, earliest complete data, fixed PCA fit cutoff, membership coverage and rate/cost assumptions recorded. Incomplete/mismatched inputs fail closed. The riskfield intraday source currently includes **current S&P constituents**, i.e. historic survivorship is NOT certified.
- **1. Predictive risk:** same 2018–19 development origin dates, same next-five-session realized *factor-covariance* target. `D_Stein(S,F)=tr(SF^{-1}) + log det F − log det S − k` (proper relative Gaussian covariance score); portfolio-specific factor-direction QLIKE; log-Euclidean/AIRM/Bures errors. Dates and target must match before paired HAC; report yearly and stress segments.
- **2. Regime:** next-five-session risk QLIKE under filtered state versus fixed training variance, regime churn, coverage and geodesic rotation; don't interpret latent label names as factor-direction forecasts without evidence.
- **3. Alpha:** rank-slope MSE, proper heteroskedastic predictive log score if posterior calibration can be independently checked, yearly signed lift, paired HAC and multi-seed variation, no label leakage. Previous 11 extra alpha families, failed HEDGE-01 and RISK-02 belong to the >=162 trial inventory. The 2018–19 development data have already been used to compare many models and cannot be treated as pristine.
- **4. Portfolio:** after (1)–(3), separately register a matched-capital, finance-consistent paired **whole-fund net excess Sharpe** test, delta annual net return at matched risk, cost/hedge/borrow attribution and blocked-bootstrap uncertainty. A higher risk-forecast score does not automatically improve investment returns. No H9 forward lock is opened; P9 shadow requires separate owner-approved registration.
- **5. Causal production audit:** exact order timestamp (15:59 or next close) must precede all risk/MASTER features. Here the conservative geometry uses previous session `t−1`; the original MASTER score's own availability remains a separately required audit. No trade or live modification occurs from this research branch.

All tests with generated fixtures are **software/mathematical property tests only**, not synthetic return evidence. Computational cost is not an arbitrary stop criterion: optional Torch SPDNet/MoE and convex optimisation can use substantial resources when proper data and convergence diagnostics warrant it.

## Academic sources: primary / recent (selection)

1. Han and Park (2022), *A geometric framework for covariance dynamics*, Journal of Banking & Finance: https://www.sciencedirect.com/science/article/pii/S0378426621002703
2. Kastner (2019), *Sparse Bayesian Time-Varying Covariance Estimation in Many Dimensions*: https://ideas.repec.org/a/eee/econom/v210y2019i1p98-115.html
3. Arsigny et al. (2007), Log-Euclidean geometry; and empirical-Bayes SPD shrinkage: https://pmc.ncbi.nlm.nih.gov/articles/PMC11000275/
4. Huang and Van Gool (2017), *A Riemannian Network for SPD Matrix Learning* (SPDNet): https://ojs.aaai.org/index.php/AAAI/article/view/10866
5. Coifman and Lafon (2006), *Diffusion maps*: https://www.sciencedirect.com/science/article/pii/S1063520306000546
6. Jayasumana et al. (2013/2015), *Kernel Methods on the Riemannian Manifold of SPD Matrices*: https://openaccess.thecvf.com/content_cvpr_2013/papers/Jayasumana_Kernel_Methods_on_2013_CVPR_paper.pdf
7. Lian, Talmon, Zaveri, Carin and Coifman (2015), *Multivariate time-series analysis and diffusion maps*: https://www.sciencedirect.com/science/article/pii/S016516841500136X
8. Thanwerdas and Pennec (2023), *Bures–Wasserstein Minimizing Geodesics between Covariance Matrices of Different Ranks*: https://epubs.siam.org/doi/10.1137/22M149168X
9. Lesniewski and Missaoui (2026), *Grassmannian and SPD Geometry of Dynamic Factor Covariance Models* — preprint, not peer-reviewed evidence of fund performance: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6934958
10. Scalable Bayesian inference for heat-kernel Gaussian processes on manifolds (2025/26): https://academic.oup.com/jrsssb/article/88/2/516/8251661
11. A Gentle Introduction to Interpolation on the Grassmann Manifold (2026): https://epubs.siam.org/doi/full/10.1137/24M1628591
12. Boyd et al. (2017), *Multi-Period Trading via Convex Optimization*: https://stanford.edu/~boyd/papers/cvx_portfolio.html
13. Gârleanu and Pedersen (2013), *Dynamic Trading with Predictable Returns and Transaction Costs*: https://www.nber.org/papers/w15205
14. Mohajerin Esfahani and Kuhn (2018), Wasserstein distributionally robust optimisation: https://link.springer.com/article/10.1007/s10107-017-1172-1
15. The 2026 *Grassmannian and SPD Geometry* preprint and 2026 *Geometric Regime-Switching Diffusions* (https://arxiv.org/abs/2607.17192) are **research leads**, not validated deployed models.
