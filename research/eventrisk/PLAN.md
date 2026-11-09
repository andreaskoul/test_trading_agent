# Forward-looking risk in the pipeline: implementation plan

*2026-11-09. Owner's brief: integrate items 1–5 of the narrative review as one assembly; before each design choice
consult the literature and the mathematics and, where possible, test on past data. Tests and their rules are in
`PREREG.md`; numbers are copied from `DEV_RESULT.json` and `OOS_RESULT.json`. Nothing here trades. The fund is frozen:
everything below that touches a desk is a proposal for one protocol.*

## Summary of what the evidence decided

| Item | Decision | Basis |
|---|---|---|
| 3a. Earnings inside the holding period | **Build.** Stop/target width and size use an event-inclusive variance | passed out of sample (E1, E2, P-E1) |
| 3b. Macro announcement days (Fed, CPI, employment report) | **Do not build** | failed (E4): no extra variance in hedged returns |
| 3c. Shared policy events priced on prediction markets | **Archive only**, no risk limit yet | too few liquid, resolved, firm-specific events to validate an exposure |
| 1. Prediction-market archive | **Extend the existing context archive** by one source | the reader is 3c's validation test |
| 2. Shared narrative basis from embeddings | **Do not build now** | its only reader would be 3c, which is not built |
| 4. Scoreable theses | **Read existing records at 150 closed positions**; no prompt change | 49 closed positions today: no power |
| 5. Probability changes as a stock signal | **Not before 3c validates** | it needs the same exposures |

One component is built, one source is added to a job that already runs, and three ideas are stopped by evidence.

## Decision 1. How to forecast variance when a report falls inside the holding period

* **Literature.** Earnings announcements raise return variance (Beaver 1968 and replications); option markets price
  the announcement as a jump on a known date, and the anticipated jump variance is large, time-varying and
  informative (Dubinsky, Johannes, Kaeck, Seeger 2019). [search summaries; papers not opened]
* **Mathematics.** With independent increments, Var(Σ e) = Σ Var(e). So V = (H − n_E)·σ_d² + n_E·σ_E², where σ_d² is
  a normal day's variance, σ_E² the report day's and n_E the number of reports in the window. The fund's current
  forecast H·σ_e² mixes past report days into σ_e, which overstates quiet windows and understates report windows.
* **Test (E1).** QLIKE loss (the loss that ranks variance forecasts correctly with a noisy target, Patton 2011),
  daily cross-sectional mean difference, Newey–West t.

| | Development 2017–19 | Out of sample 2020–25 |
|---|---:|---:|
| Gain over the fund's forecast, 5-day window | 0.189 (t 8.1) | 0.127 (t 9.2) |
| Gain, 15-day window | 0.126 (t 7.5) | 0.074 (t 6.6) |
| Realised ÷ forecast variance in report windows, 5-day, current | 4.83 | 3.84 |
| Realised ÷ forecast variance in report windows, 5-day, proposed | 1.27 | 1.21 |

* **Failure control.** With each firm's calendar shifted 21 sessions, the event term's gain is zero (t −0.01 and
  −0.55 out of sample). The test can fail and did on the planted fault.
* **Choice.** Adopt the additive form.

## Decision 2. Pooled or firm-specific report-day variance

* **Mathematics.** The ratio q = e²/σ_d² on a report day is roughly a scaled χ²(1) draw, so a firm mean over n
  reports has sampling variance about 2c²/n. A one-way random-effects split gives the shrinkage weight
  n/(n + k), k = within-firm variance ÷ between-firm variance. No tuned constant.
* **Test (E2).** Firm-shrunk against pooled, report windows only: gain 0.036 (t 3.7) in development, 0.034 (t 4.5)
  out of sample. The pooled multiple was 17.6 at the start of 2020 and 14.9 at the end of 2025; k was about 8.5,
  i.e. a firm's own history gets half the weight after about 8 reports.
* **Choice.** Firm-specific, shrunk. A firm with no history uses the pooled multiple.

