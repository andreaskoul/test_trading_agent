# Executable ETF cross-asset trend sleeve — forward shadow record — pre-registration (2026-11-26)

Committed before the record begins. The owner authorised this on 2026-11-25 ("Ok") as one of two free
pre-registrations. It is the **executable forward arm** promised in `PREREG_XASSET.md` §6 and §7 ("what a pass
earns: a forward shadow record in executable form … matching ETFs SHY/IEI/IEF/TLT and FXY/FXB/FXF/FXC/FXA/FXE …
trading is a separate owner decision"). Research only, forward only: nothing under `fund/` changes; no instrument
is authorised for trading; the record is a paper shadow that accrues from its start date and is never back-filled.

**Frozen inputs and their revisions** (CLAUDE.md rule 4; `repository`):
`research/xasset/PREREG_XASSET.md` §2, §4, §6 (commit 1284c08), `research/xasset/SCOPE.md` §2a, §3, §7 (commit
8e9eca2), `research/xasset/VALIDATE.md` (commit aa92835), `research/etf_forward/etf_coverage.py` (coverage gate,
committed here), the allocation posterior rule on `origin/research/allocation-20261124` (`repo`, not on this
branch), `reports/research/DESIGN_RULES.md` rule 5 (signed 2026-11-02).

## 1. Why a forward record, and what it is for

The three-source framework of `PREREG_XASSET.md` §1 keeps evidence apart: an out-of-window literature **prior**;
the 1962–2002 proxy **read** (sealed behind its commodity gate); and an **executable forward record** that supplies
the posterior update, the implementation fidelity, and — uniquely — the dependence with MASTER. This document is
that third source.

Three things only a forward record in tradable ETFs can give (`PREREG_XASSET.md` §1, §7; `SCOPE.md` §8.3;
`reasoning`):
1. **Implementation fidelity.** The proxy read runs on yield/spot-built series and back-adjusted futures with
   literature costs; this record runs on the actual ETFs a book would hold, with their real tracking, roll drag,
   expense ratios and quoted spreads.
2. **Independence.** The executable ETF history before today is spent (S1) or overlaps spent markets (S6, S7);
   **only the forward record is independent** (`SCOPE.md` §8.3). It starts accruing now.
3. **Dependence with MASTER.** MASTER has no history before 2013 and the fund's book is live from 2026; the
   correlation of a non-equity trend sleeve with MASTER and with the core can be measured **only forward**
   (`PREREG_XASSET.md` §7). This record is the only instrument that can estimate the appraisal ratio against the
   *existing fund* rather than against the core alone.

It is registered now, independently of whether the 1962–2002 read ever runs: that read is blocked by its
commodity-breadth gate and the owner has declined to buy data, so the forward clock should not wait on it. If the
read later runs, this record becomes its posterior update; if it never runs, this record stands as a powered forward
test in its own right once enough time has passed.

## 2. The sleeve — identical to the proxy read's construction, in ETFs (no choice is tuned)

The signal, sizing and portfolio rule are taken verbatim from `PREREG_XASSET.md` §4 (Moskowitz–Ooi–Pedersen 2012),
so the forward record and the historical read measure the *same* strategy in different instruments. No parameter is
re-chosen here.

* **Universe** (tradable ETFs; `SCOPE.md` §2a, matched to the proxy legs):
  * **Rates/bonds:** SHY, IEI, IEF, TLT (the 1–3y / 3–7y / 7–10y / 20y+ Treasury ladder).
  * **Currencies (vs USD):** FXE, FXY, FXB, FXF, FXA, FXC; UUP is **excluded as redundant** with the basket (it is
    the dollar index, i.e. the negative of the basket) and its exclusion is registered.
  * **Commodities:** DBC (basket), GLD (gold), USO (WTI), SLV (silver), DBA (agriculture), DBB (base metals),
    UNG (natural gas). PDBC (no-K-1 basket) is held in reserve as a DBC substitute only if DBC fails the coverage
    gate, and that substitution rule is registered here.
  * The universe set is fixed; an ETF enters on its first session (all exist by 2007, so the record is full from
    day one).
* **Signal:** sign of each ETF's trailing 12-month total-return excess over DTB3 (MOP k = 12, h = 1), at each
  month end.
* **Position:** sign × 40% / σ̂, σ̂ the ex-ante annualised volatility from an EWMA of daily excess returns, centre
  of mass 60 days, lagged one day (MOP).
* **Portfolio:** equal weight within each class (bonds, currencies, commodities); equal weight across the three
  classes; the sleeve scaled to **10% ex-ante annualised volatility** from the 36-month rolling sd of the unscaled
  sleeve, past data only.
* **Rebalance:** monthly, at the month-end close, 1-month hold. Signals and vol use data to the prior close only
  (no look-ahead).

## 3. Costs and execution (recorded, not assumed)

Because the instruments are real ETFs, costs are **measured from the record, not taken from the literature**
(`DESIGN_RULES.md` rule 5; `SCOPE.md` §3):
* each simulated rebalance is filled at the **next session's** volume-weighted price proxy (close used as the
  recorded mark; the half-spread charged on |Δposition|);
* half-spread assumptions, registered as priors and then replaced by realised quotes as the record accrues: liquid
  Treasury and gold ETFs ≈ 1–3 bp a side; DBC, UNG, USO and the FX ETFs wider (`SCOPE.md` §3, `reasoning`);
* ETF expense ratios and any roll drag are inside the ETFs' own NAV and so are captured automatically in total
  return;
* a **2× cost sensitivity** is reported alongside, matching `PREREG_XASSET.md` §4.

No real order is placed. "Fills" are paper marks on public closes; the record is a shadow.

