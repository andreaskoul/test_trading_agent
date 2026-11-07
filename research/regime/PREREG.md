# Pre-registration: regime-dependent edges in S&P 500 stocks (search protocol)

*Written 2026-11-07, before any of the data below has been computed for this study. The owner asked for "a
statistically regime-dependent edge with an associated regime detection technique, which might have associations to
news in embedding space or correlations in sectors and outside of them", tested out of sample, and taken forward only
if it is worth it. Research only: nothing here trades. Rule 17 (instruments and hedges are policy) is respected: every
strategy is a market-hedged stock selection; no market exposure or hedge is timed or tuned.*

## Question

Does the profit of a standard cross-sectional stock signal depend, predictably and out of sample, on a regime that can
be detected from information available at the decision? An "edge" here is that dependence: a regime-conditioned
strategy that beats the same strategy run unconditionally, after costs.

## Data and splits

* **Stocks:** S&P 500 point-in-time members (`data/raw/stocks/sp500_membership.csv`), daily closes 2009–2025
  (`.cache/quant_trials/sp500_close.parquet`, the panel of `PREREG_quant_sp500.md`), SPY.
* **Sectors:** GICS sector from `sp500_current.csv` where known. A name without one (a former member) gets the sector
  whose equal-weight daily return it correlates with most over the trailing 252 sessions, recomputed at each decision
  from past data only.
* **News:** the 31-name news panel of the quant trials (`.cache/quant_trials/text/<T>_dedup.npz`: per session, the sum
  and count of `gemini-embedding-001` vectors of deduplicated news facts), 2016–2025.
* **Development:** every decision up to 2019-12-31 (news detectors: 2017–2019, after a one-year warm-up).
* **Out of sample (OOS):** decisions 2020-01-01 → 2025-12-31 (about 310 weeks), **read once**, after the frozen
  specification below is committed.
* **Sealed:** 2026. Nothing from 2026 is read (the P8 holdout rule and the forward period).

## Mechanics (fixed)

* Weekly decisions at Thursday's close (signal at close t); entered at close t+1; held to close t+6. Non-overlapping.
* Base signals, z-scored across eligible names:
  * **REV**: minus the 5-session residual return (r − β·r_SPY, β the shrunk 252-session beta of the panel);
  * **SREV**: minus the 5-session return in excess of the name's sector equal-weight return;
  * **MOM**: 12-1 month momentum (log price 20 sessions ago minus 252 sessions ago).
* Book: long the top decile, short the bottom decile, equal weight, 50% of capital per side; SPY sets the book's beta
  to zero. Costs 5 bp per side on all traded weight, the hedge included. Returns over the holding week, in excess of
  nothing (a dollar-neutral book).
* Regime detectors, computed from data up to close t only. Each is turned into a percentile against its own trailing
  3-year history (expanding before 3 years are available), so no detector uses the future:
  * **D1 VOL**: SPY realised volatility over the last L sessions;
  * **D2 PANIC**: SPY's 252-session return < 0 and D1 above its median (Daniel & Moskowitz 2016);
  * **D3 SCORR**: average pairwise correlation of residual daily returns within sectors minus across sectors, over
    the last L sessions;
  * **D4 NEWSHOM**: news homogeneity, the mean pairwise cosine similarity across the 31 firms of their weekly news
    centroids, each demeaned by the firm's trailing 52-week centroid (firms with news that week only);
  * **D5 NEWSSHIFT**: cosine distance between this week's cross-firm news centroid and the trailing 13-week centroid;
  * **D6 HMM**: filtered probability of the high-volatility state of a 2-state Gaussian HMM on weekly SPY return and
    log realised volatility, refit each January on all prior data (filtered, never smoothed).

## Hypotheses (direction fixed in advance)

| | Strategy | Detector | Mechanism | Predicted |
|---|---|---|---|---|
| H1 | REV | D1 VOL | liquidity provision earns more when volatility is high (Nagel 2012) | b > 0 |
| H2 | SREV | D3 SCORR | when names co-move within sectors, a name's deviation from its sector is temporary | b > 0 |
| H3 | MOM | D2 PANIC | momentum crashes in rebounds after bear markets with high volatility (Daniel & Moskowitz 2016) | b < 0 |
| H4 | REV | D4 NEWSHOM | when news is common (macro-dominated), stock-specific moves are noise and revert | b > 0 |
| H5 | MOM | D5 NEWSSHIFT | an abrupt shift in what the news is about unwinds trends | b < 0 |
| H6 | REV vs MOM | D6 HMM | in the high-volatility state reversal pays; in the calm state momentum pays | b > 0 for (REV − MOM) |

