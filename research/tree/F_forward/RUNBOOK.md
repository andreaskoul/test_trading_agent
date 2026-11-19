# Forward phase (PREREG Layer 3, Amendment 9): weekly runbook

The coordinator runs this by hand, once a week, after the Thursday whose book is to be recorded has a complete
5-session target (that is, from the following Friday's close). No job is installed. An installed runner needs the
owner's go-ahead, because it touches the machine that runs the fund (Amendment 7). See the last section.

**Forward weeks** are the Thursdays after 2026-11-12. The first is 2026-11-19. Its 5-session target runs from the
close of session d+1 to the close of d+6. Thanksgiving falls on Thu 2026-11-26, so d+6 is **Mon 2026-11-30**, and the
first record can be written on Saturday 2026-12-05. There is no 2026-11-26 book, because there is no session, as in
H7. The test (H9: F1 − F0 paired; secondary: F2 − F0 at matched volatility; Holm) is read
**once, at forward week 104**. Until then, nobody computes or prints any difference, ranking or Sharpe of the
constructions' returns. `h9_forward.py` never prints a return.

## Weekly sequence

1. **Fetch** (key-needing: always through the redacting wrapper, and keep the command free of other file edits,
   CLAUDE.md rule 16):

   ```
   python3 ~/.claude/hooks/with_secrets.py 'python3 research/tree/fetch_broad.py fwd'
   python3 ~/.claude/hooks/with_secrets.py 'python3 research/tree/fetch_broad.py fwdraw'
   ```

   * Each fetch writes a new folder, `.cache/tree/y2026/fwd_<end>/chunks{,_raw}`. It runs from the previous
     window's end (one overlap session) to the last complete session.
   * It never touches the frozen y2026 chunks or an earlier window (rule 4). A window counts only once its meta says
     `complete`.
   * `h7_build.read_chunks` reads the windows in order, and so does `h9_forward.raw_dollar_volume`, through it.
     Adjusted closes are chain-linked on the overlap session, because `adjustment=all` is as of the fetch date, so a
     dividend inside a window rescales only that window. On the overlap session the earlier, frozen bar stands.
   * Tested end to end on a synthetic window: `h9_forward.py fwdtest`.
   * Register this as a dated operational note before the first forward fetch.
   * `weekly.sh` runs all of steps 1-5. `INSTALL.md` has the job.

2. **Extend the panels** (no key):

   ```
   python3 research/tree/h7_build.py broad_panel                         # .cache/tree/y2026/broad_panel.npz
   ~/.cache/quant-tf-venv/bin/python research/tree/h7_build.py sp_panel  # fund side, for the H7 extension
   ```

   `broad_panel` rebuilds the whole panel and checks it against the saved 2009-2025 panel (`H7_build/CHECKS.json`
   step3). Before going on, confirm that every 2025 field is still `equal: true`.

3. **Predict with the frozen 2026 models.** The trees are refit deterministically: same code, seeds 0-2, and
   `train_end` 2025-12-19 for 2026. There is no saved model object, so "frozen" means the same training rows and
   seeds give the same model.

   ```
   python3 research/tree/h7_build.py trees 2026                          # rewrites trees_2026.npy on the new panel
   ```

   * Copy the old `trees_2026.npy` aside first. The new file must equal the old one on every Thursday that both
     contain. This holds if the panel up to 2025 is unchanged, because the training rows end in 2025. If the two
     files differ, the books of past weeks change. `books` then reports `drift_vs_recorded` and exits non-zero
     without overwriting anything.
   * MASTER (fund side, H7 extension) is the same idea: `master 2026` with the frozen configuration and seeds 0-4.
     It takes about 5 hours on MPS. Whether a full refit is needed each week, or only scoring with the saved seeds,
     is the coordinator's choice. It does not affect the broad books.
   * **Each January** (Amendment 9: models refit each January on targets ending before that year): run
     `h7_build.py trees 2027` (or `master 2027`) once, writing `trees_2027.npy`. `h9_forward.py` picks up
     `trees_YYYY.npy` for year YYYY by name and checks its shape against the panel.

4. **Record the books** (no key):

   ```
   OMP_NUM_THREADS=3 python3 research/tree/h9_forward.py books --through <Thursday>
   python3 research/tree/h9_forward.py status
   ```

   * Takes about 10 minutes. Most of it is F2's covariance (about 6 s per week), recomputed from January 2025 on
     every run.
   * Appends one line per (week, construction) to `RECORDS.jsonl`, and the forward weights of F0, F1 and F2 to
     `WEIGHTS.jsonl`. The weights are needed for the vol-matched F2 read.
   * Weeks up to 2026-11-12 go only to `BACKFILL_2025_2026.jsonl` (not forward; code check only).
   * Writes `CHECKS.json`. Exit status 1 means **QUALITY GATE FAILED** (the records were saved first): read
     `CHECKS.json` `pass`, `drift_vs_recorded` and `input_defects`.
   * `--h7check` repeats the equality of F0 at flat 14 bp with `h7_read.broad_books()`, which needs H7_DRY-style use
     of its functions only.

5. **Commit** `research/tree/F_forward/{RECORDS,WEIGHTS}.jsonl` and `CHECKS.json` on the research branch (never
   `fund-data`; merge windows per CLAUDE.md rule 15). Push loops must fail loudly (rule 10).

6. **Every 13 forward weeks:** report `status`. That is turnover, realised cost (spread, impact, bp per unit traded)
   and holdings counts per construction, and nothing else. The cumulative H7 increment test continues on F0_flat14 ×
   0.59 per Amendments 7 and 9; that is the coordinator's read, not this script's.

## What is frozen

* **Code:** `h9_forward.py` and what it imports: M1 `build("decile")`, Q6 `build("T1")` (`hysteresis`, enter 0.10,
  exit 0.30), Q4 `t_mvnl` with the L1 no-trade rule k 2, gross 1, LW2020 nonlinear shrinkage, 252-session window.
* **Constants:** half-spreads 9.4 / 6.2 / 4.2 bp by dollar-volume tercile (`COST_STUDY.json`), K 0.5, AUM $10M,
  σ = 60-session sd of `r`, ADV = 20-session median of daily unadjusted $ volume, flat 14 bp for the H7 extension,
  y5 clipped at ±1, at least 50 names a week, eligible broad names only.
* **Books** are carried from January 2025 (Amendment 7a), so the first forward week enters already held.
* **Data:** the fetched bars, frozen at first fetch. Recorded weeks are never recomputed or rewritten. A
  recomputation that differs is reported as drift, and the file keeps the first value.
* **The read:** once, at forward week 104; no interim test of F1 − F0 or F2 − F0.

## What an installed weekly job would need (owner approved 2026-11-14; built as `weekly.sh` and `INSTALL.md`, not loaded)

* A launchd job on the fund Mac on Saturdays (outside every merge-block window in rule 15). It would run steps 1-5
  in order and stop at the first non-zero exit.
* The incremental fetch of step 1 (the blocker above), run through `with_secrets.py`, with the key file never read by
  the job script itself.
* Steps 2-3 take about 15 minutes for the broad side, without MASTER. MASTER's refit (about 5 h, MPS) should not run
  on the fund machine during trading hours. Score with frozen seeds instead, or run it on another machine.
* The quality gate: a non-zero exit from `broad_panel` checks, from `books` (`CHECKS.json` pass false) or from a
  failed push opens an issue and texts the owner, as the other runner jobs do (rules 9-10).
* A coverage contract against what was expected (rule 3): 1,500 eligible broad names each Thursday and at least 90%
  of them scored. `books` checks this for forward weeks and reports `input_defects`.
* Disk: `broad_panel.npz` is about 1 GB and is rebuilt each week. Keep one previous copy for the drift comparison.
