# Protocol 6: the fund, as a weekly pipeline of desks

> Earlier protocols (1–5), the research they reference (the ridge, the FX ladder, the per-firm
> core 20) and their reports are preserved on the `legacy-gold-agent` branch.

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

## Amendment 3 (2026-09-27, before any live decision): execution, the go-live rule, and what counts as a result

**Why now.** Paper trading starts with the first live week (as-of 2026-09-30). The
rule for deciding whether to trade real money is fixed before any result exists.
Otherwise a good or bad quarter would decide it after the fact.

**Execution (desk 10, `fund/execute.py`, Alpaca paper account).**
* The fund book is traded at the close of the first trading day after the as-of
  Wednesday, the same price the performance desk scores at. That is normally
  Thursday; after a Thursday holiday it is the next session.
* Orders are market-on-close (`cls`), sent while the market is open, whole shares at
  the account's equity.
* Alpaca rejects an order that takes a position through zero. A name that flips side
  is therefore closed with a market order first and reopened on the close; these are
  logged as flips.
* Pre-trade rules:
  * no valid book after the Thursday 19:00 UTC deadline, a risk halt, or a book that
    fails sanity checks (gross including SPY > 3, any stock > 12% of NAV) means the
    target is flat;
  * longs must be tradable, and shorts shortable and easy to borrow. A dropped
    name's beta goes back to the SPY hedge;
  * gross is scaled to at most 1.8× equity (Reg T 2×).
* Idempotent: one execution per week, and client order ids are fixed per week,
  symbol and leg.
* Reconciliation after the close records each fill against the official close
  (slippage in bp; positive means worse), realised against target weights, and the
  broker's daily NAV.

**Risk halts.** If the broker NAV falls 10% from its peak, or 5% over the last five
sessions, a HALT file is written. From the next execution the fund is flat until a
person reviews it and resumes (`fund_execute.yml`, input `resume`).

**What is measured.**
* Weekly returns are now measured from the close of the execution day to the first
  close on or after the next Thursday. Before, a holiday Thursday fell back to the
  Wednesday price.
* A week without a book is recorded as flat, with the cost of closing out.
* Each stock book also reports its return **in excess of cash**:
  gross − 5 bp/side costs − r_f × net dollar exposure, with r_f the 3-month T-bill
  (FRED DTB3). The book is a beta-hedged overlay, so "beats the market" means
  SPY plus the overlay beats SPY, which is exactly an overlay excess return above 0.
* The screen adds whether a member reports earnings inside the holding week (Finnhub
  earnings calendar). Analysts and the red team see it as a price fact.

**The go-live rule (`performance/gate.md`, recomputed every week).**

| look (scored weeks) | 13 | 26 | 39 | 52 |
|---|---:|---:|---:|---:|
| GO if the NW t (lags 2) of the fund's weekly excess return ≥ | 4.05 | 2.86 | 2.34 | 2.02 |

These are O'Brien–Fleming boundaries for four looks at an overall two-sided α of 5%.
Early looks need overwhelming evidence, so looking early does not inflate the false
positive rate. At each look, in order:

1. **HALTED** if a risk halt is active.
2. **STOP** if any of these NW t-statistics is ≤ −2: the fund's excess return,
   fund − quant, or the weekly analyst-score slope.
3. **GO** if the boundary is crossed and operations pass. Operations pass means:
   * decisions on time in ≥ 90% of weeks;
   * weeks fully executed (every order filled) ≥ 90%;
   * median absolute slippage against the close ≤ 10 bp.
4. **NO-GO** at 52 weeks with no boundary crossed: no edge shown.
5. **GO-SMALL** (from 13 weeks) if operations pass, nothing has stopped it, and the
   mean excess return is positive. This permits a small live allocation sized as if
   the edge were zero (tuition, not an allocation). It is not evidence of an edge.
6. **CONTINUE** otherwise.

The verdict only changes at a look, except for a risk halt. The primary test of
Protocol 6 (fund − quant) is unchanged and remains a stop condition. Going live
with real money is still the owner's decision; the gate says what the evidence
allows.

