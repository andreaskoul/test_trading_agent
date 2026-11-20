# L6_regime (Layer 6 T2): latent regimes with state-dependent means — all three configurations fail the development gate (no read)

*Written by the branch agent; saved by the coordinating session because subagent report writes are refused.
**Development only**: as-run MASTER scores, decision weeks 2015-02-05 to 2019-12-19 (249 weeks) after a 104-week
burn-in. Book level, %/yr (weekly × 52, returns × 7/days). Numbers from `RESULT.json`. `READ_L6T2.lock` was not
created.*

| Configuration | Timed Sharpe | Untimed Sharpe | Matched-exposure Δ %/yr (NW t) | LW HAC Sharpe-diff z (p) | Years Δ > 0 | Gate |
|---|---|---|---|---|---|---|
| Gaussian HMM, K = 2 | 0.09 | −0.22 | +1.48 (1.26) | 1.35 (0.089) | 5 of 5 | fail (z < 2) |
| Gaussian HMM, K = 3 | 0.14 | −0.22 | +1.73 (1.39) | 1.30 (0.097) | 5 of 5 | fail |
| Markov-switching regression on 13-week IC | −0.60 | −0.22 | −5.09 (−1.51) | −0.96 (0.83) | 2 of 5 | fail |

**HMMs.**
* The difference is positive in every year: K = 2 gives +1.25, +0.84, +4.13, +0.09 and +1.07 %/yr.
* The exposure correlation with next-week return is small (0.07 and 0.08), and timing costs 0.16 and 0.21 %/yr.
* Timing is only partly active. The development book's mean is negative (−0.93 %/yr), so the expanding mean of
  E/Var was ≤ 0 in 124 (K = 2) and 111 (K = 3) of 249 weeks, and the registered fallback set exposure to 1.
* Exposure was 0 in about 30% of weeks; mean exposure 0.72 and 0.74.

**Markov-switching regression:** mean exposure 0.28, at 0 in 58% of weeks; it loses, with timing costs of 0.91 %/yr.

**Fits** (20 refits each, 20 starts all finite):
* median transition diagonal: [0.97, 0.93] for K = 2, [0.91, 0.94, 0.92] for K = 3, [0.96, 0.92] for the regression;
* the states' means of b are close together, so the regimes separate mainly on the other variables.

**Checks.**
* The book build matches the B0 ledger for 2020-2025 exactly (302 weeks), and L6_complexity's frozen development
  series to 2.7e-10.
* Leakage test at two cut-offs: future perturbation leaves every exposure bit-identical. The test can fail:
  perturbing the 10 sessions before the cut-off changes raw E/Var in 6 of 6 cases.
* A synthetic two-state HMM is recovered by the EM.

**Choices** (in STATE.json).
* Own EM implementation (hmmlearn and statsmodels are not installed; nothing was installed); the signal uses the
  Hamilton filter only.
* Strict timing: data up to the previous Friday, with the state forecast propagated two steps.
* Expanding standardisation; timing cost on the week's actual book gross.

**Trial count:** T2 contributes 3 configurations. With T1's 56, a Layer 6 DSR would use N = 162 + 56 + 3 = 221.

Files: `lib.py`, `run.py`, `STATE.json`, `RESULT.json`; `.cache/tree/l6r/`.
