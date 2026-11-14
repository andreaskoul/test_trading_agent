# Tree search over stock-selection models: protocol and pre-registration

*Written 2026-11-10, before any agent has run. Owner's brief (2026-11-10): explore the limits of mathematics, model
design and network design with several agents, as a tree search that explores and then exploits. Research only;
nothing in the traded fund changes.*

## 1. The problem a search creates, and the guard against it

A search over many models picks the luckiest one. On 353 development weeks, the standard error of a mean weekly rank
IC is about 0.01, so differences below 0.01 between models are noise. The guard is a holdout no agent can reach:

* **Development sample:** S&P 500 members, daily, 2009-01 .. 2019-12-31 (`.cache/tree/dev.npz`, built from the
  `research/quant_trials` panel). The file contains nothing after 2019.
* **Holdout:** 2020-01 .. 2025-12. Read once, by the coordinating session only, for at most three finalists.
* **Disclosure.** 2020–2025 is known in aggregate (momentum and volatility tilts did well; the MASTER 5-day model's
  results there are known). A new model's predictions there have not been seen. Forward weeks remain the only clean
  confirmation.

## 2. The task and the metric

Predict the cross-section of 5-session hedged returns entered at the next close (`y5`). Interface and rules: the
docstring of `harness.py`. Development metric: mean weekly Spearman IC on the Thursdays of 2013–2019, walk-forward
(each validation year predicted by a model fitted only on rows whose target ended before that year), ranks averaged
over 3 seeds; also IC by year and a decile spread net of 5 bp a side.

References on the development sample: ridge on the five characteristics, IC −0.002 (t −0.2); the MASTER 5-day model as
scored in October, IC 0.0125 (t 1.43).

## 3. The search

* **Round 1, explore (five branches, one agent each):** A loss mathematics; B network architecture; C features and
  econometrics; D trees, ensembles and stacking; E regime-adaptive models.
* **Round 2, exploit:** the two or three branches with the best development evidence are refined and combined.
* Every configuration scored is appended to the branch's `RESULTS.jsonl`. The total count is reported with the result.
* Budget per agent: about 15 configurations, each fit within about 6 minutes on 2 CPU threads.

## 4. Finalists and the one read

* **Finalists (at most three),** chosen by the coordinating session after round 2: the highest development IC t among
  configurations with a positive IC in at least 5 of the 7 years, at most one per branch.
* **Holdout run:** the finalist's `fit_predict`, annual refits 2020..2025 on the full panel, 3 seeds.
* **Tests (`READ.lock`):** for each finalist, (i) mean weekly IC > 0 (t with Newey–West, 4 lags), one-sided; Holm
  across the finalists at α = 0.05; (ii) reported, not tested: IC against the MASTER 5-day model's on the same weeks,
  the decile spread net of 5 bp, IC by year.
* **Consequences.** A finalist that passes (i): propose one forward paper book (research only). None passes: the
  search is closed on this panel and its count of configurations is recorded as the price of the null.

## 5. Not claimed

Nothing found on the development sample is evidence. A holdout pass is evidence for a forward test, not for trading.

## Amendment 1 (2026-11-12, before any holdout data is read): finalists

**Search size.** Round 1: 60 configurations (A 12, B 11, C 15, D 7, E 15). Round 2: X1 11, X2 11, X3 32 (14
online/yearly pairs and 4 staleness diagnostics). Total 114 logged configurations.

**Finalists by the §4 rule** (highest development IC t with a positive IC in at least 5 of 7 years, one per branch):

| Finalist | Branch | Development IC | t |
|---|---|---:|---:|
| X1_8p: D trees + C ridge + MLP, 4 horizons each, panic overlay | X1 | 0.0282 | 2.91 |
| A_mse_rank: MLP on ranked targets | A | 0.0188 | 2.45 |
| D_hgb_mh: boosted trees, 4 horizons | D | 0.0236 | 2.41 |

**One departure, disclosed.** The second-highest t (2.47) belongs to an X3 row that its agent labelled a post-hoc
diagnostic, "not proposed as a model": the same linear model run with a deliberate one-year extra lag. It is excluded
as not a candidate. The X2 row with t 2.41 is the same model as D_hgb_mh, reproduced; D's is used.

