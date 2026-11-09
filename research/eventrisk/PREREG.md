# Scheduled-event risk for the stock book: pre-registration

*Written 2026-11-09, before any statistic in this file was computed. Owner's brief (2026-11-09): integrate
forward-looking event risk into the pipeline as one assembly; before each design choice consult the literature and
the mathematics and, where possible, test on past data. Nothing here trades. The traded fund is frozen (CLAUDE.md
rule 13); anything that passes is a proposal for a protocol. 2026 data are not read: every loader filters to dates
≤ 2025-12-31.*

## 1. Idea in one paragraph

The fund's stop and target width is W = σ_e·√H, with σ_e an exponentially weighted standard deviation of past
hedged returns, frozen at entry. It is blind to the calendar. A scheduled announcement inside the holding period
adds variance on a date known in advance. With independent increments, the variance of the H-day sum is the sum of
the daily variances, so the forecast should be V = (H − n_E)·σ_d² + n_E·σ_E², where σ_d² is the variance of a day
without an announcement, σ_E² that of an announcement day, and n_E the number of the firm's own earnings reaction
sessions in the window. The tests ask whether this beats the fund's forecast, whether firm-specific announcement
variance beats a pooled multiple, whether sizing by it lowers position variance at equal gross exposure, and
whether macro announcement days (Fed, CPI, employment report) carry extra variance in hedged returns at all.

## 2. Literature consulted before the design (access label in brackets)

* Earnings announcements raise return variance (Beaver 1968 and replications) [search summary]. Options price the
  announcement as a jump on a known date, and the anticipated jump variance is large, varies over time and forecasts
  realised volatility (Dubinsky, Johannes, Kaeck, Seeger, RFS 2019) [search summary]. This motivates the additive
  form and a firm-specific, time-varying σ_E².
* Loss function: only MSE and QLIKE rank variance forecasts consistently when the target is a noisy proxy (Patton,
  J. Econometrics 2011); QLIKE has the greater power in Diebold–Mariano tests (Patton and Sheppard) [search summary].
* Discretely monitored barriers: a barrier checked at closes behaves like a continuous one moved outward by
  0.5826·σ·√Δt (Broadie, Glasserman, Kou, Math. Finance 1997) [search summary]. Used only for the theoretical noise
  hit rate in S1.
* Stop rules cannot add expected return under a random walk (Kaminski and Lo, J. Financial Markets 2014) [search
  summary]. Hence S1 measures calibration of the stop, not profit.
* Volatility-managed sizing: positive in sample (Moreira and Muir 2017), not reliably out of sample (Cederburg et al.,
  JFE 2020) [search summary]. Hence the sizing claim is tested here only as a variance statement at equal gross
  (P-E1), never as a return claim.
* Macro announcement days: market volatility is only about 4% higher on them (Savor and Wilson 2013) [search
  summary]. The prior for E4 is therefore a null.
* Shrinkage of noisy firm means toward a pooled mean: James–Stein / one-way random effects [from memory, not re-read].

The repo's own evidence: `research/riskfield` M0 (HAR with an earnings-in-window dummy) beat the EWMA forecast in
development and out of sample. That test did not isolate the event term, did not use the fund's W, and did not
separate firm from pooled announcement variance.

## 3. Data (all ≤ 2025-12-31)

* **Returns:** `.cache/riskfield/hf.npz` (30-minute bars from the owner's Stock2Vec cache, current S&P 500
  constituents plus SPY, 2016-01-04 .. 2025-12-31). The daily log return is the sum of the day's 14 returns; a day
  with any missing return is missing. Survivorship is disclosed, as in `research/riskfield`.
* **Earnings reaction sessions:** `.cache/p8/events.parquet`, column `t0` (the first session that trades on the
  report), universe `sp500`. Realised dates are used; they are scheduled in advance (disclosed).
* **Macro calendar:** `research/eventrisk/macro_dates.json`: scheduled FOMC decision days (Federal Reserve calendar
  pages; unscheduled and cancelled meetings excluded), CPI (FRED release 10, last date in each month) and the
  employment report (FRED release 50, first date in each month). A date that is not a session maps to the next session.
