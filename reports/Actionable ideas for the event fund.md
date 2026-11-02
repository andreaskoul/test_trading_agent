# Actionable ideas for the event fund

*2 November 2026. A critical extraction from the six notes in
[`research_notes/Portfolio construction after a signal stop/`](../research_notes/Portfolio%20construction%20after%20a%20signal%20stop/),
the synthesis [Portfolio construction after a signal stop](Portfolio%20construction%20after%20a%20signal%20stop.md),
the six notes in [`research_notes/Order timing literature and practice/`](../research_notes/Order%20timing%20literature%20and%20practice/),
[Fund pipeline against research and forums](Fund%20pipeline%20against%20research%20and%20forums.md), the soft-news
read and diagnostics ([read](research/p8/E_SOFT_READ.md), [diagnostics](research/p8/E_SOFT_DIAG.md)), and the fund's
design documents (PROTOCOL_fund.md, PREREG_family_E.md, PREREG_thesis_tree.md, CLAUDE.md). I also used, without
looking at any outcome, the label files the soft-news read produced (`.cache/p8/soft_labels.jsonl`) and the desk's
four cohort files on `fund-data` (`fund_state/live/<as-of>/lifecycle.json`), and the fund's own archive results already
in the repository (`technicals_backtest.md`, `p8/decay_earnings.md`, `p8/E_DRY_FIT.md`, `p8/E_VALIDATION.md`).*

**Conventions.**

* Returns are % of NAV per year unless marked "bp per trade", which means bp per unit of position weight over the
  stated holding window.
* **Registered cost**: the 5 bp per side the fund is scored at (round trip 10 bp). **Live cost**: 1–2 bp per side
  (round trip 2–4 bp); measured paper slippage is +0.57 ± 0.78 bp against the close.
* **Fund timing**: news to the Wednesday 22:00 UTC cutoff, entry at the next Thursday close, about 22–23 h later.
  The news vendor (Finnhub) serves articles 1.5–3 h late, with a 95th-percentile lag of about 23 h (1,377 min).
* **Read**: a one-shot, pre-registered, locked test. About 38 have been run and none has passed. Every new read adds
  to that count.
* **STOP / rule A**: the pre-registered decision of 1 November 2026 that stops soft-news entries in the live book.
* **7B**: the live protocol since 28 October 2026. **Amendment 8 horizon**: the formula that sets each position's
  holding period from its event type, the attention it got, its age and the share of the typical move already in the
  price.
* **Design effect (DEFF)**: how much clustering, for example of events in the same week, inflates the variance of a
  mean compared with independent events.
* Evidence labels: **[E]** peer-reviewed or measured evidence; **[E-unref]** an unrefereed paper; **[T]** theory;
  **[P]** practitioner opinion; **[V]** vendor claim; **[S]** search snippet only; **[Own]** the fund's own data;
  **[Inf]** my own inference or arithmetic.

---

## 1. Bottom line

1. **At the fund's latency, every source puts after-lag drift in S&P 500 news at about 0–15 bp gross per 5–10
   sessions.** That covers the literature, the fund's 8,924-event gap archive, its 13,860 soft-news events and its
   earnings-decay curves. This is the same size as the registered round trip of 10 bp. **No read the fund can run
   before the 31 March 2027 programme stop can tell 5 bp from 15 bp:** that takes 4,000–27,000 events (section 2).
   The usable levers are therefore:
   * which trades are allowed: taxonomy coverage and soft views on held names;
   * how long positions are held: the tail beyond about 15 sessions;
   * how reads are designed: precision targets, placebo baselines, a programme-wide evidence bar;
   * cheap forward measurement.

   New directional "edges" are not among the usable levers.
2. **The STOP leaves a definitional gap I found in the fund's own labels.** The desk files contain 80 views with a
   non-zero weight. Applying rule A to them as written (soft type **and** hard = false), 48 survive. **32 of those 48
   (67%) are labelled not hard by the desk itself:** analyst revisions, dated catalysts, legal or regulatory news, and
   half the earnings and guidance views. The read tested none of these cells, and the large-cap literature gives them
   no better support than soft news. Of the 3,017 shocks the classifier labelled, 12 of 90 M&A rumours carry
   hard = true and so escape the STOP.
3. **The live horizon rules have drifted away from the fund's own drift evidence.** The 2012–2025 gap archive was
   measured from the fund's Thursday entry. It shows nothing positive past about 15 sessions, and in 2012–21 the drift
   is negative: −14 bp at +20 sessions, t −3.6; gap-up longs −27 to −39 bp at +30 to +40 sessions, t −2.8 to −3.3.
   Despite this, the rules now let positions run well past 15 sessions:
   * Amendment 8 gives 20-session base horizons (and up to 25) to earnings, guidance, analyst downgrades and cross-firm
     news;
   * 7B R2 runs structural theses to 63 sessions;
   * 7B Amendment 1 holds losing positions into earnings for up to 40 or 63 sessions.

   The 2022–25 data are flatter (+10 bp at +20, t 1.5), so this is a measure-first item, not a proven loss.
4. **R5 is still the only branch aimed at the large term: the price reaction itself.** On my rough arithmetic
   (item 7) it is worth 1–2% a year *if* its primary test passes. Protect it, and give it a free baseline (news tone
   and novelty) so that a pass can be attributed.

---

## 2. Planning numbers the fund should design with

These come from the fund's own records, recomputed where possible. They drive every power figure below.

