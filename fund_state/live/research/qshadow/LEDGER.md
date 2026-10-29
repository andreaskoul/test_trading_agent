# Research shadow books (quant trials)

Never traded. Weekly, Thursday close to Thursday close, 5 bp per side, cash 0. Primaries: qn_h10, q5_h20. Jan-Sep 2026 is the sealed P8 window: no books. Only `live` rows are forward evidence.

Below each span: the primaries on top of SPY, held 1x and through the owner's dynamic sleeve (1.3x SPY when SPY closes above its 200-session average at the as-of close, 0.7x otherwise; a debit balance pays the margin rate, DTB3 + 2.43% (Alpaca's 6.50% today), idle cash earns nothing, easy-to-borrow shorts cost nothing), against SPY buy-and-hold and a risk-matched SPY holding the span's mean sleeve. All lines use the books' holding weeks: a week without a session Wednesday (e.g. 4 July, Juneteenth, Christmas) is flat for every line. The sleeve is the owner's policy (2026-10-19), not a tested or tuned parameter.

## backfill 2018-21

| book | weeks | cumulative | Sharpe (ann.) | max drawdown | mean IC |
|---|---|---|---|---|---|
| q5_h5 | 202 | +84.1% | +0.72 | -19.7% | +0.001 |
| qn_h5 | 202 | +151.6% | +1.05 | -12.7% | +0.038 |
| q5_h10 | 202 | +111.3% | +0.86 | -18.2% | -0.001 |
| qn_h10 (primary) | 202 | +199.8% | +1.22 | -12.4% | +0.050 |
| q5_h20 (primary) | 202 | +85.5% | +0.73 | -17.0% | -0.012 |
| qn_h20 | 202 | +233.5% | +1.33 | -12.0% | +0.058 |

Against the S&P 500 (202 weeks; mean sleeve 1.23x):

| line | cumulative | annualised | vs S&P (ann.) | vs risk-matched (ann.) | Sharpe | max drawdown |
|---|---|---|---|---|---|---|
| S&P 500 buy & hold | +80.7% | +16.5% | +0.0% | -2.5% | +0.89 | -28.6% |
| risk-matched S&P (1.23x) | +96.3% | +19.0% | +2.5% | +0.0% | +0.85 | -34.6% |
| dynamic sleeve alone (1.3x / 0.7x) | +73.1% | +15.2% | -1.3% | -3.8% | +0.74 | -35.2% |
| qn_h10 + S&P | +453.1% | +55.3% | +38.9% | +36.4% | +1.61 | -15.3% |
| qn_h10 + dynamic sleeve | +441.9% | +54.5% | +38.0% | +35.5% | +1.52 | -22.5% |
| q5_h20 + S&P | +239.6% | +37.0% | +20.5% | +18.0% | +1.16 | -18.6% |
| q5_h20 + dynamic sleeve | +234.7% | +36.5% | +20.0% | +17.5% | +1.10 | -25.4% |

## backfill 2022-25 (seen in research)

| book | weeks | cumulative | Sharpe (ann.) | max drawdown | mean IC |
|---|---|---|---|---|---|
| q5_h5 | 202 | +50.3% | +0.81 | -12.1% | +0.033 |
| qn_h5 | 202 | +33.6% | +0.55 | -15.9% | +0.024 |
| q5_h10 | 202 | +50.7% | +0.81 | -16.0% | +0.041 |
| qn_h10 (primary) | 202 | +19.5% | +0.36 | -17.4% | +0.035 |
| q5_h20 (primary) | 202 | +41.4% | +0.69 | -18.6% | +0.067 |
| qn_h20 | 202 | +32.7% | +0.52 | -18.4% | +0.058 |

Against the S&P 500 (202 weeks; mean sleeve 1.14x):

| line | cumulative | annualised | vs S&P (ann.) | vs risk-matched (ann.) | Sharpe | max drawdown |
|---|---|---|---|---|---|---|
| S&P 500 buy & hold | +55.3% | +12.0% | +0.0% | -0.5% | +0.77 | -21.6% |
| risk-matched S&P (1.14x) | +58.0% | +12.5% | +0.5% | +0.0% | +0.73 | -24.7% |
| dynamic sleeve alone (1.3x / 0.7x) | +48.5% | +10.7% | -1.3% | -1.8% | +0.69 | -23.0% |
| qn_h10 + S&P | +82.9% | +16.8% | +4.8% | +4.3% | +0.75 | -29.9% |
| qn_h10 + dynamic sleeve | +84.1% | +17.0% | +5.0% | +4.5% | +0.74 | -33.3% |
| q5_h20 + S&P | +117.0% | +22.1% | +10.1% | +9.6% | +0.98 | -21.7% |
| q5_h20 + dynamic sleeve | +118.4% | +22.3% | +10.3% | +9.8% | +0.97 | -20.4% |

## Oct 2026 catch-up (computed late)

| book | weeks | cumulative | Sharpe (ann.) | max drawdown | mean IC |
|---|---|---|---|---|---|
| q5_h5 | 2 | -4.7% | -77.99 | -4.7% | -0.378 |
| qn_h5 | 2 | -4.7% | -10.79 | -4.7% | -0.423 |
| q5_h10 | 2 | -3.2% | -10.53 | -3.2% | -0.504 |
| qn_h10 (primary) | 2 | -4.7% | -12.41 | -4.7% | -0.558 |
| q5_h20 (primary) | 2 | -4.4% | -8.65 | -4.4% | – |
| qn_h20 | 2 | -4.8% | -11.86 | -4.8% | – |

Against the S&P 500 (2 weeks; mean sleeve 1.30x):

| line | cumulative | annualised | vs S&P (ann.) | vs risk-matched (ann.) | Sharpe | max drawdown |
|---|---|---|---|---|---|---|
| S&P 500 buy & hold | -1.3% | – | – | – | -8.92 | -1.3% |
| risk-matched S&P (1.30x) | -1.7% | – | – | – | -9.32 | -1.7% |
| dynamic sleeve alone (1.3x / 0.7x) | -1.7% | – | – | – | -9.32 | -1.7% |
| qn_h10 + S&P | -6.0% | – | – | – | -11.45 | -6.0% |
| qn_h10 + dynamic sleeve | -6.3% | – | – | – | -11.26 | -6.3% |
| q5_h20 + S&P | -5.7% | – | – | – | -8.71 | -5.7% |
| q5_h20 + dynamic sleeve | -6.1% | – | – | – | -8.77 | -6.1% |

## live (forward)

| book | weeks | cumulative | Sharpe (ann.) | max drawdown | mean IC |
|---|---|---|---|---|---|
| q5_h5 | – | – | – | – | – |
| qn_h5 | – | – | – | – | – |
| q5_h10 | – | – | – | – | – |
| qn_h10 (primary) | – | – | – | – | – |
| q5_h20 (primary) | – | – | – | – | – |
| qn_h20 | – | – | – | – | – |
