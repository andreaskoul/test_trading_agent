# From signals to trades: literature review and draft strategy for models that pass (DRAFT, 2026-10-23)

**Status:** a literature draft for the owner. **Nothing here is pre-registered and nothing has been tested on
these signals.** The strategies below would be fixed in a pre-registration before they see any outcome.

All returns are in **% per year**.

## 1. Questions
1. **Portfolio construction.** Given a weekly cross-sectional score per stock (MASTER, TFT, Chronos-2 or ridge, at
   5/10/20 days), what portfolio should be held?
2. **Live trading.** Once a model passes, how should that portfolio be traded, and at what cost?

## 2. What the literature says

### Portfolio construction from a return signal

| Idea | Source | What it implies for us |
|---|---|---|
| **Fundamental law:** information ratio ≈ IC × √breadth | Grinold & Kahn, *Active Portfolio Management* (2000) | An IC of 0.03 on 31 names supports a weak book; on ~450 S&P names it can carry a real one. Breadth is the main lever. |
| **Alpha = volatility × IC × score:** weight by the standardised signal, not just in or out | Grinold (1994), "Alpha is volatility times IC times score" | Signal-proportional weights use the whole ranking instead of only its top and bottom 5. |
| **Trade partially toward an "aim portfolio"** that blends today's ideal portfolio with expected future ones; slow signals get more weight | Gârleanu & Pedersen (2013, *J. Finance*), "Dynamic trading with predictable returns and transaction costs"; generalised by Smerlak (CFM, arXiv 2610.24558, 2026) | Do not jump to the new target each week; move a fixed fraction of the way. 20-day signals should be traded more slowly than 5-day ones. |
| **Buy/hold band (hysteresis):** enter in the top 10%, exit only below the top 20% | Novy-Marx & Velikov (2016, *RFS*), "A taxonomy of anomalies and their trading costs" | Cuts turnover by about half for mid-frequency anomalies, with little loss of gross return. The simplest cost control. |
| **Combine characteristics with costs in mind:** costs reduce the number of useful signals, and combining them nets out trades | DeMiguel, Martín-Utrera, Nogales & Uppal (2020, *RFS*) | Blend model scores (e.g. ridge + transformer) before trading, not after. |
| **Parametric portfolio policies:** choose weights directly as a function of characteristics to maximise utility, with costs | Brandt, Santa-Clara & Valkanov (2009, *RFS*) | An alternative to "forecast, then sort". It has more parameters to overfit, so it is a later step. |
| **Volatility-managed exposure:** scale the book by target volatility ÷ recent volatility | Moreira & Muir (2017, *J. Finance*); Barroso & Santa-Clara (2015, *JFE*); Daniel & Moskowitz (2016, *JFE*) on momentum crashes | Our factors include 12-1 momentum, which crashes in rebounds (2009, 2020). Vol scaling cuts those drawdowns. Out-of-sample gains are disputed (Cederburg et al. 2020, *JFE*), so use it for risk, not as a source of return. |
| **Uncertainty-adjusted sorting:** shrink scores with high prediction uncertainty | arXiv 2601.00593 (2026) | Chronos-2 and TFT give quantiles. Sorting on median ÷ inter-quantile width is cheap to try. |
| **Forecast accuracy ≠ portfolio value:** constraints and costs reorder models; low-turnover models survive | arXiv 2606.09420 (2026); "smart predict-then-optimise" literature (2601.04062) | Judge every construction net of costs, against the risk-matched S&P. |
| **Costs erase most frictionless gains in daily strategies;** weekly or slower survives | Rahimikia et al. (arXiv 2511.18578); Frazzini, Israel & Moskowitz (2018), "Trading costs" (real AQR executions) | Our weekly cadence is right. Daily rebalancing is not worth testing. |

### Execution

| Idea | Source | What it implies for us |
|---|---|---|
| The closing auction concentrates liquidity and sets the official close | Bogousslavsky & Muravyev (2023, *JFE*), "Who trades at the close?" | Market-on-close orders match our benchmark price. Paper fills: 0.8 bp slippage. |
| Optimal execution trades impact against risk over a schedule (Almgren–Chriss); VWAP is optimal when impact tracks volume | Almgren & Chriss (2001); arXiv 1408.6118 | Relevant only once orders are a meaningful share of volume. At $100k and S&P 500 names, impact is negligible. |
| Institutional implementation costs on large-cap equity are a few to ~15 bp per side, rising with size | Frazzini, Israel & Moskowitz (2018) | Our 5 bp (books) and 10 bp (S&P read) per side are realistic to conservative at our size. |

