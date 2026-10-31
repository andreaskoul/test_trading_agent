# The fund's current order-timing implementation: an audit from code and records

Scope: read-only audit of the repository at worktree `bridge-cse_019mcjbKCjkxWjxJxaR8xan9` (main at 9cfff04) and of the
records on `origin/fund-data` as fetched on 2026-10-30 (head 46bd967, "execution reconcile 2026-10-30T01:11Z", which
includes the reconciled 2026-10-29 session). Citations are `path:line` in the repository, or `fund-data:<path>` for
records (all under `fund_state/live/`). Analysis scripts and copied records are in `/tmp/otaudit/` (a1.py slippage,
a2.py barriers, a3.py price drift, a4.py sizing); no API was called. Times are UTC unless marked ET. All sessions in the
record are US daylight-saving sessions (close 16:00 ET = 20:00 UTC); from Monday 2026-11-02 the close is 21:00 UTC.

## 1. End-to-end timeline of a trading day and of a weekly cohort; scheduling; timing incidents and their fixes

### Takeaway
Under Protocol 7 the account is traded every session by `fund/lifecycle.py trade`: kill-condition news checks on news up
to T−20 min, a barrier/sizing decision on IEX last-trade prices fetched at T−3 min (the decision is logged about 5–10 s
later, at T−175 to T−170 s), and market orders in the last 75 s before the close, with fills observed at T−73 to T−42 s
(median T−54 s). The T−150 s re-sizing (`PREPARE_AT`) applies only to the retired weekly execution and daily review, not
to Protocol 7. A weekly cohort is decided on news to Wednesday 22:00 UTC and entered at Thursday's close, about 22 h
later (23 h in winter time). Every scheduling incident so far (late or missing GitHub cron runs, a duplicate review, a
runner crash, a launchd file limit, a late data vendor) was fixed operationally; the move to a local Mac runner is the
main structural fix.

### Cited Findings

**Daily timeline (Protocol 7, every session from 2026-10-15)**
- Protocol 7 rule: "the news checks run on articles published up to T − 20 min; the barriers are checked on live prices
  at T − 3 min ...; the decision is logged in `lifecycle/live/<day>.json` ...; the account is traded to it with the
  pre-close send" — reports/research/PROTOCOL_fund.md:597-604. Constants `NEWS_AT, PRICES_AT = 1200, 180` (seconds
  before the close) — fund/lifecycle.py:74-76.
- The scheduler starts the `lifecycle` job Mon–Fri at 16:15 UTC, and it may still start up to 180 min late (Mac asleep)
  — fund/local/runner.py:49-51; the job's timeout is 330 min — fund/local/runner.py:88. The job runs
  `python fund/lifecycle.py trade`, then the ledger, then commits to `fund-data` and opens an issue on failure —
  fund/local/runner.py:385-394.
- `trade()` reads Alpaca's clock and next close (`broker.Clock`, which corrects the local clock by the broker's
  timestamp and prints a warning if the offset exceeds 2 s) — fund/lifecycle.py:1451-1455, fund/broker.py:72-89.
  It returns if the market is closed, refuses a day already `submitted`, and refuses to decide after T−21 min
  ("missed the decision window") — fund/lifecycle.py:1452-1464. Protocol 7 says a session with no live run holds
  everything — reports/research/PROTOCOL_fund.md:606-608.
- T−20 min: sleeps to `close_at − NEWS_AT`, then runs `decide()` once so that the kill checks run and are logged
  (`lifecycle/news/<day>.json`) — fund/lifecycle.py:1479-1482; the kill check is cached and never rerun —
  fund/lifecycle.py:653-660. For a live day the `close_ts` passed to the checks is the news cutoff, not the close —
  fund/lifecycle.py:984, 1007.
- T−3 min: sleeps to `close_at − PRICES_AT`, re-runs `decide()`: previous official closes from Alpaca SIP daily bars
  (adjusted), live prices from `broker.prices` (IEX snapshot: latest trade, else daily bar, else previous daily bar),
  live return = live price / previous close − 1, and the whole book is rebuilt to "now" on those returns —
  fund/lifecycle.py:1469-1477, 1484-1485, fund/lifecycle.py:293-323, fund/broker.py:120-130.
- Sizing: target weight = lot notional / model NAV; quantity = round(weight × broker equity / T−3-min price); a sign
  change becomes a `flatten` leg plus an `open` leg; the record is written with status `sending` before any order —
  fund/lifecycle.py:1486-1516. Lifecycle orders are **not** re-priced at T−150 s: `PREPARE_AT` is used only by
  fund/execute.py:198, 313-317 and fund/review.py:73, 207-209, which no longer trade from 2026-10-15
  (fund/execute.py:200-201; reports/research/PROTOCOL_fund.md:616-619).
- Any open order not in today's plan is cancelled, then `broker.send` runs — fund/lifecycle.py:1523-1528.
- The send (fund/broker.py:9-13, 37-39, 150-257): flip close legs at T−75 s; every other order (SPY included) at T−60 s;
  a flip's open leg as soon as its close leg is fully filled; from T−30 s to T−10 s, an order with no new fill for
  10 s is cancelled and its remainder resent (at most 3 attempts, client ids `<base>-a<n>`); nothing new after T−10 s;
  at T+5 s anything open is cancelled and the residual is logged, never carried. Orders are plain `market`, `day`
  time-in-force — fund/broker.py:182-183. A rerun adopts attempts an earlier run already sent (HTTP 422 on a duplicate
  client order id) — fund/broker.py:184-185, 194-199.
- After the send the record is rewritten with fills and status `submitted`; unfilled orders write `problems.txt` and
  fail the job (issue + text) — fund/lifecycle.py:1529-1536.
- Observed timestamps, all 11 live records 2026-10-15..10-29 (fund-data:lifecycle/live/<day>.json, fields
  `news_ts`, `decided_at`, `submitted_at`; fund-data:lifecycle/news/<day>.json `checked_at`):
  * news cutoff 19:40:00 every day (`close_et` 16:00 every day: no half-day yet);
  * kill checks finished 19:41:11–19:44:39 (71–279 s after the cutoff);
  * `decided_at` 19:57:05–19:57:10, i.e. T−175 to T−170 s (the T−3-min price fetch is at T−180 s);
  * fills (`filled_at` in fund-data:execution/fills.csv, 150 pre-close fills): T−73 to T−42 s, median T−54 s; flip
    close legs T−73 to T−71 s, flip open legs T−49 to T−45 s, all other legs T−59 to T−42 s;
  * `submitted_at` 20:00:08–20:00:09 (T+8/9 s); the `lifecycle trade` commit lands at 20:00 UTC (git log of
    origin/fund-data).
- Overnight: the `reconcile` job (Tue–Sat 01:10 UTC, may run up to 12 h late) runs `execute.py reconcile` (fills vs the
  official close, broker NAV, halts), then `lifecycle.py daily` (the nightly rebuild that marks at official closes and
  applies the logged actions), the replay gate and the 7B shadow control — fund/local/runner.py:47, 353-366;
  reports/research/PROTOCOL_fund.md:606-608. Reconcile waits until 45 min after the close before touching a record —
  fund/execute.py:103-104. Observed reconcile commits 01:10–01:14 UTC (git log of origin/fund-data).

