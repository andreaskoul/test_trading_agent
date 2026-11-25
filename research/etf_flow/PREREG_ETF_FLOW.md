# Synchronous daily cross-asset information flow into US equity, ETF closes 2007–2026 — pre-registration (2026-11-26)

Committed before any statistic of any price series is computed. The owner authorised two free pre-registrations on
2026-11-25 ("Ok"): an executable ETF trend forward shadow (`research/etf_forward/PREREG_ETF_TREND_FORWARD.md`) and
this synchronous daily-ETF information-flow study. Research only: nothing under `fund/` changes; no instrument is
authorised for trading.

**Frozen inputs and their revisions** (CLAUDE.md rule 4; `repository`):
`research/xasset/LIT_FLOW.md` §2–§8 (commit 1453c3d), `research/xasset/PREREG_XASSET.md` Amendment 2 (commit
1284c08), `research/xasset/SCOPE.md` §2a and §8 (commit 8e9eca2), `research/etf_forward/etf_coverage.py` (the
coverage gate, committed with this registration), `reports/research/DESIGN_RULES.md` (signed 2026-11-02).

## 1. What this read is, and what it is not

**Estimated.** Whether any non-equity ETF carries information about the next US-equity move *beyond what the trend
core already knows*, at the daily and weekly horizons, over the ETF era. The family mirrors `LIT_FLOW.md` §7 but is
re-cast for tradable ETFs whose closes are **synchronous** (all NYSE-listed, 16:00 ET). It is a **precision
estimate** in the sense of `DESIGN_RULES.md` rule 6 and `PREREG_XASSET.md` §6: the verdict classifies the estimate,
it is not a pass/fail.

**Not estimated.**
* Not the 1962–2002 proxy read (`PREREG_XASSET.md`): that is a different sample and stays sealed behind its
  commodity-breadth gate. This study neither spends nor unlocks it.
* Not an executable sleeve: a predictability slope is not a traded position. Any economic-significance translation
  (implied timed Sharpe) is reported as an identity under frictionless timing (`LIT_FLOW.md` §8), labelled, and is
  never a return of a traded book.
* Not a test of the fund with these signals: adopting any of F1, F2, F4, F5 to time the core's exposure is the
  owner's strategic policy under CLAUDE.md rule 17 and a separate protocol decision. This read is the one
  pre-registered long-history test rule 17 permits for those four; it is never tuned on its own result.

**The distinctive design fact (why this study exists).** `LIT_FLOW.md` §5.4 and §7 record that a daily-frequency
cross-asset family was **blocked for the proxy read** by undeclared futures settlement times and unknown H.15 yield
stamps: with asynchronous closes, a one-day "lead" into equity is mechanical, not informational. ETFs remove that
obstruction — every instrument here is a US-listed ETF marked at the single 16:00 ET auction. A same-session
cross-asset→equity test is therefore admissible without the one-day skip that H5 of the proxy read was forced to
use. That is the one thing this study can do that the historical read cannot. Its costs are the opposite ones: a
short sample (≈ 19 years) and data that overlap spent modern samples (§2).

## 2. Data and its independence (frozen; `ETF_MANIFEST.json`, coverage in `ETF_COVERAGE.json`)

Source: `etf_coverage.py` (`yfinance`, `auto_adjust=False`, actions kept; no login, no key, generic client; no
personal details in any request). Prices are read **only** by the locked read script, after the coverage gate (§3)
has passed and been committed. Total returns use the adjusted close (dividends and splits reinvested); the
unadjusted close is kept only for the coverage checks.

**Instruments**, fixed before any download, by the exposure they carry (`SCOPE.md` §2a):

| Composite | ETFs | First common date |
|---|---|---|
| US equity (target) | SPY | 1993 |
| US Treasuries | SHY (1–3y), IEI (3–7y, from 2007-01-11), IEF (7–10y), TLT (20y+) | 2007-01 |
| Credit | LQD (investment grade), HYG (high yield, from 2007-04-11) | 2007-04 |
| Currencies (vs USD) | UUP (dollar, from 2007-03-01); FXE, FXY, FXB, FXF, FXA, FXC as a basket | 2007-03 |
| Commodities | DBC (basket), GLD (gold), USO (WTI), SLV, DBA, DBB, UNG (from 2007-04-18) | 2007-05 |

* **Target window:** the panel is read from 2007-07-01 (the first month in which **every** composite above exists —
  UNG, 2007-04-18, is last — plus a buffer), of which 2007-07-01..2008-06-30 is the held-out calibration slice, so
  the **evaluated** target runs 2008-07-01 to the last full calendar month at the read. Chosen before any statistic.
  Nothing earlier is touched.
