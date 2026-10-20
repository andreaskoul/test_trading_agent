# Pre-registration: the Thesis Tree tests (Protocol 8 evidence)

> **Status: PRE-REGISTERED.** Signed off by the owner on 2026-10-14, in the commit that removed the draft banner.
> That commit comes before any test below was run, before any feature was computed on a validation or sealed sample,
> and before the first R5 prediction. Changes from here on are appended as dated amendments, each stating whether any
> result had been seen.

**Owner's design (2026-10-14).**
* A thesis per firm: its image between quarterly reports, built from its own events, competitors' events, sector
  dynamics (geopolitics, within-sector correlation) and its place in the production funnel.
* Horizons are thesis-driven, not fixed.
* Reassessment on new company or sector news is kept.
* Instrument and hedge choices are a trader's strategic policy and are **not tested here**.
* Free data only.
* S&P 500 and S&P 400.
* Protocol 8 switches as soon as these tests pass.

**Plan and stress test:** the owner-approved plan of 2026-10-14. Its section 1 lists the evidence behind every
prior below.

---

## 0. What this document decides, and what it does not

It decides **which components may enter Protocol 8**. A component enters only if its primary test passes as
specified here, on the samples specified here.

It does not decide:
* instrument choice, hedging or net market exposure (trader's policy, declared in Protocol 8);
* the lifecycle and reassessment *mechanics* (their rules are written in §8 and pre-registered with Protocol 8;
  the decay half-lives they use come from H8);
* any traded book before Protocol 8. Protocol 7 is untouched.

---

## 1. Samples, splits and data rules

| split | dates (by report date or signal date) | use |
|---|---|---|
| **fit** | 2012-01-01 – 2021-12-31 | estimation of any fixed coefficient (e.g. decay half-lives, the SUE → CAR mapping) |
| **validation** | 2022-01-01 – 2025-12-31 | the family-wise test of §6; at most the variants listed here |
| **sealed test** | 2026-01-01 – 2026-09-30 | **read once**, after validation, for the survivors only. Untouched by every earlier study (the technicals backtest ends 2025-12-31) |
| **forward** | from the first R5 prediction | uncontaminated LLM evidence (R5) |

**Universes.**
* **S&P 500**: point-in-time membership (`data/raw/stocks/sp500_membership.csv`).
* **S&P 400**:
  * built from the current list plus documented changes;
  * survivorship is stated, and the share of firm-quarters lost to missing prices is reported;
  * acquired and delisted names missing from yfinance are a known bias, controlled by paired and long-short
    designs.
* Every test is reported for each universe separately. **A universe enters Protocol 8 only on its own result.**

**Point-in-time rules** (enforced by a test that fails the run):
* Each feature row carries `available_ts`, and every row must satisfy `available_ts ≤ decision_ts`.
* **XBRL**: per (firm, concept, period), the value in the earliest filing (`filed`, accession). Later restatements
  are ignored.
* **Report time t0**: the acceptance time of the 8-K with item 2.02.
  * Accepted before 09:30 ET: t0 = that session.
  * Accepted after 16:00 ET: t0 = the next session.
  * Accepted in between: t0 = that session.
  * With no 8-K 2.02, the 10-Q/10-K filing time is used and flagged; such reports are excluded from CAR tests.
* **Text**: 10-K and 10-Q sections by acceptance time. 1993–2020 items come from the HF dataset
  `eloukas/edgar-corpus`; 2021–2026 from EDGAR HTML. The parser is validated on 50 overlap filings
  (≥ 95% of section lengths within 10%).
* **Macro**: first-release vintages from ALFRED.
* **TNIC peers**: the Hoberg–Phillips TNIC-3 file of the fiscal year *before* the signal year. For 2024–2026,
  own 10-K Item 1 embedding similarity, used only if it passes the S1 contract (§7).

**Returns.** Daily total returns.

**Residual return e** (primary): the return minus β_m·r_SPY minus β_s·r_sector, where r_sector is the SPDR sector
ETF return residualised on SPY. Betas are from 252 daily returns ending 21 sessions before the window, Welch
slope-winsorised and shrunk ⅓ toward 1 (as `screen.py`). A market-only residual is reported alongside.

**CAR** = Σ e over sessions t0−1 … t0+1.

**SUE** = (EPS_q − EPS_{q−4}) / sd(EPS_{q−k} − EPS_{q−k−4}, k = 1..8):
* first-filed diluted EPS;
* at least 6 of the 8 differences required;
* winsorised at ±10.

**Season** = the calendar quarter of t0.

**Industry** = the GICS industry, about 70 clusters. This is the cluster for inference.

---

## 2. Inference rules (all tests)

* **One primary statistic per hypothesis**, defined in §4–§5. Everything else is descriptive.
* **Event / report-level tests:**
  * a linear model with **season × GICS-sector fixed effects**;
  * p-values from a **wild-cluster bootstrap** (Rademacher weights, clustered by industry, 9,999 draws);
  * **randomization inference**: the signal permuted within season × sector, 9,999 draws.
  * A test passes only if **both** p-values pass.
* **Monthly portfolio tests:**
  * Fama–MacBeth slopes with Newey–West standard errors (lag 3);
  * plus a long-short decile (or tercile, if fewer than 300 names) spread, net of 10 bp round trip at the
    signal's own turnover.
* **One-sided** in the pre-registered direction.
* **Family-wise:** Holm at α = 0.05 within each family (§6), on validation. Survivors are read once on the sealed
  test, with Holm again among the survivors.
* **Economic significance** is required too: the net long-short spread > 0 on the sample that decides.
* **Stability:** the primary statistic must have the pre-registered sign in both halves of the validation sample
  (2022–23, 2024–25).

---

## 3. The production funnel (frozen with this file)

* The templates are `fund/chains.json`, version 2026-10-14-draft:
  * stages S0 (primary inputs) … S5 (end demand);
  * 12 chains;
  * a service layer outside the funnel.
* Every GICS sub-industry is assigned:
  * S&P 500: 392 firms in the funnel, 111 in the service layer;
  * S&P 400: 293 and 107, from the current list in `data/raw/stocks/sp400_current.csv`.
* The S&P 400 sub-industries were added in the sign-off commit, before any test (`_assigned_at_signoff` in
  `chains.json`).
* **Firm-level overrides:**
  * an LLM reads each firm's 10-K Item 1 and may move the firm to another (chain, stage) with a stated reason;
  * overrides are frozen per fiscal year and spot-checked by the owner (30 firms; ≥ 90% agreement, else the
    override step is dropped and sub-industry defaults are used).

**Propagation signs** (theory, not fitted):
* demand shocks travel upstream, same sign;
* supply and cost shocks travel downstream;
* competitor events are *contagion* (same sign) or *competitive* (opposite sign) by their channel;
* early-to-late reporter sympathy is expected to *over*-react (reverse).

---

## 4. Historical deterministic family H (no LLM)

| id | signal (at decision time) | target | primary statistic, direction | sample / arm |
|---|---|---|---|---|
| **H1 sympathy reversal** | S_i = mean of the late firm's e over each early peer's [t0_p − 1, t0_p + 1], peers = TNIC-3 ∪ same sub-industry reporting ≥ 3 sessions before t0_i in the season; weights ∝ TNIC score (GICS-only peers equal) | CAR_i | slope of CAR_i on S_i, **negative** (Thomas & Zhang 2008) | all late reporters with ≥ 1 early peer |
| **H2 link momentum** | M_i = mean e over the last month of firm i's named customers (from i's 10-K, ≥ 10% customers and customers named in Item 1/7) | e_i over the next month | Fama–MacBeth slope, **positive** | **primary arm: S&P 400 suppliers with ≥ 1 named S&P 500 customer** (size asymmetry; Pinchuk). Run only if ≥ 100 such suppliers per year on average, else reported as underpowered and not tested |
| H2b TNIC momentum | as H2 with TNIC-3 peers, weights ∝ score | e_i next month | FM slope, positive | each universe |
| **H3a funnel lead-lag** | equal-weight e of the chain's stage k+1 (downstream) over month m | e of stage k over month m+1 | pooled FM slope across chains, **positive** (demand travels upstream) | chains in `chains.json` with ≥ 3 firms per stage |
| **H3b inventory bullwhip** | −Δ_yoy(inventory / sales) of stage k+1 (sales-weighted, latest first-filed 10-Q/10-K before decision) | SUE of stage-k firms at their next report, and at the one after | slope, **positive** (downstream inventory builds → upstream misses) | firms in chains with inventory-carrying downstream stages |
| **H4 geopolitical drift** | days in the top 5% of daily GPR innovations (threats and acts separately); sector day-0 residual response R0 | sector residual return over days +1 … +20 | slope of the 20-day return on R0, **positive** (drift) | 11 sectors; season FE replaced by year FE |
| **H5 Lazy Prices** | cosine similarity of the latest 10-K Item 7 / Item 1A (10-Q MD&A) with the same section a year earlier (`gemini-embedding-2`) | e_i over the next 3 months; CAR at the next report (secondary) | FM slope, **positive** (non-changers outperform) | each universe |

