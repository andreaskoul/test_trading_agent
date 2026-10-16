# Model parity: GLM 5.3 flash vs DeepSeek v4.1 flash

Reference `deepseek/deepseek-v4.1-flash` (run twice), candidate `z-ai/glm-5.3-flash` (default reasoning), same saved prompts, JSON mode, temperature 0. Pass rule (fixed before the first run): valid(candidate) >= valid(reference) − 0.05 and agreement >= noise − 0.1. Parity only: which model decides better is a forward question.

| operation | prompts | valid ref | valid cand | noise (ref vs ref) | agreement (cand vs ref) | $/call ref | $/call cand | s/call ref | s/call cand | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| analysts | 10 | 1.00 | 1.00 | 0.90 | 0.95 | 0.0032 | 0.0029 | 22 | 40 | **PASS** |
| redteam | 10 | 0.95 | 1.00 | 0.60 | 0.60 | 0.0050 | 0.0043 | 193 | 47 | **PASS** |
| c8 | 10 | 1.00 | 1.00 | 0.70 | 0.80 | 0.0024 | 0.0037 | 21 | 37 | **PASS** |
| c9 | 2 | 1.00 | 1.00 | 0.98 | 0.77 | 0.0160 | 0.0102 | 93 | 78 | FAIL |
| macro | 2 | 1.00 | 1.00 | 0.86 | 0.77 | 0.0039 | 0.0038 | 16 | 26 | **PASS** |
| lifecycle_card | 10 | 1.00 | 1.00 | 1.00 | 0.85 | 0.0017 | 0.0022 | 11 | 46 | FAIL |
| lifecycle_check | 10 | 1.00 | 1.00 | 0.95 | 0.95 | 0.0015 | 0.0012 | 16 | 14 | **PASS** |
| r5_ledger | 10 | 1.00 | 1.00 | 0.70 | 0.82 | 0.0085 | 0.0056 | 246 | 70 | **PASS** |
| r5_peers | 10 | 1.00 | 1.00 | 0.95 | 0.89 | 0.0026 | 0.0015 | 24 | 13 | **PASS** |

Cost of the same calls: reference $0.288, candidate $0.242 (16% cheaper).

Not replayable yet (no saved prompts; they need prompt capture first): ideation, IC memo, FX desk, shadow challengers C2–C5 and the canary, daily review (action + confirm), R5 card (its saved prompt is truncated), and the dashboard pipeline's story naming and summaries (andreaskoul/my-website).

## Reading the two failures (2026-10-16)

- **lifecycle_card (2 of 10 differ).**
  - **PEP 10-07:** both DeepSeek runs typed it `dated_catalyst` with earnings on 2026-10-08. GLM typed it `analyst_revisions` with no date. A dated catalyst sets the position's horizon (trading days to the catalyst + 1), so this is a decision-relevant miss.
  - **SBAC 10-14:** `macro_readthrough` (DeepSeek) vs `mna_rumour` (GLM). A judgement call.
  - **Conclusion:** not switched until a rerun on all 40 saved cards passes.
- **c9 (ranker).** Rank correlation with DeepSeek 0.77, against DeepSeek's 0.98 with itself. GLM reorders the middle ranks. Only 2 weekly prompts exist, so this is inconclusive rather than a pass. It needs 4 or more weeks of prompts.
- **Cost.** GLM is 16% cheaper on these real prompts, not the 36% seen on news tagging. C8 and lifecycle cards cost more on GLM; the R5 ledger costs 34% less. It is often faster: the red team took 47 s instead of 193 s, the R5 ledger 70 s instead of 246 s.

## Transition schedule

What is frozen decides when a switch can happen:
- **Protocol 7** freezes the model of every desk that feeds a decision, traded or shadow-scored. Changing the model restarts its clock under a new protocol number.
- **The Thesis Tree pre-registration** fixes R5's model.
- **Only new or unfrozen work can switch freely.**

| when | step |
|---|---|
| Sat 17 Oct (weekend merge window) | Merge `fund/llm-call-log`: every call's prompt, model and billed cost is logged. |
| Sat 17 – Wed 21 Oct | One full cycle (daily jobs + the Wed weekly run) captures the prompts of the operations not yet testable: ideation, IC memo, FX desk, shadow C2–C5 and the canary, the daily review (action + confirm), and the R5 card. It also gives the fund's first exact weekly spend by job. |
| Thu 22 – Sat 24 Oct | Parity on those 6 operations. Rerun lifecycle_card on all 40 saved cards. C9 stays open until 4 or more weekly prompts exist. Dashboard pipeline (my-website story naming and summaries): parity from its own logged calls. |
| Sun 25 Oct | **Owner decision**: start Protocol 7.1 with GLM on every operation that passed, with DeepSeek kept per operation where GLM failed. `common.llm` gets a per-desk model map, which is needed either way. |
| Wed 28 Oct weekly run | Protocol 7.1 starts (if approved): traded lifecycle, weekly desks, shadow challengers, and the research desk's dashboard model. The record restarts. Doing it now loses 2 weeks of Protocol 7 history; later would lose more. |
| From its first run | News desk on GLM from day 1, since it is not frozen yet. Its node-contract test picks `effort: low` or default reasoning. |
| Q4-2026 season start (mid-Jan 2027) | R5 on GLM through a dated PREREG amendment at the season boundary, so the Q3 forward season stays single-model. GLM was released 2026-08-26, so before any historical replay with it the R0 knowledge-horizon probe must be rerun: its training may cover the sealed Jan–Sep 2026 holdout. Forward predictions are unaffected. |

Embeddings stay on `google/gemini-embedding-2`. GLM is a chat model only.
