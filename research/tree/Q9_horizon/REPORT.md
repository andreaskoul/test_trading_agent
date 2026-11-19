# Q9_horizon: longer prediction horizons and the IC / turnover frontier (Layer 3, Amendment 10)

*Written by the branch agent; saved by the coordinating session because subagent report writes are refused.
**Development data only** (S&P 500, `harness.load()`, walk-forward 2013-2019, annual refits, seeds 0-2; 353 IC
weeks, 352 book weeks). Not out of sample. Numbers from `RESULTS.jsonl` and `RESULT.json`.*

**Verdict: the registered rule selects the reference** (`finalists/D_hgb_mh` {3,5,10,20} with rank hysteresis): net
Sharpe at 14 bp 0.16 ± 0.38. Only the reference and the {5,21,63} mix meet the IC condition (within 0.005 of 0.0236).
* Longer horizons raise ρ and cut decile turnover by 12-19 points a week.
* Hysteresis alone saves 28 points at no IC cost.
* On top of hysteresis, longer horizons save only 4-7 points more, and the IC they lose is not paid back: every
  longer-horizon hysteresis book trails the reference, paired, at both cost levels.
* Nothing is nominated.

## Results (development)

| Config | Book | IC y5 (NW t) | ρ | Turnover/wk | Net SR 14 bp ± Lo | %/yr 14 bp | Net SR sqrt ± Lo | %/yr sqrt | Gross %/yr |
|---|---|---|---:|---:|---|---:|---|---:|---:|
| ref | deciles | 0.0236 (2.41) | 0.799 | 0.447 | −0.46 ± 0.38 | −3.20 | 0.16 ± 0.38 | 1.12 | 3.31 |
| ref | hyst | 0.0236 (2.41) | 0.799 | 0.170 | **0.16 ± 0.38** | 0.98 | 0.45 ± 0.38 | 2.73 | 3.45 |
| h21 | deciles | 0.0177 (2.10) | 0.853 | 0.321 | −0.52 ± 0.38 | −2.92 | 0.03 ± 0.38 | 0.19 | 1.75 |
| h21 | hyst | 0.0177 (2.10) | 0.853 | 0.133 | −0.07 ± 0.38 | −0.36 | 0.20 ± 0.38 | 1.01 | 1.57 |
| h63 | deciles | 0.0146 (2.21) | 0.886 | 0.261 | −0.12 ± 0.38 | −0.58 | 0.39 ± 0.38 | 1.93 | 3.21 |
| h63 | hyst | 0.0146 (2.21) | 0.886 | 0.104 | 0.14 ± 0.38 | 0.60 | 0.40 ± 0.38 | 1.68 | 2.11 |
| mix | deciles | 0.0201 (2.30) | 0.877 | 0.332 | −0.35 ± 0.38 | −2.05 | 0.20 ± 0.38 | 1.17 | 2.78 |
| mix | hyst | 0.0201 (2.30) | 0.877 | 0.115 | 0.08 ± 0.38 | 0.41 | 0.31 ± 0.38 | 1.62 | 2.09 |

"sqrt" = Q6's square-root cost model at S&P costs (half-spread 2.3 bp, K 0.5, AUM $10M). The reference with
hysteresis reproduces Q6's T1_trees (sqrt Sharpe 0.4536).

## Frontier (paired against the same-construction reference, NW t)

| Book | IC lost (t) | Turnover saved vs ref deciles (vs same construction) | Paired net 14 bp %/yr (t) | Paired net sqrt %/yr (t) | Pareto |
|---|---|---|---|---|---|
| h21 deciles | 0.0058 (−1.97) | 0.127 (0.127) | +0.29 (0.21) | −0.92 (−0.67) | no |
| h63 deciles | 0.0089 (−1.51) | 0.187 (0.187) | +2.62 (1.23) | +0.81 (0.38) | no |
| mix deciles | 0.0034 (−1.33) | 0.115 (0.115) | +1.15 (0.97) | +0.06 (0.05) | no |
| ref hyst | 0 | 0.277 (0) | n/a | n/a | yes |
| h21 hyst | 0.0058 (−1.97) | 0.315 (0.038) | −1.34 (−1.47) | −1.72 (−1.89) | no |
| h63 hyst | 0.0089 (−1.51) | 0.343 (0.066) | −0.38 (−0.22) | −1.06 (−0.62) | yes |
| mix hyst | 0.0034 (−1.33) | 0.332 (0.055) | −0.56 (−0.70) | −1.11 (−1.39) | yes |

## Grinold-Kahn fit, turnover ≈ k·√(2(1−ρ))

* Deciles: pooled k 0.638, R² centred 0.75.
* Hysteresis: k 0.245, R² centred 0.83.
* The law orders the configurations correctly, but k falls as ρ rises: from the reference to h63, √(2(1−ρ)) falls
  25% while decile turnover falls 42%.
* Hysteresis divides k by about 2.6.

## By year, hysteresis books, net %/yr at 14 bp (2013-2019)

* ref: 1.78, 2.40, 8.71, −12.24, −0.08, 2.41, 4.03
* h21: 0.17, 2.91, 4.05, −11.65, −3.33, 3.75, 1.73
* h63: 2.28, 3.22, 0.48, −3.36, −1.70, 0.46, 3.03
* mix: 1.03, 3.83, 4.27, −9.43, −2.93, 3.40, 2.93

Most of h63's relative strength is a smaller loss in 2016 (IC .004 against −.017), which is one year.

## Method notes

* Targets are built as dev `y5` is: `resid(h)`, the beta-hedged sum over rows t+2..t+1+h, demeaned; `resid(5)`
  reproduces y5 to 1.3e-7.
* Training rows satisfy t ≤ te+5−h, so no target crosses into the scored year.
* Deviation, noted and left unchanged: D's internal tree-count selection keeps its 8-row gap, shorter than a
  63-session target. The overlap reaches only the window that chooses the tree count, never the scored year.
* Survivorship contract: does not apply (no new inputs).

Files: `run.py`, `RESULTS.jsonl`, `RESULT.json`, `STATE.json`, logs; `.cache/tree/preds/Q9_horizon/`.
