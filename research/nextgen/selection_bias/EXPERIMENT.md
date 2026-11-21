# SEL-01 — selection-bias falsification under a correlated search tree

**Research date:** 2026-11-19. **Status:** wholly synthetic Monte Carlo, designed *before running* the fixed experiments. Does **not** reopen 2013–2026 historical data, run a trading model, refit MASTER or claim empirical Sharpe.

## Hypothesis

Selecting the largest measured Sharpe among many correlated model trials can create apparent in-sample Sharpe > 1 even if *every single model* has the same true Sharpe < 1. The apparent discovery fails on independently generated forward observations. Candidate dependence reduces but need not eliminate the optimism. This illustrates why the incumbent's repeatedly inspected 2020–2026 windows cannot be treated as sealed holdout after iterative design selection.

## Locked simulation specification

- **Number of candidates**: 162, matching `L4_exploit/REPORT.md`'s reported trial family count, but **not** using the returns of those trials.
- **Training period**: 302 synthetic independent weeks (matching B0's published 2020–2025 count).
- **Forward period**: a fresh, independent synthetic 302 weeks of the **selected model**.
- **All candidate population annual Sharpe**: 0.60; annualisation `sqrt(52)`, weekly sigma `0.02`, weekly mean `0.6 * 0.02 / sqrt(52)`.
- **Candidate pairwise correlation of weekly random returns**: `rho in {0.0, 0.8, 0.95}`, with one common Gaussian factor and independently generated idiosyncratic Gaussian disturbances; independent draws across weeks.
- **Search**: select the greatest *measured* annual Sharpe of 162 candidates, **once** per simulation replication.
- **Replications**: 1,000 independent replicates for each rho, same fixed PRNG seed `20261119` reinitialised for each condition.
- **Reported outcomes**: mean selected in-sample Sharpe, mean independent forward Sharpe, selection optimism and simulation frequency of an in-sample measured winner >1.0 although the true Sharpe is only 0.60. No fitted parameters or trial tuning after seeing results.

`python -m research.nextgen.selection_bias.reproduce` runs the locked design and prints JSON. No market-data paths or APIs are touched.

## Simulated results (deterministic seed)

| Candidate correlation | Mean winner sample Sharpe | Mean selected forward Sharpe | Mean selection optimism (Monte Carlo 95% error) | P(winner sample >1.0) (Monte Carlo 95% error) |
| --- | ---: | ---: | ---: | ---: |
| 0% | 1.7315 | 0.5827 | 1.1489 ±0.0284 | 1.000 ±0.000 |
| 80% | 1.1322 | 0.6073 | 0.5249 ±0.0343 | 0.642 ±0.030 |
| 95% | 0.8820 | 0.6132 | 0.2689 ±0.0354 | 0.396 ±0.030 |

The MC error bars describe the **finite 1,000-replicate simulation estimate**, not confidence intervals for the real fund. The normal-iid first-order annual Sharpe standard error for a single true-Sharpe-0.6 strategy observed for 302 weeks is `sqrt((52 + 0.6**2/2)/302) = 0.41567`. It must not be substituted for a time-dependent, correlated, post-selection empirical inference.

**Interpretation:** apparent sample SR > 1 is routine when a broad family of models with true SR 0.6 is screened, even at strong within-family correlation. This is NOT an estimate of the real team's actual overfitting, probability of failure, or the true Sharpe of any existing model. Heavy tails, heteroskedasticity, market-state transitions, broker fees and changing research choices are deliberately excluded.

## Executed engineering checks

- Nine synthetic tests + eight edge-case subtests: deterministic equality, no-selection negative control, correlation monotonicity, forward independence, input guards and first-order Sharpe SE.
- New `core.py`: 100% statement coverage (35/35).
- Branch-only tests, including the four previously merged nextgen modules: **46 passed, 16 subtests passed**.
- Local broader suite including **unmerged** PR #176 accounting audit and **unmerged** PR #177 finance stress: **77 passed, 24 subtests passed**. Do not interpret the broader suite as code already present on this PR branch.
- Code source in GitHub is compared to exact Git blob SHA of local executed Python files.

## Implications for the actual trading research

1. Publish and preserve the **complete multibranch trial family**, including failed variants, altered models, seeds, feature tests, financing cases and outcome-motivated reruns. 162 is an inventory snapshot, not necessarily all adaptive decisions.
2. Require preregistered point-in-time forward *whole-fund* net excess-return performance; previous 2013–2026 results are already used and exploratory.
3. Compare at **matched portfolio risk, margin/cash treatment, capacity and all costs**. Use an appropriately paired serial-dependence-adjusted test for net return improvement and a validated separate Sharpe difference test. The existing simple percentile bootstrap in PR #175 was explicitly exploratory, not a significance test.
4. Calculate prospective test power and expected duration before declaring SR>1. A single six-year sample's iid Sharpe SE can be of order 0.4; paired differences may be far more precise only when correctly designed.
5. Introduce no model into the live fund based on this simulation; it is a *research search-governance stress test*.

## Academic provenance

- White (2000), *A Reality Check for Data Snooping*, Econometrica, DOI 10.1111/1468-0262.00152.
- Harvey, Liu & Zhu (2016), *…and the Cross-Section of Expected Returns*, RFS 29(1), DOI 10.1093/rfs/hhv059.
- Bailey & López de Prado (2014), *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality*, JPM, DOI 10.3905/jpm.2014.40.5.094.

**Isolation:** changes only `research/nextgen/selection_bias/`, from unchanged research/tree-layer3 baseline. No live code, trading changes, broker interaction, cached market data or alteration to incumbent results.
