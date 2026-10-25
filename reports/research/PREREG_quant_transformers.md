# Pre-registration: three off-the-shelf transformers on the S&P 500, then forward on factors + news (signed 2026-10-20)

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
| M3-ft | **Chronos-2, fine-tuned** | the same pipeline's `fit` (full fine-tuning, library defaults) | refit annually on the training window |

**Compute is not a constraint (owner, 2026-10-20):** "the goal is a successful model; even 3 days of retraining a
year is fine". Every setting below is chosen for model quality, not runtime, and is fixed before any test-year
score exists.

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
    paper's stop rule (train loss < 0.95). Up to 100 epochs; training also stops after 15 epochs without a gain
    in validation rank IC, and the epoch kept is the one with the best validation rank IC. (In the smoke check the
    paper's stop rule never fired within 40 epochs, and the best epoch was often the 39th.)
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
* **M3-ft Chronos-2, fine-tuned.** At each annual refit, a fresh copy of `amazon/chronos-2` is fully fine-tuned with
  the pipeline's `fit`: every name's daily residual-return series with its five signals as past covariates, up to
  the refit point less 21 sessions. Non-member days are given as missing targets.
  * Library defaults (lr 1e-6), 2,000 steps, batch 64, context 512, prediction length 21.
  * Scoring is then as for M3.

## Fitting
* **Annual expanding refits.** Training starts 2010-01-04. Test years 2013–2025 are each predicted by a model
  trained on rows whose target ends before 1 January of that year (h-session embargo).
* **Tuning by rank IC, never MSE** (the quant trials' lesson).
  * Settings are chosen by mean weekly rank IC on the last 20% of the training window, at the **first refit only**
    (test year 2013), then frozen for every later refit. This bounds compute.
  * Grids:
    * M1: d_model ∈ {64, 256} × gate temperature β ∈ {2, 5} (the paper's two values).
    * M2: hidden size ∈ {16, 64} × epochs ∈ {5, 15, 30}.
    * M3 and M3-ft: none.
* **Seeds.** At every refit, M1 averages 5 seeds (the paper's `main.py` uses seeds 0–4) and M2 averages 3. The
  grid is searched with seed 0.
* **Execution.** The read runs as separate parts in parallel (`run ridge`, `run chronos2`, `run chronos2_ft`,
  `run master_h5` … `run tft_h20`). `score` combines them only when every part is saved under the same signed
  commit. The measured runtime is several days on the M4.
* **Comparator.** A ridge on the same five signals, refit annually on the same windows, with α chosen by
  validation rank IC (grid 1e-2 … 1e5), at each h.

## Hypotheses (one read, 12 tests, Holm at 0.05)
For each model M ∈ {M1, M2, M3, M3-ft} and each h ∈ {5, 10, 20}:

**H(M, h).** M's mean weekly cross-sectional Spearman IC with the h-session residual return, pooled over
2013–2025, is > 0. This is a one-sided Newey–West test (lag 4).

**Pass** only if all of these hold:
1. Holm-adjusted p < 0.05 across the 12;
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

**Owner sign-off:** signed by the owner in session, 2026-10-20 ("Signed"), before any test-year score.


## Amendment 1 (2026-10-23): costs measured in paper trading, written before any score

Written before `score` has run. No prediction of any part has been opened, and no 2013–25 IC has been computed.

**Why.** The owner asked that profitability be judged with the costs the paper account has actually shown.

**Measured costs.** From the paper account (`fund-data: fund_state/live/execution/fills.csv` and `activities.csv`,
1–22 October 2026; 118 filled orders, $347k traded):
* slippage against the official close: 0.8 bp, weighted by traded value (median 0.3 bp); 1 order in 10 was off by
  13.8 bp or more;
* regulatory fees: 0.08 bp of traded value;
* 11% of orders expired unfilled, all of them in week 1.

**Documented costs.** From Alpaca, the fund's broker
(https://docs.alpaca.markets/docs/margin-and-short-selling, read 2026-10-23):
* $0 locate and borrow fees on easy-to-borrow shorts, which are the only shorts Alpaca opens;
* margin interest of 6.50% a year (non-elite tier) on the settlement-date debit balance, on an actual/360 basis.

Paper fills have no market impact, so the measured slippage is a lower bound.

**What changes.**
1. **Pass rule 5 is unchanged at 10 bp per unit of one-way turnover.** That is about 12× the measured cost and
   leaves room for real fills being worse than paper ones.
2. **New descriptive lines** (no pass/fail): the net decile spread at 1 bp (measured) and at 20 bp (stress).
3. **The decile long-short portfolio pays no margin interest.** Its longs are funded by its short proceeds, so the
   account carries no debit balance. Shorts are assumed easy-to-borrow, at a $0 fee.
   * Limitation: there is no history of each stock's borrow status, so a stock that was hard to borrow at the time
     still counts as shortable. For S&P 500 members this is rare.
4. **Stage-2 books** (PROTOCOL_fund.md "Market exposure") use the broker's terms:
   * a debit balance pays 6.50% a year;
   * idle cash earns nothing;
   * trading costs 5 bp per side, about 6× the measured cost;
   * the measured cost is reported alongside.
5. **The parts already saved stay valid.** They were run under the signed commit, and nothing in this amendment
   touches fitting or prediction. `score` accepts parts whose commit is an ancestor of this one.

## Amendment 2 (2026-10-23): every model on every literature strategy, written before any score

Written before `score` has run. No prediction has been opened. Owner: "test all models on all strategies from
literature" (`reports/research/quant_trials/STRATEGY_LITERATURE.md`).

**What runs.** `python sp500_transformers.py strategies` runs after `score`. It covers every model (ridge, MASTER,
TFT, Chronos-2, Chronos-2-ft) × h ∈ {5, 10, 20} × the strategies below, on the 2013–2025 Thursday decisions, with
these parameters fixed now.
* **Descriptive only.** It changes no pass/fail above. These predictions will have been seen, so the choice of
  strategy is made on forward weeks only.

**Common rules:**
* **Book:** long/short, 50% long and 50% short of NAV (the research books' gross), beta-hedged with SPY to zero
  252-day shrunk beta.
* **Holding period:** from close(d+1) to the next decision's close(d+1), on raw returns, dividends included.
* **Sleeve:** the owner's dynamic SPY sleeve (1.3x when SPY closes above its 200-session average at d, else 0.7x).
* **Costs (Amendment 1, broker terms):**
  * 5 bp per side on every weight change, the hedge and sleeve included;
  * debit balance at DTB3 + 2.43% (actual/360);
  * idle cash 0;
  * easy-to-borrow shorts $0.
* **Reported in % per year:**
  * the book alone;
  * book + sleeve;
  * excess over SPY buy-and-hold;
  * excess over the risk-matched S&P;
  * Sharpe, max drawdown and turnover (% of NAV per year);
  * all for 2013–25, 2013–19, 2020–25 and 2022.

**Strategies** (adapted to ~450 names; deciles replace the 31-name top/bottom 5):

| | Rule |
|---|---|
| S0 | top 10% long, bottom 10% short, equal weight, rebalanced weekly |
| S1 | band: enter in the top/bottom 10%, hold until the name leaves the top/bottom 20% (Novy-Marx & Velikov 2016) |
| S2 | signal-weighted: weights ∝ cross-sectional z-score ÷ 60-day volatility, over the top and bottom thirds (Grinold 1994) |
| S3 | partial adjustment toward S2 (Gârleanu & Pedersen 2013): w_t = w_{t−1} + λ(S2_t − w_{t−1}), λ = 1 − 0.5^(5/h) |
| S4 | S3 × min(1.5, 10% ÷ the book's realised volatility over the last 13 weeks, annualised) (Moreira & Muir 2017) |
| S5 | uncertainty-adjusted (median ÷ q90−q10 range): **not run historically**, because the saved parts hold no quantiles; forward only |

* Sector caps are not applied on the S&P universe.
* **The DTB3 series is downloaded once and frozen** in `.cache/quant_trials/dtb3.csv`.

## Amendment 3 (2026-10-25): Timestral, and the softmax fix, written before any Timestral test-year score
Owner request (2026-10-25):
* test Timestral (Mistral, released 2026-10-15) on the current setup at several horizons, with and without news,
  against our models;
* check whether the softmax/cross-entropy fix of Barron, Gnanapragasam & Tschannen (DeepMind, arXiv 2610.31642)
  applies to our models and what it changes;
* test and verify before every final decision.

Before this amendment, only these ran: the smoke test (2012, a training-period year; panel 2017) and the F1
diagnostic below, which uses only the 2013 refit window's training and validation rows. No Timestral prediction
on 2013–2025 exists. The 2013–25 S&P data have been seen for the other models; Timestral is a new model on them.

**T1: Timestral on the S&P 500 read, 2013–25 (confirmatory for Timestral).**
* **Model:** Timestral-209M, zero-shot. Code: github.com/mistralai/timestral@a534bdb. The weights' hub revision
  is recorded in the saved part. There are no fine-tuning tools, so there is no fitting and no grid.
* **Input:** exactly as zero-shot Chronos-2 (`chronos_scores`):
  * per eligible name, the daily residual series as target;
  * the five z-scored signals as past covariates;
  * context 512, prediction length 21;
  * names as independent series;
  * library defaults (symmetric averaging on), `clip_nonnegative` off.
* **Score:** the sum of median steps 1..h, so sessions d+2..d+1+h, the target's window.
* **Same universe, eligibility, embargo, Thursday decisions, scorer and pass rule** as the signed read:
  * Holm p < 0.05;
  * IC above ridge;
  * IC > 0 in 2013–19 and in 2020–25;
  * IC ≥ 0 in 2022;
  * net decile spread > 0 at 10 bp.
* **Holm across Timestral's 3 horizons** (5, 10, 20). This is its own family; the 12-test read stays as recorded.
* **Then, descriptive:** Timestral on S0–S4 and **S5** (median ÷ (q90 − q10) of the h-step sums, then S3),
  next to ridge, Chronos-2, Chronos-2-ft and MASTER, in % per year with broker costs.
* **Caveat:** Timestral's pretraining corpus is not disclosed and may contain market series up to 2026, so a
  2013–25 zero-shot result can be contaminated. A pass earns at most a forward book; forward weeks are the clean
  test.

**T2: Timestral ± news on the 31-name panel, 2018–25 (descriptive).**
* **Two arms at h ∈ {5, 10, 20}:**
  * factors only: the panel's five signals as past covariates;
  * factors + news: adds 3 intensity columns and PCA-8 of the half-life-5 headline state (the PCA is fit on
    2016–17 sessions only).
* **Target:** the panel's residual target. Thursday decisions.
* **Reported:**
  * weekly IC per arm, Δ IC (news − none) with NW t, and sector-neutral Δ;
  * spans 2018–25 and 2022–25, and by year.
* **Descriptive only:** the panel was used before, has low power, and its news idea already failed
  (`DECISION.md`).

**F: the softmax fix (2610.31642).**
* **Why it might matter.** None of our models trains on cross-entropy: MASTER uses MSE, TFT and Chronos-2 use
  quantile losses. Softmax appears only in attention and in MASTER's feature gate. In fp32, a softmax row whose
  top logit exceeds the log-sum-exp of the rest by a margin m loses accuracy in the top entry's gradient. The
  port's tests measured the error at about 0.2% at m = 10, about 17% at m = 15, and 100% past the cliff at about
  16.6.
* **Timestral is inference-only, so the fix does not apply to it.**
* **F1, diagnostic.** Retrain the 2013 refit window (training and validation rows only) for:
  * MASTER h5 (5 seeds, the frozen settings);
  * TFT h10 (seed 0);
  * Chronos-2-ft (2000 steps, eager attention so that softmax is visible).

  Log every softmax row's margin.
  * **Rule:** if under 0.1% of rows have m > 15, the fix is a numerical no-op for that model. This is recorded,
    and there is no retraining.
* **F2, only where F1's rule is crossed.**
  * Swap in the ported fixed softmax (`softmax_fix.py`; tests in `test_softmax_fix.py`).
  * Compare validation IC of the 2013 window, 5 seeds each, standard vs fixed.
* **F3, only if Δ val-IC > 2 seed standard errors.** The fixed variant becomes an extra forward-book arm in the
  forward-books amendment. There is **no second read of 2013–25**: those years were seen, so any re-run on them
  is labelled descriptive.

**Owner sign-off (Amendment 3):** _pending_
