# Design rules for locked reads (signed 2026-11-02)

Every pre-registration written after these rules are signed follows them. Reads already made, and Family E, stay as
registered.

**Why.** The programme has made 37 locked hypothesis reads on 2022–2025 data (`DATA_USE.md`), and none has admitted
a component. Family E's soft-news read (rule A) reached the right decision by the wrong route
(`p8/E_SOFT_DIAG.md` §4):
* its agreement bar sat below break-even;
* a condition was decided by 12 trades;
* its cost hurdle was below the cost the fund is scored at;
* 90% of its sample was events the desk does not trade.

Earlier reads also had low power. E1 had about a 40% chance of passing even if the fit estimate were true, and E2
could only detect about 150 bp (`reports/Actionable ideas for the event fund.md`). The rules below make each read
answer the question the fund actually faces, at a power that makes it worth spending.

Notation:
* μ is the effect per event in the read's units;
* σ is the per-event standard deviation;
* D is the design effect: the variance inflation from events in the same week. It is measured on the fit window
  (it was about 1.0 for E3), not assumed.
* n is the expected number of read events.

## 1. Cost hurdles: both, stated in the read's units

* h_L, the live round trip: twice the one-sided 95% upper bound of the measured cost per side. The gate prints it;
  on 2026-10-31 it was 1.93 bp, so h_L ≈ 4 bp.
* h_R, the registered round trip: 2 × 5 bp = 10 bp, the cost the fund is scored at.
* **Test** H0: μ ≤ h_L. **The economic condition** also requires the point estimate μ̂ ≥ h_R.
* Where the read's sign or side differs from the live trade, the hurdle is restated for the live trade (rule 4).

## 2. Admission level for the programme

* Admit only if the one-sided p is at most α = 0.10 / N, where N counts every locked read to date, this one included.
  This holds the programme's family-wise error at 10%.
* With N = 38, the bar is **p ≤ 0.0026 (z ≥ 2.79)**.
* p is the registered max over inference methods, as in Family E.
* Holm still applies within a read's own family.

## 3. Power before the read: no read is spent that cannot pass

* Plausible effect: δ = ½ × the fit-window estimate (the usual haircut for decay and selection), or the literature
  value when there is no fit.
* Expected standard error: SE = σ·√(D/n).
* Power: P = Φ((δ − h_L)/SE − z_α).
* **The read is spent only if P ≥ 0.5.** The power table (δ, σ, D, n, SE, minimum detectable effect, P) is committed
  with the pre-registration.
* If P < 0.5, the question becomes a precision estimate (rule 6) or measurement only. It does not get a pass/fail
  read.

## 4. Applicability bars come from break-even

* If the live trade agrees with the tested direction with probability a, the live edge is (2a − 1)·μ. It covers cost
  only when **a ≥ a\* = (1 + h_L/μ̂)/2**. If μ̂ ≤ h_L, no a is enough.
* An applicability condition passes only if:
  * at least **n ≥ 40** live cases exist (standard error of a share ≤ 0.08); and
  * with a uniform prior, the posterior P(a ≥ a\*) ≥ 0.5.
* With fewer cases the condition cannot pass: the burden is on the trade. It is reported with its Wilson interval.
* The count comes from the decision ledger (`fund/attribution.py`, agreement table).

## 5. What is estimated must be what is traded

* When several sources are pooled, each is weighted by its share of the live decisions it governs. When the traded
  source cannot reach the power of rule 3 alone, that limit is stated, and the read does not stand in a proxy for it.
* **Co-primary all-data estimate.** If nothing is selected on the fit window (no horizon, sign, threshold or
  parameter), fit and holdout are exchangeable. The pooled estimate is then registered alongside the holdout test,
  and admission requires the pooled point estimate ≥ h_R as well.
* **Placebo baseline.** The same statistic on matched non-events (the same names in the same month on sessions
  without events) is registered beforehand. The decision uses the event-minus-placebo difference wherever a drift
  baseline is plausible, such as momentum, sector moves or reversal.

## 6. Precision estimates instead of pass/fail when power is out of reach

When rule 3 fails, the pre-registration names:
* the interval's target half-width;
* the data (all of it, fit and holdout, if nothing is selected);
* the decision rule on the 95% interval:
  * **upper bound < h_L:** stop or limit the activity;
  * **lower bound > h_R:** propose a powered read on new data;
  * **otherwise:** measurement only, with no change in capital.

The estimate counts in N (rule 2) only if it can admit something.

## 7. Records

* The power table, both hurdles, the placebo construction, the weights and the co-primary estimate are committed
  before any outcome of the read is examined, as for every pre-registration.
* `DATA_USE.md` records N after each read.

**Owner sign-off:** 2026-11-02 (merged #134 after the request to sign or change it).
