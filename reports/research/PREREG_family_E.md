# Pre-registration: Family E — event modules for the next operations flow, and the soft-news rule

> **Status: PRE-REGISTERED.** The owner approved this design on 2026-10-30 (the evidence-gated operations-flow plan).
> This file is committed **before any Family E data is loaded or fetched**: no 8-K item list beyond item 2.02, no
> Finnhub shock list, no 2026 price extension and no Family E statistic exists at the commit. Changes from here on are
> appended as dated amendments, each stating what had been seen.

Companion documents:

* [PREREG_thesis_tree.md](PREREG_thesis_tree.md): P8's alpha formula, sizing and holding rules, and the R5 read.
* [DATA_USE.md](DATA_USE.md): every window read, by hypothesis and lock.
* `reports/Fund pipeline against research and forums.md` and `reports/Order timing literature and practice.md`:
  the priors.

## 0. What this decides

1. **Admission** of three candidate modules for the next operations flow: post-release earnings continuation (E1),
   continuation after hard 8-K events (E2), and the earnings pre-release forecast (E4, R5's economic test). A module
   that is not admitted gets zero weight in the alpha combination.
2. **Soft-news entries in the live book** (rule A → Protocol 7B Amendment 3), from study E3.
3. **Rules registered now, applied later:**
   * promotion of the new flow to the traded protocol (rule C);
   * go-live sizing (rule D);
   * the programme stop date.

It does not decide instruments, the hedge or net market exposure; those are owner policy.

## 1. Samples, hygiene and locks

| split | dates (event session) | universe | use |
|---|---|---|---|
| fit | 2016-01-01 – 2021-12-31 | S&P 500, point in time | selection by the written rules below, descriptive statistics; no lock |
| validation | 2022-01-01 – 2025-12-31 (target windows fully observed by 2025-12-31) | S&P 500, point in time | **one locked read**: `reports/research/p8/E_VALIDATION.lock` |
| sealed | 2026-01-01 – 2026-09-30 | S&P 500, point in time | **one locked read** for survivors: `reports/research/p8/E_SEALED.lock` |
| soft-news holdout | 8-K events 2022–2025; Finnhub shocks 2026-05-01 – 2026-10-31 | S&P 500 | **one locked read** for rule A: `reports/research/p8/E_SOFT_READ.lock` |

Hygiene:

* **What has been seen.** 2012–2021 SUE drift has been seen (`p8/decay_earnings.md`), so the fit sample serves
  selection only. 2022–2025 has been read for other hypotheses (34 reads, listed in DATA_USE.md); Family E's
  hypotheses have not.
  * Admission therefore also needs the sealed 2026 check.
  * The report gives, as a diagnostic, the Bonferroni p over all hypotheses ever read on the window.
* **S&P 400.** Results (current list, current GICS) are descriptive only, never an admission.
* **Lock files.** Each is written first, with the commit hash and UTC time. A second read refuses to run.
* **Data.**
  * Prices: Alpaca SIP daily bars with `adjustment=all`, delisted names included (`research/p8/prices.py`), extended
    through 2026-10-31 for the sealed and soft windows. Opens are added to the fetch for the open-entry
    descriptive.
  * Membership: `data/raw/stocks/sp500_membership.csv`.
  * Filings: SEC bulk `submissions.zip` (`research/p8/edgar.py`).

  A firm without a CIK has no events (coverage in `p8/D5_D6_coverage.md`).
* **Residuals.** $e = r - \beta\,r_{SPY}$, with β the shrunk Welch beta of `research/p8/residuals.betas` (252
  sessions ending 21 sessions before the event). The sector-residual variant is reported, not used for a decision.

## 2. Information time and entry points

Info time is when the fund could have acted:

* **8-K events:** `accepted_et` from EDGAR. An event accepted on a trading day before 15:40 ET belongs to that
  session; otherwise to the next session. That session is $t_0$.
* **Finnhub shocks:** the publish time plus the 95th-percentile serving lag measured by the news audit
  (`fund/news_audit.py`, fixed when E3's data is built and recorded in the E3 output). It must fall before 15:40 ET to
  count for that session.
* **No look-ahead.** A signal measured on a session's close can only be traded at a later close.

Entry points:

| name | close traded | used by |
|---|---|---|
| `t0` | $t_0$ | E1 (the surprise is known by T−20 for releases before 15:40 ET) |
| `t0+1` | the session after $t_0$ | E1, E2 |
| `fund` | the first Thursday close after the next Wednesday desk. The desk's as-of is the first Wednesday whose 22:00 UTC cutoff is at or after the info time; entry is the next trading day | E3 (rule A) |
| `open+1` | the open after $t_0$ | descriptive only |

**Overlap.** Within each module, only the first event per name in any window of $h$ sessions is kept.

## 3. Inference (all modules)

* **Event tests** use `research/p8/inference.event_test` (season × sector fixed effects) with
  $p = \max(p_{\text{wild, GICS industry}},\ p_{\text{RI}},\ p_{\text{CR1, calendar month}})$. Wild cluster
  bootstrap: restricted, Rademacher (Webb under 12 clusters), B = 9,999. Randomisation inference: B = 9,999.
* **Mean tests** (E2's primary and rule A) have no cross-sectional regressor, so randomisation and within-cell
  demeaning do not apply. They use the one-sided
  $p = \max(p_{\text{CR1, week}},\ p_{\text{wild, week}},\ p_{\text{CR1, industry}},\ p_{\text{wild, industry}})$,
  with weeks and industries as clusters, the null imposed, and B = 9,999. A new function `mean_test` will be
  validated in `research/p8/test_inference.py` on simulated data before any Family E read.
* **Holm** runs across the modules read together in the validation read (E1, E2: m = 2).
* **Costs:**
  * the estimated live cost is $c$ = 2 bp per side: half the average quoted spread of the S&P 500, rounded up, with
    no credit for price improvement;
  * a stock round trip is $2c$ = 4 bp;
  * the stress round trip is 20 bp;
  * the hedge trades the book's net beta and is not charged per event.

## 4. Modules

### E1 — `earnings_post`: continuation after the earnings surprise

* **Events:** 8-K item 2.02 releases (`releases_202.parquet`); $t_0$ by section 2; S&P 500 members at $t_0$.
* **Signal:** SUE from `research/p8/events.sue_series` (first-filed XBRL EPS). This is admissible live only if the
  live parser of the EX-99.1 release agrees exactly with XBRL on ≥ 95% of 200 releases (rule B.5).
* **Target:** $D = \sum e$ from the entry close to $h$ sessions later.
* **Selection on fit (written now).** Grid: entry ∈ {`t0`, `t0+1`} × h ∈ {5, 10, 20, 40}. Choose the cell with the
  highest season-level IC t (Spearman per season, averaged). Ties go to the shorter h, then to `t0`. The chosen cell
  and its fit IC are recorded in `E_DRY_FIT.json` before the validation read.
* **Primary statistic:** the `event_test` slope of D on SUE standardised within season × sector. Registered sign:
  positive.
* **Economic statistic:**
  * $S$ = mean D (top SUE tercile) − mean D (bottom tercile), per event;
  * net at the live cost = $S - 2 \times 4$ bp; net at stress = $S - 2 \times 20$ bp.
* **Descriptive, never decisive:** the cost of each entry delay (`t0` vs `t0+1` vs `fund` vs `open+1`), and the decay
  over h = 1…60.

### E2 — `news_8k`: continuation after hard 8-K events

* **Events:** 8-K filings with any of items 2.01 (acquisition or disposition completed), 2.05 (exit or restructuring
  costs), 2.06 (material impairment) or 4.02 (non-reliance on prior financials), with:
  * no item 2.02 in the filing;
  * no 8-K item 2.02 within ±2 sessions.

  Items 7.01 and 8.01 are descriptive only (too heterogeneous).
* **Direction:** $d = \operatorname{sign}(e_{t_0})$.
* **Target:** $y = d \sum e$ from the `t0+1` close over $h$.
* **Selection on fit:** h ∈ {5, 10, 20} by the highest t of mean y, then the shorter h.
* **Primary statistic:** mean y, tested with `mean_test` (section 3). Registered sign: positive.
* **Economic statistic:** net = mean y − 4 bp (live) and mean y − 20 bp (stress).

### E3 — `news_soft`: the soft-news rule for the live book (rule A)

* **Events:**
  1. 8-K filings with item 5.02 (officer or director change) or 1.01 (material definitive agreement), with none of
     E2's items, no item 2.02, and no 2.02 within ±2 sessions; 2016–2025.
  2. Finnhub news shocks, 2025-11-01 – 2026-10-31: sessions with ≥ 5 articles and ≥ 3× the name's median daily
     count, as in `fund/lifecycle.py:m_table`, not within ±2 sessions of an item 2.02. Typed by one frozen
     classifier.
     * The classifier is called through `fund/guards.guarded_llm` at temperature 0, with a fixed schema and the
       fund's model and taxonomy. It returns event type and whether the event is hard (a reported or official
       fact with numbers or legal force).
     * Capped at 3,000 events and $5. No price is in the prompt.
     * Soft = type in {product_launch, partnership, leadership, macro_readthrough, mna_rumour, other} and not hard.
* **Direction:** $d = \operatorname{sign}(e)$ on the event session.
* **Target:** $y = d \sum e$ over the 5 sessions after the `fund` entry close. One event per name per 5 sessions.
* **Fit and descriptive windows:** 8-K events 2016–2021; Finnhub shocks 2025-11-01 – 2026-04-30. These are used to
  check the pipeline and the classifier (a sample of 50 classified events opened next to their headlines, CLAUDE.md
  rule 11).
* **Decision read:** the pooled holdout (8-K 2022–2025 + Finnhub 2026-05-01 – 2026-10-31), read once.

### E4 — `earnings_pre`: R5's economic test

The R5 read stays exactly as pre-registered (PREREG_thesis_tree.md §5: two seasons, SUE-beat target). Family E adds
only an admission condition. On the same records, the tercile spread of $\text{CAR}[t_0-1, t_0+1]$ by
`score_combined` must pass rule B.3, with each name's weight inside the announcement-risk cap ($|w|\cdot\hat\sigma(|
\text{CAR}|) \le$ 30 bp of NAV). No new read of R5 is created.

