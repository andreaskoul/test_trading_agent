# Order timing implementation plan

*30 October 2026. Turns [Fund pipeline against research and forums](Fund%20pipeline%20against%20research%20and%20forums.md)
into changes to the live pipeline, the trade monitor and the shadow books. Every item is tagged with its change class
under CLAUDE.md rules 13–14:*

* *operational: cannot change a trading decision; CHANGELOG line;*
* *amendment: changes decisions; mechanical text written before outcomes are examined; the owner decides;*
* *diagnostic shadow: never traded and never promoted.*

## What changes, in one table

| Id | Change | Where | Class | Ships | Owner sign-off |
|---|---|---|---|---|---|
| **A** | Operational fixes and logging: scorecard reads the right records; decision-price provenance; entry-day move; late-served news audit; close sources; control news symmetry; contract tests | `score.py`, `broker.py`, `lifecycle.py`, `execute.py`, `tests/` | operational | PR-1, weekend 31 Oct – 1 Nov | merge only |
| **M** | Trade monitor: new "Execution and news health" section; shadow page: estimated-live-cost line, judgement dates, weeks needed | `fund/monitor.py` (new), `site/index.html`, `site/shadow/index.html`, `fund_pages.yml` | operational | PR-1 (data), PR-3 (pages) | merge only |
| **B** | Amendment: "already priced in" measured to the entry decision with the real release time; 24-hour news lookback; entry-day news check for new names | `lifecycle.py` | amendment (Protocol 7B, Amendment 2) | PR-2, merge by Tue 3 Nov 15:30 UTC; live from session Thu 5 Nov | **yes** |
| **C** | Two diagnostic shadow books: "exits only on hard news" and "no soft-news positions" | `lifecycle.py` variants, `shadow_ledger.py`, shadow page | diagnostic shadow, registered with B | PR-2 | **yes** |
| **D** | Scorecard statistic: signed mean cost with a day-clustered bound replaces median absolute slippage | `score.py`, PROTOCOL | amendment, before the first 13-week look | PR-4, by Fri 13 Nov | **yes** |
| **E** | Offline entry-timing study: earnings 2012–2025, news shocks for the last ~12 months, by hard vs soft and by entry time | `research/` (new script), PREREG | pre-registered research | prereg Fri 6 Nov; run week of 9 Nov | **yes** (decision rules) |
| **F** | Calendar checks: winter time (Mon 2 Nov), half-day (Fri 27 Nov), quad witching (Fri 18 Dec) | runner, monitor, tests | operational | PR-1 tests; checks on the dates | no |
| **G** | Close-auction orders with a market-order fallback | go-live protocol | future protocol | at go-live only | yes, later |

**Unchanged:**

* the pre-close send at T−60 s;
* the T−20 / T−3 / T−60 timings;
* the registered 5 bp per side;
* barriers, rounding, sizing;
* the SPY sleeve and hedge policy;
* the timing shadow books, which stay as monitors.

---

## A. Operational fixes and logging (PR-1, this weekend)

None of these can change a traded decision. Each gets a CHANGELOG line that answers "could this change a decision?
No".

### A1. The scorecard reads the lifecycle records

* **Now.** The operations rule takes "executed" from weekly `execution.json` files (`fund/score.py:334-342`). Under
  Protocol 7 those are not written, so `gate.md` shows 0% of weeks fully executed.
* **Change.** For weeks from the 7B start, take "executed" from `lifecycle/live/<day>.json`: a week passes when every
  session in it has `status == "submitted"` and every order is `filled` (`fills.csv`, `source == "lifecycle"`).
* **Also compute and print, without gating yet** (D makes it the rule):
  * signed notional-weighted mean slippage against the official close, with a day-block bootstrap 95% interval;
  * the 95% one-sided upper bound;
  * fill rate;
  * residual opportunity cost on intended notional.
