# Pre-registration: the Thesis Tree tests (Protocol 8 evidence)

> **Status: DRAFT for the owner's sign-off.**
> * This file becomes the pre-registration in the commit that removes this banner. That commit must come before
>   any test below is run, and before any feature is computed on a validation or sealed sample.
> * Until then, only data plumbing runs.
> * After sign-off, changes are appended as dated amendments, each stating whether any result had been seen.

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
* Every S&P 500 GICS sub-industry is assigned (392 firms in the funnel, 111 in the service layer). S&P 400
  sub-industries not yet listed are assigned in the sign-off commit, by the same reading, before any test.
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
* **R5 Forward seasons** (uncontaminated).
  * For every S&P 500 and S&P 400 firm with a report expected in the window:
    * the desk writes z_i at 22:00 UTC on the session before t0_i, from information to that time;
    * it commits the prediction file to `fund-data` under `research/r5/<date>.json`, with SHA-256 of each record.
  * A prediction counts only if the git commit time is earlier than the 8-K 2.02 acceptance time. This is audited
    automatically.
  * The Q3-2026 season starts as soon as the minimal desk works. Firms that have already reported are skipped,
    never back-filled.

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
| Owner | ☐ signed (date, commit) |
| Variants not listed here are not run | ☐ |
| S&P 400 sub-industry assignments added before any test | ☐ |