## 3. Draft strategy menu
To be pre-registered before use. Parameters come from the papers, not from fitting.

Every strategy is **long/short** (owner rule). It sits on the owner's SPY sleeve (1.3x above the 200-day average,
0.7x below) with costs on Alpaca's terms:
* 5 bp per side;
* margin at 6.50% (T-bill + 2.43%);
* idle cash earns 0;
* easy-to-borrow shorts cost $0.

| | Construction | Rule | Expected effect |
|---|---|---|---|
| S0 | **Baseline (today)** | top 5 long / bottom 5 short at 10% each, beta-hedged | reference |
| S1 | **Band (Novy-Marx–Velikov)** | enter in the top/bottom 5; hold until the name leaves the top/bottom 10 | turnover about −40–50%, gross about unchanged |
| S2 | **Signal-weighted (Grinold)** | weights ∝ cross-sectional z-score ÷ 60-day volatility over the top and bottom thirds; gross 100%; same risk caps | uses more breadth; smoother |
| S3 | **Partial adjustment (Gârleanu–Pedersen)** | w_t = w_{t−1} + λ·(target_t − w_{t−1}), with λ = 1 − 0.5^(5/h) (half-life = the signal horizon h): λ ≈ 0.50 at h = 5, 0.29 at h = 10, 0.16 at h = 20 | lower turnover; holding period matched to signal decay |
| S4 | **S3 + volatility target (Moreira–Muir)** | book gross × min(1.5, 10% ÷ realised 60-day book volatility) | smaller crash drawdowns (momentum); Sharpe effect uncertain |
| S5 | **Uncertainty-adjusted** (probabilistic models only) | score = median ÷ (q90 − q10), then S3 | discounts noisy forecasts |

**How to choose, without overfitting.**
* All six are declared in advance with these parameters and reported together.
* **On the historical S&P predictions** (once the transformer read is done), the comparison is *descriptive*,
  because those predictions have been seen.
* **The choice is made on forward weeks only:** the strategy with the best net % per year over the risk-matched
  S&P at 52 weeks, with Holm across the six.

## 4. Draft live-trading plan (only after a model passes the forward verdict)

1. **Paper first.** The passing model plus strategy runs in the Alpaca paper account for ≥ 8 weeks:
   * measure slippage, fill rate and borrow availability against the 5 bp assumption;
   * any short that is not easy to borrow is dropped and its beta goes to SPY, as in `execute.py`.
2. **Orders:**
   * market-on-close at the Thursday close, the same benchmark as the scorer (fills 0.8 bp in paper);
   * a minimum trade size of 0.5% of NAV, so smaller changes are skipped (cuts small, costly turnover);
   * the existing idempotent client order ids and retries.
3. **Risk:**
   * the existing halts (−10% from peak, −5% over 5 sessions → flat);
   * sector net ≤ 30%;
   * any single name ≤ 12%;
   * gross ≤ 1.8× equity.
4. **Cost tracking.** Each week, realised costs (slippage, fees, margin interest) are reconciled against the model.
   If 8-week realised costs exceed 2× the assumption, the cost assumption is raised and the net % per year
   restated.
5. **Scale.** At $100k, impact is negligible. Above about $5M, re-check participation (order ÷ closing-auction
   volume ≤ 1%) and consider VWAP over the last hour (Almgren–Chriss) for the largest orders.
6. **Real money** only after the forward verdict and the paper-execution check, with your explicit decision. Any
   change to the traded fund is a new protocol (CLAUDE.md 13).

## 5. Restated so far, in % per year
* **Ridge five-factor S&P 500 read (failed):** top-minus-bottom decile, net of 10 bp per side: **−8.4% per year**
  (−16.8 bp a week).
* **Research books + dynamic sleeve against the risk-matched S&P** (broker costs; history already seen, not evidence):

| | 2018–21 | 2022–25 |
|---|---|---|
| `qn_h10` | +35.5% per year | +4.5% per year |
| `q5_h20` | +17.5% per year | +9.8% per year |
| sleeve alone | −3.8% per year | −1.8% per year |