**Contracts (not alpha tests):**
* **H6 risk model**: out-of-sample bias statistic in [0.9, 1.1] and min-variance portfolio vol below the
  market-only and GICS-only models.
* **H8 decay**: IC(h) for h ∈ {1, 5, 10, 20, 40, 60, 90, 120} sessions for each passing signal and, for LLM
  evidence, each event type. Half-lives are fitted (exponential) on fit data, reported on validation, and never
  refitted on the sealed sample. They feed the lifecycle (§8).

**Replication checks before any validation read** (they must reproduce the published sign on the published
period, or the code is wrong):
* Cohen–Frazzini customer momentum, 1981–2004 (with the data available);
* Lazy Prices, 1995–2014.

**Placebos, all expected null:** shuffled links (H2), shuffled stages (H3), shuffled peers (H1).

---

## 5. LLM family R (post-horizon replay and forward seasons)

**The model is the production model** (`deepseek/deepseek-v4.1-flash`, as the fund). No LLM output ever sees a
price.

* **R0 Knowledge horizon (run first).**
  * About 240 items over Jan 2025 – Sep 2026: per month, 8 real dated corporate outcomes (a reported quarter's
    revenue direction, completed deals, guidance changes) and 4 matched placebos. Entities are masked; the model
    is asked for the outcome.
  * The horizon is the last month in which accuracy on real items exceeds accuracy on placebos (one-sided
    binomial p < 0.05).
  * The replay window starts at the later of that month + 1 and the model's release date.