| Quantity | Value | Source and check |
|---|---|---|
| Standard deviation of the 5-session signed residual return per event, from fund entry | 8-K events 386–455 bp; Finnhub shocks 516–718 bp (pooled 553–569 bp) | E_SOFT_DIAG tables **[Own]** |
| Measured design effect (week-clustered vs independent standard error) | 8-K holdout 1.01; 8-K fit 1.27; Finnhub holdout 1.44; Finnhub fit 1.24; all E3 rows 1.18 | **[Inf]**, from DEFF = (SE_cluster / (sd/√n))²: e.g. 445/√13,860 = 3.78 bp vs 4.1 bp reported → 1.18. The 2–3 assumed in the brief is conservative for signed event returns. Keep 2–3 for the live desk's own positions, whose names in a cohort share themes (not measured) |
| Shock rate (≥ 5 articles and ≥ 3× the median daily count) | 3,539 a year on 503 names; 30% labelled hard | E_SOFT_CHECK **[Own]** |
| Shocks by type, labelled, about one year | analyst revisions 729, other 494, macro read-through 382, partnership 340, dated catalyst 207, legal/regulatory 174, earnings 158 (most earnings shocks are excluded by the ±2-session rule), product launch 152, leadership 107, capital return 102, M&A rumour 90, guidance 82 | E_SOFT_CHECK **[Own]** |
| 8-K event rates (S&P 500) | item 5.02 ≈ 980 a year; 1.01 ≈ 460; hard items 2.01/2.05/2.06/4.02 after the overlap filter ≈ 55–70; earnings (2.02) after filters ≈ 1,300–1,800 | E_SOFT_DIAG, E_DRY_FIT, E_VALIDATION **[Own]** |
| Live desk | 20 views a week (80 in four cohorts); about 45% soft-type; about 11 a week, or 550 a year, survive the STOP | `lifecycle.json` ×4 **[Own]** |
| Cost hurdles per event | 2–4 bp live, 10 bp registered, 20 bp stress (round trip) | PREREG_family_E §3; PROTOCOL_fund |
| Constant for one-sided 5%, 80% power | K = z₀.₉₅ + z₀.₈₀ = 2.486 | — |
| Minimum detectable effect (MDE) | K · sd · √(DEFF/n) | — |
| Events needed for an effect δ above the hurdle (sd 560 bp, DEFF 1.4 / sd 445 bp, DEFF 1.2) | δ = 5 bp: 108,600 / 58,800. δ = 10: 27,100 / 14,700. δ = 20: 6,800 / 3,700. δ = 40: 1,700 / 920 | **[Inf]** |
| MDE on the data that is still fresh | Finnhub hard shocks, one year (≈ 1,000): **52 bp** at 5 sessions (≈ 40 bp at 3). S&P 500 earnings in 2026 (≈ 1,450, sd ≈ 620 at 10 sessions): **≈ 50 bp**. Live post-STOP entries, one year (550, DEFF 2.5): **≈ 94 bp** | **[Inf]** |
| Fresh (unread) windows | S&P 500 point-in-time 2026-01..09 for any E1/E2-type hypothesis (the sealed read was never run); returns of Finnhub **hard** shocks 2025-11..2026-10 (never joined). 2022–2025 already carries 36 hypotheses | DATA_USE.md **[Own]** |

**What this implies.** The literature expects 10–35 bp of gross drift for hard news after a 1–2 day lag (section 3).
Every fresh sample's MDE is 40–95 bp. **A pass-or-fail read on fresh data will almost surely return "not
significant", whatever the truth.**

---

## 3. What the evidence says about after-lag drift, by event class (S&P 500, fund timing)

| Class | Literature (after day 0, large caps where available) | Fund's own data | Net verdict at fund timing |
|---|---|---|---|
| Earnings | PEAD "non-existent since 2006" for large stocks [E, Martineau 2022]. LLM headline drift −4.7 bp, not significant [E-unref → JFE, Lopez-Lira & Tang]. +0.22% over days 6–20, adjusted, mixed sizes [E-unref, Kargarzadeh 2026] | E1 SUE IC 0.051 (fit) → 0.025 (validation, p 0.24); tercile spread 43 → 21 bp at h 10; net −19 bp at the 20 bp stress cost | ≈ 0–20 bp gross; at or below the registered cost |
| Guidance, capital returns | +0.13% and +0.35% over days 6–20, adjusted [E-unref, Kargarzadeh] | not tested at fund timing | weak, single unrefereed source |
| Analyst revisions | post-revision drift not different from zero, 2003–10 [E, Altinkilic, Hansen & Ye 2016]; +0.10% over days 6–20 adjusted, and the move ratio of 1.20 says it is "finished at publication" [E-unref, Kargarzadeh] | 729 shocks a year, **0 labelled hard** | no support; Amendment 8's B = 20 for downgrades rests on Womack 1996 (pre-2000) |
| Legal and regulatory | raw +11 bp (days 1–5) and +29 bp (days 6–20), but **placebo-adjusted −8 bp (p 0.22)**; calendar-time Sharpe 0.66 gross, 0.12 at 10 bp per side, −0.43 at 20 bp [E-unref, Kargarzadeh] | 8 of 8 desk views labelled not hard | no support (the "positive follow-through" in the news note is background drift) |
| Hard 8-K items (2.01, 2.05, 2.06, 4.02) | 8-K items show "some" drift up to 90 days; no large-cap split [S/E, NYU working paper] | fit +32.4 bp (t 1.23, n 424), validation +54.8 bp (p 0.18, n 221) at h 10 from t0+1. **Pooled +38 ± 23 bp [Inf]**, biased up because the horizon was chosen on the fit window | the largest point estimate; ≈ 60 events a year, so it cannot be confirmed |
| Soft, story-driven (launch, partnership, leadership, macro, rumour) | reversal over days 6–20: adjusted −0.18% to −0.34% (raw −0.51% to −0.76%) [E-unref]; M&A rumours give back about 2× the pop over three quarters (mixed sizes, 1999–2018) [E, via CLS Blue Sky] | **+3.7 ± 4.1 bp** over 5 sessions (13,860 events); Finnhub alone −3.6 ± 19.8 | ≈ 0 gross; STOP is right |
| All news, weekly-aggregated tone | weekly decile long-short 0.32%, 0.20%, 0.26% in weeks 1–3, 0.21% in week 13 (2003–10, all sizes) [E, Heston & Sinha]; negative news slow up to 13 weeks | not measured | the one shape that fits a weekly cadence; untested in large caps after 2015 |
| Price-gap events, all types | — | from Thursday entry: +4, +12, +13, +7, +9 bp at 1, 2, 3, 5, 10 sessions (t ≤ 1.4); −6 (t −2.1) at +20; −27 (t −1.4) at +60 | days 1–3 are the only positive stretch |

---

## 4. Errors and overstatements in the notes

