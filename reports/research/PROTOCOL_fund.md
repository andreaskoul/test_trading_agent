# Protocol 6: the fund, as a weekly pipeline of desks

Committed before any of the fund's code exists and before any decision.
**Supersedes Protocol 5's workflow** (which never ran). Protocol 5's
per-firm "core 20" book is kept as one of the logged comparison books.

## How a fund would do it, and why it's organised this way

A discretionary-quant equity fund doesn't have one person, or one model,
look at 500 stocks. Work moves down a funnel, and each stage is owned by
someone who can be held to account:

1. **Screening:** the quant desk ranks the whole universe cheaply on
   signals and on *attention* (where the news flow is unusual).
2. **Ideation:** a PM or senior analyst picks the few names worth a
   deeper look. That's the scarce resource: research time.
3. **Research:** analysts build the narrative for each name: what the
   stories are, which are growing, what happened this week.
4. **Analyst memos:** a view per name, with thesis, catalysts, risks and
   conviction.
5. **Red team:** someone whose job is to argue the other side before capital
   goes in.
6. **PM and risk:** turn views into a book that isn't secretly a bet on
   the market, one sector, or one name.
7. **Investment committee memo:** the written record of why.
8. **Performance and attribution:** did each stage add value? A stage
   that doesn't beat the one before it should be cut.

Each stage below is a script with a file output. The LLM steps use
`deepseek/deepseek-v4.1-flash` at temperature 0. Every artefact is committed
to the `fund-data` branch before the Thursday close at which positions are set.

## Weekly schedule

Wednesday 22:15 UTC (after the US close), one GitHub Actions run. The hard
deadline is Thursday 19:00 UTC; if it's missed, the week is flat and logged.
Positions are set at the Thursday close and held to the next Thursday close.

## Desks

| # | desk | script | method |
|---|---|---|---|
| 1 | Screen | `fund/screen.py` | S&P 500 members: Protocol 4 signal z-scores, frozen ridge forecast, 60-day beta to SPY, GICS sector; **attention**: Finnhub article count over the 7 days to the cutoff, as a cross-sectional z of log(1 + count), minus the firm's own trailing 8-week mean once ≥ 4 weeks of history exist |
| 2 | Ideation | `fund/ideate.py` | LLM reads the screen (one line per member) and nominates ≤ 12 long and ≤ 12 short ideas, each with a falsifiable hypothesis. Coverage = the dashboard's core 20 ∪ LLM nominations ∪ ridge top/bottom 6 ∪ attention top 6, capped at 45 (nominations first) |
| 3 | Research | `fund/research.py` | The narrative-dashboard pipeline (`andreaskoul/my-website` `pipeline/fetch.py` + `build.py`, pinned commit) run on the coverage list in its own workspace, with feeds and story state persisted on `fund-data`, so a name keeps its stories' continuity across weeks. New names backfill 91 days. The match regex is built from the S&P 500 security name and the ticker |
| 4 | Analysts | `fund/analysts.py` | One memo per covered name: thesis, dated catalysts, risks, `score` ∈ {−2..+2} (next-week return relative to the covered set), `confidence`. Input: signals, ridge, beta, sector, and the full narrative state (stories with 8-week continuity, weekly headlines, this week's articles, events) |
| 5 | Red team | `fund/redteam.py` | For every memo with abs(score) ≥ 1: an adversarial review on the same inputs, returning a verdict `uphold` / `weaken` / `reverse` and an adjusted score |
| 6 | PM + risk | `fund/pm_risk.py` | Deterministic, no LLM. Rank covered S&P names by (adjusted score, confidence, ridge); 10 longs and 10 shorts, filling from ridge rank if fewer than 10 per side carry a non-zero score. Risk: 60-day beta neutral (short leg scaled), each sector's net ≤ 20% of gross (the lowest-ranked offending name is replaced), single-name weight ≤ 10% of gross |
| 7 | IC memo | `fund/ic_memo.py` | LLM writes the week's investment committee memo from the book and memos. Record only; it cannot change the book |
| 8 | Macro (FX) | `fund/fx_desk.py` | Protocol 5's FX call: 17 currencies, 4 long / 4 short |
| 9 | Performance | `fund/score.py` | Thursday-to-Thursday P&L per book, costs 5 bp per side on turnover (FX: Protocol 3 costs) |

## Books logged every week

| book | what it isolates |
|---|---|
| **fund** | final, after red team and risk |
| analyst | desk 4 scores → same PM/risk rules, no red team |
| quant | ridge top/bottom 10 over the whole S&P 500 → same risk rules |
| core20 | Protocol 5: per-firm scores on the dashboard's 20, top/bottom 4 |
| random | 10/10 drawn from the covered set, seeded by date |
| fx, fx_quant, fx_random | macro desk |

## Evaluation (forward only; the LLM's training data rules out any backtest)

Primary: **fund − quant** weekly net return, Newey–West t (lags 2).
Stage value-add, pre-registered secondaries:
* analyst − quant (does research and judgement beat the screen?);
* fund − analyst (does the red team add value?);
* ideation: mean next-week |return| and signed return of nominated versus
  non-nominated names (does ideation find where the action is?);
* cross-section: weekly regression over covered names of next-week return
  on (ridge rank, analyst score), with an NW t on the analyst score.

First formal read at 52 weeks, decision at 104. No prompt, model, parameter
or pipeline-commit change inside the window. A change restarts the clock
under a new protocol number. Operational fixes that can't change a
decision (crashes, retries, logging) are allowed and are logged in
`fund/CHANGELOG.md`.

## Secrets

`OPENROUTER_API_KEY` (LLM and embeddings), `FINNHUB_API_KEY` (attention
and research), `POLYGON_API_KEY` (optional, research). If a required
secret is missing, the run fails loudly.

## Amendment 1 (2026-09-27, before any live decision): hybrid narrative input

The analyst and red-team desks receive the research output **structure first,
evidence second** (`fund/common.py: narrative_text`):

* Structure: every story over the full dashboard window (about 13 weeks), with
  its weekly share of the firm's relevant coverage, a label (NEW / rising /
  fading / stable: share now vs its own 4-week average, ±5 points), and every
  dated event in the window (* = active in the 7 days to the cutoff).
* Evidence: this week's articles under each story (date, publisher,
  headline, summary cut to 200 characters) and the top headlines of the
  events active this week.

Previously the input had 8 weeks of counts and shares, 4 weekly representative
headlines, this week's articles with 400-character summaries, and only this
week's events. Structure-only input was considered and rejected before any
use. On the dashboard's 20 firms this week, material news (Netflix's two
broker downgrades, JPMorgan's $20B QIA partnership and dividend increase)
appeared only in article text, not as detected events; direction words
appear in 30% of headlines against 36% of event names and 38% of story
blurbs, and 8 of 20 firms had no event at all.
