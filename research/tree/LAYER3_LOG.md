# Layer 3: process log

*One entry per step, written when the step is done. Plan: `PHASE3_PLAN.md`. Registrations: `PREREG.md`.*

## Step 1 — power calculation (2026-11-12, before any layer-3 registration)

**What was done.** Weekly rank ICs of the two cleanest out-of-sample series in the project were decomposed into
cross-sectional sampling noise (about 1/√N) and time variation (`LAYER3_POWER.json`):

| Series | Weeks | Names | Mean IC | sd of weekly IC | Share of variance from time variation |
|---|---:|---:|---:|---:|---:|
| IPCA, S&P 400 read | 353 | 332 | 0.0183 | 0.174 | 90% |
| MASTER, S&P 500 2020–2025 | 303 | 463 | 0.0326 | 0.183 | 94% |

**Finding.** The noise in a mean IC is almost all the market's week-to-week variation in what pays, not the number
of names. Power at one-sided α 0.025 (Holm's first step with two finalists), Newey–West inflation 1.1:

| Read | True IC 0.015 | True IC 0.02 |
|---|---:|---:|
| 350 weeks, 330 names | 31% | 50% |
| 350 weeks, 1,000 names | 33% | 53% |
| 465 weeks (2017–2025), 1,000 names | 42% | 65% |

**Correction to the plan.** `PHASE3_PLAN.md` L3.1 said the broad universe cuts the standard error "by about √3".
That was wrong: it cuts it by about 3%. Power comes from weeks. The broad universe is still the right next sample,
for a different reason: it is fresh and survivorship-free. The read window is moved to 2017–2025 (the first year
with a full year of history in Alpaca's bars), which raises power for a true IC of 0.02 from 53% to 65%.

**Consequence for the policy.** Even a real IC of 0.02 fails a two-finalist read about a third of the time. A failed
read of a candidate with a strong prior (IPCA, the trees) is weak evidence against it; forward weeks remain necessary.

## Step 2 — exploitation round and overfitting diagnostics launched; universe build started (2026-11-12)

**Agents (development data only, each with `STATE.json`):**
* **X4_exploit:** fixed-weight combinations of validated pieces (MASTER + IPCA, + trees, + short volume) and the
  no-trade band against plain deciles; IPCA against its declared control on 2013–2019. Weights written into its plan
  before scoring.
* **X5_overfit:** probability of backtest overfitting (CSCV), deflated Sharpe ratio and shrunk ICs for each branch,
  then a calibration check: would they have predicted which of the six finalists survived? Output: a mechanical
  selection rule for later reads.

**Universe (coordinating session, data for the sealed read):**
* Symbols: 33,565 Alpaca US-equity assets (active and inactive) read; 22,507 dropped for exchange (not NYSE, NASDAQ,
  AMEX); 1,390 dropped as ETF or test issue by Nasdaq Trader's typed flags; **9,668 kept**.
* Daily bars 2016–2025 downloading in 194 chunks of 50 symbols, resumable.
* `panel_broad.py` written: applies the registered eligibility rule each session (top 1,500 by 63-session dollar
  volume, price above $5, 252 sessions of history, read names excluded). To share code with the S&P 400 panel,
  `panel400.build` was refactored into `fields()`; the S&P 400 panel was checked **bit-identical** before and after
  (SHA-1 of every array), so the phase-2 read is unaffected.

## Step 2a — exploitation round result (X4, development data, 2026-11-12)

* **No combination beats its best single piece by more than noise.** The best blend (MASTER + IPCA + trees, equal
  thirds) has IC .0247 against .0236 for the trees alone.
* **IPCA does not beat its declared control** on 2013–2019: +.0017 over the Fama-MacBeth ridge on the same 24
  characteristics (t 0.23), rank correlation 0.70. This is the control check the phase-2 finalist rule skipped. It
  weakens the reading of IPCA's S&P 400 pass as evidence for the IPCA method specifically: the ridge may do as well.
* **The no-trade band is the one robust gain:** +1.0 to +1.5%/yr on fast single signals (t 2.0–2.65), little on blends,
  negative on the slow short-volume signal.
* **Consequence for the registered read (L3.1):** none; candidates and controls were fixed before this result. The
  read reports IPCA against the ridge as a paired difference, which will show whether the gap stays at zero.

## Step 2b — overfitting diagnostics result (X5, development data, 2026-11-12)

* **PBO and the deflated Sharpe ratio would not have predicted which finalists survived** (rank correlations with
  retention +0.32, −0.20, −0.09). The best deflated Sharpe (the SDF, 0.995) kept 23%; IPCA, with the worst PBO (0.75),
  passed.
* **Why:** selection inside every branch was noise (PBO about 0.5; the in-sample best never beat the branch median out
  of sample). Survival depended on whether a branch's level was real, which these tools do not measure.
* **What did line up:** the shrunk IC forecast holdout IC better than the raw IC; finalists chosen by mean IC kept
  78–82%, those chosen by t over a higher-IC sibling kept −2% to 41%. Six points, found after looking.
* **Adopted (PREREG Layer 3, Amendment 2):** choose by mean IC, never t; rank by shrunk IC; at most two finalists with
  controls; report PBO and the deflated Sharpe ratio, not gate on them. For the pending read, power at the shrunk IC
  is about 70% for the trees and 42% for IPCA, so a failed IPCA read was registered in advance as uninformative.

## Step 3 — news: size and cost (2026-11-12)

**What was done.** `news_probe.py` counted every 2019 Alpaca (Benzinga) article for 25 names drawn with a fixed seed
from the development panel's mid-2019 members (69 API calls; no text kept; `N4_news/PROBE.json`).

| | Value |
|---|---|
| Articles per name per year | mean 116, median 57, range 23–1,027 |
| Articles with a summary | 0%: headlines only for this period |
| Estimate, S&P 500 2015–2025 | about 640,000 headlines, 15,000 API calls, about 85 minutes at the rate limit |
| Text volume | about 16 million headline tokens |

**Cost.** Dictionary features (counts, novelty, Loughran–McDonald tone) cost nothing beyond the download. Embedding
16 million tokens with a small embedding model would cost well under a dollar at typical list prices (not checked
against the current OpenRouter price list), so even the embedding step is cheap; the LLM budget is not the constraint.

**Decision.** Go. The download shares the Alpaca rate limit with the universe bars, so it starts after them. Then one
agent builds and tests the N4 branch on the development years as an increment over MASTER, saving every
configuration's predictions (Amendment 2). Coverage caveat: one name in the sample has 1,027 articles and the median
has 57, so news features will be sparse for most names in most weeks.

## Step 4a — universe download repaired; read script fixed before the panel exists (2026-11-13)

* **Download.** The first bars run saved 122 of 191 chunks; 69 got a non-200 answer, spread evenly through the run
  (rate limiting, not bad symbols). `fetch_broad.py` now retries a failed request four times (5, 15, 45, 90 s) and
  resumes from the saved chunks. No saved chunk is re-downloaded.
* **Read script.** `read3.py` was written and committed **before the broad panel was built**. It runs exactly the
  Amendment 1 test: candidates and controls as registered, seeds 0-2, years 2017-2025, broad names scored,
  Newey-West t at 4 lags, Holm across L3a and L3b; `READ3.lock` records each candidate's start and refuses a second
  read. Coverage (`read3.py panel`) is checked before any prediction is scored.
* **Checks.** The D-trees library's disk cache is off by default (`X1_combine/lib.py` `DISK = None`), and every
  in-memory cache is keyed by the panel's arrays or cleared each call. No development fit can leak into the read.

## Step 5 — fourth wave launched: four agents, development data only (2026-11-13)

Owner's request: continue exploring and exploiting with several agents, deep learning welcome. Registered first
(PREREG Layer 3, Amendment 3), then launched, each with `STATE.json` and every configuration's predictions saved:

| Branch | What it explores | Control | Why this, now |
|---|---|---|---|
| Q1_seqnet | GRU/LSTM, temporal convolution, time-axis transformer on 60-session histories + rich characteristics, rank/IC losses | B_arch's MLP | B_arch's networks saw only 5 characteristics, 6 epochs, MSE (best IC .016); the trees reach .0236 with 27 inputs, so the gap may be inputs and training, not architecture |
| Q2_xsattn | attention across names within a week (set transformer, MASTER-style), market-state mixture of experts | the same network without the module | one week is a natural set; listwise losses fit it |
| Q3_rankgbm | learning-to-rank boosted trees (LambdaRank / pairwise), monotone constraints, DART, horizon averaging | D trees, 5-session target | the trees are the best development model; ranking objectives match the IC metric |
| Q4_portfolio | nonlinear covariance shrinkage, mean-variance long/short, turnover penalty, volatility-managed scaling, drawdown control | decile book + no-trade band | X4: construction (the band) was the one robust gain; Sharpe and drawdown live here |

No candidate from this wave gets a sealed read without a later amendment naming fresh data. Q1-Q3 are judged by the
Amendment 2 rule (mean IC, years positive, shrunk IC); Q4 by net Sharpe with drawdown no worse than its control.

## Step 6 — literature review of preprocessing (L1); two pipeline faults found and fixed before the read (2026-11-13)

**What was done.** One agent read the published preprocessing choices for machine-learning return models (Gu-Kelly-Xiu
2020, Chen-Pelger-Zhu, MASTER, the Qlib benchmarks, Bryzgalova-Lerner-Lettau-Pelger, Jensen-Kelly-Pedersen, Poh et al.
and others; access labels and the search log in `L1_lit/REPORT.md`) and compared them with our code.

**Findings acted on now.**
1. *Development-panel survivorship* (checked here, not taken on the relay): 241 of 738 ever-eligible names have no
   price; 23.5% of eligible name-weeks lack a target. Disclosed in PREREG Layer 3, Amendment 4. Repair is a separate,
   later job (Alpaca bars for the missing names, 2016 on), queued after the downloads.
2. *Look-ahead in the broad universe filter*: the $5 rule read adjusted closes. Fixed by Amendment 4 (unadjusted
   prices for eligibility), before the panel exists.
3. *Delisting returns dropped*: reported as a bound (Amendment 4), with IC by size tercile.

**The bars download, diagnosed.** The 69 failed chunks were not rate limits: the bars endpoint answers 400 "invalid
symbol" for some asset symbols (CUSIP-like ids, `*_DELISTED` renames). The fetch now drops such a symbol, records it,
and retries the chunk.

**Queued from the review (development data, each to be registered with its control before scoring):** rank or
winsorise the five base characteristics; missing-value indicators for the long-window features; per-stock volatility
scaling of sequence inputs (Q1); 10 seeds for network finalists.

## Step 7 — L1 findings fed to each leaf (2026-11-13)

Each running agent (Q1-Q4) received the findings that bear on its branch, as optional variants to be added to its plan
before scoring, plus the survivorship caveat and the seed-noise rule (re-score a nominated candidate with seeds 0-9).
The same text, per branch, is in `L1_lit/FEED.md`, so a successor agent resuming after a limit gets it too. The news
branch (N4, not started) has its notes there: missing-news weeks as an explicit state, increment over MASTER, size
terciles.

## Step 8 — Q4 portfolio construction result (development data, 2026-11-13)

* **No construction beats the no-trade band** on the same signal by more than noise (30 rows; best vol-matched
  paired t 0.72). The band stays the construction rule; no candidate nominated.
* **Mean-variance with Ledoit-Wolf 2020 shrinkage carries real information**: gross Sharpe about 1.0 on the trees
  against the band's 0.56. But it trades too much to keep it net of 5 bp; with an L1 no-trade region, net Sharpe 0.64
  vs 0.35. The branch agent declined to nominate it: added after seeing results, k at a grid edge, fails on the other
  three signals in 2013-2016, and drifts net long without a hedge. Linear shrinkage does as well gross: the gain is
  the covariance, not the nonlinear shrinkage.
* **Volatility-managed scaling** helps trees and IPCA, hurts MASTER and the blend (all |t| ≤ 0.4). **Drawdown rule**:
  lower raw drawdown, same Sharpe.
* **Both books earn in calm weeks** and in middle-volatility names, not in volatile periods or names.
* **What to carry forward.** The covariance-aware book is the one lead worth a registered test: fix k and the hedge
  in advance, test it on all four signals at once, and judge it on fresh weeks.

## Step 9 — ledger fault fixed; Q3 interim (2026-11-13)

* **Fault (reported by the Q3 agent, confirmed in the code):** `state.py` rewrote every branch's `STATE.json`,
  including running agents', and crashed Q3's bookkeeping once (no result lost: `RESULTS.jsonl` and predictions are
  written separately). It also chose "best" by t, against Amendment 2, and never cleared "name: spec" plan entries
  from pending. Fixed: the script now only reads branch files (checked: checksums of every `STATE.json` unchanged by a
  rebuild); best = highest mean IC (mean increment for track N, net Sharpe for Q4) among configurations positive in at
  least 5 of 7 years. Q1 and Q2 were told to re-check their state files.
* **Q3 interim (5 of 16 scored):** no ranking objective beats squared-error trees. Control .0216; RankNet .0206;
  LightGBM L2 .0204; monotone .0192; LambdaRank (quintile grades) .0171. Second batch running, including the two
  literature variants (native NaN; ranked Z).

## Step 10 — adjusted bars complete (2026-11-13)

* All 191 chunks saved; no failed chunk. 379 symbols rejected by the bars endpoint as invalid and dropped
  (`chunks/_dropped.json`): CUSIP-like ids of contingent value rights, escrow and similar non-trading lines, and
  `*_DELISTED` renames. The first five chunks held only such symbols, so they are empty. The `*_DELISTED` renames are
  the one real loss (delisted names whose bars Alpaca does not serve under that symbol); counted in the read.
* Unadjusted bars (Amendment 4, eligibility only) downloading now; then the panel, its coverage check, and the read.

## Step 11 — Q3 ranking trees result (development data, 2026-11-13)

* **No learning-to-rank objective, constraint or ensemble variant beats squared-error trees on a ranked target.**
  19 rows. Best `ens_ctrl_mh_huber` (rank average of the control, multi-horizon LightGBM and Huber LightGBM): IC
  .0222 vs .0216, paired difference +.0006, Newey-West t +0.48. Shrinkage factor 0: the configurations are not
  distinguishable from one another.
* **Ranking losses**: one-sided LambdaRank loses (.0171, .0154) because NDCG weights the top of the list while the
  long/short book uses both ends; a two-sided version ties (.0214). Monotone constraints hurt (t -1.76). Bigger trees
  hurt (t -1.46): D's low-capacity settings are near the optimum.
* **Literature variants** (native NaN, ranked Z): no gain.
* **Seed check**: 10 seeds move the control by .0001 and lgb_mh by .0005, about the size of the best edge.
* **Huber loss** gives the best decile net (+1.7 %/yr) at a lower IC; a tail effect, not a ranking gain. Noted as a
  construction-side lead, not tested.
* **Consequence**: the trees branch is saturated on these 25 inputs; further gains must come from new information
  (news, survivorship-repaired data, other universes), not from loss or ensemble engineering.

## Step 12 — broad panel built and checked (2026-11-13)

* Two build bugs: empty chunk files (only invalid symbols) made the price table non-numeric; and an earlier run's exit
  status was hidden by a pipe into `tail`. Fixed (numeric cast, empty files skipped, exit code captured).
* **Coverage** as designed: 1,500 eligible names every Thursday 2017-2025, 3,684 distinct; 17.3% inactive at Alpaca;
  16.2% stop trading before December 2025. Survivorship loss: 59 `*_DELISTED` symbols.
* **Content check found bad prints** (AQB $0.144 on 8 shares between $528 and $530): 95 targets beyond ±100%.
  Amendment 5, before any prediction: books earn the clipped target; the rank-IC test is unchanged.
* **Next: the registered read** (L3a IPCA vs ridge, L3b trees vs 5-session trees), once.

## Step 13 — the registered L3.1 read (broad survivorship-free universe, 2017-2025, 455 weeks, 1,500 names a week)

**Both candidates pass (Holm, alpha 0.05).** Out-of-sample: fitted only on rows whose target ended before each year.

| | IC | t | p (one-sided) | years positive | decile book net %/yr (Sharpe) | band book net %/yr (Sharpe) |
|---|---:|---:|---:|---:|---:|---:|
| L3b trees, 4 horizons (candidate) | .0249 | 4.41 | 5e-6 | 9/9 | 6.3 (0.65) | 5.6 (0.62) |
| trees, 5-session target (control) | .0237 | 4.15 | — | 9/9 | 7.2 (0.72) | 6.4 (0.68) |
| L3a IPCA (candidate) | .0173 | 3.11 | 9e-4 | 9/9 | 2.2 (0.22) | 2.5 (0.28) |
| Fama-MacBeth ridge, 24 characteristics (control) | .0224 | 4.04 | — | 9/9 | 6.5 (0.65) | 6.0 (0.65) |

Books: stock long/short only, gross 1, beta-hedged, 5 bp a side, target clipped at ±100% (Amendment 5).

* **Replication, on data with delisted names.** The trees pass at about 70% registered power, so this counts as
  evidence for them. Keeping delisting returns changes no IC by more than .0001.
* **Controls.** The 4-horizon trees beat their 5-session control by +.0012 IC (t 1.18; not significant). IPCA trails
  the ridge by .005 (t −2.04), as on development data: the information is in the characteristics, not IPCA's method.
* **Not a small-name effect.** Trees IC by dollar-volume tercile .032 / .019 / .024. The smallest tercile is
  strongest, so trading costs there need checking before the book is traded.
* **The band does not help here** (6.3 → 5.6 %/yr for the candidate), unlike on development data.
* **A process fault.** In the trees read, the books call failed on a module-name clash (`lib`). The books were
  recomputed from the saved read predictions with the same code; the IC test was unaffected.
* **Against the owner's bar** (net Sharpe > 1, out of sample): no stock book reaches it alone. Best book 0.72; the
  whole fund on 2020-2025 is 0.94 (`OOS_RETURNS.json`).

## Step 14 — Q2 attention across names result (development data only, 2026-11-13)

* **No module beats its ablation.** The nominated pair at seeds 0-9: pooling −0.0007 (t −0.41). Self-attention on the
  best network −0.0033 (t −1.76). The market-state gate −0.0035; MASTER's input gate 0.
* **The best network** (no module; listwise IC loss, 4 uniform heads, width 128) ties the trees on development data
  (.0237 vs .0236, t 0.02). Its weekly ICs correlate 0.94 with the trees': the same signal, re-learned, not a new one.
* **What mattered**: the loss (a listwise IC loss beats squared error by .008); raw return history as an input hurts
  (−.020).
* **Out-of-sample status**: none. The network is a development result. It is not a diversifier for the trees (IC
  correlation 0.94), so it is not a route to a higher Sharpe; no read requested.

## Step 15 — combination check and policy round (2026-11-13)

**Combination check** (`combo_check.py`, `COMBO_CHECK.json`; descriptive, both series already read, 2020-2025):

| Broad book cost | Broad book Sharpe | Correlation with fund | Fund + broad book, equal-risk rule | Upper bound (best weight, ex post) |
|---|---:|---:|---:|---:|
| 5 bp | 0.75 | 0.07 | **1.09** (25.9 %/yr) | 1.16 |
| 10 bp | 0.55 | 0.07 | **1.03** (24.6 %/yr) | 1.05 |
| 20 bp | 0.13 | 0.07 | 0.92 | 0.94 |

The fund alone: 0.94 (21.0 %/yr on these weeks). The broad book is close to uncorrelated with the fund (0.07; 0.16
with its stock book), so it diversifies. Whether the bar of 1 is cleared depends on the true cost of trading the broad
names: measure it before anything else.

**Tree after the policy (PREREG Layer 3, Amendment 6):**

```
root: weekly cross-sectional stock selection + S&P core
├── EXPLOIT (out-of-sample evidence)
│   ├── trees, broad universe ── PASSED L3.1 (IC .0249, t 4.41)
│   │   ├── E1 cost study: broad half-spreads from SIP quotes ── running
│   │   └── E2 combined fund (core + MASTER + broad trees, equal risk) ── forward only, needs the owner's go-ahead
│   ├── IPCA ── passed twice (S&P 400, broad); trails its ridge control ── no further spend
│   └── MASTER, S&P 500 fund ── 0.94 out of sample (2020-25) ── traded
├── EXPLORE (development data)
│   ├── Q5_rl  RL construction (Moody-Saffell RRL, PPO, EIIE, differentiable Sharpe) ── launched
│   ├── N4_news  headlines 2015-2025 ── downloading; branch on completion
│   ├── Q1_seqnet  sequence nets ── finishing (best dev .0225)
│   └── R1 survivorship repair of the development panel ── queued
└── CLOSED this layer: Q2 attention (no), Q3 ranking trees (no), Q4 construction (band stays; covariance book = lead)
```

## Step 16 — E1 cost study: what the broad names cost to trade (2026-11-13)

Quoted half-spread one second before 15:59 ET, on 12 seeded days in 2019-2025, every eligible name (`COST_STUDY.json`):

| Universe | Names × days | Quoted | Median half-spread | Mean | 90th percentile |
|---|---:|---:|---:|---:|---:|
| S&P 500 panel names | 6,046 | 99% | 1.4 bp | 2.3 bp | 4.4 bp |
| Broad names, all | 18,000 | 88% | 4.2 bp | 6.4 bp | 11.5 bp |
| Broad, smallest dollar-volume third | 5,999 | 78% | 6.2 bp | 9.4 bp | 17.9 bp |
| Broad, middle third | 6,001 | 90% | 4.2 bp | 6.2 bp | 10.6 bp |
| Broad, largest third | 6,000 | 96% | 2.7 bp | 4.2 bp | 7.8 bp |

**Reading against the combination check** (Sharpe 1.09 at 5 bp, 1.03 at 10 bp, 0.92 at 20 bp; interpolation, not
measured):
* **Spread alone** (mean 6.4 bp): about 1.07.
* **With the same cushion the S&P 500 assumption carries** (5 bp charged against a 2.3 bp mean spread, ×2.2; so
  about 14 bp for broad names): about 0.99.
* So the combined fund sits **at the bar, not clearly above it**. Impact and the unquoted 22% of the smallest third
  are not in these numbers.
* **Implication:** the smallest dollar-volume third carries the highest IC (.032) and the highest cost (9.4 bp mean).
  A cost-aware broad book (e.g. trading only the two larger thirds, or size-scaled cost in construction) is the
  natural next exploitation. It was found after looking at spent data, so it can only be judged forward.

## Step 17 — lead's decision: test the combined fund on 2026 (2026-11-13)

**The owner's question:** "can't we split the history data to train and test?" Answer: we do, but each test set can be
read once. For the combination, 2020-2025 and 2017-2025 are spent. Re-splitting them would test ideas that came from
looking at them. The one unused stretch is January-November 2026: no backtest of this combination has touched it.

**Decision (lead):** register H7 (PREREG Layer 3, Amendment 7) before any 2026 price exists here.
* **Arms:** combined fund, full broad book (H7a) and cost-aware broad book, top two dollar-volume thirds (H7b).
* **Costs:** 14 bp for broad names, from the cost study.
* **Training:** everything up to 2025; test once on 2026; Holm across the two arms.
* **Power:** registered as low (about 10-20%), so a fail is not a rejection. Forward weeks extend the same test.
* **Roles:** the coordinating session fetches the 2026 data (redacting wrapper, frozen at first fetch) and runs the
  one scored read. One build agent (H7_build) builds the refits and prediction files and is barred from computing
  any 2026 statistic.

## Step 18 — Q5 reinforcement-learned construction result (development data only, 2026-11-13)

* **No RL policy beats both controls; nothing nominated.** Best: Moody-Saffell online differential-Sharpe RRL on
  the trees signal, net Sharpe 0.43 vs the band's 0.31 (vol-matched +0.82 %/yr, t 1.50), but behind the covariance
  book `mvnl_nt` (0.74). It loses on MASTER (t −2.16). With 24 candidates, a best t of 1.5 is what noise produces.
* **Overfitting is the story**: batch-Sharpe RRL reaches in-sample Sharpe 1.25-1.93 and 0.03-0.38 walk-forward; the
  per-asset networks (EIIE, end-to-end) are negative walk-forward. About 200 training weeks cannot support them.
* **What the one modest learner learned**, consistently on two signals: a slightly wider exit band, a tilt away from
  high-volatility names, lower exposure when dispersion or recent IC is high. A fixed wider band alone ties. These
  overlap with the L2 survey's rank-hysteresis rule, which is the cleaner, parameter-free version to register.
* **Consequence**: the covariance-aware book (`mvnl_nt`) stays the construction lead; RL closed for this layer.

## Step 19 — Q1 sequence networks result (development data only, 2026-11-13)

* **No: sequence encoders add nothing measurable.** The best (GRU on 60 sessions + D's 27 inputs, IC loss) has IC
  .0206 at 10 seeds (.0225 at 3), +.0003 (t 0.05) over the same network without the encoder, and does not beat the
  trees (−.0030 vs the multi-horizon trees). The gain over the old network control (+.0065, t 1.19) comes from
  inputs and loss.
* **A blend with the trees** (50/50 ranks, reported, not selected) has IC .0237: no gain over the trees alone (.0236).
* **Fourth wave closed.** Q1 sequence nets, Q2 attention, Q3 ranking trees and Q5 RL find nothing over the trees.
  Q4 leaves the covariance book as the construction lead. The trees on these 25-27 price inputs are the ceiling of
  model engineering here. Remaining gains are in cost and construction (L2: rank hysteresis, decay, neutralisation)
  and in new information (news, industry-relative features).

## Step 20 — two reviews merged; fifth wave launched (2026-11-13)

**Inputs:** the L2 practitioner survey (Numerai, Kaggle write-ups, Quantpedia, Robot Wealth) and the L3 literature
review (JKMP, Novy-Marx-Velikov, Frazzini-Israel-Moskowitz, Dai et al., Ehsani-Harvey-Li and others). Both are
in-project readings, with access labels.

**Lead's synthesis.** Both say the same thing: for a fast reversal-heavy signal, net Sharpe is decided by
construction and cost, not by the forecast.
* JKMP: net Sharpe 0.94 → 1.38 by learning weights under costs, with turnover 0.76 → 0.32 a month.
* Novy-Marx-Velikov: a buy/hold spread lifts industry-relative reversal from net 0.16 to 0.35 %/month.
* Quantpedia: weekly reversal −31 bp a week net on 1,500 names, +29 on 100.

So the fifth wave (Amendment 8) is three development branches on cost, information and risk:
* **Q6_trade:** a square-root cost model first, then hysteresis, decay and partial trading toward the Ledoit-Wolf aim.
* **Q7_features:** industry-relative and announcement-masked reversal, short-run industry momentum, and horizon by
  turnover.
* **Q8_neutral:** partial and sector neutralisation.

**Planning haircut adopted** (McLean-Pontiff, Chen-Velikov): expect the broad trees book to earn about 0.7× its
out-of-sample Sharpe forward. On that haircut, the independent-books projection is √(0.94² + (0.7 × 0.55)²) = 1.02 to
√(0.94² + (0.7 × 0.75)²) = 1.08. In `COMBO_CHECK.json` the equal-risk rule realised about 0.05 below that formula, so
roughly 0.97-1.03 at measured costs [reasoning; ignores the fund's own decay]. (Corrected the same day: a first draft
of this line said 0.96-1.0, an arithmetic slip.)
Sharpe > 1 therefore needs the construction gains, not just the combination.

## Step 21 — Q8 neutralisation result (development data only, 2026-11-13)

* **No neutralisation earns a place.** Partial neutralisation (p 0.5) and within-sector ranking cut the sd of weekly
  IC by about 20% and 35% and cut decile drawdowns, but always cost mean IC. The decile Sharpe gains (trees 0.15 →
  0.32; MASTER −0.26 → −0.11) are insignificant (t 0.31, 0.93) and sit in 2013-16 only. The band book does not
  improve. IPCA is hurt (t −1.59).
* **Ehsani-Harvey-Li's rule is unstable here**: the trees decision flips between 2013-16 and 2017-19, and applying it
  made trees worse.
* **Useful descriptive fact**: the trees signal correlates −0.55 with beta and −0.30 with volatility; 41% of its
  cross-sectional variance is explained by beta, size, volatility and sector. Low-beta/low-vol tilts are much of what
  the model learned.
* **Keep as a risk lever only**, not a return source. The book construction rule is unchanged.

## Step 22 — Q7 industry features result, and a leak finding (development data only, 2026-11-13)

* **No feature gain.** Industry-relative reversal, short-run industry momentum and earnings-masked reversal add
  nothing to the trees: F1 −0.0009 (t −0.42); F2 +0.0010 over the multi-horizon trees (t 0.71), which reverses to
  −0.0009 on names with a sector code. Horizon by volume tercile (H1) −0.0017; it is untested in its registered form,
  because the proxy is share volume, not turnover.
* **Leak finding (important beyond Q7).** Whether a name appears in `.cache/p8/gics.json`, which is built from
  *today's* S&P 500/400 lists, predicts its 2013-2019 returns: the indicator alone has weekly IC +0.0149 (t 3.85).
  Any model input or grouping whose *availability* depends on current index membership carries survivorship
  information. Q7 declared a covered-subset check in advance and caught it.
  * **Q8** used sector dummies with a "missing" group, so its N1/N2 rows may carry the same leak. They showed no gain
    anyway.
  * **Unaffected:** the out-of-sample whole-fund figures (`OOS_RETURNS.json`, `COMBO_CHECK.json`). The fund's S0
    construction does not use sectors.
  * **Queued audit A1:** list every model and read whose inputs come from current-membership files (gics.json, the
    P8 events/sector fields, the S&P 400 current list) and check whether a missingness indicator or group entered.
    Owner of the fix: the coordinating session.
* **Consequence**: the trees on price inputs remain the model; feature engineering on industry adds nothing on large
  caps at a weekly horizon.

## Step 23 — Q6 trading-less result; fifth wave closed (development data only, 2026-11-13)

* **Square-root cost model built and tested.** K 0.5 is anchored on JKMP and Frazzini-Israel-Moskowitz; ADV comes
  from Yahoo consolidated dollar volume. That is a disclosed departure: FINRA share volume cannot give dollars.
  * At $10M, S&P 500 names cost about the flat 5 bp.
  * At $100M the band's impact triples and its Sharpe halves.
* **No rule beats the covariance book `mvnl_nt` on trees.** It scores 0.70 under the square-root model at $10M and
  0.65 at $100M. The best registered candidate is rank hysteresis T1 (enter at the 10% tails, exit outside 30%): 0.45
  vs the band's 0.38 (vol-matched t 1.31). It cuts turnover by a third at no gross cost and keeps 0.34 at $100M. It
  also helps IPCA (t 1.35). Gârleanu-Pedersen partial trading fails everywhere. Nothing is significant.
* **Fifth wave closed** (Q6, Q7, Q8). Development data show a consistent pattern:
  * cost-saving construction helps a little (hysteresis, the covariance book with a no-trade region);
  * neutralisation and industry features do not.
* **What goes forward** (to be registered as forward-only constructions alongside H7, never chosen on 2026 data):
  the broad trees book under (i) deciles, as H7 registers, (ii) rank hysteresis 10/30 and (iii) the covariance book
  with an L1 no-trade region, all under the square-root cost model with the broad names' own spreads and ADV. Only
  forward weeks can judge them on the broad universe; the development panel's low costs understate the savings.

## Step 24 — H7: the 2026 read of the combined fund (2026-11-14; out of sample, 43 weeks, 8 Jan - 29 Oct 2026)

**Process disclosure.** The read ran once, with the script committed in c8528d3, but not when intended. A patch adding
a dry-run mode failed its own assertion and left the script unchanged; the next command, meant as a dry run on 2025
weeks, therefore executed the registered read. Nothing was seen before it, the code is the committed code, and
`H7.lock` holds the time. The result stands as the one read.

**Test (Holm, α 0.05): neither arm passes.** Registered power was 10-20%; a fail is not a rejection.

| Arm | Increment over the fund, %/yr | t | p (one-sided) | Holm |
|---|---:|---:|---:|---|
| H7a full broad book, k 0.59 | +13.0 | 1.76 | 0.039 | fail (needs 0.025) |
| H7b top two dollar-volume thirds, k 0.53 | +10.4 | 1.36 | 0.087 | fail |

**"Broken" rule: not triggered.** Broad trees IC 2026 = .042 (t 2.85); increments positive.

**Reported, 2026 (43 weeks; short, noisy):**

| | % per year | Net Sharpe | Worst fall |
|---|---:|---:|---:|
| Broad trees book alone (14 bp), all names | +22.0 | 1.65 | −5.0% |
| Broad trees book alone, top two thirds | +19.6 | 1.34 | −7.7% |
| Fund alone (S&P core + MASTER book, 5 bp) | −1.5 | −0.10 | −11.9% |
| Combined, H7a | +11.5 | 0.76 | −11.5% |
| Combined, H7b | +8.9 | 0.60 | −12.2% |
| S&P 500 (same weeks) | +7.3 | | |

* **The broad trees signal held up on fresh data**: IC .042, about its 2024-2025 level; positive in every
  dollar-volume third (.049 / .037 / .040). Turnover is 42% a week.
* **The fund alone lost money in 2026** while the S&P gained 7.3 %/yr: MASTER's IC was .003 (t 0.17). Either the
  MASTER book stopped working this year or the 1.3×/0.7× core whipsawed; the split is not yet computed.
* **The cost-aware arm (H7b) did worse than the full book**: dropping the least liquid third lost more signal than
  it saved in cost, at 14 bp.
* **Against the owner's bar**: the combined fund's 2026 net Sharpe is 0.76, below 1. The broad book alone is 1.65 over
  43 weeks; its standard error is about 1.1, so this is not evidence of a Sharpe above 1.
* **Next (registered path):** the same pipeline runs on forward weeks as the extension of H7. Separately, the fund's
  2026 loss needs a decomposition (core vs MASTER book) before anything else is built on MASTER.