* **R1 Quality contracts:**
  * card numbers vs XBRL ≥ 95% exact;
  * E1 channel, sign and novelty vs a gold set of 300 events (labelled by a different model family, with 60 owner
    checks): accuracy ≥ 0.8 and κ ≥ 0.6;
  * duplicate events after deduplication ≤ 5%;
  * kill conditions observable in news ≥ 90%.
* **R2 Ledger faithfulness.** A 10% random audit by a different model family; ≥ 90% of items supported by their
  cited source.
* **R3 The thesis predicts the next report** (primary LLM test).
  * Predictor: the thesis score z_i, centred and standardised within season × sector, at the last decision ≥ 1
    session before t0_i.
  * **Primary target:** 1{SUE_i > season × sector median}.
  * **Primary statistic:** the slope in a linear probability model with season × sector FE, positive.
  * Secondary targets: CAR_i; the residual return over the position's life under §8.
  * **Pass:** both p-values (§2) < 0.05 pooled over **≥ 2 seasons** (replay holdout seasons and/or forward
    seasons), the pre-registered sign in each season separately, and a positive increment of z over the
    deterministic composite (passing H signals), past returns (1 week, 1 month, 3 months) and the mean news tone
    of the quarter.
* **R4 Ablation ladder.** Rungs:
  1. own events;
  2. + text peers;
  3. + named links;
  4. + funnel stage;
  5. + sector state and geopolitics;
  6. + deterministic signals.

  Each rung is kept if its marginal effect on the R3 target passes (Holm across rungs). 1 sample is compared with
  3 at the final rung. **Prior: rung 1 ≈ 0.**