**Weekly cohort timeline**
- News cutoff for the weekly desks is fixed at the as-of Wednesday 22:00 UTC (`news_cutoff(asof) = asof + 22 h`) —
  fund/common.py:41-43; reports/research/PROTOCOL_fund.md:310-311. The lifecycle desk (event type, horizon, kill
  conditions) uses the same cutoff — fund/lifecycle.py:101-106.
- The weekly job runs Wednesday 22:15 UTC (may start up to 1,140 min late, "still decidable before Thu 19:00") —
  fund/local/runner.py:44; README schedule table — fund/README.md:20-24. A live run past Thursday 19:00 UTC is
  refused — fund/common.py:85-87, fund/local/runner.py:302-305. Observed: decisions committed Wed 23:33 UTC for as-of
  10-14; "fund memo + performance" commits at Wed 23:44 UTC (as-of 10-21) and Thu 00:06 UTC (as-of 10-28) (git log
  of origin/fund-data).
- Entry: the cohort's names are entered by the Thursday live run at T−3 min and bought or sold in the last minute
  before Thursday's close; entry volatility uses history to the previous close — fund/lifecycle.py:1252-1259;
  reports/research/PROTOCOL_fund.md:605. The new lot's `entry_close_ts` is the live day's `close_ts`, which is the
  T−20-min news cutoff — fund/lifecycle.py:1259, 984, 1007.
- Positions under Protocol 6 were "held from one Thursday close to the next" — fund/README.md:45-47;
  reports/research/PROTOCOL_fund.md:36-39.
- From Wednesday 22:00 UTC cutoff to Thursday's close is 22 h in summer time (close 20:00 UTC) and 23 h in winter time
  (close 21:00 UTC) — arithmetic from fund/common.py:41-43 and the close times.

**Scheduling layers**
- All scheduled operations run on the owner's Mac through launchd (`runner.py tick` every minute); a missed slot still
  starts on wake within a per-job limit (3 h for trade, review and archive) — fund/README.md:13-18, 30-34;
  fund/local/runner.py:171-199. Each job holds a `caffeinate` assertion — fund/local/runner.py:545.
- GitHub workflows are manual fallbacks only (no cron) — .github/workflows/fund_execute.yml:13-15;
  .github/workflows/fund_lifecycle.yml:9, 26 (timeout 330 min "waits for the news checks and the last minute before the
  close").
- A Claude scheduled task at 17:03 UTC on weekdays dispatches the GitHub workflow if the day's trade or review record
  is missing — fund/README.md:32-34; it stands down while the runner's 5-minute heartbeat on branch
  `runner-heartbeat` is fresh — fund/local/runner.py:144-169.

**Timing-related incidents in fund/CHANGELOG.md and their fixes**
- 2026-10-01: GitHub started the first live week's scheduled runs 3–6 h late (weekly 01:17 instead of 22:15; review
  21:21 instead of 17:07; reconcile 07:07 instead of 01:07). Fix: hourly execution attempts 14:13–19:13 on Thursdays,
  idempotent — fund/CHANGELOG.md:145.
- 2026-10-01: GitHub started no scheduled execution run on the first trade day; dispatched by hand at 16:10 UTC. Fix:
  an external scheduler may start jobs; the weekly desks gained a decided-once guard — fund/CHANGELOG.md:146. All
  schedules moved to cron-job.org — fund/CHANGELOG.md:147.
- 2026-10-02: all scheduled operations moved to the local runner on the owner's Mac (launchd, every minute); workflows
  kept as manual fallback; the 17:03 UTC backstop unchanged — fund/CHANGELOG.md:149.
- 2026-10-01/03: all 20 market-on-close (`cls`) orders expired on the paper account (6 part-filled 15:59:55–15:59:58
  ET); the paper engine has no closing auction. Fix: pre-close market orders with retries and residual cancellation
  — fund/CHANGELOG.md:150; reports/research/PROTOCOL_fund.md:397-424. The week is recorded as an execution failure
  (about 11% filled) and was not topped up — reports/research/PROTOCOL_fund.md:428-429. Records: 20 rows `expired`,
  shares filled 9.7% of ordered (fund-data:execution/fills.csv, exec_day 2026-10-01).
- 2026-10-05: the 1-SPY pipeline test did not run (runner crash in a workflow-drift check); fix and a text on any
  runner crash; tests moved to 10-06/10-07 — fund/CHANGELOG.md:158. Both tests then filled: buy 1 SPY 779.25 vs close
  779.09 (+2.05 bp), sell 1 SPY 777.47 vs close 777.22 (−3.22 bp) — fund-data:execution/tests.csv.
- 2026-10-07: two daily reviews traded (local runner and a GitHub run started by the 17:03 backstop, which saw no record
  because the local review writes its record only after the pre-close send). Shared client order ids kept STZ and SPY
  single, but the GitHub run's 1-share MU reduce also traded. Fix: runner heartbeat; the backstop stands down while it
  is fresh — fund/CHANGELOG.md:157.
- 2026-10-08: the weekly screen priced only 299 of 500 names because launchd's 256 open-file limit broke the parallel
  download; fix: raised limits — fund/CHANGELOG.md:156.
- 2026-10-09: at 01:10 UTC yfinance had not yet served Thursday's daily bar; C10 switched to Alpaca SIP daily bars
  (official close, queryable 15 min after the bar) — fund/CHANGELOG.md:154; fund/lifecycle.py:293-297.
- 2026-10-09: pre-close send made the method for the live account too; `FUND_EXEC_STYLE=cls` removed —
  fund/CHANGELOG.md:161.
- 2026-10-14: a late-published T-bill rate (FRED DTB3 a day late) moved recorded NAVs by 3–13 cents on rebuild; fix:
  the rate is frozen per session (`lifecycle/rf_used.csv`) — fund/CHANGELOG.md:95; repository rule 4 — CLAUDE.md:18.
- 2026-10-26: Amendment 8 was deployed 10 days late (branch never merged), so the 10-21 cohort used the old horizon
  table and eight lots closed at their horizon on 10-20/21 without review — fund/CHANGELOG.md:64.
- 2026-10-28: Alpaca stamps each daily equity point with the next calendar day; the performance report shifts labels
  back one business day — fund/CHANGELOG.md:163.