For each hypothesis, b is the slope of the weekly book return (gross) on the detector percentile at the decision,
NW t with 4 lags.

## Development (≤ 2019): choosing one specification per hypothesis

Each hypothesis has at most four specifications: window L ∈ {21, 63} sessions (D4–D6: the 52-week demeaning and the
13-week shift are fixed; their two choices are the percentile history, 1 or 3 years) × conditioning form
∈ {binary: trade only when the detector is in the predicted half; linear: scale the book by the percentile (or one
minus it)}. For H6 the conditioned book holds REV with weight p and MOM with weight 1 − p (linear) or the one the
state selects (binary).

The specification with the largest development t of b in the predicted direction is chosen. A hypothesis goes to the
OOS read only if its chosen specification has development t ≥ 1.5 in the predicted direction **and** its conditioned
book's net mean return is above the unconditioned book's. The finalists and their frozen specifications are committed
in an amendment below before the OOS read.

## OOS read (once) and what counts

* **Primary:** b in the predicted direction, one-sided, Holm across the finalists at α = 0.05 (NW t, 4 lags).
* **Worth taking forward** (all three):
  1. Holm-significant primary;
  2. the conditioned book's net Sharpe ratio in OOS exceeds the unconditioned book's;
  3. the conditioned book's OOS net mean return is positive.
* Reported for every finalist: b and its t, net and gross returns in % per year, Sharpe, worst drawdown, turnover,
  results by year, and the fraction of weeks the conditioned book trades.
* **If nothing is worth taking forward**, that is the result; it is reported as such. A further search would need a
  new pre-registration and a new untouched sample (the forward period).
* **If something is**, it goes to a forward paper book on the research-data branch with its own pre-registered rule
  (never traded), not into the fund.

## Known limits

* 2020–2025 prices were used by earlier studies of other signals (PREREG_quant_sp500.md); these regime hypotheses were
  not tested there.
* The news detectors rest on 31 large caps; they proxy the market's news state, they do not measure it.
* Literature results (H1, H3) are well known; the question is whether they hold in this universe, after 5 bp costs,
  in 2020–2025.

---

## Amendment 1 (2026-11-07, before any round-2 statistic; the OOS sample is still unread)

**Round 1 result (development only).** No hypothesis reached development t ≥ 1.5 in its predicted direction (H1 0.63,
H2 0.33, H3 1.19, H4 0.03, H5 −0.82, H6 0.93; `.cache/regime/dev_table.csv`). There are no round-1 finalists, so no
round-1 OOS read will be made. **Disclosure:** the panel build printed full-period (2010–2025) summary statistics
of the three unconditioned books (mean weekly gross: REV +7.8 bp, SREV +5.4 bp, MOM −3.0 bp; REV turnover 1.8 a
week). No conditioned or regime statistic was computed on 2020–2025.

**Round 2: five further hypotheses**, same mechanics, development rule (t ≥ 1.5 in the predicted direction and a
conditioned net mean above the unconditioned), and OOS rules. Holm runs across all finalists of both rounds.

Added data: S&P 500 earnings events 2012–2025 (`.cache/p8/events.parquet`: report session t0 by SEC acceptance time
and SUE from first-filed XBRL EPS; the P8 construction). The P8 validation read (2022–2025) used these events for
other hypotheses (peer sympathy, earnings decay); none below was tested there.