* **Acceptance.** `gate.md` shows "weeks fully executed 100%" for the 7B weeks, and the new statistics match a
  hand-computed check on `fills.csv`. Today's mean is +0.57 bp, standard error 0.78.
* **CHANGELOG.** "Scorecard reads the lifecycle records for orders filled; it misread Protocol 7 weeks as unexecuted.
  Could this change a decision? No; the gate verdict is reporting until a look."

### A2. Decision-price provenance and staleness

* **Now.** `broker.prices()` (`fund/broker.py:120-130`) returns the IEX latest trade. If there is none, it silently
  falls back to today's daily bar or **the previous close**: a stale price that makes the day's provisional return
  zero. No timestamp is kept.
* **Change.**
  * Add `broker.quotes(symbols)`: from the same snapshot call, return `{px, src, trade_ts, bid, ask}`, where `src` is
    one of `latestTrade`, `dailyBar` or `prevDailyBar`. `prices()` keeps its return value, so decisions are identical.
  * `lifecycle.trade()` logs `prices_meta` for both phases (T−20 and T−3) in `lifecycle/live/<day>.json`.
  * `broker.send()` takes one snapshot at T−60 and logs the quote at submission, `quote_at_send`.
* **Staleness flag, logged and shown only:**
  * `src != latestTrade`; or
  * trade age > 120 s at T−3; or
  * bid–ask spread > 25 bp.
* **Acceptance.** The Monday 2 Nov plan run writes `prices_meta` for every ticker. The flag fires on a fixture with a
  `prevDailyBar` fallback.

### A3. Entry-day move and desk-time vs entry-time "priced in"

* **Change.** In `trade()`, for every lot entering today, log:
  * `car_entry_day = side·(r_T−3 − β·r_SPY,T−3)`, the move from the as-of close to the decision;
  * the desk's `p` and `H`;
  * `p_entry` and `H_entry`, recomputed with the A3 window. This is logged only until B1 makes it the rule.
* **Acceptance.** The cohort entry on Thu 5 Nov logs all four fields per new lot. The monitor shows them (M2).

### A4. Late-served news audit

The A4 logging is a measurement, not an amendment.

* **Change.** In the nightly `daily()`, after the rebuild, re-query Finnhub over each live check's window `(lo, hi]`.
  Count the articles with publish time ≤ `hi` whose normalised headline is absent from that check's `headlines`. Log
  them to `lifecycle/news_audit/<day>.json` with publish time and source. No language-model call, and nothing feeds a
  decision.
* **Acceptance.** For 15–29 Oct (backfilled from the logged checks), the audit reproduces the earlier finding that
  live checks saw almost none of the day's late articles (1.7% vs about 25% for checks run after the close).
* **Why separate from B2.** It measures the gap before the fix, and after it.

### A5. Close sources in reconciliation

* **Now.** Slippage is computed against yfinance closes (`fund/execute.py:115-121`), while the books are marked at
  Alpaca SIP daily-bar closes (`fund/lifecycle.py:301`). Forum warning: paper, backtest and live can each use a
  different "close" (Chan; Alpaca staff on daily-bar opens and closes).
* **Change.** `fills.csv` gains `close_alpaca`, the SIP daily bar of the session. If the Alpaca auctions endpoint is
  available on this plan, it also gains `close_auction`; if not, it is skipped and logged once. `slip_bp` keeps its
  current definition.
* **Acceptance.** The monitor shows the maximum |yfinance − Alpaca| close difference per session; it is expected to
  be 0–1 tick.

### A6. Shadow control: news checked at the same time as the live book

* **Now.** The control's own positions are checked at the close in the nightly job (`control_news`,
  `fund/lifecycle.py:899-917`), about five hours after the live check. It sees about 15× more of the day's late
  articles and so has an informational edge.
* **Change.**
  * In `trade()`, once the live checks finish at T−20, run `kill_check` for the control's own open lots with the same
    `hi` (T−20) into `control/news_own/<day>.json`.
  * The run is non-fatal and bounded: it stops by T−5 min, and the live decision never waits for it.
  * The nightly `control_news` uses that file when present. Otherwise it falls back to the close and records
    `late_check: true`. The monitor counts those days.
