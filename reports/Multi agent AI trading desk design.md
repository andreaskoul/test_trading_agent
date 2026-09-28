# Freeze a leaner champion, race the challengers

The strongest design the evidence supports doesn't have more LLM personas. It has fewer, narrower ones. LLMs do short, checkable reading jobs on deduplicated text. A deterministic statistical and risk layer sizes and hedges the positions. Independent samples are aggregated rather than debated. A frozen champion book is judged forward against challenger books that are pre-registered and run in shadow. Protocol 6 is already closer to that than most published frameworks: the PM desk is deterministic, the red team can only filter, the evaluation is forward-only, and the ablation books are logged. So the fixes are not structural. Three problems need fixing before the first live week (as-of 2026-09-30), because each one undermines the evaluation the protocol depends on.

**1. The fund's returns aren't clean of the exposures they'll be judged on.** Analyst scores load +0.33 on last week's return. The quant benchmark loads the other way, because the ridge is about −0.64 correlated with last week's return. So "fund − quant" is largely a bet on the weekly reversal factor. On top of that, a 60-day beta hedge is very noisy in today's concentrated market.

**2. The go-live gate has little power.** My simulation gives it about 18% power if the true annual Sharpe is 1, and about 8% at 0.5. So its most likely 52-week verdict, "NO-GO: redesign or retire", will say little either way.

**3. Nothing pins the LLM provider, and nothing says what happens if `deepseek-v4.1-flash` is retired mid-window.** Under the current rules that would restart the clock.

For a large-cap weekly LLM-news book, a realistic gross Sharpe is well under 1. Costs can reach about 10% of NAV a year if the book turns over fully each week. Year one can catch bugs and catastrophic failure, but it can't confirm alpha. The main job is to set things up now so that the year's data can still teach something.

## The literature rewards narrow reading tasks, not bigger desks

