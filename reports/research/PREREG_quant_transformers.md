# Pre-registration: three off-the-shelf transformers on the S&P 500, then forward on factors + news (DRAFT, not signed)

**Status:** draft. `research/quant_trials/sp500_transformers.py run` refuses to score anything until the owner
signs this off and the commit is pushed. Before sign-off only the smoke check below may run.

**Dated:** 2026-10-19.

## Why
The owner asked for transformer models from the literature and GitHub, tested on factors + news at 5, 10 and 20
sessions. The goal is always to beat buy-and-hold of the S&P 500.

**What we already know.**
* On the 31-name news panel, the quant trials ranked deep nets last: trees > ridge ≈ kernel > deep nets
  (`reports/research/quant_trials/DECISION.md`). No text model passed the 2022–25 read.
* Qlib's public benchmark (CSI300, Alpha158) shows the same: vanilla Transformer IC 0.026, Linear 0.040,
  LightGBM 0.045.

So no transformer reaches the forward books on the 31 names unless it first beats ridge on the S&P 500, where a
test has power. The 31-name panel has no clean history left:
* 2018–21 was explored;
* 2022–25 was read;
* Jan–Sep 2026 is the sealed P8 holdout.

## Models (ready code, pinned)
| | Model | Code (pinned) | How it is used |
|---|---|---|---|
| M1 | **MASTER** (Li et al., AAAI 2024, arXiv 2312.15235) | `SJTU-DMTai/MASTER` @ `de8f585`, MIT, vendored unchanged (`master.py`) | cross-sectional ranker, trained |
| M2 | **Temporal Fusion Transformer** (Lim et al. 2021) | `darts` `TFTModel` (Apache-2.0), pinned in `requirements-quant.txt` | global multi-series forecaster, trained |
| M3 | **Chronos-2** (Ansari et al. 2025, arXiv 2510.15821) | `chronos-forecasting` `Chronos2Pipeline`, weights `amazon/chronos-2` (Apache-2.0) | pretrained, zero-shot, no training |

**Why darts and not neuralforecast for TFT.** Darts takes per-row sample weights. That lets training count only
rows where the name was an index member that day, as the ridge test does. Neuralforecast has no such mask.

## Data
**Inputs taken verbatim from `PREREG_quant_sp500.md`** (the ridge test, drafted 2026-10-17):
* universe;
* prices;
* the five signals, z-scored across eligible members per session;
* residual target: r − β·r_SPY from close(d+1), with the shrunk Welch β over 252 sessions to d, cross-sectionally
  demeaned;
* coverage reporting;
* no data after 2025-12-31; Jan–Sep 2026 is never loaded.

**Additions:**
* Horizons h ∈ {5, 10, 20}.
* Decisions are Thursdays, as in the ridge test.
* A model's score at d uses only closes ≤ d.