* **R5 Forward seasons** (uncontaminated). The specification below is version `r5-v1`, implemented in
  `fund/r5.py`.
  * **Who.** Every S&P 500 and S&P 400 firm (current lists) with an entry dated D in the Finnhub earnings
    calendar. A firm whose latest 8-K item 2.02 is fewer than 45 days before the cutoff has already reported this
    season and is skipped.
  * **Information cutoff.** C = 22:00 UTC on the last trading day before the **report date D**. This is the date of
    the release itself, *not* t0: an after-close release on D must not be used by the decision for t0 = D+1.
    * News: published ≤ C.
    * Filings: accepted ≤ C.
    * The run may happen any time after C.
  * **Card** (1 call, temperature 0). From the EX-99.1 press release (first 15,000 characters) of the firm's latest
    8-K item 2.02 before C: 3–5 drivers, with what the release said and any guidance; the guidance in numbers; 1–3
    kill conditions.
  * **Own ledger (rung 1).**
    * Input: Finnhub company news in (that release, C], deduplicated:
      * exact headline;
      * token-set Jaccard ≥ 0.7 within 3 days;
      * at most 60 items, each a headline plus its summary cut to 150 characters: the last 30 days in full, older
        items sampled evenly in time.
    * The three passes run concurrently. A pass that fails (time limit, empty or invalid answer, after the client's
      retries) is dropped.
    * 3 passes at temperature 0: two wordings plus the first wording with the items shuffled.
    * Each pass lists events: driver, direction (−1/0/+1 against what the last release set up), size (1–3),
      hard/soft, new/recap.
    * Pass score = Σ over **new** events of direction × size × (1.5 if hard) / √(1 + n_new).
    * **score_own** = the median over the passes that succeed (≥ 2 needed).
  * **Peers (rung 2).**
    * Input: the current-season EX-99.1 releases (first 4,000 characters) of up to 5 same-sub-industry universe
      firms whose 8-K 2.02 was accepted within 45 days before C (most recent first).
    * 3 passes; peer order reversed in the third.
    * Each peer gets a channel (contagion / competitive / none), direction (−1/0/+1 for the firm), size (1–3) and a
      driver.
    * Pass score = Σ over peers with a channel of direction × size / √(1 + n).
    * **score_peer** = the median over passes; missing if no peer has reported.
  * **score_combined** = score_own + 0.5 × score_peer (score_peer counted as 0 when missing). This is the R3
    predictor z for forward seasons; score_own and score_combined are R4 rungs 1–2.
  * **Secondary, descriptive:** the majority "above / inline / below" call, and the Finnhub consensus (EPS and
    revenue estimates) as fetched at decision time. That consensus is also kept as a free, point-in-time
    expectation for SUE-against-consensus robustness.
  * **No price** is given to any call. Stock moves, ratings and price targets are excluded by instruction.
  * **Record and timestamp proof.**
    * One file per report date: `fund_state/live/research/r5/<D>.json`. It is append-only per ticker, and each
      record carries its SHA-256 (canonical JSON) plus a batch SHA-256.
    * Pushed to the orphan branch `research-data`, separate from the fund's records so research never races the
      fund's jobs.
    * The batch hashes are posted as a comment on the R5 timestamp-log issue.
    * **A prediction counts only if the earlier of GitHub's push time and the comment time precedes the 8-K item
      2.02 acceptance time.** This is audited automatically. Unknown or failed records count as missing, never as
      a prediction.
  * **Start.** The Q3-2026 season starts with the first run after this commit. Firms that have already reported
    are skipped and never back-filled. The forward record is test-only: prompts and weights are not changed within
    or between forward seasons except by a dated amendment, and the amendment's first season is analysed
    separately.

**Tuning discipline.** Prompts and aggregation weights may be developed only on replay seasons marked *tuning* in
the R0 report: the first post-horizon season. Every later season, and every forward season, is test-only.

---

## 6. Families and decision rule