* **Sector:** the `sector` column of the events file.

**Input contracts.** A name is used at origin t only if it has at least 3 earnings sessions in the 300 sessions to t
(else its calendar is incomplete: counted and reported, not guessed). Coverage of names per origin day is reported
against the 500 expected.

## 4. Definitions

* **Beta:** as the fund's hedge beta: OLS over 252 sessions (min 200) of daily simple returns clipped to
  [−2 r_m, 4 r_m], b = 2/3·OLS + 1/3; the value of session t−1 is used on session t.
* **Hedged return:** e_t = r_t − b_{t−1}·r_SPY,t (simple returns).
* **B0, the fund's forecast:** σ_e = max(EW std of e, span 60; 0.75 × std of the last 252 e (min 120)), at the close
  of t. V_B0 = H·σ_e².
* **σ_d:** the same formula on the series of e with the firm's own earnings sessions removed.
* **Announcement ratio:** q = e²/σ_d² (σ_d of the previous session) on an earnings session.
* **Pooled multiple c:** the mean of q over all firms' earnings sessions before the refit date. Refit on the first
  session of each month. (The mean of ratios is the QLIKE-optimal scalar.)
* **Firm multiple:** c_i = mean of the firm's last ≤ 12 ratios before t (n_i of them). Shrunk:
  c*_i = (n_i·c_i + k·c)/(n_i + k), with k = s_w²/τ² from a one-way random-effects decomposition of q on the fit
  sample (s_w² pooled within-firm variance; τ² = max(variance of firm means − s_w²·mean(1/n_i), 0)), k clipped to
  [1, 200]; n_i = 0 gives c.
* **Forecasts** for the window t+1..t+H with n_E own earnings sessions in it:
  * M1 = H·σ_d² (decomposition without the event term; attribution only);
  * C1 = (H − n_E)·σ_d² + n_E·c·σ_d²;
  * C3 = (H − n_E)·σ_d² + n_E·c*_i·σ_d².
* **Target:** RV = Σ_{k=1..H} e²_{t+k}; the window needs all H values.
* **Loss:** QLIKE, L = RV/F − log(RV/F) − 1.
* **Comparison statistic** (as `research/riskfield`): the daily cross-sectional mean of L_benchmark − L_candidate on
  the common sample, its time mean, and a Newey–West t with H + 5 lags. Positive = the candidate is better.

## 5. Tests