| | Strategy | Detector | Mechanism | Predicted |
|---|---|---|---|---|
| H7 | **PEAD**: long the top, short the bottom SUE quintile of S&P 500 members whose t0 fell in the last 20 sessions | **CROWD**: S&P 500 reports in the last 5 sessions | limited attention: drift is larger when many firms report at once (Hirshleifer, Lim & Teoh 2009) | b > 0 |
| H8 | **NREV**: REV with the sign flipped for names whose t0 fell in the formation week (hard news continues, no-news moves revert; Chan 2003) | **SEASON**: share of S&P 500 members reporting in the last 20 sessions | the news/no-news split matters when much news arrives | b > 0 for (NREV − REV) |
| H9 | **FMOM**: each of five factor books (MOM, REV, SREV, LOWVOL = minus 60-session volatility, HIGH52 = price over its 252-session high), held only while its own trailing return is positive | the factor's own trailing return (26 or 52 weeks) | factor momentum (Ehsani & Linnainmaa 2022) | b > 0 (pooled over the five factors, week-clustered) |
| H10 | **SECMOM**: long the top 3, short the bottom 3 of the 11 GICS sector equal-weight portfolios by 12-1 month return | **ACORR**: average correlation of residual returns across sectors (L = 21 or 63) | when sectors decouple, sector trends persist | b < 0 |
| H11 | **MOM** scaled by the inverse of its own realised volatility | **MOMVOL**: MOM book's realised volatility over the last 26 or 52 weeks | momentum crashes cluster when momentum is volatile (Barroso & Santa-Clara 2015) | b < 0 |

For H9 the conditioned book is the equal-weight mix of the factors in their "on" state, the unconditioned one all
five; the two variants are the 26- and 52-week trailing windows, and the forms binary (on/off) and linear (weight by
the percentile of the trailing return). H11's linear form scales by (1 − percentile); its binary form trades only
when MOMVOL is below its median.

---

## Amendment 2 (2026-11-07, before any round-3 statistic; the OOS sample is still unread)

**Round 2 result (development only).** Development t in the predicted direction: H7 1.26, H8 2.20, H9 −1.15
(factor *reversal*, not momentum: −1.84 at 26 weeks), H10 1.30, H11 0.50. **H8 is a finalist** (variant: 3-year
percentile history; form: linear). Its conditioned book still loses after costs in development (−0.52% a year,
turnover 1.7 a week), so on its own it cannot meet "worth taking forward" criterion 3.

**Round 3: four further hypotheses.** Same development rule, OOS rules, and Holm across all finalists of all rounds.

| | Strategy | Detector | Mechanism | Predicted |
|---|---|---|---|---|
| H12 | **H8 with a holding band** (cost-aware): each of NREV and REV enters at its top/bottom decile and keeps a name while it stays in its top/bottom 30%; the season regime blends them as in H8 | SEASON (as H8) | as H8; the band only lowers turnover | b > 0 for (NREV − REV), banded books |
| H13 | **Novel vs stale news** (31 names, names with news in the formation week): score = r5 × (2·rank(novelty) − 1), long the top third, short the bottom third, beta-hedged; unconditioned = REV on the same names | **NOVELTY**, per firm and week: 1 − cosine(the week's news centroid, the firm's trailing 13- or 26-week centroid), ranked across firms with news | stale news is over-reacted to and reverses, novel news is under-reacted to and continues (Tetlock 2011), measured in embedding space | b > 0: Fama–MacBeth slope on r5 × (rank − 0.5) of next-week residual return |
| H14 | **Factor reversal**: each of the five factor books held only while its own trailing return is negative | the factor's own trailing return, 26 or 52 weeks (decisions k−1−w .. k−2) | factor crowding unwinds (suggested by H9's development sign; stated here as a new hypothesis, so OOS decides) | b < 0 (pooled) |
| H15 | **Industry momentum, long history**: Ken French 49 industries (value-weighted, daily, 1926–2025): long the top 7, short the bottom 7 by 12-1 month return, equal weight, weekly | **IACORR**: average pairwise correlation of industry returns in excess of the 49-industry mean, over L = 21 or 63 sessions | when industries decouple, industry trends persist (H10's mechanism with 100 years of data) | b < 0 |

H15 has its own split: **development 1927–1999, OOS 2000–2025**, read once with the others; 2026 is not used. Its
costs: 5 bp per side on industry weights (tradeable through sector baskets or ETFs; no hedge, the book is dollar
neutral). H13's forms: binary (r5 if novelty above the cross-sectional median, else −r5) and linear (as in the
table); its variants are the 13- and 26-week trailing centroids.
