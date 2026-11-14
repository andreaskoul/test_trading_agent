# R2: the point-in-time broad universe (Layer 3, Amendment 10)

*Written by the branch agent; saved by the coordinating session because subagent report writes are refused.
**Descriptive**: every period is out of sample but already spent, so nothing here is a test. Returns in % per year,
copied from `RESULT.json`. Book level means the broad trees decile book (F0) on its own, not the whole fund.*

## Results (2017-01 .. 2026-11, the same 498 weeks in both universes)

| | Hindsight universe (H7_DECOMP) | Point-in-time universe | PIT − hindsight, paired by week |
|---|---|---|---|
| Weekly IC (NW t) | .0264 (4.93) | **.0196 (3.44)** | −.0068 (t −3.06) |
| F0 at 5 bp flat: %/yr; Sharpe ± Lo SE | 7.94; 0.79 ± 0.32 | **5.75; 0.56 ± 0.32** | −2.19 %/yr (t −1.37); weekly corr 0.88 |
| F0 at 14 bp flat | 3.75; 0.37 ± 0.32 | **1.26; 0.12 ± 0.32** | −2.49 %/yr (t −1.56) |
| F0 under the forward cost model (half-spread by tercile + square-root impact) | 0.21; 0.02 ± 0.32 | **0.29; 0.03 ± 0.32** | +0.08 (t 0.05) |
| Forward cost model: gross / spread / impact %/yr; one-way turnover per week | 10.27 / 3.07 / 6.98; 0.447 | 8.23 / 3.26 / 4.68; 0.479 | |

* **Common names** (about 1,072 a week): PIT model .0200 (t 3.47) against hindsight model .0227 (t 4.07);
  difference −.0027 (t −1.57); score rank correlation 0.92.
* **Re-admitted names** (PIT model, about 426 a week): .0193 (t 3.17). Current S&P 400 names .0209 (t 3.19); S&P 500
  panel tickers outside their membership spells .0168 (t 2.51).
* **Smaller names pushed out of the PIT top 1,500** (hindsight model, about 426 a week): .0361 (t 6.35). Most of the
  hindsight IC advantage comes from these smaller names.

IC by year, hindsight / PIT:

| | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|
| Hindsight | .021 | .010 | .021 | .011 | .015 | .036 | .022 | .046 | .043 | .042 |
| PIT | .013 | .014 | .009 | .011 | −.007 | .033 | .014 | .046 | .037 | .030 |

PIT F0 book by year, %/yr:

| | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|
| 14 bp | −2.8 | 1.5 | −10.1 | −3.5 | −18.5 | 10.5 | 1.0 | 10.2 | 15.9 | 10.8 |
| Forward cost model | −3.3 | 2.5 | −9.2 | −5.0 | −19.4 | 10.6 | −0.4 | 7.7 | 11.7 | 9.8 |

**Consequence, as registered:** the pooled out-of-sample figures quoted for the broad trees book are now the PIT ones:
IC .0196; Sharpe 0.56 at 5 bp, 0.12 at 14 bp, 0.03 under the forward cost model.

## Reproduction

* Run with the old hindsight exclusion, the code rebuilds `y2026/broad_panel.npz` exactly (every field
  `array_equal`).
* The hindsight comparator reproduces H7_DECOMP.json to 1.1e-16.
* The cost inputs equal `h9_forward.cost_inputs`.
* Refits: `finalists/D_hgb_mh`, seeds 0-2, train end 8 sessions before each year's first session, as in H7.

## Universe and content checks

* **Rule:** Amendment 1/4 eligibility, applied to Alpaca names that are not S&P 500 members at t (point-in-time
  membership, extended by CIK so renamed tickers are excluded too).
* **Size:** 3,644 broad columns.
* **Coverage:** 1,500 every Thursday, except one at 1,499. Share re-admitted 27.5% → 29.5%.
* **Bars:** no fetch was needed. 18 re-admitted names are not Alpaca assets on the allowed exchanges, so the rule
  excludes them.
* **Spot-check against yfinance:**
  * NYT: corr 0.99996.
  * KBH: corr 0.99998.
  * CCEP: one day differs at the merger that formed it.
* **Residual defect, disclosed:** some member renames are not grouped in ciks.json (FB→META, HRS→LHX and others), so
  956 of 749,999 name-weeks (0.13%) admit a firm while it was a member.

## Data completeness

Eligible names whose last bar falls in the year (PIT): 2017 0, 2018 20, 2019 72, 2020 62, 2021 73, 2022 55,
2023 1, 2024 0, 2025 4. Across Alpaca's whole universe, tickers whose last bar falls in each year 2016-2025:
0, 0, 92, 245, 300, 648, 317, 16, 12, 43. EDGAR Form 25 filers (typed Form Type field) number 650-1,000 a year, an
upper bound.

**Verdict:** the delisting gap in 2016-2017 and 2023-2024 is real. The broad universe is still survivor-biased in
those years (dead names missing). Probable cause (not verified): Alpaca's inactive list is incomplete, or delisted
names now carry a current OTC exchange and fail the NYSE/NASDAQ/AMEX filter, which is a current field, not point in
time. No bug was found in our code. The 59 `*_DELISTED` symbols cannot be dated from typed sources; general
knowledge points to 2018 acquisitions.

Files: `r2.py`, `RESULT.json`, `INPUTS.json`, `STATE.json`, logs; `.cache/tree/preds/R2_pit/`, `.cache/tree/r2/`.
