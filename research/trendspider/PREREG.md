# Pre-registration: replica and out-of-sample read of TrendSpider's "SSO Opus 5.5 Swing 15m"

Written 2026-11-04, before any replica result exists. Research only: nothing is traded, and `fund/` is not touched.

## Rules (as published on the share page, 2026-11-03)
These rules run on the regular session only. A signal forms on a bar's close and fills at the next bar's open. One
position at a time, fully invested, long only.
* Filter: SMA(50) > SMA(200) and ADX(10) > 20, all on 15-minute bars.
* Setup A: close > the highest high of the 14 bars ending one bar ago, and volume ≥ SMA20(volume) "by at least 100%".
* Setup B: the day-anchored VWAP "crosses ↗" the close, RSI(14) > 50, and volume ≥ SMA20(volume) "by at least 50%".
* Exits are evaluated on the bar close. Stop: P&L < −3.5%. Target: P&L > +15%. Trailing stop: 7% from the highest
  close since entry. Time exits: after 25 bars if P&L < 0, after 60 bars if P&L < 1%.

## Ambiguities: resolved on the in-sample window only (2022-03-24 → 2026-11-03)
1. "By at least X%": either volume ≥ (1+X)·SMA, or volume ≥ X·SMA.
2. "VWAP crosses ↗ close": either VWAP crosses above the close, or the close crosses above VWAP.

All four combinations are run on the in-sample window. The one closest to the page's figures (153% total, 40% wins,
+0.96% average trade, −12.5% drawdown) is the **replica**. The distance is |log total-return ratio| plus |win-rate
difference|. It is chosen before the out-of-sample window is computed. If no variant comes within 25% of total return,
the report says the strategy could not be reproduced, and the out-of-sample read is still made on the closest variant.

## Read (made once)
* Out-of-sample window: **2016-03-01 → 2022-03-23** on SSO (bars from 2016-01 serve as warm-up). The 2020 COVID
  crash is a regime: results are also shown with 2020 excluded.
* Costs: 2 bp per side (the primary); 0 bp is also shown.
* **The strategy "replicates out of sample" if** its out-of-sample Sharpe exceeds both SPY buy-and-hold and the
  "SSO above its 200-day SMA, else cash" rule over the same window, with costs. Otherwise it does not.
* Robustness: 300 configurations, each parameter drawn independently from {−20%, 0, +20%} of its published value
  (integers rounded, seed 20261104). Two measures:
  1. The share of configurations whose out-of-sample Sharpe beats SPY's.
  2. The probability of backtest overfitting (CSCV, Bailey et al. 2014) over the full 2016–2026 daily returns of the
     300 configurations plus the replica, in 16 blocks.

  PBO < 0.5 means "selection on past performance helped".
* Other instruments, descriptive only: the same replica rules on SPY, QLD and UPRO over 2016–2026.

No result changes these rules after the fact.
