# Nextgen C: scientific, temporal and branch-isolation pre-registration

**Written 2026-11-19 before any nextgen market-data evaluations.** This independent proposal does **not** amend the actively edited `research/tree/PREREG.md` and authorises neither historical testing nor live trades.

## Existing state and explicit nonoverlap
- Branch basis: `research/tree-layer3` commit `0f83c0e3f6acff1bd37aa3687e66881b10fee191`.
- Existing in-progress MASTER retraining and architecture grid: reserved to the established tree agent. Do not duplicate.
- Existing capital-efficient 200-day core financing study planned for 2026-11-21: reserved to the incumbent coordinator. No modifications of the core rule.
- Frozen `fund/`, `main`, `.cache/`, `.claude/worktrees/`, and `research/tree/` logs/states. Lane A writes only `research/nextgen/metrics/`, lane B only `research/nextgen/optimizer/`, lane C only `research/nextgen/contracts/`. Each lane has a distinct branch from the frozen base, and a draft PR. No merge without owner review.
- 2020–2025 and 2026 have been repeatedly examined. Walk-forward predictions do **not** restore a sealed model-selection holdout. 2013–2019 is a repeatedly used development sample. R2's broad history contains residual delisting and current-exchange survivorship defects. Later CIK ticker reuse and GICS classification defects remain material.

## Testable hypotheses
**H_A: accounting invariant.** Weekly net return must reconcile to **fund NAV** gross core + gross books − financing − execution − other fees under the identical holding interval. Report a legacy raw-return/vol ratio for faithful reproduction, *and* conventional excess-return Sharpe after subtracting an aligned, vintage-frozen risk-free series. Reject a candidate before comparing Sharpe if the ledger fails. First reconcile H7 versus Layer 4 2026 date/annualisation differences.

**H_B: implementable optimisation.** A quadratic-risk portfolio based on *historically calibrated expected excess returns* (not raw model ranks) may dominate rigid top/bottom deciles in net utility after spread and square-root impact. Compare vs the unchanged B0, hysteresis, Q4 covariance and cost-ignorant controls at the same factor exposure, risk, capacity and funding. This is an untested hypothesis; the independent optimiser is only a one-period convex prototype. Full jointly financed core and sleeve optimisation is a separate later experiment.

**H_C: point-in-time validity.** Use an immutable identifier for the *historical security/issuer*, never today's ticker-to-CIK map. Every record must meet `observed_at <= published_at <= ingested_at < decision_at`, with documented latency and revision. Every supervised training target must **end before** the relevant evaluation cutoff minus purging/embargo. Missing members, delistings or any material content contract defect fail closed. An availability-indicator IC is only a diagnostic, not proof against survivorship.

## Evidence governance and research gates
1. **Engineering**: synthetic unit tests for timestamps, duplicate revisions, purging, PSD covariance, trading costs, gross/neutral/beta constraints and reconciliation. Tests must run without fetching market data.
2. **Reproduction**: explicitly authorised later integration must exactly reconstruct B0, NAV, financing and benchmark from immutable data. Confirm 2026 comparability; no unexplained differences.
3. **Development**: fit and calibrate only using information available before prediction; purged rolling-origin walk-forward; pre-register candidate counts, causal economic mechanism, alternative simpler baselines and configuration/seed budget.
4. **Already viewed results**: describe 2013–2026 results as exploratory/reused, counting all candidate variants in multiple-testing sensitivity. No re-labelling as clean OOS.
5. **Future shadow**: before first unobserved return pre-register exposure rule, test statistic, economic materiality threshold, matched-risk control, variance estimator/bootstrap rules, dates/power and multiplicity family. Tests on paired **mean excess net-utility** differences require serial-correlation correction; Sharpe-difference inference is separate and must use a validated procedure. Do not claim a Sharpe >1 on a short sample.
6. **Capacity and governance**: report net excess Sharpe, information ratio, CAGR, max DD, tail loss, all execution/financing/borrow charges, annual decompositions and AUM-impact sensitivity. No shadow is an instruction to trade.

## Primary references (mathematical provenance, not validated effect sizes)
- Gârleanu and Pedersen (2013), *Dynamic Trading with Predictable Returns and Transaction Costs*, JF 68(6), DOI 10.1111/jofi.12080.
- Jensen, Kelly, Malamud and Pedersen (2026), *Machine Learning and the Implementable Efficient Frontier*, RFS, DOI 10.1093/rfs/hhag022.
- Ledoit and Wolf (2008), *Robust Performance Hypothesis Testing with the Sharpe Ratio*, J Empirical Finance, DOI 10.1016/j.jempfin.2008.03.005.
- Bailey and López de Prado (2014), *The Deflated Sharpe Ratio*, JPM, DOI 10.3905/jpm.2014.40.5.094.

Run tests from the repository root: `python -m unittest -v research.nextgen.contracts.test_pit` or `python -m pytest -q research/nextgen`.