**Code check before the read.** Each finalist's `model.py` (`research/tree/finalists/`) must reproduce its logged
development IC to four decimals (`verify.py`, results in each `VERIFY.json`). A finalist that does not reproduce is
dropped, not repaired.

**Reported beside the registered tests** (not tested): each finalist's decile spread with the X2 score smoothing
(exponential, half-life 1 week, over the current and 12 preceding Thursdays), since branch X2 showed smoothing cuts
costs without lowering IC on the development sample.

## Result of the holdout read (2026-11-12, `HOLDOUT_RESULT.json`, `HOLDOUT_SMOOTHED.json`; 303 weeks, 2020-01 .. 2025-12)

| Finalist | IC | Newey–West t | one-sided p | Holm (α 0.05) | IC by year 2020 → 2025 | IC minus MASTER (t) |
|---|---:|---:|---:|---|---|---:|
| X1_8p combined | 0.0224 | 2.11 | 0.0173 | **fails** (needs 0.0167) | .035 .005 .023 .014 .026 .031 | −0.010 (−0.86) |
| D_hgb_mh trees | 0.0185 | 1.89 | 0.0293 | fails | .027 .001 .035 .002 .015 .031 | −0.014 (−1.21) |
| A_mse_rank MLP | 0.0078 | 0.79 | 0.2162 | fails | .017 −.015 .012 −.004 .031 .006 | −0.025 (−1.87) |
| MASTER 5-day (reference, already seen) | 0.0326 | 3.14 | | | | |

Reported, not tested: decile spread net of 5 bp a side, raw and with the X2 smoothing (half-life 1 week).

| | raw % a year (Sharpe) | smoothed % a year (Sharpe) |
|---|---:|---:|
| X1_8p | +2.6 (0.27) | +4.7 (0.53) |
| D_hgb_mh | +2.0 (0.22) | +2.8 (0.33) |
| A_mse_rank | −3.7 (−0.41) | −0.1 (−0.02) |

**Consequence as registered: no finalist passes; the search is closed on this panel.** It cost 114 logged
configurations. The best search model missed the Holm bar narrowly (p 0.0173 against 0.0167) and was positive in all
six holdout years, but it is below the MASTER 5-day model on the same weeks, which therefore remains the project's best
stock-selection model. Development leads of about +0.01 IC over MASTER did not survive the holdout: they reversed to
−0.010 to −0.025, the size of selection bias the protocol warned of (§1).

## Phase 2 (2026-11-12, before any phase-2 agent runs)

Plan: `PHASE2_PLAN.md`. Harness additions: `load_extra` (input files ending 2019) and `increment` (paired weekly IC
over the frozen MASTER 5-day scores). Track N branches are judged by `increment`; track M branches by `score` on the
S&P 500 development sample, and confirmed once on the S&P 400 (2019–2025) by the coordinating session. Development
gate for both tracks: t ≥ 1.5 with the predicted sign; one read per finalist, Holm across all phase-2 finalists.

## Phase 2, Amendment 2 (2026-11-12, after all phase-2 development results, before any phase-2 holdout data is built or read): finalists and the reads

**Search size, phase 2:** M1 18, M2 20, M3 8, M4 12, M5 13, M6 12, N1 23 (9 configurations + 14 single characteristics),
N2 11, N3 20 logged rows. N4 (news) not run. With phase 1's 114, 251 logged configurations in all.

