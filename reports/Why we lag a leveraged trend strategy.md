# Why we lag a leveraged trend strategy, and what to do about it

*2026-11-04. Analysis only: nothing in the traded fund, its protocol or the runner changes. Returns are in % per year
unless marked otherwise. Sharpe ratios use daily returns, are annualised, and take cash at 0 in every table, so the
rows compare like with like. Scripts and raw results are in [`research/trendspider/`](../research/trendspider/).*

---

## 0. Verdict

**The question rests on a false premise. The answer still exposes a real flaw in how we are set up.**

1. **The TrendSpider strategy does not beat the S&P.** It is a long-only, 2×-leveraged S&P ETF (SSO) traded on
   15-minute bars. Its page shows 4.6 years that start at the top of the 2022 bear market. It states no costs and
   compares itself with SSO, not with the S&P.
   * I rebuilt it from its published rules on ten years of 15-minute bars.
   * In the six years before its window (2016–22), the replica made **7.6% a year, against 16.2% for SPY
     buy-and-hold**. Its Sharpe ratio was 0.57 against 0.91 for SPY.
   * Only 6% of nearby parameter settings beat SPY over those years.
   * The probability that choosing it on past performance was overfitting is 0.65. Above 0.5, picking the best
     backtest makes you worse off than picking at random.

   It is a well-fitted backtest, not a strategy.

   **Short and long/short versions fail too** (§1.5, a second pre-registered round):
   * The same rules mirrored to the short side lost **7.9% a year** over 2016–26, including in the 2022 bear market.
   * Long/short together made **2.9% a year (Sharpe 0.24)**, against SPY's 15.4% (0.90).
   * The best-known *published* long/short intraday strategy on SPY (Zarattini, Aziz & Barbon 2024) replicates in
     its own sample: 20.2% a year, Sharpe 1.35 over 2016–24, against the paper's 19.6% and 1.33. **In the 22 months
     after its sample it lost 7.5% a year**, and both its long and its short legs lost money.
2. **Its headline still reveals what actually beats the S&P on paper: more S&P.** The strategy's results over its
   own window come from three things:
   * 2× leverage on the index;
   * a trend filter that sat out most of 2022 and April 2025;
   * a window that starts on that drawdown.

   Over the same window, the plain rule "hold SSO when it is above its 200-day average, else cash" made 16.9% a year.
   SPY made 13.3%. None of this involves information about companies.
3. **Our fund is built so that it cannot win the race the owner has set it.** The stated goal is "beat buy-and-hold
   of the S&P". The traded book is a long/short stock book **hedged to zero market beta**, so it holds no S&P at all.
   * To match SPY's roughly 10% a year it would need about 10% a year of pure stock-picking alpha, on top of cash.
   * The fund's own prior is a Sharpe ratio of 0–0.5 after costs ([`fund/README.md`](../fund/README.md)). At
     about 10% volatility that is **0–5% a year**.
   * So even the optimistic end of our own expectations loses to SPY in an average year, by design.
4. **The one lever that does move results against the S&P has been ruled out of research.** CLAUDE.md rule 17 says
   market exposure, leverage and hedges are "strategic policy, never tested or optimised". The traded book is
   beta-neutral. The 1.3×/0.7× SPY sleeve exists only in the research ledger (`fund/qshadow.py:59`).
5. **On the evidence so far, the stock-picking machine has shown no skill. It is also too complex and changes too
   often to show any within a useful time.**
   * The fund is down 3.8% in 5 weeks, against a roughly flat S&P (−1.1% to +0.5%, depending on the mark).
   * A *random* book on the same names lost about as much as the language-model books.
   * Nine pre-registered research reads produced one marginal pass.
   * The "frozen" design has been amended about eight times in five weeks.

The rest of this report backs each point and closes with a plan from the objective down to the code (§6).

---

## 1. The TrendSpider strategy, taken apart

### 1.1 What it is

| | |
|---|---|
| Instrument | **SSO**, ProShares Ultra S&P 500: twice the S&P's *daily* return, reset every day |
| Bars | 15 minutes, regular session; signal on a bar's close, fill at the next bar's open |
| Filter | 50-bar average above 200-bar average (≈ 2 vs 8 trading days), and ADX(10) > 20 (a trend-strength index) |
| Entry A | Close above the highest high of the previous 14 bars, on volume at least twice its 20-bar average |
| Entry B | The day's volume-weighted average price (VWAP) crosses above the close, RSI(14) > 50, and volume ≥ 1.5× average |
| Exits | Stop −3.5%; target +15%; trailing stop 7%; after 25 bars if losing; after 60 bars if up less than 1% |
| Sizing | 100% of equity, one position, long only |

The name "Opus 5.5" suggests a language model built it, presumably by searching rule combinations on the same window
it reports. Nine thresholds and lengths, two alternative setups and five exits leave a great deal of room to fit noise.

### 1.2 What the page actually claims

I decoded the equity curve embedded in the share page. Benchmarks over the same window come from daily closes:

