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
