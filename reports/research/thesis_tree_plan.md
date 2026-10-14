# The Thesis Tree: firm theses on a sector and supply-chain graph, and the lab that decides Protocol 8

## Context

**Where we are.** The desk review of 2026-10-14 (PR #85) found that the traded design has close to zero edge by
construction. Three reasons:
* it reads single headlines days late, in the most efficiently priced names;
* nothing converts the LLM score into a forecast;
* the risk layer can't see sector, theme or supply-chain structure.

The in-house drift study agrees: a news gap's direction earns nothing out to 20 sessions and reverses at 30–60.

**What the owner wants** (2026-10-14):
* Stop chasing news at short notice. Build a **thesis per firm: its image between quarterly updates**, formed
  from the accumulation of its own events, its competitors' events, its sector's dynamics (including geopolitics
  and within-sector correlation), and its place in the **production funnel**: raw materials → production tools
  → assembly → sellers → consumers.
* **Horizons are not fixed**: a thesis lives as long as it holds.
* The **reassessment on new company or sector news stays**.
* **Instrument choices** (SPY, sector ETFs, shorts) are a trader's strategic decisions, not testable ideas.
* Free data only.
* Test the S&P 500 and the S&P 400.
* Switch Protocol 8 as soon as its tests pass. Shadow P&L is never the evidence (the April 2027 rule).

This plan was stress-tested (§1) against the literature before being written. Several priors were reversed.

---

## 1. Stress test: the questions a demanding PM asks, and what changed

| # | the challenge | what the evidence says | what changed in the plan |
|---|---|---|---|
| 1 | *"What is our edge over 20–40 sell-side analysts per S&P 500 name?"* | Reading a firm's own disclosures is the most crowded job in finance. AI already explains ~17–20% of *same-day* earnings moves from the release text (Koijen & Levy 2026, real-time, out of sample): the market moves on it at once. Analysts, though, incorporate **news about linked firms sluggishly**, more so for complex and indirect links (Ali & Hirshleifer 2020: connected-firm momentum, 1.68%/month, t = 9.7, subsumes industry, customer and technology momentum). | **The edge hypothesis sits in the edges, not the nodes.** The prior for the own-firm rung is ≈ 0; the hypothesis is cross-firm and indirect synthesis plus breadth and discipline. The thesis card is the container; the claim to test is that the *links* add IC (R4 ladder). |
| 2 | *"The published cross-firm effects: do they survive in large caps today?"* | **Mostly not as published.** Customer momentum (1.55%/month, 1981–2004) is **not significant value-weighted after 2004**, and is largely a large-to-small lead-lag: it shrinks 2–4× when customer and supplier are of similar size (Pinchuk). Anomalies lose ~58% after publication (McLean & Pontiff 2016). | S&P 500-internal links are expected weak. The **test structure follows size asymmetry**: S&P 500 customers → S&P 400 suppliers is a pre-specified arm. Links enter P8 only on their holdout result, by universe. |
| 3 | *"Peers that report early: do we follow them?"* | **The opposite.** The market *over*-reacts to intra-industry transfers: late announcers' sympathy moves are negatively related to their own later announcement reaction (Thomas & Zhang 2008, 1973–2005). | Propagation rule rewritten (§4): the tradable signal is the **reversal of an unjustified sympathy move**, judged by whether the early reporter's news actually touches the late firm's drivers. H1 tests that direction. |
| 4 | *"Can an LLM predict surprises at all?"* | Benchmarks show apparent accuracy that is mostly class imbalance: models are biased toward predicting "beat" (FinCall-Surprise, ACL 2026). Kim, Muhn & Nikolaev report ~60% earnings-direction accuracy from statements, but the look-ahead critique applies (Gao, Jiang & Yan). | Never score raw "beat/miss" accuracy. The targets are **centred within season × sector** (beats are the base rate). The aggregation **z-scores evidence cross-sectionally every week**, so a global optimism bias cancels. Placebo items are in every replay. |
| 5 | *"Your ledger: 1,000 LLM reads per firm per quarter. Errors compound."* | Repetition is the danger: the same event re-reported 30 times must count once. | **Novelty is a first-class field**: event-level deduplication (the narrative pipeline's clustering plus 8-K item matching). Evidence weight per *event*, not per article. A 10% audit by a different model family. |
| 6 | *"Power. Three replay seasons is three draws of the macro."* | Cluster-robust errors with 3 clusters are invalid. | Inference uses **season × industry fixed effects, a wild-cluster bootstrap over industry clusters, and randomization inference** (scores permuted within season × industry). One primary statistic per hypothesis, written down before the run; everything else is descriptive. |
| 7 | *"2022–25 has already been read for the technicals study."* | Reusing a holdout across studies is data snooping. | **A sealed holdout: Jan–Sep 2026**, untouched by every study so far (the technicals sample ends 2025-12-31). 2022–25 becomes validation. P8 inclusion is decided on the sealed read, once. |
| 8 | *"Your horizon is a guess."* (owner) | Institutional fundamental alpha decays with a **half-life of about 4 months**, and skilled managers build and unwind gradually (Di Mascio, Lines & Naik). | **No fixed horizon** (§5.5). A position lives while its forecast alpha, decayed at the *measured* rate for its evidence type (H8) and refreshed by new evidence, exceeds its cost hurdle. The own report is a mandatory **checkpoint**, not an exit. |
| 9 | *"Do supply-chain lags show up in prices, or only in fundamentals?"* | Equity prices of upstream firms react fast to downstream capex headlines. The slow part is the **bullwhip in inventories and orders**. | H3 is split: H3a price lead-lag (expected weak); **H3b the inventory signal**: downstream inventory-to-sales builds (XBRL) predict upstream *surprises* 1–2 quarters later. Free, sharp, testable. |
| 10 | *"Geopolitics: alpha or risk?"* | Exposures are heterogeneous and real (Caldara & Iacoviello; Fed note 2025, firm-centred industry exposure); there is no documented post-shock drift. | Geopolitics enters as **risk and as a reassessment trigger**. It is alpha only if H4's drift test passes. Little build effort before then. |
| 11 | *"Fifteen modules, one owner, an infrastructure with weekly incidents."* | Complexity is the largest operational risk. | **Kill-gates before building** (§7). Cheap deterministic tests run first; propagation machinery is built only for edge types that pass. Every new job uses the existing runner, guards and alerts. |
| 12 | *"The uncontaminated data is happening now."* | Q3-2026 reports run from about 20 Oct to 20 Nov. Each week of delay loses about a fifth of a season. | **A forward-season sprint (R5) is week 1's first deliverable**: minimal cards plus ledger, predictions committed before each report. |
| 13 | *"Has the model seen 2026?"* | Its training cutoff is unpublished (DeepSeek). | R0 knowledge-horizon probe first. If the horizon is late, the forward seasons carry the LLM evidence. **LLM components need ≥ 2 seasons (replay + forward, or two forward)**; otherwise P8 ships the deterministic parts and the LLM stays in shadow. |
| 14 | *"Earnings moves are at record size."* | The average S&P 500 move is ~5–6% each way in 2024–25 (BofA). | An **announcement-risk budget** binds in peak weeks (§5.5). It is also the reason the announcement is where a correct thesis pays. |

---

## 2. Tree-level design principles

1. **Every node is a contract**: inputs, an output schema, *its own observable target*, a pre-registered test, a
   cost. A node that fails its test is pruned, and its children fall back to a prior.
2. **LLMs read; statistics decide.** LLMs extract, classify, name the channel and write kill conditions. Sizes
   come from deterministic aggregation. No LLM sees prices.
3. **Typed edges with theory-given signs** (§4). Weights change only through the pre-registered update rule.
4. **Cadence matches information**:
   * structure: yearly or quarterly;
   * events: on arrival;
   * theses: re-underwritten at each report, and reassessed on any trigger;
   * risk: daily.
5. **Point in time everywhere**: filings by acceptance time; XBRL by the first `filed` value per period (no
   restatements); macro by first-release vintage (ALFRED); news by publication and ingestion time; links by
   filing date.
6. **Decorrelated errors**: event-level deduplication, 3 samples where outputs feed sizes, a different-family
   audit of 10%, cross-sectional centring.
7. **Credit assignment by ablation** (R4), and pruning.
8. **Evidence before trading**:
   * deterministic nodes: fit 2012–21, validate 2022–25, **sealed test Jan–Sep 2026**;
   * LLM nodes: post-horizon replay plus forward seasons;
   * shadow runs test mechanics only.

---

## 3. The process tree

```
T0  OBJECTIVE  risk-adjusted residual return of the thesis book (IR after hedges); S&P 500 = yardstick only
│
├─ T1  INFORMATION (point in time, free)
│   I1 prices (Alpaca SIP, yfinance)   I2 filings 10-K/10-Q/8-K + EX-99.1 (EDGAR; edgar-corpus 1993–2020)
│   I3 XBRL fundamentals, first-filed  I4 report timestamps: 8-K item 2.02 acceptance
│   I5 news: Finnhub (1 yr) + own archive  I6 macro: ALFRED vintages, FRED calendar
│   I7 geopolitics: GPR threats/acts, GDELT  I8 free consensus (audited: yfinance, Finnhub, Alpha Vantage)
│
├─ T2  STRUCTURE
│   S1 peers: Hoberg–Phillips TNIC (free, 1989–2023) + own 10-K embedding similarity for 2024–26 (calibrated on overlap)
│   S2 links: named customers / suppliers / competitors from 10-K text (LLM extraction, dated); news co-mention (live)
│   S3 funnel: chain templates × stage S0..S5 (§4)
│   S4 exposures: geographic revenue, input commodities, rates, GPR betas
│   S5 risk model: market + sector + within-sector cluster factors
│
├─ T3  STATE
│   E1 event reader (LLM, 3 samples): event-level, deduplicated → driver, sign, size, hard/soft, novelty, channel
│   E2 propagation (deterministic, typed edges, §4)
│   E3 sector & stage state; macro and geo shocks via S4
│
├─ T4  THESIS
│   Q1 card at each report: drivers, guidance, what the market expects, milestones, kill conditions,
│      the expected resolution path
│   Q2 evidence ledger (append-only, event-level)
│   Q3 thesis score: centred, decayed, weighted per driver
│   Q4 forecast: thesis ⊕ deterministic signals, residualised on past returns, style and sector, shrunk → α, σ, decay rate
│   Q5 REASSESSMENT PROTOCOL (§5.6): triggers → hold / add / trim / exit / re-underwrite
│
├─ T5  PORTFOLIO
│   P1 sizing w ∝ α/σ² under S5; neutral to beta, sector, clusters, style; ex-ante TE target
│   P2 lifecycle: thesis-driven horizon (§5.5), announcement-risk budget
│   P3 instruments and hedges: a trader's policy (§5.4)
│   P4 net market exposure: a standing strategic choice declared in P8
│
├─ T6  EXECUTION   the existing pre-close send (fund/broker.py), daily target
├─ T7  MEASUREMENT & LEARNING   node tests, R4 ladder, gate, pre-registered quarterly empirical-Bayes update (bounded)
└─ T8  RELIABILITY   point-in-time stores, input guards, determinism gates, degraded-node fallbacks
```

**Mapping onto IR ≈ IC × √(effective breadth) × TC − costs:**
* **IC** comes from E2, Q3 and Q4. This is the edge claim.
* **Effective breadth** comes from about 900 names and from S5 neutrality (independent bets, not one theme).
* **TC** comes from Q4 and P1.
* **Costs** come from P2: low turnover.

**The arithmetic.** Fewer, longer bets need a higher IC per bet. IR 0.5 at TC 0.6 with about 300 independent bets
a year needs IC ≈ 0.05 per bet. That is plausible for slow cross-firm information and not plausible for single
headlines.

### Node contracts

| node | done by | the node's own target | test | pass rule (pre-registered) |
|---|---|---|---|---|
| S1 | data + embeddings | own-similarity peers overlap TNIC-3 (2019–23) | historical | Jaccard ≥ 0.5 vs TNIC-3 top-10 |
| S2 links | LLM extraction | precision on a gold set of 200 firm-years | gold | precision ≥ 0.9 |
| S3 funnel | rules + LLM override | stage assignment agreement with the owner's spot check | gold | ≥ 90% |
| S5 risk model | statistics | out-of-sample bias statistic; min-variance vol vs market-only and GICS-only | historical | bias in [0.9, 1.1]; vol lower |
| E1 reader | LLM ×3 | channel, sign and novelty vs gold set (300 events: different-family labels + 60 owner checks) | gold + replay | accuracy ≥ 0.8, κ ≥ 0.6; duplicate rate after dedup ≤ 5% |
| E2/E3 | deterministic | marginal IC on targets | H1–H3 + R4 | Holm-passing increment |
| Q1 card | LLM | numbers match XBRL; kill conditions observable in news | replay | ≥ 95%; ≥ 90% |
| Q3/Q4 | deterministic + statistics | IC on the next-report reaction and on the residual return over the forecast horizon | R3 + sealed test | §6 |
| Q5 reassessment | LLM checks + rules | exits on kill triggers: post-exit residual in the thesis direction ≤ 0 | replay + forward | mean ≤ 0, t-test descriptive |
| P1/P2 | deterministic | TC ≥ 0.5; realised vs ex-ante TE within ±20% | simulation | as stated |

---

## 4. The production funnel and propagation rules

**Stages.**

| stage | what it covers |
|---|---|
| **S0** primary inputs | energy, metals & mining, chemicals, agriculture |
| **S1** tools & capital equipment | industrial machinery, semiconductor equipment, electrical equipment |
| **S2** components & intermediates | chips and memory, auto parts, packaging, electronic components |
| **S3** assembly / OEM / integrators | systems and servers, autos, aerospace, pharma manufacturing, homebuilders |
| **S4** sellers & distribution | distributors, retail, e-commerce, freight and logistics, platforms |
| **S5** end demand | consumers, enterprises, government, seen through ALFRED macro and S4 results |

**Chain templates**, written and committed before any test:
* AI and semiconductors;
* autos and EV;
* aerospace and defence;
* energy;
* homebuilding and construction;
* consumer staples;
* apparel and retail;
* healthcare;
* cloud and software.

Financials sit outside the funnel. Each firm gets a (chain, stage) from its GICS sub-industry, with a frozen yearly
LLM override from its 10-K.

**Propagation rules (E2).**
* **Demand shocks travel upstream**, same sign, with lags that grow by stage. **Supply and cost shocks travel
  downstream.** Disruptions hurt customers (Acemoglu, Akcigit & Kerr; Barrot & Sauvagnat).
* **The bullwhip.** Downstream inventory-to-sales builds → upstream order cuts 1–2 quarters later. Amplitude grows
  upstream. This is H3b, the sharpest funnel claim.
* **Competitors.** E1 labels each event *contagion* (it reveals industry demand: same sign) or *competitive* (it
  shifts share: opposite sign) (Lang & Stulz 1992).
* **Early → late reporters.** The default expectation is *over*-reaction (Thomas & Zhang 2008). The signal is
  the late firm's sympathy move **minus** what the early report implies for the late firm's *own* drivers, as
  judged from its card. A large sympathy move with no driver overlap is expected to reverse at its report.
* **Size asymmetry** (Pinchuk; Hou 2007). Information flows from larger to smaller and less-covered firms. Edge
  weights carry a size-ratio term, fixed in advance.

---

## 5. Sector dynamics, instruments, lifecycle, reassessment

### 5.1 Within-sector correlation (S5)
* Daily residual returns on SPY + 11 sector factors + 1–3 cluster factors per sector (PCA on within-sector
  residuals; k chosen on validation bias statistics), with EWMA covariance.
* **Uses:**
  * neutrality (no hidden theme bets);
  * a propagation fallback (residual correlation) where no economic link exists;
  * the effective number of bets (Meucci), reported daily;
  * the hedge-instrument choice (§5.4).

### 5.2 Sector and stage state (E3)
* Breadth-weighted evidence across a sub-industry or stage, plus macro and geo shocks pushed through S4
  exposures. It enters each member's card as a *sector driver*.
* It becomes a sector *position* only if H3 or H4 pass. In that case it is expressed through the sector ETF
  (§5.4).

### 5.3 Geopolitics (S4 + E1)
* Statistical exposures: sector, stage and firm residual betas to GPR threats/acts, oil, USD and rates.
* LLM channel labels: tariff, export control, sanctions, conflict or supply disruption, energy; with countries and
  products named. They are mapped to firms through 10-K geographic revenue and supplier-country extraction.
* Use: risk limits and reassessment triggers. Alpha only if H4's drift test passes.

### 5.4 Instruments and hedging: a trader's policy, declared and not tested
Owner, 2026-10-14: instrument choice is strategic. Nothing here is fitted or put through §6.

**Principle.** Hold only the risk the thesis is about; hedge every other risk with the cheapest, most liquid
matching instrument.

| risk | is it the thesis? | handling |
|---|---|---|
| market beta | no, for firm and sector theses | SPY short sized by the risk model's beta; re-hedged when \|net beta\| > 10% of gross |
| sector / cluster factor | no, for firm theses | the matching sector or industry ETF (XLK, SMH, XLE, XLV, …), or a cluster-peer basket. The choice has the lowest residual basis variance in S5; or long/short pairs inside the cluster when both legs carry theses |
| sector / stage view (if E3 passes) | yes | the sector or industry ETF itself, hedged with SPY |
| firm driver | yes | the stock |
| announcement risk | yes, bounded | §5.5 budget |

**Net market exposure** is a standing strategic choice of the owner, declared in P8 (default beta-flat). It is set
by judgement and is not changed by the thesis machinery.

**Binding practicalities:**
* whole shares;
* ETF liquidity at the pre-close send;
* borrow (more binding on S&P 400 shorts);
* Reg T gross ≤ 1.8×;
* 5 bp/side;
* hedge no-trade bands.

### 5.5 The lifecycle: thesis-driven horizons (`fund/lifecycle.py`, a class hook; P7's tactical path byte-identical)

* **No fixed horizon.** Each position carries α_t from Q4:
  * the forecast at entry, decayed at the **measured half-life of its evidence type** (H8, estimated on 2012–21
    data, validated on 2022–25), and refreshed whenever new evidence enters the ledger;
  * the position is held while |α_t| exceeds the cost and risk hurdle (round-trip cost plus a fixed margin),
    and sized continuously with a 25% no-trade band;
  * gradual accumulation and unwinding come from this rule, not from tranche parameters.
* **Checkpoints, not exits.**
  * The firm's own report forces a full **re-underwriting**: the new card may continue, extend, flip or close
    the thesis.
  * The card's milestones (peer reports, product, regulatory or court dates, capacity ramps) are scheduled
    reassessments.
* **Exits.**
  1. α below the hurdle (the thesis has played out or faded);
  2. a kill condition confirmed (§5.6);
  3. re-underwriting closes the thesis;
  4. a catastrophic residual-drawdown stop at −3 × σ_e × √(days held), never tuned. It is a risk control, not a
     signal.

  There is no profit target. Mechanical expiry needs **no supporting evidence for 8 weeks and α below the
  hurdle**, both conditions.
* **Announcement risk.**
  * Per name: |w| × σ̂(|CAR| over its last 8 reports) ≤ 30 bp NAV.
  * Total per week: ≤ 150 bp.
  * When the budget binds (peak weeks), it is allocated by α/σ.

### 5.6 The reassessment protocol (owner: retained and extended)
**Triggers** (any one opens a reassessment of the affected theses):
* the firm's own news, deduplicated, touching a card driver;
* propagated evidence from peers, chain neighbours, the sector or geopolitics that touches a driver
  (E2/E3 above threshold);
* a scheduled milestone or the firm's own report;
* an **unexplained residual move**: |e| > 2.5σ_e with no new event. Price moving without news can mean others
  know something. This is a trigger to look, never an exit by itself.

**The check** (the existing `kill_check` machinery, extended):
* 3 independent passes (two wordings plus shuffled order), the same as today;
* kill conditions: matched in ≥ 2 → exit; partial in ≥ 2 → trim to half;
* driver updates go into the ledger and so move α through Q3/Q4;
* an "add" needs **new hard-number evidence in ≥ 2 passes** and the risk budget.

**Outcomes and their asymmetry:**
* Outcomes are hold, add, trim, exit and re-underwrite.
* Exits need less evidence than adds: the discipline is to cut on invalidation and add only on hard facts.
* Every reassessment is logged with its trigger.
* Q5's own test: kill exits should not be followed by residual returns in the thesis's favour.

---

## 6. The tests (pre-registered in one commit before any is run)

**Inference, common to all tests:**
* one primary statistic per hypothesis;
* season × industry fixed effects;
* a wild-cluster bootstrap over industry clusters plus randomization inference;
* Holm within each family;
* validation 2022–25 for model choice;
* **the sealed test (Jan–Sep 2026) read once** for P8 inclusion;
* S&P 500 and S&P 400 reported separately; a universe enters only on its own result;
* economic significance net of 10 bp round trip;
* survivorship caveat: yfinance misses delisted names, which is controlled by paired and long-short designs, and
  the missing share is reported.

**Historical deterministic family (no LLM):**
* **H1 Sympathy reversal.**
  * Signal: the late reporter's sympathy residual return after early peers' reports, minus the implied change in
    its drivers (an SUE-based proxy in the historical version).
  * Target: the late reporter's CAR[−1,+1].
  * Expected sign: negative (Thomas & Zhang).
* **H2 Link momentum by size asymmetry.**
  * Signal: link-weighted past-month residual returns of TNIC peers and of named customers.
  * Target: the next month's residual return.
  * Primary arm: S&P 500 customers → S&P 400 suppliers. Secondary arms: within the S&P 500, and TNIC within each
    universe.
* **H3a Funnel price lead-lag.** Adjacent-stage portfolio residual returns in the theory's direction, weekly and
  monthly.
* **H3b The inventory bullwhip.**
  * Signal: the change in downstream inventory-to-sales (XBRL, first-filed).
  * Target: upstream SUE and announcement CAR one and two quarters later.
* **H4 Geopolitical drift.** Sector residual returns over 1–20 sessions after GPR jumps (top 5% of innovations),
  threats vs acts.
* **H5 Lazy Prices.** Year-on-year 10-K/10-Q section similarity. Targets: the next quarter's residual return and
  CAR.
* **H6 Risk model** (S5 contract).
* **H8 Decay profiles.** IC at horizons of 1–120 sessions for each passing signal and each event type. This gives
  the half-lives the lifecycle uses (§5.5). It is estimated on fit data, checked on validation, and never tuned
  on the sealed test.

**LLM family (replay after the knowledge horizon + forward seasons; `fund/replay_lab.py`):**
* **R0 Knowledge horizon.** Masked-entity and date recall by month, with placebo items. The window starts at the
  later of the horizon and the model's release.
* **R1 Card and reader quality** (the contracts above).
* **R2 Ledger faithfulness.** ≥ 90% of items supported by the cited source (different-family audit).
* **R3 The thesis forecast predicts.**
  * Targets: SUE sign (centred within season × sector) first, then CAR[−1,+1], then the residual return over
    each position's actual life.
  * Pass: the primary statistic passes over **≥ 2 seasons**, with a positive increment over the deterministic
    composite and over past returns and news tone.
* **R4 Ablation ladder.** Own events → + text peers → + named links → + funnel → + sector and geo →
  + deterministic signals; 1 sample against 3. Each rung is kept on a Holm-passing marginal IC.
  **The own-events rung is expected ≈ 0** (§1 #1).
* **R5 Forward seasons.** Predictions for every upcoming report are committed to `fund-data` before the report.
  They start with Q3-2026 (late Oct–Nov) and continue each season.

**Power, expected.**
* About 900 firm-reports per season. With centred SUE-sign targets, a 55% hit rate gives t ≈ 3 per season.
  CAR-based tests are weaker (t ≈ 2 per season).
* So one season can be suggestive; two are required.

**Fallbacks, pre-registered:**
* if R3 fails and the H tests pass: P8 is a deterministic network and filings book; the LLM does extraction only
  (S2, S3, Q1 numbers, E1 channel labels in shadow);
* if R3 passes but no edge rung passes: P8 is not built on links; the thesis desk stays in shadow;
* if everything fails: no P8, written up.

---

## 7. Sequence with kill-gates (P7 untouched; merge windows as before)

| step | when | work | gate |
|---|---|---|---|
| **1 R5 sprint + pre-registration** | Sat 17 Oct – Sat 24 Oct | `PREREG_thesis_tree.md` committed first. Minimal forward desk: Q1 cards from each firm's Q2 report (EX-99.1 + 10-Q MD&A), ledger from the archive since July (E1 own + text peers), centred Q3 score; predictions committed before each Q3 report from about Mon 26 Oct. R0 probe in parallel | predictions logged with commit time < report time |
| 2 Data foundations | weeks 1–3 | XBRL first-filed, 8-K timestamps, TNIC import, filings text (edgar-corpus + 2021–26 parse), consensus audit, ALFRED, S&P 400 universe, bars | coverage ≥ 95% of firm-quarters |
| **3 Gate A: cheap deterministic tests** | weeks 2–4 | H1, H2, H3b, H5, H6, then H3a, H4, H8; validation reads | if nothing passes in either universe, stop building propagation; only the LLM path (R3/R4) continues |
| 4 Replay lab | weeks 3–6 | R1–R4 on post-horizon seasons; R5 accrues | — |
| **5 Sealed test** | when 3 and 4 are done | one read of every surviving component on Jan–Sep 2026 | the P8 inclusion list |
| 6 Shadow build | after 5 | passing components only: lifecycle class hook, reassessment extension, risk model in monitor mode; mechanical gates; champion hashes | ≥ 10 sessions clean, including a report-heavy week |
| 7 Protocol 8 | first safe window after 6 | pre-registration: components, hedging policy, net exposure, lifecycle and reassessment rules, gate, challenger family (P7's tactical book becomes a shadow benchmark) | owner sign-off |

At the switch, every firm's card comes from its latest report, so the book starts with a full cohort.

## 8. Files

**New:**
* `fund/filings.py`
* `fund/fundamentals.py` (XBRL first-filed, SUE, 8-K 2.02 timestamps, inventory/sales)
* `fund/consensus_audit.py`
* `fund/links.py` (TNIC import, own similarity, 10-K link extraction)
* `fund/chains.py` + `fund/chains.json`
* `fund/exposures.py`
* `fund/sector_model.py`
* `fund/events.py` (E1, deduplication)
* `fund/propagate.py`
* `fund/thesis.py` (Q1–Q3, ledger)
* `fund/forecast.py` (Q4, decay)
* `fund/backtest_thesis.py` (H)
* `fund/replay_lab.py` (R0–R5)
* `reports/research/PREREG_thesis_tree.md`, `reports/research/thesis_tree_results.md`

**Modified later:**
* `fund/lifecycle.py`: class hook, thesis horizon, extended reassessment triggers;
* `fund/score.py`;
* `fund/local/runner.py` + workflows;
* `PROTOCOL_fund.md`;
* `fund/CHANGELOG.md`.

**Reused:**
* `context_archive.edgar()` (CIK map, submissions);
* `neighbours.py` (co-mention graph, 8-K item labels);
* `infoflow` (point-in-time reads);
* `backtest_levels.py` (bars, residual-return code, split discipline);
* `lifecycle.kill_check`, `entry_vol`, `caps`;
* `common.llm`, `save_prompts`;
* `score.nw_t`, `obf`;
* `emb_store.py`;
* the narrative pipeline's clustering (event deduplication);
* `broker.py`;
* `eloukas/edgar-corpus`;
* the Hoberg–Phillips data library.

**Cost:** LLM extraction and replay ≈ low tens of dollars on the flash model; free data; local compute; SEC
< 10 req/s.

## 9. Verification

* **Look-ahead unit test:** every feature row asserts `available_ts ≤ decision_ts`. XBRL values use the first
  `filed` value per period.
* **Replications before any holdout read:** Lazy Prices and customer momentum reproduce their published signs on
  the original periods.
* **Placebos:** shuffled links, shuffled stages and shuffled ledgers show nothing.
* **R5:** each prediction's `fund-data` commit time precedes its report's 8-K acceptance time. This is audited
  automatically.
* **Lifecycle hook:** P7's `state.json` is unchanged on rebuild; `replay` stays at 0.0000 bp. Unit tests cover
  α-hurdle exits, re-underwriting at a report, kill trims and the announcement budget.
* **Shadow:** daily mechanical gates and champion hashes are unchanged for ≥ 10 sessions; `execute.py plan`
  builds the target with ETF hedges inside Reg T and the borrow checks.

## 10. Owner decisions

* **D1, net market exposure and hedge instruments**: declared at P8 (default beta-flat; SPY plus sector or
  industry ETFs).
* **Gold-set spot checks**: about 60 events and 30 stage assignments (≈ 1.5 h).
* **The P8 sign-off.**

## Sources consulted for the stress test
* Ali & Hirshleifer (2020), *Shared analyst coverage* — https://papers.ssrn.com/abstract=3015582
* Pinchuk, *Customer Momentum* (out of sample after 2004) — https://arxiv.org/html/2301.11394
* Thomas & Zhang (2008), *Overreaction to intra-industry information transfers?* — https://ideas.repec.org/a/bla/joares/v46y2008i4p909-940.html
* Engelberg, McLean & Pontiff (2018), *Anomalies and News* — https://ideas.repec.org/a/bla/jfinan/v73y2018i5p1971-2001.html
* McLean & Pontiff (2016), post-publication decay — https://www.cxoadvisory.com/big-ideas/effects-of-market-adaptation
* Cohen, Malloy & Nguyen (2020), *Lazy Prices* — https://www.nber.org/papers/w25084
* Koijen & Levy (2026), *Optimized Agentic AI Systems for Asset Pricing* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7108739
* FinCall-Surprise (2026), the LLM "beat" bias — https://arxiv.org/abs/2510.03965
* Gao, Jiang & Yan, *Detecting Lookahead Bias in LLM Forecasts* — https://arxiv.org/pdf/2512.23847
* Kim, Muhn & Nikolaev (2024), *Financial Statement Analysis with LLMs* — https://rotmandigital.ca/wp-content/uploads/2025/01/Financial-Statement-Analysis-with-Large-Language-Models.pdf
* Hoberg–Phillips Data Library (TNIC, 1989–2023) — https://hobergphillips.tuck.dartmouth.edu/
* Fed note (2025), geopolitical risk exposure across industries — https://www.federalreserve.gov/econres/notes/feds-notes/measuring-geopolitical-risk-exposure-across-industries-a-firm-centered-approach-20250829.html
* Di Mascio, Lines & Naik, *Alpha Decay* (≈ 4-month half-life) — https://www.top1000funds.com/wp-content/uploads/2021/05/SSRN-id2580551.pdf
* Record earnings-day moves, 2025 — https://www.advisorperspectives.com/articles/2025/01/14/traders-brace-biggest-s-p-earnings-reactions
* News co-mention cross-predictability — https://arxiv.org/abs/2108.05721v2
