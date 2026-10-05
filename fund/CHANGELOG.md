# Fund changelog

Operational changes during the protocol window that cannot change a decision
(crashes, retries, logging) are recorded here. Anything that could change a
decision restarts the clock under a new protocol number (PROTOCOL_fund.md).

- 2026-09-27: pipeline built; Protocol 6 pre-registered (181752c). No live decision yet.
- 2026-09-27, dry run 1 (asof 2026-09-23, run 36298379110), before any live decision:
  - research: `build.py` crashed on a fresh workspace (missing `data/state`, `site/data`); every memo ran without narratives. Directories are created, dashboard-tracked firms start from the dashboard's fitted story state, and the desk now fails loudly if no firm gets narratives.
  - PM/risk: the short-leg scale was clipped at 0.5, which left the dry-run book at net beta −0.36. Both legs are now scaled so that beta is exactly neutral at gross 2, as PROTOCOL_fund.md specifies.
- 2026-09-27: Amendment 1, hybrid narrative input (structure first, this week's articles as evidence), before any live decision.
- 2026-09-27: news archive is incremental: raw feeds and story state are saved to `fund-data` on every run (dry runs included), the dashboard's 20 feeds are merged in each week, and Finnhub is asked only for the gap since each firm's newest stored article. Embedding-cache keep-alive workflow added. Data plumbing only; no decision input changes.
- 2026-09-27: embedding cache stored permanently in a private Hugging Face dataset (fund/emb_store.py); Actions cache kept as fast path; keep-alive workflow removed. Data plumbing only.
- 2026-09-27: Amendment 2 before any live decision, after dry run 2. The ridge is out of the analyst and red-team inputs; they get raw price facts instead. The red team can only uphold, or weaken with a named flaw. Positions are sized by conviction, with no ridge fill, sector ≤ 30% NAV, dollar net ≤ 20% of gross, and an SPY beta hedge. Factor attribution and red-team calibration are added to performance. Rationale and ridge out-of-sample evidence are in PROTOCOL_fund.md.
- 2026-09-27, dry run 4 (run 36308406530, first Amendment 2 run), before any live decision:
  - state restore: `git checkout origin/fund-data -- fund_state fund_research` restored nothing because `fund_state` isn't on the branch yet (dry runs only save research data). As a result, 24 already-stored names re-fetched 91 days (~50 min). Each path is now restored separately, and the step prints the counts.
  - ideation: one share class per issuer (GOOG and GOOGL both got covered, which cost 6,384 articles of duplicate research).
  - LLM: an empty `content` (reasoning used up the budget) is retried; 3 tries instead of 2. EXPE's red-team review failed this way.
  - PM: floating-point tolerance on the sector and dollar caps (spurious "+0.30 -> +0.30" log).
- 2026-09-27: data desk: a daily S&P 500 news archive (fund/archive.py, Finnhub, one file per UTC day) in a private Hugging Face dataset. Research merges it for the coverage list once the 91-day window is complete. Rows are cleaned exactly as pipeline/fetch.py cleans them. Data plumbing only; the articles are the ones fetch.py would have fetched, and Polygon still comes from fetch.py.
- 2026-09-27: Amendment 3, before any live decision. Adds the execution desk (Alpaca paper, closing auction, flips, halts, reconciliation) and the go-live gate (O'Brien–Fleming looks at 13/26/39/52 weeks on the fund's excess return, with stop and operations rules). Returns are aligned to trading days and a week without a book is recorded as flat. Earnings in the holding week are now a price fact. Failures, halts and gate verdicts open GitHub issues.
- 2026-09-27, dry run 5 (run 36318184301): the restore fix works (57 feeds restored; stored names fetched +0 to +14 articles, only 6 new names pulled 91 days; research 33 min). The analyst desk then printed nothing for 82 minutes and the run was cancelled. OpenRouter keeps a slow request alive with whitespace, so the 300 s socket timeout never fired on a hung call. Fix (operational):
  - a hard 240 s deadline per LLM call, read in chunks with `read1`, verified against a fake server that sends whitespace forever;
  - desk time budgets: analysts 75 min, red team 45 min; names not started by then score 0 or keep the analyst score;
  - a progress line per memo and review.
- 2026-09-28: Amendment 4 before any live decision, from the evidence review (reports/Multi agent AI trading desk design.md).
  - Decision rules (pre-registered):
    - the gate needs alpha net of SPY and reversal;
    - STOP rules are reversal-adjusted;
    - Welch-winsorised, shrunk hedge beta;
    - dollar cap at 10%;
    - pinned DeepSeek provider with a frozen canary and a succession rule;
    - degraded runs hold last week's book;
    - fixed news cutoff;
    - ideation input sorted by attention;
    - halt semantics;
    - six shadow challengers with a promotion rule.
  - Operational:
    - prompts saved;
    - append-only archive with hashes;
    - weekly monitors (performance/monitor.csv).
- 2026-09-28, dry run 6: every LLM call pinned to DeepSeek's own endpoint returned 404. The account's no-training data policy excludes that provider, and the degraded-run rule correctly held the book flat. The provider check workflow confirmed Novita, DeepInfra, GMICloud, Fireworks and AtlasCloud serve the model; unpinned routing went to Together. The pin is now Novita with DeepInfra as the only fallback (Amendment 4, corrected before any live decision). Fixed the degraded-run log line and made the IC memo tolerate a missing FX book.
- 2026-09-28: a live (not dry-run) weekly run was dispatched at 06:25 UTC for as-of 2026-09-23, after that week's deadline. Its LLM calls all failed on the DeepSeek pin, and its performance step committed live state: a missed-deadline book and an **empty** model canary. That state was removed from `fund-data`; the attention history was kept. Guards added: the weekly workflow refuses a live run past its deadline, and the canary is frozen only from a week with at least 15 ok memos.
- 2026-09-28: the provider pin was removed at the owner's request, before any live decision; OpenRouter now routes to any available host. The serving provider is still logged per call and listed in `performance/monitor.csv`. The canary rule in Amendment 4 now covers host changes: pooling across a drift needs the canary to agree, and two consecutive weeks below its thresholds restart the clock.
- 2026-09-30: position ledger (`fund/ledger.py`), an Excel file rebuilt after each weekly run and each execution/reconcile. Reporting only; no decision input changes.
- 2026-09-30: Amendment 5 before any live decision. A daily position review (`fund/review.py`, `fund_review.yml`) can exit, reduce or increase held names on confirmed material new news, traded at the same day's close with SPY re-hedged. The fund is scored piecewise between review closes. A new c7_noreview shadow book is added, and the challenger boundaries are recomputed for seven challengers. The ledger splits lots at review changes.
- 2026-09-30: reconciliation covers daily-review orders too. It now runs Tue–Sat at 01:07 UTC, one run per previous session. Also:
  - fills.csv gains a `source` column; re-reconciling one record no longer drops another's rows;
  - Alpaca cash activity (dividends on longs and shorts, fees, interest) is saved to `execution/activities.csv`;
  - the ledger values every lot boundary at the actual fill of the order traded there, so lot P&Ls add up to trading P&L;
  - the ledger lists review fills and slippage, and has a Cash activity sheet.
  Records only; no decision input changes.
- 2026-09-30: repository reduced to the fund. The legacy gold agent, its workflows, earlier protocols and reports are preserved on the `legacy-gold-agent` branch. No fund code or decision input changed.
- 2026-10-01: GitHub started the first live week's scheduled runs 3-6 hours late (weekly desks 01:17 instead of 22:15 UTC, daily review 21:21 instead of 17:07, reconcile 07:07 instead of 01:07). A late Thursday run would miss the closing auction, so execution is now attempted hourly 14:13-19:13 UTC on Thursdays (and Fridays after a Thursday holiday) and the daily review hourly 14:23-19:23 UTC; both are idempotent, so only the first run in time acts. Fill price is unchanged (closing auction). Operational only.
- 2026-10-01: GitHub did not start any scheduled execution run on the first trade day; the trade was dispatched by hand at 16:10 UTC (20/20 orders accepted). Jobs can now also be started by an external scheduler; the weekly desks gained a guard so a week with a book is never decided twice. Operational only.
- 2026-10-01: all scheduled operations moved to one external scheduler (cron-job.org) dispatching the workflows; the GitHub cron triggers were removed from the weekly, execution, review and archive workflows. Schedule and request bodies are in fund/README.md. Operational only.
- 2026-10-02: context archive (`fund/context_archive.py`), a step at the end of the daily news-archive job: FRED release calendar, Kalshi US macro markets, AI-GPR, GDELT theme volume and tone (best effort: GDELT rate-limits GitHub's runners), Finnhub general market news and S&P 500 8-K filings, stored point in time in a private Hugging Face dataset. Can't fail the news archive. No champion desk reads it; it is the input for the Amendment 6 shadow challengers (fund/AMENDMENT6_PLAN.md). Data plumbing only; no decision input changes.
- 2026-10-02: scheduled operations moved from cron-job.org + GitHub Actions to a local runner on the owner's Mac (`fund/local/runner.py`, launchd, every minute). Each job runs its workflow's steps in a fresh clone of `main`, with the same state restore, `fund-data` commits, failure issues and GitHub Pages deploy (`fund_pages.yml` dispatched after every weekly, trade, review and reconcile run). Native Python 3.11, as CI. Includes the Amendment 6 context archive step, and the Amendment 6 shadow-stage scripts once they are on `main`. The workflows stay as the manual fallback, and the 17:03 UTC backstop is unchanged. Operational only.
- 2026-10-03: execution note to Amendment 3. All 20 `cls` orders of week 2026-09-30 expired on the paper account: 6 filled in part, 14 names and the SPY hedge got nothing. Alpaca paper has no closing auction. Weekly and review orders now go out as market orders in the last minute before the close, with retries and the residual cancelled (`fund/broker.py`). Reconcile records filled quantity and fill ratio, and the ledger and dashboard use actual filled shares. The page lists filled orders only. Week 2026-09-30 is recorded as an execution failure and not topped up (owner). Scoring is unchanged. Operational only.
- 2026-10-03: mock mode removed (`FUND_MOCK`, mock outputs, the `mock_book` workflow input). Testing is on real data only: plan mode on the real account, real-call dry runs, and labelled pipeline tests. No decision input changes.
- 2026-10-03: Amendment 6 built. Shadow desks run after the decisions are committed: macro brief, neighbourhood (co-mention graph on Finnhub article ids), C8 informed analysts, C9 ranker, review-context logger. Each weekly run hashes the champion's files before the shadow stage and must find them identical after it. Real-data dry run (as-of 2026-09-30): champion hashes unchanged, C8 45/45 memos, C9 ok. Champion unchanged.
- 2026-10-05: the 1-SPY pipeline test did not run: the local runner crashed in its workflow-drift check (no workflow for the local-only filltest job) before sending anything. Fixed; any crash of the runner now texts the owner. The buy test moves to Tue 10-06 and the sell test to Wed 10-07, both before the 10-08 trade. Operational only.
- 2026-10-03: Amendment 7 pre-registered and built as shadow book C10 (`fund/lifecycle.py`): per-position horizon from an event-type table, volatility-scaled stop and target on hedged residual returns, kill-condition news exits (3 passes), overlapping cohorts, NAV-based scoring, daily mechanical gates. Challenger boundaries are now computed by integration at α/10 for C1–C10. Real-data dry run: 19/19 names classified, cohort entered 10-01, gates pass. Never traded before Protocol 7.
