# GROSS-01 — Fund-aware convex allocation under the frozen SPY core

**2026-11-19 | Exploratory research, not a historical backtest.** Branch starts from `research/tree-layer3` commit `4b0d7b2c759c543c3dcf56a35ed36fca4fb0a661`. Changes only `research/nextgen/fund_aware/`; no modifications to `main`, `fund/`, original tree logs or drafts #176–#180.

## 1. Hypothesis and scope

The merged stock-only optimizer constrains `sum(abs(w)) <= 0.6`, but the existing Layer 4 simulator calculates fund gross as `abs(s - beta @ w) + sum(abs(w))`, with frozen core SPY exposure `s=1.3` in uptrends and `s=0.7` otherwise. The standalone optimizer's book limit does not imply a fund-level limit. Layer 5 PEAD documented that additive books barely fit into the uptrend capital budget.

**Important:** the simulator uses `max(CAP, gross_of(B0))` when scaling *additional* books. Hence its reference `CAP=1.9` is **not** an unconditional incumbent hard cap. Here `G=1.9` is a deliberately **hypothetical hard fund limit** that would require owner risk-policy approval before adoption. This investigation does not change the core rule or production hedge.

## 2. Exact joint optimisation

With calibrated fractional holding-period *residual excess returns* `mu`, fixed SPY core `s`, stock book `w`, and beta hedge `q=s-beta'w`:

```
E[R_fund_excess] = s*mu_SPY + mu_residual'w
Var(R_fund) = s^2*var_SPY + 2*s*c'w + w'Sigma_residual*w
G(w) = abs(s-beta'w) + ||w||_1.
```

The objective is full-fund predicted mean−gamma/2 variance−stock turnover spreads−convex 3/2 market-impact proxies−SPY net-turnover spread. The covariance block `[[Sigma,c],[c',var_SPY]]` must be PSD. The **fixed core** and book are jointly considered only for risk, hedge, gross feasibility and turnover; the SPY core decision is not optimized.

To enforce gross exactly, introduce `u_i >= w_i`, `u_i >= -w_i`, `v >= s-beta'w`, `v >= -s+beta'w`, with `sum(u)+v <= G`. These constraints are linear; the penalised utility is convex to minimise after a sign change. Additional constraints bound individual names, book gross and stock-book dollar neutrality. SLSQP uses analytic gradients, with independent post-solve checks of the **original absolute-value** constraints. Solver failure or invalid covariance aborts. A previously over-limit position can be de-risked from a core-only feasible initial guess. No broker execution or orders occur.

**Not modelled:** actual margin debit, SPY and stock borrow, cash interest, short-sale collateral, borrow recalls, dynamic liquidation, taxes, fill slippage, or true net NAV. Those gaps are material and FIN-01 addresses only counterfactual funding sensitivities.

## 3. Stage A — mechanical capital-feasibility comparison

Pre-specified 120 iid synthetic forecasts per fixed core state, 8 stocks, `G=1.9`, book cap `0.6`, name cap `0.15`, random bounded stock beta/spreads/ADV and seed 20261119. Compare:

A. Existing stock-only optimizer, with beta bound deliberately **relaxed to 1.5** to isolate the independent-book-gross issue; then *uniformly scale* the book via exact convex bisection to meet whole-fund cap.
B. New fund-aware optimizer under the full cap.

This is **not** a clone of the incumbent beta-limit setting (`0.01`). Both candidate portfolios are evaluated using the same synthetic **predicted** quadratic objective.

| SPY core | Original stock book breaks G=1.9 | Joint − scaled predicted utility ± MC SE | Mean scale haircut |
| --- | ---: | ---: | ---: |
| 1.3 | 55% | +0.0002862788 ±0.0000463883 | 5.2028% |
| 0.7 | 0% | −0.00000000925 ±0.00000000652 | 0% |

