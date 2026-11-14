# H7 build: inputs for the 2026 sealed test (PREREG Layer 3, Amendment 7)

Built 2026-11-13 by `research/tree/h7_build.py`. There is one subcommand per step, and each step writes its checks
into `research/tree/H7_build/CHECKS.json`. Logs for every step are in this folder. **No statistic in this build
combines a 2026 prediction with a 2026 outcome.** The checks are shapes, coverage counts, correlations between
prediction vectors, and comparisons on data up to 2025-12-31. 2026 targets (y5) are computed inside the panels,
because the scored read needs them, but no 2026 target value was printed, summarised or examined.

Data: the coordinator's Alpaca SIP fetch, `.cache/tree/y2026/chunks` and `chunks_raw`, 195 files each, 2025-01-02 to
2026-11-12. That is the last complete session; the end date was moved from 2026-11-13 after a 403 response, with no
bar saved. `fetch_end()` keeps sessions up to and including the `end` in `_fetch_*.json`, and no bar after it existed.

## Output files

| file | shape | content |
|---|---|---|
| `.cache/tree/y2026/sp500_close_ext.parquet` | 4494 sessions x 851 (850 names + SPY) | yfinance closes to 2025-12-31, Alpaca 2026 chain-linked |
| `.cache/tree/y2026/sp_panel.npz` | S 4494, names 850; Z 4494x850x5; y5/y10/y20/elig/e/r/beta/valid/frozen 4494x850 | `sp500_test.build` on the extended prices |
| `.cache/tree/y2026/master_h5_2026.npy` | 4494 x 850 float32 | MASTER 5-day, mean of seeds 0-4, rows = 45 Thursdays of 2026 (NaN elsewhere) |
| `.cache/tree/y2026/master_seeds/2026_seed{0..4}.npy` | 45 x 850 each | per-seed scores (+ `.json` with epochs and validation IC) |
| `.cache/tree/y2026/master_h5_2025_refit.npy` | 4276 x 850 | fidelity refit for 2025 (spent data) |
| `.cache/tree/y2026/broad_panel.npz` | S 4494, names 4780 (850 S&P + 3930 broad), isb 4780; Z 4494x4780x5; y5/elig/e/r/beta/valid/dv/y5_delist 4494x4780 | extended broad panel, read3.load_panel format |
| `.cache/tree/y2026/trees_2026.npy` | 4494 x 4780 float32 | L3b trees, rank mean of seeds 0-2, rows = 45 Thursdays of 2026 |
| `.cache/tree/y2026/trees_dv_tercile_2026.npz` | rows 45, dates 45, names 4780, tercile 45 x 4780 int8 | 1/2/3 = dollar-volume tercile among eligible broad names (3 = highest); 0 = not an eligible broad name. H7b keeps 2 and 3 |
| `.cache/tree/y2026/trees_2025_refit.npy` | 4494 x 4780 | fidelity refit for 2025 |
| `research/tree/H7_WEIGHTS.json` | | k_a = 0.59, k_b = 0.5307, with the method |

The 2026 Thursdays run from 2026-01-08 to 2026-11-12 (45 in all). Under the registration, the scored weeks are those
whose 5-session target is complete by 2026-11-12. The y5 window of Thursday d covers the closes of rows d+1 to
d+6, so in the panel's convention the last scorable Thursday is the one where d+6 is at most the last row. The
coordinator applies this; nothing here selects scored weeks.

## Step 1: S&P 500 panel extended to 2026-11-12

* **Construction.** 2026 closes for each panel name and SPY = Alpaca adjusted close × (yfinance close / Alpaca close)
  on the last 2025 date where both exist. For every anchored name that date is 2025-12-31. The fund panel is
  `sp500_test.build()` run with `T.PX`, `T.END` and `T.membership` patched, as `spx_live.py` does. Only files under
  `.cache/tree/y2026/` were written; nothing in the quant-tf cache changed.
* **Calendar.** Alpaca and yfinance agree on all 250 sessions of 2025. 2026 has 218 sessions (2026-01-02 to
  2026-11-12).
* **Seam check (2025 only).** Correlation of daily returns, Alpaca vs yfinance, over the 619 names with at least 20
  common 2025 returns: median 0.999999, 5th percentile 0.99991, 1st percentile 0.9904; SPY 0.9999998. Seven names
  are below 0.99:
  * KG 0.43, PCL 0.66 and CAM 0.99 are old tickers. Alpaca's history for them is a different issuer. None is a 2026
    member, so none is eligible in 2026.
  * FTV 0.90, TDG 0.97, WDC 0.98 and LEN 0.988 are 2026 members. Each had a 2025 corporate action that the two
    vendors adjust differently: FTV's Ralliant spin-off, WDC's SanDisk spin-off, LEN's Millrose spin-off and TDG's
    special dividend. This affects 2025 prices only. Their 2026 returns are Alpaca's own adjusted returns.