## Amendment 4 (2026-09-28, before any live decision): what the evidence review changed

Source: `reports/Multi agent AI trading desk design.md`, a review of the literature on
multi-agent LLM trading, leakage, institutional risk practice and LLM news alpha, applied
desk by desk. The review found no reason to add agents, debate or reflection memory. The
debate literature predicts they would make the book more cautious, not more skilful, and
no post-cutoff ablation supports them. It did find four validity threats, fixed here
before the clock starts.

**1. The verdict must measure news skill, not beta or reversal.** The quant benchmark is
essentially a one-week reversal book: the ridge correlates +0.66 with rev1w on the
2026-09-23 screen. The dry-run analysts leaned the other way, with +0.33 against last
week's return. So fund − quant ≈ news skill − about 2× the reversal factor.
* **GO** now needs *both* the excess-return NW t *and* the NW t of the intercept of the
  fund's excess return regressed on SPY and the rev1w factor to cross the look's
  boundary.
* **STOP on fund − quant** uses the intercept t after regressing the difference on
  rev1w.
* **STOP on the score slope** uses the weekly cross-sectional slope of next-week return
  on the analyst score, controlling for last week's return, hedge beta and sector.
* **NO-GO at 52 weeks** means "no real money". The paper record continues to Protocol 6's
  104-week decision.
* Computed in `fund/score.py` → `performance/gate.md`.

**2. The hedge must rest on a real beta.** 60-day OLS betas had a median of 0.31 and an
interquartile range of −0.10 to 1.01 in September 2026, with a standard error of about
0.2.
* The hedge beta is now Welch's (2022) slope-winsorised 252-day beta: each daily stock
  return is clipped to lie between −2× and 4× the market's return. It is then shrunk one
  third toward 1: β_hedge = ⅔·β_W + ⅓.
* Execution re-hedges dropped names with the same beta.
* Dollar net is capped at **10%** of stock gross (was 20%).
* `beta60` stays a price fact for the analysts.

**3. The model must not change unseen.** OpenRouter routes `deepseek/deepseek-v4.1-flash`
to the cheapest of about 20 hosts, some serving fp4 or fp8 quantisations.
* **Serving provider.** It is left to OpenRouter's routing, so whichever host is available
  serves `deepseek/deepseek-v4.1-flash`. This is the owner's decision of 2026-09-28, before
  any live decision. The provider that answered and the raw output are logged with every
  memo, and the weekly monitor lists the providers used.
  * History: the draft pinned DeepSeek's own endpoint, which the account's no-training data
    policy excludes (dry run 6: HTTP 404 on every call). A Novita/DeepInfra pin then
    worked (dry run 7).
  * Because hosts differ (fp4 to full precision), the canary below is the control on
    whether the served model's behaviour changed.
* **Canary.** The first live week's first 20 analyst prompts are frozen and re-scored at
  temperature 0 every week (`fund/shadow.py`, `canary/history.csv`).
* **Degraded run.** If more than 25% of memos fail, the fund and analyst books hold last
  week's weights (flat if there are none). A partial set of views is not a book.
* **Succession.** If the model is retired, the successor is `deepseek/deepseek-v4.1`.
  * Weeks before and after a switch are pooled for the gate only if the canary shows
    ≥ 80% exact score agreement and a mean absolute difference ≤ 0.3 against the frozen
    scores.
  * Otherwise the clock restarts. The same rule applies if the canary drifts below those
    thresholds for two consecutive weeks for any reason, including a change of host.

**4. Decisions must be replayable.**
* The analyst and red-team news cutoff is fixed at Wednesday 22:00 UTC (it was the run's
  wall clock).
* Every prompt is saved gzipped with its week.
* The news archive is append-only: first-seen text is never overwritten, and revised text
  is kept as a further row with its content hash and ingestion time.

**Smaller changes.**
* Ideation reads the 500 screen lines sorted by attention shock, not alphabetically,
  because LLMs attend least to the middle of long inputs.
