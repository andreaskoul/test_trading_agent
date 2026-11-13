# Branch Q5_rl (Layer 3, Amendment 6): reinforcement-learned portfolio construction on fixed signals

*Written by the branch agent; saved by the coordinating session because the agent's writes were refused.
**Development data only (2013-2019; 2014-2019 scored walk-forward). Not out of sample**: the signals were selected on
these years. 30 rows: 6 controls, 15 registered candidates, 9 post-hoc ablations; 66 tuning grid points
(`TUNING.jsonl`).*

**Verdict.** No RL construction beats both controls; nothing is nominated. Best: Moody-Saffell RRL trained online on
the differential Sharpe ratio (`rrl_dsr_trees`): net Sharpe 0.43 vs the band's 0.31 (+0.47 %/yr, t 0.78; vol-matched
+0.82 %/yr, t 1.50), ahead in both 2014-16 and 2017-19, drawdown at equal vol 15.7% vs 16.2%. Behind Q4's `mvnl_nt`
(0.74; vol-matched −0.44 %/yr, t −0.75). Wins on IPCA (t 0.92), loses on MASTER (t −2.16). Every network policy
(EIIE, end-to-end, PPO) loses to the band. With 24 candidates and 66 grid points, a best t of 1.5 is the expected
maximum under the null.

## Setup

* **Book**: M1 `simulate` convention (weights at Thursday t from data ≤ t, next close, w·y5 net of 5 bp × sum|dw|);
  y5 is beta-hedged, so each book carries an implicit SPY leg −Σ w_i β_i whose cost is not charged (as for the
  controls); dollar-neutral, gross ≤ 1; exposure heads scale gross down only (mean gross 0.4-1.0), hence vol-matched
  comparisons.