* **No anchor: 25 names.** These symbols have no yfinance close at all in the panel (the October download got
  nothing), yet Alpaca returns partial 2026 bars under them, some of them renamed tickers (BK, MMC). They are **left
  without 2026 prices**, as they were before: APC ATGE AVB BBBY BK CA CMA CSRA CTRA DAY EA EQR HOLX LEG LIFE MMC NFX
  PSKY PX QRVO SEE SGP SPLS TGNA WBD. Ten of them are 2026 members: AVB BK CTRA DAY EA EQR HOLX MMC PSKY WBD.
  Because they had no prices in 2009-2025 either, MASTER never scored them in the October read; the same holds here.
  This is the deviation flagged in the first round of the build. I made the change after looking only at symbol
  coverage, before any model was fitted. 617 panel names carry 2026 prices. No anchored name has a missing session
  inside its 2026 span, and one stops before the last session.
* **Membership.** `sp500_membership.csv` runs to 2026-08-18 and has 14 rows in 2026. It is used point in time and
  its last row is carried forward to 2026-11-12. That last row equals `sp500_current.csv` exactly (503 names), so
  no current-list row is appended. Sixteen 2026 members are not panel columns and have no prices: BNY CASY COHR ECHO
  FDXF FERG FLEX HONA LITE MRSH MRVL RDDT SATS VEEV VMRK VRT. The panel's names are fixed at the 850 of the October
  build. Index changes after 2026-08-18 are not in the file. Eligible names per 2026 Thursday: 488 to 503; with all
  five Z values present, at least 485. (2025 had 480 to 490 names scored.)
* **Equality with the original build, dates up to 2025-12-31.** Z, frozen, elig, e, r, rm, spy, beta and valid are
  **identical** (`np.array_equal`). y5, y10 and y20 are identical wherever the original is finite. The only
  differences are cells that were NaN in the original because their target window runs into 2026. They are now
  finite and were counted, never examined: y5 has 2958 cells (2025-12-23 to 12-31), y10 5423 and y20 10346.

## Step 2: MASTER 5-day refit, training through 2025

* **Configuration.** As in the October read (`sp500_transformers.py`, part `master_h5`): d_model 256 and beta 5.
  This equals `sp500_tf_master_h5.npz` meta `chosen`, which the script asserts. Seeds 0-4 are averaged by
  `nanmean` of raw scores, as `run()` does. `windows(S, 2026, h=5)`: training rows 2010-01-04 to 2025-12-22 (the
  last row's target ends at the 2025-12-31 close). Fitting uses 2010-01-04 to 2022-09-29; validation (best epoch,
  patience 15) uses 2022-10-10 to 2025-12-22. y5 is blanked after
  the last training row before the call; this has no effect, because no other row is read. The model is
  `master_fit_predict`, unchanged. It ran on MPS with torch at 3 threads.
* **Fidelity on spent data.** The same code refit for 2025 (training through 2024, original build) reproduces the
  October read's 2025 scores. The per-Thursday Spearman correlation with `sp500_tf_master_h5.npz` is **1.000** on
  all 48 Thursdays (min 0.9999999999999998). The rank correlation between seeds averages 0.33, so the five-seed
  mean matters, and it is reproduced.
* **2026 refit.** All five seeds finished (`master_2026.log`, 16:40 to 21:26 on 2026-11-13). Epochs run / best
  epoch / validation IC (2022-10 to 2025-12, inside the training window): seed 0 29/13/0.037, seed 1 31/15/0.041,
  seed 2 37/21/0.038, seed 3 41/25/0.046, seed 4 29/13/0.058. Scores exist on exactly the 45 Thursdays from
  2026-01-08 to 2026-11-12, for 484 to 493 names per Thursday. The mean rank correlation between seeds is 0.50.

## Step 3: broad panel extended to 2026-11-12

* **Construction.** Adjusted closes: `.cache/tree/broad/chunks` to 2025-12-31, with 2026 values from the y2026
  adjusted chunks, chain-linked on the last common 2025 date. One name anchors on a date other than 2025-12-31. 30
  names have 2026 bars and no 2025 overlap; they take Alpaca levels at scale 1 and none of them can reach 252
  sessions of history. Unadjusted prices drive eligibility only. They come from `broad/chunks_raw` up to
  2025-12-31 and from `y2026/chunks_raw` after; they are not chain-linked. The eligibility rule is the
  Amendment 1/4 rule, `panel_broad.eligibility`: close above $5, at least 252 sessions, top 1,500 by 63-session
  dollar volume. The exclusions are the same: S&P 500 panel names, the S&P 400 names already read (panel400.build's
  construction) and SPY. Fields come from `panel400.fields` on the S&P extension of step 1 plus the broad names.
* **Column order (deviation, harmless).** The saved panel's 3753 broad names come first, in their saved order, then
  the 177 names that are eligible only in 2026, sorted. `panel_broad.build` would sort all names together. I chose
  this order so that the 2025 refit reproduces exactly (row order inside the tree training set).
