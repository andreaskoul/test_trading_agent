# Amendment 6 implementation plan: macro, peer and filing information for the news desk

Status: planned 2026-10-01; part 1 merged 2026-10-01; parts 2–8 built 2026-10-03 on this branch. Source analysis: the desk-flow review of the first live week (as-of 2026-09-30).
This file is the working plan; the binding text goes into `reports/research/PROTOCOL_fund.md` as Amendment 6.

## Ground rules

* **The champion does not change.** Protocol 6 is live (first decision as-of 2026-09-30). Nothing below changes
  what screen, ideation, research, analysts, red team, PM/risk, execution or the daily review read or decide.
  Every new desk runs after `Commit decisions`, or after the review's trades, with `continue-on-error: true`.
* **Proof of that:** a full mock run (`FUND_MOCK=1 FUND_ASOF=2026-09-23`) on `main` and on the branch must give
  byte-identical `screen.json`, `ideation.json`, `analysts.json`, `redteam.json` and the `fund`, `analyst`,
  `quant`, `core20`, `random`, `c4_volscaled`, `c5_reversal` books. A diff blocks the merge.
* **Point in time.** Every new input is stored with the time it was fetched and read only if it was available
  before the week's fixed cutoff (Wednesday 22:00 UTC, `news_cutoff`). Sources that publish with a lag (AI-GPR is
  updated roughly monthly) are used for level and country split only, never for timing.
* **Cost ceiling:** ≤ $0.25 per week of new LLM spend at the rates billed in week one. Provider routing is
  unchanged (Amendment 4 canary rule).
* **Tests use `dry_run`.** The only automatic live effect is new files in `fund-data`.
* Commits and PR text carry no tool attribution lines.

## What gets built

| # | file | runs in | LLM | output |
|---|---|---|---|---|
| 1 | `fund/context_archive.py` | `fund_archive.yml`, daily 21:20 UTC, after the news archive | no | private HF dataset `<you>/fund-context-archive`, `days/YYYY-MM-DD.parquet` + `manifest.json` |
| 2 | `fund/macro_desk.py` | `fund_weekly.yml`, shadow stage | 1 call | `macro_brief.json` (≤ 600 tokens, fixed schema) |
| 3 | `fund/neighbours.py` | `fund_weekly.yml`, shadow stage | no | `neighbours.json` (per covered name: 5 strongest co-mentioned firms, their events in the 7 days to the cutoff, sub-industry events, 8-K items) |
| 4 | `fund/shadow_info.py` | `fund_weekly.yml`, shadow stage | 45 + 1 calls | `shadow_info.json`: C8 informed analysts, C9 ranker |
| 5 | `fund/pm_risk.py` (`FUND_SHADOW=1` branch only) | shadow stage | no | `c8_informed`, `c9_ranker` in `shadow_book.json` |
| 6 | `fund/score.py` | as now | no | C8/C9 scored as challengers; paired weekly rank-IC monitor (C8 − analyst) |
| 7 | `fund/review_context.py` | `fund_review.yml`, after the review and its trades | no | `review_context/<day>.json` (not inside `reviews/`, which review.py reads as the previous review): what proposal F would have shown, logged only |
| 8 | docs | — | — | Amendment 6, CHANGELOG, `fund/README.md` desk table and schedule |

### 1. Context archive (daily, data plumbing)
Per run, one row per item with `source`, `fetched_at`, `published_at` (when the source gives one), payload:
* FRED release calendar, next 14 days and last 14 (`fred/releases/dates`, `include_release_dates_with_no_data=true`), secret `FRED_API_KEY`; skipped with a log line if absent.
* Kalshi public market data for a fixed list of macro series (Fed decision, CPI, payrolls, GDP, recession): mid prices, snapshot at fetch time.
* AI-GPR daily CSV and its country split (whole file, versioned by hash; a new hash is a new row set).
* GDELT DOC 2.0 `timelinevol` and `timelinetone` for a fixed theme list (tariffs, export controls, sanctions, AI capex, oil supply, Fed, China, Middle East, labour strikes), with explicit `enddatetime` so a later fetch never sees post-cutoff coverage.
* Finnhub general market news (category `general`), deduplicated by id.
* SEC EDGAR daily form index (one request per business day) filtered to 8-K / 8-K/A for current S&P 500 CIKs, then each filing's item numbers and acceptance time. Secret `SEC_USER_AGENT` (name and contact email, required by the SEC); skipped if absent. Backfill 91 days on first run.
* Every source is independent: one failure logs and the rest continue; the step never fails the news archive job.

### 2. Macro desk (weekly, shadow stage)
Reads only context-archive rows with availability ≤ cutoff, plus this week's `fx.json` view and `ideation.json`
themes. One call (`llm()`, temperature 0, JSON) returns
`{"calendar": [...holding-week releases...], "regime": str ≤ 60 words, "themes": [{"name", "evidence", "sectors": [GICS]}] ≤ 3, "fx_view": str}`.
The rendered brief is a fixed-format text block, identical for every C8 call. Prompt saved (`prompts_macro.jsonl.gz`).

