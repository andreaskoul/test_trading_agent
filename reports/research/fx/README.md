# Cross-sectional FX: results

Protocols: [`PROTOCOL_fx.md`](../PROTOCOL_fx.md) (c19aa2c, amended afaf433 before any
return analysis) and [`PROTOCOL_fx_confirm.md`](../PROTOCOL_fx_confirm.md) (44cca11,
committed before the 1990–2003 data was downloaded).

```
python scripts/xs/fetch_fx.py
python scripts/xs/fx_ladder.py     # Protocol 3, 2004-2026
python scripts/xs/fx_confirm.py    # Protocol 3b, 1990-2003
```

## Protocol 3: 0 of 16 pass

17 currencies against USD, weekly, rank-weighted, dollar-neutral, Thursday
execution one day after the Wednesday signal, excess returns including interest
accrual. Holdout 2016-01 → 2026-03 (534 weeks), H = 1 week:

| signal | Sharpe | HAC t | α vs DOL t | FM t | cost/yr | DSR | dev Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|
| carry | **0.75** | **2.5** | **2.7** | **2.5** | 0.04% | 0.16 | 0.15 |
| mom12 | −0.23 | −0.8 | −0.8 | −0.4 | 0.6% | 0.00 | −0.17 |
| mom3 | −0.86 | −3.0 | −3.0 | −2.4 | 1.1% | 0.00 | −0.55 |
| mom1 | −0.90 | −3.3 | −3.3 | −2.1 | 1.8% | 0.00 | −0.73 |
| rev1w | −0.23 | −0.8 | −0.8 | 1.0 | 3.4% | 0.00 | −0.07 |
| value | 0.31 | 1.0 | 1.3 | 1.2 | 0.3% | 0.01 | 0.64 |
| combo | 0.64 | 2.1 | 2.3 | 2.3 | 0.4% | 0.09 | −0.18 |
| ridge | 0.28 | 1.0 | 1.1 | 2.0 | 1.5% | 0.01 | 0.30 |

(H = 4 rows and cost sensitivity: `fx_ladder_results.csv`. The coin flip is −0.76
at H = 1 and −0.37 at H = 4.)

* **Carry is the only positive signal that holds up on holdout**, and it failed
  only the deflation hurdle. The 16 trials had very spread-out Sharpe ratios (the
  momentum trials were strongly negative), so the deflated hurdle was a Sharpe
  of 1.07.
* **combo** is 77% carry (β to carry 0.77; α t 0.2 after controlling for carry).
  It adds nothing beyond carry.
* **Short-horizon momentum was strongly negative in both dev and holdout.**
  Read the other way round, that is reversal, and it looked like a second
  finding.

## Protocol 3b: the untouched 1990–2003 sample

12 currencies (Fed H.10 series, DKK standing in for Europe before the euro),
costs doubled, and pass requires t > 2.13 on both tests (Bonferroni, 3 one-sided):

| hypothesis | Sharpe | HAC t | FM t | result |
|---|---:|---:|---:|---|
| 1-month reversal, H = 1 | −1.07 | −4.1 | −3.1 | **not confirmed; the opposite** |
| 1-month reversal, H = 4 | −0.93 | −3.7 | −3.1 | **not confirmed; the opposite** |
| carry, H = 4 | 0.63 | 2.4 | 2.5 | **confirmed** |

* **Reversal is an era, not a signal.** In 1990–2003 the same currencies showed
  strong *momentum*. In 2004–2026 it turns into reversal. That matches the
  literature on FX trend profits disappearing after the 1990s. A signal whose
  sign depends on the decade can't be traded without knowing the decade in advance.
* **Carry confirms on data nobody had looked at.** Sharpe 0.63 in 1990–2003,
  about 0 in 2004–15 (the 2008 unwind), 0.75 in 2016–26. It is the one robust
  premium here. It is a risk premium with crash exposure, not an information
  edge: it pays for bearing the risk of the 2008-style drawdown.

## Audits

* **Source robustness** (exploratory): restricted to the 12 Fed H.10 series,
  2004–26 carry still has holdout t 2.2 and FM t 2.2. The 2004–26 reversal is
  weaker in the clean H.10 data (t −1.9) than in the five Yahoo-sourced currencies
  (holdout t −3.7). Part of the "reversal" may come from stale Yahoo prints.
* An independent re-implementation (`fx_confirm.py` run over 2004–15 on the H.10
  set) reproduces the sign of each pattern.
* Universe eligibility uses only prices known at trade time. An earlier draft
  selected on the *next* week's price existing, and that was fixed before the
  first run.

## What to take from it

Carry is real and the only survivor across three disjoint samples. It is not
new, though, and its return is compensation for crash risk. Whether to run it
is a portfolio decision (size it for a 2008-type unwind), not a research
finding.
