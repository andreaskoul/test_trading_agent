# EXE-01: empirical paper-order execution audit (2026-11-20)

**Decision: instrumentation/measurement before execution-policy changes.** Research-only. No broker calls, no changes to `main`, `fund/`, trading orders, or 104-week H9 forward records. All observations below come from existing **paper** execution logs, not synthetic backtests or live implementation-shortfall measurements.

## Sources and reproducibility

- `fund-data:fund_state/live/execution/fills.csv`, Git blob `9cc0bb1a3f6e7d95d1e9d2e83184cdfa7265352b`, as of 2026-11-20.
- `main:fund/execute.py` (`reconcile` mode) computes `slip_bp = (buy ? +1 : -1)*(fill/close - 1)*10000`, using a Yahoo Finance daily close; it *attempts* a second raw Alpaca SIP close in `close_alpaca`.
- `research/tree/COST_STUDY.json`: existing S&P500 quoted half-spread median 1.373 bp / mean 2.294 bp measured at a particular preclose timestamp, **not identical to fill-to-close costs**.
- A standalone read-only TCA CLI with **15 passing engineering tests** is supplied as `execution_tca_readonly_20261120.zip` for owner local execution; it is not part of live fund execution. The CLI returns exit code 2 on missing reference coverage, while still writing its report to an empty directory outside the source folder.

## Empirical inspection of the exact committed CSV

| Field | Observed |
| --- | ---: |
| Order rows | 272 |
| `filled` status | 252 |
| `expired` status | 20 |
| Positive fills with valid price/close | 258 |
| Partial fills (included in 258) | 6 |
| Unfilled orders | 14 |
| Filled USD notional (summed, not NAV) | $862,941.24 |
| Median absolute fill-to-close difference | 5.6446 bp |
| Notional-weighted **signed** difference | −0.6895 bp |
| Absolute differences exceeding 10 bp | 70 / 258 = 27.13% |
| Validated stored signed-slippage equations | 258 / 258 |
| Independent `close_alpaca` fields populated | **0 / 258** |

All 20 expired orders belong to the opening 2026-10-01 legacy close-auction experiment (6 partially filled, 14 never filled). Subsequent recorded orders have no reported `expired` status. The data span is 2026-10-01 to 2026-11-19. Price differences on **paper fills** should not be used to infer the live spread, impact or market-immediacy cost. A signed negative close-price difference can arise from price movements between execution and the official close; it is not an observed negative cost.

**Hard data-quality finding:** the existing reconciliation attempts raw Alpaca SIP closes, but none is populated in the committed ledger. No Yahoo-versus-SIP price cross-check has actually been completed. Potential causes include SIP permissions, request failure, data not yet available at reconciliation, ticker mapping and vendor handling; the source of the gap is **not determined** by this CSV. The current `fund/execute.py` catches exceptions and silently returns empty alternate prices on failure, so a missing SIP result should be surfaced as an explicit audit defect rather than implied to pass.

## What must be instrumented *before* execution optimisation

1. Preserve decision/arrival timestamp and bid/ask snapshot, as-of model decision and quoted spread alongside order and fill timestamps; distinguish SIP official close, Yahoo unadjusted close, and adjusted total-return close, with venue/feed/version.
2. Report **complete, partial, expired and not-filled** quantities and opportunity cost; do not measure slippage only on filled orders.
3. Fix/diagnose raw-SIP close capture **in a reviewed, isolated change**; account for SIP entitlements and close-price availability; flag missing reference rows instead of silently omitting them. Do not make a trading-order change.
4. Only once dual-source integrity and decision-time quotes are available, compute notional-weighted arrival-price implementation shortfall, opportunity cost and paid-versus-forecast execution cost at $10m reference AUM. Compare matched market/sector/time-of-day scenarios with uncertainty before preregistering one trading modification.

Practitioner sources: CFA Institute (2015) *Transaction Cost Measurement and Management*; Frazzini, Israel & Moskowitz (2018) *Trading Costs* (AQR); Gârleanu & Pedersen (2013) *Dynamic Trading With Predictable Returns and Transaction Costs*.

**Competing workstreams:** financing study scheduled 2026-11-21 handles cash/borrow assumptions; MASTER architecture screen 2026-11-20 reports no passing new architecture (rank-correlation loss +0.008 IC, t=0.52; multi-horizon +0.008, t=0.40). This execution audit does not retest them. `fund/core.py` Protocol 9 uses 1.9x overlay cap, while the older `fund/execute.py` / pre-Protocol-9 lifecycle logic uses 1.8x: these belong to different operational protocols, so do **not** infer the active core+MASTER gross policy from the retired execution script.