## Decision 3. Constant or time-varying barrier

* **Mathematics.** For a driftless walk checked at closes, the chance of touching −2W within the horizon is about
  2Φ(−(2 + 0.5826/√H)) (reflection principle with the Broadie–Glasserman–Kou correction): 2.4% at H = 5, 3.2% at
  H = 15. This is the stop's noise rate.
* **Measurement (S1, reported, not tested), out of sample.**

| Stop-hit rate of random positions | Windows with a report | Other windows |
|---|---:|---:|
| Current width, H = 5 | 15.4% | 2.6% |
| Proposed width, H = 5 | 4.3% | 3.2% |
| Current width, H = 15 | 9.3% | 2.9% |
| Proposed width, H = 15 | 4.4% | 3.7% |

  With the current width, 59% of the stops in 5-day report windows fire on the report session itself.
* **Choice.** Keep one constant width frozen at entry, as now. A width that steps up on the report day would be more
  exact but adds a moving part; the constant one already brings the two rates within 1.1 points of each other.
* **Not claimed.** Stops add no expected return under a random walk (Kaminski and Lo 2014). This is calibration of
  the stop, not a profit claim.

## Decision 4. Whether size should shrink with the wider width

* **Literature.** Volatility-managed sizing looks good in sample and is unreliable out of sample as a return
  strategy (Moreira and Muir 2017; Cederburg et al. 2020). So only a variance claim is tested.
* **Mathematics.** Loss at the stop is 2·W·weight. Scaling weight by s = √(V_no-event / V) keeps it constant. At
  equal total gross, moving weight away from higher-variance positions lowers Σ w²σ² (Cauchy–Schwarz) if the
  forecast is right.
* **Test (P-E1).** Thursday entries, 5 sessions: position variance at equal gross falls to 0.860 of the unscaled
  book in development (t 6.9) and 0.915 out of sample (t 9.5). About 8% of positions are scaled, by 0.56 on average.
* **Choice.** Scale. This replaces the analyst instruction to "lower your confidence" before earnings, which must be
  removed in the same protocol so the discount is not applied twice.

## Decision 5. Macro announcement days

* **Literature.** Market volatility is only about 4% higher on macro announcement days (Savor and Wilson 2013), so
  the prior was a null.
* **Test (E4).** Variance of hedged returns on the day against all other days.

| Out of sample, variance ratio | Stock level | Sector level |
|---|---:|---:|
| Fed decision days (47) | 1.02 | 0.95 |
| CPI days (71) | 1.03 | 1.16 (p 0.17) |
| Employment report days (71) | 0.99 | 1.12 (p 0.16) |

  The bar was 1.25 with Bonferroni p < 0.05. Only Fed days at the sector level passed the development gate (1.20,
  t 1.74), and it failed out of sample. In development CPI and employment days were *quieter* than other days.
* **Choice.** Drop macro calendars from the design. After the SPY hedge they are not a risk the stock book carries.

## Decision 6. Shared events with prediction-market probabilities

* **Literature.** A firm's exposure to a binary event is the slope of its return on the event probability
  (Snowberg, Wolfers, Zitzewitz 2007; Knight 2006). Text gives a usable prior for exposures (Hassan et al. 2019).
  [search summaries] I found no study linking prediction-market probabilities to firm-level returns for the 2026
  tariff ruling; four searches, so this is the reach of the search, not evidence of absence.
* **Mathematics (my estimate, not a computed power study).** In the resolution-day test, an event contributes
  roughly t² ≈ N·ρ·(sd(β)·|𝟙 − p| / σ)², with N exposed firms, ρ the reliability of the estimated exposure and σ the
  day's hedged volatility. With N = 50, σ = 1.5%, surprise 0.3 and ρ = 0.25: a spread of exposures of 2% gives
  t² ≈ 2 per event, a spread of 0.5% gives 0.13. Only events that split firms widely are testable, and about 30 of
  them are needed.
