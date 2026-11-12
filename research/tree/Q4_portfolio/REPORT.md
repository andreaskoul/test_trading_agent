# Branch Q4_portfolio (Layer 3, Amendment 3): portfolio construction on fixed signals

*Written by the branch agent; saved by the coordinating session because the agent's writes were refused. Development
data 2013-2019 only, 352 scored weeks, 30 rows (4 controls, 4 decile references, 22 candidates).*

**Verdict.** No construction beats M1's no-trade band on the same signal by more than noise (best vol-matched paired
t 0.72). Keep the band. No candidate nominated.

## Inputs and checks

* Signals: MASTER `D["master_h5_ref"]`; D trees (`finalists/D_hgb_mh`, seeds 0-2; IC .02357 as logged; equals
  `M1_dyntrade/base_hgb_multihorizon.npy` to 3e-8); IPCA (`M2_ipca/model.py`, one seed since the seed is unused;
  correlation 1.0000 with the logged predictions); X4 blend (equal thirds of ranks; IC .0247, band book +1.95 %/yr vs
  X4's .0247 and +1.94).
* Book: M1 `simulate`; weights at Thursday t from data up to t, entered at the next close, earn w·y5 net of 5 bp ×
  sum|dw|. Control: M1 band at 0.1; reproduces M1/X4 (MASTER −0.28 %/yr, Sharpe −0.05).
* Fixed a priori: 252-session covariance window; vol-managed scale = median past book variance / current variance
  (weights × last 21 sessions of `e`), capped at 2, not lagged a week; drawdown rule: exposure 0.5 when known drawdown
  exceeds 1× past annual vol, back to full below 0.5×.
* Tuned on 2013-2016 only (net Sharpe; grids in `TUNING.jsonl`): partial-adjustment tau {.25,.5,.75}; no-trade width
  k {.5,1,2}, then {2,3,4,6} after k hit the grid edge. 2017-2019 reported separately.
* Ledoit-Wolf 2020 analytical nonlinear shrinkage, transcribed from their code, on residual returns standardised by own
  vol (missing → 0), rescaled to a covariance. Synthetic test (p 200, n 600): min-variance true variance 1.29× oracle
  (nonlinear) vs 1.38× (linear LW); tie when names outnumber sessions.
* Caveats: development-panel survivorship (241 of 738 names unpriced; 23.5% of eligible name-weeks without a target)
  may bias the short leg; delisting losses are not in the record, so drawdowns understate them. Both affect candidates
  and controls alike.

## Results

"Diff": weekly net, candidate minus control, %/yr, Newey-West t (4 lags). "Vol-matched": candidate scaled to the
control's full-period vol (whole-sample scaling; a proxy for a Sharpe-difference test). "(ref)": phase-1 decile book.

| config | net %/yr | gross %/yr (Sharpe) | net Sharpe | 13–16 | 17–19 | vol | maxDD | DD at ctl vol | turn/wk | diff (t) | vol-matched diff (t) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C_band_master | −0.28 | 1.70 (.28) | −0.05 | −0.18 | 0.15 | 6.1 | 17.7% | 17.7% | 38% | – | – |
| C_band_trees | +2.20 | 3.58 (.56) | 0.35 | 0.22 | 0.56 | 6.4 | 16.2% | 16.2% | 26% | – | – |
| C_band_ipca | +2.24 | 3.98 (.64) | 0.36 | 0.31 | 0.42 | 6.2 | 11.8% | 11.8% | 34% | – | – |
| C_band_blend | +1.95 | 3.58 (.56) | 0.30 | 0.18 | 0.49 | 6.4 | 14.6% | 14.6% | 31% | – | – |
| R_decile_master (ref) | −1.78 | 0.97 (.15) | −0.27 | −0.26 | −0.28 | 6.6 | 23.4% | 21.8% | 53% | −1.50 (−2.65) | −1.37 (−2.53) |
| R_decile_trees (ref) | +0.98 | 3.31 (.48) | 0.14 | 0.11 | 0.20 | 6.9 | 19.3% | 17.9% | 45% | −1.22 (−2.52) | −1.30 (−2.88) |
| R_decile_ipca (ref) | +1.46 | 4.08 (.61) | 0.22 | 0.05 | 0.42 | 6.7 | 13.2% | 12.4% | 50% | −0.78 (−1.50) | −0.87 (−1.79) |
| R_decile_blend (ref) | +1.20 | 3.70 (.55) | 0.18 | 0.09 | 0.32 | 6.7 | 16.4% | 15.8% | 48% | −0.75 (−1.53) | −0.80 (−1.66) |
| rank_trees | +0.93 | 2.30 (.52) | 0.21 | 0.14 | 0.32 | 4.4 | 10.5% | 14.8% | 26% | −1.27 (−1.32) | −0.87 (−1.30) |
| rank_blend | +0.84 | 2.39 (.52) | 0.18 | 0.11 | 0.30 | 4.6 | 11.5% | 15.8% | 30% | −1.11 (−1.24) | −0.78 (−1.23) |
| rank_pa_trees (τ .75) | +1.28 | 2.31 (.51) | 0.28 | 0.19 | 0.43 | 4.5 | 10.3% | 14.4% | 20% | −0.92 (−1.03) | −0.39 (−0.66) |
| rank_pa_blend (τ .5) | +1.40 | 2.22 (.46) | 0.29 | 0.17 | 0.48 | 4.8 | 11.6% | 15.2% | 16% | −0.55 (−0.70) | −0.09 (−0.15) |
| band_legvol_trees | +2.23 | 3.64 (.58) | 0.36 | 0.25 | 0.52 | 6.3 | 14.9% | 15.2% | 27% | +0.02 (0.12) | +0.07 (0.33) |
| band_legvol_blend | +1.96 | 3.65 (.58) | 0.31 | 0.22 | 0.44 | 6.3 | 13.0% | 13.3% | 33% | +0.00 (0.02) | +0.04 (0.21) |
| band_vm_trees | +2.00 | 3.74 (.79) | 0.42 | 0.30 | 0.56 | 4.8 | 8.1% | 10.8% | 34% | −0.20 (−0.14) | +0.48 (0.30) |
| band_vm_blend | +0.26 | 2.14 (.53) | 0.06 | −0.31 | 0.52 | 4.0 | 10.1% | 15.9% | 36% | −1.69 (−0.98) | −1.54 (−0.76) |
| band_vm_ipca | +1.84 | 3.75 (.91) | 0.45 | 0.22 | 0.74 | 4.1 | 8.7% | 12.9% | 37% | −0.40 (−0.29) | +0.57 (0.37) |
| band_vm_master | −1.86 | 0.30 (.07) | −0.44 | −0.53 | −0.32 | 4.3 | 20.0% | 27.4% | 42% | −1.58 (−1.13) | −2.37 (−1.48) |
| band_dd_trees | +1.78 | 2.73 (.54) | 0.35 | 0.43 | 0.23 | 5.0 | 10.9% | 13.7% | 18% | −0.43 (−0.49) | +0.05 (0.07) |
| band_dd_blend | +0.98 | 2.14 (.43) | 0.20 | 0.24 | 0.13 | 5.0 | 11.3% | 14.4% | 22% | −0.97 (−1.19) | −0.69 (−0.93) |
| mvnl_trees | −0.57 | 1.33 (1.02) | −0.44 | −0.43 | −0.45 | 1.3 | 5.8% | 25.8% | 37% | −2.78 (−1.15) | −4.99 (−1.65) |
| mvnl_blend | −1.02 | 1.09 (.76) | −0.71 | −0.74 | −0.65 | 1.4 | 7.7% | 30.7% | 41% | −2.97 (−1.33) | −6.48 (−2.41) |
| mvnl_pa_trees (τ .25) | +0.12 | 0.63 (.50) | 0.09 | −0.07 | 0.33 | 1.3 | 4.1% | 19.4% | 10% | −2.09 (−0.88) | −1.62 (−0.58) |
| mvnl_pa_blend (τ .5) | −0.49 | 0.60 (.43) | −0.35 | −0.46 | −0.20 | 1.4 | 4.4% | 19.8% | 21% | −2.44 (−1.11) | −4.22 (−1.75) |
| **mvnl_nt_trees (k 2)** | +0.88 | 1.10 (.79) | **0.64** | 0.31 | 1.06 | 1.4 | 2.8% | 12.2% | 4% | −1.32 (−0.57) | +1.84 (0.72) |
| mvnl_nt_blend (k 2) | +0.71 | 0.98 (.59) | 0.42 | −0.16 | 1.15 | 1.7 | 4.5% | 16.5% | 5% | −1.24 (−0.62) | +0.77 (0.39) |
| mvlw_nt_trees (linear LW, k .5) | +0.00 | 1.01 (.83) | 0.00 | 0.01 | −0.01 | 1.2 | 3.2% | 16.0% | 19% | −2.20 (−0.92) | −2.19 (−0.77) |
| mvnl_ntx_trees (k 6) | +0.59 | 0.59 (.40) | 0.40 | 0.55 | 0.22 | 1.5 | 2.6% | 11.1% | 0.1% | −1.62 (−0.67) | +0.32 (0.10) |
| mvnl_ntx_ipca (k 6) | +0.29 | 0.29 (.21) | 0.20 | 0.42 | −0.13 | 1.4 | 3.8% | 15.8% | 0.1% | −1.95 (−0.92) | −0.98 (−0.37) |
| mvnl_ntx_master (k 6) | +0.01 | 0.01 (.01) | 0.01 | −0.05 | 0.07 | 1.5 | 3.0% | 11.7% | 0.1% | +0.29 (0.13) | +0.31 (0.10) |

Order of scoring: first wave on trees and the blend; `band_vm` repeated on MASTER and IPCA (declared at the start: the
best construction at that point is repeated on those signals). Added after seeing the first wave (post hoc, greedy):
mean-variance with an L1 no-trade region, the linear-LW ablation, the wider k grid. 22 candidates exceeds the 10-20
asked; count it against any best-of selection.

## Findings

* **Rank-proportional sizing loses to the band**: similar gross Sharpe (.52 vs .56), vol falls to 4.4%, turnover does
  not fall; net Sharpe 0.21 vs 0.35. Partial adjustment narrows the gap (0.28-0.29), does not close it.
* **Leg volatility matching changes nothing** (net Sharpe within 0.01).
* **Volatility-managed scaling helps 2 of 4 signals**: trees 0.42, IPCA 0.45 (gross Sharpe .79-.91, lower drawdown at
  equal vol); hurts the blend (0.06) and MASTER (−0.44). All |t| ≤ 0.4: not robust.
* **The drawdown rule cuts raw drawdown, not Sharpe**: trees 16.2% → 10.9% (13.7% at equal vol); blend barely moves at
  equal vol (14.4% vs 14.6%) and Sharpe falls.
* **Mean-variance with LW2020 finds signal but cannot afford to trade it**: on trees gross Sharpe ≈1.0 vs the band's
  0.56 (rank weights on the same names 0.52, so the covariance adds information); at gross 1, vol 1.3 %/yr and 37%
  weekly turnover; costs 1.9 %/yr exceed the 1.3 %/yr gross. Partial adjustment destroys the alpha (week-on-week rank
  autocorrelation about 0.2); an L1 no-trade region keeps most of it (`mvnl_nt_trees`).
* **Correction**: the linear-LW ablation has similar gross Sharpe (.83 vs .79); its net 0.00 comes from k 0.5 chosen
  on 2013-2016 (19% weekly turnover), not from shrinkage. Nonlinear shrinkage is not shown to matter.
* **The best mean-variance result is fragile**: k = 2 at the tuning-grid edge; the wider grid is flat and
  non-monotone (k 3/4/6: 0.52/0.48/0.55 on 2013-2016), k 6 barely trades (stale book); in 2013-2016 the same
  construction loses on the blend (−0.16), IPCA (−0.16 at k 2), MASTER (−0.13 at k 2); clipping lets the held book
  drift on average 9% net long dollars (up to 23%), beta 0.075, so a live book needs an explicit hedge; matching the
  control's 6.4 %/yr vol needs about 4.5× gross.
* **Split check**: 2013-2016 rankings do not carry to 2017-2019 (`mvnl_ntx_trees` 0.55 → 0.22; `band_dd_trees`
  0.43 → 0.23, vs the control's 0.56); the 2017-2019 leaders were ordinary on 2013-2016; every control is strongest in
  2017-2019, so part of those years' gains is the period, not the construction.

## Diagnostics requested by the coordinator (`diag.py`, `DIAG.json`; no new configurations)

* Gross and net: in every row above.
* By size proxy (gross %/yr by residual-vol tercile, low/mid/high): best book 0.10 / 0.74 / 0.25; control
  0.68 / 2.03 / 0.87. Neither depends on high-vol names; both earn mostly in the middle tercile.
* By market volatility (net %/yr, weeks split at median cross-sectional residual vol): best book high-vol +0.09
  (Sharpe 0.06), low-vol +1.67 (1.32); control high-vol +0.64 (0.09), low-vol +3.77 (0.72). Both earn in calm weeks,
  unlike the US literature's finding that ML profits concentrate in volatile periods.

## Best construction

`mvnl_nt_trees` (`model.py`, `build_weights(scores, D, rows)`): LW2020 mean-variance, dollar- and beta-neutral at the
target, gross 1, L1 no-trade region k 2. `python model.py` reproduces the logged Sharpe (`ok: True`).

| | mvnl_nt_trees | Control (band on trees) |
|---|---|---|
| Net Sharpe | 0.64 | 0.35 |
| Max drawdown at gross 1 | 2.8% | 16.2% |
| Max drawdown at control vol | 12.2% | 16.2% |
| Net return at gross 1 | +0.88 %/yr | +2.20 %/yr |

Vol-matched paired difference +1.84 %/yr, t 0.72: not significant. Not nominated: added after seeing results, tuned
to a grid edge, fails on the other three signals in its tuning years.

## Files

`Q4_portfolio/`: `lib.py`, `run.py`, `make_signals.py`, `table.py`, `diag.py`, `model.py`, `RESULTS.jsonl`,
`TUNING.jsonl`, `DIAG.json`, `STATE.json`. Weekly nets and signals: `.cache/tree/preds/Q4_portfolio/`.