| # | Where | Claim | Check |
|---|---|---|---|
| 1 | turnover_discipline.md, header | "cost drag ≈ 40 × 4 bp = 1.6%" | Turnover is one-way (27% of NAV a day ≈ 68× a year), so drag = turnover × **per-side** cost. 4 bp is a round trip. The correct figures are **0.4–1.4% a year at 1–2 bp** and **2.0–3.4% at 5 bp** |
| 2 | forum_practitioner_views.md, Q3 inferences | "costs alone roughly 0.8–2.7% of NAV a year" at 1–2 bp per side | Double-counted; it should be 0.4–1.4% |
| 3 | news_event_strategy_evidence.md §5; synthesis | legal/regulatory is "the one hard category … worth pre-registering" | The raw +11/+29 bp is background drift. Adjusted −8 bp (p 0.22); Sharpe 0.12 at 10 bp per side (latency note §4–5). **Not a candidate** |
| 4 | news_event_strategy_evidence.md §1; synthesis | short tilt on negative hard news is "the most promising residual" | Lopez-Lira & Tang's top size tercile shows **no** drift after negative news. Heston–Sinha attribute slow negative news to short-sale constraints, which bind little in the S&P 500. The fund's gap-down shorts earn ≈ 0 from Thursday entry (−1, +7, +8, 0, +3 bp at 1–10 sessions, t ≤ 0.1). Weak |
| 5 | synthesis, "story-driven" figures | launch −0.73%, macro −0.76%, leadership −0.51% (days 6–20) | These are **raw** figures. The paper's placebo-adjusted values are −0.18%, −0.34% and −0.18%. It warns that neutral-coverage large caps drift −0.34% a month, which raw figures absorb |
| 6 | academic_news_latency.md §2; Heston–Sinha | weekly news "predicts for about a quarter" | The summed weekly coefficients (2.15%) exceed the paper's plotted cumulative (1.4–1.6%), so treat 2.15% as an upper bound. Sample 2003–10, all sizes |
| 7 | Fund pipeline report §1.2 | soft −20 to −44 bp; hard "0 to +19 bp" per unit of weight | Soft is superseded by the fund's own +3.7 ± 4.1 bp. The hard range is just as unsupported by own data and should not be carried forward either |
| 8 | synthesis, recommendation 7 | pre-register a conviction-ratio read for April 2027 | Underpowered. With high vs low halves of about 550 entries a year, lot-life sd about 750 bp and DEFF 2, the standard error of the difference ≈ 90 bp and the **MDE ≈ 225 bp**. Keep it descriptive; do not spend a read |
| 9 | synthesis, idiosyncratic volatility | 30% a year from 445 bp × √(252/5) | Event windows carry raised volatility, so this overstates steady-state idiosyncratic volatility. The conclusions do not change |
| 10 | Protocol 7B rationale | "earnings information priced over 10–40 sessions" (decay_earnings) | That curve sorts on the **surprise** (SUE), not on the reaction direction the desk trades. On the reaction (CAR) the curve is +26 to +28 bp at h 10–20, then **−34 bp at h 60 and −68 bp at h 120** (2016–21; t −0.9 and −1.95) |
| 11 | Fund pipeline report §3.3 | "Earnings and guidance get B = 15" | The code's Amendment 8 table (`B_TYPE`) has 20; 15 is Amendment 7's `EVENTS` table |
| 12 | sizing note §2 | agreement trades needed "a few weeks … at ~10 a side" | That count is for soft trades, which no longer accrue. For hard entries (≈ 11 a week) the exact binomial 51 trades take ≈ 5 weeks, or ≈ 7 with within-week clustering |

Checked and correct:

* break-even agreement a\* = (1 + c/μ)/2 = 0.675 at 11.4 bp and 4 bp; 0.94 at the registered cost;
* the Beta(8,6) posterior: P(a > 0.675) = 0.221 and P(a > 0.5) = 0.709;
* exact binomial n = 51 (power 0.81);
* standard error 5.5 bp from p = 0.0895;
* Bayes-factor bound 1.70;
* deflated-Sharpe expected maximum z of 2.17 (N = 38) and 2.53 (N = 100); Bonferroni z 3.01;
* 76,500 trades for a 4 bp edge at sd 445;
* 80% power at μ ≥ 15.5 bp;
* the Wilson interval [0.32, 0.81];
* the contribution table in the synthesis;
* the Gârleanu–Pedersen and half-Kelly arithmetic.

---

## 5. All items, ranked

Score = expected value × probability it holds for this fund × feasibility.

* **EV** is % of NAV a year at the registered cost unless noted. For measurement items it is the value of the
  information: the value of the decision it informs times the chance it changes that decision.
* **P** is my probability that the benefit holds for this fund.
* **F** is feasibility: cost, effort and the fit with the owner's rules, from 0 to 1.

All three are rough judgements, stated so they can be argued with.

| Rank | Item | Evidence | Key number | Plugs into | Change class | EV | P | F | Score | New read? |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Power-first design for the hard-news question: a precision target, no Finnhub-only read | [Own]+[Inf] | MDE on fresh data 40–95 bp vs 10–35 bp expected; the all-data estimate gives a 95% CI of ±9–10 bp | evaluation, pre-registration | research pre-registration | 0.30 (VOI) | 0.9 | 1.0 | **0.27** | 1, replacing others |
| 2 | Close the STOP's coverage gap: tabulate and decide the hard = false, non-soft-type cells | [Own] labels + [E] | 32 of 48 surviving views are not hard; 1,002 of 3,017 shocks | desk taxonomy, event filter | measurement now → 7B amendment (owner) | 0.60 | 0.6 | 0.7 | **0.25** | no |
| 3 | Log the desk-vs-news-day agreement and a per-lot P&L decomposition for every hard entry | [Inf]+[Own] | a\* = (1 + 2c/μ)/2; 51 entries ≈ 5–7 weeks | kill checks, evaluation | operational (measurement) | 0.25 (VOI) | 0.95 | 1.0 | **0.24** | no |
| 4 | Holding tail beyond 15 sessions: measure it, and pre-register a horizon rule with a placebo-based B_type re-estimate | [Own]+[E] | gap archive +20: −6 bp (t −2.1); 2012–21 −14 (t −3.6); 2022–25 +10 (t 1.5) | Amendment 8 horizon, 7B R2/A1 | measurement → 7B amendment | 0.80 | 0.25 | 0.8 | **0.16** | no (descriptive) |
| 5 | Programme-wide evidence bar for the remaining reads | [Inf]+[E] | 0 passes in 38 → prior odds ≲ 1:10–1:20 → require p ≤ 0.003 (z ≥ 2.75) | evaluation | research pre-registration policy | 0.20 | 0.8 | 1.0 | **0.16** | no |
| 6 | Placebo baseline, both cost hurdles and a co-primary all-data estimate in every event read | [E-unref]+[Inf] | background drift −0.34% a month for neutral large caps | evaluation | pre-registration rule | 0.15 | 0.9 | 1.0 | **0.14** | no |
| 7 | R5: register a news-tone and novelty baseline and an earnings-week attribution before the March read | [E]+[Inf] | earnings-week long-short 5.57% (t 2.66) over 13 weeks; R5 worth ≈ 1–2% a year if it passes | R5, thesis tree | research pre-registration (dated amendment) | 0.30 | 0.5 | 0.9 | **0.14** | secondary only |
| 8 | Forward log of weekly news tone for all names (free dictionary or FinBERT) | [E]+[Inf] | IC after decay ≈ 0.011; ≈ 100–200 weeks to detect | new signal, thesis tree | measurement (later a new protocol) | 1.0 | 0.2 | 0.6 | **0.12** | yes, about 2028 |
| 9 | "A soft view is no view" on held names | [Own]+[T] | each soft extension, increase or flip spends ≥ 1 side of cost for ≈ 0 edge | lifecycle re-selection, kill checks | 7B Amendment 3 text, before the merge | 0.10 | 0.9 | 0.95 | **0.09** | no |
| 10 | Mechanical novelty, quantification and source features on every shock and entry | [E]+[E-unref] | fresh vs stale day-1 response 39 vs 23 bp; unquantified −0.12%, press-wire −0.19% | desk taxonomy, R5 baseline | measurement | 0.30 | 0.25 | 0.9 | **0.07** | no |
| 11 | Short tilt on negative hard news | mixed | Lopez-Lira & Tang large caps: none; own gap-down ≈ 0 | sizing, side | secondary inside item 1's estimate | 0.80 | 0.15 | 0.5 | 0.06 | no |
| 12 | Fade story-driven soft news over days 6–20 | [E-unref] vs [Own] | adjusted −0.18% to −0.34%; own days 1–5 +3.7 bp | new rule | free fit-window descriptive only | 1.30 | 0.15 | 0.3 | 0.06 | would add ≥ 2 |
| 13 | Measure re-entries after horizon exits | [E]+[Inf] | saving ≈ 2·q·0.18·T·c ≤ 0.3% a year registered | turnover rules | measurement | 0.15 | 0.3 | 1.0 | 0.05 | no |
| 14 | Daily event-driven entries at the first close after the news | [E]+[Own] | own archive: no loss from Thursday entry (day 1–3: +4/+12/+13 vs +5/+8/+6 bp) | timing | new protocol | 0.50 | 0.3 | 0.3 | 0.05 | yes |
| 15 | Attention multiplier: "after the close" fires on about half of all earnings | [E]+[Own] | ×1.25 lengthens those horizons by about 5 sessions without large-cap support | Amendment 8 horizon | mechanical 7B amendment | 0.08 | 0.6 | 0.8 | 0.04 | no |
| 16 | Earnings-print exposure log and an announcement-risk cap on positions held into a report | [P]+[E] | print-day sd ≈ 5%; a 5% lot adds ≈ 25 bp of NAV risk per print at zero expected value | sizing, 7B A1 | measurement → 7B amendment | 0.08 | 0.5 | 0.8 | 0.03 | no |
| 17 | Anomaly signals as a filter on news days | [E] | anomaly returns +50% on news days, 6× on earnings days (all sizes) | event filter | — | 0.50 | 0.1 | 0.5 | 0.03 | yes |
| 18 | Reversal of large moves with no news | [E] | S&P 500 2000–09 reversal on no-news days; magnitudes not in the notes | new signal | — | 0.50 | 0.15 | 0.3 | 0.02 | yes |
| 19 | Legal/regulatory continuation | [E-unref] | adjusted −8 bp; Sharpe 0.12 at 10 bp per side | taxonomy | — | 0.30 | 0.1 | 0.5 | 0.02 | yes |
| 20 | SPY hedge band | [T] | real SPY cost ≈ 0.13 bp quoted spread; saving ≈ 0.01% a year real (0.2–0.3% scored) | hedge | owner policy | 0.01 | 0.9 | 0.3 | 0.00 | no |
| 21 | M&A rumour reversal as a sleeve | [E] | ≈ 90 rumours a year; MDE ≈ 480 bp per year of data | new signal | — | 0.20 | 0.2 | 0.1 | 0.00 | yes |
| 22 | Conviction-ratio read | [P]+[V] | MDE ≈ 225 bp in a year | sizing | — | 0 | — | — | 0.00 | yes |
| 23 | Redistribute freed weight, raise caps or conviction-weight | [T]+[P] | no IR gain; 1.67× leverage on an unproven signal | sizing | — | < 0 | — | — | < 0 | — |