| Test | Claim | Statistic |
|---|---|---|
| **E1** (H = 5 and H = 15) | C3 forecasts the window's variance better than B0 | QLIKE gain, C3 vs B0, every session an origin |
| **E2** (H = 15) | the firm-specific multiple adds to the pooled one | QLIKE gain, C3 vs C1, windows with n_E ≥ 1 |
| **P-E1** | scaling a position by s = √(M1/C3) lowers position variance at equal gross | Thursday origins, H = 5: D_t = mean_i x_i − mean_i (k_t·s_i)²·x_i, x_i = (Σ_{k=1..5} e_{i,t+k})², k_t = 1/mean_i s_i; Newey–West t (2 lags) of D_t, and the ratio Σ scaled / Σ unscaled |
| **E4** (gate, 3 calendars × 2 levels) | hedged returns have extra variance on macro days | name level: daily cross-sectional mean of e²/σ_d² (the firm's own earnings sessions excluded), macro days against all other days, Welch t with days as units; sector level: the same for equal-weighted sector means of e (≥ 5 names) against their own EW variance (span 60) |

**Reported, not tested:**
* E1 split into windows with and without an earnings session, and M1 vs B0 (attribution);
* the level of each forecast: mean of RV/F;
* **S1, stop calibration.** For every origin and both sides, a hypothetical lot with barriers −2W and +3W on the
  cumulative e at closes from t+1 to t+H, W = √V. Stop-hit rates for windows with and without an earnings session,
  under B0 and C3, the share of stops that fall on the earnings session, and the Gaussian noise rate
  2Φ(−(2 + 0.5826/√H)) for reference.
* **Failure control:** every test is rerun with each name's earnings calendar shifted forward by 21 sessions. The
  event term's gain (L_M1 − L_C3 on windows with a placebo event) must be ≤ 0 within noise; if it is positive at
  t ≥ 2 the code is wrong and no result is read.

## 6. Periods and gates

* **Development:** origins from the first session where every input exists (not before 2017-01-03), targets ending
  ≤ 2019-12-31.
* **Development gate:** a test goes forward with the predicted sign and t ≥ 1.5.
* **Out of sample:** origins from 2020-01-02, targets ending ≤ 2025-12-31. **One read** of all finalists
  (`OOS_READ.lock`), one-sided p, Holm across {E1 H=5, E1 H=15, P-E1}. Parameters refit monthly on past data only, so
  nothing is frozen from development except the design.
* Disclosure: 2020–2025 was read by `research/riskfield` for other hypotheses; its M0-vs-EWMA result is known.

## 7. Consequences, fixed now

* **E1 passes** at a horizon (Holm p < 0.05): propose, as a protocol, that W uses the event-inclusive variance.
  Fails: W stays as it is and the component is not built.
* **E2** (own p < 0.05 out of sample): firm-specific multiple; otherwise the pooled multiple (one parameter).
* **P-E1 passes:** propose the size scalar with it. Fails: stop width only, no change to sizing.
* **E4:** a macro calendar enters the forward record only if its out-of-sample variance ratio is ≥ 1.25 with
  Bonferroni p < 0.05 (six tests) at the name or sector level. Otherwise macro announcement days are dropped from the
  design, and shared-event risk is limited to events with firm-specific exposures (policy and legal contracts), which
  can only be validated on forward records.

## 8. Not claimed

No return or alpha claim. No claim about option-implied announcement variance (history from 2024-02 only). No claim
about prediction-market probabilities: no test in this file uses them.

### Amendment 1 (2026-11-09, after the development results, before the out-of-sample read)

**Coverage defect found in development, and its fix.** The first development run used the intraday panel named in
§3. A daily return there is missing when any 30-minute bar is missing (8–9% of name-days in 2016–2019), so only
266 names a day at H = 5 and 230 at H = 15 had a complete window, against about 500 expected (CLAUDE.md rule 3).
That run is kept as `DEV_RESULT_intraday_panel.json`.

**Change, data only:** daily returns now come from the P8 Alpaca closes, adjusted for splits and dividends
(`research/p8/prices.py: panel`), with point-in-time S&P 500 membership (`members`). A name is used at origin t only
if it is a member at t. This also removes most of the survivorship bias. No definition, test, statistic or gate in
§§4–7 changes. Disclosed: the change was made after the first development numbers were seen; every test had the same
sign and passed its gate on both panels.

**Development results on the amended data** (`DEV_RESULT.json`, targets ending ≤ 2019-12-31):

| Test | Result | t | Gate (t ≥ 1.5) |
|---|---|---:|---|
| E1, H = 5 | QLIKE gain 0.189 | 8.10 | finalist |
| E1, H = 15 | QLIKE gain 0.126 | 7.48 | finalist |
| E2, H = 15 | QLIKE gain 0.036 on event windows | 3.72 | finalist |
| P-E1 | position variance ratio 0.860 at equal gross | 6.95 | finalist |
| E4 FOMC, sector level | variance ratio 1.20 | 1.74 | finalist |
| E4 FOMC, name level | 1.02 | 0.23 | no |
| E4 CPI, name / sector | 0.83 / 0.75 | −3.15 / −3.42 | no (wrong sign) |
| E4 employment report, name / sector | 0.79 / 0.71 | −4.66 / −4.22 | no (wrong sign) |

**Failure control (placebo calendar, +21 sessions):** the event term's gain is −0.006 (t −0.73) at H = 5 and −0.002
(t −0.77) at H = 15, against +3.32 (t 13.3) and +0.76 (t 12.2) with the real calendar. The control fails as it
should, so the results are read.

**Remaining coverage limit, disclosed:** 353 of 504 members a day are used. About 130 members a day have no complete
earnings calendar in `.cache/p8/events.parquet` (about 100 members have no events in it at all, e.g. BLK, V, HSY).
They are excluded, not guessed. The live fund reads Finnhub's calendar, so its coverage will differ and must be
measured there.

**Out-of-sample read:** finalists E1 (H = 5, H = 15), P-E1 (Holm across these three), E2 (own p) and E4 FOMC at
the sector level (Bonferroni over the six E4 tests, ratio ≥ 1.25 required). CPI and the employment report do not go
forward: macro data releases are dropped from the design.

### Amendment 2 (2026-11-10, before any statistic of AP1 or AP2): the earnings-announcement premium

**Why.** Owner's brief (2026-11-10): find ways to raise the Sharpe ratio and beat the S&P. The literature reports
that firms scheduled to report earn an abnormal return (Frazzini and Lamont 2007; Barber et al. 2013; Savor and
Wilson 2016: 9.9% a year), and a later paper argues it has disappeared [all search summaries]. The repo has not
tested it. It also bears on Protocol 11: the size scalar shrinks positions before a report, which forgoes a premium on
longs if one exists.

**Disclosure.** §§5–6 read 2020–2025 for variance statistics only (squares, and stop rates over both sides). No mean
return of announcers was computed. This family has its own lock, `OOS2_READ.lock`.

**Definitions** (data, universe, hedged return e and eligibility as in §§3–4 and Amendment 1).
* Origins: every Thursday session t. x_i = Σ_{k=1..5} e_{i,t+k}.
* Announcers A_t: names with an earnings session in t+1..t+5. Others N_t. A week counts only if |A_t| ≥ 10.
* **AP1:** d_t = mean_{A_t} x − mean_{N_t} x. A book long announcers and short the others, equal weights, each leg
  hedged to zero beta. Predicted sign: positive.
* **AP2:** a_t = mean_{A_t} x. Announcers against SPY only. Predicted sign: positive.
* Statistic: mean and Newey–West t (2 lags) of the weekly series; reported as % a year (52 × mean) and annualised
  Sharpe. Costs: 2 bp a side on the turnover of the equal weights of each leg, week to week, reported net as well;
  weeks that do not count hold nothing.

**Periods and gates.** As §6: development Thursdays with windows ending ≤ 2019-12-31, gate t ≥ 1.5 with the predicted
sign; one out-of-sample read 2020-01-02 .. 2025-12-31, one-sided p, Holm across {AP1, AP2}.

**Consequences, fixed now.**
* AP1 passes net of costs: propose a forward paper book (research only), and add it to the list of validated
  overlays. Fails: no book.
* AP2 passes: the Protocol 11 text must state the scalar's cost on long positions, μ_A × (1 − s) per position-week,
  and the owner decides whether the scalar applies to longs. Fails: the scalar is symmetric, as planned.
* Failure control: the placebo calendar (+21 sessions) must give t < 2 for both.

**Amendment 2, development result (2026-11-10, `DEV2_RESULT.json`, Thursdays with windows ending ≤ 2019-12-31).**
151 weeks, 75 counted (about 50 announcers each).

| Test | % a year, gross | t | % a year, net of 2 bp a side | Gate |
|---|---:|---:|---:|---|
| AP1 announcers minus others | −5.0 | −0.89 | −6.4 | fails: wrong sign |
| AP2 announcers against SPY | −5.8 | −1.00 | −6.8 | fails: wrong sign |

Placebo calendar: t 1.03 and 0.91 (below 2, as required). **Neither test goes forward; the 2020–2025 read for this
family was not made (`OOS2_READ.lock` does not exist).** Consequences as registered: no announcer book; the Protocol 11
size scalar stays symmetric.
