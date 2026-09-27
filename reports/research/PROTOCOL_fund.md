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

## Amendment 2 (2026-09-27, before any live decision): the news desk makes the views, the quant desk measures them

**What the evidence said.** Dry run 2 (asof 2026-09-23) showed the time-series
forecast steering the news desk. Analyst scores correlated 0.54 with the ridge
forecast they were shown, and the book was 67% net long before the beta scaling.
The red team, allowed to reverse views, upheld none of 43: 37 weakened, 6
reversed, and 32 of 43 final scores were zero. After the ridge fill, the fund
book was mostly the ridge's book. The ridge does not deserve that weight:

| frozen ridge, weekly top/bottom decile | gross bp/wk | beta to EW market | alpha bp/wk | alpha t |
|---|---:|---:|---:|---:|
| 2016–26 holdout | 19.3 | 0.61 | 2.8 | 0.38 |
| 2026 live (Apr–Sep, IC 0.063, t 1.84) | 67.5 | 0.06 | 65.4 | 1.46 |

Over ten years the ridge's return is mostly market beta. Its good 2026 is 24
weeks at t 1.46. It is a weak, style-loaded signal, so as an input it anchors
the analysts on exposures the risk desk then has to hedge away, and it crowds
out the one thing only the news desk can add. It is kept where it is useful: as a
benchmark and as the factor model that the news desk's returns are measured
against.

**Changes (replacing desks 4–6 above and the book definitions):**

0. *Ideation*'s LLM sees the same price facts plus attention and the latest
   headlines, not the ridge, because its hypotheses reach the analysts. The
   ridge top/bottom 6 keep their rule-based coverage slots: the quant screen
   decides where research time goes, not which way the view points.
1. *Analysts* no longer see the ridge forecast, its rank, or the signal
   z-scores. They see price facts: sector, sub-industry, 60-day beta,
   annualised 60-day volatility, 1-week, 1-month and 12-1-month returns, % below
   the 52-week high, 7-day article count and attention shock. These are for
   judging what is already priced. The score is 0 unless the view comes from
   news. A large move on its own is not a view, and beta and style are hedged
   by the risk desk.
2. *Red team* is a filter for mistakes, not a second analyst. Its verdict is
   `uphold` (score unchanged) or `weaken`. A weaken must name its flaw
   (`factual`, `stale`, `recycled`, `contra`, `priced`) and moves the score one
   step toward 0; two steps only for a thesis-killing factual error. It never
   crosses 0. The code rejects any answer that breaks these rules; a rejected
   review falls back to the analyst's score. Counts of verdicts and flaws are
   logged every week.
3. *PM + risk*: only non-zero scores enter, at most 10 per side ranked by
   |score| × confidence. Each name's weight is score × confidence / 20 of NAV, so
   the name cap is 10% of NAV and the stock gross is at most 2. There is no ridge
   fill: a week with few views is a small book and a week with none is flat.
   Risk rules, in order:
   * sector net ≤ 30% of NAV, with the heavy side shrunk pro rata;
   * stock dollar net ≤ 20% of stock gross, with the heavy leg shrunk pro rata,
     so a one-sided week is flat;
   * an SPY position that brings the 60-day beta to zero.
4. *Books*:
   * fund and analyst as in 3.
   * quant: the ridge top/bottom 10 over the S&P 500 at 10% each.
   * random: 10/10 from the covered set at 10% each.
   * quant and random go through the same risk rules as fund and analyst.
   * core20: top/bottom 4 non-zero analyst scores among the dashboard's 20, at
     25% each, with no fill.
5. *Evaluation additions*, all pre-registered secondaries:
   * **Attribution.** Each book's weekly net return is regressed on the S&P
     members' equal-weight market return and rank-weighted long-short returns
     on rev1w, mom12_1 and lowvol. The intercept, with NW t, is the fund's
     alpha beyond the exposures the quant signals already explain. Reported
     from 8 weeks.
   * **Red-team calibration.** The mean excess return, signed in the analyst's
     direction, is compared for upheld and for weakened names.

The primary test, fund − quant, and the 52/104-week reads are unchanged. The
clock starts at the first live decision under this amendment.
