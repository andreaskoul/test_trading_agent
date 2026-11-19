# Empirical B0 funding review — exact 302-week reproduction (2026-11-19)

**Classification:** Reused 2020–2025 historical accounting sensitivity; **not** a newly untouched holdout, independently sampled broker interest expense, or investment-result confirmation. This is a read-only review of pre-existing committed weekly ledger rows. It neither refits nor evaluates new alphas. No changes to `fund/`, the trading runner, original `L4_exploit/RESULT.json`, or H9 append-only forward records.

## Ground truth of the *simulated* incumbent

Sources committed on `research/tree-layer3` at `research/tree/L4_exploit/b0_audit_runner/`:

- `audit.json` Git blob `0d6e4fa20aea9e775095606a58d91dae880d968d` — metadata, source file SHA-256 hashes and exact reproduction status.
- `weekly_b0_ledger.csv` Git blob `2313f28e85f973152094f423df16d5f492531b56` — 302 weekly accounting rows, 2020-01-02 through 2025-12-11.
- Historical input score join `master_joined_reused.npz` remains **local only**, never copied into the repository or this PR. Preserve it outside macOS scratch/tmp with its checksums and original audit metadata.

Local runner's status: `B0_EXACT_REPRODUCED_READ_ONLY`; 302 observations, compounded CAGR **21.691326537386058%**, legacy raw total-return/vol ratio **0.9369462404420277**, annual volatility 22.37378782545176%, and max absolute difference in period total return vs `construct.run`: **zero**. No missing held-stock return in the exported 302 rows. Model-training PIT lineage remains explicitly `false` in audit metadata.

Independent re-aggregation of the CSV also reproduces the above CAGR and ratio to `<5e-13` in reported units, using the exact 2,177 calendar days and the definitions below. This is a summary- and exported-ledger-level check, not an audit of independent broker or custodial settlement data.

## Frozen, three-scenario cash-cost calculation

For weekly period `t`, the exported columns are `fund_total_return` (decimal simple return), `days`, `legacy_margin_cost_nav`, `legacy_margin_debit_nav`, `conditional_segregated_debit_nav` and `modeled_margin_rate` (annual fractional rate). The actual held weights, price returns, beta hedges, spreads and core decision are frozen across all scenarios.

- **Existing simulator:** `r_existing[t] = fund_total_return[t]`.
- **No margin-interest paper-style hypothetical:** `r_zero[t] = r_existing[t] + legacy_margin_cost_nav[t]`.
- **Segregated short-sale proceeds hypothetical:** `incremental_interest[t] = (conditional_segregated_debit_nav[t] - legacy_margin_debit_nav[t]) * modeled_margin_rate[t] * days[t]/360`; `r_segregated[t] = r_existing[t] - incremental_interest[t]`.

For any scenario `r`:

```text
CAGR_pct = 100 * ( exp( 365.25/sum(days) * sum(log(1+r[t])) ) - 1 )
legacy_ratio = sqrt(52) * mean(7*r[t]/days[t]) / sample_std(7*r[t]/days[t])
annualised_margin_cost_pct_nav = 100 * sum(margin_cost_nav[t]) * 365.25/sum(days)
```

The ratio is the historical **total-return-to-volatility convention**, NOT cash-adjusted excess Sharpe; no new strategy candidate or trial has been selected.

| Reused 2020–25 metric | No modeled margin cost | Existing net-debit model | Segregated-proceeds debit |
| --- | ---: | ---: | ---: |
| Annualised margin charge, NAV % | 0 | **1.37461963** | **2.65359985** |
| CAGR, % | **23.36808656** | **21.69132654** | **20.15125772** |
| Legacy return/vol ratio | **0.99809182** | **0.93694624** | **0.88033528** |
| Maximum drawdown, % | −29.94045 | −29.98545 | −30.02303 |

The segregated model adds **1.27898021 percentage points annualised NAV funding cost** and lowers compounded CAGR by **1.54006882 percentage points** at unchanged returns/weights. The no-margin model increases CAGR by **1.67676002 percentage points**. These are *scenario accounting sensitivities* on already-used historical data, not broker-validated outcomes or statistical evidence for changing strategy.

## Checked implementation constraints

- 302 period rows with 2,177 total calendar days. CSV annual returns and ratio reproduce the published benchmark to machine precision.
- All `rate_vintage_date` entries precede the portfolio `date`: **297** are 1 calendar day earlier; **5** are 2 days earlier; none are dated at or after decision.
- Mean historical `legacy_margin_debit_nav=0.25378397`, mean `conditional_segregated_debit_nav=0.48972714`. Their difference averages **0.23594317 NAV**, not exactly the fixed 0.30 NAV stock-short notional, due to the max-with-zero debit floor.
- `whole_fund_gross > 1.9` on **159/302** baseline periods, with maximum **2.11671085**; the original `CAP=1.9` is not an unconditional incumbent hard limit. A hard 1.9 re-optimisation therefore constitutes a new capital policy and should be matched in the comparator rather than silently substituted.
- Missing held stock returns: **0** in the ledger. No observation generated `r <= −1`.
- Inputs do **not** contain the actual broker's historical settled daily cash debit, interest posting, collateral/short-proceeds rights, securities loan accrual or live historical rates.

## Alpaca distinction: paper != live financing validation

The official Alpaca article `https://alpaca.markets/learn/start-paper-trading` (section *Paper Trading API vs Live Trading API*) explicitly states that **paper accounts do not apply borrow fees and margin interest**, whereas live accounts do. A zero-interest paper activity ledger therefore **cannot validate or falsify** the simulator's *live economic financing rate*. Paper activity can still be used to check positions, fills and balance identities, but not its absence of interest as a live margin rate.

Alpaca's live documentation `https://docs.alpaca.markets/us/docs/margin-and-short-selling` says margin interest is charged on the **settled end-of-day debit balance** using a /360 convention, generally posted monthly. ETB short stock has zero borrow/locate fees for Trading API users, but HTB shorts can incur separate locate and daily borrow fees. Live rates and account conditions must be verified for each historical vintage; do not equate the simulator's `T-bill + 2.43%` with a time-invariant Alpaca rate or infer historical short collateral rules from current FAQ pages.

## Decision after this empirical gate

**Accept** the 302-row reproducibility of the incumbent and keep the accounting PR; **do not approve** a new margin financing rule, new hard gross cap, or allocator on paper-account evidence alone.

Next strictly ordered checks:
1. On a **separate read-only local analysis**, inspect a real live account's settled debit/interest/HTB fees **if available and explicitly authorised**, or obtain Alpaca's written account-specific short-proceeds and historical interest-rate policy. Do not retrieve secrets, change orders or use the paper balance to infer live costs.
2. Preserve the immutable joined 5.7 MB NPZ in a persistent non-repository directory and record its SHA-256 alongside the audit; the .cache files are unavailable from GitHub and macOS scratch can be purged.
3. Preregister exactly one gross-aware trend core+MASTER comparison using the existing capital/financing assumptions, with an *explicitly matched and unchanged* core-plus-book B0 comparator. Holdout 2020–2026 is reused; report it as descriptive and reserve actual inference for unviewed forward observations.
4. Respect the Saturday 2026-11-21 daily-reset leveraged fund vs margin study; do not duplicate it or change the existing 104-week H9 forward evaluation timetable.

**This note adds no synthetic experiment and no production code.**