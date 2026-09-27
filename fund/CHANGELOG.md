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
