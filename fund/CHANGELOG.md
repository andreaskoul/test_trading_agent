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
