# Nextgen B — cost-aware allocator (research-only)

Independent namespace: `research/nextgen/optimizer/`. No use of `fund/`, local live runner, `.cache/`, `research/tree/` logs or incumbent state.

For calibrated **holding-period** fractional excess return vector `mu`, PSD covariance `Sigma`, previous fund-NAV position weights `w_prev`, and AUM/ADV in the same dollar units, solve:

`max_w mu.T @ w - gamma/2*w.T @ Sigma @ w - sum_i [s_i*abs(dw_i) + k*sigma_daily_i*sqrt(AUM/ADV_i)*abs(dw_i)**1.5]`.

Constraints: gross <= 0.6 by default, per-name bound, optional dollar neutrality, and beta exposure bound. A convex smooth epsilon approximation supports SciPy SLSQP with analytic gradients; post-solve **original nonsmooth constraints** are enforced. Failure or invalid input aborts. No rankings are treated as expected return magnitudes.

This is a **static mathematical prototype**, not a reproduction of the full dynamic optimisation literature or a portfolio candidate validated on market data. Financing, borrow, hedges, core exposure, capital and margin usage, forced liquidation, settlement, actual fills and realistic historical issuer identity remain outside scope and must be included in any later fund-level test.

Ablations for a later pre-registered investigation: identical calibrated MASTER alpha input, risk-only, cost-aware, original B0 deciles, Q4 and hysteresis at the **same risk, capacity, beta and financing**. Never choose on the repeatedly inspected 2020–2026 sample. Unit tests are synthetic; run from the repository root: `python -m unittest -v research.nextgen.optimizer.test_nextgen_optimizer` or `python -m pytest -q research/nextgen`.

Academic basis: Gârleanu & Pedersen (2013), DOI 10.1111/jofi.12080; Jensen, Kelly, Malamud & Pedersen (2026), *Machine Learning and the Implementable Efficient Frontier*, DOI 10.1093/rfs/hhag022. Neither paper's empirical outperformance has been reproduced here.
