# N2: FINRA short volume on top of MASTER (development 2013-2019, 353 weeks; 2026-11-12)

7 prediction configurations + 3 double-ML estimates, all logged in `RESULTS.jsonl` (training-row screens in
`SCREEN.jsonl`). Code: `lib.py` (causal features), `run.py` (c1-c7), `dml.py`, `model.py` (c3). Combinations score
only MASTER's names; c1 scores every name with FINRA data. Fixed weights and the 2013 fallback (0.7/0.3) set in advance.

| Config | IC | base IC | incr. | incr. t | yrs + /7 | corr MASTER | decile net %/yr | net Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MASTER 5-day alone (reference) | 0.0125 | | | | | 1 | -1.73 | -0.26 |
| c1 F2 alone (IC t 2.59 by `score`) | 0.0110 | 0.0125 | -0.0015 | -0.15 | 3 | 0.08 | +1.49 | 0.45 |
| c2 rank avg 0.5/0.5 | 0.0145 | 0.0125 | +0.0020 | 0.50 | 3 | 0.74 | +0.84 | 0.16 |
| **c3 rank avg 0.7/0.3** | 0.0145 | 0.0125 | +0.0020 | **1.14** | 5 | 0.93 | +0.42 | 0.07 |
| c4 Fama-MacBeth [MASTER, F2] | 0.0126 | 0.0125 | +0.0000 | 0.01 | 4 | 0.77 | +0.26 | 0.05 |
| c5 FM [MASTER, 7 short features] | 0.0104 | 0.0125 | -0.0022 | -0.45 | 4 | 0.67 | -1.29 | -0.27 |
| c6 FM [MASTER, screened (IC t>=2)] | 0.0117 | 0.0125 | -0.0008 | -0.21 | 4 | 0.75 | -0.11 | -0.02 |
| c7 boosted trees [MASTER, 7 feats, Z] | 0.0070 | 0.0125 | -0.0055 | -0.81 | 4 | 0.38 | -4.63 | -0.97 |

Short features: 5/20/60-session ratios, change (5 minus 60), ratio vs its own 252-session history (z), short volume
and total volume vs their own 252-session average. No shares outstanding in the data, so "relative to turnover" is
proxied by the ratio itself and abnormal total volume. Screen (training rows from 2012): only the ratio levels
(f2, f5, f60) ever reach t >= 2; change and abnormal measures never do.

**Double ML** (partially linear; HistGradientBoosting nuisances on MASTER rank + 5 characteristics, cross-fitted by
year; NW(4) over weekly sums; 131,703 name-weeks): F2 theta **0.0074, t 1.61** (raw slope 0.0106). Controls explain
2.6% of F2's variance, so F2 is not a tilt MASTER or the characteristics already carry; about 30% of its raw slope
goes once they are partialled out. f5: 0.0050 (t 1.11); f60: 0.0062 (t 1.34).

**Honest reading.**
* No configuration reaches the registered gate (increment t >= 1.5). The best, c3 (0.7/0.3 fixed), has t 1.14 and is
  the best of 7 tries, so its t is biased upward. Under the phase-2 rule N2 has no development finalist.
* Signs agree: F2 is nearly uncorrelated with MASTER (0.08), positive alone, and its partial effect after MASTER is
  +0.007 (t 1.6). But MASTER's own development IC is only 0.0125 (t 1.43); an IC gain of 0.002 is inside noise.
* Fitted weights (c4-c7) do worse than fixed ones: 6 years of weekly ICs are too few to estimate them; adding
  features or trees subtracts. 2018 is negative for every combination.
* Cost side, descriptive only: blending F2 (slow, low turnover) turns MASTER's decile book from -1.7%/yr to
  +0.4..+0.8%/yr net at 5 bp. Not a tested claim.
* Data end 2019; nothing here touched 2020-2025. F2's own 2020-2025 pass is prior evidence, not used here.
