# Q7_features: industry-relative and announcement-aware reversal (Layer 3, Amendment 8)

*Written by the branch agent; saved by the coordinating session because the agent's writes were refused.
**Development results only** (S&P 500 2013-2019, `harness.load()`); not out of sample. Survivorship gap: 241 of 738
names unpriced; 23.5% of eligible name-weeks without a target. Every configuration declared before scoring; seeds
0-2; walk-forward 2013-2019, 353 weeks.*

**Verdict: none of the three configurations adds anything once the coverage leak is removed.**
* **F1** (feature set on the 5-session D trees): −0.0009 vs control (t −0.42).
* **F2** (the set on the multi-horizon target): highest IC (0.0246), but +0.0010 over its own reference D_hgb_mh
  (t 0.71). On names with a GICS code the gain reverses (−0.0009, 1 of 7 years positive). The declared rule
  attributes it to the coverage leak.
* **H1** (horizon by volume tercile): −0.0017 (t −0.72). Its proxy is share volume, not turnover, so H1 does not
  cleanly test the registered idea.

D_hgb_mh stays the reference.

## 1. Data-source audit (CLAUDE.md rules 1-4)

| Input | Source and typed field | Coverage (vs expected) | Point-in-time status |
|---|---|---|---|
| Industry / sector | `.cache/p8/gics.json` (`research/p8/gics.py`): GICS sub-industry *name* from Wikipedia's current S&P 500/400 lists (`data/raw/stocks/sp{500,400}_current.csv`, fetched 2026-10-14), exact-matched to Wikipedia's 8-digit codes; fields `firms[t].industry_code` (6 digits, 69 industries) and `firms[t].sector` (11); 902 firms, 0 unmatched | 434 of 666 eligible names; 71.4% of eligible name-weeks (66.4% in 2013 → 77.9% in 2019). The other 232 (e.g. AABA, AET, BK, AVB, CAG) left both lists by 2026: a typed defect, features missing → 0 | **Look-ahead**: today's classification on 2013-2019, and coverage depends on surviving to 2026. **The has-GICS indicator alone has weekly IC with y5 of +0.0149 (t 3.85)**: coverage carries future information. Hence the declared covered-subset diagnostic |
| Announcement dates | `.cache/p8/decay_earnings_events.parquet` (`research/p8/decay_earnings.py`): quarterly diluted EPS from first-filed XBRL, matched to the first SEC 8-K item 2.02 accepted 1-100 days after quarter end; `t0` = reaction session (after 16:00 ET → next session). Only `ticker`, `t0` read (t0 ≤ 2019-12-31); outcome columns never read | 77% of event tickers are panel names; 70.0% of eligible name-quarters have an event (61% in 2013 → 79% in 2019); 193 eligible names have none (events only where SUE was computable and the ticker was in the P8 price set). emask5 NaN (→ 0) where no event in the previous 126 sessions | Known at t0's close. Coverage not survivorship-informative (indicator IC +0.0016, t 0.57) |
| Share volume (H1) | `harness.load_extra("finra")["total"]`: FINRA Reg SHO (off-exchange/TRF), not consolidated | 95.0% (2013) → 99.6% (2019) of eligible name-days; no zeros; names without a 63-session mean get h 5 (3.1% of name-weeks) | Causal. **Proxy defect**: no shares outstanding, so share volume, not turnover. Where XBRL `shares_0` exists (53.5% of name-days), Spearman of log volume with log(volume/shares) is 0.31; terciles agree on 43% of names (33% chance) |

Frozen at first use: `model.load_inputs` checks sha256 (`gics.json` daba07b7…cfb2c; events a7831d1d…eed0;
`extra_finra.npz` b5f8a54d…e3713; `dev.npz` b37cb691…aa9c9). Content check (rule 11): AAPL 2015-01-08 leave-one-out
industry arithmetic checked by hand (mates HPQ, NTAP, SNDK, STX, WDC), exact; added features cover 70-71% of eligible
name-weeks; Spearman with the plain 5-day residual return: irel_e5 0.73, emask5 0.95, imom5 0.39.

## 2. Configurations

