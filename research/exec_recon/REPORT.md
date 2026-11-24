# Execution reconciliation of the paper account, 2026-10-01 to 2026-11-24

*Written by a separate AI research session in this project; saved by the coordinator, who checked the halt, cost and
ledger figures against `RESULT.json` and the HALT file on `fund-data`. It is not an outside review.*

Research only. Nothing under `fund/`, `fund-data` or the broker account was changed. Broker calls were GET requests
through the redacting wrapper. This extends the earlier execution audit (EXE-01, PR #184), which covered the 272 rows
of `fills.csv` as of 11-20. It does not repeat that audit. New here: the broker's own orders, executions, positions and
equity; the SIP official close and the SIP price at the send minute; the ledger rebuilt from executions; and the risk
halt.

**Bottom line.** Orders, fills, quantities and positions reconcile exactly. The cash and holdings ledger rebuilds the
broker's equity to the cent on all 38 sessions. Realised cost is about 1 bp a trade: 1.10 bp against the price at the
send, 1.57 bp against the official close (notional-weighted). That is 0.8 to 1.2 % of NAV a year at the observed
turnover of 74x a year. The model assumes 5 bp, which is 3.7 %/yr. The one defect that changed a decision is timing:
**the risk halt is evaluated one session late.** It tripped on Friday 11-20's close but was written only after Monday
11-23. The account went flat at the close of **11-24** and is flat now ($89,928.34 cash, 0 positions, broker snapshot
2026-11-24 21:45 UTC). It stays flat until a person resumes it (issue #193, open).

## Sources

| Short name | What | Where |
| --- | --- | --- |
| records | order-bearing records: weekly `execution.json` (2), daily reviews (7), lifecycle `live/<day>.json` (29); `tests.csv` (2 pipeline tests) | `origin/fund-data` @ `3a7bbfc`, `fund_state/live/` |
| record versions | every committed version of those records (61 versions of 31 files) | `git log origin/fund-data` |
| fills.csv | the fund's fill ledger, 293 rows | `fund_state/live/execution/fills.csv` |
| nav.csv | the broker equity curve as the fund stores it | `fund_state/live/execution/nav.csv` |
| broker orders | 316 orders since 2026-09-29 | `GET /v2/orders?status=all` |
| executions | 633 fill activities (337 partial, 296 final) | `GET /v2/account/activities/FILL` |
| activities | 697: FILL 633, FEE 63, DIV 1 | `GET /v2/account/activities` |
| broker equity | daily equity with raw timestamps | `GET /v2/account/portfolio/history?period=3M&timeframe=1D` |
| SIP close | official daily close, raw, 72 symbols | `GET data /v2/stocks/bars timeframe=1Day feed=sip` |
| arrival price | open of the SIP 1-minute bar in which the order was submitted | `GET data /v2/stocks/bars timeframe=1Min feed=sip`, 15:50 to 16:05 ET |

The 11-24 session is not yet in `fills.csv` (the fund reconciles it at 01:10 UTC on 11-25). Its 21 orders are counted
here from the broker and marked provisional.

Methods: order-to-fill matching on client and broker order ids; position reconciliation by cumulating signed
executions; a ledger rebuild (cash from executions, fees and dividends; holdings at the SIP close); transaction cost
analysis against the official close and the arrival price (implementation shortfall); annualised as cost dollars over
mean broker equity × 252 / sessions covered.

## 1. Completeness

* **Planned to sent.** 314 planned orders and 2 pipeline tests; all 316 have exactly one broker order; no retries were
  needed (`attempts_per_order: {1: 314}`); zero planned orders unsent.
* **Sent to planned.** All 316 broker orders match a record; none unexplained.
* **Terminal state.** 296 filled (market, day); 20 expired (the 10-01 market-on-close orders, 6 partly filled; in
  EXE-01). Zero open, cancelled or rejected.
* **Executions.** All 633 belong to a known order; 182 orders filled in several executions; summed quantity and price
  equal `filled_qty` and `filled_avg_price` on every order.
* **Fill ledger.** Every planned order has a `fills.csv` row except the 21 orders of 11-24 (not reconciled yet). No
  row lacks a plan; no duplicates.
* **Record versions.** No record's orders changed between committed versions (trade, then reconcile).
* **Plan files.** No `*.plan.json` was ever committed; "planned" means the orders in each submitted record, computed
  before the send.

Every day from 10-01 to 11-24 has planned = sent = broker orders (`RESULT.json: 1_completeness.by_day`).

## 2. Quantities, sides and positions

* Zero side mismatches. Filled quantity equals planned on all 294 pre-close market orders (shortfalls only on the 20
  market-on-close orders of 10-01: 64 of 711 shares).
* `fills.csv` against the broker: quantity equal on all rows; price equal to 6e-14 dollars; `filled_at` within 1 ms on
  all 279 filled rows.
* Sizing: for 256 (day, name) pairs, planned shares = round(target weight × equity / reference price) − holding, zero
  residual.
* Positions: the holding each of 35 records saw before trading equals the cumulated executions; broker positions now 0.
* Realised weights on the SPY core days: SPY within 0.4 points of target (11-19: 1.2041 against 1.2056); stock gross
  within 0.9 points.

## 3. Timestamps

Design (`fund/broker.py`): size at T−150 s, flip close legs at T−75 s, other orders at T−60 s, retries T−30 to T−10 s,
sweep at T+5 s; decision at T−3 min (`fund/lifecycle.py: PRICES_AT`).

| Measure | n | Median | 5 %–95 % | Range |
| --- | ---: | ---: | --- | --- |
| Decision, s before close | 28 | 172.5 | 163.7–175.0 | 162–175 |
| Submission, s before close | 294 | 56.7 | 47.8–59.3 | 42.4–74.5 |
| Flip close legs | 4 | 74.4 | | 73.9–74.5 |
| First fill after submission, s | 294 | 1.05 | p90 1.98, p99 2.98 | 0.10–3.47 |
| Last fill vs close, s | 294 | −54.1 | −58.1 to −45.7 | −73.4 to −41.9 |

* No fill after the close; no execution outside the regular session (0 of 633).
* Orders go out one at a time, alphabetically, about 0.45 s apart; 98 of 294 left later than T−55 s (10-15: the last
  at T−42.4 s; SPY at T−44.8 s). No cost found: correlation of send time with the move to the close 0.014.
* The broker stamps each daily equity bar at 20:00 New York (01:00 UTC next day), which matters for the ledger and
  the halt (section 5).

## 4. Realised costs

Signed slippage in bp, positive = worse for the fund: side × (fill / benchmark − 1) × 10,000. 294 pre-close market
orders ($994,124 traded; median order $2,471); market-on-close orders excluded.

| Benchmark | Mean (SE) | Median | p10 / p90 | Notional-weighted | Mean absolute |
| --- | --- | ---: | --- | ---: | ---: |
| Official close, SIP | 0.81 (0.70) | 0.57 | −11.89 / 13.34 | **1.57** | 8.56 |
| Close as recorded, yfinance (273) | 0.44 (0.72) | 0.41 | −11.94 / 12.90 | 1.07 | 8.39 |
| Arrival, SIP minute at the send | **1.16 (0.29)** | 0.97 | −2.89 / 6.04 | **1.10** | 3.19 |
| Move from send to close | 0.36 (0.67) | 0.07 | −12.67 / 14.25 | −0.48 | 8.44 |

* Cost against arrival is small, positive, t ≈ 4. The close benchmark adds a last-minute move that averages near zero
  with about 8 bp spread per order: noisy, not biased.
* Sells cost more than buys against arrival (2.16 against 0.24 bp); the least liquid third of stocks costs most.
  Orders are tiny against volume (median 0.008 bp of 20-day ADV).
* **The yfinance close the fund records equals the SIP official close on all 273 reconciled fills**, so the empty
  `close_alpaca` column hides no close-source error in this period.

**In % of NAV a year** (`4_costs.annualised`; 35 sessions, mean equity $96,852.74, turnover 73.9x a year):

| | % of NAV a year |
| --- | ---: |
| Realised, against the official close | **1.16** |
| Realised, against arrival | **0.81** |
| Model assumption at the same turnover (5 bp a side) | 3.70 |
| Regulatory fees (−$9.28) | 0.07 |

The SPY core + book period (7 sessions, 139x) holds three one-off trades (move into the core, the 1.3x→0.7x switch,
the halt liquidation) and is not annualised. **Paper caveat:** the paper engine fills at the quote with no market
impact, so these are lower bounds for live trading.

## 5. Ledger

* **Rebuilt ledger** (cash from $100,000 plus 633 executions, 63 fees, 1 dividend; holdings at the SIP close) equals the
  broker's daily equity on all 38 sessions, difference $0.00. Cash went negative on 4 sessions (11-16 to 11-19), down
  to −$32,628.17; highest gross 1.58x.
* **`reconciled.equity`** (read at about 01:11 UTC) is marked at after-hours prices: median +1.2 bp against the close
  equity, 5 %–95 % −31.1 to +50.0 bp, largest +91.8 bp.
* **`nav.csv` labels are one day late** on all 40 rows (8 on Saturdays): `execute.py` takes the UTC date of a
  20:00-New-York stamp. `fund/perf_report.py` corrects it; `fund/ledger.py` and `fund/shadow_ledger.py` do not.
* **Model NAV against broker equity** while mirroring the per-trade book (21 sessions): broker −2.479 %, model
  −2.334 %; the −14.78 bp gap is explained by the model's cash income the paper account does not pay (37.15 bp), the
  model's 5 bp cost (22.78), realised cost (1.47) and 1.07 bp unexplained.
* **Financing:** no interest, margin or borrow activity in 697 activities, although cash was negative and shorts were
  held.

**The risk halt** (`fund_state/live/HALT`, written 2026-11-24T01:11:51; drawdown 12.62 %, week −8.37 %), recomputed on
broker equity with session dates:

| Session | Equity | Drawdown from peak | 5-session change | Trips? |
| --- | ---: | ---: | ---: | --- |
| 11-19 | 92,149.55 | 8.19 % | −4.29 % | no |
| **11-20** | 87,702.83 | 12.62 % | −8.37 % | **yes, first** |
| 11-23 | 90,285.19 | 10.05 % | −6.11 % | yes |

Peak $100,372.87 on 10-09; SPY fell from 754.37 (11-13) to 689.81 (11-20). The drawdown is real and the rule is the
registered one. But at the 01:12 UTC reconcile after 11-20 the broker's history ended at session 11-19, and at the one
after 11-23 it ended at 11-20. The account flattened at the 11-24 close instead of 11-23; the extra session cost
$356.85 (−0.395 %) this time. The lag is structural: every halt check reads the session before the last.

## Defects found

| # | Defect | Severity | Could this change a decision? |
| --- | --- | --- | --- |
| 1 | **The risk halt is checked one session late** (`execute.py reconcile` reads `/v2/account/portfolio/history` at about 01:10 UTC, before the bar of the session just closed is served). | **High** | **Yes**: it decides the session on which the account goes flat. Operational fix: evaluate the halt on the session's own equity (cash + holdings × official close; this rebuild matches the broker to the cent), or append the next morning's `last_equity`. |
| 2 | **The account is flat under the halt now** (issue #193). Not a defect: the registered rule. | **Owner action** | Yes, by design: flat until a person resumes. |
| 3 | The paper account books no financing (margin debit, borrow, cash interest); the model credits ~4.5 %/yr of NAV in cash income. | Medium (measurement) | No for trading; yes for account-vs-model comparisons and live costs. |
| 4 | `reconciled.equity` is marked after hours, up to +91.8 bp off. | Low | No: logged only. |
| 5 | `nav.csv` dates one calendar day late (40 of 40 rows). | Low | No for trading; yes for any join by date. Fix: label by the New York date of the stamp. |
| 6 | Known: `close_alpaca` empty on all 293 rows (fix in PR #194); not reconstructed. | Low (known) | No: yfinance close = SIP close on all 273 fills. |
| 7 | Orders sent alphabetically; on busy days the last leave at T−42 s, SPY late. | Low | No measured effect; sending SPY and the largest orders first is cheap. |
| 8 | The logged `quote_at_send` is IEX (median spread 11.9 bp, mean 192 bp); unusable as a benchmark. | Low | No (log only). |

## Reproduce

```
bash research/exec_recon/export.sh <scratch>          # read-only copies of fund-data records
python3 ~/.claude/hooks/with_secrets.py 'python3 research/exec_recon/fetch_broker.py <scratch>/broker <scratch>/symbols.txt'
python3 research/exec_recon/recon.py <scratch>/fd <scratch>/broker <scratch>/hist research/exec_recon
```

Outputs: `RESULT.json` (every figure above), `fills_recon.csv`, `ledger_recon.csv`. A rerun after 11-25 picks up the
11-24 rows of `fills.csv`; a later snapshot may change the provisional 11-24 figures.
