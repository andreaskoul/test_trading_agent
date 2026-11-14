# N4_news: Benzinga headline features on top of MASTER (development 2016-2019, 202 weeks; 2026-11-14)

*Written by the branch agent; saved by the coordinating session because subagent report writes are refused.*

**Development results only, not out of sample.** S&P 500 development panel (`harness.load()`). Headlines with
`created_at` <= 2019-12-31 only (filter applied at load and asserted; no 2020+ file opened).
* The archive starts 2015-01-01, so only **4 validation years (2016-2019)** are scored, training from 2015. Declared
  before scoring: the ">= 5 of 7 years" rule becomes ">= 3 of 4".
* Development survivorship gap: 241 of 738 names unpriced; 23.5% of eligible name-weeks without a target.
* All configurations planned in `STATE.json` before scoring; seeds 0-2 where stochastic; predictions in
  `.cache/tree/preds/N4_news/`, rows in `RESULTS.jsonl`.

**Verdict: no news configuration adds to MASTER, and none meets the selection rule (positive in >= 3 of 4 years).**
* Best mean increment: c6 (tone x novelty blend) +0.0007 (t 0.43), positive in 1 of 4 years.
* Fitted models subtract: Fama-MacBeth -0.0130, trees -0.0126.
* News added to the D trees lowers their IC by 0.0071 (t -1.12).
* Double ML: tone theta +0.005 (t 0.93), tone x novelty +0.006 (t 1.10); neither significant, both carried by 2017.
* Shrunk increment over the 6 news configurations: -0.0040. N4 nominates no candidate.

## 1. Data audit (`audit.py` -> `AUDIT.json`)

* Source: `.cache/tree/news/<TICKER>.parquet`, Alpaca news API fields `id, created_at, symbols, headline`
  (`fetch_news.py`; frozen at first use). All 850 panel names have a file. Headlines only (no summaries); `source`
  blank on almost every row.
* Headlines per eligible name-year (probe expectation: median 57): 2015 median 65 (15 of 529 names with zero);
  2016 68 (13/533); 2017 57 (6/533); 2018 71 (1/529); 2019 66 (1/533).
* Share of eligible Thursday name-weeks with a headline in the prior 21 sessions: 0.89 / 0.89 / 0.88 / 0.92 / 0.90
  (2015-2019); prior 5 sessions about 0.55. By dollar-volume tercile 0.81 / 0.91 / 0.98. Name-weeks without a target
  equally covered (2019: 0.896 vs 0.901).
* Survival: 132 names that left before end-2019 have *more* headlines per eligible year than the 505 stayers (median
  103 vs 77). Coverage does not depend on survival the way GICS coverage did.
* **Availability check:** has-news (21 sessions) indicator IC with y5 **+0.0053, NW t 1.29**; by year +0.015 / -0.001
  / +0.018 / -0.011. 5-session indicator -0.0027 (t -0.56). Covered-subset diagnostic still run for every comparison.
* Content check: KO 2019-04-23, FB 2018-07-26, AZO 2017-05-25 checked headline by headline; counts, tone, roundup
  share and days-since-last correct. Multi-symbol roundups excluded from tone.
