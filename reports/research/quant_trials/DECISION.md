# Quant trials · decision memo (2026-10-16)

**Question (owner, 2026-10-15).** Can a quant department turn our Gemini headline embeddings into return signals,
using the ideas in 2605.30652 (FinBERT/Siamese + transformer) and 2510.04357 (CSHT), with networks trained
locally on longer horizons?

**Answer: no desk.** No pre-registered candidate passed the one 2022–2025 read (`CONFIRM.md`, pre-registration
commit 8de9271). Under the pre-registration's own rule, the idea is closed for this panel. A new attempt needs new
data, or forward evidence from live headlines.

## What was tested
- **Panel:** the owner's thesis data. 31 large caps, 2016–2025; LLM-cleaned headlines embedded with
  gemini-embedding-001, mapped to NYSE sessions.
- **Target:** residual returns from close(d+1).
- **Exploration:** 370 configurations on test years 2018–2021 (`trials.csv`, `TRIALS.md`).
- **The two papers:**
  - 2605.30652's headline is an artefact. On our data, persistence scores R² 0.94–0.99 on its price-level
    target. Its transformer gets 43–48% direction and loses to buy-and-hold. Its Siamese head is at chance
    (AUC 0.50–0.52).
  - CSHT's reported MAE equals a zero forecast. Its Granger hypergraph is almost empty on our names: 0–7 of 930
    pairs pass FDR.
- **Models:** ridge, gradient-boosted trees, random-feature kernel ridge, MLP, the paper's transformer, an angular
  (CSHT) transformer, and cross-firm attention with own / sector / Granger / random masks.
  - Exploration ranking: trees > ridge ≈ kernel (with a sensible bandwidth) > deep nets.
  - The literature's kernel bandwidth was degenerate on 28 inputs.
- **Horizons:** 1, 3, 5, 10, 20, 40, 60 sessions. Text added nothing at 1 day and grew with horizon in
  2018–2021.
- **COVID critique (owner):**
  - The 2020 gain was mostly sector rotation; it vanishes sector-neutral.
  - Trained without 2020, the 2021 gain turned negative at h ≥ 20.

## The confirmation read (2022–2025, one read)
Δ is the text model's IC minus the IC of its price-only twin.

| | Q1 ridge h10 | Q2 ridge h20 | Q3 trees h40 |
|---|---|---|---|
| Δ IC, pooled (NW t) | +0.006 (0.33) | −0.020 (−0.81) | −0.067 (−1.88) |
| Δ in 2022 / 2023 / 2024 / 2025 | −0.068 / +0.015 / +0.032 / +0.048 | −0.121 / +0.013 / +0.004 / +0.024 | −0.158 / −0.091 / +0.014 / −0.033 |
| Δ IC vs placebo | +0.009 | −0.017 | −0.051 |
| Sector-neutral Δ IC (t) | +0.021 (1.73) | +0.008 (0.54) | −0.003 (−0.09) |
| Holm p | 1.0 | 1.0 | 1.0 |
| **Pass** | no | no | no |

- **2022 broke every candidate,** as the owner expected: the COVID-era text patterns reversed.
- **The strongest exploration result failed hardest.** Q3 (trees, h40) leaned most on 2020; in 2022 it lost
  −0.16 IC against its twin.
- **Training without 2020 (Q1x–Q3x, descriptive)** halves the 2022 damage, but the overall increment is ≈ 0.
- **One residual, recorded for what it's worth.** Q1 (ridge, h10) has a small, sector-neutral increment
  (+0.021, t 1.73) and recovered in 2023–25 (+0.015 / +0.032 / +0.048). It is not significant; it failed the
  pre-registered tests and is not a result. If anything is revisited, it is this, and only with forward data from
  live headlines.

## Operational notes
- During the read, `confirm.py` crashed in the net-spread scorer, on a week where all predictions were tied.
  - It crashed before any statistic was computed; the raw per-year ICs had already been printed to the log.
  - Fix: an empty tercile leg holds no position. Fitted predictions were reused; nothing was refit.
  - Disclosed in `NOTES.log`, commit 9cdccc8.
- Nothing in `fund/`, the runner or Protocol 7 was touched. The sealed P8 window (Jan–Sep 2026) was never loaded.