## 5. Rules

### Rule A — soft-news entries (becomes Protocol 7B Amendment 3 mechanically)

* Let $\hat\mu$ be the pooled holdout mean of y (E3), and $p$ the one-sided p of $H_0\!: \mu \le 2c$ (4 bp), as in
  section 3.
* **KEEP** soft-news entries iff $p \le 0.10$.
* **STOP otherwise.** An inconclusive result stops them: the burden of proof is on the trade.
* **Applicability.** Over the live book's soft-news entries from the 2026-10-15 session to the read date, compute the
  share whose side equals the sign of the residual move on the news session (B1's release session). If that share is
  below 60%, the historical evidence does not describe the desk's trades, and the result is STOP.
* **STOP means:** from the first as-of after the amendment merges, lifecycle cohorts do not enter names whose desk
  event type is soft and whose desk `hard` label is false. Open lots run out under their own rules. The suppressed
  entries are kept in the decision ledger as counterfactual rows.
* **Fading** soft news (trading against d) is not authorised by this rule. It needs its own admission under rule B.

### Rule B — module admission (all must hold)

1. The primary cell is chosen on the fit sample by the written rule. In the locked validation read, Holm-adjusted
   p ≤ 0.05.
2. The registered sign holds in 2022–2023 and in 2024–2025 separately.
3. **Economic test.** The net per-event spread at the live cost exceeds the hold margin $m = 2c$ = 4 bp, and the net
   at stress is ≥ 0.
4. **Sealed 2026 check:** the registered sign and a positive net at the live cost.
5. **Live equivalence:**
   * the live signal matches the historical definition (E1: ≥ 95% exact agreement on 200 releases);
   * every input's info time precedes the decision, tested on real fixtures.

An admitted module enters with:

* $\text{IC}_k = \tfrac12 \times$ its validation IC;
* half-life $\tau_k$ from its fit-sample decay;
* the registry status `admitted`, with the lock hashes.

**Retirement.** A module is retired when its forward IC over ≥ 4 seasons falls more than 2 standard errors below
$\text{IC}_k$. Forward data can retire a module; it cannot admit one.

### Rule C — promotion of the new flow to the traded protocol

All must hold:

* ≥ 1 module admitted.
* 20 consecutive clean shadow sessions. This is an operational gate, not a statistical one. "Clean" means all of:
  * a rebuild reproduces weights and NAV to the cent;
  * 100% of info times precede the decision;
  * zero beta and sector exposure;
  * ex-ante tracking error within ±25% of target;
  * realised transfer coefficient ≥ 0.5;
  * turnover within budget;
  * no announcement-cap breach.
* The owner commits the protocol text before its first decision. The current book (Protocol 7B) becomes its control.

### Rule D — go-live sizing

* $\text{IR}_0 = \text{IC}_c\sqrt{\text{breadth}/\text{design effect}}\cdot\text{TC}$, with the design effect from
  the season-level variance of the validation IC.
* $\psi = \min(\text{TE cap},\ \text{IR}_0/2\lambda)$; λ and the cap are owner policy.
* Start at ψ/2. Go to full ψ at the first O'Brien–Fleming look if t ≥ 0; go to 0 if t ≤ −2.
* The overlay is judged against cash and the market sleeve against SPY, separately.
* If the owner's sleeve plus the overlay would exceed the broker's overnight margin limit, the overlay is scaled
  down, never the sleeve.

### Programme stop

If no module is admitted under rule B by **2027-03-31**, building the new flow stops (maintenance only). The traded
book stays Protocol 7B, plus whatever market-exposure policy the owner sets.

## 6. Order of work

1. This file and DATA_USE.md are committed. Then data is built: 8-K items, prices extended through 2026-10, Finnhub
   shocks.
2. Dry fit on 2016–2021, without a lock: E1 and E2 cells chosen and written to `E_DRY_FIT.json`; the E3 pipeline
   checked on its fit and descriptive windows.
3. Validation read (E1, E2; `E_VALIDATION.lock`). Then the soft-news read (E3; `E_SOFT_READ.lock`), with rule A
   applied as Protocol 7B Amendment 3 in the next safe merge window.
4. Sealed read for E1 and E2 survivors (`E_SEALED.lock`).
5. E4 at R5's read (about mid-March 2027).

Each read writes `reports/research/p8/E_*.md` and `.json`, and a row in DATA_USE.md.

## Amendment 1 (2026-10-31): acceptance times from SEC's live API

**What had been seen.** No Family E statistic: no return, drift or IC of any Family E event. Only data-quality views
of the 8-K item table were seen, which are not outcomes:
* filing counts by year and item;
* the hour of acceptance;
* a comparison of acceptance times with SEC's live API.

**What was found.** SEC's live API (data.sec.gov/submissions) gives acceptanceDateTime in true UTC. SEC's filing
index pages confirm it (Apple 0000320193-24-000005: API `2024-02-01T21:30:30.000Z`, index *Accepted 2024-02-01
16:30:30* EST).

SEC's bulk submissions.zip, which built the P8 cache, mixes encodings for the same field:
* 31,973 filings of 8 large filers read 4–5 hours later than the API;
* in samples of other filers, 7% of ordinary filings and 360 of 360 odd-hour filings read the same as the API.

The P8 code had read the bulk value as Eastern clock time.

**Change.**
* Family E takes every acceptance time from the live API (`research/p8/family_e.py live`) and converts it from UTC
  to Eastern (`fund/edgar_time.py`) before the session rules of §2.
* E1's events keep their firm-quarters from `events.parquet`. Each takes the live time of the firm's 8-K 2.02 that
  its bulk time encodes (equal, or 4 or 5 hours later, to the second). An event with no or several matches is
  dropped and counted.
* No other rule changes.

**Consequence outside Family E.** Family H's spent reads used the bulk times as Eastern. That defect is reported in
`reports/research/p8/DATA_DEFECT_2026-10-31.md` and in DATA_USE.md. Family H's reads are not repeated here.

## Amendment 2 (2026-10-31): two-way clustering in the mean test

**What had been seen.** No Family E statistic. Only the simulation in `research/p8/test_inference.py`
(`test_mean_test_size_power`), which §3 requires before any read.

**Found.** With shocks by both calendar week and industry (simulated sd 0.4 and 0.3 against an idiosyncratic sd of
1, 1,500 events), §3's one-sided mean test rejected a true null in 8.3% of 120 draws at the 5% level. It takes the
largest of the CR1 and wild p-values clustered by week and by industry, but clustering on one dimension at a time
misses the dependence along the other.

**Change.** The test also takes the Cameron–Gelbach–Miller two-way clustered p-value (week × industry: V_week +
V_industry − V_week∩industry, at least either one-way variance, t with min(G) − 1 degrees of freedom). The maximum
covers five p-values. With it, the rejection rate under the null is 4.0% in 400 draws, and power is 0.82 at a 0.15 sd
effect. Only rule A and E2's primary use this test.