* **Class.** This changes a shadow's registered definition, not a traded decision. It goes in now, before any
  comparison of the 28 Oct rules with their control has been made, with a dated note in PROTOCOL_fund.md under
  "Protocol 7B".
* **Acceptance.** On Thu 5 Nov, `control/news_own/<day>.json` has `close_ts` equal to the live `news_ts`. The control
  gate's look-ahead check passes.

### A7. Contract tests on real fixtures (CLAUDE.md rule 12)

New file `fund/tests/test_timing.py`, fixtures from `fund-data` copied to `fund/tests/fixtures/timing/`:

| Test | Fixture | Asserts |
|---|---|---|
| scorecard reads lifecycle records | `lifecycle/live/2026-10-15.json`, `…10-29.json`, the matching `fills.csv` rows | executed = 1.0; signed mean equals the hand value |
| retry and residual path in `broker.send` | fake API replaying Alpaca paper behaviour: a random 10% partial fill, a stalled order | resend at T−30..T−10 s, at most 3 attempts, residual cancelled at T+5 s, statuses `partial` and `unfilled` |
| half-day timeline | Alpaca calendar entry with a 13:00 close (27 Nov 2026) | T−20 = 12:40 ET, T−60 = 12:59 ET, nothing scheduled from 16:00 |
| stale price flag | snapshot with only `prevDailyBar` | `src = prevDailyBar`, flag set, `prices()` value unchanged |
| late-served audit | a logged check plus an article list containing one item published before `hi` but missing from `headlines` | audit counts 1 |
| release-time session (for B1) | MSFT and GOOGL, cohort as-of 2026-10-28, with 8-K item 2.02 acceptance times | news session = 2026-10-29, not 10-28 |

All existing tests still pass (`test_guards.py`, `test_levels.py`, `test_lifecycle_rules.py`, `test_qshadow.py`,
`test_review_rules.py`). The `daily` rebuild reproduces the NAV and leaves recorded days unchanged.

### A8. Documentation

* `fund/README.md:72` still says "closing-auction orders". Replace with "market orders in the last minute before the
  close (`broker.py`)".
* Add the pre-close timeline and the A2–A5 logs to the README's records list.

---

## M. Trade monitor and shadow page