* A resumed risk halt continues the same clock, and halted weeks score the fund as flat.

**Shadow challengers.** These are registered now, computed every week from the same
inputs, scored with the same costs, and never traded:

| book | what it tests |
|---|---|
| c1_wedclose, c1_thuopen | The fund's weights entered at the Wednesday close (notional) and at the execution day's open, each held a week. This measures what the one-day delay costs; large-cap news drift is mostly one day. |
| c2_selfconsistency | 5 samples at temperature 0.7. Score = median; confidence = max(0, 1 − sd/2). |
| c3_textonly | No price facts or hypothesis; the firm's name, ticker and match terms are masked. Separates reading the news from chasing last week's return. |
| c4_volscaled | Score × confidence / volatility, scaled to the fund's stock gross, each name ≤ 10%. Band: a held name whose score drops to 0 keeps its weight one more week. |
| c5_reversal | The fund's views, plus a short-term reversal position (rank of last week's return, ≤ 3% each) on covered names with a zero score and no event active in the last 7 days. Uses the LLM as a news/no-news classifier, where its evidence is strongest. |

**Promotion rule.** A challenger replaces the champion only at a look, if its excess
return minus the fund's has an NW t at or above the same O'Brien–Fleming design at α =
0.05/6: 5.34 / 3.77 / 3.08 / 2.67 at 13 / 26 / 39 / 52 weeks. The promoted book's
clock is its shadow start date. The registered trial count is 6 challengers plus the
champion. Any new variant adds to it.

**What stays.**
* The deterministic PM desk, the filter-only red team, the random, analyst and quant
  books, execution, halts and costs.
* The review's own estimate: a large-cap weekly LLM news book should be expected at
  roughly 0–0.5 Sharpe after costs.
  * Under that prior the modal 52-week verdict is NO-GO. That reflects the test's power,
    not proof of no edge.
  * The highest-power evidence the year will produce is the adjusted score slope, the
    timing books and the challenger contrasts.

## Amendment 5 (2026-09-30, before any live decision): daily position review

The owner asked for held positions to be re-examined every day against new news: exit
when news materially contradicts the thesis, and enlarge when it materially strengthens
it. This is registered before the first live week, so it is part of the fund under test
from day one.

**Desk 12, `fund/review.py`, `fund_review.yml`.**
* **When.** Every trading day strictly between the week's execution day and the next
  one: Friday, Monday, Tuesday and Wednesday in a normal week. It runs at 17:07 UTC,
  with an 18:07 fallback, and trades in that day's closing auction.
* **What it reads.** For each held stock, only the news published since the last review.
  For the first review of a week, that is news since the book's Wednesday 22:00 UTC
  cutoff. A stock with no new article is held, and no LLM call is made.
* **Two calls per proposed change.**
  * A reviewer (same model, temperature 0) proposes hold, exit, reduce or increase from
    the position, its entry thesis, catalysts and risks, the move since entry, and the
    numbered new articles. Any action other than hold must cite articles.
  * A risk officer must then confirm it. It rejects only by naming a flaw: factual,
    stale, recycled, priced or immaterial. A rejection means hold.
* **Sizes.**
  * exit → 0.
  * reduce → half the current weight.
  * increase → 1.5× the book's weight, capped at 10% of NAV, and at most once per name
    per week.
  * At most 5 actions a day, largest positions first.
  * An increase is dropped if stock dollar net would exceed 10% of stock gross and be
    more unbalanced than before.
  * SPY is re-hedged to zero beta with the book's hedge betas. If the hedge would cross
    zero, it goes to zero that day.
* **Safety.**
  * No reviews while a risk halt is active.
  * One review per day, idempotent.
  * No new positions and no flips; only held names change.

**Evaluation.**
* The fund is scored piecewise between review closes, with 5 bp/side on each change.
* A new shadow book, **c7_noreview**, holds the weekly book untouched all week. So
  fund − c7_noreview is what the reviews added or cost, including their extra costs.
