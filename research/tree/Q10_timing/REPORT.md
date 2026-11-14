# Q10_timing: liquidity-provision timing (Nagel 2012) of the boosted-trees decile book — no pass

*Written by the branch agent; saved by the coordinating session because subagent report writes are refused.
**Development data only (2013-2019, `harness.load()`); not out of sample.** Numbers from `RESULT.json`.*

**Window.** The book starts 2013-01-03 (353 weeks). The exposure rule starts after a 104-week burn-in, on 2015-02-05;
the test window is 2015-02-05 .. 2019-12-19 (249 weeks). Pass rule (fixed in STATE.json before scoring): Sharpe
difference > 0 with Lo z ≥ 1.96 against both controls. **Neither candidate passes; every point estimate is negative.**

| Candidate (lagged variable) | vs constant: ΔSharpe (Lo HAC SE; z) [iid z] | paired NW t | vs Moreira-Muir: ΔSharpe (SE; z) [iid z] | paired NW t |
|---|---|---|---|---|
| DISP (dispersion of 5-day returns) | −0.296 (0.214; −1.39) [−1.21] | −1.34 | −0.193 (0.123; −1.57) [−1.37] | −1.57 |
| SPYVOL (SPY 21-session vol) | −0.015 (0.207; −0.07) [−0.07] | −0.06 | −0.124 (0.267; −0.46) [−0.44] | −0.36 |

Holm across the two candidates (descriptive), using the larger p over the two controls: DISP 0.33, SPYVOL 0.94.

**Levels on the test window at matched average gross (development).**

| | Mean gross | %/yr | Vol %/yr | Net Sharpe | Worst fall |
|---|---|---|---|---|---|
| DISP candidate | 0.935 | −2.38 | 8.18 | −0.29 | 24.2% |
| DISP constant | 0.935 | +0.03 | 7.09 | 0.005 | 18.1% |
| DISP Moreira-Muir (scale 1.09) | 0.935 | −0.73 | 7.44 | −0.10 | 18.5% |
| SPYVOL candidate | 0.705 | −0.07 | 7.14 | −0.01 | 18.3% |
| SPYVOL constant | 0.705 | +0.03 | 5.34 | 0.005 | 13.9% |
| SPYVOL Moreira-Muir (scale 0.78) | 0.705 | +0.59 | 5.22 | 0.11 | 11.6% |

**Exposure behaviour.**
* Correlation of each candidate's exposure path with its Moreira-Muir control: DISP 0.80, SPYVOL −0.03.
* Share of weeks at the 0.5 floor / the 2 cap: DISP candidate 49% / 13%; DISP Moreira-Muir 10% / 0.4%; SPYVOL
  candidate 62% / 2%; SPYVOL Moreira-Muir 13% / 1%.
* Cost of the exposure changes, %/yr: DISP candidate 1.13, Moreira-Muir 0.65; SPYVOL 0.22 and 0.19.
* Exact-weights sensitivity through M1 `simulate` leaves the ranking unchanged. Net Sharpe, candidate / constant /
  Moreira-Muir: DISP −0.23 / 0.00 / −0.06; SPYVOL 0.00 / 0.00 / 0.13.

**Step 1 (full sample, 352 weeks, OLS with NW t).**
* DISP: return slope −0.051 (t −0.62); squared-return slope 0.0037 (t 2.48).
* SPYVOL: return slope −0.0051 (t −0.45); squared-return slope 0.00057 (t 2.19).
* The mean slope has the opposite sign to Nagel's and is insignificant; only the variance responds.
* Expanding-window slopes change sign over time: DISP +0.031 (end-2014), −0.153 (2016), −0.051 (2019).
* So μ̂/σ̂² cuts exposure when variance is high, on a mean estimate with the wrong sign that keeps changing: it adds
  cost and loses to both controls.
* Moreira-Muir on SPYVOL has the best point Sharpe (0.11) but was not a candidate, and Q4's earlier finding on
  volatility-managed books (|t| ≤ 0.4) suggests it is not robust.

**Implementation notes (fixed before scoring).**
* Predictions are the saved trees base, `M1_dyntrade/base_hgb_multihorizon.npy`, byte-identical to
  `D_ensembles/pred_hgb_multihorizon.npy`. Because it is stored as float32, about 10% of each week's ranks tie:
  IC 0.0235772 against the logged 0.0235684. This was declared in STATE.json with a 5e-5 tolerance.
* The base book's Sharpe on the test window alone is only 0.005, against 0.156 over 2013-2019. The base is weak in
  the very window the test uses.
* Variables are measured at the previous scored Thursday. The step-2 fits use only weeks whose return had ended
  before formation.
* Net return = e·b − 5 bp·|Δe|. The Sharpe difference's standard error uses the delta method with an NW covariance.
* One code fix after the first run: week 0, whose lagged value is NaN, was excluded from the fits. Nothing else
  changed.

Files: `run.py`, `RESULT.json`, `STATE.json`; `.cache/tree/preds/Q10_timing/weekly.npz`.