All visible text is in plain language, with record names only in the glossary (as in PR #120).

### M0. Data: `fund/monitor.py` → `ledger/monitor.json`

A new module: no language model, no orders. It runs in the reconcile job after `ledger.py`, and `fund_pages.yml`
copies `monitor.json` next to `dashboard.json`. Inputs: `fills.csv`, `lifecycle/live/*.json`, `lifecycle/news/*.json`,
`lifecycle/news_audit/*.json`, `lifecycle/state.json` and `control/`.

### M1–M6. New section on the trade monitor (`fund/site/index.html`): "Execution and news health"

| Panel | Plain title | Shows | Amber when |
|---|---|---|---|
| M1 | **What trading costs us** | since start and last 20 sessions: signed average cost vs the official close (bp, 95% range); the split of decision price → send → fill → close (delay, trading, residual); fill rate; retries used | the 95% upper bound > 5 bp, or any unfilled order |
| M2 | **How much the price moved before we traded** | per new position: move from the signal date's close to our decision, "already priced in" at the signal vs at entry, and the horizon both ways | the move exceeds the event type's typical move (p ≥ 1) |
| M3 | **How fresh the news was** | per session: age of the newest article at the check (minutes), articles checked, late-served articles missed (A4) | newest article > 120 min old while the stock had news that day; any missed article |
| M4 | **Deciding 3 minutes early** | per session: largest gap between the decision-time and closing-time return in volatility units, closest position to a stop or target, decisions that would differ at the close | any differing decision |
| M5 | **Price checks** | stale decision prices (A2), the yfinance vs Alpaca close gap (A5) | any stale price on a traded name |
| M6 | **Calendar** | next half-day, the next expiry or index-rebalance day (wider closing gaps expected), clock offset to the broker | a half-day or expiry day within 5 sessions |

The section opens with one line: "Orders are sent in the last minute before the close and scored against the official
closing price."

### M7–M10. Shadow page (`fund/site/shadow/index.html`, `fund/shadow_ledger.py`)

* **M7. Estimated live cost line.** Every book gets a second NAV line at **2 bp per side**: half the average quoted
  spread (1.9 bp for the top 100 S&P 500 names, 2.3 bp for all 500), rounded, with no credit for price improvement
  and with paper fees of about 0.1 bp. This replaces the illustrative 1.5 bp of the companion report. It sits beside the registered 5 bp line, with a toggle that defaults to
  registered. The text says the registered line is the test, and the estimated-cost line shows what the book would
  likely earn live.
* **M8. When a comparison can be read.** Each comparison shows the earlier of two dates as "earliest fair reading":
  * the owner's mid-April 2027 date;
  * the date by which $n = (2.8\,\sigma_D/\delta)^2$ observations exist for $\delta$ = 5% a year, with $\sigma_D$ the
    observed standard deviation of the paired difference.

  If that is past 2030, the page says "cannot be told apart from noise within this experiment".
* **M9. Timing books** (entered at Wednesday's close, entered at Thursday's open). The heading reads "Monitors only:
  the difference is mostly timing luck". It shows the observed weekly difference spread and the weeks needed.
* **M10. Control symmetry date.** One line under the control: "From 5 Nov 2026 the control's own positions are
  checked for news at the same time as the fund's."

---

## B. Protocol 7B, Amendment 2 (owner decision; live from session Thu 5 Nov 2026)

*Draft text for PROTOCOL_fund.md. The owner edits and dates it. It must be committed before Tue 3 Nov 15:30 UTC to
govern the as-of 2026-11-04 cohort.*

> **Protocol 7B, Amendment 2 (owner, 2026-11-0X; from session 2026-11-05): timing corrections.** Written before any
> outcome of the affected rules has been examined. Gated by the date constant `P7B_A2`, so recorded days never change.
> Applies to the live book and to the shadow control alike, because both use the same machinery.
>
> **B1. "Already priced in" is measured to the entry decision, from the release.**
> * The news session of an earnings or guidance event is the session of its release time:
>   * first choice, the 8-K item 2.02 acceptance time within one calendar day of `first_reported`;
>   * else the earnings calendar's `bmo`/`amc` flag (before the open → that day's session; after the close → the next
>     session);
>   * else the current rule (the first article of the first-report date).
>   * Other event types keep the current rule.
> * At the entry decision (T−3 min on the entry day), CAR runs from that session to the decision. It is the daily
>   beta-adjusted returns to the as-of close plus the provisional entry-day return to T−3 min.
> * $p$ and $H$ are recomputed with Amendment 8's formula, unchanged. If $p \ge 1$, soft news is not entered and hard
>   news gets $H = 3$, as now.
> * The structural rule (R2) keeps precedence for structural lots.
> * Both the desk-time and entry-time values are logged.
>
> **B2. News checks look back 24 hours.**
> * A check takes articles published in $(\text{previous cutoff} - 24\text{h},\ \text{T}-20\text{ min}]$ and drops any
>   headline already checked for that position (the existing `seen` set).
> * An article the vendor serves late is therefore checked at the next session at the latest. Nothing published after
>   T−20 min is used.
>
> **B3. New positions are checked before entry.**
> * On the entry day, at T−20 min, each new cohort name gets the standard three-pass check of its kill conditions.
> * Articles: published from 24 hours before the desk's cutoff to T−20 min, minus headlines the desk already read.
> * Matched in ≥ 2 passes: not entered. Partial in ≥ 2: entered at half weight. Otherwise as decided.
> * No increase at entry.
>
> **Reporting.** Descriptive counts only: lots whose horizon changed under B1, articles caught only by B2, entries
> stopped or halved by B3. They are not evidence of edge. The 7B clock does not restart, since these are corrections
> to shared machinery.

