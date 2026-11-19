# FIN-01 — Short-sale proceeds, financing cost and the Sharpe target

**Research date:** 2026-11-19. **Pre-registered exercise:** read-only algebraic stress, not a new historical backtest. Source baseline is **already reused** 2020–2025 B0. Do not choose a model from these results.

## Hypothesis and mutually exclusive financing assumptions

The existing `research/sharpe/construct.py` / `research/tree/L4_exploit/run.py` simulators debit roughly

```python
legacy_debit = max(core_spy + stock_weights.sum() + spy_beta_hedge - 1, 0)
legacy_charge = legacy_debit * (risk_free + margin_spread) * days / 360
```

FIN-01 asks whether the *economic evaluation* changes materially if short-sale proceeds are collateral and **cannot finance other purchases**. This is a **counterfactual**; the actual Alpaca account's interest-bearing *settled debit balance* has **not** been fetched or verified.

Use consolidated SPY exposure `s = core - beta' w`. Define `L = max(s,0) + sum(max(w_i,0))` and `S = max(-s,0) + sum(max(-w_i,0))`. Self-financing identity `L-S = core - beta'w + sum(w_i)`. The conditional segregated-collateral debit is `D_seg=max(L-1,0)`; legacy is `D_legacy=max(L-S-1,0)`. Therefore:

```text
0 <= D_seg - D_legacy <= S.
c_seg = D_seg * margin_rate * days/360
        + stock_short_borrow_fee - rebate_on_short_collateral
        - yield_on_idle_unencumbered_cash
c_legacy = D_legacy * legacy_margin_rate * days/360
incremental cost (fraction of NAV for interval) = c_seg - c_legacy
```

**Both the ability to reuse short proceeds and actual margin rates are broker/account-specific.** The scenario may overstate or understate reality. The simulated net exposure formula is *not* sufficient to prove an actual financing defect; the daily broker statement is the ground truth.

## Scenario design: fixed **positions**, no predictive fitting

- SPY core: 1.3x (uptrend) **or** 0.7x (downtrend).
- Stock book: +0.30 NAV and −0.30 NAV, stock beta 1 on both legs, hence SPY beta hedge 0.
- Annual rates (illustrative, not observed historical rates): 3%, 5%, 6.25%, 8%, equal in the legacy and segregated scenarios to isolate proceeds treatment.
- Both names declared shortable; stock borrow, short rebate and uninvested-cash yield are **zero for this table only**. The code supports nonzero explicit fees/rebate/cash credit and refuses missing/false shortability.
- Day count: 360; unchanged 7-day positions. No borrow status, settlement changes, day-to-day exposure drift or trading impact is generated.

| Core | Rate | Legacy debit NAV | Segregated debit NAV | Extra cost, NAV % per 360 days | Fixed-vol **legacy ratio** approximation |
|---|---:|---:|---:|---:|---:|
| 1.3x | 3% | 0.30 | 0.60 | 0.900% | 0.8967 |
| 1.3x | 5% | 0.30 | 0.60 | 1.500% | 0.8699 |
| 1.3x | 6.25% | 0.30 | 0.60 | 1.875% | 0.8531 |
| 1.3x | 8% | 0.30 | 0.60 | 2.400% | 0.8297 |
| 0.7x | all above | 0 | 0 | 0% | 0.9369 |

The fixed-vol ratio is `0.93694624 - extra_annual_cost / 0.2237378783` in the **existing raw-return-to-vol convention**. It is **not** a realized net Sharpe, excess-return Sharpe, or backtested result. It is conditional on constant costs, the static positions, and unchanged return volatility; actual financing costs vary with time, portfolio, cash settlement and rates. No 2020–2025 historical financing state series was observed.

## Baseline and economic relevance

Existing L4 B0 published values (GitHub report blob `b18b04d9b884500d46d5ede566e444044e0b04a3`): raw return/vol 0.93694624; annual vol 22.37378783%; CAGR 21.69132654%; book arithmetic net return 5.0859785%/yr; book trading cost 1.9589740%/yr; mean gross 1.7684756. No empirical `D_seg` or rate histories are available in the accessible repository. The increase in *annual arithmetic return* required to move 0.93694624 to 1.0 at fixed volatility is **1.4107514 percentage points** (ignoring how the 2020–2025 benchmark/cash treatment changes the excess-return statistic).

Hence this conditional funding scenario can exceed the fixed-vol gap to 1.0 **in the 1.3x state**, but one cannot translate that result into a revised historical SR. Do not optimize the 1.3x/0.7x regime rule here: the tree coordinator already reserved its own financing/core study.

## Scientific tests and reproducibility

From the repository root:

```bash
python -m research.nextgen.funding_sensitivity.reproduce
python -m pytest -q research/nextgen/metrics research/nextgen/inference research/nextgen/contracts research/nextgen/optimizer research/nextgen/funding_sensitivity
```

Actual local execution against GitHub-byte-identical source: **55 tests and 16 subtests passed**, including 18 new financing tests, 2,000 deterministic random self-financing cases, portfolio-beta-hedge identities, short-borrow eligibility, extreme inputs, and formula consistency; new `core.py` **100% statement coverage (78/78)**. A parallel local test suite including *unmerged* PR #176 reaches 68 tests and 16 subtests; do not confuse this with the current PR's branch-only tests.

## Next falsification gates

1. For **existing reused** periods only, collect signed actual/expected positions `w_{i,t}`, as-of beta, core and hedge, shortable/ETB/HTB status as known at *decision time*, and settled cash/interest/accrual events from authoritative account records. Do not infer shortability from current ticker state.
2. Reconstruct the historical daily cash debit and interest charges independent of fund simulation, compare to `D_legacy` and `D_seg` **row-by-row**, and report errors; fail closed on missing collateral or rate vintages.
3. Incorporate idle cash interest, HTB locates/borrow fees, short-sale rebates, SPY shorts, dividends paid on shorts, margin haircuts, and stochastic margin calls according to the actual account contract. ETB borrowing may be fee-free in the Alpaca Trading API—do not impose a blanket borrow cost.
4. Only after a reconciled NAV ledger, recompute true **excess** Sharpe and a properly registered matched-risk *forward* comparison. All previously examined 2013–2026 observations remain reused.

**References:** Gârleanu & Pedersen (2013), *Dynamic Trading with Predictable Returns and Transaction Costs*, Journal of Finance 68, 2309–2340, DOI 10.1111/jofi.12080. Frazzini, Israel & Moskowitz (2018), *Trading Costs* (AQR research paper). Alpaca [Margin and Short Selling](https://docs.alpaca.markets/us/docs/margin-and-short-selling), including ETB and borrowing documentation; Interactive Brokers [Short Proceeds and Margin Collateral FAQ](https://www.interactivebrokers.com/support/faq/content/58449559). Broker public pages are context, **not evidence of the user's account's actual ledger**.

**Isolation:** writes only `research/nextgen/funding_sensitivity/` on a new research branch. No modification to `main`, `fund/`, existing research logs, or market-data cache. No broker calls, historical data acquisition or trade changes.
