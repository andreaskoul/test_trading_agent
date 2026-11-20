# L6_complexity (Layer 6 T1): complexity timing of the MASTER book (Kelly-Malamud-Zhou) — development gate FAILED, no read

*Written by the branch agent; saved by the coordinating session because subagent report writes are refused.
**Development only** (decisions 2015-2019, the S0 decile book: gross 0.6, beta-hedged, 5 bp). Numbers from
`RESULT.json`. `READ_L6T1.lock` was not created.*

**Gate** (amendment of 18:00 UTC: T1 against the better of B_m and B_mv; z ≥ 2 and ≥ 3 of 5 years positive):

| Comparison | T1 Sharpe | Other Sharpe | LW HAC Sharpe diff (SE) | z | Matched-exposure Δ | Years + |
|---|---|---|---|---|---|---|
| T1 vs B_m (trailing-mean timing) | −0.66 | −0.43 | −0.23 (0.46) | −0.50 | −0.53 %/yr | 1/5 |
| T1 vs B_mv (mean/variance timing) | −0.66 | −0.44 | −0.22 (0.44) | −0.50 | −0.18 %/yr | 2/5 |
| T1 vs constant (reported) | −0.66 | −0.24 | −0.42 (0.47) | −0.89 | −4.06 %/yr | 1/5 |

* Both benchmarks also lose to constant exposure (−3.5 and −3.9 %/yr).
* Annual (c, z) choices are all at low complexity: (0.5, 0.1), (1, 0.001), (1, 0.001), (0.1, 0.1), (1, 0.1).
* Mean exposure 0.44 (sd 0.68).

**Block-bootstrap null** (stationary, mean block 4 weeks, 1,000 draws, full pipeline rerun):
* T1 Sharpe: p = 0.68.
* T1 − constant: p = 0.60.
* T1 − better benchmark: p = 0.58.

**Virtue-of-complexity surface** (8 values of c × 7 of z, 10 seeds):
* Net timed Sharpe is negative in every cell (−1.51 to −0.22). The paper's timing return before costs is positive
  only near c = 1-2 at small z (+0.13 to +0.16).
* Out-of-sample R² is negative everywhere, with the interpolation spike at c = 1, z = 0.001.
* Ridgeless-limit check: the Spearman correlation of Sharpe with c is +0.36 and not monotone. "Sharpe rises with c"
  does not hold here.

**Checks.**
* The 2020-2025 book reproduces the B0 ledger exactly; the development book Sharpe is −0.161.
* FRED DTB3, DGS10, BAA and AAA, and VIX, are frozen with sha256.
* BAA and AAA are used from 7 days after month-end, with one-day lags elsewhere. MASTER's realised IC is used only
  after its target has completed.
* Leakage test across three cut dates: unchanged before each cut; planted look-aheads are caught.

**Choices.**
* Forecasts normalised by their expanding mean absolute value, then clipped to [0, 2].
* The amendment was applied before any score: an unpenalised intercept and centred features.
* The gate requires a pass against both benchmarks.
* The 2015 inner block is 46 weeks (the data start in 2013).
* N = 56 configurations.

Files: `lib.py`, `build.py`, `test_timing.py`, `dev.py`, `STATE.json`, `BUILD_CHECK.json`, `TEST_TIMING.json`,
`RESULT.json`; `.cache/tree/l6/`.