---

## 6. The items in detail

### Item 1. A power-first design for the hard-news question

**What it is.**
* The synthesis recommends that the next read be the hard-news analogue of the soft-news study, since after the STOP
  hard news is the whole book.
* The planning numbers in section 2 show that a pass-or-fail read on fresh data cannot work. The only adequately sized
  sample is the all-data archive:
  * S&P 500 earnings (8-K 2.02) at fund timing, 2016–2025: about 15,100 events (E1's 7,957 + 7,164);
  * hard 8-K items: about 645;
  * Finnhub hard shocks 2025-11..2026-10: about 1,000.
* That archive's 2022–25 part already carries 36 hypotheses.
* Source: my arithmetic on E_SOFT_DIAG, E_DRY_FIT and E_VALIDATION **[Own]+[Inf]**. The design principle is
  Carver's: "Pre-cost returns are actually very hard to predict" [P].

**Numbers.**
* About 16,800 events, sd 500–600 bp, DEFF 1.3: standard error 4.4–5.3 bp, 95% CI ±8.6–10.3 bp.
* That is enough to say whether hard follow-through is clearly above the 10 bp registered round trip (estimate
  ≥ 20 bp) or clearly at or below zero.
* It is **not** enough to separate 5 from 15 bp.
* Existing descriptive evidence points to the middle:
  * gap archive +7 bp at 5 sessions and +9 at 10;
  * CAR-sorted earnings +26 bp at h 10 (Q5−Q1, which is two legs, so about 13 bp a leg).

**Where it plugs in.** Evaluation and pre-registration of the decision on what the post-STOP book is for. Change
class: research pre-registration.

**EV and why it might fail.**
* Value of information about 0.3% a year. The decision concerns a book with about 13× NAV a year of entry notional:
  about 1.3% a year of registered round-trip cost, 0.4% live.
* It also saves a read that would otherwise be wasted.
* Main risk: the archive's proxy direction (the news-day move) is not the desk's side. Item 3 measures the gap.

**Minimal design.**
* Statistic: the mean of y = d·Σe over sessions 1–3 and 1–5 after the fund's Thursday entry, with sector-residual
  e to reduce variance, minus a placebo mean (item 6).
* Hard cells defined before any outcome is seen (item 2).
* Report a precision estimate with CI, not a p-value.
* Mechanical decision rule written in advance:
  * the upper 95% bound < 10 bp → the hard book does not cover the registered cost;
  * the lower bound > 10 bp → it does;
  * otherwise "unresolved", and the burden-of-proof principle of rule A applies.
* Report the live (4 bp) and registered (10 bp) hurdles side by side.
* The data exist: prices 2016–2026, 8-K acceptance times, labelled shocks. Multiplicity: one read, replacing a series
  of slice reads.

### Item 2. The STOP's coverage gap (taxonomy consistency)

**What it is.** Rule A stops entries whose type is in {product launch, partnership, leadership, macro read-through,
M&A rumour, other} **and** whose hard label is false. Two sets of labels show what that leaves in the book.

**The desk's four cohort files** (80 views with a non-zero weight) **[Own]**:

| Cell | Views | What happens under rule A |
|---|---:|---|
| Soft type, hard = false | 32 | stopped |
| Soft type, hard = true (1 M&A rumour, 1 other, 2 partnership) | 4 | survive |
| Non-soft type, hard = true (9 earnings, 3 guidance) | 12 | survive |
| Non-soft type, **hard = false** (4 analyst, 6 dated catalyst, 9 earnings, 5 guidance, 8 legal) | **32** | **survive** |

**The classifier's 3,017 labelled shocks** **[Own]**:

* analyst revisions: 0 of 729 hard;
* dated catalysts: 2 of 207 hard;
* M&A rumours: 12 of 90 hard (these escape the STOP);
* partnership: 174 of 340 hard;
* other: 180 of 494 hard;
* overall, 1,002 shocks (33%) are hard = false outside the soft set, and 467 (15%) are hard = true inside it.

**Evidence on the surviving not-hard cells.**
* Analyst revisions: zero drift after 2003 [E, Altinkilic et al.]; "finished at publication" [E-unref].
* Legal: adjusted −8 bp [E-unref].
* Dated catalysts (for example "Is CF a smart buy before Q1 earnings?" in the 50-label sample): no literature, and the
  label reads like a preview, not news.
* M&A rumours: reversal [E, mixed sizes].

**Numbers.**
* The not-hard survivors are about 40% of views: roughly 10× NAV a year of entry notional at the average weight of
  about 2.6%.
* If their edge is like soft news (about 0 gross), they cost about 1.0% a year at the registered round trip and 0.3%
  live. That puts the central EV at about 0.6% a year.
* Caveat: 80 views from four weeks.

**Where it plugs in.**
* The desk taxonomy and the entry filter.
* Measurement now: an operational tabulation of every cohort by (type, hard) with weights, logged; no outcome needed.
* Any change to entry is a dated 7B amendment (owner). It must not be presented as part of rule A's mechanical
  amendment, because rule A's text fixes the cells.
* Two narrower fixes have direct literature support and could be proposed on their own:
  * "M&A rumour is never hard";
  * "dated-catalyst previews are soft".

**Why it might fail.** The desk's hard label may be noisy. The 9 not-hard earnings views are probably label noise
(post-release commentary). Stopping on a noisy label stops some real hard events.

**Minimal design.** No read. Log the cells forward. Bring the counts and the turnover each cell causes to the owner.
If a test is ever wanted, it is part of item 1's all-data estimate, by cell, as a pre-registered secondary.

### Item 3. Log the desk-vs-news-day agreement and a per-lot P&L decomposition for every hard entry

**What it is.**
* For every entry, log:
  * whether the desk's side equals the sign of the news-session residual move, and the sign of the Wednesday-close to
    Thursday-close move;
  * the per-lot P&L split into entry day, sessions 1–3, 4–15 and beyond 15, and print-day vs other-day return;
  * the side;
  * the (type, hard) cell.
* Sources:
  * the break-even identity a\* = (1 + c/μ)/2 (sizing note §2) **[Inf]**;
  * the synthesis's lesson that "the thing estimated was not the thing traded";
  * the gross, names-per-side and suppressed-names logging it recommends (item 5 there).

**Numbers.**
* The soft desk agreed with the news-day move on 7 of 12 trades.
* If hard follow-through is μ = 10–20 bp, then a\* = 0.60–0.70 at the live 4 bp round trip, and 0.75 to infeasible
  (> 1) at the registered 10 bp.
* An exact binomial needs 51 hard entries to separate 0.675 from 0.5 at 80% power: about 5 weeks at about 11 a week,
  about 7 with within-week clustering.
* The 80 existing views can be scored for agreement now, because agreement uses only the news-session move, which was
  known before entry.

**Where it plugs in.** Evaluation, and the applicability condition of item 1. Change class: operational. It cannot
change a decision.

**EV and why it might fail.**
* Value of information about 0.25% a year. If agreement is near 50%, no historical "news-day direction" estimate
  describes the desk, and the hard book's value rests entirely on the desk's unmeasured contrarian skill.
* Risk: the desk's disagreements may be informed fades. The (2a − 1)μ formula assumes they are not. The P&L
  decomposition shows which.

**Minimal design.** Descriptive. If a rule is wanted, pre-register "applicability requires a ≥ a\* with n ≥ 51"
before the data accrue.

### Item 4. The holding tail beyond about 15 sessions

**What it is.**
* The fund's own archive (8,924 S&P 500 gap events, 2012–2025, technicals_backtest.md) **[Own]**, measured from the
  Thursday entry: +20 sessions −6 bp (t −2.1); +30 −10 (t −2.3); +60 −27 (t −1.4).
  * 2012–21: +20 −14 (t −3.6), +30 −13 (t −3.0).
  * Gap-up longs: +30 −27 (t −2.8), +40 −39 (t −3.3).
  * 2022–25: +20 +10 (t 1.5), +40 −19 (t −0.2).
* The archive's own conclusion was "swing and positional classes disabled for news views", horizons 3–15.
* Earnings sorted on the reaction (CAR): −34 bp at h 60 and −68 bp at h 120 (2016–21) **[Own]**.
* Literature:
  * no large-cap PEAD after 2006 [E];
  * no analyst drift after 2003 [E];
  * cross-firm lead-lag "mostly not significant value-weighted after 2004" (pipeline report §3.11; the primary source
    is not in the notes [Inf/unverified]).

**Numbers.**
* Live rules that hold past 15 sessions:
  * B_type = 20 for earnings, guidance, capital returns, analyst downgrades and cross-firm news (horizon up to 25);
  * structural theses to 63 sessions (7B R2);
  * losing lots held into reports up to 40/63 sessions (7B A1).
* Assume 30–50% of hard entry notional (about 4–7× NAV a year) runs 10–25 sessions past day 15. If the tail drift is
  −10 to −25 bp per unit of weight, that is about −0.4 to −1.7% a year. EV central 0.8% a year.
* P is only 0.25:
  * 2022–25 does not show the loss;
  * the archive table has about 180 cells, so one |t| of 3.3 is not remarkable;
  * the view there is the gap direction, not the desk's.

**Where it plugs in.** The Amendment 8 horizon table, 7B R2 and A1. Change class: measurement now (item 3's tail
split); a dated 7B amendment later (owner).
* Amendment 8 already pre-registers a B_type re-estimate: "85% of the 30-day maximum of the signed CAR curve per type,
  against a placebo baseline".
* **Flaw in that rule:** on a flat or noisy curve, the maximum of noise sets B, which biases horizons upward. Add, now,
  before the estimate is run: if a type's placebo-adjusted curve does not exceed its placebo at the 5% level at any
  horizon, B is the minimum (5).

**Why it might fail.** Structural theses may be a genuinely different population, and the 7B-vs-control comparison
exists to test exactly R2 and A1. That comparison is far too weak, though: about 220 bp MDE on a year of live tails
(sd ≈ 890 bp over 20 extra sessions, n ≈ 200, DEFF 2).

**Minimal design.**
* Statistic: mean side-signed residual return per unit of weight from session 16 to exit, against a counterfactual
  exit at session 15.
* Hurdle 0: the exit cost is paid either way, so it does not enter.
* Burden of proof on the long hold: H₀ tail ≤ 0.
* Archive precision: sd ≈ 1,000 bp over 25 sessions, n 8,924, DEFF 1.3 → standard error ≈ 12 bp.
* The data exist (archive, labelled shocks, 8-K). Descriptive, so no new read.

### Item 5. A programme-wide evidence bar

**What it is.** The STOP note shows that after 38 null reads, one p = 0.09 is below what chance delivers:
P(min p ≤ 0.0895) = 0.97, and the expected maximum z is 2.17. Harvey–Liu–Zhu ask for t > 3 [E]. I turn the
programme's record into a prior **[Inf]**.

**Numbers.**
* Model each read as having power 0.3 against a true effect and α 0.075 (both illustrative). If a share π of tested
  hypotheses were true, P(0 passes in 38) is:

  | π | P(0 passes) |
  |---|---|
  | 0 | 0.052 |
  | 0.05 | 0.032 |
  | 0.10 | 0.020 |
  | 0.30 | 0.003 |

* The record favours π near 0. Prior odds for the next read of about 1:10 to 1:20 are generous.
* To reach a posterior above 50% a read needs a Bayes factor of 10–20. The bound 1/(−e·p·ln p) gives BF ≤ 8 at
  p = 0.01, 14 at p = 0.005 and 21 at p = 0.003.
* So: **p ≤ 0.003, one-sided z ≥ 2.75**, close to Bonferroni's 3.0 at m = 38.

**Where it plugs in.** Evaluation policy for the remaining reads: R5/R3, E4, item 1, item 8. Change class: research
pre-registration policy.

**EV.** About 0.2% a year. With 3–5 more reads at α 0.05–0.10, the chance of at least one false pass is about 25–35%.
A false pass that goes live costs its turnover, roughly 0.5–1% a year, until retirement.

**Why it might fail.** It costs power. R5's design expects t ≈ 3 per season at a 55% hit rate (about 900
firm-reports a season, 0.05/(0.5/√900) = 3.0, with no clustering). With DEFF 2 that falls to about 2.1 a season and
3.0 pooled over two seasons. A z ≥ 2.75 bar would bind.
Use it as the programme bar for **admitting** new modules, and leave R5's registered rule in place as written.