* **Equality with `.cache/tree/broad/panel.npz`, dates up to 2025-12-31, saved names.** elig, Z, valid, r, e, beta,
  rm, spy and dv are **identical**. y5 is identical wherever the saved panel is finite. 11946 cells, dated
  2025-12-23 to 12-31, are newly finite because their window runs into 2026. No saved name is missing.
  `y5_delist` (reported only by Amendment 4; H7 does not use it) differs in 94458 cells and becomes NaN in 49. The
  cause is symbol reuse: a few delisted tickers trade again in the 2026 fetch, so their "last bar" moves. Their old
  windows are then no longer counted as delistings, and the cross-sectional demeaning of those rows changes.
* **Coverage.** Exactly 1500 broad names are eligible on every 2026 Thursday; at least 488 S&P names are eligible.
* **Symbol reuse in 2026 (for the coordinator).** Nine names are eligible in 2026 although their earlier history ends
  long before 2025-12 (the eligibility history counts the old issuer's sessions): AKTS AYA HAWK JAN PS RVI LIME PPLC
  XE. This is the registered rule and is identical to how panel_broad behaves before 2026. None of the nine has a
  tree prediction in 2026, because Z (12-1 momentum) is NaN, so none can enter a book. They do take places in the
  top-1500 eligibility, in the dollar-volume terciles and in the demeaning of y5.

## Step 4: broad trees refit, training through 2025

* `finalists/D_hgb_mh/model.py` `fit_predict` is run through `harness.walk_forward(seeds=(0, 1, 2), years=(2026,))`,
  which rank-averages the seeds. `train_end = harness.train_end(D, 2026)` is row 2025-12-19, whose y5 ends at
  2025-12-30. walk_forward blanks y5 after it. The 3/10/20-session targets in X1 lib end at row te+6 or earlier,
  that is, before 2026. The 45 Thursdays of 2026 are predicted, with 1489 to 1494 broad names scored per Thursday.
* **Fidelity on spent data.** The 2025 refit on the extended panel reproduces the saved L3b read predictions
  (`read3_pred_L3b_candidate.npy`, 2025 rows). The NaN pattern is identical, the max abs difference is 3e-8 (float32
  storage) and the per-Thursday rank correlation is 0.99999998 (min 0.99999996).
* **Dollar-volume terciles per 2026 Thursday.** Each tercile holds at least 499 names.
* **Trees vs MASTER (predictions only).** On the S&P 500 names, the per-Thursday rank correlation between
  `trees_2026.npy` and `master_h5_2026.npy` averages 0.37 over the 45 Thursdays (min -0.03, max 0.66), on 484 to
  493 names. The first 850 columns of the broad panel are the S&P panel names in the same order, and both files
  have predictions on the same 45 rows.

## Step 5: weights (`research/tree/H7_WEIGHTS.json`)

* k_a = **0.59**, fixed by the registration. As a check, the same equal-risk rule at 14 bp on all eligible names
  gives 0.5924, against COMBO_CHECK's 0.5928 at 5 bp, 0.5926 at 10 bp and 0.5921 at 20 bp.
* k_b = **0.5307** = sd(weekly fund stock-book return) / sd(weekly broad-book net return at 14 bp, restricted each
  week to eligible broad names in dollar-volume terciles 2 and 3). The terciles rank the 63-session mean unadjusted
  dollar volume among eligible broad names that have one, as `read3.extras` does. The two series are inner-joined
  over 302 weeks, 2020-01-02 to 2025-12-11 (spent data): sd of the fund stock book 0.00918 and sd of the restricted
  broad book 0.01730 (0.01550 unrestricted). The functions are `combo_check.fund_weekly()` (`wk_book`), M1
  `build("decile")`/`simulate` with `M1.COST = 14e-4`, y5 clipped at ±1, weeks with at least 50 names, and the L3b
  candidate predictions.

## Before scoring, the coordinator must know

1. Use `broad_panel.npz` names and `isb` to align `trees_2026.npy`, and `sp_panel.npz` names to align
   `master_h5_2026.npy`. The broad column order differs from `panel_broad.build`'s sorted order.
2. The fund side needs the fund construction (`research/sharpe/construct.py` via oos_returns) on `sp_panel.npz` or
   `sp500_close_ext.parquet`. That construction was not built here. It needs the T-bill rate for 2026 (`K.ST.dtb3()`),
   frozen at first use per CLAUDE.md rule 4. It also needs the 200-session core on the extended SPY.
3. Ten 2026 members have no prices (unanchored, as in 2009-2025), and sixteen members are not panel columns.
4. Nine broad symbol-reuse names are eligible without predictions (step 3).
5. The scored weeks are those with a complete 5-session target by 2026-11-12. The last rows have NaN y5 by
   construction.
