# Desk review, 2026-10-14: the process graph, its weak points, and where to improve

Written on the day of Protocol 7's first decision. The question: given the goal of **beating the S&P 500
consistently**, where does the desk lose expected value?

**Method.** The desk is treated as a tree of processes. Each node is examined, and then the coupling between
nodes, because in a funnel the weaknesses multiply.

**Sources.**
* the code (`fund/*.py`);
* `PROTOCOL_fund.md` (Protocol 6, Amendments 1–7, Protocol 7);
* the evidence review and `technicals_backtest.md`;
* the live record on `fund-data`: weeks 2026-09-30 and 2026-10-07, the C10 state, fills and NAV;
* the runner logs.

**What this review is not.** It is not a performance verdict. Two weeks of P&L are noise, and no book is judged
here, in line with the owner's rule that the first judgement comes around April 2027. Every number below is a
property of the *process* (what the desks produce), not of the outcome.

## 1. The objective, decomposed

"Beat the S&P consistently" means a positive active return a = r_account − r_SPY with a high information ratio
(IR). Consistency is a direct function of IR (normal approximation):

| IR (annual) | P(active > 0 in a quarter) | P(active > 0 in a year) |
|---:|---:|---:|
| 0.25 | 55% | 60% |
| 0.5 | 60% | 69% |
| 1.0 | 69% | 84% |
| 1.5 | 77% | 93% |

By the fundamental law (Grinold & Kahn), IR ≈ IC × √(effective breadth) × transfer coefficient (TC), less costs.
That gives the value tree:

```
O  Beat SPY consistently  (maximise IR of r_account − r_SPY)
├─ A  Account construction: how active return becomes account return
├─ B  Alpha generation: IR ≈ IC · √BR · TC
│   ├─ B1 Universe & coverage ............ screen.py, ideate.py (core 20 + nominations + rule slots)
│   ├─ B2 Information set & timing ...... archive.py, research.py (narrative pipeline), cutoff, weekly cadence
│   ├─ B3 Signal extraction (LLM) ....... analysts.py, redteam.py, lifecycle desk, kill checks
│   ├─ B4 Signal → forecast ............. (missing: no calibration, no residualisation)
│   └─ B5 Forecast → portfolio .......... pm_risk.py, lifecycle caps, barriers, horizons
├─ C  Implementation: costs and TC ...... broker.py pre-close send, hedge, reconcile
├─ D  Measurement & learning loop ....... score.py, gate, challengers C0–C10, canary
└─ E  Reliability substrate ............. local runner, HF archives, fund-data commits, determinism gates
```

## 2. The process graph

```
daily 21:20  Finnhub ──▶ news archive (HF) ──▶ context archive (shadow only)
Wed 22:15    screen(500) ─▶ ideation LLM (1 call; sees ret_1w + 2 headlines) ─▶ coverage 45 (20 fixed core)
             ─▶ research (narrative pipeline: dedup, embed, relevance, stories, events, LLM names)
             ─▶ analysts LLM ×45 (narratives + price facts + ideation hypothesis) ─▶ score ∈ {−2..2} × confidence
             ─▶ red team LLM ×~38 (same model; uphold or weaken) ─▶ PM/risk (w = s·c/20, caps, SPY β-hedge)
             ─▶ lifecycle desk LLM ×20 (event type, first report, kill conditions) ─▶ H = table − news age; stale dropped
             ─▶ shadow desks (C2–C9, macro, FX, IC memo) ─▶ score.py
daily T−20m  kill checks LLM ×3 passes per open lot; T−3m barriers on live prices ─▶ decision log ─▶ broker send
01:10        reconcile ─▶ C10 rebuild + determinism and replay gates ─▶ ledger, pages
feedback     performance ──(only through a new protocol; 13–52 week latency; ~8–18% power)──▶ design
```

The only edge from outcomes back to design is human, slow and low-powered. That shapes everything else (§4).

## 3. Findings by node

### A. Account construction: high severity for the stated goal
* The account is a beta-neutral overlay plus idle cash:
  * stock gross is 0.64 in the weekly book and 0.36–0.43 in C10;
  * the SPY hedge is −0.16 to −0.20.

  It has no market exposure, so in a +15% year for SPY it earns roughly cash plus alpha. **As traded, it cannot
  beat the S&P in account terms unless the alpha exceeds the equity premium.**