* The challenger promotion boundaries are recomputed for seven challengers at α = 0.05/7:
  **5.44 / 3.85 / 3.14 / 2.72**.
* If c7_noreview beats the fund at a look by that margin, the reviews are removed, by
  the same promotion rule.

**Why it is registered this way.** In the review's evidence base, large-cap news is
mostly priced within about a day. Acting at the next close may therefore add turnover
more often than it avoids losses. The c7 contrast measures exactly that, instead of
assuming it.

## Execution note to Amendment 3 (2026-10-03, operational; no decision input or score changes)

**What happened.** On 2026-10-01 all 20 market-on-close orders of the first live week
expired on the Alpaca paper account. Six filled in part, between 15:59:55 and 15:59:58 ET;
fourteen names and the SPY hedge got nothing. The paper engine has no closing auction:
it fills a `cls` order against the quote in the last seconds, part-fills 10% of fill
evaluations at random, and expires the rest (Alpaca staff on the community forum; paper
trading documentation). Alpaca staff also say live `cls` orders need auction routing.

**Change.** Orders, both weekly and daily review, go out as market orders in the last
minute before the close (`fund/broker.py`):
* T − 150 s: the orders are sized from fresh prices, equity and positions.
* T − 75 s: the close legs of flips go out.
* T − 60 s: all other orders, SPY included. A flip's open leg goes out once its close
  leg has filled.
* T − 30 s to T − 10 s: every 10 s, an order with no new fill is cancelled and its
  remainder resent, up to 3 attempts.
* T − 10 s: nothing new is sent.
* T + 5 s: anything still open is cancelled. The residual is recorded as not fully
  filled and absorbed by the next rebalance, never carried overnight.

T is the session close from Alpaca's clock, corrected for the local clock's offset.

**Why this price.** For large caps, the closing auction and the 4 pm midquote differ by a
median 1.7 bp (Bogousslavsky & Muravyev, *Who trades at the close?*). One order at T − 1
min tracks the close better than a split over the last minutes. A median slippage within
the gate's 10 bp is therefore expected. It is measured, not assumed: reconciliation
records every fill against the official close.

**What does not change.** The books are scored at official closes as before, and the
operations rule (≥ 90% of weeks fully filled, median slippage ≤ 10 bp) is unchanged.
Week 2026-09-30 is recorded as an execution failure (about 11% filled), and by the
owner's decision it is not topped up before its next rebalance.

**Before go-live.** `FUND_EXEC_STYLE=cls` (real market-on-close orders, sent before
15:50 ET) is available. It may be used on a live account only after Alpaca confirms
auction routing for it. Until then the pre-close send is the method.

**Proof before the next weekly trade.** One labelled share of SPY is bought on
Mon 2026-10-05 and sold on Tue 2026-10-06 through the same path (`execute.py filltest`,
client ids `fund-test-…`). Pass: 100% filled, |fill − official close| ≤ 10 bp.

## Amendment 6 (2026-10-03, before the first week it affects, as-of 2026-10-07): macro, peer and filing information, shadow only

**The champion does not change.** Screen, ideation, research, analysts, red team, PM/risk, execution
and the daily review read nothing new. The new desks run after the decisions are committed, and must
leave the champion's files (`screen`, `ideation`, `analysts`, `redteam`, `book`, `fx`) byte-identical.
The weekly job hashes these files before the shadow stage, re-checks them after it, and fails on any
difference.

**Inputs, point in time.** All inputs are read only if they were available before the week's cutoff
(Wednesday 22:00 UTC).
* *Context archive* (`fund/context_archive.py`, daily after the news archive): FRED release calendar,
  Kalshi US macro markets, AI-GPR (level only; it is revised and published with a lag), GDELT theme
  volume and tone, Finnhub market news, and S&P 500 8-K filings. It is append-only, and a desk reads
  rows by fetch time.
* *News archive* (`fund/archive.py`): read by publication time.

