# Pre-registration: quant trials Stage 2, news-embedding signals (DRAFT, not signed)

**Status:** draft. Nothing is frozen until the owner signs it off and the commit is pushed. `confirm.py` refuses
to run until then.

**Dated:** 2026-10-16.

**What has been seen.** No result for any session in 2022–2025 has been seen:
- Every Stage-1 prediction and metric covers test years 2018–2021 only (`trials.csv`: max fold 2021).
- Prices and text through 2025-12-31 were loaded to compute features, but nothing in 2022–25 was predicted or
  scored.
- Jan–Sep 2026 (the sealed P8 holdout) is never loaded; the panel cuts at 2025-12-31.

**Stage-1 search size.** 370 configurations and 904 fold runs, all in `reports/research/quant_trials/trials.csv`.
The winner below was picked from that many tries. That's why this read uses a Holm correction and requires sign
stability, and why Stage-1 t-statistics are not quoted as evidence.

## 1. What Stage 1 found (why these candidates)
- **Text adds information at 5–60 sessions and none at 1 session.** The text arm is a decayed headline state,
  half-life 5 sessions, scored as cosine similarities to 16 k-means topic prototypes fit on the training window.
  The increment is +0.03 to +0.10 IC over a price-only twin and over a shuffled-text placebo, but no single
  configuration reaches t ≥ 2.
- **Regularised models win.** Ridge is about equal to a kernel with a sensible bandwidth; trees are better at
  long horizons. Deep nets (MLP, the paper's transformer, the angular CSHT-style transformer, cross-firm attention)
  add nothing. Random features at the literature's bandwidth (γ = 2) are degenerate on 28 inputs.
- **COVID critique (owner's request):**
  - Most of the 2020 gain disappears sector-neutral: it was sector rotation.
  - Trained without 2020, the increment in 2021 turns negative at h ≥ 20.
  - Pre-COVID test years 2018 and 2019 are small positives for the ridge candidate.
  - 2022 (the reversal of the COVID trades) is therefore the decisive year, and gets its own rule.

## 2. Frozen candidates
The primary family is Q1–Q3 and gets the Holm correction. The secondary rows are descriptive only. They answer
whether leaving COVID out of training helps after the regime change.

```json
{
  "candidates": [
    {"id": "Q1", "family": "primary", "arm": "proto_hl5", "model": "ridge", "h": 10, "placebo": false},
    {"id": "Q2", "family": "primary", "arm": "proto_hl5", "model": "ridge", "h": 20, "placebo": false},
    {"id": "Q3", "family": "primary", "arm": "proto_hl5", "model": "gbrt", "h": 40, "placebo": false, "seeds": 5},
    {"id": "Q1x", "family": "secondary", "arm": "proto_hl5", "model": "ridge", "h": 10, "placebo": false,
     "variant": "exCOVIDtrain", "train_exclude": ["2020-01-01", "2020-12-31"]},
    {"id": "Q2x", "family": "secondary", "arm": "proto_hl5", "model": "ridge", "h": 20, "placebo": false,
     "variant": "exCOVIDtrain", "train_exclude": ["2020-01-01", "2020-12-31"]},
    {"id": "Q3x", "family": "secondary", "arm": "proto_hl5", "model": "gbrt", "h": 40, "placebo": false,
     "seeds": 5, "variant": "exCOVIDtrain", "train_exclude": ["2020-01-01", "2020-12-31"]}
  ]
}
```

**Q3 is flagged as high-risk.** It was the strongest Stage-1 result, but it leans most on 2020 and failed the
trained-without-2020 test.

**Everything else is fixed at this commit's code** (`research/quant_trials/`):
- the 31 names;
- the features;
- the target: residual return from close(d+1) to close(d+1+h), cross-sectionally demeaned;
- the encoders (16 prototypes, seed 0);
- the model settings (ridge α chosen on the last 20% of each training window; trees depth 3, learning rate 0.03,
  early stopping).

## 3. Fitting
- For each Y in 2022, 2023, 2024, 2025: train on 2016-01-04 .. Y−1, with an h-session embargo; predict year Y.
  Test decisions are kept only when their whole target window lies inside Y.
- Each candidate is fitted together with its price-only twin (same model, text removed) and its placebo (text
  shuffled across names within each date).

## 4. Statistics and pass rule (primary family)
All IC statistics use weekly (Thursday) cross-sectional Spearman IC.

**Primary statistic:** the weekly IC difference, candidate minus price-only twin, pooled over 2022–2025. Its
Newey–West t uses lag ⌈h/5⌉, with a one-sided p.

A candidate **passes** only if all of the following hold:
1. Holm-adjusted p < 0.05 within Q1–Q3.
2. Mean increment > 0 in 2022–23 **and** in 2024–25.
3. **Mean increment ≥ 0 in 2022 alone** (the regime-reversal year).
4. Pooled increment over the placebo > 0.
5. Mean weekly long-short tercile spread > 0, net of 5 bp per unit one-way turnover. The portfolio is rebalanced
   weekly and held one week.

**Classification**, reported for every candidate: **firm-level** if the sector-neutral increment is > 0, otherwise
**sector-rotation**. This doesn't change pass/fail. It decides what kind of input the signal could become
(P8 firm thesis vs a sector tilt).

**Also reported:** per-year increments, sector-neutral t, and the secondary rows.

## 5. After the read
- The read is made once (`python research/quant_trials/confirm.py`). The script refuses a second run.
- Results are written to `reports/research/quant_trials/CONFIRM.md` whatever they are.
- No re-tuning on 2022–25.
- If nothing passes, the quant-desk idea is closed for this panel. Any new idea needs new data, or forward
  evidence from live headlines.
- If something passes, the decision memo lays out the options (no desk / P8 input / shadow desk) for the owner.

**Owner sign-off:** _pending_