* **Data.** Of the 400 highest-volume resolved Polymarket events (each above $5.8M), 70 are tagged economy, policy,
  business or technology. Most are Fed decisions, which Decision 5 shows carry no extra hedged variance, and Iran
  or Ukraine geopolitics. Firm-splitting events are few; the tariff ruling market reportedly had about $4.5M of
  volume. Polymarket earnings contracts are thin ($1.6k–$4.4k volume on the three inspected).
* **Choice.** No exposure model and no limit now. Archive prices, and run the validity test once 30 qualifying
  events have resolved. Qualifying: volume ≥ $1M, at least 5 days of price history before resolution,
  |𝟙 − p| ≥ 0.2 at the last pre-resolution snapshot, and at least 20 S&P 500 names with a non-zero text exposure.

## Decision 7. Scoreable theses (item 4)

* **Literature.** Verbalised model confidence is typically overconfident and clusters in a few values; agreement
  across samples is the strongest simple alternative. [search summaries, general benchmarks, not finance]
* **Data.** The live book has 69 entries and 49 exits: 29 at the horizon, 11 for capacity, 5 on news, 3 flips,
  1 stop. Five-sample classification exists for 23 entries; 5 of those 23 were not unanimous on the news type.
* **Mathematics.** Detecting a rank correlation of 0.2 between confidence and outcome at 80% power (one-sided 5%)
  needs about (1.645 + 0.84)²/0.2² ≈ 155 positions; 0.3 needs about 70.
* **Choice.** No read now and no prompt change. At 150 closed positions (roughly ten more weeks at the current
  rate), one pre-registered read of three questions: confidence against outcome in stop-width units; exit cause by
  hard and soft news; unanimous against split classification. The criteria are written before that read.

## The assembly

| Stage (existing) | Change | Replaces |
|---|---|---|
| Weekly screen | For each stock: next report session, the firm's shrunk report-day multiple c*, and the pooled multiple | the bare "earnings this week" flag |
| Entry (`entry_vol`, sizing) | W = √((H − n_E)·σ_d² + n_E·c*·σ_d²); weight × √(H·σ_d² / W²); both frozen at entry | the analyst's "lower your confidence" line |
| Context archive (nightly) | add the Polymarket source to its list | nothing |
| Overnight audit | one row per report passed: realised e² against forecast | nothing |
| Monitor | per position: report inside the horizon yes/no, the width used | nothing |

* **Typed input, no guess.** The report date comes from the calendar the fund already reads. No date, or fewer than
  one past report: the position keeps today's width and size, and is counted as a defect (rules 1 and 2).
* **Coverage to measure before adoption.** The research calendar covered 441 of 502 members a day out of sample.
  Finnhub's calendar returned a date for 52 of the 69 live entries.
* **Materiality in the live book.** 4 of those 52 entries (8%) had a report inside the planned horizon, the same
  share as random 5-day windows (7.8%). Small sample.
* **Removal rule.** The overnight audit accumulates realised ÷ forecast variance for report windows. If after 100
  report windows it is outside 0.7–1.5, the component is switched off and reviewed.
* **Open point for the protocol.** The 28 October amendment keeps a losing position open when earnings are expected.
  It overlaps with the wider width; the protocol should say which governs.

## Order of work

1. Owner decision on this plan and on a protocol number.
2. Contract tests on real fixtures: a position with a report inside, one without, one with no calendar date, one
   with no report history.
3. Shadow record for two weeks next to the live width, as Protocol 9 did.
4. Polymarket source in the context archive (research side, no protocol).
5. Item 4 pre-registration, then its read at 150 closed positions.

## Limits

* Realised report dates were used; they are scheduled in advance, but a date moved at short notice would not have
  been known.
* 2020–2025 had been read before for other hypotheses.
* The development run first used a panel with a coverage defect; Amendment 1 records the change.
* Literature claims rest on search summaries, not on the papers.
* The placebo run shows a statistically visible but negligible P-E1 effect (variance ratio 0.9993 out of sample, t 2.4), because
  the placebo multiple is not exactly 1.