**Desks.**
* *Macro brief* (`fund/macro_desk.py`, one call): a fixed schema of holding-week calendar, regime
  (≤ 60 words), ≤ 3 themes mapped to GICS sectors, and an FX view. It is rendered as one text block,
  identical for every C8 call.
* *Neighbourhood* (`fund/neighbours.py`, no LLM): a co-mention graph over the 91 days to the cutoff.
  An edge counts distinct Finnhub articles filed under both firms; round-ups filed under more than
  10 firms are excluded. Each covered name gets its 5 strongest neighbours (≥ 3 shared articles), each
  with up to 3 headlines from the last 7 days. Articles also filed under the name itself are excluded.
  It adds up to 5 sub-industry headlines and the name's own 8-K items in the window, at most 3,200
  characters per name.
* *C8 informed analysts* (`fund/shadow_info.py`): the champion analyst prompt unchanged, between a
  shared block (the brief, ideation themes, the FX view, every covered name's hypothesis) and the
  neighbourhood. The system prompt is the champion's plus one paragraph on the new blocks. Same schema
  and checks, no red team, so **C8 against `analyst` isolates the information**. Book: the champion's
  sizing and risk rules.
* *C9 ranker*: one call orders C8's non-zero views, ties allowed, with longs above shorts. Book: the
  champion's caps and hedge, N per side in the ranker's order, sized by C8's score × confidence.
* A week with more than 25% failed C8 memos has no C8 or C9 book.
* *Review context* (`fund/review_context.py`, after each daily review, no LLM): logs per held name the
  move since entry, net of its sector ETF, scheduled releases, the GPR level, new 8-Ks and neighbour
  headlines. Nothing reads it.

**Scoring.** C8 and C9 are challengers, scored like every weekly book. A monitor, not a gate: the
weekly Spearman rank IC of C8 scores minus the analysts' on the names both scored, with its running
mean and NW t.

## Amendment 7 (2026-10-03, before the first cohort, as-of 2026-10-07): a lifecycle for every position, shadow book C10

**Why.** A news view has its own life. Large-cap drift after news is short and depends on the kind of
news: hard-number news drifts for days to weeks; soft news is priced on the day and tends to reverse
(Kargarzadeh et al. 2026; Lopez-Lira & Tang; Tetlock 2007/2011; post-earnings drift has largely gone
from large caps, Martineau 2021). A one-week hold for every view ignores that. C10 tests a position
lifecycle against the weekly book, without trading it.

**The cohort.** Each week's fund book (after the red team and PM/risk) is a cohort. It enters at the
close of the execution day.

**Horizon: a fixed table, not the model's guess.** LLMs are poorly calibrated on time horizons
(KalshiBench). The lifecycle desk (`fund/lifecycle.py desk`, one call per name) only classifies:
* the driving `event_type` (fixed list);
* the date the event was first reported (within the 91 days to the cutoff);
* a scheduled `catalyst_date` (a real trading day after entry, ≤ 20 trading days away);
* 1–3 falsifiable `kill_conditions` observable in news.

| event type | H_type (trading days) |
|---|---|
| earnings, guidance, capital return | 15 |
| analyst revisions | 10 |
| legal or regulatory | 7 |
| product launch, partnership, leadership, macro read-through, M&A rumour, other | 5 |
| dated catalyst | trading days to the catalyst + 1 |

H = H_type − news_age, where news_age is the number of trading days from the first report to the
entry day. H is clamped to 3–20. If H_type − news_age ≤ 2 the view is stale and not entered.
Re-estimating the table requires ≥ 30 own trades per type and a new amendment.

**Stop and target, on hedged residual returns, at the close.**
* e = r − β·r_SPY, with β the screen's hedge beta.
* σ_e is the EWMA (span 60) of e up to the entry close, floored at 0.75 × the 252-day standard
  deviation and frozen at entry.
* W = σ_e·√H, also frozen at entry.
* Exit at the close when R = side·Σe since entry reaches **−2.0·W (stop)** or **+3.0·W (target)**.
  This is never checked on the entry day.
* The stop is wide on purpose: stops help only under momentum or regime shifts, and tight stops on
  single stocks underperform (Kaminski & Lo 2014; Lo & Remorov 2017). The target is wider still,
  because selling winners early forgoes drift (Odean 1998; Frazzini 2006).
* After a stop: no same-side re-entry for 5 trading days unless a new event has an |score| at least
  as high. After a target: no re-entry without a new event.
* A sensitivity grid (stop 1.5–2.5, target 2.5–off) is reported as a monitor and never used to tune.

**News exit.** Each trading day, only stories that are new since the last check go to a checker.
* For each kill condition it answers matched / partial / not, quoting the article.
* It runs three independent passes: two wordings, plus one with the articles shuffled. It is never
  asked to reconsider (LLM judges flip under pushback; Jagged Judges 2026).
* Only events that happened after the entry close count.
* Matched in ≥ 2 passes: exit. Partial or matched in ≥ 2 passes: halve, once per lot.
* A new material hard-number event in the position's direction in ≥ 2 passes: once per lot, up to
  1.5× the entry weight (≤ 10% of NAV, within the gross cap).

**Book across weeks** (overlapping cohorts; Jegadeesh & Titman 1993).
* Carried lots keep their weight. The caps rebalance a lot only if they move it by more than 25%
  (no-trade band; Gârleanu & Pedersen).
* Re-selected names:
  * same side, new event: H extends to max(remaining, new H), at max(old, new) weight;
  * same story: not renewed;
  * opposite view: the lot closes and the new view opens.
* Capacity: at most 10 a side. Carried names are ranked by |w| × the share of H left, new ones by
  |w| − 10 bp.
* Then the champion's caps apply: sector net ≤ 30%, dollar net ≤ 10% of stock gross, gross including
  SPY ≤ 1.8.
* SPY re-hedges to zero beta on cohort days, and on other trading days with trades when
  |net beta| > 10% of gross.

**Scoring C10.**
* A self-financing book on $100,000, marked at official total-return closes. Cash earns the 3-month
  bill, and every trade, the hedge included, costs 5 bp per side.
* Weekly return = NAV ratio over the same Thursday-close boundaries as every book; excess return =
  that minus the bill.
* Daily returns are frozen when first seen, and every LLM output is logged, so the book can be
  rebuilt from its inputs to the cent.

**Multiple testing (applies to every challenger from now on).**
* Every challenger ever scored counts: C1–C10, so m = 10, at α = 0.05/10 each.
* Boundaries are O'Brien–Fleming, K = 4, computed in `score.py` by integrating the joint normal law
  of the look statistics: **5.665 / 4.006 / 3.271 / 2.832** at 13 / 26 / 39 / 52 weeks.
* The integration must first reproduce the champion's 4.049 / 2.863 / 2.337 / 2.024 at α = 0.05.
* The C1–C7 boundaries tighten from α/7, which is allowed: no challenger has been scored, so nothing
  has been rejected.
* Future challengers get a pre-registered online-Bonferroni share. A threshold never loosens.

**Mechanical gates, checked daily (`lifecycle/checks.json`), before C10 may ever trade.**
* Daily lot P&L + hedge P&L + cash income − costs reconcile to the NAV change, to the cent.
* No limit is broken on a trading day.
* No duplicate or orphan lots.
* Every stop or target has its trigger.
* No news after a session's close is used at that close.
* A second rebuild from the logged inputs reproduces the NAV exactly, and no recorded day changes on
  rebuild.
* *Degenerate replay* (`lifecycle.py replay`): with H = the week, no barriers, no news and the book's
  own weights, the engine must reproduce the weekly book's gross return within 1 bp.

**What would make C10 the traded fund.** Running C10 only as a shadow tests the mechanics, not the
idea. Trading it is Protocol 7, a new hypothesis with its own clock, not a promotion:
* The amendment is committed before Protocol 7's first decision and states its reason and that no
  Protocol 6 performance was used to choose it.
* Every Protocol 6 week stays in the record.
* The weekly champion keeps running as a shadow (`c0_weekly`), with a pre-registered paired test on
  the weekly difference (NW t, lag ≥ the longest horizon in weeks).
* Any headline claim must survive α/k over the k champion protocols run (or a deflated Sharpe ratio;
  Bailey & López de Prado 2014).

## Protocol 7 (pre-registered 2026-10-09, before its first decision on 2026-10-14): the lifecycle book trades

**What changes, and why.** From the session of **2026-10-15**, the account is traded by the lifecycle book of
Amendment 7 (C10) instead of the weekly book. The reason is the owner's design decision (2026-10-03) that each
trade has its own life: a horizon from its thesis, an exit when news ends the thesis, and volatility-scaled
stop and target. It was **not chosen on performance**: no Protocol 6 week had been scored when this was
registered, and the C10 shadow had run for one session.

This is a new hypothesis with its own clock, not a promotion.

**The rules are Amendment 7's, unchanged.** Event-type horizon table, stop −2.0·W and target +3.0·W on hedged
residual returns, three-pass kill-condition news checks, overlapping cohorts with the champion's caps,
SPY hedge. Two things change because the book now trades:
* **Decided live, before the close.** Each session:
  * the news checks run on articles published up to **T − 20 min**;
  * the barriers are checked on live prices at **T − 3 min** (the provisional return to that moment);
  * the decision is logged in `lifecycle/live/<day>.json` (prices, timestamps, every action, the target
    book);
  * the account is traded to it with the pre-close send (`fund/broker.py`).
  Entry volatility for a new lot uses history to the previous close.
* **The record applies the decisions as taken.** The nightly rebuild marks every lot at the official close
  and applies that day's logged actions; it does not recompute them on the close. A session with no live run
  holds everything.

**Transition.** The champion starts from the C10 shadow's lots as they stand at the 2026-10-14 close. On
2026-10-15 the account moves from the Protocol 6 holdings to that book plus the new cohort (as-of
2026-10-14). From that session:
* the weekly execution (`execute.py trade`) and the Amendment 5 daily review stop trading;
* the kill-condition checks replace the review;
* reconciliation, risk halts, the IC memo and every shadow desk continue.

**Scoring and the gate.**
* **The fund's weekly return is the lifecycle book's NAV return** over the usual Thursday-close weeks
  (Amendment 7 accounting).
* **The gate's clock restarts** at the first Protocol 7 week (as-of 2026-10-14), with the same O'Brien–
  Fleming looks at 13/26/39/52 weeks and the same operations rules.
* **The Protocol 6 record stays.** Its weeks (2026-09-30, 2026-10-07) stay in `weekly_books.csv`.
* **Headline claims.** Any claim across both protocols must survive α/2 (two champion protocols run), or a
  deflated Sharpe ratio over the protocols run.
* **`c0_weekly`: the weekly book it replaces.** It is the fund book of each week held Thursday to Thursday,
  scored as a challenger.
* **The pre-registered paired test** is d_w = r_fund − r_c0_weekly, reported weekly, with its NW t at lag
  max(⌊4(T/100)^{2/9}⌋, 4).
* **Reverting.** If c0_weekly beats the fund at a look by its challenger boundary, the weekly book takes
  the account back, by the promotion rule.
* **Multiple testing.** c0_weekly is a new test: the challenger family is now C0–C10 (m = 11) at
  α = 0.05/11, with boundaries **5.724 / 4.048 / 3.305 / 2.862** (computed in `score.py`, which first
  reproduces the champion's 4.049 / 2.863 / 2.337 / 2.024).

**Mechanical gates kept every day.** All of Amendment 7's checks: reconciliation to the cent, limits, no
duplicate lots, triggers, no look-ahead (news after the decision time is never used), and determinism.
In addition, every order is reconciled against the official close; the operations rule is unchanged (≥ 90%
of weeks fully filled, median slippage ≤ 10 bp).

**Before go-live.** Unchanged from Amendment 3, plus one condition: Alpaca must confirm whether a live account
supports market-on-close orders. Until then the pre-close send stays the method.
