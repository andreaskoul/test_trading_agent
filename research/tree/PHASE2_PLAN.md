# Tree search, phase 2: plan

*2026-11-12, after the phase-1 holdout read. Plan only: nothing here has run.*

## What phase 1 settled

* The S&P 500 daily price panel 2009–2025 is spent for stock selection. 114 configurations; no finalist passed; the
  development leads over MASTER reversed on the holdout.
* Whole-fund returns 2020–2025 (`OOS_RETURNS.json`, descriptive; 200-session core + decile book, 5 bp a side):

| | book gross 0.6 | book gross 1.0 |
|---|---|---|
| MASTER 5-day | 21.7%/yr, Sharpe 0.94 | 25.3%/yr, Sharpe 0.98 |
| Search's best (X1_8p) | 15.8%/yr, 0.75 | 15.3%/yr, 0.70 |
| Core only | 16.1%/yr, 0.79 | |
| S&P buy and hold | 15.0%/yr | |

  Only MASTER adds to the core. The search models subtract from it at 5 bp. Score smoothing helped X1 and *lowered*
  MASTER (21.7 to 20.7 at 0.6), so it is not a general fix.
* Network design, regime adaptation and weekly refitting added nothing. Inputs and the cost of trading did matter.

## The rule for phase 2

Gains can now come only from **information the panel does not contain**. Each branch adds new inputs to a **frozen
base** and is judged on the **increment** over that base:

* Base: the MASTER 5-day scores as already computed (no refit). The base's 2020–2025 performance is known; the
  relation of the new inputs to 2020–2025 returns is not, so the increment test is clean.
* Development 2013–2019 (gate: increment t ≥ 1.5); one read 2020–2025 per branch's finalist, Holm across branches.
* A pass earns a forward paper book. Forward weeks from 2026-11 are the only fully clean confirmation.

## Branches

| | Branch | New information | Why it can work | Cost |
|---|---|---|---|---|
| N1 | Fundamentals | SEC XBRL company facts (free): profitability, accruals, asset growth, investment; earnings surprise (already in `events.parquet`) | Slow signals with documented premia; low turnover, so they survive costs where price signals did not | No LLM; one bulk download |
| N2 | Short interest and flows | FINRA daily short volume (cached; F2 passed alone), as a feature in the base | The one validated non-price signal, never combined with MASTER | None |
| N3 | Intraday | 30-minute bars (cached, 2016–2025): overnight vs. intraday returns, closing-auction moves | Overnight/intraday return split is a documented, separate effect | None; survivorship disclosed |
| N4 | News | Alpaca/Benzinga headlines (from 2015, every member): counts, novelty, a dictionary tone; embeddings only if the cheap features pass | The fund's own thesis that news matters, tested at index scale for the first time | Dictionary: none. Embeddings: estimate before running |
| X | Combination | The passing branches' features in one model on top of MASTER | Breadth: independent signals add | After N1–N4 |
| P | Fund level | The validated sleeves together: core, MASTER book, F2 book, momentum-panic switch; sizing by the rule in the 21 Nov study | Sharpe rises with uncorrelated sleeves even if none improves | Descriptive on seen data; forward only |

Order: N2 and N3 first (data on disk, a day each), then N1, then N4, then X and P.

## Track M: models and econometrics (added 2026-11-12, owner)

**The sample problem, and the answer.** A new method tested again on the S&P 500 2020–2025 would be scored on spent
data. A fresh sample exists: **the S&P 400**, 390 current members with daily closes 2016–2025 (`.cache/p8`). No
stock-selection model in this project has been scored on it (P8's H1 earnings-sympathy test used it for a different
hypothesis; disclosed). Survivorship: current members only, disclosed; it matters less for cross-sectional rank IC.

* Develop on the S&P 500, 2013–2019, as in phase 1.
* Confirm once on the S&P 400, 2019–2025: each model trained on S&P 500 data up to year y − 1 and applied to the
  S&P 400 in year y (a transfer test of the method, not of fitted luck). Within-400 walk-forward reported beside it.
* The bar is the phase-1 best (X1_8p, frozen) run on the same S&P 400 weeks, and the decile book after costs.

| | Method | What it adds over phase 1 | Literature (from memory, to be checked) |
|---|---|---|---|
| M1 | **Dynamic trading with costs** | Trades a fraction of the way toward an aim portfolio each week, the fraction set by the signal's decay and the cost; the principled form of the smoothing that helped one model and hurt another. Applies to MASTER too | Gârleanu and Pedersen 2013 |
| M2 | **Instrumented PCA** | Betas and alphas as linear functions of characteristics, estimated jointly; separates compensated risk from mispricing | Kelly, Pruitt and Su 2019 |
| M3 | **Conditional autoencoder** | The neural version of M2: characteristics map to betas through a network, factors from returns | Gu, Kelly and Xiu 2021 |
| M4 | **Shrinkage of the stochastic discount factor** | A ridge-type prior on characteristic-based portfolio weights, chosen by cross-validated pricing error, not by return | Kozak, Nagel and Santosh 2020 |
| M5 | **Peer graph network** | Each stock's score uses its 10-K text neighbours' features (neighbours already cached in `research/riskfield`); the owner's thesis-tree idea in learnable form | graph networks for stock prediction (survey to be read) |
| M6 | **Self-supervised return embeddings** | Representations of return windows learned without labels (the owner's Stock2Vec), used as features | contrastive learning for time series |
| M7 | **Double machine learning** | For tracks N1–N4: the increment of a new input estimated after flexibly partialling out the price features, so a new signal is not credited for a tilt the base already has | Chernozhukov et al. 2018 |
| M8 | **Covariance for the book** | Nonlinear shrinkage covariance in M1's optimiser; phase-1 linear shrinkage with mean-variance weights lost to equal weights | Ledoit and Wolf 2020 |

**Deprioritised, with reason:** time-varying coefficients by Kalman filter and other online schemes (X3: refitting
inside the year did not help); deeper or attention-based tabular networks (B: no gain over a small MLP); hidden-Markov
regimes (failed in `research/regime`).

**Order:** M1 first (it acts on the cost problem that decided phase 1, and can be applied to MASTER immediately), then
M2 and M3 (the two leading academic models, built for this exact task), M4, then M5 and M6. M7 is used inside N1–N4.

## Guards carried over

* One development file per branch that ends in 2019; holdout code runs only in the coordinating session.
* Every configuration logged; the count is reported with the result.
* Agents write `model.py` and their report early: the account's usage limits stopped agents four times in phase 1.
* Each agent gets its own worktree.