* **States and calibration warm up before the first evaluated day:** the core's 200-session state from SPY's 1993
  history; the 252-session absorption ratio (F4) from the composites' own 2007 history, so F4's first read day is
  mid-2008 and its target window is 2008-07-01 onward, recorded separately. A **calibration slice,
  2007-07-01..2008-06-30, is held out of every evaluated target** and used only to warm the states and to fix F5's
  bandwidth (§5); the evaluated daily sample for F1–F3, F6 therefore begins 2008-07-01, and F5's evaluated weekly
  sample likewise. This keeps every outcome statistic out of the slice its tuning touched.
* **Dynamic universe within a composite:** an ETF enters its composite on its first session; the commodity and
  currency composites are equal-weight across the ETFs present that day. The composite set itself is fixed.

**Independence — stated plainly, because it bounds the claim** (`SCOPE.md` §2a independence column; `reasoning`):
* This sample (2007–2026) is **independent in time** of the 1962–2002 proxy read. It is the "fresh era" the
  recommendation named.
* It is **not independent** of the modern exposure-rule reads: IEF/TLT/GLD/DBC/UUP are S1's instruments, the
  currencies are S6's (2004–2026), and volatility/rate states were used in S9 (2008–2025). The *flow* hypotheses
  here — one asset's return leading next-session equity beyond the core's state — were **not** the objects of those
  reads, which were exposure-level or regime-state reads, not lead–lag predictability tests. So the evidence is new
  for these hypotheses but the data are shared.
* **F4 is the exception and is labelled partly-overlapping**: an absorption-ratio regime state is closest to S9's
  regime work. F4 conditions on the S9-style core state already in Z and is reported with its verdict discounted to
  "measurement" rather than independent evidence. Credit (F3) is the only composite not in any spent list
  (`SCOPE.md` §2a, "credit itself is unread"): F3 is the one fully independent hypothesis.

This independence ledger is the data-use entry; N (§5) is incremented accordingly, and the cross-reference is
written to `research/DATA_USE.md` by a dated line at registration.

## 3. Coverage gate before the read (`etf_coverage.py`; the read refuses to run unless it passes and is committed)

`etf_coverage.py` computes **coverage only** — presence, sessions expected vs present, missing/zero-volume days,
split and dividend events, served adjusted close, and median dollar volume over two fixed windows. It computes no
return, signal, volatility, correlation or any statistic of a price level. Its header states this and the read
binds to its frozen manifest sha256.

Gate conditions, all decided here:
1. **Synchronicity (the premise of the whole study).** Every instrument is a US-listed ETF of record type `ETF`
   trading on an NYSE/Arca/BATS session with a 16:00 ET close (`etf_coverage.py` records `instrumentType` and
   `exchangeName`). Any instrument whose record type or exchange is not a US equity-market ETF is dropped, and the
   drop is recorded. There is no foreign-exchange or futures instrument in this study, by construction, so no
   asynchronous stamp enters.
2. **Calendar coverage.** Against the NYSE calendar over each ETF's listed span, sessions missing ≤ 0.5% and no
   extra non-session rows; `Adj Close` served with no missing values; zero-volume sessions since 2020 = 0. An ETF
   failing is dropped from its composite and the drop recorded; a composite that loses its last member drops the
   hypotheses that need it (§5 evaluable set).
3. **Liquidity floor.** Median dollar volume ≥ $20 M/day in the fixed 2025-11..2026-10 window and ≥ $5 M/day in its
   first listed year, as a level (not a return). Below the floor, the ETF is dropped; the floors are registered here.
4. **Content contracts** (CLAUDE.md rules 1–3) on every series; coverage against the expected calendar, never
   against zero.

The evaluable set and the frozen F5 bandwidth (§5) are written to `CHECKS_ETF_FLOW.json` before the lock.

## 4. Common design (all hypotheses)

* **Target.** The SPY total-return excess over the 3-month T-bill (DTB3, frozen at first use), at the daily close
  and, for F5, the weekly Friday→Friday close. Because closes are synchronous, the daily target on session t+1 is
  regressed on predictors measured to the close of session t: a one-session lead, with **no skipped day**.