## 4. Coverage gate before the record starts (`etf_coverage.py`, committed; same gate as the flow study §3)

The record does not begin until `etf_coverage.py` has run `coverage`, passed and been committed: synchronicity and
record-type checks, NYSE-calendar coverage, served adjusted close, zero-volume floor, and a liquidity floor (median
dollar volume ≥ $20 M/day over the fixed 2025-11..2026-10 window). An ETF below a floor is dropped from its class
and the drop recorded before the first accrual; the class stays if it keeps ≥ 1 member, else that class is dropped
and the sleeve re-weights across the classes present (per §2). The gate computes **coverage only**, no return
statistic (its header states this), and the record binds to the frozen manifest sha256.

## 5. The forward record — what is written, and when

* **Start.** The first full month-end after this registration is committed and the coverage gate has passed —
  i.e. the **2026-12-31 close** is the first mark (2026-11-30 is too close to registration for a clean first month
  and is skipped, which is registered here). Positions are set from signals and volatilities computed to the
  2026-12-31 close from each ETF's prior 12-month / 60-day history. No history before the start date is ever
  recorded (CLAUDE.md rule 14; this is the F2/riskfield forward convention).
* **Cadence.** A weekly append (the fund runner's existing weekly job, extended by a registered step) writing, to
  `research/etf_forward/FORWARD_ETF.json`, append-only:
  * the sleeve's weekly excess return, net of recorded costs and at 2× costs;
  * per-class and per-ETF contributions;
  * the realised sleeve volatility vs its 10% target;
  * the SPY-excess core return that week and MASTER's book return that week (for the dependence estimate);
  * a content-contract pass on every input (CLAUDE.md rules 1–3); a missing official close is a typed defect and a
    gap, never a guess (the fund's halt/valuation-hold discipline applies to the data read, not to any order,
    because there is no order).
* **Freezing.** Each recorded week is frozen at first write and never recomputed, even if Yahoo later revises an
  adjusted close (CLAUDE.md rule 4). The weekly job reinstallation is logged like the other forward jobs.

## 6. Pre-registered read of the record (no interim verdict)

* **No verdict before the horizon.** By `shadow-books-judgement`, no forward book is judged before ≈ 3× its longest
  signal horizon. The longest here is the 12-month momentum lookback, so **no verdict before ≈ 2030**, and the
  first scheduled read is at **156 weeks** (≈ 3 years) with a power table committed in advance. Interim appends are
  descriptive only and carry that label.
* **At the read, the quantities** (`PREREG_XASSET.md` §6; `second-book-decision-framework`):
  * the appraisal ratio of the sleeve **against the existing fund** (core + MASTER book), measured on the forward
    months — the quantity a promotion actually needs, which the proxy read explicitly cannot estimate;
  * the AR against the core alone, for comparison with the proxy read;
  * residual alpha after recorded costs, and at 2× costs;
  * the sleeve's correlation with the core and with MASTER in the core's worst 10% of forward weeks;
  * the constrained marginal contribution to fund Sharpe, weights ≥ 0, the core at policy weight, under both
    exposure rules of `PREREG_XASSET.md` §6 (the 1.9× notional cap and the volatility-equivalent rule).
* **Verdict classes** (owner's framework, not pass/fail): **supported** (90% one-sided lower bound of the
  fund-appraisal ratio > 0 **and** residual alpha > 0 **and** constrained contribution > 0); **rejected** (90%
  upper bound of the AR < 0.15); **inconclusive** otherwise. Low power is not read as no edge; if at the 156-week
  read power is still short, the record continues and the read is deferred, not spent (`DESIGN_RULES.md` rule 6).
* **Sizing, if ever proposed.** Only the allocation pre-registration's posterior rule
  (`origin/research/allocation-20261124`) sizes any sleeve, with non-negative weights and the forward-decay
  haircut. A supported verdict is a **proposal to the owner**; trading is a separate decision under CLAUDE.md
  rule 17.

## 7. Power and the honest limit

* A committed no-data script (`etf_forward_power.py`, reads no price series) writes the detection probability of a
  positive fund-appraisal ratio as a function of elapsed weeks and true AR, from the Lo (2002) SE, to
  `ETF_FORWARD_POWER.json` before the first read. Design expectation (`SCOPE.md` §8.3, `reasoning`): under ~35%
  power after 5 years for a moderate AR, so the record is explicitly a **long-horizon precision estimate**, not a
  quick test.
* The binding limit, stated here (`DESIGN_RULES.md` rule 5): the thing measured forward (ETF sleeve vs the live
  fund) *is* the thing a promotion would trade — this record does not stand a proxy in for it — but its power grows
  only with calendar time, and no amount of design accelerates it.

## 8. Not claimed

* Not a backtest: no pre-start return exists or will be computed. Any reader wanting history is pointed to the
  sealed proxy read and the out-of-window literature prior, kept separate per `PREREG_XASSET.md` §1.
* Not tradable as authorised: it is a paper shadow on public closes; the owner's rule-17 decision is separate.
* Not independent of the modern exposure samples for its *pre-start* instruments; independence holds only for the
  forward months, which is the whole point of recording forward.
* Not peer-reviewed; an in-project adversarial reading of the construction and the record script is requested
  before the first scheduled read (`research-integrity` §5).

## Search and access log

```
Query: none — this registration fixes an executable analogue of an already-registered construction
       (PREREG_XASSET.md §4, commit 1284c08) and reuses SCOPE.md §2a inception dates (commit 8e9eca2).  Date: 2026-11-26
Opened: the committed input docs in the header (repository).
Blocked: none this session.
Stopped: no.
Conclusion: no new literature search was needed; the signal and sizing come from the already-read MOP 2012 via the
            proxy read, and the instruments from the already-committed ETF inventory.
```