| 2022-03-24 → 2026-11-03 | Return | Volatility | Max drawdown | Sharpe |
|---|---:|---:|---:|---:|
| TrendSpider, as published (no costs stated) | **22.3%** | 15.4% | −12.0% | ≈ 1.4 |
| SPY buy-and-hold | 13.3% | 16.7% | −22.1% | 0.83 |
| SSO buy-and-hold (the page's "111%") | 17.8% | 33.4% | −42.5% | 0.66 |
| SSO above its 200-day average, else cash | 16.9% | 20.9% | −19.4% | 0.86 |
| SPY above its 200-day average, else cash | 11.2% | 11.0% | −12.5% | 1.02 |

The yearly pattern shows where the result comes from (published curve):

| | 2022 (from 24 Mar) | 2023 | 2024 | 2025 | 2026 (to 3 Nov) |
|---|---:|---:|---:|---:|---:|
| TrendSpider | **+9.6%** | +31% | +8% | +33% | +22% |
| SSO buy-and-hold | −31.6% | +47% | +44% | +26% | +17% |

* It **lost to plain SSO in 2023 and 2024**, two of its four full years. The whole edge is not being invested in
  2022, plus partly avoiding the April 2025 tariff crash.
* That is a drawdown-avoidance result from one bear market. The window starts at the March 2022 high, which is the
  most favourable possible start for a trend filter.

**How much 4.6 years can tell us.**
* A Sharpe ratio's standard error is about √((1 + SR²/2)/years) ≈ 0.6 here, so the published 1.4 has t ≈ 2 for a
  *single* pre-specified test.
* Bailey and López de Prado's **deflated Sharpe ratio** asks how likely the true Sharpe is to be above zero, given
  how many variants were tried. On the replica's in-sample record:

| Variants tried | Expected best Sharpe if none works | P(true Sharpe > 0) |
|---:|---:|---:|
| 1 | 0 | 0.98 |
| 10 | 0.40 | 0.89 |
| 100 | 0.64 | 0.77 |
| 1,000 | 0.82 | 0.63 |

An LLM searching rules easily tries hundreds of variants, so the published record alone is weak evidence.

### 1.3 The replica and the out-of-sample test

The method was written down and committed before any result
([`research/trendspider/PREREG.md`](../research/trendspider/PREREG.md), commit `b702cbd`):
* Alpaca 15-minute bars (consolidated feed, split and dividend adjusted), January 2016 to November 2026.
* Two wording ambiguities were settled on the strategy's own window only, by matching the page (commit `068a188`).
* One read of 2016-03 → 2022-03, which the strategy's author never showed, at 2 bp per side.

**Fit to the page (in-sample).** 41% winning trades (page: 40%), average trade +0.80% (page: +0.96%), 105 trades.
Final wealth is 19% below the page's, so the replica makes 16.9% a year against the page's 22.3%. The residual gap
is the usual one between back-testers: data vendor, bar construction and exit timing. The replica is therefore
somewhat *less* flattering than the page.

**Out of sample, 2016-03 → 2022-03** (the one pre-registered read):

| | Return | Volatility | Max drawdown | Sharpe |
|---|---:|---:|---:|---:|
| **Replica, 2 bp per side** | **7.6%** | 14.9% | −24.6% | **0.57** |
| Replica, no costs | 9.9% | 15.1% | −24.2% | 0.70 |
| Replica, 2 bp, 2020 excluded (COVID treated as a regime) | 9.2% | | | 0.72 |
| SPY buy-and-hold | **16.2%** | 18.3% | −33.8% | **0.91** |
| SPY above 200-day average, else cash | 10.6% | 12.0% | −17.4% | 0.90 |
| SSO buy-and-hold | 27.8% | 36.7% | −59.4% | 0.86 |
| SSO above 200-day average, else cash | 10.7% | 23.0% | −42.1% | 0.56 |

**Pre-registered verdict: it does not replicate.** Its out-of-sample Sharpe is below both SPY's and the 200-day
rule's. It lost money in 2016 (−12%) and 2021 (−10%), a year in which SPY made +29%.

**Robustness.** 300 variants, each parameter moved −20%, 0 or +20%:
* Only **6%** of them beat SPY's Sharpe out of sample. The middle 80% sit between 0.19 and 0.85.
* The published setting has an in-sample Sharpe of 0.97, against **0.57 for the median of its neighbours**. It is an
  outlier in its own neighbourhood, which is the signature of a cherry-picked backtest.
* In-sample and out-of-sample Sharpe are **uncorrelated across the variants (ρ = −0.03)**, so a good in-sample number
  predicts nothing.
* **Probability of backtest overfitting** (combinatorially symmetric cross-validation, Bailey, Borwein, López de Prado
  and Zhu): **0.65**. Picking the best in-sample variant does worse out of sample than the median variant 65% of
  the time.

**Same rules on other ETFs, 2 bp per side** (descriptive only):

| Return / Sharpe | Replica 2016–22 | Buy-and-hold 2016–22 | Replica 2022–26 | Buy-and-hold 2022–26 |
|---|---:|---:|---:|---:|
| SPY (1×) | 7.8% / 0.91 | 16.2% / 0.91 | 2.8% / 0.36 | 13.3% / 0.83 |
| UPRO (3× S&P) | 11.5% / 0.61 | 36.5% / 0.85 | 9.4% / 0.51 | 19.9% / 0.61 |
| QLD (2× Nasdaq) | 5.5% / 0.38 | 40.7% / 1.00 | 8.6% / 0.48 | 19.9% / 0.63 |

The rules don't transfer, even to SPY in-sample, the very index SSO tracks. Whatever SSO did in 2022–26 was specific
to that path.

### 1.4 What it does teach

* **Beta is the cheap source of return. Leverage is how a backtest "beats the S&P".** Holding SSO earned about twice
  SPY's excess return, at twice its risk and a −42% to −59% drawdown. SSO also earned less than 2× SPY in 2022–26
  (17.8% against about 26%). Daily re-leveraging loses roughly the variance of the index each year, and a leveraged
  fund also pays financing (Cheng & Madhavan 2009).
* **Trend filters buy drawdown control, not return.** Over 2016–22, a lagging 200-day rule on SSO *cut* the return
  from 27.8% to 10.7% a year and *lowered* the Sharpe ratio, because it whipsawed in late 2018 and in the 2020 crash.
  In 2022–26 it helped. Over the long run that is the honest finding of the trend literature (§4). The pay-off is
  tail protection, and it depends on the regime.
* **What the TrendSpider author got right, in process if not in result.** One liquid instrument, a simple hypothesis,
  many years of intraday data, and an evaluation that takes seconds. We have none of those for the stock-picking
  book, because it can't be backtested at all (§3.4).

### 1.5 Second round: the short side, robustness, and a published long/short strategy

The owner's rule is that every strategy must be able to go short, so the second round tests short and long/short
versions, not only long ones. Its method was committed before any of its code existed
([`research/trendspider/PREREG_2.md`](../research/trendspider/PREREG_2.md), commit `4aaefe9`). Each confirmatory
number was computed once; results are in `research/trendspider/results/{B,C,D}.json`.

**B. The TrendSpider rules mirrored to the short side** (new rules, read once over 2016-03 → 2026-11).
* Costs are 2 bp per side, plus a 3% a year borrow fee while short.
* Before the read I checked that the long/short simulator, run long-only, reproduces the replica exactly (270
  trades, identical returns).

| 2016-03 → 2026-11 | Return | Volatility | Max drawdown | Sharpe | Trades | Winning trades |
|---|---:|---:|---:|---:|---:|---:|
| SSO long only (the replica) | 11.8% | 16.2% | −27.4% | 0.77 | 266 | 37% |
| **SSO short only (the mirror)** | **−7.9%** | 16.7% | **−64.5%** | **−0.41** | 271 | 21% |
| **SSO long/short** | **2.9%** | 22.5% | −59.8% | **0.24** | 495 | 30% |
| SPY long only / short only / long/short (descriptive) | 5.7% / −4.8% / 1.0% | | | 0.69 / −0.48 / 0.14 | | |
| SPY buy-and-hold | **15.4%** | 17.7% | −33.8% | **0.90** | | |

* **B1, short-only: FAIL.** The bootstrap probability that its mean return is ≤ 0 is 0.94.
* **B2, long/short: FAIL.** Its Sharpe is below both the long-only replica's and SPY's. The bootstrap probability
  that it does not beat SPY is 0.94.
* The short mirror **lost money even in 2022 (−4.8%)**, a year in which SSO fell 39%. Breakout shorts on a leveraged
  index ETF are stopped out by bear-market rallies. In the years the index rises (2016, 2017, 2021, 2024, 2026) they
  lose 13–19%.
* Shorting the S&P on momentum signals fights the market's positive drift. That drift is the single most reliable
  number in this report: about 15% a year since 2016.

**C. How robust the published long rules are** (descriptive; that read is spent).
* **Costs:** 0, 1, 2, 5 and 10 bp per side give 13.2%, 12.5%, 11.8%, 10.1% and 7.8% a year (Sharpe 0.84 down to
  0.54). Even at zero cost it is below SPY's 15.4% and 0.90.
* **Longer bars:** on 30-minute bars it makes 9.9% a year (Sharpe 0.77); on 60-minute bars, 10.4% (0.82).
* **Walk-forward selection.** Every 6 months, pick the best of the 301 variants on the previous 2 years and trade it
  for the next 6. Result over 2018–26: 12.1% a year, Sharpe 0.80. SPY over the same span made 14.2% at Sharpe 0.80.
  Choosing parameters on recent history ties SPY's risk-adjusted return at best and lags its return. **The published
  setting was never chosen** (0 of 18 segments).
* **Bootstrap**, replica minus SPY Sharpe over 2016–26: −0.13, 90% interval [−0.69, +0.41]. Ten years of 15-minute
  data can't separate this strategy from the index, and the point estimate is negative.

**D. Intraday momentum on SPY, long and short** (Zarattini, Aziz & Barbon 2024, the paper's final model).
* **Rules.** A position opens when SPY leaves its time-of-day "noise area" (the average move from the open at that
  time over the last 14 days). It goes long above the area, short below it, and the VWAP and the area's edge act as
  trailing stops. Decisions are made only on the half-hour; everything is flat at the close.
* **Sizing and costs.** Size targets 2% daily volatility, capped at 4×. Costs are the paper's ($0.0045 a share per
  side).

| | Return | Volatility | Max drawdown | Sharpe | NW t |
|---|---:|---:|---:|---:|---:|
| **2016-03 → 2024-12, inside the paper's sample (replication)** | | | | | |
| Full model, long and short | **20.2%** | 14.4% | −26.2% | **1.35** | 4.19 |
| Long leg only / short leg only | 11.1% / 8.2% | 8.6% / 11.9% | | 1.26 / 0.72 | |
| SPY buy-and-hold | 15.2% | 17.9% | −33.8% | 0.88 | |
| **2025-01 → 2026-11, after the paper's sample (confirmatory)** | | | | | |
| Full model, long and short | **−7.5%** | 14.3% | −23.2% | **−0.47** | −0.68 |
| Long leg only / short leg only | −2.0% / −5.6% | 7.3% / 12.2% | | −0.24 / −0.41 | |
| Costs doubled / next-bar fills / no volatility sizing | −8.3% / −7.4% / −1.3% | | | −0.53 / −0.47 / −0.19 | |
| SPY buy-and-hold | **16.0%** | 16.2% | −18.7% | **1.00** | |
| SPY risk-matched to the strategy's volatility | 14.2% | 14.3% | −16.7% | 1.00 | |

* **The implementation is right.** Inside the paper's sample it reproduces the published 19.6% a year and Sharpe
  1.33, at 15-minute rather than 1-minute resolution.
* **The pre-registered read fails.** The criterion was a positive mean with NW t ≥ 1.65, and t is −0.68.
* The read had only about 55% power, but the point estimate is not "small", it is negative. If the strategy's true
  Sharpe were the published 1.33, a result of −0.47 or worse over 461 sessions would have a probability of about 0.7%.
* **Both legs lost money** after publication: long −2.0% a year, short −5.6%.
* Inside its own sample it was also regime-dependent: it lost 12.5% in 2016 and 9.0% in 2017, two calm years, and
  made 61% in 2018.
* Its correlation with SPY is near zero (−0.04 to −0.08). That makes it a diversifier when it works and pure drag
  when it doesn't.

**What the second round shows:**
1. **Every short or long/short timing rule we tested on the S&P index lost to holding it.** The index's positive
   drift (about 15% a year over 2016–26) is a high bar for any rule that is sometimes flat or short.
2. **The published, peer-reviewed-style version did what McLean and Pontiff (2016) predict**: strong in its sample,
   gone afterwards. One more reason to judge every strategy only on data its author never saw.
3. **Nothing tested here beats SPY on data the author never saw.** That includes the TrendSpider rules (long, short
   and long/short), their walk-forward re-selection, longer bars, zero costs, and the best published intraday
   long/short model.

---

## 2. Our record, scored honestly

### 2.1 The traded fund

Alpaca paper account, broker net asset value:

| | 1 Oct 2026 | 3 Nov 2026 | 5-week return | Annualised (noisy) |
|---|---:|---:|---:|---:|
| Fund (the live book in force each week: weekly book, then from 15 Oct the position-lifecycle book) | 100,000 | 96,233 | **−3.8%** | ≈ −34% |
| SPY, close to close | 762.63 | 754.35 | −1.1% | ≈ −11% |
| S&P 500 buy-and-hold book on the shadow page (marked 4 Nov) | | | +0.5% | |

* Five weeks prove nothing statistically: one standard deviation of a 5-week return at about 10% volatility is about
  3%. **But nothing points the other way.** The fund lost 3.8% in a month when its stated yardstick was flat.
* The scorecard's first formal look is at 13 weeks. Its "fully executed 0%" row is a known defect: it reads a retired
  file.

### 2.2 The shadow books (all hedged long/short, 1 Oct → 4 Nov)

| Book | What it is | Return to date |
|---|---|---:|
| c2 self-consistency | analyst scores averaged over 5 samples | −8.8% |
| **random** | **10 longs and 10 shorts drawn at random from the covered names, same risk rules** | **−6.3%** |
| c5 reversal | news-conditioned short-term reversal | −5.9% |
| analyst | analyst scores, no red team | −5.8% |
| c0 weekly | the former traded weekly book | −5.3% |
| c3 text only | analysts with names masked | −4.5% |
| c4 vol-scaled | inverse-volatility sizing | −4.4% |
| c8 informed / c9 ranker | analysts with macro and peer context; a ranking pass | −4.4% / −4.3% |
| quant | price-factor (ridge) ranking over the whole S&P 500 | −1.0% |
| core20 | a fixed, arbitrary list of 20 large caps | +0.5% |
| S&P 500 buy-and-hold | yardstick | +0.5% |
| Position-lifecycle book (traded since 15 Oct) / its rule-change control | | 96,418 / 96,243 on 100,000 |

The owner's rule is that rankings mean nothing before mid-April 2027, and this report does not rank the books. It
reads two **gross** facts, which are not rankings:

1. **The random book sits in the middle of the language-model books.** Whatever cost everyone 4–9% is common to the
   *covered set* (the names with unusual news attention) and to the hedge, not to the analysts' judgement. The shadow
   books share a universe, a portfolio construction and a hedge, so **they measure the same thing nine times.**
   Their returns will be highly correlated, and the multiple-testing penalty for 11 challengers (an O'Brien–Fleming
   boundary at t = 5.44 at 13 weeks) means none can ever be promoted on a realistic edge.
2. **There is no book in the set that holds the market.** Every book is long/short around zero beta, with the S&P as
   a yardstick only. Nothing in the shadow set tests the lever that matters most against the owner's goal (§0.3).

### 2.3 The research programme, all pre-registered

| Idea | Read | Result |
|---|---|---|
| Technical entry levels and the follow-through gate (S&P 500, 2012–25) | holdout | **fail** (−19.7 bp a week, t −0.58) |
| News-embedding return models (31 names) | 2022–25 | **fail** (Holm p = 1) |
| Ridge on price factors, S&P 500 | 2013–25 | **fail** (IC −0.006) |
| MASTER transformer, 5-day horizon | 2013–25 | **pass**, but +0.4% a year net of 10 bp |
| Timestral, zero-shot | 2013–25 | **fail** |
| Cross-firm links (sympathy reversal, Lazy Prices…) | sealed 2026 | **fail** (wrong sign) |
| Earnings surprise continuation; hard 8-K | validation 2022–25 | **fail** |
| Soft-news positions | 2025–26 | **STOP** |
| Hard-news precision | 2016–26 | ≈ **break-even** (−2.6 bp net per trade) |

Nine reads and one thin pass. The work is rigorous, and the negative results are honest and well documented. The
pattern is also exactly what the literature predicts for this search space:
* large-cap US stocks;
* public news delivered hours late;
* weekly decisions;
* a fast, inexpensive language model.

These are the most efficiently priced securities in the world, using information everyone else has first.

---

## 3. Critique, without softening

### 3.1 The objective and the instrument contradict each other
"Beat buy-and-hold of the S&P" is a **total-return** goal. A beta-neutral long/short book is an **absolute-return**
product: its natural benchmark is cash plus a risk budget. Asking the second to beat the first means asking for
about 10% a year of pure alpha from a design whose own documents expect 0–5%.

Since 2009, the US market's Sharpe ratio has been about 0.8–0.9. A market-neutral book needs a Sharpe of about 1 at
10% volatility just to tie SPY, which is hedge-fund-top-decile territory. Every other choice in the fund sits
downstream of this mismatch.

### 3.2 The strategic policy fence is in the wrong place
Rule 17 protects exposure choices from data mining. That is a legitimate worry, as the TrendSpider strategy shows.
But the rule also blocks *pre-registered, long-history* research on the one dimension where:
* the literature is a century deep;
* the data are free (S&P daily from 1928; Ken French factors from 1926);
* the effect on the owner's goal is first-order.

We spend pre-registration effort on 5-week news edges and none on the market exposure that determines most of the
P&L against the stated benchmark. The fence should block *tuning*, not *testing*.

### 3.3 The design is not frozen, so the forward test can never conclude
* Protocol 6 ran from 30 Sep. Protocol 7 started 14 Oct, with the clock restarted. Amendments 8 and 9 went live
  27 Oct. Protocol 7B started 28 Oct, with the clock restarted again. 7B Amendment 1 followed on 30 Oct, and
  Amendments 2 and 3 take effect 5 Nov.
* That is about eight decision-changing changes in five weeks, under a rule that says "the traded fund is frozen".
* Each change is reasonable on its own; together they guarantee that no 13-week look ever happens on a single design.
* Power arithmetic: detecting a true Sharpe of 0.5 at t = 2 needs about 16 years of a fixed design. A Sharpe of 1.0
  needs about 4 years. The pre-registered first read at 52 weeks can only catch a Sharpe above about 2, which nobody
  expects.
* **The forward test, as run, is a monitor of gross failure, not a measurement of skill.** That is acceptable if
  everyone says so. It is not acceptable as the basis of a "go-live" decision.

### 3.4 We chose the only kind of edge that can't be backtested
* Language-model judgements about news can't be backtested, because the model has read the outcomes (look-ahead
  bias; Glasserman & Lin 2023 show that the model's general knowledge about the firm can do even more harm than the
  look-ahead itself).