* **Family H**: H1, H2, H2b, H3a, H3b, H4, H5 (7 primary statistics). Holm at 0.05 on validation; survivors are
  read once on the sealed test, with Holm among the survivors.
* **Family R**: R3, then the R4 rungs (sequential: a rung is tested only if R3 passes).
* **Inclusion in Protocol 8:**
  * an H signal that passes its sealed read, by universe;
  * the LLM thesis desk only if R3 passes over ≥ 2 seasons; its link layers only for the R4 rungs that pass;
  * H6 and the R1/R2 contracts are prerequisites for whatever uses them.
* **Fallbacks:**
  * R3 fails and H passes → a deterministic network and filings book, with the LLM restricted to extraction;
  * R3 passes but no link rung passes → the thesis desk stays in shadow and Protocol 8 does not use links;
  * nothing passes → no Protocol 8, and this file's results are published as they are.
* **Expected power** (stated so a null is read correctly):
  * R3: about 900 firm-reports per season; with a 55% centred hit rate, t ≈ 3 per season.
  * H1/H5: thousands of firm-quarters; the expected effects are small after publication (−58% on average,
    McLean & Pontiff).
  * A validation pass is not expected for every H; most are expected to fail in the S&P 500.

---

## 7. Node contracts (prerequisites, not alpha)

| node | contract |
|---|---|
| S1 own text peers (2024–26) | top-10 Jaccard ≥ 0.5 against TNIC-3 on 2019–2023 |
| S2 named links | precision ≥ 0.9 on 200 hand-checked firm-years |
| S3 overrides | ≥ 90% owner agreement on 30 firms |
| H6 risk model | bias statistic in [0.9, 1.1]; min-variance vol below the alternatives |
| R1, R2 | as in §5 |

---

## 8. Not tested here; written now so it can't drift (pre-registered with Protocol 8)

* **Horizon.**
  * A position carries α_t: the Q4 forecast at entry, decayed at the H8 half-life of its evidence type, and
    refreshed by new ledger evidence.
  * It is held while |α_t| > round-trip cost + a fixed margin, sized continuously with a 25% no-trade band.
  * The firm's own report forces re-underwriting (continue, extend, flip or close).
  * Mechanical expiry needs **both** 8 weeks with no supporting evidence **and** α below the hurdle.
  * A catastrophic residual stop at −3·σ_e·√(days held) is a risk control, never tuned.
* **Reassessment protocol** (kept and extended).
  * Triggers:
    * the firm's own deduplicated news touching a driver;
    * propagated peer, chain, sector or geopolitical evidence touching a driver;
    * scheduled milestones;
    * the firm's report;
    * an unexplained residual move (|e| > 2.5σ_e with no new event): a trigger to look, never an exit by itself.
  * The check is the existing 3-pass kill check: matched in ≥ 2 → exit; partial in ≥ 2 → trim to half.
  * Adds need new hard-number evidence in ≥ 2 passes.
* **Announcement risk.** Per name, |w|·σ̂(|CAR|, last 8 reports) ≤ 30 bp NAV; per week ≤ 150 bp, allocated by
  α/σ when it binds.
* **Instruments and hedging.** The trader's policy (hold only the risk the thesis is about):
  * SPY for beta;
  * sector or industry ETFs or peer baskets for sector and cluster risk;
  * ETFs as the instrument for sector views;
  * net exposure is the owner's standing choice.

  Not tested, by design.

---

## Sign-off

| | |
|---|---|
| Owner | ☑ signed 2026-10-14 ("Confirmed"), in the commit that removed the draft banner |
| Variants not listed here are not run | ☑ |
| S&P 400 sub-industry assignments added before any test | ☑ (`fund/chains.json`, `_assigned_at_signoff`) |
| R5 v1 specified before the first prediction | ☑ (§5, this commit) |

---

## Amendment 1 (2026-10-16): R5 input and robustness defects; r5-v2

**Written before any outcome of the affected firms was examined.** Every criterion below is mechanical: document
type, content and logged statuses. None depends on a return or a reported result.

**What happened** in the first two R5 runs (15 and 16 Oct, 20 firms; `fund/r5.py` v1):