* The paper account's cash activity holds only FEE rows: no interest is credited. The model credits the 3-month
  bill on all cash, including short proceeds.
  * The excess-return statistic is barely affected (≈ rf × net short, about 0.4%/yr).
  * The account's absolute return trails the model's by about rf (~4%/yr).
* The gate's statistic, the overlay's return in excess of cash (Amendment 3), is already the right measure of
  alpha. What is off is the account construction and the framing: the `sp500_hold` line on the shadow monitor
  compares a market-neutral book with buy-and-hold.
* Direction: **portable alpha**, i.e. SPY (or ES) as the core with the overlay on top. Reg T has room
  (1 + 0.64 + 0.2 < 2). At a minimum, idle cash should sit in a T-bill ETF. Report the IR against SPY.

### B1. Universe and coverage: high severity
* 20 of the 45 coverage slots are always the dashboard's core 20: the most efficiently priced mega-caps.
* 19 of the 20 got a non-zero score in both live weeks. About half the book sits in names such as NVDA, GOOGL,
  META, AVGO, AMD, LLY, ORCL, BRK.B, WMT and NFLX.
* The evidence says this is the hardest universe for the signal:
  * large caps absorb news in about a day (Ke, Kelly & Xiu: 11 bp in one day, against 52 bp over three days for
    small caps);
  * LLM news alpha is concentrated in small caps and on the short side, and its Sharpe fell from 6.5 to 1.2 over
    2021–24 (Lopez-Lira & Tang).
* At $100k, capacity is no constraint on going broader.
* Ideation always nominates the maximum (12 long + 12 short). The nominations fill the remaining slots before the
  attention-shock rule slots: 5 and 4 of the 6 attention names made coverage.