* **ref_control**: `D_ensembles/model.py` (reproduces 0.021598). **ref_mh**: `finalists/D_hgb_mh` (reproduces 0.023568).
* **F1**: D trees + 9 ranked inputs: industry-relative 1/5/21-day reversal on r and on e (stock minus the leave-one-out
  equal-weight mean of eligible names in its GICS industry; sector mean if fewer than 3), 5- and 21-day leave-one-out
  industry momentum, 5-day residual reversal with t0 and t0+1 set to 0.
* **F2**: F1's inputs on the 3/5/10/20-session target, rank-averaged.
* **H1**: D's inputs; horizon by volume tercile (low → 20, mid → 10, high → 5); target = cross-sectional rank of the
  own-horizon return.

## 3. Results

| Config | IC | t | years > 0 | min year | decile net %/yr (Sharpe) | vs ref_control Δ IC (NW t), years Δ > 0 | rank corr with ref_control |
|---|---:|---:|---:|---:|---:|---|---:|
| ref_control | 0.0216 | 2.30 | 6/7 | −0.0155 | 0.38 (0.05) | n/a | n/a |
| ref_mh | 0.0236 | 2.41 | 6/7 | −0.0166 | 1.04 (0.15) | +0.0020 (0.93), 3/7 | 0.92 |
| F1 | 0.0207 | 2.19 | 6/7 | −0.0116 | 1.40 (0.21) | −0.0009 (−0.42), 4/7 | 0.91 |
| **F2** (best by rule) | **0.0246** | 2.54 | 6/7 | −0.0172 | 1.39 (0.21) | +0.0030 (1.17), 4/7 | 0.88 |
| H1 | 0.0199 | 2.32 | 6/7 | −0.0079 | 0.43 (0.07) | −0.0017 (−0.72), 2/7 | 0.88 |

F2 vs ref_mh: +0.0010 (t 0.71), 3 of 7 years, rank correlation 0.95.

**Leak diagnostic (a), declared**: both restricted to GICS-covered names (reference ICs rise there: ref_control
0.0230, ref_mh 0.0253, consistent with the has-GICS indicator predicting returns).

| Comparison | Full panel | GICS-covered only | Rule (gain matched ≥ half?) |
|---|---|---|---|
| F1 vs ref_control | −0.0009 (t −0.42) | −0.0025 (t −1.18), 4/7 | no gain to attribute |
| F2 vs ref_control | +0.0030 (t 1.17) | +0.0015 (t 0.59), 4/7 | exactly half (from the multi-horizon target, not the set) |
| **F2 vs ref_mh** (isolates the set) | +0.0010 (t 0.71) | **−0.0009 (t −0.61), 1/7** | **not matched → coverage leak** |

**Permutation importance (b)** (F1, seed-0 models, validation Thursdays; `IMPORTANCE.json`): shuffling all 9 added
inputs lowers IC by 0.0007 on average (4 of 7 years); no single input matters consistently (imom21 +0.0005, 2/7,
driven by 2019; irel_r5 +0.0005, 5/7; imom5 −0.0012). In 6 of 7 years the model selected the minimum 50 trees.

**H1 (c)**: smaller drawdown year (2016 −0.0079 vs −0.0155) but lower in 5 of 7 years; uninformative about the
turnover mechanism because the proxy is share volume.

## 4. Reading

* Industry-relative reversal, short-run industry momentum and earnings-masked reversal add nothing to the D trees on
  large caps at a weekly horizon; the trees already see e1/e5/e21 and r5/r21 (correlations 0.7-0.95 with the new
  inputs). Literature effects are from broad CRSP samples with monthly sorts.
* `model.py` holds F2 (the branch rule; `VERIFY.json` reproduces IC 0.024577 exactly), but its gain fails the declared
  leak check: it should **not** replace D_hgb_mh.
* H1 untested in its registered form: needs shares outstanding (a new typed input). A point-in-time sector map (SEC
  submissions `sic` in `.cache/p8/edgar/submissions`) would remove the GICS look-ahead. Both would be amendments; not
  run.

Files: `model.py` (`make(name)`; `fit_predict` = F2), `run.py`, `importance.py`, `IMPORTANCE.json`, `VERIFY.json`,
`RESULTS.jsonl`, `STATE.json`, `run.log`. Predictions: `.cache/tree/preds/Q7_features/{ref_control,ref_mh,F1,F2,H1}.npy`.
