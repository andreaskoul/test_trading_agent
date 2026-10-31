# Fund pipeline against research and forums

*30 October 2026. A component-by-component comparison of every model, pipeline and decision rule in the fund and its
research programme against three bodies of evidence: the academic literature, industry practice and practitioner
forums and chats. Companion to [Order timing literature and practice](Order%20timing%20literature%20and%20practice.md);
the source notes are in [`research_notes/Order timing literature and practice/`](../research_notes/Order%20timing%20literature%20and%20practice/).
Returns are % per year unless marked otherwise.*

## Verdicts first

The fund is a **news-driven, beta-hedged long/short book in S&P 500 stocks**. Its parts are:

* **Signal:** a language model reads company news and scores it.
* **Portfolio construction:** at most 10 names a side, weights from score × confidence, sector and net-exposure caps,
  and an SPY hedge to zero beta.
* **Rebalancing:** event-driven position lifecycles. Each position has a holding horizon, stop and target barriers,
  and news-triggered exits.
* **Execution:** orders sent every trading day in the last minute before the close.

The evidence gives one clear verdict. **The execution is right. The value is decided upstream, by when information
reaches the decision and by which kinds of news the book holds.**

| # | Component | Verdict | Change class |
|---|---|---|---|
| 1 | "Already priced in" fraction behind the horizon | **Fix.** It cannot see an after-close release on the as-of day: same news, 24-session vs 3-session horizon depending on the release day | dated amendment |
| 2 | News window and the weekly blind window | **Fix.** Late-served articles are never checked; new entries get no news check between Wednesday evening and entry | dated amendment |
| 3 | Soft-news positions (launch, partnership, rumour, macro, leadership) | **Test decisively on the archive, then likely drop or fade.** Best current evidence puts them at negative expected value after costs | offline research → next protocol |
| 4 | News-driven exits and increases | **Condition on hard vs soft news.** Exit on hard adverse news; hold through soft adverse news | next protocol (shadow first) |
| 5 | Go-live scorecard | **Fix.** It reads retired files (shows 0% executed) and tests dispersion, not cost | operational + dated amendment before the first 13-week look |
| 6 | Shadow control of the 2026-10-28 rules | **Fix now.** It checks news five hours later than the live book, a built-in bias in its favour | operational (before any comparison) |
| 7 | Decision and execution logging | **Add.** Decision-price timestamps and quotes, the vendor's per-article delay, the entry-day move, and the close sources | operational |
| 8 | Pre-close market orders at T−60 s | **Keep.** Close-auction orders are for go-live only, with a 15:45 decision and a market-order fallback | keep; go-live protocol |
| 9 | Cost assumption 5 bp per side | **Keep as registered. Report measured costs beside it.** Turnover, not price per trade, is the lever | reporting |
| 10 | Stop and target barriers | **Keep, and expect nothing from them.** Under no drift they fire on 2–3% (stop) and 0.1–0.2% (target) of positions | none |
| 11 | Whole-share rounding, the T−3 min decision price | **Keep.** Economically negligible, shown below | none |
| 12 | SPY sleeve timing (owner's policy) | **Keep.** A one-day lag costs nothing measurable for a 200-session trend rule. Log the distance to the threshold | none (policy) |
| 13 | Timing shadow books (Wednesday close, Thursday open) | **Do not read them for years.** Plausible delay costs need a decade or more of weeks to detect | evaluation |
| 14 | Research programme (R5, P8, transformer and quant trials) | **Aligned.** R5 is the only component aimed at the price reaction itself; protect its pre-release timestamps | none |

The change classes follow the repository's rules (CLAUDE.md rules 13–14):

* **Operational:** cannot change a trading decision; needs a CHANGELOG line.
* **Dated amendment:** changes decisions, so it is written with mechanical criteria before any outcome is examined,
  and the owner decides.
* **Next protocol or shadow:** a new hypothesis. It is never judged before the owner's mid-April 2027 horizon.

---

## 1. Where the money is in a news event

Every comparison below rests on one decomposition, so it comes first.

### 1.1 The path of an event's abnormal return

Write the abnormal (beta-adjusted) return of a stock after news released at time 0 as

$$A(t) \;=\; \underbrace{J}_{\text{reaction}} \;+\; \underbrace{D\,(1-e^{-t/\tau_f})}_{\text{fast drift}} \;+\; \underbrace{S\,(1-e^{-t/\tau_s})}_{\text{slow drift}} \;-\; \underbrace{V(t)}_{\text{reversal}}$$

A book that enters at lag $\ell$ earns only $A(\infty) - A(\ell)$: what is left after it arrives. What the evidence says
about each term for US large caps, in data since 2005:

| Term | Size and speed | Evidence |
|---|---|---|
| Reaction $J$ | Most of the move, absorbed in seconds to minutes. Earnings: about 70% of price discovery within 5 minutes. On announcement days, 80% of discovery happens 16:00–18:30 after hours. Over 95% of earnings are released outside regular hours (99.1% of S&P 1500 firms, 2011–15) | [Christensen, Timmermann & Veliyev, arXiv 2601.08962](https://arxiv.org/abs/2601.08962); [Grégoire & Martineau 2022](https://papers.ssrn.com/abstract=3060094) |
| Fast drift $D$ | About **11 bp on the day after news** for stocks above the NYSE median; complete after one day; half-life about 1 day ($\tau_f \approx 1.4$ days) | [Ke, Kelly & Xiu](https://www.nber.org/system/files/working_papers/w26186/w26186.pdf); [Heston & Sinha](https://www.federalreserve.gov/econresdata/feds/2016/files/2016048pap.pdf) (day 0: 1.99%, day +1: 0.17%, day +2: 0.04%) |
| Slow drift $S$ | Absent above microcaps since about 2006 for earnings surprises. Small positive continuation after hard, quantified news (2023–26, days 6–20): earnings +0.22%, guidance +0.13%, analyst actions +0.10%, capital returns +0.35% | [Martineau, "Rest in Peace PEAD"](https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf); [Kargarzadeh et al., arXiv 2608.14014](https://arxiv.org/abs/2608.14014) (workshop paper, mixed sizes) |
| Reversal $V$ | After soft news (2023–26): macro read-throughs −0.34%, product launches −0.18%, leadership −0.18%, competition −0.17% over days 6–20. Days 1–5, raw: launches, macro and M&A deals about −0.22% each. M&A rumours: everything happens on the rumour day | [Kargarzadeh et al.](https://arxiv.org/abs/2608.14014); no-news moves reverse, identified-news moves continue ([Boudoukh et al.](https://www.nber.org/papers/w18725)) |

The forums agree, and here they are unanimous. A news-bot builder found newswire feeds update "5-10 minutes after the
article is meant to go live". A latency-sensitive reply: "The market is pricing everything in from the news drop 10
milliseconds in" ([r/algotrading, Nov 2025](https://www.reddit.com/r/algotrading/comments/1ozljry/news_feed_latency)).
Another: "by the time your sentiment signal is computable the [market has] already moved… that's usually where these
die". This is **[CONSENSUS]**: no credible voice disputes it.

### 1.2 What this book can capture

The fund decides once a day, a minute before the close, on news that reaches it 1.5–3 hours late (section 3.1). For
it, $J$ is gone by construction. The expected P&L of a position of weight $w$ is

$$\mathbb{E}[\text{P\&L}] \;=\; w\,\big(D e^{-\ell/\tau_f} + S e^{-\ell/\tau_s} - V\big) \;-\; 2c\,|w|$$

Here $c$ is the cost per side. Put in the literature's numbers, for a lot entered one to two days after the news and
held for its horizon:

| Event class | Drift left at entry | Round trip at the registered $c$ = 5 bp | Round trip at the estimated live $c$ = 1.5 bp | Expected value per unit of weight |
|---|---|---|---|---|
| Hard (earnings, guidance, analyst, capital return) | +10 to +22 bp, partly front-loaded | −10 bp | −3 bp | **about 0 to +19 bp** |
| Soft (launch, partnership, leadership, macro, rumour) | −17 to −34 bp (reversal) | −10 bp | −3 bp | **about −20 to −44 bp** |

The book's new-entry gross is about 26× NAV a year (cohorts of 38–64% of NAV a week), split roughly half and half
between the classes (30 hard, 33 soft or other among the 63 entries so far). That gives an order-of-magnitude budget:

$$\underbrace{13 \times (0 \text{ to } 0.19\%)}_{\text{hard: } 0 \text{ to } +2.5\%/\text{yr}} \;+\; \underbrace{13 \times (-0.20 \text{ to } -0.44\%)}_{\text{soft: } -2.6 \text{ to } -5.7\%/\text{yr}}$$

**On the best per-type evidence available, the soft-news half of the book costs as much as the hard-news half earns,
or more.**

This is the most consequential number in the report, and its evidence is the weakest link:

* The per-type drift comes mainly from one non-peer-reviewed 2023–26 study on mixed-size stocks.
* The fund's own 8,924-event drift study (price-gap events, 2012–2025) found no significant drift at any horizon to
  20 sessions, from either entry time ([technicals_backtest.md](research/technicals_backtest.md)).
* The language model and red team may select better-than-average soft events.

This is why item 3 is "test decisively on the archive" rather than "drop now". It is cheap to test: section 4.1.

### 1.3 The three places an edge can live

The decomposition leaves three places, and the fund's components map onto them:

1. **Forecast the reaction $J$ before the release.** This is the only way to own the large term. It is what **R5**
   does: forward predictions for each earnings report, timestamped before the 8-K is accepted (section 3.11).
2. **Select events with slow drift $S$:** hard, complex, cross-firm or low-attention news. This is what the horizon
   model tries to do with its event types and its attention and complexity multipliers.
3. **Avoid or fade the reversal $V$.** The fund does not do this. It enters soft news in the news direction.

Execution timing affects only the cost term. It cannot create value; at best it stops destroying it. That is why the
execution verdicts below are short.

---

## 2. How the sources are weighted

* **Academic** results carry the most weight, with their sample periods. Pre-2005 and small-cap results are flagged.
* **Industry** sources are exchange rulebooks and research, TCA providers, broker documents and AQR's live trading
  data. Their facts about rules are authoritative; their effect sizes are often promotional.
* **Forums and chats** are labelled as in the notes:
  * **[CONSENSUS]:** several credible, independent voices and no credible pushback.
  * **[CONTESTED]:** credible voices disagree.
  * **[ANECDOTE]:** one person's experience.

  Identified professionals are weighted above anonymous posters: Rob Carver (ex-AHL), Corey Hoffstein (Newfound),
  Ernie Chan (QTS), Allocate Smartly, Concretum Group, and Proof Trading. Forums are most valuable on what papers
  skip: operational failure modes, broker quirks, the realism of paper fills, and how professionals deal with "decide
  on the close, trade on the close".
* **Our records** are 150 paper fills, 16 sessions of the lifecycle book, 63 cohort entries and 124 lifecycle events
  on the `fund-data` branch. They are used for measurement, never as evidence of edge. The owner's rule defers any
  verdict on books to mid-April 2027.

---

## 3. Component by component

### 3.1 Information set: the news feed and its windows

**What we do.**

* The live check reads articles published up to T−20 min, where T is the close.
* Each check takes only articles published after the previous check's cutoff.
* The weekly desk reads news to Wednesday 22:00 UTC; new positions are entered at Thursday's close.

**What we measured** (from [the audit](../research_notes/Order%20timing%20literature%20and%20practice/current_implementation_audit.md)):

* The newest article any live check saw was 95 minutes to about 2.8 hours older than its cutoff (median 2 h 49 min).
  Finnhub appears to serve articles 1.5–3 hours late.
* Checks run five hours after the close saw about 25% of the day's articles stamped in the two hours before the
  cutoff. Live checks saw 1.7%.
* Each window starts exactly at the previous cutoff. An article stamped before a cutoff but served after it falls in
  no window and is **never checked**.
* Between Wednesday 22:00 UTC and Thursday's entry, no news is read for the new cohort's names at all.

**What the sources say.**

* Retail newswire feeds lag 5–10 minutes ([r/algotrading](https://www.reddit.com/r/algotrading/comments/1ozljry/news_feed_latency)).
  Our feed lags 1.5–3 hours: roughly 10 to 30 times worse.
* Concretum Group's first production lesson is staleness ([Concretum](https://concretumgroup.com/building-reliable-trading-systems-algorithmic-trading-automation)):
  an algo "traded all afternoon on a price that hadn't updated since 11 AM… Connection status said connected". The
  fix: "track when each ticker was last updated and stop trading if the data becomes stale". **[CONSENSUS, firm-level.]**
  Our news feed has this exact failure, silently.
* Ke, Kelly & Xiu deliberately exclude the 30 minutes before the open "to calculate positions". A cutoff buffer is
  standard. A buffer that is silently three hours wide is not.

**Is the T−20 min cutoff itself worth defending?** No. With a 2–3 hour vendor lag, the gap between a T−20 cutoff and
a T−30 or T−45 cutoff contains almost no articles. That matters for section 3.6: the cutoff can move earlier at almost
no information cost if a close-auction design is ever wanted.

**Verdict.**

* **(a) Operational, now:** log, for every article, its publish time and the time we first saw it. This turns the
  vendor-lag estimate into a measurement. Add an alert when the newest article is older than a set limit.
* **(b) Dated amendment:** select articles for a check by "not yet checked" (first-seen time) instead of by publish
  time, so none falls between windows. This restores the registered intent ("only stories new since the last
  check"). It still changes which articles the checker sees, so the owner decides.
* **(c) Dated amendment:** run the T−20 news check on the new cohort's names on entry day, before they are entered.
  This closes the blind window.

### 3.2 The weekly signal and the Thursday entry: "the market has moved on the news"

**What we do.** The signal is formed on information to Wednesday evening and entered at Thursday's close: a lag of
about 22–23 hours. For news released after Wednesday's close, the lag runs past the whole Thursday session.

**What we measured.**

* Across the four cohorts so far (63 entered names), the mean absolute abnormal move from Wednesday's close to our
  Thursday entry was **276 bp**: 341 bp for hard news, 217 bp for soft. 34 of 63 names moved more than 2%.
* The signed mean was −32 bp (t = −0.7). On average the entry-day move was neither for nor against us, but it was
  large.
* Earnings released after Wednesday's close:
  * GOOGL (short) fell about 12% on Thursday 29 Oct, before our entry.
  * LRCX (short, 22 Oct) fell about 11% before entry and rebounded about 9.5% after.
  * CSX (long, 22 Oct) rose about 8% before entry and 0.4% after.
  * These are yfinance closes with beta 1.

**What the sources say.**

* By the next open, after-hours earnings for liquid stocks are essentially priced (section 1.1).
* A one-day delay costs a daily-horizon text signal **25–65% of its implementable drift**
  ([notes §2](../research_notes/Order%20timing%20literature%20and%20practice/academic_news_latency.md)). A weekly or
  multi-week signal loses only 5–15%.
* Practitioners split into two camps:
  * "Decide just before the close and send close-auction orders" (QuantConnect staff, Quant SE).
  * "Build a deliberate one-day lag into the backtest" (Carver; Allocate Smartly).

  Allocate Smartly measured the lag at −0.02%/yr for monthly asset-allocation signals, but harmful in fast markets
  such as March 2020 ([Allocate Smartly](https://allocatesmartly.com/adding-a-1-day-lag-when-executing-taa-strategies)).
  **[CONSENSUS among identified pros for slow signals; does not transfer to news.]** Hoffstein: "for certain
  strategies… trading the next day is necessary to capture the trends."

**The arithmetic of the delay.** With the fast drift above ($D \approx 11$ bp, $\tau_f \approx 1.4$ days), a one-day
lag forgoes about $D(1-e^{-1/1.4}) \approx 5.5$ bp per unit of weight entered. At 26× NAV a year of entry gross, that
is

$$26 \times 5.5\,\text{bp} \;\approx\; 1.4\%/\text{yr} \quad \text{(upper end if all of } D \text{ were lost: } 26 \times 11\,\text{bp} \approx 2.9\%/\text{yr)}$$

The fund's own drift study bounds it from below. Day-1 drift from the news-day close was +5 bp, and the study shows no
loss from entering at the Thursday close (+4, +12 and +13 bp at days 1–3, t ≤ 1.5). Assuming a 200 bp daily residual
standard deviation per event, the study's standard error is about $200/\sqrt{8924} \approx 2$ bp, so it could detect a
6 bp day-1 effect. **The delay costs 0–1.4% a
year, most likely the lower half.** That is real money, but it is not the main loss: section 1.2's soft-news term is
2–4× larger.

**Verdict.** The delay is a candidate for the next protocol: event-driven daily entries at the first close after the
news, reusing the T−20 / T−3 machinery, as the 2026-10-14 desk review proposed. It cannot be judged from the timing
shadow books (section 3.10). The archive (section 4.1) answers it.

### 3.3 Horizons and the "already priced in" fraction

**What we do.** Since the 2026-10-28 cohort, each position's horizon shrinks with

$$p \;=\; \operatorname{clip}\!\Big(\frac{\text{side}\cdot \text{CAR}}{M_{\text{type}}},\, 0,\, 1.5\Big)$$

* CAR is the beta-adjusted return from the news session to the last close before the decision.
* $M_{\text{type}}$ is the median absolute two-day move of past events of that group and sector.
* The horizon is $H = \operatorname{clamp}\big(\operatorname{round}((B\,m - \text{age})(1-\tfrac12\min(p,1))),\,3,\,25\big)$.
* When $p \ge 1$, soft news is not entered and hard news gets $H = 3$.

This is the right idea, and it matches the literature exactly: measure how much of the typical move is already in the
price. But two implementation details blind it to the case the owner raised:

1. Prices are taken only up to the as-of Wednesday close (`fund/lifecycle.py:166`). The entry-day move never enters
   CAR.
2. The news session comes from the first article on the first-report date, often a midnight preview: 00:06 ET for
   MSFT, 00:16 ET for GOOGL. A 16:05 release is therefore treated as a Wednesday-session event, and its CAR window
   ends before the release.

**The resulting asymmetry is arbitrary.** In the 2026-10-28 cohort, all six are hard-news earnings lots without the
structural label:

| Release relative to the as-of close | Names | $p$ | $H$ |
|---|---|---|---|
| before it (Mon–Tue) | LH, CDNS, BRO | ≥ 1 | 3 |
| after it (Wednesday after the close) | MSFT, GOOGL, EQIX | 0, 0, 0.16 | 25, 24, 22 |

The information class is the same. The horizon differs eightfold only because of the weekday of the release. With
$M_{\text{hard}} \approx 3.4\text{–}5.3\%$, GOOGL's 12% entry-day move would have given $p = 1.5$ and $H = 3$.

The horizon table set against the evidence:

* Earnings and guidance get $B = 15$. The large-cap evidence says drift after the event day is about zero (Martineau)
  or small and positive (+0.13–0.22% over days 6–20, Kargarzadeh et al.). A long horizon is defensible only with the
  structural label of 2026-10-28 (rule R2: hold to the next report), and the desk already applies it selectively.
* Soft types get $B = 5$, then minus age, so $H \approx 3$. A short horizon is right *given* entry. The question is
  whether to enter at all (section 1.2).

**Verdict: dated amendment, mechanical.**

* Take the news session from the release time: 8-K item 2.02 acceptance for earnings (the repo already reads it in
  `edgar_202`), or the calendar's before-open/after-close flag (already used for next reports).
* Recompute CAR and $p$ at the entry decision, with the T−3 min price, inside the same live run that already
  re-prices everything.
* Everything else in the horizon formula stays.

This is a bug in the instrument that serves the owner's own observation, so it should come first.

### 3.4 News-driven exits, reductions and increases

**What we do.**

* Each day, a three-pass checker tests each position's kill conditions against new articles.
* Matched in at least 2 of 3 passes: exit. Partial: halve.
* New hard-number news in the position's direction: increase once, to 1.5× (no increase while the position is losing,
  from 2026-10-28).
* Orders go at the same close.

**The timing problem is the same as the owner's.** By T−1 min, more than 90% of a large cap's reaction to that day's
news is done. Only the drift after the close can be earned or avoided. The value of an action with weight change
$\Delta w$ is

$$\mathbb{E}[\text{action}] \;=\; \Delta w \cdot \mathbb{E}[\text{drift after the close}\mid\text{type}] \;-\; |\Delta w|\, c$$

| Action | Hard news (continues) | Soft news (reverses) |
|---|---|---|
| Exit on adverse news ($\Delta w = -w$) | $w(d_h - c) > 0$: right | $-w(r_s + c) < 0$: **sells the overshoot** |
| Increase on supportive news ($\Delta w = +w/2$) | $\tfrac{w}{2}(d_h - c)$: small and positive | $-\tfrac{w}{2}(r_s + c)$: buys the overshoot |

Here $d_h \approx$ 10–22 bp and $r_s \approx$ 17–34 bp. For an increase on a 5%-of-NAV position with $d_h = 20$ bp and
$c$ = 1.5 bp, the expected gain is about $0.025 \times 18.5\,\text{bp} \approx 0.05$ bp of NAV. **Increases are almost
worthless in expectation even when they are right.** Exits matter only through the type split.

**What we measured** (16 sessions; abnormal returns over the next five sessions, in the position's direction; overlapping
and clustered by day, so the t-values overstate):

* 15 increases: +160 bp mean (t 1.4).
* 3 exits: −618 bp (the exits avoided losses).
* 15 horizon exits: −357 bp (t −2.8; names kept moving against the thesis after we left).

These are noise-dominated and are not used as evidence. They do not contradict the table.

**Verdict.** The next protocol should condition news exits on the hardness of the *incoming* news: exit on hard
adverse news, hold through soft adverse news. Increases are low-value either way. The checker already classifies;
adding a hard/soft label to each matched article is one field. Run it as a shadow first.

### 3.5 Stop and target barriers

**What we do.** Exit at the close when the hedged residual return since entry reaches $-2W$ (stop) or $+3W$ (target),
with $W = \sigma_e\sqrt{H}$, checked on T−3 min prices.

**The arithmetic.** Under no drift, by the reflection principle, the chance that a Brownian path touches $-kW$ within
$H$ days is $2\Phi(-k)$. Checking only at daily closes shifts the barrier out by $0.5826\,\sigma_e$ (Broadie–Glasserman–Kou
continuity correction; my derivation, not from the notes):

| $H$ (sessions) | Stop $-2W$, continuous | Stop, daily checks | Target $+3W$, daily checks |
|---|---|---|---|
| 3 | 4.6% | 2.0% | 0.08% |
| 10 | 4.6% | 2.9% | 0.15% |
| 20 | 4.6% | 3.3% | 0.17% |

Our record: 1 stop and 0 targets in 59 entries. That fits the table. A drift of the size the literature allows (tens of
bp against $W$ of 5–15%) moves these probabilities by a fraction of a point. **The barriers are a tail-risk stop, not a
return engine.** They neither earn nor cost anything measurable.

**The T−3 min decision price.** A decision flips between the T−3 price and the close when the residual is within the
last-3-minute move of a barrier. To first order,

$$P(\text{flip}) \approx f_R(\text{barrier})\cdot \mathbb{E}|\Delta|$$

With $\mathbb{E}|\Delta| \approx 8$ bp (measured) and $R$ spread over roughly $\pm 2W$ with $W \approx 10\%$,
$f_R \approx 1/(4W)$, so $P \approx 8/4000 = 0.2\%$ per position-day. That is about 10 flips a year across 20
positions, each at a barrier where the P&L difference is about zero. The audit found none in 131 position-days and 91
actions; the closest was 0.23 W. Hoffstein's warning about "40 basis point afternoon luck" on threshold rules
([ReSolve](https://investresolve.com/podcasts/corey-hoffstein-strategy-construction-why-simple-is-fragile)) is
**[CONSENSUS]** in general, but it does not bite here, because the barriers sit 2–3 W away. **Verdict: keep. Spend no
effort here.**

### 3.6 Execution: market orders in the last minute

**What we do.**

* Decide at about T−172 s.
* Send plain market day orders at T−60 s (the close legs of position flips at T−75 s).
* Cancel and resend stalled orders every 10 s until T−10 s.
* Cancel any residual at T+5 s.
* Fills land at T−73 to T−42 s (median T−54 s).

**Measured.**

* 150 fills: signed mean **+0.57 bp** (standard error 0.78), median |slip| 5.3 bp, 90th percentile 13.9 bp, about
  $36 in total on $468k traded.
* Every order filled on the first attempt.
* The slippage is mostly the price move between fill and close (correlation −0.57).

**The alternatives, against every source.**

| Alternative | Academic | Industry | Forums | Verdict for us |
|---|---|---|---|---|
| **Closing auction (market-on-close)** | Cheapest venue for non-micro caps; the auction price is within 1.7 bp median of the 4 pm mid ([Bogousslavsky & Muravyev](https://www.aeaweb.org/conference/2021/preliminary/paper/H9T4hef7)); impact lower than continuous ([Goyal, Jegadeesh & Wu, JFQA 2026](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/price-impact-in-closing-auctions-opening-auctions-and-continuous-markets-a-benchmark-for-cost-of-trading-on-anomalies/0F72910A79C5B42CF6E85F55164CE846)) | 12–13% of volume in 2025; index funds' default; cutoffs: NYSE 15:50, Nasdaq 15:55 (late limit-on-close to 15:58), **Alpaca 15:50** | "Pretty much a guaranteed fill" (Elite Trader) **[CONSENSUS]**; "guarantees the price type, not the price" (Quant SE). Alpaca paper does not simulate it **[CONSENSUS, staff-confirmed]**; live access at Alpaca is **[CONTESTED]** (staff: "not generally supported unless… elite smart router") | Impossible after 15:50; untestable on paper. **Go-live option only** (below) |
| **Next open (market-on-open)** | Open auctions are expensive; effective spreads at 9:30–9:45 widened by about 10 bp for large caps (2010–18); attention-grabbing stocks open too high ([Berkman et al.](https://www.cxoadvisory.com/calendar-effects/the-lure-of-trading-at-the-open/)) | Opening auction is about 0.9% of daily volume | "hardly any volume on open, I get bad fills even on small smart orders" **[ANECDOTE]**; the pro-open view is a minority **[CONTESTED]** | **Reject.** Entering at the open also gives up the overnight return, where momentum and market premia accrue |
| **VWAP/TWAP over the day, or tranching** | Splitting helps only orders large relative to liquidity (Almgren–Chriss; Bertsimas–Lo). Ours are 0.001–0.01% of daily volume | VWAP costs about 10 bp against arrival (Proof) | Hoffstein: "TWAP over your execution window, and let the randomness average out" **[CONSENSUS, identified pro]** | **Reject for execution.** The book is marked at the official close; TWAP adds tracking noise to that mark and saves no impact. Hoffstein's point applies to *economic* timing luck (section 3.10) |
| **Passive, then aggressive limit orders** | — | — | Carver cut costs by about 80–90% in futures with it **[ANECDOTE, identified pro]**; "limit midpoint orders during fast moves almost never fill" | **Reject in paper.** Paper fills marketable orders at the quote, gives no price improvement, and won't fill a limit better than the quote. In live trading it could save about 1 bp per side at the risk of non-fills in a 60-second window |
| **Earlier send (T−5 min to T−2 min)** | Adds last-minutes drift to the tracking error (a few bp) | Widens the retry window against outages | Concretum's fallback fires at 3:59:58 | Would count as operational, by the 2026-10-03 precedent. **Not worth it**: the retry path has never run |

**What a T−60 s fill costs against a close-auction fill, live.** The extra cost is a half-spread: about 1–2.3 bp (the
average quoted spread is about 3.7 bp across the top 100 S&P 500 names and 4.5 bp across all 500, narrowest near the
close). The extra tracking variance is that of the last minute's move plus the auction jump. At about 40–68× NAV a
year of one-way turnover, the half-spread is worth at most $0.4\text{–}1.6\%$ a year. That is an upper bound: live
fills also get price improvement from wholesalers.

**The go-live design, from the forums.** Concretum's layered pattern **[CONSENSUS, firm-level]**: send close-auction
orders before the cutoff ("we use 3:49:55 ET") and keep "a fallback market order ready at 3:59:58 in case the MOC gets
rejected". For us that means:

* deciding by about 15:45, moving the news cutoff to about T−30 min. Section 3.1 shows that costs almost no
  information;
* checking barriers on 15:45 prices. Section 3.5 shows the flip risk is negligible;
* keeping the existing T−60 s market-order path as the fallback.

Confirm with Alpaca in writing that live close-auction orders route to the primary auction, since the forum record is
**[CONTESTED]**. **Verdict: keep the pre-close send for paper. Pre-register the close-auction design as part of the
go-live protocol, not before.**

**Forum warnings to apply.**

* "Choosing the signal minute is itself an overfitting risk" ([r/algotrading](https://www.reddit.com/r/algotrading/comments/ni1zuj/backtesting_a_close_near_low_strategy)).
  **Never tune T−20, T−3 or T−60 on outcomes.**
* Quarterly expiry, index-rebalance and Russell days move the close away from the last quote. That is when the 90th
  percentile of slippage will widen; the next one is Friday 18 December 2026. It is not an execution failure.

### 3.7 Sizing and whole-share rounding

The rounding error of a whole-share position is uniform on $\pm \tfrac{1}{2}$ share. Its weight error has standard
deviation $P/(\text{NAV}\sqrt{12})$: 0.072% of NAV for a $250 stock on $100k.

Its return cost is that error times the stock's daily volatility. Across 20 names, with about 2% daily volatility,
that is about $\sqrt{20}\times 0.072\% \times 2\% \approx 0.006\%$ a day, or about 0.1% a year of tracking difference.
The difference has mean zero.

The SPY hedge moves in steps of one share, about 0.68% of NAV. That gives a beta mismatch of at most 0.34% of NAV,
times SPY's daily volatility of about 1%: at most 0.3 bp a day, again with mean zero.

The audit's figures of "54 bp of NAV a day" (stocks) and "28 bp" (hedge) are weight mismatches, not returns. Sizing
uses the same T−3 min prices as the decision, which adds less than 0.1 bp of NAV per name. **Verdict: keep.** Fractional
shares would remove it for longs only, since shorts cannot be fractional, and buy nothing.

### 3.8 Costs and turnover

**Measured.**

* 16 sessions: mean one-way turnover **27% of NAV a day**, median 16%. That is about 40–68× NAV a year; the mean
  includes the 15 Oct transition and the cohort days.
* Volatility of the net book return: **10.5% a year** (16 sessions, so a rough figure).

**Cost in Sharpe-ratio units** (cost per year divided by volatility):

| Cost per side | Drag | Sharpe units |
|---|---|---|
| 5 bp (registered) | 2.0–3.4% | **0.19–0.32** |
| 1.5 bp (estimated live: half-spread plus 0.1 bp fees) | 0.6–1.0% | 0.06–0.10 |
| 0.9 bp (measured paper) | 0.4–0.6% | 0.03–0.06 |

Rob Carver's "speed limit" says never spend more than a third of the expected pre-cost Sharpe ratio on costs
(*Systematic Trading*, 2015; my source, not in the notes). The fund's own prior is a Sharpe ratio of 0–0.5 after costs.
At the registered 5 bp, costs alone use up most of that prior. **The registered cost model makes the book look like it
breaks the speed limit. Measured and estimated live costs say it does not.**

Two decisive implications:

1. **Keep the registered 5 bp; never change it mid-window.** But report a measured-cost line beside every score. Under
   the registered cost, the book's scored return is understated by about 1.5–3% a year against the S&P yardstick. The
   owner should know that when reading the scorecard.
2. **Turnover is the lever, not the price per trade.** Short-horizon soft-news positions generate most round trips
   per unit of expected return (section 1.2). Gârleanu & Pedersen's result, "aim in front of the target, trade
   partially toward it", already sits in the P8 plan as a 25% no-trade band with decaying alpha
   ([PREREG_thesis_tree.md](research/PREREG_thesis_tree.md) §P8). It is the literature-consistent answer.

### 3.9 The SPY sleeve (the owner's policy)

The sleeve is set at the as-of close (1.3× SPY above the 200-session average, 0.7× below) and traded a day later. The
policy is not tested or tuned (owner, 2026-10-14 and 2026-10-19).

On implementation only:

* Allocate Smartly measured a one-day lag on trend and asset-allocation rules at −0.02% a year (monthly rules,
  1990–2020) and −0.1% to +0.2% a year (aggregate signal, 2000–2026), i.e. noise
  ([Allocate Smartly](https://allocatesmartly.com/adding-a-1-day-lag-when-executing-taa-strategies);
  [2026 update](https://allocatesmartly.com/the-wisdom-of-100-strategies-using-aggregate-taa-allocation-as-a-trading-signal)).
* Hoffstein's threshold-luck example is a 200-day average rule that came within 40 bp of switching in an afternoon.

**Verdict: keep. Log the distance to the 200-session average at each as-of, so a near-switch is visible.**

### 3.10 Evaluation: the scorecard, the shadow books and timing luck

**The go-live scorecard.**

* It reads retired weekly files (`fund/score.py:334-342`), so it reports 0% of weeks fully executed under the current
  protocol. All orders actually filled. Pointing it at the lifecycle records is **operational**.
* Its slippage test, median |slip| ≤ 10 bp, measures dispersion, not cost. For normal errors,
  median $|x| = 0.674\sigma$, so the test fails only if $\sigma > 14.8$ bp, whatever the bias. The evaluation notes and
  Proof Trading's public TCA agree on the replacement **[CONSENSUS in industry]**:
  * signed, notional-weighted mean cost, with a confidence interval clustered by day;
  * implementation shortfall against the decision price (Wagner's split into delay + trading + opportunity cost);
  * opportunity cost of cancelled residuals charged on *intended* notional, so partial fills cannot flatter the
    statistic.

  Today: mean +0.57 bp, standard error 0.78. The one-sided 95% upper bound is $0.57 + 1.645 \times 0.78 = 1.85$ bp,
  below 5 bp. **The 5 bp assumption is conservative with high confidence, in paper.** Changing the registered gate
  statistic is a **dated amendment before the first 13-week look** (late January 2027).

**The timing shadow books cannot answer the timing question.** The weekly difference between the
Wednesday-close-entry book and the fund has standard deviation $\sigma_D \approx 0.83\%$ a week (3 weeks: +0.46%/wk,
i.e. +27% a year annualised, which is noise). That fits a bottom-up estimate:

$$\sigma_D \approx \sqrt{\textstyle\sum_i w_i^2}\;\sigma_{\text{entry-day}} \approx 0.18 \times 366\,\text{bp} \approx 66\,\text{bp/week}$$

The number of weeks needed to detect a delay cost $\delta$ at 80% power and 5% two-sided is
$n \approx (2.8\,\sigma_D/\delta)^2$:

| Book-level delay cost $\delta$ | Annualised | Weeks needed |
|---|---|---|
| 0.05%/wk (section 3.2's central estimate) | ≈ 2.6% | ≈ 2,200 (42 years) |
| 0.10%/wk | ≈ 5.3% | ≈ 540 (10 years) |
| 0.25%/wk | ≈ 14% | ≈ 86 (1.7 years) |

**Verdict.** Keep the books, since they are cheap, but treat them as a monitor of gross failures. The question is
answered on the 2012–2025 event archive (section 4.1), whose 8,924 events give a standard error of about 2 bp per
event.

**Timing luck, made explicit.** Hoffstein's measure is the dispersion between identical books that differ only in
schedule. Here $\sigma_D\sqrt{52} \approx 4.8\text{–}6\%$ a year separates "enter Wednesday close" from "enter Thursday
close". That is as large as the whole plausible alpha (0–0.5 Sharpe × 10.5% ≈ 0–5% a year). **A single year of this
record cannot tell skill from schedule.** This is a mathematical restatement of the owner's mid-April 2027 rule; it
supports the rule and argues for a longer window.

Tranching (Hoffstein, Newfound) would cut this luck by $1/\sqrt{N}$ by splitting each entry across N days. A signal
with a one-day half-life cannot afford that. The overlapping weekly cohorts already tranche *across* names, not
*within* a name.

**The 7B shadow control is biased in its favour.** The control's own positions are checked for news at the close in
the nightly job (`control_news`, `fund/lifecycle.py:899`), about five hours after the live check. It therefore sees
about 15× more of the day's late articles, and it checks barriers on official closes. Before anyone compares the
2026-10-28 rules with their control, give the control the live check's time. This is **operational**, because the
control trades nothing; fix it now.

### 3.11 The research programme

| Component | Timing assumption | Against the evidence | Verdict |
|---|---|---|---|
| **R5** forward earnings predictions | Information cut off at 22:00 UTC on the trading day before the report; hashed and timestamped before the 8-K | The only component aimed at the reaction term $J$, the large one. Its discipline (no after-close release used for the next day's decision) is exactly what the literature requires | **Protect it.** It is also where the 2026-10-29 cost runaway sits; cap its spend, not its timestamps |
| **Transformer and quant trials** | Target from close(d+1): a built-in one-day lag; 10 bp per unit of turnover (5 bp in the trials) | The Carver and Allocate Smartly camp: never ask live trading to do what the backtest could not. Costs conservative against the measured 0.9 bp | Keep |
| **P8 thesis tree** | Decaying alpha, held while it exceeds round-trip cost plus a margin; 25% no-trade band; announcement-risk budget | Gârleanu–Pedersen, consistent with the decay evidence. Set the fast half-life at about 1 day for large-cap firm news. Allow multi-week half-lives only for hard, complex or cross-firm evidence (Ke, Kelly & Xiu; Kargarzadeh et al.; cross-firm lead-lag is mostly not significant value-weighted after 2004) | Keep; seed the half-lives from section 1.1 |
| **Technicals backtest** | Entry at the first Thursday close after the news | The only adequately powered timing evidence in the repo (8,924 events). Its result, no slow drift after gaps, agrees with the large-cap literature | Re-use it for section 4.1 |

### 3.12 Operations around the close

Concretum's ten production lessons were set against our runner:

| Lesson | Ours |
|---|---|
| Exchange calendar, not a hard-coded 16:00 | ✔ broker calendar |
| Exchange timezone | ✔ `America/New_York` |
| Clock synced to the broker | ✔ offset-corrected |
| Reconcile against the broker on restart; trust the broker | ✔ idempotent client order ids; reconcile job |
| Alert, never fail silently | ✔ issue plus text |
| Stale-data checks | ✘ **missing for news** (section 3.1) and unlogged for the IEX decision prices |
| Paper vs live differences | Documented (2026-10-03 note) |
| Half-days | Untested until Friday 27 November (13:00 close; also a cohort entry day after Thanksgiving, with a 44-hour information delay) |

Alpaca-specific forum warnings:

* Paper randomly injects partial fills, 10% of the time **[staff-confirmed]**. Our retry path exists but has never run.
* There are 2026 reports of paper positions changing overnight with no transaction **[ANECDOTE ×3]**. The reconcile
  job's account-value match is the right guard.

**Verdict:**

* Add a staleness check (trade timestamp) on the IEX decision prices. IEX carries a few percent of volume, so its
  "latest trade" can be minutes old for quieter names. This is operational to log; a rule to act on it is an amendment.
* Dry-run the trade path on the 27 November half-day schedule beforehand.

---

## 4. What to do, in order

### 4.1 The decisive offline test (no protocol change, about a day of work)

Re-run the 2012–2025 event study ([technicals_backtest.md](research/technicals_backtest.md), 8,924 events) with:

1. **Release timing** from 8-K item 2.02 acceptance times (earnings) and article timestamps (other news).
2. **Event type** from the same label set the desk uses: hard (earnings, guidance, analyst, capital return) vs soft.
3. **Drift paths** from four entry points: the release session's close, the next close, the next Thursday close, and
   the next open. Report days 1, 5, 10 and 20, as beta-adjusted, cost-free means with day-clustered standard errors.

Pre-register the read before running it. For example: "soft-news positions are dropped from the next protocol if
their 5-day drift from the fund's entry point is ≤ 0 with t ≤ −2, or ≤ +2 bp". This answers items 3 and 4 of the
verdict table and the delay question of section 3.2 with about 100 times the power of the forward shadow books.

### 4.2 Ranked actions

| Rank | Action | Class | Value |
|---|---|---|---|
| 1 | Measure CAR and $p$ to the T−3 min price, with the true release session | dated amendment | Removes an arbitrary 3-vs-24-session horizon split on about a third of entries |
| 2 | Event archive split by type and entry time (4.1) | offline research | Decides the largest expected-value term (section 1.2) |
| 3 | Fix the control's news-time asymmetry | operational | Without it, the 2026-10-28 rules cannot be judged |
| 4 | Scorecard reads lifecycle records; add signed mean cost, implementation shortfall and a measured-cost line | operational + dated amendment | Stops a false "operations failed" verdict at the first look |
| 5 | Log first-seen time per article, decision-price trade timestamps and quotes, and the entry-day move | operational | Turns three estimates in this report into measurements |
| 6 | Articles selected by "not yet checked"; T−20 news check on entry day for new cohort names | dated amendment | Closes two silent information gaps |
| 7 | News exits conditioned on hard vs soft incoming news | shadow, then next protocol | Stops selling overshoots |
| 8 | Event-driven daily entries | next protocol, after 4.1 | Recovers 0–1.4%/yr of delay, if 4.1 finds it |
| 9 | Close-auction orders with a market-order fallback | go-live protocol | At most 0.4–1.6%/yr of half-spread, live only |

**What not to do:**

* Do not tune the T−20, T−3 or T−60 minute marks.
* Do not move execution to the open, to VWAP or TWAP, or to limit orders while on paper.
* Do not lower the registered cost assumption mid-window.
* Do not read the timing shadow books before years have passed.
* Do not touch the sleeve or hedge policy.

### 4.3 Merge timing

Operational items 3–5 fit this weekend's safe window. The half-day dry run must be merged before Tuesday 24 November,
15:30 UTC. The dated amendments (items 1 and 6) need the owner's decision, written before any further outcome of the
affected rules is examined. `main` is merged by the owner.

---

## 5. Limits of this analysis

* **Section 1.2's per-type drift is the load-bearing number, and its evidence is thin.** One 2023–26 workshop paper,
  mixed sizes, single-beta adjustment. Section 4.1 exists to replace it.
* **Our own figures are small samples.** 16 sessions, 63 entries, 150 fills, 3 timing weeks. They are used for
  measurement and arithmetic, never as evidence of edge.
* **The vendor lag is inferred from timestamps**, not measured (item 5 fixes that).
* **Live costs are estimated** from quoted spreads; paper has no impact, no price improvement and no auction.
* **Some numbers are my derivations, marked where used:** the barrier continuity correction, the flip-rate
  approximation, the rounding arithmetic, the delay model's $\tau_f$, Carver's speed limit and the Gârleanu–Pedersen
  framing. They do not come from the research notes.