* So every idea needs months of forward data, while a rule-based idea can be checked on 10–30 years in seconds.
* The cost of that choice is that **we learn at the speed of the calendar.** The TrendSpider author learned at the
  speed of a CPU, and overfitted. We learn slowly and so far have nothing to show for it. Neither is a good place.

### 3.5 The information we trade on is late and thin
* Finnhub serves articles **1.5–3 hours late**, and the live kill checks read only **43%** of the articles.
* The weekly cohort enters a day after the news. Across four cohorts, the mean absolute abnormal move on the entry
  day *before* we trade was 2.8%: GOOGL moved +12% and LRCX +11% before entry.
* Earnings are judged from headlines, without the numbers or the consensus (the AAPL case, PR #139).
* Whatever the model's reasoning, it acts on the second-hand, late slice of public information.

### 3.6 Costs are large against a small expected edge
* Turnover is **40–68× NAV a year**. At the registered 5 bp per side that is 2–3.4% a year, 0.19–0.32 Sharpe:
  most of the fund's own prior.
* Language-model calls cost $13–23 a week, about **$700–1,200 a year**, which is **0.7–1.2% of a $100k book**. On real
  capital of that size, the API bill alone eats a quarter or more of the optimistic alpha.
* The TrendSpider strategy trades about 20–25 times a year at near-zero cost.

### 3.7 Complexity has outgrown the evidence
* Around 11,000 lines across `fund/*.py`, 17+ desks, 12 shadow books, a Mac launchd runner, three data branches and
  about 110 pull requests since late September.
* The incident log is long. A file-name rule fed 7 of 20 cards an 8-K cover page. A decided amendment sat unmerged
  for 10 days. The installed runner predated the rules it was meant to run, so the control book never ran. The gate
  reads a retired file. Abandoned LLM calls were billed for twice what the log showed.
* None of these is a sign of carelessness; each was found and fixed. They are the sign of a system whose operational
  surface is far larger than its demonstrated edge.
* Every desk without evidence of value is a source of incidents, cost and amendment pressure.

### 3.8 Earlier internal reviews were too generous
The October pipeline review ([`Fund pipeline against research and forums.md`](Fund%20pipeline%20against%20research%20and%20forums.md))
concluded that "the execution is right" and that the research programme was "aligned". Both were true, and both
answered the wrong question. It is now clear that:
* execution quality (+0.6 bp slippage) is irrelevant when the expected edge is about zero;
* "aligned" research that keeps failing is a signal about the search space, not a reason to keep searching it.

### 3.9 What is genuinely good, and worth keeping
* **Pre-registration with one-shot reads.** It is the reason we *know* the nine ideas failed, instead of believing
  a TrendSpider-style curve. It is rare even in professional shops.
* **The input and output guardrails** (`fund/guards.py`, CLAUDE.md rules 1–12): typed inputs, grounding checks,
  fail-loudly gates.
* **Honest negative results**, documented with their defects.
* **Execution infrastructure** that fills at the close within a basis point.

That is a solid research *process* aimed at a target where the expected prize is close to zero.

---

## 4. What the literature says

**Trend following and time-series momentum.**
* Faber (2007, *Journal of Wealth Management*) popularised the 10-month and 200-day rule: similar returns to
  buy-and-hold, with much smaller drawdowns.
* Moskowitz, Ooi & Pedersen (2012, *Journal of Financial Economics*) show 12-month time-series momentum across 58
  futures markets.
* Hurst, Ooi & Pedersen (2017, *Journal of Portfolio Management*) extend the evidence to a century.
* The consistent finding is that trend works **across many diversified markets** and pays off in crises. On a single
  equity index it is mostly a drawdown hedge: little or no return improvement, and losses in V-shaped recoveries
  (2018, 2020). Our 2016–22 table above is a textbook case.

**Volatility management.**
* Moreira & Muir (2017, *Journal of Finance*): scaling exposure by the inverse of recent variance raised Sharpe
  ratios for the market and for factors.
* Cederburg, O'Doherty, Wang & Yan (2020, *Journal of Financial Economics*) find the gains largely fail to hold up in
  real-time, out-of-sample implementations across many factors.
* DeMiguel et al. (2024, *Journal of Finance*) find that a multifactor version can be rescued.
* For a market core, volatility targeting is a reasonable, cheap *risk* policy, not an alpha source.

**Leverage.**
* Frazzini & Pedersen (2014, *Journal of Financial Economics*, "Betting against beta") argue that leverage-constrained
  investors overpay for high-beta assets. That makes **modest, cheap leverage on a diversified core** the efficient
  way to take more risk, not stock picking or leveraged ETFs.
* Cheng & Madhavan (2009, *Journal of Investment Management*) document the daily-reset decay of leveraged ETFs and
  their volatility-dependent path.

**Intraday market momentum.**
* Gao, Han, Li & Zhou (2018, *Journal of Financial Economics*): on SPY, 1993–2013, the first half-hour's return
  predicts the last half-hour's.
* Zarattini, Aziz & Barbon (2024, Swiss Finance Institute RP 24-97) report an intraday SPY momentum strategy at 19.6%
  a year and Sharpe 1.33 net of costs over 2007–24.
* This is the *credible* version of what the TrendSpider strategy gestures at. **We tested it (§1.5 D):** it
  replicates in its own sample and lost 7.5% a year in the 22 months after it.

**Backtest overfitting and multiple testing.**
* Bailey & López de Prado (2014, *Journal of Portfolio Management*): the deflated Sharpe ratio.
* Bailey, Borwein, López de Prado & Zhu (2017, *Journal of Computational Finance*): the probability of backtest
  overfitting.
* Harvey, Liu & Zhu (2016, *Review of Financial Studies*) argue that a new factor needs t > 3.
* The TrendSpider strategy fails all three. Our programme applies them, which is why it keeps saying no.

**Decay of published anomalies.** McLean & Pontiff (2016, *Journal of Finance*): returns fall about 26% out of
sample and 58% after publication. Large-cap, public-information signals decay fastest.

**Language models and news.**
* Lopez-Lira & Tang (2023, working paper) found next-day predictability from ChatGPT headline scores. It is
  concentrated in small stocks and in the days after the news, and it shrinks as the models spread.
* Glasserman & Lin (2023, arXiv 2309.17322) show look-ahead and "distraction" biases in exactly this kind of
  backtest.
* The literature's expected edge for large-cap names at a weekly horizon, after costs, is close to zero. Our own
  hard-news estimate (−2.6 bp net per trade) agrees.

---

## 5. Root causes, in one line each

1. **Wrong benchmark for the product:** a zero-beta book judged against a 100%-beta index.
2. **The lever that matters is outside the research fence:** exposure is policy, untested.
3. **The edge is sought in the most efficient corner of the market**, with late, public, second-hand information.
4. **The edge chosen can't be backtested**, so learning runs at calendar speed.
5. **Design churn** resets the only clock we have.
6. **Costs (turnover plus the API bill) are the same size as the plausible alpha.**
7. **Complexity is out of proportion to the evidence**, which generates incidents, which generate amendments.

---

## 6. How to proceed, top to bottom

Each item says what class of change it is under the repository's rules: **owner decision**, **operational fix**,
**dated amendment** (pre-registered, mechanical) or **new protocol**. Merges follow CLAUDE.md rule 15. The safe
windows are weekends, and Mon, Tue and Fri 02:00–15:30 UTC.

### Level 1: the objective (owner decision, this weekend)
1. **Pick one of two honest objectives and write it into the protocol.**
   * **(A) Core-satellite (recommended).** The fund = an S&P core + the long/short book as an overlay. The goal is
     "beat SPY buy-and-hold on total return and on Sharpe". With zero alpha the fund ties SPY minus costs, the
     correct null. Every basis point of real stock-picking alpha shows up directly against the owner's yardstick.
   * **(B) Absolute return.** Keep the beta-neutral book and judge it against cash and a risk-matched SPY at its own
     volatility. Stop saying it should beat SPY.
2. **Report one headline number per book:** total return in % a year next to SPY and a risk-matched SPY, with the
   drawdown, and a power statement saying what size of edge the current sample could detect.

### Level 2: market exposure (owner decision, then a new protocol, P8-core)
3. **Amend rule 17 from "never tested" to "never tuned on recent data; tested once, pre-registered, on long
   history".**
4. **Pre-register an exposure study on free, long data.** S&P daily total return 1928–2026, plus 2016–26 Alpaca bars
   as a modern check. One read, with Holm correction across at most four candidates:
   * constant 1.0× (the null);
   * constant leverage matched to a 15% volatility target;
   * a volatility-targeted core in the spirit of Moreira–Muir, capped at 0–1.5×;
   * the owner's 1.3×/0.7× 200-day sleeve, *tested for the first time rather than assumed*.

   Pass criterion: Sharpe above the 1.0× core at t ≥ 2 after deflation, with the drawdown not worse. My expectation,
   stated in advance: volatility targeting passes on drawdown and roughly ties on Sharpe; the 200-day sleeve does not
   beat a constant risk-matched exposure.
5. **Implement the winner with SPY plus margin (≤ 1.5×), not leveraged ETFs.** Daily-reset decay and fees make SSO
   and UPRO poor long-term holdings (§1.4).

### Level 3: the stock-picking book (the traded fund)
6. **A real freeze, from the session of 5 Nov (7B with Amendments 2 and 3), to the 13-week look in late January
   2027.** No decision-changing amendment, whatever the trade log shows; findings go to a queue for the next protocol.
   This is the single cheapest way to make the forward test mean anything.
7. **Pre-register a kill rule now.** At 26 weeks (late April 2027), if the book's excess return over cash has
   NW t < 0, or it has not beaten the random book, it stops. The capital then goes to the core. *(dated amendment)*
8. **In the next protocol, cut to the components with evidence.**
   * Keep the hard-news, primary-source earnings path (PR #139: EX-99.1 numbers against a frozen consensus).
   * Drop the remaining soft-news machinery.
   * Measure the ideation, red-team and narrative desks with the decision ledger at 13 weeks. Remove any desk with
     no positive contribution.
   * Aim for a quarter of today's desk count. *(new protocol)*
9. **Cut turnover by design, not by tweaking.** Fewer, longer, event-anchored positions (an earnings-to-earnings
   horizon, the P8 plan's no-trade band) instead of weekly cohorts. *(new protocol)*
10. **Fix information latency at the source.** SEC EDGAR real-time filings are the primary trigger; Finnhub is
    confirmation only. Enter at the first close after a filing, not the next Thursday. *(new protocol; the order-timing
    report already specifies it)*

### Level 4: the shadow books (operational and dated amendment)
11. **Stop adding variants of the same book.** A tenth long/short variant on the same covered names adds cost, not
    information.
12. **Add orthogonal yardsticks that answer the owner's actual question.** All of them are deterministic and cost
    nothing to run:
    * SPY 1×;
    * a risk-matched SPY;
    * SPY with a 200-day rule;
    * a volatility-targeted SPY;
    * 60/40 (SPY/IEF);
    * equal-weight S&P (RSP);
    * a factor sleeve (MTUM, QUAL, USMV).
13. **Retire c2–c5, c8 and c9 at the end of their registered window**, on grounds of redundancy (correlation with c0
    and with random), not ranking, so the April 2027 rule is respected. Keep c0, analyst, quant, random and the 7B
    control.
14. **Do not run the TrendSpider strategy as a forward book.** It failed its pre-registered read. Keep the replica as
    a worked example of overfitting (§7).

### Level 5: the research programme
15. **Stop mining large-cap public news at short horizons.** Nine reads have answered that question. Close it with a
    memo.
16. **Before any new idea, apply DESIGN_RULES' power bar (≥ 0.5 power before a read)**, and prefer ideas with:
    * long free history;
    * a known economic reason;
    * evidence outside the US large-cap set.
17. **Candidates that still meet the bar** (intraday SPY momentum has now been tested and **failed** after its
    sample, §1.5 D; the index-timing family is closed):
    * **(a) The volatility-targeted core of item 4.** It is the only candidate aimed at the owner's goal that the
      tests above don't contradict. It is a risk policy, not an alpha bet.
    * **(b) Earnings-surprise drift in mid and small caps** (S&P 400/600), where the anomaly survives better than in
      the large caps where our version failed. Long and short by construction.
    * **(c) Optional:** keep the intraday momentum model as a zero-cost forward paper record from November 2026, as
      a check on whether 2025–26 was a regime or the end of it. Judge it no earlier than 2028, and never trade it on
      the in-sample record.
18. **Keep the MASTER 5-day forward book and R5 on their registered schedules.** They are running and cheap. Read
    them when registered, not before.

### Level 6: engineering and operations
19. **Shrink the surface.** Delete desks that no protocol uses, merge duplicated monitors, and keep one dashboard
    with the Level-1 headline numbers. Target under half of today's `fund/` line count by the next protocol.
20. **Automate the failure classes that cost us this month:**
    * a CI check that every "decided" amendment is on `main` before its effective date;
    * a check that the runner's installed version equals `main`;
    * a daily comparison of the API bill against the call log.
21. **Budget the API spend as a cost line in the score** (at about 1% of NAV a year it is not negligible), and set
    the model per desk by the fixture-based contract tests, as already started for GLM.

### Level 7: evaluation and governance
22. **Hold one date-certain decision point: 31 March 2027.**
    * Write the criteria now: the core study result, the stock-picking book's NW t against cash, the random-book
      comparison, cost per year.
    * Each outcome maps to a pre-written action: continue, shrink or stop.
23. **A checklist for any external "beats the S&P" claim**, applied before anyone spends a week on it:

    | Question | TrendSpider SSO |
    |---|---|
    | Benchmark: the index, or itself? | itself (SSO), not SPY |
    | Leverage or beta above 1? | yes, 2× |
    | Window start relative to a drawdown? | starts at the 2022 top |
    | Costs stated? | no |
    | How many variants were tried? | unknown; LLM-searched |
    | Out-of-sample record? | none published; our read fails |
    | Does it transfer to related instruments? | no |
    | Does its short or long/short version work? | no: short −7.9%, long/short +2.9% a year against SPY's 15.4% |

---

## 7. Appendix: reproduce

```
python3 research/trendspider/download.py           # through the redacting wrapper (CLAUDE.md rule 16); Alpaca 15-min bars
python3 research/trendspider/replica.py calibrate  # in-sample variant choice -> results/calibration_in_sample.csv
python3 research/trendspider/replica.py read plus/vwap_over   # the one read -> results/read.json, read_table.csv
PYTHONPATH=research/trendspider python3 research/trendspider/tests2.py B   # short mirror, long/short (once)
PYTHONPATH=research/trendspider python3 research/trendspider/tests2.py C   # robustness of the long rules
PYTHONPATH=research/trendspider python3 research/trendspider/tests2.py D   # intraday momentum, long and short (once)
```

* The published TrendSpider curve was decoded from the share page's embedded chart data: 1,001 points,
  2022-03-24 → 2026-11-03.
* Live fund figures: `fund-data` branch, `fund_state/live/execution/nav.csv`, `ledger/shadow.json` and
  `performance/gate.md`, as of 2026-11-04.
* The replica's equity is marked at 15-minute closes; daily figures use the last bar of each session.
* Yearly returns, 2 bp per side (calendar years):

| Year | Replica (SSO) | SSO buy-and-hold | SSO 200-day | SPY buy-and-hold | SPY 200-day |
|---|---:|---:|---:|---:|---:|
| 2016 (from 4 Jan) | −12.3% | +25.2% | +11.5% | +13.0% | +5.9% |
| 2017 | +20.6% | +44.3% | +44.3% | +21.7% | +21.7% |
| 2018 | +17.6% | −14.6% | −19.6% | −4.9% | −2.5% |
| 2019 | +32.7% | +63.5% | +28.9% | +31.1% | +16.7% |
| 2020 | +3.5% | +21.5% | −9.0% | +18.3% | +9.9% |
| 2021 | −10.3% | +60.6% | +60.6% | +28.7% | +28.7% |
| 2022 | −4.6% | −39.0% | −25.5% | −18.2% | −14.8% |
| 2023 | +28.0% | +46.6% | +13.0% | +26.2% | +15.5% |
| 2024 | +10.4% | +43.6% | +43.6% | +24.9% | +24.9% |
| 2025 | +18.6% | +26.2% | +17.2% | +17.7% | +11.9% |
| 2026 (to 3 Nov) | +27.8% | +17.1% | +10.0% | +11.5% | +7.0% |

## Sources
* TrendSpider, ["SSO Opus 5.5 Swing 15m"](https://share.trendspider.com/strategies/79a84053fa45a1b7f292091e?t=1), shared 2026-11-03.
* Gao, Han, Li & Zhou, [Market intraday momentum](https://econpapers.repec.org/RePEc:eee:jfinec:v:129:y:2018:i:2:p:394-414), JFE 129(2), 2018.
* Zarattini, Aziz & Barbon, [Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)](https://ideas.repec.org/p/chf/rpseri/rp2497.html), SFI RP 24-97, 2024.
* Moreira & Muir, [Volatility-Managed Portfolios](https://www.nber.org/papers/w22208), Journal of Finance 72(4), 2017.
* Bailey, Borwein, López de Prado & Zhu, [The Probability of Backtest Overfitting](https://papers.ssrn.com/abstract=2326253), Journal of Computational Finance.
* Cheng & Madhavan, [The Dynamics of Leveraged and Inverse Exchange-Traded Funds](https://www.joim.com/the-dynamics-of-leveraged-and-inverse-exchange-traded-funds/), JOIM 7(4), 2009.
* Glasserman & Lin, [Assessing Look-Ahead Bias in Stock Return Predictions Generated by GPT Sentiment Analysis](https://arxiv.org/abs/2309.17322), 2023.
* Also cited, standard references: Faber (2007); Moskowitz, Ooi & Pedersen (2012); Hurst, Ooi & Pedersen (2017);
  Frazzini & Pedersen (2014); Cederburg, O'Doherty, Wang & Yan (2020); DeMiguel et al. (2024); Bailey & López de
  Prado (2014); Harvey, Liu & Zhu (2016); McLean & Pontiff (2016); Lopez-Lira & Tang (2023).