**Minimal design.** None; it is a rule. Write it before the next lock.

### Item 6. Placebo baseline, both cost hurdles, co-primary all-data estimate

**What it is.**
* From Kargarzadeh et al. [E-unref]: without a placebo, a background drift (neutral-coverage large caps −0.34% over the
  following month) "masquerades as 'good news reverses, bad news continues'". Their legal/regulatory raw +29 bp turns
  into −8 bp adjusted.
* From the STOP diagnostics [Own]:
  * register the fit-plus-holdout estimate as co-primary when the fit window selects nothing;
  * derive bars from break-even;
  * set a minimum n before a condition can bind;
  * weight the estimand toward the source traded.
* The return leg used the 4 bp live round trip while the fund is scored at 10 bp.

**Numbers.** The soft holdout passed at 4 bp (z 1.37) and failed at 10 bp (z 0.26). The all-data estimate (+3.7 ± 4.1)
reversed the holdout's message.

**Where it plugs in.** Every event read. Change class: a pre-registration rule. Placebo means: the same names and the
same entry weekday in non-event weeks, matched on sector and month, with returns computed identically.

**EV and failure mode.** About 0.15% a year by avoiding biased adoption. The placebo adds variance (√2 on the
difference if the placebo n equals the event n). Use several placebos per event to keep the variance cost small.