**Finalists** (each branch's best by its registered metric among those meeting the t >= 1.5 gate):

| Finalist | Track | Development | Read |
|---|---|---|---|
| N1 fm_fixed70: 0.7 MASTER + 0.3 Fama-MacBeth fundamentals | N | increment +0.0047, t 2.29 | S&P 500, 2020-2025: mean weekly increment over MASTER > 0 |
| M2 M05_U: IPCA, 24 characteristics, unrestricted | M | IC 0.0224, t 2.27 | S&P 400, 2019-2025: mean weekly IC > 0 |
| M4 S04: unshrunk SDF on 324 characteristic products | M | IC 0.0141, t 3.67 | S&P 400, 2019-2025: mean weekly IC > 0 |

One-sided Newey-West t (4 lags), Holm across the three at alpha 0.05. Lock: `READ2.lock`.

**How each read is built (fixed now):**
* **N1:** the full S&P 500 panel 2009-2025 (`holdout.full_panel`), MASTER's 2020-2025 scores as already computed, and the
  point-in-time fundamentals rebuilt by `build_fundamentals.py` with the filing cut-off moved from 2019-12-31 to
  2025-12-31 and the same rules. Annual refits 2020..2025 as in phase 1. The model's own loaders are pointed at these
  full-period inputs. Reported, not tested: the registered no-fit fallback comp_blend70.
* **M2, M4:** one panel holding the S&P 500 names (2009-2025, as in phase 1) and the 390 current S&P 400 members
  (Alpaca adjusted closes, 2016-2025; current constituents only: survivorship, disclosed), every characteristic built
  by the same code on the combined cross-section. Each year y in 2019..2025 is predicted by a model fitted on all rows
  whose target ended before y (S&P 500 and S&P 400 names together); weekly IC is scored on the S&P 400 names only.
  Reported, not tested: the phase-1 best X1_8p on the same S&P 400 weeks, and each finalist's decile book with and
  without M1's no-trade band.
* A finalist whose code cannot run on the read's inputs is reported as not read, not repaired after seeing data.

**Consequences.** A pass earns a forward paper book (research only). Fail: closed on that panel.

## Result of the phase-2 reads (2026-11-12, `HOLDOUT2_RESULT.json`; locks `READ2_N1.lock`, `READ2_M2.lock`, `READ2_M4.lock`)

| Finalist | Panel | Statistic | Newey–West t | one-sided p | Holm (α 0.05) |
|---|---|---:|---:|---:|---|
| **M2 IPCA (M05_U)** | S&P 400, 2019–2025, 353 weeks, ~332 names | IC **0.0183** | **2.17** | **0.0149** | **passes** (needs 0.0167) |
| M4 unshrunk SDF (S04) | same | IC 0.0033 | 0.86 | 0.196 | fails |
| N1 fundamentals over MASTER | S&P 500, 2020–2025, 303 weeks | increment −0.0001 | −0.02 | 0.507 | fails |

* M2 IC by year 2019 → 2025: .014 .015 .010 .030 −.002 .042 .019 (positive in 6 of 7).
* N1: MASTER's IC on these weeks is 0.0326; the fundamentals blend scores 0.0326 as well. The registered no-fit
  fallback: increment +0.0003 (t 0.11). The development gain (t 2.29) did not survive.
* Reported, not tested: decile book net of 5 bp (harness definition) on the S&P 400: M2 +19.0%/yr (Sharpe 0.45), M4
  +12.9%/yr (0.31). Return levels on a current-members panel are not reliable (below). The band comparison failed to run
  (a bug in the reporting helper, which is not part of the test).

**Survivorship check (descriptive, disclosed; not a test).** The S&P 400 panel holds today's members only, which
conditions on 2019–2025 outcomes (names that left the index by rising, falling or being acquired are missing). The same
M2 model was therefore also run on the point-in-time S&P 500, 2020–2025 (a panel already read in phase 1 for other
models; these predictions had not been seen): IC 0.0121 (t 1.02), decile net −3.3%/yr, correlation with MASTER 0.26,
against MASTER 0.0326 on the same weeks. The S&P 400 pass is real under its registered test, but part of it may
come from the survivorship conditioning or from mid-caps being less efficient; the S&P 500 check cannot tell which.

**Consequences as registered.** M2 IPCA earns a forward paper book (research only), to run on S&P 400 and S&P 500
members with point-in-time membership, which removes the survivorship question going forward. M4 and N1 are closed on
their panels.

## Correction (2026-11-12, after the phase-2 reads): how the phase-2 finalists were actually chosen

Amendment 2 says finalists were "each branch's best by its registered metric among those meeting the t >= 1.5 gate".
That is not what was done. Under that wording, M3 (ca2_c32_k3, t 2.00), M5 (best peer configuration R4, t 2.21) and
M6 (con16_embZ, t 2.08) also qualified and were not named. They were left out because each failed against its own
control in development (factor structure vs direct prediction; graph vs no-graph; embedding vs no-embedding), as
their agents reported. That control rule was not written down, and it was not applied to M2 and M4, which had no
declared control (M2 was +0.0015 over C's ridge on the same characteristics, not significant). The phase-2 reads
themselves are unaffected: each finalist's read was registered before any holdout data was built. But the finalist
set was chosen by an unwritten, unevenly applied rule; the M2 pass should be read with that in mind. Fix for layer 3:
every candidate declares its control in advance, and both rules are written before selection.

Reported only, after fixing a field-name bug in the reporting helper: on the S&P 400 read, M1's no-trade band changed
M2's decile book from +19.2%/yr (Sharpe 0.45) to +15.9%/yr (0.48), and M4's from +13.0% (0.31) to +11.5% (0.33).

## Layer 3, Amendment 1 (2026-11-12, before the universe is built or any of its returns are read)

**Universe (rule fixed now; typed fields only).**
* Symbols: Alpaca assets with `class` = `us_equity`, active and inactive (inactive keeps delisted names), listed on
  `NYSE`, `NASDAQ` or `AMEX` (not ARCA, BATS or OTC); minus every symbol flagged `ETF` = Y or `Test Issue` = Y in Nasdaq
  Trader's `nasdaqlisted.txt` / `otherlisted.txt`; minus the 850 S&P 500 panel names and the 346 S&P 400 names already
  read. Residual risk disclosed: delisted ETFs listed on Nasdaq that no current file flags.
* Prices: Alpaca SIP daily bars, `adjustment=all`, 2016-01-04 .. 2025-12-31.
* Eligibility each session: close above $5, at least 252 sessions of history, and among the 1,500 eligible names with
  the highest 63-session mean dollar volume (close × volume). Point in time by construction.
* Panel: the S&P 500 panel (as in phase 1) plus these names, every field built by `panel400.build`'s code on the
  combined cross-section. Each year y is predicted by a model fitted on all rows whose target ended before y; weekly
  IC is scored on the broad names only.

**Candidates and declared controls.**

| | Candidate | Control (reported as a paired difference, not tested) |
|---|---|---|
| L3a | M2 IPCA M05_U (`M2_ipca/model.py`) | C's Fama-MacBeth ridge on the same 24 characteristics (`C_features/model.py`) |
| L3b | D trees on 4 horizons (`finalists/D_hgb_mh/model.py`) | the same trees on the 5-session target only (`D_ensembles/model.py`) |

**Test (once; `READ3.lock`).** Read window 2017-01 .. 2025-12. For each candidate, mean weekly IC > 0, one-sided
Newey–West t (4 lags); Holm across the two at α 0.05. Power (Step 1): about 65% at a true IC of 0.02.

**Reported, not tested.** Paired difference against the control; IC by year; decile book net of 5 bp with and without
M1's no-trade band; names per week; the share of the universe that is delisted by 2025.

**Consequences.** A pass: replication evidence, added to the case for a forward paper book. A fail: recorded with the
power above; the candidate is not discarded on this read alone if its forward record later says otherwise.

## Layer 3, Amendment 2 (2026-11-12, after the X5 diagnostics, before the L3.1 universe panel is built or read)

**Interpretation of the L3.1 read, fixed now (the test itself is unchanged).** Power at the shrunk IC (X5): D trees
(shrunk IC .0214) about 70%; IPCA (shrunk IC .0151) about 42%. Because IPCA's power is below 50%, a failed IPCA read
is registered now as not evidence against it: forward weeks decide. A failed trees read, at about 70% power, counts
against them.

**Selection rule for every later read** (from X5; adopted as written there, section 6): within a branch choose by
development mean IC (mean increment for track N), never by t, among configurations positive in at least 5 of 7
years; forecast by the shrunk IC over all the branch's logged configurations; rank across branches by shrunk IC; at
most two finalists, each with a declared control; record power at the shrunk IC, PBO (S = 16), the deflated Sharpe
ratio at branch and cumulative counts, and flag a weekly IC sd below 0.6 x the branch median. Every configuration's
predictions are saved from now on. Basis: six finalists, pattern found after looking: adopted as a prudent rule, not
as a validated one.

## Layer 3, Amendment 3 (2026-11-13, before any of these branches is scored): fourth wave, development data only

Owner's request: continue exploring and exploiting with several agents; machine-learning and deep-learning models
accepted. Development file only (2013-2019 validation years, `harness.load()`); no agent opens the broad panel, the
S&P 400 panel or any 2020+ data. Each branch keeps `STATE.json` and saves every configuration's predictions to
`.cache/tree/preds/<branch>/<config>.npy` (Amendment 2). Selection by Amendment 2's rule: development mean IC, positive
in at least 5 of 7 years, shrunk IC across the branch's logged configurations; the branch nominates at most one
candidate, reported with its declared control. No candidate gets a sealed read from this amendment; reads need a later
amendment naming fresh data.

| Branch | Question | Declared control |
|---|---|---|
| Q1_seqnet | Do sequence networks (GRU/LSTM, temporal convolution, a small time-axis transformer) on each name's last 60 sessions of returns, residual returns and volume features add to direct characteristics? | B_arch's best MLP on the same rows (`B_arch/model.py`) |
| Q2_xsattn | Does attention across names within a week (a set transformer, as in MASTER's inter-stock module), or a market-state-gated mixture of experts, beat the same network without it? | the same network with the cross-name attention (or gate) removed |
| Q3_rankgbm | Do learning-to-rank objectives (pairwise/listwise losses in boosted trees or a ranking MLP), monotone constraints or deeper ensembles beat squared-error trees? | D trees on the 5-session target (`D_ensembles/model.py`) |
| Q4_portfolio | Given fixed signals (MASTER, D trees, IPCA, from their saved development predictions), does construction raise net Sharpe or cut drawdown: nonlinear covariance shrinkage (Ledoit-Wolf 2020) with mean-variance long/short weights, turnover penalty, leg vol-matching, volatility-managed scaling (Moreira-Muir 2017), drawdown-conditioned exposure? Metrics: net Sharpe and maximum drawdown at 5 bp. | the decile book with M1's no-trade band on the same signal |

Every configuration is added to `plan` in `STATE.json` before it is scored.

## Layer 3, Amendment 4 (2026-11-13, after the L1 literature review, before the broad panel is built or any of its returns read)

Source: `L1_lit/REPORT.md` (an in-project literature reading by a separate AI session; not an outside review).

**Change to the L3.1 test universe (look-ahead fix).** Eligibility (close above $5; 63-session mean dollar volume)
uses **unadjusted** Alpaca SIP closes and volumes (`adjustment=raw`, `fetch_broad.py raw`); returns and every model
field keep `adjustment=all`. Reason: adjusted past closes embed later splits and dividends, so a name that later
reverse-split passes the $5 filter in the past at a price it never traded (`panel_broad.py`, previous line 38). The
candidates, controls, window, test and Holm step are unchanged.

**Reported, not tested (added to `read3.py`).** (a) Each candidate's and control's IC with delisting returns kept: a
broad name whose last close falls inside the 5-session window keeps a target, the return to its last close then 0
(Alpaca gives no delisting reason, so no Shumway -30%; this bounds the bias from one side only). (b) IC by
dollar-volume tercile of the eligible broad names each week (Avramov-Cheng-Metzker; Gu-Kelly-Xiu: profits concentrate
in small names).

**Disclosure (development panel).** 241 of the 738 S&P 500 names ever eligible in the development file have no price;
on average 136 of 501 eligible names a session are unpriced (146 in 2013, 80 in 2019); 23.5% of eligible Thursday
name-weeks 2013-2019 have no target (checked by the coordinating session from `dev.npz`). The panel's prices omit
names that left the index, which is survivorship bias in every development result and in the 2020-2025 S&P 500
holdout built the same way. Its sign and size are unknown. The broad universe (L3.1) is built from active and inactive
Alpaca assets and does not share it, except for the symbols the bars endpoint rejects (listed in
`.cache/tree/broad/chunks/_dropped.json`, counted in the read).

## Layer 3, Amendment 5 (2026-11-13, after the broad panel's coverage and content check, before any prediction on it)

**Panel as built** (`READ3_PANEL.json`): 3,684 broad names eligible at some point in 2017-2025; 1,500 eligible every
Thursday by construction (1,499 with a target on average); 17.3% inactive at Alpaca, 16.2% with a last bar before
December 2025. 379 symbols the bars endpoint rejects were dropped, 59 of them `*_DELISTED` renames (the one real
survivorship loss); the rest are CUSIP-like ids of non-trading lines.

**Content check** (CLAUDE.md rule 11). Daily moves above 100% in 0.012% of eligible name-days (318 names). The
largest are bad prints: e.g. AQB on 2017-01-09 at $0.144 on 8 shares between closes of $528 and $530, giving 5-day
targets near +179 (17,900%). 95 of 681,939 eligible broad Thursday targets in 2017-2025 exceed ±1 (±100%).

**Change (reported books only).** The decile and band books in `read3.py` earn the target clipped to [-1, 1]. The
registered test (weekly rank IC, Newey-West t, Holm) uses the unclipped target: a rank statistic, which one print
moves by at most one rank position. No print is removed from the panel; the models see the data as a live fund would.

## Layer 3, Amendment 6 (2026-11-13): policy round after the L3.1 read and the combination check

**State.** The L3.1 read passed for the trees and IPCA (step 13). `combo_check.py` (descriptive; both series already
read) found that the broad trees book correlates 0.07 with the fund's 2020-2025 weekly returns. Adding it at equal risk
to the fund's existing stock book (a rule fixed before running) gives Sharpe 1.09 at 5 bp, 1.03 at 10 bp and 0.92 at
20 bp, against 0.94 for the fund alone. The cost of trading the broad names decides the bar.

**Exploitation (coordinating session).**
* **E1, cost study.** Measure the quoted half-spread of the broad names from Alpaca SIP quotes, sampled at a fixed
  time on fixed days chosen by seed. It reads no returns and no predictions, and sets the cost assumption for E2.
* **E2, combined fund, forward only.** Core + MASTER S&P 500 book + broad trees book (L3b candidate, refit yearly) at
  the equal-risk weight, with costs from E1. No past sample remains unread for it, so it is judged on forward paper
  weeks only. It needs the owner's go-ahead (the traded fund is frozen; this would be a research shadow record).

**Exploration (agents, development data only).**
* **Q5_rl.** Reinforcement learning for portfolio construction given fixed signals and other inputs (market state,
  volatility, current holdings, costs). Methods: Moody-Saffell recurrent reinforcement learning (direct differential
  Sharpe), policy gradient or PPO on a small parametric policy (trade rate, exposure, no-trade width as functions of
  state), a per-asset shared-network policy (EIIE-style), and an end-to-end net-Sharpe objective. Signals: MASTER, D
  trees, IPCA (saved development predictions). Declared controls: M1's band book on the same signal, and Q4's
  `mvnl_nt` book. Metrics: net Sharpe at 5 bp, maximum drawdown, turnover; hyperparameters chosen on 2013-2016 only,
  2017-2019 reported separately. Selection by net Sharpe with drawdown no worse than the control. At most one
  candidate is nominated; it gets a read only under a later amendment naming fresh data.
* **N4_news.** The headline download starts now. The branch is launched when the download completes (FEED.md notes).

## Layer 3, Amendment 7 (2026-11-13, before any 2026 price is fetched): the 2026 sealed test of the combined fund (H7)

**Why.** Every past sample is spent for the combination (fund 2020-2025; broad 2017-2025). January to November 2026
has been used by no backtest of it: the research panels end 2025-12-31. (The live forward research books have run
since late October 2026, a few weeks the owner may have seen; disclosed.) Train on data up to 2025, test once on 2026.

**Data (coordinating session; frozen at first fetch, CLAUDE.md rule 4).** Alpaca SIP daily bars from 2025-01-02 to
the fetch date for the broad symbols, the 850 S&P 500 panel names and SPY, both `adjustment=all` and `raw`, into new
folders (`.cache/tree/y2026/`). S&P names and SPY: 2026 daily returns chain-linked onto the panel's 2025-12-31 closes.
The 2025 overlap is used only to check the seam (no scored statistic). Membership: point in time from the repository's
membership files. Broad eligibility: the Amendment 1/4 rule on unadjusted prices.

**Models (fitted on targets ending before 2026-01-01; no 2026 target used).**
* MASTER 5-day: one refit with the October read's configuration and seeds (`sp500_transformers.py`, part `master_h5`),
  training through 2025. The live model (trained to October 2026) is excluded.
* Broad trees: the L3b candidate (`finalists/D_hgb_mh/model.py`), seeds 0-2, on the broad panel through 2025.
* Weeks: Thursdays from 2026-01-08 whose 5-session target is complete by the fetch date.

**Arms.** Fund = 200-session S&P core 1.3×/0.7× + MASTER decile book (gross 0.6, 5 bp), as in `OOS_RETURNS.json`.
* **H7a:** fund + k_a × broad trees decile book (M1 decile, 14 bp a unit traded, target clipped at ±1).
* **H7b:** the same, but the broad book is restricted each week to broad names in the top two-thirds by 63-session
  dollar volume.
* k = the equal-risk weight (sd of the fund's stock book / sd of the broad book), estimated on 2020-2025 weekly series
  (already spent) before the 2026 read. k_a = 0.59 (COMBO_CHECK); k_b computed the same way and written into
  `H7_WEIGHTS.json`, committed before the read.

**Test (once; `H7.lock`).** Per arm: the weekly increment of the combined fund over the fund alone (= k × the broad
book's weekly net return). One-sided Newey-West t (4 lags) of its mean > 0; Holm across H7a and H7b at α 0.05.

**Power, registered.** About 43 weeks. At the 2020-2025 increment (broad book net Sharpe 0.3-0.55 at 10-20 bp), power
is about 10-20%. A fail is therefore not evidence against the combination. "Broken" is declared only if both the broad
trees' 2026 IC ≤ 0 and the increment's mean < 0; then the combination is stopped and reviewed.

**Reported, not tested.** % per year, net Sharpe and worst fall of the fund alone and of each combined arm; IC of
MASTER and of the broad trees; turnover; IC by dollar-volume tercile.

**After the read.** The same pipeline, unchanged, runs on forward weeks as an extension of H7. The cumulative test is
reported every 13 weeks; a verdict at cumulative t ≥ 2 or 104 weeks. A forward runner needs the owner's go-ahead (it
touches the machine that runs the fund).

## Layer 3, Amendment 8 (2026-11-13, before any of these is scored): fifth wave, from the L2 survey and the L3 review

**Basis.** `L2_practice/REPORT.md` and `L3_lit/REPORT.md`: in-project readings, not outside reviews. Model engineering
on the 25-27 price inputs is saturated (Q1, Q2, Q3, Q5 closed). The remaining levers are cost and construction, and
new information. All three branches run on development data only (S&P 500 2013-2019); every configuration is
declared in its `STATE.json` plan before scoring, and every prediction or weekly net is saved.

**Q6_trade: trading less, under a square-root cost model.**
* **Cost model, built first.** Per name and week: half-spread (2.3 bp for S&P 500 names, `COST_STUDY.json`) plus
  k σ_i √(|Δw_i| × AUM / ADV_i). k is from Frazzini-Israel-Moskowitz / JKMP, documented. AUM is $10M per book, with a
  $100M sensitivity. ADV_i is consolidated volume proxied from FINRA total volume (`extra_finra.npz`), with the scale
  documented.
* **Configurations** (signals: trees primary; IPCA and MASTER secondary):
  * controls C0 deciles, C1 M1 band 0.1, C2 Q4 `mvnl_nt`;
  * T1 rank hysteresis (enter at the top or bottom 10%, exit outside 30%);
  * T2 signal decay, score = rank(s_t + 0.5 s_{t−1});
  * T3 = T1 + T2 (the 2×2);
  * T4-T6 Gârleanu-Pedersen partial trading toward the Ledoit-Wolf mean-variance aim, θ in {0.25, 0.5, 0.75}, scaled
    per name by relative ADV;
  * T7 optional: a direct cost-aware weight optimisation in the JKMP spirit, if it fits in the time.
* **No other tuning.** Judged by net Sharpe under the square-root model, with drawdown no worse than C1; flat 5 bp
  also reported.

**Q7_features: industry-relative and announcement-aware reversal.**
* **Added as one set to the D trees:** industry-relative 1/5/21-day reversal; 5- and 21-day industry momentum; 5-day
  reversal with earnings windows masked.
* **A second configuration:** the target horizon per name by turnover tercile (low → 20 sessions, mid → 10,
  high → 5), mapping fixed from Dai-Medhat-Novy-Marx-Rizova and Medhat-Schmeling.
* **Typed inputs** (CLAUDE.md rule 1): sector/industry from `.cache/p8/gics.json` (current classification applied to
  the past: disclosed look-ahead); earnings dates from `.cache/p8/decay_earnings_events.parquet` (source checked and
  documented).
* **Control:** D trees, same hyperparameters. Judged by IC, years positive and decile net.

**Q8_neutral: neutralisation of the weekly score.**
* **Configurations:** partial neutralisation at p 0.5 (Numerai form) against {beta, log ADV proxy, 60-day vol, sector
  dummies}; full sector demeaning, kept only if Ehsani-Harvey-Li's ex-ante rule, computed on 2013-2016, says so;
  applied to trees, IPCA and MASTER.
* **Control:** p 0. Judged by decile net Sharpe at 5 bp and the sd of weekly IC, not mean IC alone.

**Folded into H7 (no new test).**
* **Planning haircut** (McLean-Pontiff; Chen-Velikov): an expected forward Sharpe for the broad trees book of about
  0.7× its out-of-sample figure.
* **Decay check:** rolling 26-week IC, reported every 13 weeks.
* **Execution audit on forward weeks:** official close vs the T−60 s mid for broad names, Nasdaq microcaps split.

**For the owner (rule 17, policy).** A fund-level volatility target across core, MASTER book and broad book, tested
once on long history: proposed, not run.

## Layer 3, Amendment 7a (2026-11-14, after the build, before the H7 read): implementation details fixed

Source: `H7_build/BUILD.md` (the build agent computed no statistic touching 2026 outcomes). The test is unchanged.

* **Books enter 2026 already held.** The fund and the broad book are simulated from January 2025, on 2025 scores from
  the same models (the October MASTER scores; the trees' 2025 refit, equal to the L3.1 read's to 3e-8). Only 2026 weeks
  are scored. Reason: starting flat on 2 January would charge a one-off full entry cost that a running fund does not
  pay.
* **Fetch end:** 2026-11-12, because the data plan refuses the most recent session. Scored weeks are the 2026
  Thursdays with a complete 5-session target.
* **25 S&P panel names without a yfinance close** stay unpriced in 2026, as in every earlier read. 10 are current
  members.
* **Index membership** after 2026-08-18 is carried forward from the last row of the membership file.
* **T-bill rate:** the frozen cache; if it ends before 2026-11, the last value is used. It enters only the fund's
  margin cost (reported figures, not the test).
* **Seam between vendors:** 2026 returns are Alpaca's, chain-linked onto 2025-12-31. 4 current members have a 2025
  Alpaca-yfinance return correlation below 0.99 (FTV, TDG, WDC, LEN); kept.
* **H7b's eligible set** each week: eligible broad names with dollar-volume percentile rank ≥ 1/3 (as `read3.extras`
  ranks; cross-checked against the build's tercile file).
* **Weights:** k_a 0.59, k_b 0.5307 (`H7_WEIGHTS.json`, committed in f3f5376).
