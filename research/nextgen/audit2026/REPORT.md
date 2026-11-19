# Research-only 2026 accounting-metric reconciliation

**Audit date:** 2026-11-19. **Status:** deterministic cross-check of previously published JSON summaries only. No raw holding-period return series, market cache, trade fills, live runner, or still-sealed data accessed. **Do not interpret this as a new independent 2026 experiment.**

## Source provenance (immutable Git blob hashes)

- `research/tree/H7_RESULT.json` — `79183b1a021344369ba9f4e539cad98b4e718a6f`
- `research/tree/H7_DECOMP.json` — `ef8aa5a3ce35b43a0f4c2a99c0d73f438358d5f2`
- `research/tree/L4_exploit/RESULT.json` — `b18b04d9b884500d46d5ede566e444044e0b04a3`

## Cross-reconciled observations: B0, 2026-01-08 through 2026-10-29

| Measure | H7 published | L4 published | Audit |
| --- | ---: | ---: | --- |
| Sample length | 43 weeks | 43 weeks | Identical |
| Fund annual *arithmetic*, % | −1.4932577181 | `Sharpe × vol = −1.4932577181` | Residual < 1e-12 pp |
| Legacy raw-return/volatility ratio | −0.1035945612 | −0.1035945612 | Identical |
| Fund peak-to-trough drawdown, % | −11.9157511517 | −11.9157511517 | Identical |
| MASTER book annual arithmetic, % | −2.8999097467 | −2.8999097467 | Identical |
| Fund geometrically annualised, % | not reported | **+0.4331250960** | Different metric, not conflicting return |
| Fund cumulative simple, % | not reported | **+0.3567996537** | Implied elapsed 301.0 calendar days |

The reported discrepancy of **1.9263828142 percentage points** is the difference between `H7`'s annualised arithmetic mean of **week-normalised** period returns and `L4`'s geometric annualisation of actual compounded wealth. These values are *not estimates of the same population statistic*.

For unequal holding periods of `d_i` calendar days and simple total-NAV returns `r_i`, the two exact implementations are:

```text
H7 arithmetic = 100 * 52/n * sum_i (7/d_i) * r_i
L4 geometric  = 100 * (product_i(1+r_i)^(365.25/sum_i d_i) - 1)
```

Only one holding period observation per row is available in H7/L4 summaries. These formulas can have **opposite signs** if holding periods differ, without inconsistent fund NAV paths. The synthetic two-period test (`days = [2,12]`, `returns = [-2%,+4%]`) demonstrates this mathematically. The individual 2026 `d_i` values were **not** available from committed summaries, so the precise contribution of duration weighting to this historical sign reversal remains unverified.

**Important:** The current `H7` field name `pct_per_year` refers to an arithmetic, weekly-normalised rate, while L4 uses the same label for a geometric realised rate. Neither is a conventional cash-adjusted Sharpe: the existing ratios use *total* returns.

## Other reproducible diagnostic flags, not findings of error

1. **Rate publication/funding:** H7 records `rf_last_date = 2026-10-22`, seven calendar days before its last holding-period date `2026-10-29`. `construct.py` asks for `rf.asof(S[t]-1 day)`; the last applied available vintage, elapsed funding days, and maximum accepted staleness require period-level tracing. Being seven days old does not by itself prove an invalid funding charge.
2. **Capital policy:** L4 reports B0 mean `gross = 1.92481339165` versus reference `CAP=1.9`. In `L4_exploit/run.py`, `cap_scale` uses `max(CAP,gross_of(base))` *only for overlays*, which explicitly allows an already-larger B0 baseline. Thus `CAP` is **not an unconditional fund gross limit** in this simulation. This is a policy/interpretation issue, not a demonstrated breach of a live trading rule.
3. **Whole-fund net economic returns:** The simulator's margin cost is `max(s + sum(w) + w_spy - 1, 0)*(rf+margin_spread)*days/360`. It cannot alone establish full margin collateral, short-borrow costs, share lending proceeds, forced liquidation, or true cash NAV; that audit is still pending.

## Execution and validation

From the repository root:

```bash
python -m research.nextgen.audit2026.audit
python -m pytest -q research/nextgen
```

Local test evidence: **13/13** audit tests plus **37** existing nextgen tests and 8 subtests = **50 tests + 8 subtests passed**, on Python 3.13.5, pytest 9.0.2. Source bytes of the first two new files match GitHub SHA precisely. The report numbers were also independently recomputed directly from the three live GitHub JSON sources.

**Scope limitation:** Summary-level reconciliation is not a row-by-row NAV ledger proof. No 2020–2026 sample may be rebranded as a fresh holdout. This PR must not change the existing reported returns, research logs, broker or live fund.

**Next registered falsification experiment (requires user-approved read-only access to raw per-period cache):** Reconstruct exactly the 43 dates, durations, book/core turnover, market returns, financing and cash rate vintages; verify period NAV, compounded growth, effective leverage and risk-free adjusted Sharpe with no fitting/selection on these dates. Compare to both published summaries at tolerance 1e-10 NAV-return units; fail closed if any unmatched row. Then audit complete broker borrow/financing economics before proposing any stock-book reallocation.

**Statistical reference:** Lo (2002), *The Statistics of Sharpe Ratios*, Financial Analysts Journal 58(4), 36–52, DOI [10.2469/faj.v58.n4.2453](https://doi.org/10.2469/faj.v58.n4.2453) — sampling frequency, serial dependence and annualisation require explicit treatment.