**Implementation** (`fund/lifecycle.py`):

* **B1.**
  * Add `release_session(t, out, days, edgar, cal)`. It reuses `edgar_202` (line 346) and the calendar's `hour`
    field, which `earnings_next` (line 477) already returns.
  * In `run(live=…)`, compute CAR for lots with `entry_day == today`, using the live `ret` already passed to `run`,
    and call `horizon8` with it.
  * The control reads the same T−3 prices from the live record.
* **B2.** In `kill_check`, set `lo = news_until − 86400` (line 667). `finnhub_news`'s filter (line 648) and the `seen`
  dedup (line 671) do the rest. About 5 lines.
* **B3.** In `trade()` `decide("news checks")`, call `kill_check` for the entering lots with `news_until` = desk
  cutoff − 24 h. Seed `seen` with the desk's input headlines from `prompts_lifecycle`. Apply the verdict in the
  entry's weight before caps.
* **Tests.** The release-time fixture (A7); a B2 test where an article published before the previous cutoff but
  absent from `seen` is checked; a B3 test where `matched ≥ 2` leaves the lot out.
* **Language-model cost.** B3 adds about 3 passes × ~20 names a week, about 60 calls. B2 adds articles to existing
  calls rather than new calls. Both are small next to the forecasting research desk's spend (~85%).

**CHANGELOG** (amendment line): "Protocol 7B Amendment 2 (B1–B3). Could this change a decision? Yes: horizons of
lots whose news came after the signal-date close, news exits from late-served articles, and entries with
contradicting news on entry day."

---

## C. Two diagnostic shadow books (registered with B; start session Thu 5 Nov)

Both are **diagnostics**: never traded, never promoted, and outside the challenger family, so the champion's
multiple-testing budget is untouched. They inform the next protocol's design and verify its machinery.

| Book | Plain name on the page | Rule | Extra model calls |
|---|---|---|---|
| **C1** | **Same fund, but exits only on hard news** | A news exit or halving happens only if the matched article is hard: a reported or official fact with numbers or legal force, such as results, guidance numbers, a signed or cancelled contract with terms, or a regulatory or court decision. Leadership changes, previews, opinions and rumours are soft. Hardness comes from one labeller, 3 passes, majority, run only on matched articles. Soft matches → hold. Increases unchanged (already hard-only) | ~1–3 labeller calls per exit; own lots checked at T−20 as in A6 |
| **C2** | **Same fund, without soft-news positions** | From the as-of 2026-11-04 cohort, lots are not entered when their event type is product launch, partnership, leadership, macro read-through, M&A rumour or "other" **and** the desk's `hard` label is false. Freed capacity is left unused; SPY re-hedged. Older lots as live | none: a strict subset of live lots reuses the live checks |

**Engine.** Generalise `run(variant=…)` (line 934) from `"control"` to `{"control", "hardexit", "nosoft"}`. Each
variant logs `lifecycle/<variant>/days/<day>.json`, rebuilds deterministically and gets the control's gates
(reproduction, unchanged recorded days, no look-ahead). The runner adds two steps after "Protocol 7B shadow control"
in the reconcile job. `shadow_ledger.lifecycle(base, sub)` already takes a `sub` argument.

**Pre-registered reading.**

* Statistic: the daily return difference $d_t$ = variant − live, at registered and estimated-live costs, with a
  Newey–West t at lag 5.
* First reading: not before mid-April 2027, and not before $n \ge (2.8\,\sigma_d/\delta)^2$ sessions for $\delta$ =
  5% a year.
* With $\sigma_d \approx 20$ bp a day (an estimate, to be replaced by the observed value):