1. **Wrong input document (7 records).**
   * v1 chose the press release by file name and, failing a match, used the 8-K itself.
   * For CFG, CMC, FHN, JBHT, PNC, USB and TRV the card was therefore written from the 8-K cover page (3–10k
     characters of form text), not from the EX-99.1 release.
   * CFG failed loudly: the model correctly found no drivers.
   * The other six were recorded as `ok`, with generic cards (1–4 numbers, against 10–34 from real releases).
   * Peer blocks were chosen by the same rule.
2. **Transport (1 record).** SCHW lost 2 of 3 ledger passes, to a dropped connection (`IncompleteRead`) and a time
   limit across unpinned hosts. Nothing re-ran them, so the median had one pass and the record failed.
3. **Diagnosability.** Rejected raw answers were not logged.

**How the v1 records are treated.**
* A v1 record enters the primary R3/R4 analyses only if:
  * (a) its card source is the filing's document of declared type EX-99.x and that document passes
    `guards.release_check`, recomputed on the same accession; and
  * (b) every peer release it used meets the same test.
* Records failing (a) are excluded. By this rule that is CMC, FHN, JBHT, PNC, USB and TRV.
* Records failing only (b) enter rung 1 (score_own) and are excluded from analyses that use score_peer or
  score_combined.
* All excluded records are reported in a sensitivity analysis.
* CFG and SCHW stay missing. Nothing is back-filled.

**r5-v2** (from the first run after this amendment is merged):
* The release is chosen by declared SEC type: EX-99.1, else the first EX-99.x, from the filing index. It is
  **never** the primary 8-K.
* It must pass the press-release content contract (`guards.release_check`). If not, the record is
  `input_defect`: no LLM call, and it counts as missing.
* Peer releases are held to the same contract; a defective peer is left out and listed in `peer_defects`.
* **Card grounding.** If the card states ≥ 3 numbers, ≥ 60% must appear in its release. Otherwise the record is
  `card_ungrounded` and counts as missing.
* After a schema rejection, the call gets **one repair turn**: the same material, plus the validator's message.
  It is flagged `repaired`.
* A failed ledger or peer pass is **re-run once**, flagged `rerun`.
* Every rejected answer and transport error is logged, with its provider.
* **Run quality gate.** If input defects plus failures exceed 25% of the firms attempted (from 4 firms up), the
  run fails *after* its records are saved and committed. The runner then opens an issue and texts the owner.

**Unchanged:** prompts, scores and weights, the cutoff rule, the universe, the record and timestamp proof.
Because the mapping from a valid input to a score is unchanged, valid v1 records and v2 records are pooled. A
sensitivity analysis excludes records with `repaired` or `rerun` passes.

---

## Amendment 2 (2026-10-17): the quant validation function, and lessons from the quant trials

**What had been seen.**
* No result of any P8 test (H or R family, node contract) has been seen. No P8 feature has been computed on the
  validation or sealed sample.
* **Disclosure.** The separate quant trials (branch `research/quant-trials`,
  `reports/research/quant_trials/DECISION.md`) tested a news-embedding return model on 31 large caps. They read
  2022–25 once, under their own pre-registration (commit 8de9271), and failed.
* That model is not a P8 hypothesis. The sealed Jan–Sep 2026 window was never loaded.
* This amendment changes **no** hypothesis, primary statistic, family, split, sample or pass rule.

**Decision (owner, 2026-10-17).**
* No standalone quant signal desk. The news-embedding return model is closed (failed confirmation; 2022 broke
  every candidate) and is not a P8 node.
* The quant function becomes P8's **validation team**. It owns T7 (measurement and learning: node tests, trial
  ledger, the sealed read) and the neutrality checks behind P1/S5. It also maintains the test harness built for
  the trials: point-in-time tests, twins, placebos, a ledger, and a guarded single-read runner.

**Practices added to every deterministic P8 test.** These are reporting and process only; the primary statistics
in §4 and the rules in §2 are unchanged.
1. **Trial ledger.** Every fitted variant is logged, failures included. The count is stated in the sealed-read
   report.
