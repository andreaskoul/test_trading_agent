# L5_ensemble: MASTER averaged over the whole grid — failed the development gate (no stage 2)

*Written by the branch agent; saved by the coordinating session because subagent report writes are refused.
**Development only** (data ≤ 2019-12-31; trained ≤ 2017; 99 Thursdays of 2018-2019). `READ_L5E.lock` was not
created. Numbers from `RESULT.json["stage1"]`.*

| | IC 2018-19 | 2018 | 2019 |
|---|---:|---:|---:|
| E: equal-weight rank average of all 20 models | .0111 | .0205 | .0015 |
| C: as-run rule (d_model 256, β 5, raw-score average of seeds 0-4) | .0140 | .0174 | .0105 |

* **Gate** (E − C, paired weekly; needs NW t ≥ 1.0 and positive in both years): −.0029, t −0.33; 2018 +.0031,
  2019 −.0090. **Fail.**
* **Sensitivity** (descriptive): with C averaging ranks instead of raw scores, C is .0099 and E − C +.0012 (t 0.16).
  Still fails.

**Per configuration** (5-seed IC; per-seed ICs in brackets):
* d64 β2: .0003 (2019 −.0264) [−.021, .013, .010, .013, .012]
* d64 β5: −.0028 (2019 −.0322) [−.017, .015, .013, .002, .005]
* d256 β2: .0147 [.005, .004, .014, .014, .015]
* d256 β5 (= C): .0140 [.019, .003, .008, −.011, .014]

**Variance-reduction curve** (mean IC over all seed subsets of size k, with the spread across subsets):

| k | d256 β5 | Grid ensemble (4k models) |
|---:|---|---|
| 1 | .0065 (sd .010) | .0079 (sd .007) |
| 2 | .0101 (sd .007) | .0099 (sd .004) |
| 3 | .0120 (sd .006) | .0106 (sd .002) |
| 4 | .0132 (sd .004) | .0109 (sd .001) |
| 5 | .0140 | .0111 |

The d256 β2 curve runs .0104 → .0147.

**Reading.**
* Seed averaging works: the mean IC doubles from one seed to five, and the spread falls to zero.
* Averaging across the grid does not: the d_model 64 configurations have no 2019 signal and dilute the d256 models.
  The as-run choice of d256 was right on this window.

**Method.**
* As-run training: Adam at 1e-5, at most 100 epochs, the loss < 0.95 or 15-epoch-patience stop, best validation
  epoch kept.
* The three L4 base fits were reused, and their IC .0147 reproduces exactly. 17 fits are new.
* Gate t ≥ 1.0 follows branch E's text ("as in the architecture branch"); this was recorded before any fit.

**Compute.** 4 workers at nice 10, 13:16-16:01 UTC (10.5 worker-hours). Checkpoints were deleted after prediction.

Files: `ens.py`, `run.py`, `workers.sh`, `gate.py`, `STATE.json`, `RESULT.json`, `logs/`; `.cache/tree/l5ens/pred_*.npz`.