### 3. Neighbourhood (weekly, shadow stage, no LLM)
* Co-mention graph from the S&P 500 news archive over the 91 days to the cutoff: edge weight = articles tagging both firms, normalised by each firm's own count; self and ETF/index rows dropped.
* For each covered name: the 5 strongest neighbours, each with up to 3 deduplicated headlines from the last 7 days before the cutoff; up to 5 headlines from the rest of its GICS sub-industry; its own 8-K items in the window (item numbers mapped to plain names: 1.01 material agreement, 2.02 results, 5.02 officer change, 8.01 other events, …).
* ≤ 800 tokens per name, truncated deterministically.

### 4. C8 and C9 (weekly, shadow stage)
* **C8 informed analysts.** Prompt = shared block first (brief, ideation themes, FX view: the cacheable prefix),
  then the champion's own user prompt for the name unchanged (taken from `prompts_analysts.jsonl.gz`), then the
  neighbourhood block, then the ideation hypothesis for every covered name (rule-based names say so). System
  prompt = the champion's, plus one paragraph on how to use the shared and neighbourhood blocks. Same schema and
  checks. No red team: C8 is compared with the `analyst` book so the only difference is the information.
  Desk budget 40 minutes, 6 threads.
* **C9 cross-sectional re-score.** One call reading all C8 theses, scores, confidences, drivers and the brief;
  re-scores every name −2..+2 relative to the others, using the full range. Book: C9 score × C8 confidence,
  the champion's caps and hedge. (Changed from an ordering, which would have made C9 almost identical to C8
  whenever fewer than 10 names a side had views.)
* A week with > 25% failed C8 memos logs C8/C9 as degraded (no book), same rule as the champion.

### 5–6. Books and scoring
* `pm_risk.py` shadow branch adds `c8_informed` and `c9_ranker` with the existing `risk()`.
* `score.py`: CHALLENGERS += C8, C9. Promotion boundaries recomputed for nine challengers (O'Brien–Fleming, K = 4,
  two-sided alpha 0.05/9), computed in code and written into Amendment 6 before the first scored week.
* New monitor column: weekly Spearman rank IC of C8 scores vs next-week stock returns minus the same for the
  analyst scores, on the names both scored; running mean and NW t. This is a diagnostic, not a gate.

### 7. Review context logger (Fri, Mon, Tue, Wed, after the review)
For each held name: move since entry, the same move net of its sector ETF (XLK, XLF, …, from GICS sector), the
sector ETF's move that day, scheduled releases and a GPR spike flag in the window, new 8-Ks, neighbour headlines.
No LLM, no orders. It records what proposal F would have shown, so a later Protocol 7 has evidence.

## What is not in this amendment
* Provider sorted by price (proposal G): a host change; owner's decision under the Amendment 4 canary rule.
* Red team rebuilt as checker (D), macro-aware review decisions (F), ranker in the champion (E): Protocol 7
  candidates, only if C8/C9 earn it.

## Timeline (UTC)

| when | step | gate to pass |
|---|---|---|
| Thu 10-01 20:30 | start, after the Thursday closing auction (20:00). Confirm today's execution run succeeded and `fund-data` has the as-of 2026-09-30 execution record; if not, wait an hour, at most until 23:30 | trades placed |
| Thu night – Fri 10-02 | branch `amendment-6-info-flows`: build 1, its tests, a push-triggered dry-run workflow on the branch that runs the context archive into a scratch HF dataset and commits a summary to the branch | sources reachable, nothing written to live datasets |
| Fri 10-02 ≈ 10:00 | merge part 1 (context archive + backfill) to `main`, logged in CHANGELOG as data plumbing; first scheduled run 21:20 UTC | mock diff clean, dry run green |
| Sat 10-03 – Mon 10-05 | build 2–7 and the docs; branch tests (`a6_dryrun.yml`): mock pipeline on main vs branch, then the new desks with real calls on a copy of the live 2026-09-30 week as a dry run (cheaper than re-running the whole weekly job; `A6_TEST_CUTOFF` lets that past week see the context archive, honoured only in mock and dry runs) | champion outputs identical in mock; C8 ok-share ≥ 75%; new spend ≤ $0.25 |
| Tue 10-06 09:00 | final check; merge to `main` outside the review window (14:23–19:23); remove the temporary dry-run workflow | all gates above; context archive has ≥ 3 complete days |
| Tue 10-06 21:20 | daily context archive run | complete manifest |
| Wed 10-07 22:15 | first weekly run with the shadow stage (as-of 2026-10-07) | — |
| Thu 10-08 09:00 | post-run check: new files present, champion files unchanged in kind, cost logged, no issue opened by the new steps | report to owner |

If a gate fails, the champion keeps running as it is and the failed part waits for the next week; nothing is merged on a red gate.

## What the owner needs to add (optional, before Tue 10-06)
* Repository secret `FRED_API_KEY` (free FRED account).
* Repository secret `SEC_USER_AGENT`, e.g. `Your Name you@example.com` (SEC fair-access rule).
Without them the release calendar and the 8-K feed are skipped and logged; everything else runs.