* **Market state x_t (8 causal inputs)**: market 20/120-session return; log 21-session realised vol; drawdown from the
  252-session high; log cross-sectional dispersion of 5-session residual returns; the signal's mean realised IC over
  the last 13 and 52 weeks with closed targets (rows ≤ t−7); the signal's week-on-week rank autocorrelation. First five
  standardised on 2010-2012 Thursdays. Before any scoring, autocorrelation re-centred to (ac − .5) × 3 (the trees
  signal's is about 0.8).
* **Walk-forward (scored)**: year y in 2014-2019 uses the policy trained on weeks whose y5 ended before y; the book
  carries over; 2013 holds the control band (no earlier signal), switch cost into 2014 charged; statistics on
  2014-2019 (303 weeks), so "13-16" here is 2014-16. Controls on the same weeks (hence band trees 0.31 vs Q4's 0.35).
* **Fixed split (check)**: trained once on 2013-2016, run on 2017-2019; in-sample 2013-16 Sharpe also reported.
* **Tuning**: only training length, on walk-forward 2014-16 by seed-mean net Sharpe: RRL batch {25, 100, 300} Adam
  steps; RRL-DSR {1, 3, 10} passes; PPO {30, 100, 300} iterations; EIIE {200, 1000, 3000} updates; E2E {25, 100, 300}
  epochs. Fixed a priori: learning rates, network 5→16→16→1, DSR rate 0.04, PPO constants, 26-week window, RRL
  initialised at the control band.
* **Seeds** 0-2 per configuration; scored net = mean of the three seed books; per-seed range in the table.

## Methods

1. **`rrl_bs`, `rrl_dsr`** (Moody-Saffell RRL): 13-parameter recurrent policy — smooth no-trade band on the signal
   percentile (enter when |p−.5| > k; a held name keeps its side while |p−.5| > k−h; "held" is the recurrent input),
   size tilt by vol^−θv and signal strength, sides 0.5 each, exposure sigmoid(b0 + β·x_t) ≤ 1, initialised at the
   control band (k .4, h .1). `rrl_bs`: batch net Sharpe, full BPTT. `rrl_dsr`: online differential-Sharpe updates,
   one step a week, one-step truncated recurrence.
2. **`ppo`**: clipped surrogate + GAE; linear-Gaussian policy in (x_t, running DSR mean) choosing trade rate toward the
   band target, exit width and exposure; reward DSR; 52-week episodes, 16 per iteration, from the control book.
3. **`eiie_pvm`** (Jiang et al. 2017): shared per-name network on percentile, last week's percentile, held weight,
   log vol ratio, beta; scores centred and L1-normalised, scaled by an exposure head; portfolio-vector memory on random
   26-week mini-batches; objective net Sharpe.
4. **`e2e`** (Zhang-Zohren-Roberts style): the same network by full-sequence backprop on net Sharpe (non-RL baseline).
5. **Post-hoc ablations** of `rrl_dsr` (after seeing it lead): `rrl_dsr_book` (exposure fixed at 1), `rrl_dsr_exp`
   (book fixed at the band; exposure learns), `band15` (unlearned band, exit width 0.15 = what `rrl_dsr` learned).

## Results (walk-forward 2014-2019)

"diff (t)": weekly net, candidate minus control, %/yr, Newey-West t (4 lags). "vm": candidate scaled to the control's
full-period vol. "DD@ctl vol": max drawdown at the band control's vol. "IS 13-16" / "FS 17-19": fixed-split in-sample
Sharpe and its 2017-19 check.

| config | net %/yr | gross Sh | net Sh | 14–16 | 17–19 | seeds | vol | maxDD | DD@ctl vol | turn/wk | vs band diff (t) | vs band vm (t) | vs mvnl_nt vm (t) | IS 13–16 | FS 17–19 | length | gross |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C_band_trees | +2.01 | 0.52 | 0.31 | 0.12 | 0.56 | – | 6.5 | 16.2% | 16.2% | 26% | – | – | −0.61 (−1.09) | – | – | – | 1.00 |
| C_mvnlnt_trees | +1.05 | 0.89 | **0.74** | 0.43 | 1.06 | – | 1.4 | 2.8% | 12.3% | 4% | −0.96 (−0.39) | +2.85 (1.09) | – | – | – | – | 1.00 |
| C_band_ipca | +2.25 | 0.60 | 0.34 | 0.27 | 0.42 | – | 6.6 | 11.8% | 11.8% | 33% | – | – | +0.09 (0.16) | – | – | – | 1.00 |
| C_mvnlnt_ipca | +0.49 | 0.48 | 0.29 | −0.08 | 0.71 | – | 1.7 | 3.9% | 14.6% | 6% | −1.76 (−0.81) | −0.34 (−0.16) | – | – | – | – | 1.00 |
| C_band_master | −0.86 | 0.18 | −0.13 | −0.37 | 0.15 | – | 6.4 | 17.7% | 17.7% | 38% | – | – | +0.06 (0.10) | – | – | – | 1.00 |
| C_mvnlnt_master | −0.27 | 0.06 | −0.18 | −0.12 | −0.23 | – | 1.5 | 3.8% | 15.4% | 7% | +0.59 (0.26) | −0.27 (−0.10) | – | – | – | – | 1.00 |
| rrl_bs_trees | +0.14 | 0.20 | 0.03 | 0.05 | −0.02 | −.02–.09 | 5.1 | 12.8% | 16.1% | 17% | −1.87 (−1.18) | −1.83 (−1.13) | −1.01 (−1.74) | 1.51 | 0.18 | 300 | 0.55 |
| rrl_bs_ipca | +1.64 | 0.67 | 0.38 | 0.54 | 0.23 | .37–.40 | 4.3 | 8.2% | 12.4% | 23% | −0.61 (−0.41) | +0.27 (0.16) | +0.16 (0.24) | 1.25 | 0.31 | 100 | 0.55 |
| rrl_bs_master | −1.62 | −0.09 | −0.35 | −0.39 | −0.33 | −.36–−.34 | 4.6 | 10.4% | 14.2% | 23% | −0.76 (−0.37) | −1.37 (−0.60) | −0.26 (−0.36) | 1.93 | −0.20 | 300 | 0.39 |
| **rrl_dsr_trees** | +2.48 | 0.64 | **0.43** | 0.22 | 0.78 | .43–.44 | 5.7 | 13.9% | 15.7% | 23% | +0.47 (0.78) | +0.82 (1.50) | −0.44 (−0.75) | 0.35 | 0.76 | 3 | 0.90 |
| rrl_dsr_ipca | +2.68 | 0.67 | 0.42 | 0.30 | 0.55 | .42–.44 | 6.3 | 11.3% | 11.8% | 30% | +0.42 (0.92) | +0.53 (1.13) | +0.22 (0.40) | 0.47 | 0.43 | 3 | 0.95 |
| rrl_dsr_master | −1.47 | 0.09 | −0.24 | −0.48 | 0.06 | −.24–−.24 | 6.1 | 18.6% | 19.3% | 38% | −0.62 (−2.16) | −0.67 (−2.44) | −0.09 (−0.14) | −0.23 | 0.06 | 1 | 0.96 |
| ppo_trees | +1.39 | 0.50 | 0.30 | 0.09 | 0.56 | .23–.39 | 4.7 | 9.8% | 13.5% | 18% | −0.62 (−0.60) | −0.07 (−0.09) | −0.63 (−1.14) | 0.46 | 0.40 | 300 | 0.87 |
| ppo_ipca | +1.04 | 0.40 | 0.21 | 0.34 | 0.05 | .09–.29 | 5.0 | 10.9% | 14.1% | 18% | −1.21 (−1.13) | −0.89 (−0.85) | −0.14 (−0.26) | 0.60 | 0.03 | 300 | 0.94 |
| ppo_master | −1.10 | 0.13 | −0.23 | −0.50 | 0.11 | −.27–−.19 | 4.8 | 16.8% | 21.7% | 33% | −0.24 (−0.31) | −0.60 (−0.81) | −0.08 (−0.11) | −0.32 | 0.07 | 100 | 0.95 |
| eiie_pvm_trees | −1.53 | −0.18 | −0.40 | −0.88 | 0.25 | −.62–−.10 | 3.8 | 14.2% | 23.5% | 17% | −3.54 (−1.97) | −4.65 (−2.56) | −1.62 (−2.65) | 0.50 | 0.18 | 200 | 0.83 |
| eiie_pvm_ipca | −0.77 | 0.00 | −0.20 | −0.18 | −0.23 | −.62–.11 | 3.8 | 12.0% | 19.8% | 15% | −3.02 (−1.38) | −3.57 (−1.41) | −0.83 (−1.11) | 0.77 | 0.17 | 200 | 0.86 |
| eiie_pvm_master | −0.42 | 0.18 | −0.10 | 0.14 | −0.50 | −.14–−.03 | 4.0 | 8.8% | 13.7% | 22% | +0.44 (0.16) | +0.19 (0.06) | +0.11 (0.17) | 0.57 | 0.01 | 200 | 0.82 |
| e2e_trees | −0.31 | 0.09 | −0.07 | −0.41 | 0.26 | −.19–.04 | 4.3 | 10.3% | 15.5% | 14% | −2.32 (−1.54) | −2.48 (−1.70) | −1.15 (−1.93) | 0.41 | 0.26 | 25 | 0.92 |
| e2e_ipca | −0.12 | 0.13 | −0.03 | −0.24 | 0.18 | −.11–.02 | 4.5 | 10.3% | 15.0% | 13% | −2.37 (−1.47) | −2.42 (−1.41) | −0.54 (−0.87) | 0.48 | 0.24 | 25 | 0.95 |
| e2e_master | −1.55 | −0.25 | −0.53 | −0.83 | −0.22 | −.69–−.25 | 2.9 | 11.6% | 23.8% | 15% | −0.69 (−0.29) | −2.49 (−0.81) | −0.52 (−0.74) | 1.67 | −0.00 | 300 | 0.64 |
| *post hoc* rrl_dsr_book_trees | +2.25 | 0.55 | 0.35 | 0.15 | 0.65 | .35–.36 | 6.4 | 15.9% | 16.3% | 24% | +0.24 (0.75) | +0.30 (0.95) | −0.55 (−0.96) | 0.26 | 0.64 | 3 | 1.00 |
| *post hoc* rrl_dsr_exp_trees | +1.94 | 0.64 | 0.42 | 0.45 | 0.47 | .41–.42 | 4.6 | 9.9% | 13.8% | 20% | −0.07 (−0.06) | +0.73 (0.64) | −0.46 (−0.77) | 0.42 | 0.43 | 10 | 0.66 |
| *post hoc* band15_trees | +2.00 | 0.51 | 0.32 | 0.13 | 0.58 | – | 6.2 | 14.8% | 15.6% | 22% | −0.01 (−0.04) | +0.11 (0.35) | −0.59 (−1.03) | 0.22 | 0.58 | – | 1.00 |
| *post hoc* rrl_dsr_book_ipca | +2.67 | 0.64 | 0.40 | 0.30 | 0.49 | .39–.41 | 6.7 | 11.6% | 11.3% | 32% | +0.42 (0.89) | +0.36 (0.79) | +0.18 (0.33) | 0.47 | 0.38 | 3 | 1.00 |
| *post hoc* rrl_dsr_exp_ipca | +1.92 | 0.67 | 0.37 | 0.35 | 0.43 | .37–.38 | 5.1 | 10.4% | 13.2% | 30% | −0.33 (−0.33) | +0.20 (0.23) | +0.14 (0.24) | 0.32 | 0.48 | 10 | 0.84 |
| *post hoc* band15_ipca | +2.17 | 0.59 | 0.35 | 0.32 | 0.38 | – | 6.2 | 11.0% | 11.5% | 28% | −0.08 (−0.22) | +0.03 (0.09) | +0.10 (0.17) | 0.30 | 0.38 | – | 1.00 |
| *post hoc* rrl_dsr_book_master | −1.50 | 0.09 | −0.23 | −0.48 | 0.07 | −.23–−.23 | 6.4 | 19.4% | 19.2% | 40% | −0.64 (−2.32) | −0.62 (−2.28) | −0.08 (−0.12) | −0.25 | 0.07 | 1 | 1.00 |
| *post hoc* rrl_dsr_exp_master | −1.40 | 0.09 | −0.25 | −0.43 | −0.02 | −.25–−.24 | 5.7 | 16.8% | 18.7% | 37% | −0.54 (−1.24) | −0.72 (−1.85) | −0.10 (−0.16) | −0.14 | −0.03 | 3 | 0.94 |
| *post hoc* band15_master | −1.36 | 0.07 | −0.23 | −0.50 | 0.11 | – | 6.0 | 18.1% | 19.0% | 34% | −0.50 (−1.53) | −0.58 (−1.74) | −0.07 (−0.11) | −0.34 | 0.11 | – | 1.00 |

## Findings

* **Batch-Sharpe RRL overfits**: in-sample 2013-16 Sharpe 1.25-1.93 vs walk-forward 0.03 / 0.38 / −0.35. The length
  chosen on 2014-16 (300 steps, trees) was the worst on 2017-19 (25 steps scored 0.65 there; unused for selection).
  Exposure collapses to 0.4-0.55 gross.
* **Online DSR RRL is the only method that improves on the band, modestly.** One-step updates barely move it from the
  band initialisation (strong implicit regularisation); seed spread .43-.44 understates true estimation error. It
  learns, on trees and IPCA: a slightly wider exit band (h 0.12-0.15 vs 0.10); a tilt away from high-vol names (θv to
  0.6-0.8 by 2019); lower exposure when market vol, dispersion or recent realised IC is high (an IC mean-reversion
  bet). On MASTER it loses (t −2.16).
* **Ablations (post hoc)**: the fixed wider band alone (`band15`) ties (+0.11 / +0.03 %/yr vol-matched). On trees the
  gain splits between the exposure head (`rrl_dsr_exp` 0.42 at gross 0.66, vm +0.73, t 0.64) and book shape + tilts
  (`rrl_dsr_book` 0.35, t 0.95); on IPCA the book part carries it. None significant; pattern differs by signal.
* **PPO** does not beat the band (0.30 / 0.21 / −0.23); seed spread up to 0.20 Sharpe.
* **Per-asset networks fail**: EIIE −0.40 / −0.20 / −0.10; end-to-end −0.07 / −0.03 / −0.53; gross Sharpe ≤ 0.18 (they
  lose signal, not just trade too much); fixed-split in-sample 0.4-1.7, walk-forward negative. The non-RL baseline is
  no better than EIIE on trees and IPCA.
* **2014-16 vs 2017-19**: controls and most candidates stronger in 2017-19. `rrl_dsr_trees` leads the band in both
  halves (+0.62, +0.32 %/yr); its fixed-split 2017-19 check (0.76) matches walk-forward (0.78). Other rankings do not
  carry across halves (`rrl_bs_ipca` 0.54 → 0.23; `eiie_pvm_master` 0.14 → −0.50).
* **Versus Q4's mean-variance control**: nothing on trees comes close (mvnl_nt 0.74, 2.8% drawdown at gross 1); on
  IPCA and MASTER mvnl_nt is no better than the band and RL ties it.

## Best policy (`model.py`)

`rrl_dsr_trees` (online-DSR RRL, 3 passes, seeds 0-2, walk-forward yearly). `build_weights(scores, D, rows)` returns
seed-mean weights; `seed_books` the three sub-books. `python model.py` reproduces net Sharpe 0.43359 (`ok: True`).

| 2014-2019, 5 bp | rrl_dsr_trees | Control (a): band 0.1 | Control (b): mvnl_nt |
|---|---|---|---|
| Net Sharpe | 0.43 | 0.31 | 0.74 |
| Net %/yr | +2.48 | +2.01 | +1.05 (gross 1, vol 1.4%) |
| Max drawdown | 13.9% | 16.2% | 2.8% |
| Max drawdown at band vol | 15.7% | 16.2% | 12.3% |
| Vol-matched diff vs it | – | +0.82 %/yr (t 1.50) | −0.44 %/yr (t −0.75) |

**Not nominated**: beats only the weaker control, not significantly; fails on MASTER; within the noise of 24
candidates.

## Caveats

* Development data only; the signals were selected on these years.
* Development-panel survivorship gap (241 of 738 names unpriced; 23.5% of eligible name-weeks without a target);
  delisting losses absent; can bias the short leg and understate drawdowns, for candidates and controls alike.
* SPY hedge implicit; its cost not charged. Exposure heads cut gross, flattering raw drawdowns: use vol-matched
  columns. Seed spreads are initialisation noise only.
* EIIE and E2E configurations took about 30 minutes each (above the 25-minute target); grids not shortened.
* Departure from the brief: 9 post-hoc ablations, registered and counted, descriptive only.

Files: `lib.py`, `run.py`, `model.py`, `RESULTS.jsonl` (30 rows), `TUNING.jsonl`, `STATE.json`, `run_*.log`. Weekly
nets (2014-2019, 303 weeks): `.cache/tree/preds/Q5_rl/<name>.npy`; mvnl_nt weight panels `_W_mvnl_nt_<signal>.npy`.