| Difference to detect | Sessions needed |
|---|---|
| 5% a year (≈ 2 bp a day) | ≈ 780 (3 years) |
| 15% a year (≈ 6 bp a day) | ≈ 90 |

**So the shadows detect only gross effects.** The decisive evidence on soft news is study E. The shadows are built
because they cost almost nothing, and because the next protocol needs the machinery tested in production first.

---

## D. Scorecard statistic (amendment before the first 13-week look)

*Draft text. Commit by Fri 13 Nov; the first look on the 7B clock is in late January 2027.*

> **Operations rule, revised (owner, 2026-11-XX), before any look.** Operations pass at a look when all of these hold:
> 1. decisions are on time in ≥ 90% of sessions;
> 2. every order is fully filled in ≥ 90% of sessions (from the lifecycle records);
> 3. the one-sided 95% upper bound of the signed, notional-weighted mean cost per side against the official close is
>    ≤ 5 bp, the registered cost. The bound uses a day-block bootstrap; residuals are charged as opportunity cost on
>    intended notional at the session's official close.
>
> Median absolute slippage is reported as dispersion, not gated. Reason: the median of |slippage| tests spread, not
> cost. It fails only if the per-fill standard deviation exceeds about 15 bp, whatever the bias.

Code: `score.py` uses A1's statistics for `ops_ok`. Test: on the current `fills.csv` the bound is about 1.9 bp → pass.

---

## E. Offline entry-timing study (pre-register Fri 6 Nov; run the week of 9 Nov)

This is the decisive instrument for the two largest questions:

1. Do soft-news positions lose after costs?
2. Does entering a day after the news cost money?

It changes nothing live. Its decision rules feed the next protocol. New file `reports/research/PREREG_entry_timing.md`
and script `research/entry_timing.py`.

* **E1a, earnings, 2012–2025 (feasible now, no model calls).**
  * Events: S&P 500 8-K item 2.02 acceptance times from EDGAR (`edgar_202`).
  * Sign: the day-0 abnormal return.
  * Entry points: the release session's close; the next close; the next Thursday close (the fund's timing); the next
    open.
  * Outcome: beta-adjusted drift at days 1, 5, 10 and 20, split by before-open vs after-close release.
  * Day-clustered standard errors.
* **E1b, news shocks, the last ~12 months.**
  * Step 0, feasibility: confirm how far back Finnhub company news goes for S&P 500 names. If less than 6 months, E1b
    waits for the fund's own archive to accumulate.
  * Events: news-shock sessions as defined in `m_table`: ≥ 5 articles and ≥ 3× the name's median count, not within
    2 sessions of earnings.
  * Type: hard or soft, from one model call per event with the C1 definition. Capped at 3,000 events and $5.
  * Direction: the day-0 abnormal return. The model never sees prices or directions, which limits look-ahead from its
    training data.
* **Decision rules (pre-registered, one-sided, Holm-adjusted across the four).**
  * Soft-news 5-day drift from the fund's entry point < 0 at p < 0.05 → the next protocol enters no soft-news
    positions.
  * Soft-news drift ≤ −2× round-trip estimated live cost at p < 0.01 → the next protocol may *fade* soft news
    (separately registered).
  * Hard-news drift between the release-session close and the Thursday close > 2× round-trip cost at p < 0.05 → the
    next protocol uses event-driven daily entries.
  * Hard-news drift over days 6–20 > 0 at p < 0.05 → the multi-week horizons for hard news stand. Otherwise they
    shorten to the drift's half-life.
* **Power.** E1a has about 4 reports a year × 500 names × 14 years ≈ 28,000 events. At a 200 bp per-event daily standard
  deviation, the standard error is about 1.2 bp, so it detects about 3–4 bp. E1b at 3,000 events detects about 23 bp
  at five days, the size of the reported soft-news reversal.

---

## F. Calendar and operations checks