**Inputs per model:**
* **M1 MASTER.** For each eligible name: the last 8 sessions of the five z-scored signals.
  * Market vector at d, from SPY only (the paper's index features, without volume): the mean and std of daily SPY
    returns over 5/10/20/30/60 sessions, and SPY close ÷ its 5/10/20/30/60-session average − 1 (15 values).
  * One training batch is one session's eligible cross-section, as in the paper.
  * Labels: the paper's drop-extreme (2.5% each tail) and cross-sectional z-score, MSE loss, Adam.
  * Settings from the official `main.py`: lr 1e-5, 4 temporal and 2 cross-stock heads, dropout 0.5, and the
    paper's stop rule (train loss < 0.95) with at most 40 epochs. The epoch kept is the one with the best
    validation rank IC.
* **M2 TFT.**
  * Target series per name: the daily residual return.
  * Past covariates: the five z-signals.
  * Static covariate: GICS sector.
  * Input length 60; output length h + 1. Score = the sum of the median forecasts for steps 2 … h + 1, the target
    window.
  * Sample weight 1 on eligible member days, 0 otherwise.
  * Default quantile loss; stride 5.
* **M3 Chronos-2.**
  * Context: each eligible name's last 512 daily residual returns.
  * Past covariates: the five z-signals.
  * `cross_learning=True` in groups of about 100 names, the group size of the Chronos-2 technical report and the
    pipeline's guidance. Names are ordered by GICS sector, then ticker, so each group is sector-coherent; the call
    batch is 600 series (100 targets × 6 series each). Prediction length 21.
  * Score at h = the sum of median forecasts for steps 2 … h + 1. One forecast serves all three horizons.

## Fitting
* **Annual expanding refits.** Training starts 2010-01-04. Test years 2013–2025 are each predicted by a model
  trained on rows whose target ends before 1 January of that year (h-session embargo).
* **Tuning by rank IC, never MSE** (the quant trials' lesson).
  * Settings are chosen by mean weekly rank IC on the last 20% of the training window, at the **first refit only**
    (test year 2013), then frozen for every later refit. This bounds compute.
  * Grids:
    * M1: d_model ∈ {64, 256} × gate temperature β ∈ {2, 5} (the paper's two values).
    * M2: hidden size ∈ {16, 64} × epochs ∈ {5, 15}.
    * M3: none.
* **Seeds.** M1 averages 3 seeds per refit; M2 uses 1 seed per refit. These are fixed now and not changed after
  the smoke check.
* **Comparator.** A ridge on the same five signals, refit annually on the same windows, with α chosen by
  validation rank IC (grid 1e-2 … 1e5), at each h.

## Hypotheses (one read, 9 tests, Holm at 0.05)
For each model M ∈ {M1, M2, M3} and each h ∈ {5, 10, 20}:

**H(M, h).** M's mean weekly cross-sectional Spearman IC with the h-session residual return, pooled over
2013–2025, is > 0. This is a one-sided Newey–West test (lag 4).

**Pass** only if all of these hold:
1. Holm-adjusted p < 0.05 across the 9;
2. mean IC > the annual ridge's mean IC at the same h, on the same decisions;
3. mean IC > 0 in both 2013–2019 and 2020–2025;
4. mean IC ≥ 0 in 2022;
5. the weekly long-short decile spread on the 5-session residual return from close(d+1), held one week, is > 0
   net of 10 bp per unit of one-way turnover.

**Secondary (descriptive):**
* per-year tables;
* sector-neutral IC;
* 2022–25 alone;
* for M2, the TFT variable-selection weights;
* runtime.

## After the read
* The results go to `reports/research/quant_trials/SP500_TRANSFORMERS.md` whatever they are, and the read is
  never repeated.
* **Forward books (31-name news panel).** Each model with at least one passing horizon gets **one** forward
  research book, at its passing horizon with the highest IC.
  * Inputs: the five factors + the 16-dimensional news state of `fund/qshadow.py`, refit quarterly.
  * Its no-news twin is stored in each record.
  * Scored in `fund/qshadow.py` like the ridge books, including the market exposure lines (PROTOCOL_fund.md
    "Market exposure"): + S&P, + the 1.3x / 0.7x dynamic sleeve, against SPY and a risk-matched SPY. Every book
    is long/short.
  * **Interim at about 25 forward weeks (April 2027): a stop rule only.** Stop the book if its mean Δ IC against
    the same-horizon ridge book is < 0 with NW t < −1.
  * **Verdict at 52 forward weeks (October 2027).** All three must hold:
    1. Δ IC vs the ridge book > 0 (one-sided p < 0.05);
    2. Δ IC vs its no-news twin > 0;
    3. the book + the dynamic sleeve beats the risk-matched S&P.
* **If nothing passes,** no forward book is built and the transformer arm is closed for this universe.
* Never traded. Records go to `research-data`.

## Smoke check (allowed before sign-off; no test-year score)
* Run the first refit only (training through 2012, its validation slice inside the training window) for M1 and M2.
* Run M3 on 10 Thursdays of 2012.
* Report runtimes and shapes, and inspect a sample of scores next to their inputs.
* No 2013–2025 prediction is scored before sign-off.

**Owner sign-off:** _pending_