* **Tone lexicon:** Loughran-McDonald not obtainable offline; a small documented hand list (`lexicon.py`, about 90
  positive and 90 negative words, fixed before scoring). Known weak point ("Maintains Overweight, Lowers Price
  Target" scores 0).

## 2. Timing (`test_timing.py`, passed)

After 16:00:00 New York time, or on a non-session day, a headline belongs to the next session; features at Thursday
row t use sessions <= t. 8 assignment cases on the real calendar pass; headlines planted after Thursday's close leave
every feature at rows <= Thursday bit-identical. No early-close calendar (about 3 half-days a year).

## 3. Features (`features.py` -> `.cache/tree/extra_news_dev.npz`)

Counts over 1/5/21 sessions; abnormal count over 5/21 (log ratio to a 63-126-session baseline); novelty over 5/21;
multi-symbol share 21; hand-list tone 5/21; sessions since last headline (cap 252); has-news indicators 5/21. Ranked
across eligible names per session; NaN -> 0 with the missing state in the indicators.

## 4. Configurations (paired weekly IC increment over MASTER, NW t 4 lags; MASTER IC on these weeks 0.0045)

| Config | IC | Increment | t | 2016 / 17 / 18 / 19 | Years + | Corr. w. MASTER | Covered subset incr. (t), yrs + | Net %/yr (Sharpe) |
|---|---:|---:|---:|---|---:|---:|---|---:|
| c0 MASTER | 0.0045 | | | | | 1 | | -4.8 (-0.69) |
| c1 0.7 MASTER + 0.3 tone21 | 0.0041 | -0.0004 | -0.23 | -.0040/+.0055/-.0001/-.0031 | 1 | 0.94 | -0.0005 (-0.28), 2 | -5.2 (-0.77) |
| c2 Fama-MacBeth, MASTER + 13 news | -0.0085 | -0.0130 | -1.55 | +.0032/+.0054/-.0324/-.0291 | 2 | 0.44 | -0.0134 (-1.59), 2 | -7.6 (-1.61) |
| c3 trees, MASTER + 13 news | -0.0081 | -0.0126 | -1.50 | +.0016/+.0027/-.0356/-.0196 | 2 | 0.32 | -0.0108 (-1.18), 2 | -7.2 (-1.54) |
| ref_D D trees (control for c4) | 0.0123 | +0.0077 | 0.65 | +.0155/+.0141/+.0021/-.0012 | 3 | 0.42 | +0.0079 (0.66), 2 | -1.6 (-0.21) |
| c4 D trees + 13 news | 0.0051 | +0.0006 | 0.04 | -.0056/+.0156/-.0080/+.0004 | 2 | 0.35 | +0.0017 (0.12), 2 | -3.1 (-0.41) |
| c5 0.7 MASTER + 0.3 (e5 x abnormal attention) | 0.0051 | +0.0006 | 0.35 | +.0020/+.0015/-.0010/-.0000 | 2 | 0.92 | +0.0001 (0.06), 2 | -3.1 (-0.52) |
| c6 0.7 MASTER + 0.3 (tone5 x novelty5) | 0.0052 | +0.0007 | 0.43 | -.0003/+.0066/-.0029/-.0006 | 1 | 0.94 | +0.0009 (0.51), 2 | -5.8 (-0.89) |

c4 vs ref_D (same seeds and code; ref_D reproduces Q7 `ref_control` on these rows): **-0.0071 (t -1.12)**, 2 of 4
years; covered subset -0.0062 (t -0.96).

By size tercile (dollar-volume proxy; MASTER IC low/mid/high .0139 / .0012 / -.0001): nothing reaches t 2 positive;
fitted models lose most in the low tercile; c5 mid tercile +.0045 (t 1.58), 4 of 4 years, one cell of 18, a lead at
most.

Double ML (`dml.py`; partially linear, HGB nuisances on MASTER rank + D's 27 inputs, cross-fitted by year; 81,438
name-weeks): tone21 theta +0.0050 (t 0.93; -.002/+.013/+.001/+.009); c6 score +0.0057 (t 1.10;
+.003/+.018/-.004/+.006).

## 5. Selection and verdict

Rule: highest mean increment among news configurations positive in >= 3 of 4 years. None qualifies. Best by mean
increment regardless: c6, +0.0007 (t 0.43); `model.py` reproduces it (+0.000697; predictions match to 1.5e-08).
Development gate (t >= 1.5) not met. **No candidate.**

## 6. Caveats

Headlines only (about 60% multi-symbol roundups); hand-list tone (a Loughran-McDonald, FinBERT or LLM score is the
main untested variant); 4 validation years with thin training; weak MASTER base on these weeks; development
survivorship gap; no early-close calendar; size proxy is dollar volume. No read requested.

## Files

`research/tree/N4_news/`: `features.py`, `lexicon.py`, `test_timing.py`, `audit.py`, `lib.py`, `run.py`, `dml.py`,
`model.py`, `AUDIT.json`, `RESULTS.jsonl`, `STATE.json`, logs. Data and predictions: `.cache/tree/extra_news_dev.npz`,
`.cache/tree/preds/N4_news/{c0..c6,ref_D}.npy`.