- No incident in the CHANGELOG concerns a missed Protocol 7 send, a clock offset, or a half-day; all 11 live sessions
  were decided and submitted on time (fund-data:lifecycle/live/*.json, status `submitted`, `problems` empty).

### Inferences
- The decision is a T−3-min snapshot, but the effective execution time is about T−54 s, not the close: the official
  closing print is never traded. Everything the fund measures as "slippage" is the gap between a continuous-market
  print about a minute before 16:00 and the closing auction price.
- The send has a fixed schedule with no randomisation and no splitting: every order goes in a single burst at T−60 s
  (T−75 s for flip legs). With $0.2–6k orders this is harmless in impact terms; at real size it would be a
  predictable, one-shot footprint.
- Flip legs are the only sequenced orders; the open leg waits for a full fill of the close leg and is skipped if the
  close leg never completes — fund/broker.py:216-218, 253-254.
- Half-days are handled through Alpaca's clock and calendar (`next_close`, `close_et`), so the T−20/T−3/T−60 offsets
  move with the early close; the 16:15 UTC slot is before the T−20 mark of a 13:00 ET close (17:40 UTC in winter), but a
  late start after T−21 min would skip the day by design.

### Gaps
- No half-day session has occurred under Protocol 7 (next: Fri 2026-11-27 and Thu 2026-12-24), so early-close
  behaviour is untested in the record.
- The winter-time switch (close 21:00 UTC from 2026-11-02) has not yet happened under Protocol 7.
- The local runner's logs (`~/Library/Logs/fund/`) are not in the repository, so actual job start times and clock
  offsets printed by `broker.Clock` could not be checked; only record timestamps were available.
- One `lifecycle trade` commit at 2026-10-19 18:58 UTC (before the T−20 cutoff) touched only the ledger files; its
  cause is not recorded in the CHANGELOG.

## 2. Decision-vs-close drift, and whether any barrier decision would differ at the close

### Takeaway
It can be reconstructed exactly from the records. From the T−3-min IEX price to the official close, held names moved
a median 8.3 bp in absolute terms (p90 26.9 bp, max 54 bp) and SPY 0.8–6.3 bp. On the hedged residual R that drives
the barriers, the median absolute gap was 8.1 bp, at most 0.07 W. Across 11 live sessions (131 lot-days held through
the decision plus 91 logged actions), **no stop or target decision would have differed** had the barriers been
checked at the official close. The one stop (BA, 10-27) was far through its barrier at both times. The nearest miss was
0.23 W from a stop at the close (HPE, 10-16).

### Cited Findings
- Barrier rule: stop when R ≤ −2.0 W, target when R ≥ +3.0 W (or a lot's own `stop_R` / `target_R` after an
  Amendment 8 extension), never on the entry day; R is the side-signed sum of residual returns
  e = r − β·r_SPY at the close — fund/lifecycle.py:14-18, 70, 1117-1118, 1149-1155, 1025-1028. Under Protocol 7 the
  check uses "the provisional return to that moment" (T−3 min) — reports/research/PROTOCOL_fund.md:599-601. The
  nightly rebuild marks at the official close and applies the logged actions; it does not recompute them on the close
  — reports/research/PROTOCOL_fund.md:606-608; fund/lifecycle.py:1008 (`act = "apply" if d in logs`).
- Fields used: each live record's `lots_after[].R` and `actions[].R` are the T−3-min values, with `W`, `beta`, `side`,
  `entry_day`, `stop_R`/`target_R` where present (fund-data:lifecycle/live/<day>.json); `prices` holds the T−3-min
  price of every target symbol and `orders[].price_ref` the price of every traded symbol — fund/lifecycle.py:1507,
  1513-1514. Frozen official-close daily returns (Alpaca SIP, adjusted) are in fund-data:lifecycle/returns.csv
  (2026-10-01..10-29, 21 sessions).
- Method (scripts /tmp/otaudit/a2.py, a3.py): R_close(d) = Σ side·(r_t − β·r_SPY,t) over sessions after `entry_day`
  up to d, from returns.csv; compared with R_live(d) from the record. Validation: the reconstruction equals the R in
  fund-data:lifecycle/state.json for all 7 open lots to 1e-16; SPY closes chained from returns.csv equal the official
  closes in fund-data:execution/fills.csv on all 10 days SPY traded; the reconstructed raw drift for the 23 held names
  that also traded equals close/price_ref from fills to 0.001 bp.
- Residual drift R_close − R_live, 131 lot-days held through the decision, sessions 2026-10-15..10-29: mean −3.9 bp,
  median −2.8 bp, sd 15.2 bp, median |·| 8.1 bp, p90 |·| 26.3 bp, max |·| 46.1 bp; as a fraction of W, median
  |·| 0.014 W, max 0.071 W.
- Barrier state at T−3 min vs at the close: 131 of 131 held lot-days "inside" at both. Of 91 logged actions with an R
  (45 entries, 16 horizon, 13 news_increase, 9 capacity, 3 news_reduce, 3 news_exit, 2 flip_close, 1 stop,
  1 horizon_extend), 90 were inside the barriers at both times and the one stop was a stop at both: BA on 2026-10-27,
  R −0.1134 at T−3 min and −0.1111 at the close vs a stop at −0.0789 (W 0.0394).
- Closest calls at the close: HPE 2026-10-16, R_close −0.2224 vs stop −0.2512 (0.23 W away; drift −46 bp that
  afternoon); NKE 2026-10-22, 0.25 W away; HPE 10-19/10-20, 0.28–0.29 W away. No lot came within 4.4 W of a target.
- Raw price drift, T−3-min IEX price → official close, held names (n 131): median −0.15 bp, mean −0.8 bp,
  median |·| 8.3 bp, p90 |·| 26.9 bp, max |·| 54.1 bp. SPY by session (bp): 10-15 −1.7, 10-16 −3.4, 10-19 −5.6,
  10-20 +6.3, 10-21 −5.1, 10-22 +5.5, 10-23 +1.6, 10-26 +3.4, 10-27 −4.2, 10-28 +5.3, 10-29 +0.8.
- Traded names (150 pre-close fills, price_ref at T−180 s for Protocol 7 and T−150 s for the Protocol 6 weekly and
  review orders): close/price_ref − 1 median +1.4 bp, median |·| 7.0 bp, p90 |·| 20.2 bp, max |·| 78.5 bp (TSLA buy
  on 2026-10-22: 377.545 at T−180 s, fill 375.05 at T−49 s, close 374.58) — fund-data:execution/fills.csv joined to
  fund-data:lifecycle/live/2026-10-22.json.
- By session, the mean residual drift was negative on 7 of 11 days (−9.5, −9.3, −9.2 bp on 10-16, 10-19, 10-20;
  day-mean of means −3.7 bp, t −2.4 over 11 overlapping days). Weighted by |w|, its NAV effect summed to about
  −15 bp of NAV over the 11 sessions (largest −7.1 bp on 10-19).

### Inferences
- With W between about 3.9% and 15% of residual return in the current lots, a typical 8 bp last-three-minutes move is
  about 1% of W, so the T−3-min barrier evaluation is practically equivalent to a close evaluation for this book.
  A decision would flip only when R ends within roughly 0.1 W of a barrier at T−3 min; that has not happened yet.
- The residual drift is not a trading cost: the positions are held through the close either way, and the model book
  is marked at the official close. What matters for costs is the gap between the fill (about T−54 s) and the close,
  treated in section 3.
- The negative mean residual drift is suggestive (lots fared slightly worse in the last 3 minutes, mostly on
  10-16..10-20) but the same lots recur from day to day, so the 11 day-means are not independent; it is not evidence of
  a systematic effect.
- IEX handles a small share of US volume, so an IEX "latest trade" for a less liquid name can be older than the T−3-min
  mark. Half-penny decision prices in the records (MRVL 223.295 and TSLA 377.545 on 10-22, SPY 773.485 on 10-21) are
  consistent with IEX midpoint executions rather than quote-side prints. This adds noise, not bias, to the decision
  price.

### Gaps
- The records do not store the timestamp of the IEX trade behind each `prices` entry, so the staleness of the decision
  price cannot be measured.
- The live return `ret` and the previous close used at T−3 min are not stored in the live record; they were
  reconstructed (exactly, as validated above) from returns.csv and the price fields. A future ex-dividend day inside the
  window would need the unadjusted previous close, which is not logged.
- News exits are not price decisions, so their sensitivity is to the T−20-min news cutoff (section 5), not to T−3-min
  prices; horizon and capacity actions do not depend on intraday prices except through the caps.
- No intraday bars were pulled (no API calls), so whether the T−3-min → close moves happened before or in the closing
  auction cannot be separated here.

## 3. Slippage decomposition, outliers, fill ratio and retries

### Takeaway
Slippage is measured against the official close (yfinance unadjusted `Close`), not against the decision price. Over
150 pre-close fills (15 sessions, 2026-10-07..10-29, $468k traded) it is unbiased: signed mean +0.57 bp (se 0.78),
median +0.59 bp, notional-weighted mean +0.77 bp, about $36 in total. Its dispersion is the price move between the fill
(about T−54 s) and the closing print: median |slip| 5.3 bp, p90 13.9 bp, max 55 bp. Every one of 150 orders filled in
full on its first attempt: no `-a2`/`-a3` retry has ever been used. The CEG −55 bp "outlier" was favourable: the fund
sold at 276.52 and the stock closed at 275.00. The operations gate currently misreads Protocol 7 execution: it shows
"weeks fully executed 0%" because it reads only weekly `execution.json` files.

### Cited Findings
**How slippage is measured**
- Reconcile, at least 45 min after the close, sums every attempt's fills and takes the official close from yfinance
  (`auto_adjust=False`, `Close`); `slip_bp = side × (fill / close − 1) × 1e4`, positive = worse than the close —
  fund/execute.py:103-121. The per-record summary is the median |slip| of non-flatten legs — fund/execute.py:135-140.
  The IEX `price_ref` is stored with each order (fund/lifecycle.py:1507; fund/execute.py:280) but reconcile never uses
  it. Amendment 3: "Reconciliation after the close records each fill against the official close (slippage in bp;
  positive means worse)" — reports/research/PROTOCOL_fund.md:205-207; execution note: "It is measured, not assumed" —
  reports/research/PROTOCOL_fund.md:420-424.
- My recomputation reproduces `slip_bp` in fund-data:execution/fills.csv to 2e-12 bp (/tmp/otaudit/a1.py).

**Headline numbers** (fund-data:execution/fills.csv joined with the order records in
fund-data:lifecycle/live/*.json, fund-data:2026-10-07/execution.json and fund-data:2026-*/reviews/*.json)
- All 139 fills with a price over 2026-10-01..10-27 (incl. 6 partial MOC fills of 10-01): median +0.41, mean +0.57,
  median |·| 4.41, p90 |·| 13.83, max |·| 55.27 bp — this reproduces the coordinator's figures.
- Pre-close fills only, now including 2026-10-29 (n 150): signed median +0.59, mean +0.57 (se 0.78), median |·| 5.31,
  p90 |·| 13.95, max |·| 55.27 bp; notional-weighted mean +0.77 bp, notional-weighted mean |·| 6.32 bp; total
  notional $468,363, net slippage cost $36.22.
- Against the decision/sizing price instead (`price_ref`, IEX at T−180 s for Protocol 7, T−150 s for Protocol 6):
  median 0.00, mean +1.04, median |·| 5.63, p90 |·| 18.75, max |·| 66.0 bp; notional-weighted mean +0.79 bp; $37.01.
- Decomposition: slip vs close = slip vs price_ref − side-signed drift from price_ref to the close. Correlation of slip
  vs close with the adverse drift is −0.57 (slope −0.37); of slip vs price_ref with the adverse drift +0.76. The sd of
  daily mean slippage is 3.4 bp against an overall sd of 9.5 bp: most dispersion is name-specific within a day.

**By group (slip vs close, bp; n, signed median, signed mean, median |·|, p90 |·|)**
- By source: Protocol 6 weekly execution 10-08 (22; +0.31; +1.67; 4.52; 11.24); Protocol 6 daily reviews (12; −1.13;
  −1.82; 4.05; 11.27); Protocol 7 lifecycle (116; +1.32; +0.60; 5.37; 14.84; max 55.27).
- By side: buy (74; +1.23; +0.46; 5.54; 14.24); sell (76; +0.42; +0.67; 4.74; 12.54).
- By leg: close (44; +1.25; −0.85; 4.29; 13.45); rebalance (88; +1.01; +1.61; 5.97; 14.19); flatten (3; mean −2.80);
  open (3; mean +3.58); review reduce/rehedge/exit/increase (12 in total, see source).
- By session (n; median |·|): 10-07 (3; 11.5), 10-08 (22; 4.5), 10-09 (4; 1.2), 10-13 (3; 4.4), 10-14 (2; 7.6),
  10-15 (32; 4.4), 10-16 (3; 9.5), 10-19 (2; 6.8), 10-20 (3; 10.4), 10-21 (11; 2.1), 10-22 (27; 6.0), 10-23 (9; 7.4),
  10-26 (4; 6.0), 10-27 (8; 3.6), 10-29 (17; 6.8). No orders on 10-28. The record's own per-session statistic
  (non-flatten median) is in each live record's `reconciled.median_abs_slip_bp_close`, e.g. 10.44 on 10-20 and 7.71
  on 10-29.
- By share price: ≤$50 (18; median |·| 7.3), $50–150 (33; 6.4), $150–400 (59; 5.4), >$400 (40; 3.6).
- By order notional: ≤$1k (13; 4.6), $1–2.5k (48; 5.2), $2.5–5k (69; 6.2), >$5k (20; 3.0).
- Listing venue: no exchange field exists in the records or the screen (fund-data:2026-10-21/screen.json row keys),
  so the venue split could not be computed from records.

**The |slip| > 15 bp fills (11 of 150)** — price_ref (T−180 s) → fill (time before close) → official close
- CEG 2026-10-15, close leg, sell 10: 276.38 → 276.52 (T−55 s) → 275.00; slip −55.3 bp (better than the close), vs
  price_ref −5.1 bp; the stock fell 50 bp after the fill, between about T−55 s and the closing print.
- LH 2026-10-29, buy 6: 368.03 → 367.35 (T−53 s) → 368.16; −22.0 bp (better).
- XOM 2026-10-22, buy 14: 177.95 → 177.92 → 178.23; −17.4 bp (better).
- LLY 2026-10-15, sell 2: 1253.56 → 1253.68 → 1251.61; −16.5 bp (better).
- KHC 2026-10-15, sell 101: 23.255 → 23.24 → 23.28; +17.2 bp (worse; one cent is 4.3 bp at $23).
- ROL 2026-10-23, buy 1 ($35): 34.85 → 34.88 → 34.82; +17.2 bp. ROL 2026-10-26, sell 85: 34.525 → 34.49 → 34.55;
  +17.4 bp.
- MMM 2026-10-22, buy 15: 176.05 → 175.868 → 175.56; +17.5 bp vs close but −10.3 bp vs price_ref.
- CMG 2026-10-29, buy 86 (short closed): 31.26 → 31.34 → 31.28; +19.2 bp (+25.6 vs price_ref). CMG 2026-10-22, sell
  87: 28.025 → 28.07 → 28.14; +24.9 bp (−16.1 vs price_ref).
- VEEV 2026-10-20, sell 9: 317.505 → 317.94 → 318.67; +22.9 bp (−13.7 vs price_ref).
- In 8 of the 11 the price moved at least 10 bp between the decision price and the close and the fill landed in
  between; the other three are low-priced names (KHC, ROL, CMG at $23–35) where a cent is 3–4 bp. The largest
  decision-to-close move among traded names, TSLA on 10-22 (−78.5 bp), produced only +12.6 bp slippage because most of
  the move happened before the T−49 s fill.

**Fill timing, fill ratio and retries**
- Fills are timestamped T−73 s to T−42 s (median T−54 s); none at or after the close (fund-data:execution/fills.csv
  `filled_at`). 2026-10-01's MOC partial fills came at 15:59:55–15:59:58 ET with slippage −1.2 to +3.5 bp —
  reports/research/PROTOCOL_fund.md:399-402; fund-data:execution/fills.csv.
- Every pre-close order (150, including the 17 of 10-29 and the flips) has exactly one attempt id `-a1` and status
  `filled`; no `-a2`/`-a3` exists in any record (fund-data:lifecycle/live/*.json `attempts`; P6 records likewise).
  Shares filled / ordered = 100% on every pre-close session; 9.7% on the 10-01 MOC session.
- Flip example (AMD, 2026-10-22): flatten sell 6 filled at 508.14 at T−71 s, open sell 5 at 507.36 at T−45 s
  (fund-data:lifecycle/live/2026-10-22.json; fills.csv).

**The operations gate as computed today**
- The gate's "weeks fully executed" is the share of scored weeks with a weekly `<asof>/execution.json` that is
  `submitted` with no unfilled orders, and its slippage is the median |slip| over every non-flatten row ever written to
  fills.csv — fund/score.py:334-342. Under Protocol 7, `execute.py trade` exits before writing an execution record
  (fund/execute.py:200-201) and the trades are in `lifecycle/live/`; fund-data:performance/gate.md (1 week scored)
  shows "weeks fully executed 0%" and "median abs slippage vs close 4.4 bp", although all Protocol 7 orders filled.

**Costs assumed vs measured**
- Model books charge 5 bp per side on every trade, the hedge included — fund/lifecycle.py:30-31, 73;
  reports/research/PROTOCOL_fund.md:550; score.py uses `5e-4` per side — fund/score.py:115. The research shadow
  books keep 5 bp/side "against a measured 0.8 bp slippage and 0.08 bp fees in paper trading (1–22 October 2026, 118
  fills)" — reports/research/PROTOCOL_fund.md:858-859; fund/CHANGELOG.md:77.

### Inferences
- The measured cost of the pre-close send relative to the closing price is indistinguishable from zero; the 5 bp/side
  model charge is therefore conservative by about 4 bp per side for these small orders, before any impact at scale.
- The dispersion (median 5 bp, p90 14 bp) is a tracking error to the close created by trading about a minute early,
  not a cost. It roughly doubles for low-priced names because of the one-cent tick.
- Retries and cancellations have never been exercised in production; their logic is untested in the record except
  through code review. Paper fills are also a simulation (Alpaca's paper engine fills against the quote), so the
  100% first-attempt fill rate may not carry over to a live account.
- The gate's operations rule will show a failure ("0% fully executed") at the 13-week look unless it is pointed at the
  lifecycle records; this looks like an operational fix (CLAUDE.md:55-57) rather than a protocol change, but that is
  for the owner to judge.

### Gaps
- No intraday trade/quote data were used, so spread at the time of fill and the size of the closing-auction move
  (fill vs last continuous trade vs closing print) cannot be separated. CEG's 10-15 move after the fill could be an
  auction imbalance or a last-minute continuous move; the records cannot tell.
- Listing venue (NYSE vs Nasdaq auction mechanics) is not recorded anywhere in the repository or the records.
- The 6 partial MOC fills of 10-01 have no `fill_ratio` in fills.csv (NaN), only `filled_qty`.
- Alpaca paper fills are simulated; nothing in the records measures what a live account would pay.

## 4. Sizing timing: prices at T−3 min, equity at decision time, and the resulting weight error

### Takeaway
Protocol 7 sizes once, at T−3 min: model weights (lot notional / model NAV) × Alpaca's live equity / the T−3-min IEX
price, rounded to whole shares. Timing contributes little: broker equity sat within 8 bp of the model NAV, and the
3-minute price drift (about 8 bp) changes weights by under 0.1 bp of NAV per name. Whole-share rounding dominates: a
median 1.8 bp of NAV per name, but 54 bp of NAV summed over the stock book per day, plus a median 28 bp from the SPY
hedge, because one SPY share is about 78 bp of a $98k account. After the close, reconcile measured a median
sum-|real − target| of 108 bp of NAV. Daily re-sizing causes almost no churn: outside the 10-15 transition, four
one-share orders in total.

### Cited Findings
- Sizing code: `target = {ticker: L.n / nav}` from the T−3-min rebuild; `equity = account()["equity"]` read right after
  the decision; `tq = round(target × equity / px)`; an order only when `tq ≠ current qty` —
  fund/lifecycle.py:1486-1505. The T−150-s re-sizing (`PREPARE_AT`, "orders are sized from prices fetched at T−150 s")
  exists only on the retired weekly/review path — fund/broker.py:38; fund/execute.py:313-317; fund/review.py:207-209.
- Whole shares are a design rule since Amendment 3 ("whole shares at the account's equity") —
  reports/research/PROTOCOL_fund.md:191-192.
- Broker equity vs model NAV at the decision (fund-data:lifecycle/live/<day>.json `equity`, `nav_model`): −7.8 to
  +1.3 bp across the 11 sessions (e.g. 10-28: $99,088.99 vs $99,166.74).
- Rounding error at the decision price, per name (|round(w·E/p)·p/E − w|), all 11 sessions: median 1.8 bp of NAV,
  p90 12.0 bp, max 38.2 bp (SPY on 10-22); median position 21 shares (/tmp/otaudit/a4.py).
- Summed over the book per session (realised quantity after fills × T−3-min price / equity vs target weight): 21 to
  148 bp of NAV, median 82 bp; the SPY hedge alone 0.6–38 bp (median 28 bp), the stocks 21–117 bp (median 54 bp).
  On 10-15 to 10-20 the hedge target was +0.28% of NAV, 0.36 SPY shares, which rounds to zero.
- Reconcile's `tracking_gross` (Σ|market value / equity − target weight| from Alpaca positions after the close —
  fund/execute.py:129-134): 10-15 107.5, 10-16 91.6, 10-19 104.5, 10-20 109.8, 10-21 39.8, 10-22 128.7, 10-23 83.2,
  10-26 116.0, 10-27 54.8, 10-28 108.0, 10-29 279.5 bp of NAV; median 107.5 bp (each record's `reconciled` field).
- Orders not tied to a same-day lifecycle action: 19 of 111 stock orders, of which 15 were on 10-15, the
  Protocol 6 → 7 transition day (closing the old weekly holdings, per reports/research/PROTOCOL_fund.md:610-614).
  The other 4 are one-share rounding trades: SMCI buy 1 (10-16), CMG buy 1 and ROL buy 1 (10-23), SMCI sell 1
  (10-26), about $126 in total.

### Inferences
- The choice of T−3 min vs T−150 s for sizing is immaterial at this account size; whole-share granularity on a $98k
  account is the binding constraint, especially for the SPY hedge (a 1-share step is about 0.8% of NAV, so small
  hedges are either zero or overshoot). Fractional shares or a cheaper hedge instrument would remove most of it, but
  the hedge instrument is the owner's strategic policy (CLAUDE.md:71-73), not a tunable.
- Because the model book is marked at the official close with exact weights, the account's realised P&L differs from
  the model by roughly (rounding error × day's return); with ~1% gross mismatch and ~1–2% daily moves that is on the
  order of 1–2 bp of NAV a day of tracking noise, not bias.
- The 279.5 bp tracking on 10-29 is larger than the decision-time rounding (148 bp); the records do not show why.
  Reconcile reads positions at about 01:10 UTC, so Alpaca's after-hours marks may enter `market_value` (inference,
  not verified).

### Gaps
- Reconcile's equity and position marks are taken hours after the close; whether Alpaca's `market_value` then uses the
  official close or an after-hours price is not recorded.
- The weight error that the model's own accounting would show (model n vs account quantity × close) is not stored;
  it was approximated here with the T−3-min prices.

## 5. Signal latency built into the design

### Takeaway
The nominal news cutoff is T−20 min, but the newest article any live check has seen was published 95 min to about 2.8 h
(median) before that cutoff: Finnhub's company-news endpoint apparently serves articles with a lag of 1.5–3 h. Because
each check's window starts exactly at the previous cutoff, articles stamped in those last hours but served later are
never checked at all. Shadow checks run five hours after the close saw about a quarter of same-day articles in the last
two hours before their cutoff; live checks saw 1.7%. Of the articles checked, the median one is acted on 6.8 h after
publication; after-close news waits about 22 h. Weekly cohorts carry a 22–23 h delay from the Wednesday 22:00 UTC
cutoff to Thursday's close, plus a blind window: news published in that interval is read neither by the weekly desk
nor by any kill check. Three scored weeks of the timing shadow books lean the "wrong" way for the Thursday close
(Wednesday close +0.21 %/wk, Thursday open +0.33 %/wk better), but three weeks carry essentially no information.

### Cited Findings
**Daily kill checks**
- Each check fetches Finnhub company news by calendar date and keeps articles with lo < datetime ≤ hi, where hi is the
  live news cutoff (T−20 min) and lo is the lot's `news_until` (the previous check's hi) or its `entry_close_ts`;
  headlines already seen are dropped and at most the latest 25 are kept — fund/lifecycle.py:639-650, 662-674;
  `news_until` is set to hi after every check — fund/lifecycle.py:674, 710. A live day's check uses
  `close_ts = news_ts` (T−20 min) — fund/lifecycle.py:984, 1007, 1475.
- Checked articles (pass-0 prompts in fund-data:lifecycle/news/<day>.prompts.jsonl.gz, 11 live sessions 10-15..10-29,
  154 lot-checks, 2,270 articles), by publication time (ET): regular session to 15:40, 47.4%; pre-open 00:00–09:30,
  35.5%; after the close 16:00–24:00, 10.6%; weekend, 5.6%; the last 20 minutes 15:40–16:00, 0.8% (18 articles).
  Sources: Yahoo 2,004, SeekingAlpha 110, Benzinga 93, ChartMill 35, CNBC 25.
- Latency from publication to the decision that can act on it (T−3 min of the checking session): median 6.8 h, p10
  3.2 h, p90 22.7 h; medians by group: session 4.5 h, pre-open 8.4 h, after close 22.2 h, last 20 minutes 24.2 h,
  weekend 35.7 h. 54 of 154 lot-checks hit the 25-article cap.
- Vendor lag at the cutoff (fund-data:lifecycle/news/<day>.json `checked_at`, `close_ts`, per-lot `max_published`):
  * live sessions: cutoff 19:40 UTC, checks finished 71–279 s later; the newest article of each session was stamped
    17:27–18:05 UTC; per lot-check, the newest article was a median 169 min before the cutoff (min 95, p10 113);
    same-day articles: 0 in the last 20 min before the cutoff, 33 of 1,970 (1.7%) 20–120 min before it, 431
    120–240 min before it; 3 articles stamped in the 18:00 UTC hour and none in the 19:00 hour;
  * shadow sessions 10-09..10-14 (cutoff 20:00 UTC, checked 01:13–01:19 UTC, about 5 h later): newest article
    19:50–20:00 UTC; per lot-check median gap 39 min (min 0); same-day articles: 30 of 769 (3.9%) in the last 20 min
    and 160 (20.8%) 20–120 min before the cutoff; the 19:00 UTC hour was the busiest of the day (102 articles).
  * No live article has a timestamp ≤ its window's lower bound, so late-served articles stamped before a previous
    cutoff are never shown in any later check (/tmp/otaudit prompt parse).
- The kill-check prompt tells the model that only events after the entry close count — fund/lifecycle.py:683-684.

**Weekly cohort**
- The weekly desks and the lifecycle desk read news to Wednesday 22:00 UTC — fund/common.py:41-43;
  fund/lifecycle.py:106; entry is at Thursday's close — reports/research/PROTOCOL_fund.md:188-190, 597-605.
- A new lot's kill-check window starts at its `entry_close_ts`, set to the entry day's `close_ts`, which on a live day
  is Thursday T−20 min — fund/lifecycle.py:1259, 667, 984, 1007. Nothing reads company news stamped between
  Wednesday 22:00 UTC and Thursday 19:40 UTC (summer) for a new cohort's names before they are entered.
- Staleness filter: H = H_type − news_age (trading days since the first report), clamped to 3..20; H_type − news_age
  ≤ 2 is stale and not entered — fund/lifecycle.py:10-13, 69.
- `session_of`: news before 16:00 ET on a trading day belongs to that session, else to the next — fund/lifecycle.py:
  401-407; it dates events in the desk's horizon logic (fund/lifecycle.py:431-455, 504-512), not the kill checks.

**Timing shadow books** (fund-data:performance/weekly_books.csv, column `net`, % per week)
- Definitions: c1_wedclose = the fund's weekly weights from the as-of Wednesday close to the next Wednesday close
  (notional, "not tradable after the decision"); c1_thuopen = Thursday open to next Thursday open; the reference is the
  same weights from Thursday close to next Thursday close; 5 bp/side for all — fund/score.py:89-100, 115-119;
  reports/research/PROTOCOL_fund.md:326 ("This measures what the one-day delay costs; large-cap news drift is mostly
  one day").
- As-of 2026-09-30: Thursday-close book (c7_noreview) −1.155; c1_wedclose −0.833; c1_thuopen −0.493; fund with reviews
  −1.029.
- As-of 2026-10-07: c7_noreview −2.188; c1_wedclose −2.123; c1_thuopen −2.465; fund −1.911.
- As-of 2026-10-14 (first Protocol 7 week): c0_weekly +0.161; c1_wedclose +0.397; c1_thuopen +0.773; fund (lifecycle
  NAV) −0.989.
- Means over the 3 weeks: Thursday close −1.061, Wednesday close −0.853 (+0.208 vs Thursday close), Thursday open
  −0.729 (+0.332 vs Thursday close; worse in 1 of 3 weeks).
- The challenger rule needs a boundary of 5.724 / 4.048 / 3.305 / 2.862 (NW t) at 13/26/39/52 weeks for m = 11 —
  reports/research/PROTOCOL_fund.md:631-633; the owner's judgement on shadow books waits until about mid-April 2027 —
  fund/CHANGELOG.md:93.

### Inferences
- The effective news cutoff of the daily kill checks is roughly T−2 to T−3 h, not T−20 min, and news stamped in that
  final stretch is silently lost rather than delayed: the window boundary (lo = previous cutoff) assumes the vendor
  serves articles instantly. An overlapping look-back (for example lo = previous cutoff − 6 h, deduplicated by the
  existing `seen` headlines) would recover it, but it would change which news reaches the checker, so under
  CLAUDE.md:55-57 it is a protocol change, not an operational fix.
- Even with a perfect feed, the design trades about 1 session after most news (after-close news ~22 h, intraday news
  ~4.5 h) and enters weekly ideas ~1 day after their information set closes. The repository's own drift study puts
  most large-cap news drift inside a day (section 6), which is exactly what these delays forgo.
- The blind window for new weekly lots means a Thursday-morning story that contradicts a Wednesday thesis cannot stop
  the entry; it can only trigger an exit a day after entry.
- The three timing weeks are noise: weekly book returns move 1–2% a week, so a 0.2–0.3 %/wk difference needs dozens of
  weeks to show up at the pre-registered boundaries.

### Gaps
- Finnhub's indexing lag is inferred from the article timestamps in the prompts; the vendor's actual ingestion times
  are not recorded, and the private Hugging Face news archive (which stores `fetched_at`) was not read because it
  needs a token. How many articles were lost per session therefore cannot be counted, only bounded by the shadow
  pattern (about 20–25% of same-day articles fall in the last two hours before a 20:00 UTC cutoff).
- The articles dropped by the 25-article cap and by headline deduplication are not logged.
- Whether the weekly desks' own inputs (archive at 21:20 UTC, research pipeline) suffer the same vendor lag before the
  22:00 UTC cutoff was not examined.
- Only three timing-book weeks are scored; c1 books under Protocol 7 use the weekly book's weights, not the
  lifecycle book's, so they say nothing yet about the daily lifecycle trades' timing.

## 6. What the backtests and shadow books assume about execution, and the intraday research already done

### Takeaway
Every model, backtest and shadow book in the repository fills at the official close (or, for c1_thuopen, the official
open) and charges a flat 5 bp per side. No book models the T−54 s fill, the closing-auction gap, the spread or impact.
The intraday research (technicals pre-registration 2) tested whether intraday price paths on the news day predict the
follow-through; none passed the 2022–2025 holdout. The drift study is the main evidence on timing: from the fund's
Thursday entry only days 1–3 are positive (+4 to +13 bp, t ≤ 1.5), against about 10 bp of round-trip cost. The desk
review of 2026-10-14 rates the information set and timing "high severity" and implementation "low severity
(a strength)".

### Cited Findings
- The lifecycle book (now the fund) is "a self-financing book on $100,000, marked at official (total-return) closes;
  cash earns the 3-month bill; 5 bp per side on every trade, the hedge included" — fund/lifecycle.py:30-32;
  `COST = 5e-4` — fund/lifecycle.py:73. Under Protocol 7 the logged T−3-min actions are applied at the official close
  in the nightly rebuild — reports/research/PROTOCOL_fund.md:606-608.
- Weekly books (`score.py`): entry at the close of the first trading day after the as-of Wednesday, exit at the first
  close on or after the next Thursday, yfinance adjusted closes, 5 bp/side; c1_wedclose uses Wednesday closes and
  c1_thuopen uses opens — fund/score.py:84-100, 115-119; reports/research/PROTOCOL_fund.md:54, 188-190.
- Research shadow books: "Thursday close to Thursday close, 5 bp per" side — reports/research/PROTOCOL_fund.md:820;
  costs kept at 5 bp/side against measured 0.8 bp slippage and 0.08 bp fees — reports/research/PROTOCOL_fund.md:
  858-859.
- Technicals backtest (S&P 500 news-gap events 2012–2025): entered "at the first Thursday close after the news day (the
  fund's timing) ... 5 bp per side on every trade" — reports/research/technicals_backtest.md:5;
  fund/backtest_levels.py:10, 51.
- Drift profiles (8,924 events; side-signed cumulative residual return, bp, t on weekly means) —
  reports/research/technicals_backtest.md:249-281:
  * from the news-day close: +5 (+1 session), +8 (+2), +6 (+3), +13 (+5), +11 (+10), +7 (+15), +5 (+20), −5 (+30),
    −18 (+60); "the gap direction earns nothing significant at any horizon to 20 sessions";
  * from the fund's Thursday entry close: +4 (+1), +12 (+2), +13 (+3), +7 (+5), +9 (+10), +3 (+15), −6 (+20), −10 (+30),
    −27 (+60); "the only positive stretch is days 1–3 (+4 to +13 bp, t ≤ 1.5)"; 2022–2025 alone: +1, +9, +9, +6, +10,
    +8, +10 at +1..+20.
- Intraday pre-registration 2 (written 2026-10-08 before outcomes): close vs VWAP, last hour (close − 15:00 ET price),
  open drive kept (close − 10:00 ET price), plus two options measures; pass = holdout t ≥ 2.58; "Passed: none"; the
  intraday measures change sign between periods — reports/research/technicals_backtest.md:172-195, 196-221. Data:
  news-day 5-minute SIP bars from Alpaca — fund/backtest_intraday.py:1-8. CHANGELOG summary: all five tests fail on the
  holdout and "the drift profiles show no slow post-news drift" — fund/CHANGELOG.md:153.
- Desk review 2026-10-14: "B2. Information set and timing: high severity" — the weekly batch reads news to Wednesday
  22:00 UTC and enters at Thursday's close; the classifier dates driving events 1–5 trading days before entry (median
  2–3 in the 10-07 cohort); 6 of 20 views were stale; 11 of 14 entered lots had H = 3–4 — reports/research/
  desk_review_2026-10.md:98-106. It cites Ke, Kelly & Xiu (11 bp in one day for large caps vs 52 bp over three days for
  small caps) — reports/research/desk_review_2026-10.md:90-91. "C. Implementation: low severity (a strength). The
  pre-close send works ...; Five bp a side is conservative for Alpaca. The live barrier prices are IEX last trades.
  That is fine for mega-caps and thinner for any broader universe" — reports/research/desk_review_2026-10.md:
  165-168. Its proposal: "event-driven daily entries at the news-day close, reusing Protocol 7's T−20 / T−3 machinery"
  — reports/research/desk_review_2026-10.md:245-246.
- Amendment 5's registered rationale: "large-cap news is mostly priced within about a day. Acting at the next close
  may therefore add turnover more often than it avoids losses" — reports/research/PROTOCOL_fund.md:392-394.

### Inferences
- Because the model marks at the close while the account trades at about T−54 s, the model-vs-account gap per trade is
  the section 3 slippage (mean ≈ 0, |·| ≈ 5 bp). The model's 5 bp/side charge more than covers it, so the backtests
  and shadow books are, if anything, slightly pessimistic about costs at this size, and silent on timing risk.
- The evidence base in the repository points at signal latency (days between news and entry), not at intraday order
  timing, as the place where expected value is lost; the measured intraday execution error is an order of magnitude
  smaller than the drift the design waits through.

### Gaps
- No backtest in the repository models execution before the close, the closing auction, spreads or market impact; no
  intraday study tests entry at the news-day close vs the next close for the fund's own (LLM) views, only for price
  gaps.
- The analysts' own drift profile is to be measured from the live record as cohorts accrue
  (reports/research/technicals_backtest.md:289-291); not enough cohorts exist yet.

## 7. Design rationales, owner decisions on timing, and the constraints on any change

### Takeaway
The pre-close market-order method is a documented operational workaround (Alpaca paper has no closing auction),
confirmed by the owner on 2026-10-09 as the method for a live account too; the closing-auction option was deleted from
the code. The T−20 min / T−3 min decision times are pre-registered in Protocol 7. Protocol 7 (now 7B) is frozen: only
operational fixes with a CHANGELOG line that answers "could this change a decision?" are allowed; anything that could
change a decision (news cutoff, decision time, entry day) is a new protocol with a restarted evaluation clock, and the
owner merges `main` only in fixed windows.

### Cited Findings
- Why market-on-close was dropped: on 2026-10-01 all 20 MOC orders expired; the paper engine fills `cls` orders against
  the quote in the last seconds, part-fills 10% of fill evaluations at random and expires the rest (Alpaca staff on the
  community forum; paper documentation); live `cls` orders need auction routing — reports/research/PROTOCOL_fund.md:
  399-405; fund/broker.py:3-7.
- Why T−1 min: "For large caps, the closing auction and the 4 pm midquote differ by a median 1.7 bp (Bogousslavsky &
  Muravyev, Who trades at the close?). One order at T − 1 min tracks the close better than a split over the last
  minutes" — reports/research/PROTOCOL_fund.md:420-424.
- Owner decision 2026-10-09: "The pre-close send is also the method for a live account: no closing-auction orders, so
  going live does not depend on Alpaca's auction routing. The market-on-close option was removed from the code" —
  reports/research/PROTOCOL_fund.md:431-433; fund/CHANGELOG.md:161; fund/broker.py:16-17. Protocol 7: "Orders use the
  pre-close send on the paper and the live account alike" — reports/research/PROTOCOL_fund.md:640-641.
- Why decide live: Protocol 7 was the owner's design decision (2026-10-03) that "each trade has its own life", "not
  chosen on performance" — reports/research/PROTOCOL_fund.md:588-594; decision times T−20/T−3 min —
  reports/research/PROTOCOL_fund.md:597-604; pre-registered 2026-10-09 — fund/CHANGELOG.md:162.
- Why a fixed news cutoff: replayability (Amendment 4: "a fixed cutoff (Wednesday 22:00 UTC) instead of the run's wall
  clock") — fund/common.py:41-43; reports/research/PROTOCOL_fund.md:310-311.
- Why reviews and checks trade at the same day's close: Amendment 5 ran the daily review at 17:07 UTC and traded "in
  that day's closing auction" — reports/research/PROTOCOL_fund.md:356-358 (superseded by the pre-close send and, from
  2026-10-15, by the kill checks).
- Operations rule for go-live: decisions on time in ≥ 90% of weeks; weeks fully executed ≥ 90%; median absolute
  slippage against the close ≤ 10 bp — reports/research/PROTOCOL_fund.md:238-241, unchanged under Protocol 7 —
  reports/research/PROTOCOL_fund.md:636-638. Proof test before trading: 1 SPY share, pass = 100% filled and
  |fill − close| ≤ 10 bp — reports/research/PROTOCOL_fund.md:435-437.
- Constraints: "The traded fund is frozen. Only operational fixes, each with a CHANGELOG line that answers 'could this
  change a decision?'. Anything else is a new protocol" — CLAUDE.md:55-57; fund/CHANGELOG.md:3-5. "Never merge to
  main: Wed 21:00 → Thu 17:30 UTC; 15:30–17:30 UTC on Mon, Tue, Wed and Fri; 20:30–02:00 UTC daily. Safe windows:
  weekends, and Mon, Tue, Fri 02:00–15:30. main is merged by the owner" — CLAUDE.md:62-67. A decided amendment can
  sit unmerged (Amendment 8 waited 10 days) — fund/CHANGELOG.md:64.
- The current live protocol is Protocol 7B (from session 2026-10-28) with its own clock; Protocol 7 + Amendments 8/9
  continue as a shadow control — fund/CHANGELOG.md:41-62 (Protocol 7B entry at line 57); fund/lifecycle.py:38-39.
- Instruments and hedges (SPY, sector ETFs, net exposure) are the owner's strategic policy, not tested or optimised —
  CLAUDE.md:71-73.
- README's desk table still describes execution as "closing-auction orders on Alpaca" — fund/README.md:72 — which
  the code no longer does (stale documentation).

### Inferences
- Changes that would count as operational (no decision changes): making the operations gate read
  `lifecycle/live/` records; logging the IEX trade timestamp behind each decision price; storing the previous close
  and live returns in the live record; send-schedule tweaks that do not alter decisions (for example sending at
  T−30 s instead of T−60 s), although a different fill time changes realised P&L and arguably needs the same CHANGELOG
  justification.
- Changes that would be a new protocol: moving the news cutoff or decision time, overlapping the news windows (more
  news reaches the checker), entering weekly cohorts at the Wednesday close or on news days, or changing the exit
  timing rule.
- Any timing change also has to fit the merge windows and must not land Wednesday 21:00 → Thursday 17:30 UTC, which
  covers the weekly decision and the Thursday cohort entry.

### Gaps
- The owner's reasoning for T−20 min specifically (rather than, say, T−60 min) is not written down beyond the time
  budget implied by the 3-pass LLM checks; the records show the checks take 71–279 s.
- No document weighs a live-account closing-auction (MOC/LOC) route against the pre-close send on cost or risk; the
  2026-10-09 decision is recorded without that comparison.

## Gaps (consolidated)

### Takeaway
The records are rich enough to reconstruct decision prices, closes, barrier states and slippage exactly. What they
cannot show is what happened inside the last minute (no intraday data), how stale the IEX decision prices were, how
much news the vendor delivered late, and how any of this behaves on half-days, in winter time or at a live broker.

### Cited Findings
- Sample: 11 Protocol 7 sessions (2026-10-15..10-29), 116 lifecycle fills; 150 pre-close fills in all, since 10-07;
  3 scored weeks of timing shadow books (fund-data:execution/fills.csv; fund-data:performance/weekly_books.csv).

### Inferences
- Every quantitative statement above is a small-sample description, not an estimate with power. The barrier
  conclusion (no decision would differ) is the most robust, because the observed drift is about 1% of W.

### Gaps
- **Intraday path.** No trade/quote or 1-minute data were read (no API calls), so the fill-to-close move cannot be split
  into continuous trading vs the closing auction, and spreads at fill time are unknown (sections 2–3).
- **Decision-price staleness.** The timestamp of the IEX trade behind each `prices` / `price_ref` entry is not
  recorded (section 2).
- **Vendor lag.** Finnhub's ingestion lag is inferred from article timestamps, not measured; the private Hugging Face
  archive with `fetched_at` was not read; the number of articles lost at each cutoff, and those dropped by the
  25-article cap or headline deduplication, is not logged (section 5).
- **Untested conditions.** No half-day (next: 2026-11-27, 2026-12-24), no winter-time session (from 2026-11-02, close
  21:00 UTC), no retry or cancellation, no partial fill and no missed decision window has occurred under Protocol 7
  (sections 1, 3).
- **Live vs paper.** All fills are Alpaca paper simulations; nothing measures what a live account would pay, or how a
  closing-auction order would compare (sections 3, 7).
- **Listing venue.** Not recorded anywhere, so no NYSE/Nasdaq split (section 3).
- **Reconcile marks.** Whether Alpaca's after-hours `market_value` enters `tracking_gross` at 01:10 UTC is unknown;
  the 279.5 bp tracking on 10-29 is unexplained (section 4).
- **Runner logs.** Job start times and the clock offsets printed by `broker.Clock` live in `~/Library/Logs/fund/` on
  the Mac, outside the repository (section 1).
- **Documentation drift.** fund/README.md:72 still says "closing-auction orders"; the operations gate in
  fund/score.py:334-342 reads only weekly execution records and reports "weeks fully executed 0%" under Protocol 7
  (section 3). These are findings, not gaps, but a report should not quote either as current fact.