| When | Check | How |
|---|---|---|
| **Mon 2 Nov** (first session in US winter time) | The trade path computes T from Alpaca's clock and calendar, not a fixed UTC hour | read the plan run's log at 16:15 UTC; T−20 must be 15:40 ET = 20:40 UTC |
| **Fri 27 Nov** (13:00 close; also the cohort entry after Thanksgiving, with a 44-hour information delay) | half-day timeline | A7 test in PR-1; the monitor's calendar panel flags it from 20 Nov; a plan run at 16:00 UTC that day confirms T−20 = 17:40 UTC |
| **Fri 18 Dec** (quarterly expiry and S&P rebalance) | wider closing gaps are expected, not failures | monitor flag M6; no action |
| every session | stale decision prices (A2) | monitor M5 |

---

## G. At go-live only: close-auction orders with a fallback

Not now. Paper has no auction, and the forum record on Alpaca's live auction routing is contested. At go-live,
pre-register:

* decide at 15:45 ET, with the news cutoff moving to about T−30 min, which costs almost nothing given the 1.5–3 hour
  vendor lag;
* send close-auction orders by 15:49:55;
* keep today's T−60 s market-order path as the fallback for any rejected or unfilled order (Concretum's layered
  pattern).

Before that, get Alpaca's written confirmation that live close-auction orders route to the primary auction.

---

## What we deliberately do not do

* **No tuning of T−20, T−3 or T−60 on outcomes.** Every minute chosen is a free parameter (forum warning).
* **No open, VWAP/TWAP or limit-order execution.** Every source rules them out for a close-marked book of this size.
* **No change to the registered 5 bp.** M7 shows the estimated live cost beside it instead.
* **No reading of the timing books, C1 or C2 before their dates.** M8 prints the dates.
* **No event-driven daily entries before E1a reports.**
* **No change to the sleeve or hedge policy.**

---

## Schedule and merge windows

Safe merge windows: weekends; Mon, Tue and Fri 02:00–15:30 UTC. `main` is merged by the owner.

| Date (UTC) | Step | PR |
|---|---|---|
| Fri 30 Oct | plan reviewed by the owner; owner decides B, C, D and E's decision rules | — |
| Sat 31 Oct – Sun 1 Nov | **PR-1** (A1–A8, M0 data, A7 tests) built, tested, merged | PR-1 |
| Mon 2 Nov | first winter-time session: check the plan run (F); first `prices_meta` and news audit records | — |
| Mon 2 – Tue 3 Nov, by **15:30** | **PR-2** (B1–B3 amendment text and code; C1 and C2 variants) merged | PR-2 |
| Wed 4 Nov 22:15 | weekly desk, as-of 4 Nov cohort | — |
| **Thu 5 Nov** | first session under B; C1 and C2 start; A6 control symmetry live | — |
| Fri 6 Nov, by 15:30 | **PR-3** (monitor and shadow page M1–M10); E pre-registration committed | PR-3 |
| week of 9 Nov | run E1a, and E1b if feasible; write up | research |
| Fri 13 Nov, by 15:30 | **PR-4** (D: scorecard statistic) merged | PR-4 |
| Fri 20 Nov | monitor flags the 27 Nov half-day | — |
| Tue 24 Nov, by 15:30 | last safe window before the half-day; nothing should be pending | — |
| Fri 27 Nov | half-day plan run at 16:00 UTC; live at 17:40 UTC | — |
| late Jan 2027 | first 13-week look on the 7B clock, under D | — |
| mid-April 2027 | earliest reading of any shadow comparison (owner's rule; M8 may say later) | — |

## Owner decisions needed

1. **B (Amendment 2):** approve B1, B2 and B3 as written, or strike any of them, by Tue 3 Nov 15:30 UTC.
2. **C:** register both diagnostics, including the soft-news type list and the hard-article definition.
3. **D:** the revised operations rule, by Fri 13 Nov.
4. **E:** the four decision rules and the $5 / 3,000-event cap for E1b.
5. **A6:** confirm the control's news-time correction as a dated shadow note. It is operational for the traded book.
