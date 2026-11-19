# Nextgen A — NAV and performance measurement (research only)

Branch ownership: `research/nextgen/metrics/`. No writes to `fund/`, `research/tree/`, `.cache/`, or `main`.

This module distinguishes the incumbent's **legacy raw-return/volatility ratio** from the conventional Sharpe:
`SR = sqrt(K) * mean(r_portfolio-r_cash) / sd(r_portfolio-r_cash)`. Cash must be aligned to the same position holding periods, vintage-frozen, and expressed as fractional simple returns.

`ledger_residual` requires period NAV net return to equal gross core + gross books − funding − trading − other costs in the same NAV units. `paired_hac_mean_test` is an autocorrelation-aware **mean-return-difference** diagnostic, not an appropriate Sharpe difference test. Sharpe comparison requires separately validated Ledoit–Wolf inference or paired block bootstrap with registered block length.

**Gates before empirical use:** reproduce original B0 score unchanged; reconcile H7 versus Layer 4 2026 calendar and annualisation differences; validate financing, borrow, risk-free vintage, execution price and benchmark; preserve legacy scoreboard; no new sealed sample claims for 2020–2026.

Run synthetic tests from the **repository root**: `python -m unittest -v research.nextgen.metrics.test_nextgen_metrics` or `python -m pytest -q research/nextgen` (numpy and pytest).

References: Ledoit & Wolf, *Robust Performance Hypothesis Testing with the Sharpe Ratio*, J Empirical Finance 2008, DOI 10.1016/j.jempfin.2008.03.002. Bailey & López de Prado, *Deflated Sharpe Ratio*, JPM 2014, DOI 10.3905/jpm.2014.40.5.094.