### Item 7. R5: a news-tone and novelty baseline, and an earnings-week attribution

**What it is.**
* Heston & Sinha [E]: news not priced at publication shows up mostly around the next earnings announcement. The
  earnings-week long-short cumulates 5.57% (t 2.66) over 13 weeks, against 0.25% before earnings.
* Engelberg, McLean & Pontiff [E]: anomaly returns are 6× higher on earnings days.
* Caughran [P]: print days are 2% of days but about 20% of idiosyncratic volatility.
* R3 already requires a positive increment of the thesis score over "the mean news tone of the quarter" (thesis-tree
  prereg §5), so the tone variable must exist anyway.

**Numbers (my arithmetic, heavy assumptions).**
* A 55% hit rate on "SUE above the median" implies a score–surprise correlation of sin(0.05π) = 0.156.
* Martineau's R² of 11.7% for announcement returns on surprise deciles gives corr(CAR, surprise) ≈ 0.34, so the IC on
  CAR ≈ 0.053.
* Print-day sd ≈ 5%. Check: 20% of a 25%-a-year idiosyncratic variance over about 5 print days per year gives a
  print-day sd of 0.25/√252 × √10 ≈ 5.0%.
* A sign-only position then captures 0.05 × 0.053 × √(2/π) ≈ **21 bp per unit of weight** against 4–10 bp of cost.
* At about 12× NAV a year of earnings entries this is **1.3–2.0% a year**, halved at go-live by rule D's half-IC
  start.
* P(R3 passes and holds) is perhaps 0.15–0.25.

**Where it plugs in.** The R5 analysis plan (research pre-registration, a dated amendment to PREREG_thesis_tree,
written before the mid-March 2027 read). Make these pre-registered descriptive secondaries:

* the tone baseline's own slope on the R3 target and on CAR;
* the same for a mechanical novelty score;
* R5's score effect within and outside the earnings window.

No new primary read.

**EV and why it might fail.** EV about 0.3% a year in decision quality: it tells whether a free baseline does R5's
job (R5 is about 85% of LLM spend). Risk: the tone variable is built from Finnhub, which has only a one-year history,
so the baseline is forward-only, as R5 is.

### Item 8. A forward log of weekly news tone for all names

**What it is.**
* Heston & Sinha [E]: weekly-aggregated news tone predicts returns for up to 13 weeks. Weekly deciles give 0.32%,
  0.20% and 0.26% in weeks 1–3; negative news is slower.
* Of all the shapes in the literature, this one fits a weekly cadence and needs no speed.
* Use a free dictionary (Loughran–McDonald) or FinBERT on the Mac at zero LLM cost. The budget is $13 a week.

**Numbers.**
* The week-1 decile spread of 0.32% against a weekly residual sd of about 3% gives IC ≈ 0.32/(3.5 × 3) ≈ 0.026 (the
  decile spread is about 3.5 × IC × sd).
* After McLean–Pontiff's 58% post-publication decay: ≈ 0.011.
* Break-even IC at a 4-week hold (25% weekly turnover, 5 bp per side): 0.25 × 2 × 5 / (3.5 × 300) ≈ 0.0024.
* Weekly IC sd about 0.05 (assumption: ≈ 1/√500 plus factor noise). Weeks needed for 80% power:

  | True IC | Weeks |
  |---|---|
  | 0.011 | 209 |
  | 0.015 | 97 |
  | 0.020 | 50 |

**Where it plugs in.** A new signal for the thesis tree or a later protocol, plus R5's baseline (item 7). Change
class: measurement now; a read in about 2028.
* It conflicts with the programme stop (31 March 2027 → "maintenance only"). The owner would have to class a free log
  as maintenance.

