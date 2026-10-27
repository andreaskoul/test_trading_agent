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

## Amendment 3 (2026-10-19, draft for owner sign-off): transformer research arms; market exposure lines

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

**Owner sign-off:** _pending_

## Amendment 4 (owner, 2026-10-26): power of the decision rule, §8's open values, data rules

**What had been seen.** No P8 test result. No P8 feature has been computed on validation (2022–25) or sealed
(2026) data. Prices were fetched only to 2025-12-31 and inspected for coverage only, not for returns. The basis is
`reports/research/P8_readiness_2026-10-26.md`, whose power figures come from a Gaussian model with no data
(`reports/research/p8_power.py`).

**Why.** As registered, a monthly signal needs a true annual Sharpe of about 2.0 for a 50% chance to pass:
the 9-month sealed read alone needs 2.9 for 80% power. The rule spends about 0.25% family-wise false-positive
risk against the nominal 5%. The owner chose the option in readiness §6.1 ("go", 2026-10-26).

**1. The sealed read (replaces §2's and §6's sealed-test rule).**
* Validation is unchanged: Holm at 0.05 within each family, both p-values (§2), the stability halves and the net
  spread > 0.
* **A validation survivor passes the sealed read if its primary statistic has the pre-registered sign on the
  sealed sample, and its net long–short spread there is > 0** (for event-level tests: the slope's sign).
  No significance threshold applies on the sealed sample, and Holm among survivors is dropped.
* Its p-values on the sealed sample are still computed and reported.
* Effect, under the readiness model: at a true annual Sharpe of 1.0 the overall pass rate rises from 0.07 to
  0.26. The false-positive rate per null signal rises from 0.0004 to 0.0038, still below 0.05/7.

**2. §8's open values, fixed before any α exists.** These are textbook rules, not fitted:
* **α (the Q4 forecast).** α_{i,t} = σ_{e,i} · Σ_k (1/K) · IC_k · z_{ik,t}. This is Grinold's α = IC × volatility
  × score, with equal weights over the K signals that entered P8.
  * z_{ik,t} is signal k's score for firm i, standardised cross-sectionally per date.
  * IC_k is signal k's rank IC on fit data at its H8 horizon.
  * σ_{e,i} is firm i's residual volatility over that horizon (EWMA, span 60, as Protocol 7).
  * There are no fitted combination weights. Once R3 passes, the LLM thesis score enters as one more k.
* **The margin.** Hold while |α_t| > c + m, with c the round-trip cost and **m = c**. That is 20 bp for the
  S&P 500 (2 × 10 bp) and 40 bp for the S&P 400 (2 × 20 bp; mid-cap costs taken as twice the measured S&P 500
  cost).
  * The holding time is then t* = τ · log₂(|α₀| / 2c), where τ is the signal's half-life.
  * The rule is not tuned on results. A different m needs a later amendment.
* **No passing signal, no horizon.** If no H signal enters, P8 has no α and nothing is traded under §8. The
  pre-registered fallbacks (§6) are unchanged.

**3. Data rules (readiness §2), fixed before results.**
* **D1 prices:** Alpaca SIP bars (adjusted for splits and dividends), with ticker changes resolved by CUSIP,
  from 2016. yfinance before 2016, marked as fit-only and survivorship-biased. Coverage is reported per year
  (`reports/research/p8/D1_coverage.md`).
* **D2 delisting:** the last traded close stands. Delistings are counted per year.
* **D3 GICS:** today's classification, with a robustness row that excludes Communication Services and Real
  Estate before their creation dates (2018-09-28 and 2016-08-31).
* **D4 sector residual:** before XLRE (2015-10-08) and XLC (2018-06-19), names in those sectors use the
  market-only residual, flagged.
* **D6 Q4 EPS:** Q4 net income over Q4 average diluted shares (FY minus Q1–Q3 for both), flagged as derived.
* **D7 peers:** H1 and H2b are also reported on own-embedding peers for 2022–23, where both peer methods
  exist. The registered statistic is unchanged.
* **D10 replication:** Cohen–Frazzini is replicated on the earliest window that EDGAR's 10-K text and the price
  data allow, with survivorship stated. If no window has ≥ 120 months, the placebo checks are the gate for H2.

**Unchanged:** every hypothesis, direction, primary statistic, family, split and sample, and the R family.

**Owner sign-off:** ☑ 2026-10-26 ("go", on the recommendation in readiness §6).

## Amendment 5 (2026-10-27): data feasibility, validated inference, and the operational definition of each H test

**What had been seen.** No H statistic, on any sample. Seen so far, and listed here:
* data coverage (`reports/research/p8/D1_coverage.md`, `D5_D6_coverage.md`);
* the simulation validation of the inference code (`inference_validation.txt`), which uses no market data;
* the descriptive earnings-decay curves on fit data (`decay_earnings.md`). These use SUE and CAR, which are
  not H signals.

Each rule below is fixed before its statistic exists.

### A. Data feasibility (verified 2026-10-26/27)
1. **TNIC-3 cannot be joined.** The Hoberg–Phillips files are keyed by Compustat gvkey only (`Readme_tnic3.txt`:
   the CIK merge used a WRDS mapping). No free gvkey↔CIK link exists, so the free-data rule excludes TNIC.
   * **H1** uses same-GICS-sub-industry peers only, with equal weights. The registered text already includes
     these peers.
   * **H2b cannot be run.** It enters Holm with p = 1, and the family size stays m = 7. The S1 contract
     (own-embedding peers validated against TNIC) cannot be evaluated, so own-embedding peers are not used.
2. **Delisted firms without a CIK.** 162 symbols have no CIK in any declared SEC field (SEC's ticker file is
   current-only). They are typed defects, counted missing, never matched by name. Coverage of S&P 500 member
   firm-years with a CIK is 76% (2012) to 97% (2025), and 93–97% in validation. The bias is stated with every
   result.

### B. Inference (`research/p8/inference.py`; validated by `research/p8/test_inference.py`, commit b5243cc)
1. **Event-level p-value** = max(p_WCR, p_RI), each with B = 9,999. A test passes only if both pass (§2).
   * WCR is the wild cluster restricted bootstrap with the null imposed. It uses Rademacher weights when there are
     more than 12 clusters, and Webb's six-point weights otherwise: Rademacher has only 2^G distinct draws, and
     H4 has 11 sector clusters.
   * Simulated size at one-sided 5% (R = 300): WCR 0.057, RI 0.053, both 0.050; i.i.d. OLS 0.067.
2. **Fama–MacBeth p-value.** It comes from the simulated small-sample null distribution of the Newey–West(3) t at
   the same T, not from t(T−1). At T = 48 the t(T−1) reference over-rejects: 0.066 under i.i.d. and 0.081 at
   AR(1) 0.3. The calibrated reference gives 0.057 and 0.070, matching Kiefer–Vogelsang (2005) fixed-b.
3. **Holm** over m = 7. A hypothesis not run enters with p = 1.
4. **Stability:** the primary statistic (β, or the mean FM slope) has the registered sign in 2022–23 and in
   2024–25 separately.
5. **Economic significance.**
   * Event tests: per season, the signal (direction-signed) is sorted into terciles. The net spread is the
     mean target of the top tercile minus the bottom tercile, minus 20 bp (one 10 bp round trip per leg).
     It must be > 0.
   * Where the target is not a return (H3b), the spread is taken on CAR at the same report.
   * FM tests: as in §2.

### C. Operational definitions
Common elements, for all tests:
* **Residual:** e is the §1 residual (`research/p8/residuals.py`).
* **Report session:** t0 is the §1 report session (`research/p8/events.py`).
* **Sample:** S&P 500 at t0 (point in time) and the current S&P 400 list, each reported separately as §1
  requires.
* **Cells and clusters:** cells are season × GICS sector; clusters are the GICS industry (74, from
  `research/p8/gics.py`).

**H1 sympathy reversal** (event-level, sign −).
* For a report of firm i at t0_i, its early peers P_i are the same-sub-industry firms whose t0_p lies in the same
  calendar quarter as t0_i and ≤ t0_i − 3 sessions.
* S_i = (1/|P_i|) Σ_p Σ_{s = t0_p−1}^{t0_p+1} e_{i,s}: the late firm's own residual return around its early peers'
  reports.
* Target: CAR_i = Σ_{s = t0_i−1}^{t0_i+1} e_{i,s}.
* Reports with |P_i| ≥ 1 enter.

**H3a funnel lead-lag** (monthly FM, sign +).
* Firm-month residual: e_{i,m} = Σ of daily e in calendar month m. The betas use the §1 window ending 21
  sessions before the month.
* Each (chain, stage k) membership of firm i, for k = S0…S3, gives one row in month m:
  * signal: the equal-weight mean e_{j,m} over firms j ≠ i in stage k+1 of the same chain;
  * target: e_{i,m+1}.
* Rows enter only if stages k and k+1 of the chain each have ≥ 3 firms with returns that month.
* The FM slope is computed per month over all rows. The L/S legs are firms, de-duplicated by keeping each firm's
  first row in chain order.

**H3b inventory bullwhip** (event-level, sign +).
* Inventory/sales of a firm-quarter: InventoryNet over the quarter's revenue. Both are first-filed, by fixed
  concept preference:
  * inventory: InventoryNet, then InventoryGross;
  * revenue: Revenues, RevenueFromContractWithCustomerExcludingAssessedTax, SalesRevenueNet.
* Signal for a report of a stage-k firm at t0_i: the revenue-weighted mean of −Δ_yoy(inventory/sales) over the
  firm's stage-k+1 chain partners.
  * Each partner's value comes from its latest quarter whose first filing was accepted ≤ t0_i − 1 session.
  * Δ_yoy is against the quarter 4 earlier.
  * At least 3 partners are required.
* Target: SUE_i at t0_i (primary). The SUE at the next report is reported alongside as the registered
  secondary. The economic spread uses CAR at t0_i.

**H4 geopolitical drift** (event-level, sign +).
* Innovations: for each of GPRD_THREAT and GPRD_ACT (daily file, SHA-256 1e8799c8…6dea, frozen at first use),
  ε_t is the residual of an AR(5) on log(1 + index). It is estimated once on 2012–2021 sessions, with
  coefficients fixed.
* A shock day is a session with ε_t above the 95th percentile of fit-sample ε, for either sub-index (a day in
  both counts once).
* Event: (shock day d, sector s), for the 11 SPDR sector ETFs from their inception.
  * R0: the sector's residual return on d, r_ETF − β r_SPY, with β per §1.
  * Target: Σ_{d+1}^{d+20} of the sector residual.
* FE: year. Cluster: sector (11; Webb weights).
* Threats and acts are reported separately as descriptives. The primary is the pooled set.

**H5 Lazy Prices** (monthly FM, sign +).
* **Similarity:** the cosine similarity of term-frequency vectors, Cohen–Malloy–Nguyen's (2020) primary
  measure, replaces `gemini-embedding-2`.
  * Reason: embedding about 25,000 sections of 10–20k tokens costs ~$75, several weeks of the owner's whole
    $13/week LLM budget.
  * The term-frequency measure is the published one.
  * An embedding version needs the owner's approval of the spend, and is then reported as a secondary.
* **Text:**
  * 10-K Item 7 and Item 1A, and 10-Q Part I Item 2, parsed from EDGAR HTML for every year by one parser;
  * §1's 50-filing check against `edgar-corpus` (2012–2020);
  * lower-cased, alphabetic tokens of ≥ 3 letters, no stop-list.
* **Signal:** at each month end, firm i's mean similarity over the available sections of its latest filing
  against the same section of the same form a year earlier.
* **Target:** Σ e over months m+1 … m+3. The overlap is covered by NW(3).

**H2 link momentum** (monthly FM, sign +). This test runs only if both gates pass:
* **Customers:** named in the supplier's 10-K, where a sentence of Item 1, Item 7 or the notes states the
  customer's share of revenue as ≥ 10%.
* **Matching:** the customer is matched to a universe CIK only by exact equality of the normalised company
  name with SEC's current or former registrant names (submissions `name`, `formerNames`).
* **Contract S2:** precision ≥ 0.9 on 200 randomly drawn firm-years, each checked against the quoted sentence.
  The checks are logged.
* **Power gate (registered):** ≥ 100 S&P 400 suppliers per year on average with a named S&P 500 customer.
  Otherwise H2 is reported as underpowered and enters Holm with p = 1.

**Replication checks** (before any validation read; Amendment 4 D10).
* The published sign of Lazy Prices and of customer momentum (H2's mechanism) must reproduce on the fit sample
  2012–2021. Their published periods (1995–2014, 1981–2004) need delisted returns that free data lack.
* The registered placebos are run on fit data for H1, H2 and H3a.

**Order.** Every H test that can run is finished, its code committed, and its fit-sample results reported before
the single validation read of the whole family. No test is read on validation alone.

**Owner sign-off:** standing instruction of 2026-10-26/27 ("Go. Be meticulous and with academic and mathematical
rigor"). Two items are flagged for the owner, who can reverse either before the validation read: H5's similarity
measure (A cost), and H2b's exclusion (A1).

## Amendment 6 (2026-10-27): the §1 parser check is made on section boundaries

**What had been seen.** Only the parser check itself (`reports/research/p8/sections_validation.md`). No H5 or H2
statistic exists. Fit-sample results of H1, H3a, H3b and H4 had been recorded (`fit_results.md`). They do not
involve filings text.

**Change.** §1's check ("≥ 95% of section lengths within 10%" against edgar-corpus on 50 overlap filings) is
replaced, for both the parser and H5/H2, by **≥ 95% of sections whose start and end boundaries agree with
edgar-corpus**.
* The start boundary is the same first 8 alphabetic words.
* The end boundary: the last 8 words of one side lie within the last 400 of the other.
* A reference section is excluded only where it is demonstrably truncated, each case listed with its evidence.

**Reason.** The length criterion compares two text conversions, not two parsers. edgar-corpus keeps some table text
and drops some, so equal boundaries give lengths 15–40% apart in both directions. The criterion was failed for
that reason (86.8%), while the boundaries agree in 96.6% of the comparable sections (85/88). The registered
length figure is reported with every H5 and H2 result.

**Owner sign-off:** standing instruction of 2026-10-26/27. This is flagged for the owner, who can reverse it before
the validation read; H5 and H2 would then enter Holm with p = 1.