### B2. Information set and timing: high severity
* The weekly batch reads news to Wednesday 22:00 UTC and enters at Thursday's close. C10's classifier dates the
  driving events at **1–5 trading days before entry** (the 10-07 cohort's median is 2–3).
* In the 10-07 cohort, **6 of 20 views were stale and not entered, and 11 of the 14 entered lots have H = 3–4
  trading days**. Protocol 7 therefore mostly trades 3-day holds entered 2–5 days after the news.
* That is the window where the desk's own drift study (8,924 S&P 500 news events, 2012–25) finds nothing:
  * from the news-day close, the gap direction earns nothing significant out to 20 sessions;
  * from the fund's Thursday entry, days 1–3 give +4 to +13 bp at t ≤ 1.5, against about 10 bp of round-trip
    cost;
  * from 30 sessions on, the gap direction reverses.
* The narrative pipeline was built for the 20-firm dashboard. Its relevance test (an anchor's "feed lift" against
  the other feeds) now compares against whichever 45 names are covered that week. Story fits therefore depend on
  the coverage mix, a non-stationary input, and they are refitted every week.
* The news archive is a single point of failure for the C10 desk's 30-day headlines, and so for news age and H:
  * the Hugging Face token was invalid from 10-08 to about 10-11;
  * HF returned server errors on 10-13 (issues #68, #74, #75, #82).

### B3. LLM signal extraction: high severity
Measured on both live weeks:

| property | 09-30 | 10-07 |
|---|---:|---:|
| corr(analyst score, last week's return) | +0.37 | +0.40 |
| corr(analyst score, last month's return) | +0.32 | +0.29 |
| analyst sign agrees / disagrees with the ideation hypothesis | 19 / 2 | 17 / 3 |
| non-zero scores of 45 | 38 | 38 |
| confidence range (most values) | 0.5–0.6 | 0.5–0.6 |
| red-team "factual" flaws of 38 reviews | 3 | 6 |

* **Price anchoring persists despite the prompt.** The book is structurally short the one-week reversal factor,
  a documented (if weakened) large-cap anomaly. The expected style carry is zero or negative.
* **Ideation sets the direction.** Ideation sees price facts and two headlines. The direction therefore enters
  from price and headlines, not from the narratives that are the fund's claimed edge.
* **Little abstention.** 84% of the scores are non-zero, despite "score 0 unless the news gives a reason".
* **Confidence carries little information**, but it multiplies every weight.
* **Correlated judges.** One model does ideation, analysis, the red team, classification and the kill checks.
  The red team shares the analyst's blind spots. The canary measures drift, not quality.
* **Task framing.** The analyst is asked to forecast next week's relative return, a calibrated forecasting task
  LLMs do poorly. The evidence review recommended narrow reading tasks (event, novelty, direction, materiality)
  aggregated over samples. C2 and C3 test parts of this. C3 lacks the statistical layer with last week's return
  that the review specified.
* **Model size.** The evidence favours larger models (GPT-4 drift Sharpe 2.97 against 1.66 for GPT-3.5). Every
  call goes to a "flash" model. C6, a stronger critic from a different model family, was never built.

### B4. Signal to forecast: missing node, high severity
Nothing turns LLM outputs into an expected residual return:
* no calibration of score to return by event type;
* no residualisation against last week's and last month's return, beta, industry or size;
* no shrinkage.

The integer score times self-reported confidence *is* the forecast. This is the largest loss of transfer
coefficient, and it is why the anchoring in B3 flows straight into positions.

### B5. Portfolio construction: medium–high severity
* **Sizing.** w = s·c/20 gives 2–3% names and a stock gross of 0.36–0.64, against a design of 2.0. Most of the risk
  budget is unused, and the weights are equal weight plus confidence noise. Grinold sizing (∝ forecast / σ²) runs
  only in shadow (C4).
* **Risk model.**
  * The controls are a GICS-sector net cap of 30% of NAV (it never binds at this gross), a dollar-net cap and an
    SPY beta hedge. There is no industry, theme or style control.
  * On 10-07, 8 of 10 longs were AI infrastructure (MRVL, NVDA, GOOGL, CEG, LITE, HPE, AVGO, AMD). The shorts
    included storage and memory (STX, WDC, SNDK).
  * One theme factor dominates P&L, so effective breadth is far below 20.
* **Lifecycle.** The horizon table and the barrier multiples (2.0 W / 3.0 W) are pre-registered priors, correctly
  untuned. With H mostly 3, the horizon exit dominates and the barriers rarely matter. The hard-news increase added
  to AMD at −0.45 W: consistent with the rule, but asymmetric.

### C. Implementation: low severity (a strength)
* The pre-close send works: median slippage against the close is 0–1 bp (rebalance legs, n = 25).
* Five bp a side is conservative for Alpaca.
* The live barrier prices are IEX last trades. That is fine for mega-caps and thinner for any broader universe.

### D. Measurement and learning loop: high severity (structural)
* **Gate power.** By 52 weeks the gate has 8% power at a true Sharpe of 0.5 and 18% at 1.0. The modal verdict is
  NO-GO whatever the truth.
* **Challenger promotion** needs t ≥ 5.72 / 4.05 / 3.31 / 2.86 (Bonferroni, m = 11). In practice no challenger
  can be promoted in year one, so the shadow books cost more than they can decide.
* **Protocol churn.** Protocol 6 traded for two weeks before Protocol 7. Each restart resets the clock and adds to
  α/k. The design changes faster than the evaluation can learn.
* **The best-powered statistic is a secondary.** The cross-sectional score slope / rank IC (45 names × weeks)
  should be the primary metric for learning about the design. P&L stays the metric for going live.
* **Post-cutoff replay is underused.** Replaying the desk's LLM tasks on events after the model's knowledge
  horizon is valid and far faster evidence. It is already planned in a narrow form (Protocol 7 plan, arm B), but
  not as a standing laboratory.

### E. Reliability substrate
* **Fixed (PR #84):** the C10 determinism gate was failing falsely.
  * The rebuild used `rf.asof(day)`. FRED publishes DTB3 a day late, so a recorded day's rate changed once the
    day's own rate appeared.
  * On 10-14, 10-09 and 10-12 moved by 3–13 ¢, failing the gate (issue #83).
  * The rate is now frozen per session.
* **Fixed (PR #84):**
  * the runner's commit loops ended silently after 3 rejected pushes; they now fail the step;
  * the archive did not retry Hugging Face server errors; it now does.
* **Latent:**
  * `commit_state.sh` commits a snapshot taken at restore time, so another job's newer files could be reverted if
    run times overlapped;
  * a single Mac is the scheduler (mitigated by the heartbeat and the 17:03 UTC backstop; check that the backstop
    covers the Protocol 7 `lifecycle` job).

## 4. Dynamics across nodes

1. **Anchoring cascade (B1 → B3 → B5).** Price facts reach ideation, and ideation fixes the direction. The
   analyst inherits it (+0.4 with last week's return), and with no B4 node, sizing passes it through. Net
   exposure: short reversal, long recent winners in a hot theme. The expected alpha is then that style's return,
   which own data and the literature put at zero or below.
2. **Efficiency × latency (B1 × B2).** The most efficiently priced names are entered 2–5 days after the news.
   Each factor pushes the expected IC toward zero, and they multiply.
3. **Shrink to small (B3 → B5).** Little abstention, flat confidence and /20 sizing give many small, correlated
   bets: low TC and low effective breadth. Even with a positive IC, the last two terms of IC·√BR·TC crush the IR.
4. **Correlated judges (B3).** With one model at every stage, the red team and kill checks add cost and variance
   more than independent information.
5. **Slow feedback, fast churn (D ↔ design).** Book-level tests cannot learn within the time a design is kept,
   so changes rest on priors. Acceptable once; corrosive when repeated.

**Arithmetic.**
* IR 0.5 needs IC ≈ 0.056 at an effective breadth of 500 and TC 0.4. That is high for large caps.
* It needs only IC ≈ 0.015 at a breadth of 3,000 and TC 0.6, which means a broader universe, daily event entries,
  and proper B4 and B5 nodes.

**The levers are breadth and transfer, not more personas.**

## 5. Improvements, ranked by expected value per unit of cost

**Class 0: operational, now.**
1. Freeze the risk-free rate per recorded session. *Done in PR #84.*
2. Fail commit loops loudly, and retry Hugging Face server errors. *Done in PR #84.*
3. Confirm that the 17:03 UTC backstop and the heartbeat cover the Protocol 7 `lifecycle` job.

**Class 1: measurement, with no change to the champion.**
4. **A replay laboratory**, the main research engine:
   * probe the model's knowledge horizon with masked-entity and date recall by month (Lopez-Lira, Tang & Zhu);
   * replay the LLM tasks on post-horizon weeks (Finnhub has a year of history) to estimate the rank IC of each
     variant, with tens of weeks × hundreds of names;
   * split the weeks into tuning and holdout halves, and read the holdout once (the discipline of
     `backtest_levels.py`).
5. **Residualised rank IC as a weekly headline monitor.** The score is taken orthogonal to last week's and last
   month's return, beta and industry. Add monitors of theme and industry exposure and of ex-ante tracking error.
6. **Framing.** Show the overlay's IR against SPY, and compare `sp500_hold` only with SPY plus the overlay.

**Class 2: Protocol 8 candidates.** These are decided on the replay laboratory's evidence, not now, and
bundled into one restart.

7. **B4.** The forecast becomes a calibrated, residualised function of narrow LLM readings:
   * event type, novelty, direction of surprise, and hard versus soft news;
   * 3–5 samples per reading;
   * no price facts in the prompt; price enters only in the statistical layer.
8. **B1 and B2.**
   * event-driven daily entries at the news-day close, reusing Protocol 7's T−20 / T−3 machinery;
   * a broader universe (the S&P 1500, or the S&P 500 without its 50 largest names plus the S&P 400);
   * no guaranteed core-20 slots.
9. **B5.**
   * weights ∝ forecast / σ²_resid;
   * neutral to beta, industry group, size, momentum and one-week reversal;
   * sized to an ex-ante tracking-error target (for example 6–8% a year), not confidence / 20.
10. **A.** Portable alpha: an SPY core plus the overlay, so that the account's return is SPY plus alpha.
11. **C6.** A stronger, different-family model for the final ~20 names' checks only.

**Not recommended:**
* more analyst personas or debate;
* tuning the horizon table or the barriers on weeks of data;
* judging the shadow books before April 2027;
* expanding the macro or FX desks, which are not on the path to beating SPY.

**An honest prior.** Even done well, a $100k news-driven book's realistic IR is about 0.3–0.7: it beats SPY in
55–69% of years. "Consistently", in the sense of 80% or more, needs an IR near 1. That is reachable, if at all,
only through breadth (B1, B2) and transfer (B4, B5).