* **Control set Zₜ** (so each hypothesis asks for information *beyond the core*): {the equity excess return in
  period t; the core's state at the close of t, i.e. SPY above or below its 200-session average}. Mirrors
  `LIT_FLOW.md` §7.
* **Null distribution:** the **restricted-model residual bootstrap** of `LIT_FLOW.md` §7 — fit under H₀, resample
  the joint vector (restricted residual, the predictor's own innovations) in stationary blocks, rebuild the
  predictor, 10,000 draws, **seed 20261126**. Block mean length: 20 sessions (daily), 8 weeks (weekly) — chosen to
  match roughly one month of persistence, registered here.
* **Standard errors** on reported slopes: Newey–West, 10 lags (daily), 4 lags (weekly).
* **Reported beside each test, not decisive:** recursive out-of-sample R² from 2012-01 with Campbell–Thompson sign
  restrictions, by two-year block.
* **Multiplicity:** Holm across the evaluable hypotheses at family level 0.10; the programme-level p (0.10/N, N
  recounted from `DATA_USE.md`) also reported beside each. A separate family from the 1962–2002 read and from the
  trend-forward record.
* **Verdict per hypothesis** (`PREREG_XASSET.md` §6, same classes):
  * **supported:** Holm-adjusted p ≤ 0.10 **and** out-of-sample R² > 0;
  * **rejected:** the 90% upper bound of the implied R² is below 0.25% (the value at which a timed Sharpe moves by
    ≈ 0.03/yr, `LIT_FLOW.md` §8);
  * **inconclusive:** otherwise.
* **Posterior:** shrink the implied R² towards an out-of-window prior R² ≈ 0.5% (`LIT_FLOW.md` §4).

## 5. The family — six hypotheses, fixed here (daily unless stated)

Exactly six, to match the owner-ruled count and the programme's fixed-family discipline (`LIT_FLOW.md` §5.5).
Horizons and the one nonlinear/weekly test are registered choices, not outcomes.

| # | Hypothesis, exact statistic | Horizon, predictor | Linear/nonlinear; prior and overlap |
|---|---|---|---|
| **F1** | **Treasuries → equity.** OLS of SPY excess on [1, Zₜ, x₁ₜ]; x₁ₜ = TLT total-return over the trailing 20 sessions (level-trend, matched to the sleeve signal). t of x₁, one-sided (+), sign from Pitkäjärvi et al. (`search-summary`, via `LIT_FLOW.md`) | Daily; TLT 20-session return | Linear; flight-to-quality rebalancing. Overlaps S1 (rates); flow untested there |
| **F2** | **Energy → equity.** As F1 with x₂ₜ = USO trailing-5-session excess return. One-sided (−), sign from Driesprong et al. | Daily; USO 5-session return | Linear; oil→equity. Overlaps S1 (commodities); flow untested there. Labelled a modern-era replication of a 1973–2003 effect |
| **F3** | **Credit → equity.** As F1 with x₃ₜ = (HYG − IEF) trailing-5-session excess return, the high-yield credit spread move net of duration. One-sided (+) | Daily; credit-excess 5-session | Linear; credit leads risk appetite. **The only fully independent composite** (credit unread elsewhere, `SCOPE.md` §2a) |
| **F4** | **Absorption-ratio state → equity.** ARₜ = largest-eigenvalue share of the correlation matrix of daily returns of 5 composites (equity, Treasury, credit, currency, commodity+gold), 252-session window. Spikeₜ = 1 if (AR₁₅ − AR₂₅₂)/sd₂₅₂ ≥ 1. Coefficient of Spikeₜ in the F1-form regression, one-sided (−) | Daily state, read at each session; from 2008-07 | **Nonlinear** (threshold on a second moment); prior Kritzman et al. (`search-summary`). **Partly overlaps S9**: verdict discounted to measurement (§2). Gram matrix on 5 composites, not many names (`LIT_FLOW.md` §5.6) |
| **F5** | **Nonlinear information beyond linear (kernel).** Weekly (Fri→Fri; synchronous, so no skipped day). Fit the linear model SPY excess on [Zₜ, Xₜ], Xₜ = (TLT, credit-excess, currency-basket, commodity-basket weekly returns). Statistic: **HSIC** between the linear residual and Xₜ, Gaussian kernels, **median-heuristic bandwidth fixed on the held-out 2007-07..2008-06 calibration slice** (§2), never on the evaluated sample | Weekly; evaluated from 2008-07; T ≈ 950 | The only nonlinear omnibus test. **Wild bootstrap** for time series (Chwialkowski–Sejdinovic–Gretton), not an i.i.d. permutation (`LIT_FLOW.md` §2). Power unknown → simulated before the read (§6) |
| **F6** | **Tail flow (quantile Granger).** Quantile regression at τ = 0.10 of SPY excess on [1, Zₜ, x₁ₜ, x₂ₜ, x₃ₜ] (the daily predictor returns of F1–F3). Rank-score (Wald) test that the three cross-asset slopes are jointly 0 | Daily; τ = 0.10 | **Nonlinear in distribution**; the only "contagion into drawdowns" form. Prior: tail connectedness, Ando et al. (`search-summary`). Power simulated before the read |

**Why these six.** F1, F2, F4, F5 are the US-equity-core timing hypotheses of `LIT_FLOW.md` §7 (H1, H2, H4, H5),
re-cast daily. F3 (credit) replaces the proxy read's H3 (commodity currencies → commodities), because credit is the
one composite the ETF universe adds that is independent of every spent sample and leads equity risk appetite — the
best use of the new data. F6 is the tail form (H6). H3's commodity-currency question stays with the proxy read's
second-book family and is not re-run here.

**Diagnostics, outside the family** (not counted in N; `reasoning`): Diebold–Yilmaz total and directional spillover
and the Baruník–Křehlík frequency bands (1–5, 5–20, >20 sessions) on the daily composites by two-year block;
Forbes–Rigobon-adjusted equity–composite correlations in the core's worst 10% of sessions vs the rest; the reverse
direction of F1 and F3; transfer entropy (effective, 3-bin) reported beside F5 as a description, with its
finite-sample null bias (`LIT_FLOW.md` §8) printed so it is not read as a test.

**Deliberately left out** (`reasoning`): intraday leads (a different study, and the fund's intraday beta work
already covers contagion at that frequency, `riskfield`); single-name or sector Gram matrices (noise-dominated,
`LIT_FLOW.md` §5.6); neural-Granger / CCM / PCMCI (no size control at these T, `LIT_FLOW.md` §5.1); US→international
(wrong direction for a US fund).

## 6. Power, before the read (design arithmetic and simulation; no price data read)

* **Linear F1–F3, F4 (mean-difference):** computed by a committed script that reads **no** price series — only T,
  a hypothesised R² (or mean difference) and the formulae of `LIT_FLOW.md` §8 — and written to `ETF_FLOW_POWER.json`
  before the lock. Design expectation carried over from `LIT_FLOW.md` §6 (`reasoning`): at the daily horizon the
  larger T raises power materially over the monthly proxy read — at T ≈ 4,800 and R² ≈ 0.05% per session the
  one-sided detection probability (evaluated T ≈ 4,600 daily) is appreciable, though still short of rule 3's P ≥ 0.5
  at the programme level for the smallest forward-relevant effects. The actual table is produced by the no-data
  script, not asserted here.
* **F5 (HSIC) and F6 (quantile):** no closed-form power. Each is calibrated by **simulation on synthetic data only**
  — matched in T and autocorrelation to the gate's coverage, never the real returns — and the result committed
  before the read, exactly as `PREREG_XASSET.md` Amendment 2 requires for H5/H6.
* **Consequence (`DESIGN_RULES.md` rules 3 and 6):** because several hypotheses fall below P ≥ 0.5 at the smallest
  effects, the family is registered as a **precision estimate**, with the verdict classes of §4. Low power is not
  read as evidence of no flow (owner, `second-book-decision-framework`).

## 7. One read, and what it earns

* **One locked read.** `READ_ETF_FLOW.lock` is written first; the read runs once on the frozen, gated panel and the
  full result (every hypothesis, the diagnostics, the posterior) is committed whatever it shows. Records are
  append-only (CLAUDE.md rule 14); no back-fill, no re-scope after the drops of §3.
* **What a supported hypothesis earns.** A *proposal*, not a change: an exposure-timing overlay for the core (F1,
  F2, F4, F5) is written up for the owner's rule-17 decision; nothing is traded. F3 and F6, being book-level
  rather than core-timing, feed the second-book inventory under the appraisal-ratio framework
  (`second-book-decision-framework`), again as a proposal.
* **Relation to the trend-forward record.** This read measures *information flow*; the forward record
  (`PREREG_ETF_TREND_FORWARD.md`) measures the *tradable sleeve's* residual alpha. They are separate families and
  separate reads; neither is counted in the other's multiplicity.

## 8. Not claimed

* Not independent of the modern exposure-rule samples (§2); the independence is only across eras relative to
  1962–2002, and only F3 is fully fresh.
* Not peer-reviewed and not externally reviewed. An adversarial in-project reading by a separate session is
  requested before the read, per `research-integrity` §5.
* A supported slope is a conditional lead, not a tradable edge: no cost model is applied here, and the implied
  Sharpe is a frictionless identity.
* Sources behind the priors (Pitkäjärvi, Driesprong, Kritzman, Ando, Chen–Rogoff–Rossi) are `search-summary` via
  `LIT_FLOW.md` §9 except where that file marks a direct read; novelty is not claimed for any mechanism — these are
  known effects, measured on fresh, synchronous ETF data.

## Search and access log

```
Query: none run for this registration — it reuses research/xasset/LIT_FLOW.md §9 (commit 1453c3d), whose log lists
       the alphaXiv reads and the blocked seminal references.   Date: 2026-11-26
Opened: the committed input docs listed in the header (repository).
Blocked: none this session.
Stopped: no.
Conclusion: the design is fixed from already-committed literature; no new literature search was needed to register
            it, and none is claimed.
```