2. **Twins.** Each signal is reported next to a no-signal twin (same model, signal removed) and a placebo (signal
   permuted across names within date). This sits alongside §2's randomization inference.
3. **Sector-neutral and regime reporting.**
   * Every result also shows its sector-neutral version and per-year values, with 2022 on its own row.
   * 2020–21 is flagged as the COVID regime.
   * A descriptive "fit excluding 2020" row is added.
   * A signal whose gain disappears sector-neutral is labelled a sector tilt, not a firm-level signal.
4. **Model selection.**
   * Hyper-parameters are chosen within the training window by validation rank IC, never by MSE early stopping.
     In the trials, MSE early stopping left gradient-boosted trees with 1–30 trees.
   * Return models are shallow and regularised: ridge, or trees of depth ≤ 3.
   * Deep nets (MLP, transformers, cross-sectional attention) are not used for return prediction without a new
     amendment. They added nothing over their placebos in the trials.

**Design input (no change to the tests).**
* Propagation (E2) uses named links (S2), not embedding similarity. In the trials, text-to-return Granger edges
  between the 31 names were almost absent: 0–7 of 930 pairs at FDR ≤ 0.10.
* Embedding similarity stays where §7 puts it: peer identification (S1).

**Optional, not scheduled.** A shadow-only forward log of the trials' best residual: ridge, h = 10, cluster news
state, 31 names, a sector-neutral increment of +0.02 (t 1.7, not significant).
* It is never traded and is not a P8 node.
* It runs only on a separate go-ahead from the owner.

**Refit rule (added 2026-10-17, owner).** From the refit-cadence study (`reports/research/quant_trials/REFIT.md`):
* Quarterly refits on a 2-year rolling window cut the 2022 loss of the news model to about 0.
* Expanding windows were needed for the price factors: +0.067 IC at h = 20 in 2022–25, against +0.009 on a
  2-year rolling window.

So, for every P8 return model (deterministic nodes and Q4 combinations):
* **Refit quarterly** (first session of each calendar quarter), with an h-session embargo.
* **Expanding windows** by default. A rolling window needs a pre-registered reason.
* Encoders (topic clusters, PCA) are refit at the same quarterly dates, on text from before the refit date only.

**Owner's choice of research shadow models (2026-10-17).**
* The news model: the five quant factors plus the decayed-headline topic state, ridge tuned on rank IC,
  quarterly expanding refits, at **h = 10**.
* The quant model: the five price factors refit by ridge, quarterly expanding, at **h = 20**.

Both are research shadow books (see `PROTOCOL_fund.md` and the shadow amendment). They are never traded, and they
are not P8 nodes unless a later amendment admits them on evidence.

## Amendment 3 (2026-10-19, signed 2026-10-20): transformer research arms; market exposure lines

Written before any transformer outcome on the S&P 500 or on the news panel exists.

**What changes.** Amendment 2 §4 bars deep nets from return prediction without a new amendment. This amendment
admits exactly three transformer models as **research arms only**: MASTER, the Temporal Fusion Transformer and
Chronos-2. They run under `reports/research/PREREG_quant_transformers.md`:
* a single pre-registered S&P 500 read on factors only, against an annually refit ridge (Holm over 3 models × 3
  horizons);
* a forward research book on the 31-name news panel only for a model that passes that read.

**What does not change.**
* They are never traded and are not P8 nodes. Admitting one as a node needs a later amendment on forward
  evidence.
* §4's model-selection rule applies: settings by validation rank IC, never MSE.
* The sealed Jan–Sep 2026 window stays sealed.

**Market exposure lines (owner policy, 2026-10-19; PROTOCOL_fund.md "Market exposure").**
* The research books are also reported on top of SPY: 1x, and the owner's dynamic sleeve (1.3x SPY above the
  200-session average, 0.7x otherwise, the rest at the T-bill rate).
* The yardsticks are SPY buy-and-hold and a risk-matched SPY.
* All books stay long/short.
* The sleeve is a stated policy, not a tested or tuned parameter, and is not a P8 input.

**Owner sign-off:** signed by the owner in session, 2026-10-20 ("Signed").