**Why it might fail.**
* The 2003–10 all-size sample. Short-sale constraints (Heston–Sinha's explanation) bind little in the S&P 500.
* Finnhub's coverage may change.
* Breadth helps, IR ≈ IC·√breadth, but the fund's 10-a-side slots cap breadth unless a separate sleeve is allowed.

**Minimal design.** Mean weekly Spearman IC of tone (to the Wednesday cutoff) against the Thursday-to-Thursday residual
return, Newey–West across weeks; hurdle IC 0.0024. Data: Finnhub cache from 2025-10 (about 50 weeks already) plus the
forward log.

### Item 9. "A soft view is no view" on held names

**What it is.** The synthesis found that the lifecycle's re-selection lets a view on a name already held do three
things: extend its horizon and raise its weight to max(old, new); close it; or flip it. Rule A says only that soft
names are not *entered*. Source: synthesis §"One gap needs closing" **[Own]**; the pipeline report's "hold through soft
adverse news".

**Numbers.**
* A soft-triggered flip costs two round trips: 20 bp of the flipped weight at the registered cost.
* An increase or extension spends cost for ≈ 0 edge: the soft follow-through is +3.7 ± 4.1 bp, and agreement 7/12
  gives a desk capture of about 0.6 bp.
* Frequency is unknown. My guess is 2–4 a week, giving about 0.05–0.2% a year registered. EV 0.1.

**Where it plugs in.** The text of 7B Amendment 3, which implements rule A and is **not yet in PROTOCOL_fund.md**. Write
it before any 7B outcome is examined. The STOP is meant to take effect with the 2026-11-04 desk, so the last safe
merge window is Tuesday 3 November, 02:00–15:30 UTC (the owner merges). Add a contract test: on a recorded cohort, a
soft view on a held name leaves the lot unchanged.

**Why it might fail.** A soft-labelled view that is really hard (item 2's label noise) would be ignored. That is
acceptable: the kill check still exits on hard adverse news.

### Item 10. Mechanical novelty, quantification and source features

**What it is.**
* Tetlock 2011 [E]: stale news (similar to the last 10 stories) reverses within a week.
* Ke, Kelly & Xiu [E]: fresh news has a 39 bp one-day response and takes 4 days to incorporate; stale news 23 bp and
  2 days.
* Kargarzadeh [E-unref]: quantified articles show no drift; unquantified ones reverse −0.12%; press-wire releases
  −0.19% adjusted.
* Didisheim et al. 2026 [CEPR column, not the paper]: markets underreact to negative, number-dense topics (negative
  guidance, recalls, trial readouts) and overreact to ambiguous, high-attention ones.

**Numbers and power.**
* A moderator (novel vs stale) needs twice the standard error of a mean: on one year of shocks, MDE ≈ 100 bp; on the
  all-data hard set, ≈ 22 bp.
* The documented fresh-stale gap (16 bp on day 1) is mostly gone before the fund enters.

**Where it plugs in.** The desk taxonomy and R5's baseline (item 7). Change class: measurement.
* Compute per shock and per entry, with no LLM:
  * maximum headline similarity (token Jaccard or TF-IDF cosine) to the firm's previous 10 stories and to the
    previous 5 sessions;
  * whether the shock-day articles contain numbers (%, $, figures);
  * the share of articles from press-wire sources;
  * the number of distinct sources.
* The desk's age-based staleness rule (H ≤ 2 → not entered) stays.

**Why it might fail.** These are moderators of effects that are already near zero at the fund's lag. Their main value
is cleaner attribution for R5, not a trading filter.

### Item 11. A short tilt on negative hard news (do not test on its own)

**Evidence for.**
* Heston–Sinha: negative news is incorporated over up to 13 weeks [E].
* Chan 2003: bad-news drift [E], "mainly … smaller, more illiquid stocks".
* Lopez-Lira & Tang: the short leg carries most of the drift in the pooled sample [E-unref → JFE].
* The fund's hard 8-K items, mostly adverse: pooled +38 ± 23 bp at h 10 [Own, Inf].

**Evidence against.**
* Lopez-Lira & Tang: the **top size tercile shows no drift after negative news**.
* The fund's gap-down shorts earn ≈ 0 from Thursday entry [Own].

**Where it plugs in.** A pre-registered **secondary** in item 1: the sign asymmetry of y.
* With about 16,800 events, the standard error of the difference ≈ 8.8 bp, so MDE ≈ 22 bp.
* No separate read, and no change to sizing (instruments and net exposure are owner policy).

### Item 12. Fade story-driven soft news over days 6–20 (fit-window descriptive only)

**Evidence.**
* Kargarzadeh [E-unref], mixed sizes: adjusted reversals of −0.18% (launch, leadership) and −0.34% (macro) over days
  6–20.
* Its own calendar-time test found that fading small-cap launch and partnership news "is identical to shorting any
  covered small cap … the news direction adds nothing".
* Own data: +3.7 ± 4.1 bp over days 1–5 from fund entry, i.e. no reversal yet.

**Power.**
* Fit window (8-K 5.02/1.01 2016–21, n 7,076, sd ≈ 770 bp over 15 sessions): MDE ≈ 26 bp.
* A rule-B chain would then need validation on 2022–25 (hypothesis #37 on that window) and a sealed 2026 window (MDE
  ≈ 66 bp on about 1,100 events). The chain cannot pass unless the reversal is ≥ 60 bp.

**Recommendation.** At most a free descriptive on the fit window, which is open for selection. Stop there unless it
shows a reversal of ≥ 40 bp.

**EV if true.** (20 − 10 bp) × 13× NAV ≈ 1.3% a year. P 0.15.

### Item 13. Re-entries after horizon exits

**What it is.**
* Novy-Marx & Velikov [E]: buy/hold spreads are the "single most effective simple cost mitigation". PEAD went from
  0.26% to 0.35% a month net, but they cannot rescue a sub-cost signal (short-run reversal −1.28% → −0.72%).
* The turnover note's renewal saving is ≈ 2·q·0.18·T·c, where q is the share of horizon exits followed by a
  same-name, same-side re-entry.
* The lifecycle already extends held names on a same-side event, and 7B R3 protects working lots, so q is probably
  small.

**Numbers.** q = 1/3, T = 54, c = 5 bp gives 0.32% a year scored and 0.10% a year at 1.5 bp.

**Plug-in.** Measurement from the decision ledger (count q). Only if q ≥ 0.2 propose a hold-through rule (7B
amendment).

### Item 14. Daily event-driven entries (do not pursue now)

**Evidence.**
* A one-day delay costs a daily text signal 25–65% of its implementable drift [E, computed in the latency note].
* For big stocks, drift is about 11 bp and complete after one day [E, Ke, Kelly & Xiu].
* The fund's own archive shows **no loss** from the Thursday entry compared with the news-day close:
  * sessions 1–3: +4/+12/+13 bp vs +5/+8/+6 bp;
  * standard error ≈ 2–4 bp per horizon.

**EV.** 0–1.4% a year (the pipeline report's estimate), probably the lower half. It needs a new protocol, a
restarted clock and about 5× the desk's LLM calls against a $13-a-week budget.

### Item 15. The attention multiplier fires on most after-close earnings

**What it is.**
* Amendment 8 multiplies B by 1.25 for "low attention": abnormal volume < 1.5, a Friday, or news **after the close**
  (`session_of` in `fund/lifecycle.py`).
* More than 95% of earnings are released outside regular hours, roughly half of them after the close [E,
  Grégoire–Martineau]. So the flag is a release-time flag, not an attention measure.
* For liquid large caps, 80% of announcement-day price discovery happens 16:00–18:30 [E, Christensen et al.], and
  spillover dominates distraction [E].
* The supporting studies (DellaVigna–Pollet, Hirshleifer–Lim–Teoh) are pre-2006 and partly small-cap.

**Numbers.** 20 × 1.25 = 25, so after-close earnings lots get about 5 more sessions than pre-open ones, and this
compounds with item 4.

**Plug-in.** A mechanical 7B amendment: drop the after-close and Friday triggers for earnings and guidance; keep
abnormal volume. EV about 0.05–0.1% a year (horizon only, no turnover). Low priority, but it is one line.

### Item 16. Earnings-print exposure log, and a cap on positions held into a report

**What it is.**
* Print days are 2% of days but about 20% of idiosyncratic volatility [P, Caughran]. My check: that implies a
  print-day variance about 10× a normal day's, an sd ≈ 3.2× higher, about 5%.
* 7B A1 holds losing lots into reports.
* P8 already specifies |w|·σ̂(|CAR|) ≤ 30 bp of NAV per name and 150 bp a week; the live book has no such cap.
* Heston–Sinha: delayed reaction to *negative* news shows up around the next report, while positive news is priced
  within about a week. A1 therefore has some literature support for shorts on negative news, none for longs.

**Numbers.** A 5% lot carries ≈ 25 bp of NAV sd per print (50 bp at 10%) with zero expected value absent skill.
Twenty such holds a year add about 1.1–1.2% a year of sd, roughly 4% of variance on a 6% idiosyncratic book.

**Plug-in.** Log print exposure per lot (operational). Split A1 outcomes by side. A cap is a 7B amendment and the
owner's call. EV is risk only, ≈ 0.05–0.1% a year Sharpe-equivalent.

---

## 7. Top five, in order

1. **Before Tuesday 3 November 15:30 UTC:** write 7B Amendment 3 with "a soft view is no view" (item 9). Add, as an
   operational log only, the per-cohort table of (type, hard) cells with weights (item 2). Do not change rule A's cells
   in that amendment; bring the 32-of-48 finding to the owner as a separate decision.
2. **This week, operational:** for every entry, log agreement with the news-session move and the entry-day move, and a
   P&L decomposition (entry day, 1–3, 4–15, > 15, print vs non-print, side) (items 3, 4, 16). Score the 80 existing
   views for agreement now. Agreement needs no outcome.
3. **Before any new lock:** adopt the design rules. These are the MDE table (section 2) and a precision target rather
   than pass/fail. Add a placebo baseline, hurdles at 4 bp and 10 bp side by side, a co-primary all-data estimate, and
   a programme evidence bar of p ≤ 0.003 for admitting new modules (items 1, 5, 6). **Do not run a Finnhub-only
   hard-news read.**
4. **Pre-register the hard-news question as one all-data precision estimate** at fund timing (about 16,800 events,
   CI ±9–10 bp), by (type, hard) cell. Add the side asymmetry and the beyond-15-session tail as secondaries. Fix
   Amendment 8's B_type re-estimation so that a flat curve yields the minimum horizon (items 1, 2, 4, 11).
5. **Start free forward logs:** weekly news tone for all names, and mechanical novelty and quantification features on
   every shock. Register them now as R5 baseline secondaries for the March read (items 7, 8, 10).

## 8. Do not pursue

| Idea | Reason |
|---|---|
| A Finnhub-only (one-year) hard-news read | MDE ≈ 52 bp against 10–35 bp expected. It will return "not significant" whatever the truth and add one to the count of reads |
| Legal/regulatory continuation | Raw drift is background drift. Adjusted −8 bp (p 0.22); Sharpe 0.12 at 10 bp per side, from one unrefereed paper. The notes overstate it |
| M&A rumour reversal as a trade | About 90 rumours a year; a 3-quarter horizon gives MDE ≈ 480 bp per year of data. Mixed-size, 1999–2018 evidence. Handle rumours by exclusion (item 2) |
| A short tilt as its own read | Large-cap evidence against (Lopez-Lira & Tang top tercile; own gap-down ≈ 0). Keep it as a secondary only |
| A soft-news fade chain (rule-B admission) | Own days 1–5 show no reversal; the literature fade "adds nothing" over shorting small caps. The sealed 2026 MDE ≈ 66 bp |
| A conviction-ratio read, conviction weighting, raising caps, refilling freed slots | MDE ≈ 225 bp. Most PMs have conviction profitability ratio ≤ 1 [P/review]; "Best Ideas" works only after skill is proven [E]. Redistribution is 1.67× leverage on an unproven signal with no IR gain [T] |
| Daily event-driven entries now | The own archive shows no measurable delay cost from Thursday entry. New protocol, restarted clock, about 5× LLM cost |
| Anomaly-on-news-day filters | The +50% / 6× amplification is all-size. The fund's deterministic S&P 500 signals (Family H) all failed, so there is no anomaly signal to condition on |
| No-news extreme-move reversal | Outside the narrative mandate. Short-run reversal is net negative at academic costs [E, NMV]; P8 already treats unexplained moves as "look" triggers |
| SPY hedge band, staged entries, Gârleanu–Pedersen partial trading | SPY's quoted spread is about 0.13 bp (1 cent on about $780), so the real saving ≈ 0.01% a year. Whole-share granularity (about 0.8% of NAV) already acts as a band. Costs are linear at this size, so partial trading does not apply. The hedge is owner policy |
| A bp-denominated entry gate (≥ 2–3× round trip) | The desk produces no calibrated expected return in bp, so there is nothing to gate on until a module is admitted with an IC |
| Reading the timing shadow books or the 7B-vs-control comparison for these questions | Plausible effects need decades of weeks (pipeline report §3.10). Use them as gross-failure monitors only |

---

## 9. Limits

* **Most per-type numbers rest on one unrefereed 2023–26 workshop paper** (Kargarzadeh et al.). It has mixed sizes, a
  single-beta benchmark and no large-cap split in the retrieved pages. Didisheim et al. is a CEPR column. Pod limits
  and most forum figures are second-hand or snippets. Caughran's 2% / 20% figure is a practitioner's LinkedIn post.
* **My EV and P figures are judgements**, stated so they can be argued with. The R5 arithmetic in item 7 chains three
  assumptions (hit rate, CAR–surprise correlation, print-day sd).
* **The label tabulations (items 2 and 9) are small.** There are 80 desk views from four cohorts. The classifier labels
  are a different call from the desk's, though they use the same model and taxonomy.
* **No outcome was examined to write this.** The label files and the cohort files were read for labels and weights
  only. Every return figure quoted comes from records already in the repository.
* **Design effects are measured for signed event returns (1.0–1.45).** The live desk's same-week clustering was not
  measured; the 2–3 used for live-entry power is an assumption.