The standard multi-agent template splits analysts by data type, runs a bull/bear debate, then passes through a trader, a risk team and a manager. It copies how human desks are organised; no evidence produced it. TradingAgents, the most-cited example, reports Sharpe ratios of 5.6–8.2 on three tickers over three months in 2024. It has no component ablation and no significance tests, and its authors attribute the Sharpe ratios to a calm market ([Xiao et al.](https://arxiv.org/html/2412.20138)). The best-controlled ablation so far comes from "Toward Expert Investment Teams". It covers TOPIX 100 over 27 months, entirely after the model's training cutoff, with 10 bp costs. **Giving agents fine-grained, precomputed features beat giving them raw data by a median Sharpe of +0.19 to +0.26 (p<0.0001). Removing the quantitative, qualitative or macro agents often *improved* performance. The news agent's effect was inconsistent.** Standalone agent returns were modest; the value came from low correlation with the index when blended ([arXiv 2602.23330](https://arxiv.org/html/2602.23330v1)). The lesson: what each call is asked to compute matters more than how many personas there are.

Debate has a worse record than its popularity suggests. Across standard benchmarks, multi-agent debate often lost to plain majority voting at the same compute. More agents flipped from right to wrong than from wrong to right, and mixed-strength teams dragged strong models down by up to 8 points ([arXiv 2509.05396](https://arxiv.org/html/2509.05396)). Initial accuracy and team size explain most of final accuracy. Weaker models overturn a wrong majority only 3.6% of the time ([arXiv 2511.07784](https://arxiv.org/pdf/2511.07784)). In finance the direction is consistent: LLM strategies are "excessively conservative in bull markets" ([FINSABER](https://arxiv.org/html/2505.07078)), and risk-averse debate portfolios lagged the 2024 tech rally ([AlphaAgents](https://arxiv.org/html/2508.11152v1)). The reason is structural. A pipeline where every stage can only shrink a position drifts toward flat, and conformity then removes the disagreement that review was supposed to add.

The better-supported way to combine LLM judgements is aggregation. **A 12-model crowd matched 925 human forecasters on Metaculus: Brier 0.20 vs 0.19, difference not significant. Individual models were overconfident and biased toward "yes".** Showing the models an independent anchor improved Brier scores by 17–28% ([Schoenegger et al., Science Advances](https://www.science.org/doi/10.1126/sciadv.adp1528)). Self-consistency, meaning many samples and a majority vote, improves reasoning accuracy ([Wang et al.](https://arxiv.org/abs/2203.11171)). No finance study measures the calibration of LLM ensembles against debate, so this is transferred evidence, not proven for this domain.

Memory and reflection sound powerful but rest on contaminated tests. FinMem reported a Sharpe of 2.68. Re-tested over 20 years on 100+ symbols, it fell to 0.40–0.93, often below passive benchmarks ([FINSABER](https://arxiv.org/html/2505.07078)). When five well-known agent frameworks moved from a pre-cutoff window to a post-cutoff window with similar market returns, their Sharpe ratios fell by 51–62% ([Profit Mirage](https://arxiv.org/html/2510.07920v1)). A live benchmark that enforces point-in-time data found agents "clear the defensive baselines but not the index cleanly". It also found that independent judges rated only about 0.27 of allocations as matching the agents' own narratives ([CLQT](https://arxiv.org/html/2606.29771)). An LLM's written rationale is therefore not a reliable explanation of its trade.

Credible institutions use LLMs this way too: to produce checkable artefacts that conventional validation then gates. Man Group's AlphaGPT writes signals as code, and "several dozen" have been approved for live trading. The PM says it is not "autopilot" and has "a lot of checkpoints", and the team reports "hallucinations and inconsistent outputs" ([Hedgeweek](https://www.hedgeweek.com/man-group-deploys-agentic-ai-for-quant-signal-discovery/)). There is no audited record for any autonomous multi-persona LLM fund.

Put together, the robust architecture is a funnel:

1. Cheap rule-based screening.
2. Narrow LLM reading tasks on short, deduplicated, time-filtered text: event extraction, materiality, novelty, direction.
3. N independent samples aggregated by median.
4. A critic that can only filter, preferably a different and stronger model.
5. A deterministic layer that combines the text score with price features, sizes by risk, and hedges.
6. Every stage logged as its own book, so its value added can be measured.

## Large-cap news alpha is small, fast and decaying

The cleanest out-of-sample study, Lopez-Lira & Tang (now in the JFE), used headlines published after GPT-4's training cutoff. It found a tradable drift Sharpe of 2.97 with three properties:

- **Most of it on the short side:** 26 bp of the 34 bp daily spread.
- **Concentrated in small caps.**
- **Gone after day 2.**

The strategy was unprofitable at 20 bp round-trip costs ([arXiv 2304.07619](https://arxiv.org/pdf/2304.07619v6)). Its Sharpe fell year by year: **6.54 in 2021Q4, 3.68 in 2022, 2.33 in 2023 and 1.22 in January–May 2024**, which the authors read as markets becoming more efficient as LLM use spreads ([same](https://arxiv.org/abs/2304.07619)). The pre-LLM benchmark tells the same story about size. In SESTM, the value-weighted Sharpe was 1.33 against 4.29 equal-weighted. Large stocks absorbed news in one day (11 bp); small stocks took three days (52 bp) ([Ke, Kelly & Xiu](https://www.nber.org/system/files/working_papers/w26186/revisions/w26186.rev1.pdf)). For an S&P 500 book, the relevant prior is a large-cap, value-weighted edge well below the headline numbers. A book that trades Thursday close on Wednesday-close information also misses the one day in which most large-cap drift happens.

Three strands of evidence still leave room for a weekly design, and they happen to describe what the narrative pipeline does:

- **Aggregated news predicts slowly.** Daily news predicts returns for only 1–2 days, but *weekly* aggregated news predicts for a quarter, and bad news is incorporated with "a long-delayed reaction" ([Heston & Sinha](https://ssrn.com/abstract=2311310)).
- **Complex news is underpriced.** Markets price transparent news efficiently but underreact to complex news that needs synthesis ([Lopez-Lira & Tang, JFE abstract](https://www.sciencedirect.com/science/article/abs/pii/S0304405X26001066)).
- **News moves persist; no-news moves reverse.** Ten-day reversals are 38% weaker on news days ([Tetlock 2010](https://business.columbia.edu/sites/default/files-efs/pubfiles/4150/Tetlock%2004%2010%20News%20and%20Asymmetric%20Information-1.pdf)), and large moves without news tend to reverse ([Chan 2003](https://ideas.repec.org/a/eee/jfinec/v70y2003i2p223-260.html)). Both effects are strongest in small, illiquid names.

The economically coherent weekly bet is therefore not "this headline is good". It is "this story is gaining weight and the market hasn't finished synthesising it", together with "this move had no news behind it".

On data, the key distinction is between two problems. Memorisation of outcomes is real and not fixed by prompting: models reconstruct masked entities and dates, and "post-cutoff, we observe no recall" ([Lopez-Lira, Tang & Zhu](https://arxiv.org/abs/2504.14765)). A pure no-news "recall" signal predicts returns with t=3.53 in high-lookahead observations ([Gao, Jiang & Yan](https://arxiv.org/html/2512.23847)). This is why Protocol 6's forward-only evaluation is right and why no historical backtest of DeepSeek on pre-2026 news can be trusted. DeepSeek has no published training cutoff ([GitHub issue #615](https://github.com/deepseek-ai/DeepSeek-R1/issues/615)).

The second problem survives live trading: *distraction*. Anonymising firm names in headlines *raised* returns, more so for large firms, because the model's general knowledge of the firm gets in the way of reading the news ([Glasserman & Lin](https://arxiv.org/abs/2309.17322)). Long contexts also degrade in the middle: performance follows a U-shape in where relevant information sits in the prompt ([Liu et al., TACL](https://aclanthology.org/2024.tacl-1.9/)). Finally, vendors revise articles after publication. Alpaca/Benzinga, for example, returns both `created_at` and `updated_at` ([Alpaca docs](https://docs.alpaca.markets/us/docs/historical-news-data)). So a forward archive is point-in-time only if it stores what it saw, and when it saw it.

On the choice of model, the evidence is thin and not flattering to the one in use. Zero-shot skill scales with model size: GPT-4 drift Sharpe 2.97 against 1.66 for GPT-3.5 ([arXiv 2304.07619](https://arxiv.org/pdf/2304.07619v6)). On WSJ-based market prediction, DeepSeek underperformed ChatGPT ([arXiv 2502.10008](https://arxiv.org/abs/2502.10008)). No study covers a 2026 "flash" model on this task.

## Institutional plumbing: hedge betas carefully, trade the close, count your trials

The textbook conversion from a score to a weight follows Grinold's rule: alpha = IC × residual volatility × standardised score. With a diagonal risk model, that makes the weight proportional to the z-score divided by residual volatility, with extremes trimmed ([Grinold & Kahn notes](https://people.brandeis.edu/~yanzp/Study%20Notes/Active%20Portfolio%20Management.pdf)). "score × confidence" without volatility scaling overweights volatile names, and those are also the names with the largest news reactions. Confidence belongs as shrinkage of the score, not as a separate multiplier.

Beta estimation matters more than it looks. Welch's slope-winsorised daily beta over 252 days beats OLS by 5–10% and Blume-adjusted beta by 30–40% out of sample ([Welch 2022](https://cfr.ivo-welch.org/forthcoming/papers/welch2022simply.pdf)). The research notes calculate a standard error of about 0.20 for a 60-day large-cap beta, against about 0.10 at 252 days. The current market makes this concrete. **In the 2026-09-23 screen, the median 60-day beta to SPY across S&P 500 members is 0.31, with an interquartile range of −0.10 to 1.01.** Recomputing eight names myself confirms the prices are clean, but the estimates are unstable:

| name | 60-day beta | 252-day beta |
|---|---:|---:|
| AAPL | 0.13 | 0.67 |
| MSFT | 1.66 | 0.95 |
| XOM | −1.08 | −0.57 |

This is a concentrated market in which SPY follows a handful of mega-caps. A hedge sized off 60-day betas mostly trades on estimation noise. It also leaves the book exposed to the gap between the equal-weighted and cap-weighted market, which a SPY hedge doesn't neutralise.

Execution in the closing auction is the right choice. AQR's live data put large-cap impact at about 9 bp at institutional size ([Frazzini, Israel & Moskowitz](https://spinup-000d1a-wp-offload-media.s3.amazonaws.com/faculty/wp-content/uploads/sites/3/2021/08/Trading-Cost.pdf)). NYSE finds no persistent impact for orders up to roughly 0.5–1.2% of closing-auction volume ([NYSE](https://www.nyse.com/data-insights/closing-auction-immediate-market-impact-price-drift-and-transaction-cost-of-trading)). Alpaca rejects `cls` orders submitted between 15:50 and 19:00 ET ([Alpaca orders](https://docs.alpaca.markets/us/docs/orders-at-alpaca)), and easy-to-borrow shorts carry no fee there ([Alpaca margin](https://docs.alpaca.markets/us/docs/margin-and-short-selling)).

The binding cost is turnover, not execution. By my calculation, fully replacing a book with gross exposure of 2× NAV every week at 5 bp per side costs about 20 bp a week, roughly 10% of NAV a year.

On governance, SR 11-7 treats an LLM scorer as a model: "qualitative inputs with quantitative outputs" are in scope. It requires documentation that an outsider could follow, "effective challenge", ongoing monitoring and outcomes analysis ([Federal Reserve SR 11-7](https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm)).

On evaluation, the arithmetic is unforgiving. The number of variants tried must be recorded so reported Sharpe ratios can be deflated ([Bailey & López de Prado](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)). A newly found signal should clear t≈3, not 2 ([Harvey, Liu & Zhu](https://academic.oup.com/rfs/article/29/1/5/1843824)). By the research notes' calculation, confirming a true annual Sharpe of 1.0 from weekly returns at 95% takes about 143 weeks, and a Sharpe of 0.5 takes about 565 weeks.

## Protocol 6, desk by desk: what survives the evidence

"Strength" in the table below means the strength of the evidence behind the verdict. It is not a claim about how much the change is worth.

| desk / component | verdict | reason | strength |
|---|---|---|---|
| 0. Finnhub daily archive on HF | **keep, harden** | A forward archive is the right point-in-time base. Add `ingested_at`, a content hash and first-seen versions; never overwrite revisions | moderate (engineering + vendor docs) |
| 1. Price signals, ridge, sector | **keep** as screen and benchmark only | Amendment 2 was right: ridge alpha t is 0.38 over 2016–26, so it is mostly beta | strong (own out-of-sample) |
| 1. 60-day OLS beta vs SPY | **change** | SE ≈0.2; unstable in the 2026 regime (above); drives the hedge | strong (Welch) |
| 1. Attention z, earnings flag | **keep** | Cheap; attention fits the novelty and staleness literature; the earnings flag is a legitimate price fact | moderate |
| 2. Ideation: one LLM call over 500 alphabetical lines | **change ordering** | Lost-in-the-middle gives mid-alphabet tickers a systematic handicap | moderate (general LLM evidence, not finance) |
| 2. Rule slots, core 20 | **keep** | Rules keep research time from depending on one sample. Note that the core 20 are the most efficiently priced names | weak |
| 3. Narrative pipeline, structure first | **keep** | This is where the evidence points: weekly aggregation, complex-news synthesis, staleness and dedup. It is the fund's only plausible edge | moderate (indirect) |
| 3. Wall-clock cutoff (`cutoff = now`) | **change** | Makes a run impossible to replay and lets run-time jitter change the inputs | moderate (engineering) |
| 4. Analysts: one memo, temp 0, one sample | **keep in champion; ensemble in shadow** | Aggregation beats single samples elsewhere, but not yet shown in finance | moderate |
| 4. Price facts inside the prompt | **keep in champion; text-only in shadow** | Own dry runs show anchoring (0.54 with the ridge when shown; +0.33 with last week's return now). Distraction evidence favours text-only, anonymised input | moderate (own data + Glasserman & Lin) |
| 5. Red team: uphold or weaken with a named flaw | **keep** | Matches the literature's fixes: independent first view, no consensus, filter not debate. Measured by fund − analyst | moderate |
| 5. Same model as critic | **shadow a different-family critic** | Critic strength predicts whether wrong views get corrected | weak–moderate |
| 6. Weight = score × conf / 20, no vol scaling | **keep in champion; vol-scaled in shadow** | Grinold favours z/σ with confidence as shrinkage; untested on LLM scores | moderate |
| 6. Dollar net ≤ 20% of gross | **tighten to 10%** | At gross 2 that is 0.4 NAV of net dollars riding on a noisy beta | moderate (convention) |
| 6. Sector net ≤ 30% NAV; flat if no views | **keep** | ≈15% of gross at full size, in line with convention; no forced fill | moderate |
| 10. MOC Thursday, reconciliation, halts | **keep** | The auction is the right venue. Halts at 10% drawdown / 5% week are about 2.5× monthly and weekly volatility (own estimate), so expect occasional false halts | strong (execution) |
| 9. Costs, excess over cash, random/analyst/core20 books | **keep** | The random book is a valuable placebo; the analyst book prices the red team | strong |
| 9. Primary test fund − quant | **re-specify** | Confounded by reversal (below) | moderate (own data) |
| 9. Gate on raw excess return | **re-specify** | Mixes in residual beta and style; low power (below) | strong (arithmetic) |
| 7. IC memo | **keep as record only** | CLQT: narratives often don't match trades | moderate |
| Model / provider identity | **pin and plan succession** | Any model change restarts the clock; retirement within 52 weeks is plausible | moderate (governance) |

### The reversal confound is the most important finding

The quant benchmark is built on the ridge. In the 2026-09-23 screen, the ridge correlates +0.66 with the rev1w z-score and −0.64 with last week's return, so it is essentially a short-term reversal book. The analysts, blind to the ridge but shown returns, scored +0.33 with last week's return and −0.31 with the ridge in dry run 4. They lean toward short-term continuation.

That makes **fund − quant roughly equal to news skill plus about twice the negative of the weekly reversal factor**. In any stretch where large-cap weekly reversal pays, the primary test and the fund − quant STOP rule will fire whether or not the news reading has skill. The reverse is also true: a quarter where reversal fails will flatter the fund.

Amendment 2's attribution regresses on rev1w, but it is a secondary result and only reported from 8 weeks. The gate uses raw excess return, which also carries whatever beta the noisy hedge leaves behind, plus the gap between the equal-weighted market and SPY.

Neither correlation is established yet: each comes from one week of about 36–45 names. Whether the +0.33 reflects legitimate "news moves persist" (Chan, Tetlock) or plain anchoring is exactly what the text-only shadow book can separate.

### Timing wastes the one day where large-cap news drift lives

The decision uses Wednesday-close prices and news up to the run, but positions are set at Thursday's close. The strongest large-cap evidence says text-based signals are absorbed in about one day. So the champion is effectively betting only on the slow component: the Heston–Sinha weekly-aggregation and complex-news channel. That is a defensible bet, but it should be a measured one. A shadow book priced from Thursday's open (tradable through Alpaca's OPG orders) and a notional Wednesday-close book would measure the delay cost directly at no LLM cost.

### What must not happen: a silent model change

OpenRouter's model slug says nothing about which backend provider served a given call, and the pipeline logs only `resp["model"]`. Provider switches or silent model updates can change scores without any code change. At temperature 0, hosted APIs are still not guaranteed deterministic (research notes, engineering inference). Protocol 6 says a model change restarts the clock, but gives no rule for what happens if the model is deprecated. Over a 52–104-week window that is a real risk, not an edge case.

## A ranked plan: seven things to pre-register, the rest in shadow

The rule for sorting changes:

- **A (pre-register now):** anything that changes a position or a verdict, and that the evidence says is a validity threat. It is free before 2026-09-30 and restarts the clock after.
- **B (operational):** anything that only improves logging, monitoring or recoverability. It can go in the CHANGELOG at any time.
- **C (shadow challenger):** anything that is a better idea but untested. It becomes a pre-registered shadow book, computed each week from the same inputs, scored with the same costs, and never traded.

Registering challengers *now* matters. A challenger's shadow record from week 1 counts as its own clean forward record, which is the only way a promotion inside the first year could be justified.

| rank | change | class | evidence | why it ranks here |
|---:|---|:-:|---|---|
| 1 | Gate GO requires both the raw excess-return t **and** the t of the intercept after regressing on SPY and the rev1w factor to cross the O'Brien–Fleming boundary. STOP on fund − quant uses the rev1w-adjusted difference. Add the weekly analyst-score slope, controlling for ret_1w, beta and sector, as the high-power secondary. Reconcile the 52-week NO-GO with the base protocol's 104-week decision: NO-GO at 52 means "no real money", not "retire" | A | strong (arithmetic) + own data | Without it, the verdict can reflect beta or reversal rather than news skill |
| 2 | Beta: 252-day Welch slope-winsorised, shrunk one-third toward 1 (or the sector mean). Dollar net ≤ 10% of gross. Log ex-ante and realised book beta weekly with a ±0.15 alert band | A | strong | The hedge currently rests on noise in a concentrated market |
| 3 | Model continuity: pin the OpenRouter provider with fallbacks off; log provider, model string and raw output; re-score a frozen canary set of about 20 past inputs every week. Pre-name a successor model and a rule: pool pre- and post-switch weeks for the gate only if canary score agreement ≥ a set threshold, otherwise restart. Degraded-run rule: if more than 25% of memos fail, hold last week's book instead of trading a partial one | A | moderate (SR 11-7, engineering) | The single most likely way to lose the year's record |
| 4 | Fix the news cutoff to a deterministic timestamp (e.g. Wednesday 22:00 UTC) and save the exact prompt text and cutoff for every call | A (cutoff) / B (saving) | moderate | Makes every decision replayable and auditable |
| 5 | Ideation input sorted by attention shock (or by a date-seeded shuffle), not alphabetically | A | moderate | Removes a systematic coverage bias at zero cost |
| 6 | Register challengers C1–C5 below, the promotion rule (only at a look, challenger − champion NW t ≥ the same boundary; a promoted book's clock is its shadow start date) and the running trial count for deflating Sharpe ratios | A | strong (governance) | Makes later improvement possible without p-hacking |
| 7 | Halt semantics: a resumed halt continues the same clock; halted weeks count as flat | A | weak | Removes an ambiguity that would otherwise be settled after the fact |
| — | Archive: `ingested_at`, content hash, append-only revisions. Weekly monitors for score dispersion, share of zero scores, coverage, turnover, PSI of score distribution, realised factor exposures. Slippage against the official closing print. Incident runbook | B | moderate | Needed to trust the data, but changes no decision |
| C1 | **Timing books:** the same fund weights priced from Thursday's open and from Wednesday's close (notional) | C | strong (decay evidence) | No LLM cost; measures the size of the day-1 loss |
| C2 | **Self-consistency:** 5 samples at moderate temperature, median score, with dispersion used as confidence | C | moderate | Best-supported way to combine LLM outputs |
| C3 | **Text-only, anonymised analyst:** no price facts, names and tickers masked; its score is combined with ret_1w in a statistical layer | C | moderate (distraction + own anchoring data) | Separates news reading from price chasing |
| C4 | **Grinold sizing plus no-trade band:** weight ∝ score·conf/σ_resid; keep a position unless its score changes sign | C | moderate | Targets volatility concentration and the roughly 10%/yr cost ceiling |
| C5 | **News-conditioned reversal:** short-term reversal on covered names with score 0 and no active event; the champion's views elsewhere | C | moderate (Chan, Tetlock, LLT) | Uses the LLM as a classifier, where its evidence is strongest |
| C6 | A different-family, stronger red-team model | C | weak–moderate | Only if the budget allows; five challengers already strain the deflation budget |

Earnings handling (halving or excluding names that report in the holding week) is defensible practice. None of the notes quantifies it for S&P 500 names, though, so it belongs in the shadow set as a sixth variant only if the trial budget allows.

Some changes should be left alone. Don't add more analyst personas, a bull/bear debate or verbal reflection memory. None of them has post-cutoff ablation evidence, and the debate literature predicts they would make the book more cautious, not more skilful.

## What a year of weekly data can and cannot tell you

My simulation assumes normal weekly returns, the pre-registered O'Brien–Fleming boundaries, and a first-crossing rule:

| true annual Sharpe of excess return | P(GO by 52 weeks) | P(own-return STOP ≤ −2) |
|---:|---:|---:|
| 0 | 3% | 7% |
| 0.5 | 8% | 4% |
| 1.0 | 18% | 2% |
| 1.5 | 32% | 1% |
| 2.0 | 52% | 0.3% |

The STOP column counts only one of the three STOP statistics. With all three, a zero-edge fund is stopped more often, and a reversal-driven fund − quant stop becomes plausible even with skill.

The literature puts a large-cap, weekly, net-of-cost LLM news book at roughly 0–0.5 Sharpe, with anything above 1 unlikely. That prior is my synthesis, not a measured number. It rests on:

- the fall in Lopez-Lira & Tang's Sharpe to 1.22 in a small-cap-dominated daily sample;
- the one-third value-weighted haircut in SESTM;
- one-day large-cap absorption;
- the modest standalone results of the one clean multi-agent test.

Under that prior, the modal outcome at 52 weeks is NO-GO. That is a statement about the test's power, not proof of no edge. The go-live gate is honest in that it rarely gives a false GO, but it can't tell a mediocre real edge from none.

There is also a scale problem. By my estimate, a 20-name book at gross 2 carries about 2% weekly idiosyncratic volatility, roughly 14% a year. A net Sharpe of 0.5 therefore needs about 7% a year net. At full weekly turnover that means about 17% gross alpha, which is why turnover (C4) could matter more than any prompt.

Several things can't be known yet:

- the pipeline's IC and its decay curve;
- whether narrative structure adds anything over headline scoring (no study compares the two);
- whether DeepSeek v4.1 flash is capable enough for complex-news synthesis;
- whether the 2026 concentration regime persists;
- how often the provider will change under the pipeline.

Dry run 4's correlations are single-week observations. Thirteen weeks can reliably show only operational failures: missed deadlines, unfilled orders, hedge drift, score collapse toward zero. Twenty-six weeks can start to show stage value-adds (fund vs analyst vs random) as directions, not verdicts. The highest-power evidence the year will produce is the weekly cross-sectional score slope and the timing and challenger contrasts. The fund's P&L won't be it.

## Conclusion

The literature's headline results for multi-agent LLM desks mostly come from contaminated, short, cost-free tests. What survives careful testing favours a desk that looks less like a hedge fund org chart and more like a measurement instrument: narrow LLM reading tasks, aggregation instead of debate, deterministic sizing, and many logged counterfactual books. Protocol 6 already has that shape. Its weak points sit where it meets statistics. The benchmark it is judged against carries the opposite style bet to its analysts. The hedge rests on unstable betas. The model identity is unpinned. And the go-live test can't tell a modest edge from none within a year.

In practice, the next two days matter more than any prompt tuning. Pre-registering the evaluation fix, the beta estimator, the model-continuity rule and a small set of shadow challengers turns year one from a probable "NO-GO, cause unknown" into a record that says where any edge came from, if there is one: news synthesis, timing, sizing or style. That record is also what would justify a Protocol 7. After 2026-09-30, the only way to change the champion is to restart the clock.