The tiny negative 0.7-core difference is numerical solver tolerance. The uptrend predicted-utility improvement is largely **mechanical**, since a fully optimised convex portfolio can weakly dominate any single feasible uniform projection under the *same* objective. This is not evidence of alpha or Sharpe enhancement.

## 4. Stage B — oracle-scored synthetic forecast-error falsification

For each core `1.3` and `0.7`, independently generate 240 eight-stock true residual mean vectors and forecasts with errors `sigma in {0,0.012,0.04}`, seed 20261201; 1440 synthetic problems. **Neither optimiser observes the true vector.** Both portfolios are scored later against the hidden true expected utility with identical covariance, spread and market impact.

| Core | Forecast noise σ | Joint − scaled **true synthetic expected utility** | Paired MC SE | Mean predicted advantage |
| ---: | ---: | ---: | ---: | ---: |
| 1.3 | 0 | +0.0001834251 | 0.0000182174 | +0.0001834251 |
| 1.3 | 0.012 | +0.0002232091 | 0.0000416911 | +0.0002914676 |
| 1.3 | 0.04 | **+0.0000237596** | **0.0000524438** | +0.0006214712 |
| 0.7 | 0 | −0.0000000290 | 0.0000000138 | ≈0 |
| 0.7 | 0.012 | −0.0000013613 | 0.0000012718 | ≈0 |
| 0.7 | 0.04 | +0.0000002601 | 0.0000005173 | ≈0 |

**Falsification:** with high forecast error, the projected utility gain largely vanishes and is statistically inconclusive even in this fixed synthetic study. The book construction should not be exploited solely from deterministic optimisation results. All figures are **quadratic utility in synthetic return units**—not annual fund returns, Sharpe, or net NAV.

## 5. Tests and reproducibility

Executed locally against byte-identical source subsequently verified as six GitHub blobs:

```
python -m pytest -q research/nextgen/fund_aware
python -m pytest -q research/nextgen
python -m research.nextgen.fund_aware.reproduce
```

- **26 new passing tests:** exact fund/hedge gross, beta, hard cap, cost sensitivity, analytic gradient finite differences, invalid inputs, failure paths, out-of-limit previous positions, SPY shorts, 60 deterministic random PSD covariance feasibility cases, cap-scaling and synthetic forecast noise.
- **165 tests, 32 subtests passed** in the combined local workspace incorporating five other still-**unmerged** draft workstreams. This does not represent a GitHub CI result or guarantee compatibility with the production application. The two component full-size synthetic runs were independently completed and saved as JSON; the combined full reproduction command exceeds the local execution limit.
- No historical fund data or hidden evaluation sample was accessed in this research iteration.

## 6. Next exploit gate — NOT executed

1. Obtain an owner-approved *hard* fund leverage/cash/margin policy; do not silently reinterpret the incumbent `CAP=1.9` as broker risk policy.
2. Build validated PIT OOF MASTER *calibrated* residual return forecasts and a causal factor/residual risk model; never put ordinal ranks directly into `mu`.
3. Reconcile actual cash, short proceeds, financing and share-borrow costs, plus trading capacity and SPY hedge returns at fund-NAV level.
4. Freeze configurations and prospective paired comparisons at matched gross/risk/financing/market beta, including the original B0 and uniform-scaling baselines. Previously viewed 2013–2026 results remain exploratory. Evaluate on truly new forward data only.
5. Exploit only after robust, material **whole-fund net excess-return** improvement with uncertainty, multiplicity and tail risk accounted for.

**Literature:** Gârleanu & Pedersen (2013), *Dynamic Trading with Predictable Returns and Transaction Costs*, JF (DOI 10.1111/jofi.12080); Kan & Zhou (2007), *Optimal Portfolio Choice with Parameter Uncertainty*, JFQA (DOI 10.1017/S0022109000004129). This is a **single-period** prototype and reproduces none of those papers' empirical results.

**Research decision:** accept the exact-fund-feasibility mathematical infrastructure; reject any claim of real trading Sharpe improvement, and do not modify live fund.
