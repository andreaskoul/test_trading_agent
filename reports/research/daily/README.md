# Daily horizon: positioning, real rates, dollar, momentum

Protocol: [`../PROTOCOL_daily.md`](../PROTOCOL_daily.md), committed at 2e53ee9 (23:49),
amended at 1d9fc50 and 58fd3c0, all before the ladder was first run.

```
python scripts/daily/fetch_daily_data.py
python scripts/daily/daily_ladder.py      # pre-registered
python scripts/daily/audit_daily.py       # audits + one post-hoc statistic
```

## Result: 0 of 14 pass

Holdout 2019-01 → 2026-03 (1,824 days), 2 bp per unit turnover. Gold returned
19% a year over this window, so the bar that matters is **alpha over being
long gold**.

| rule | H | Sharpe | HAC t | alpha/yr | alpha t | β | long % | DSR | dev OOF Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| tsmom12 | 1 | 0.59 | 1.7 | −4.3% | −1.1 | 0.77 | 79 | 0.44 | 0.12 |
| tsmom1 | 1 | −0.01 | 0.0 | −7.8% | −1.4 | 0.39 | 62 | 0.04 | −0.07 |
| realrate | 1 | 0.08 | 0.2 | −0.4% | −0.1 | 0.10 | 52 | 0.06 | −0.04 |
| dollar | 1 | −0.08 | −0.2 | −1.8% | −0.3 | 0.02 | 49 | 0.02 | −0.12 |
| cot | 1 | −0.32 | −0.9 | −1.4% | −0.5 | −0.07 | 13 | 0.01 | 0.11 |
| ridge | 1 | **0.94** | **2.4** | 13.3% | 1.8 | 0.18 | 58 | 0.78 | **−0.60** |
| gbm | 1 | −0.03 | −0.1 | 2.1% | 0.3 | −0.14 | 55 | 0.03 | 0.17 |
| tsmom12 | 5 | 0.66 | 2.0 | −3.0% | −0.8 | 0.75 | 79 | 0.51 | 0.07 |
| tsmom1 | 5 | 0.11 | 0.3 | −6.2% | −1.3 | 0.41 | 62 | 0.07 | −0.22 |
| realrate | 5 | 0.21 | 0.6 | 2.7% | 0.5 | 0.03 | 52 | 0.12 | 0.26 |
| dollar | 5 | 0.02 | 0.1 | −0.2% | 0.0 | 0.03 | 48 | 0.05 | −0.06 |
| cot | 5 | −0.45 | −1.2 | −2.5% | −0.8 | −0.07 | 15 | 0.00 | 0.00 |
| ridge | 5 | 0.38 | 1.1 | 2.0% | 0.4 | 0.18 | 61 | 0.23 | −0.25 |
| gbm | 5 | 0.20 | 0.6 | 5.3% | 1.1 | −0.13 | 57 | 0.11 | −0.21 |
| *always long* | – | 1.08 | 3.1–3.3 | | | 1 | 100 | | 0.44 |
| *coin flip (500 paths)* | 1 / 5 | −0.30 / −0.11 | | | | | | | |

Full rows, dev OOF and cost sensitivity at 1/2/4 bp: `daily_ladder_results.csv`.

Reading it:

* **The momentum rules are long gold at a discount.** tsmom12 earns its Sharpe
  through β = 0.77 and is 79% long; its alpha is negative. That is what a trend
  rule does in a seven-year bull market, and holding gold does it better.
* **Real rates, the dollar and CFTC crowding carry nothing at 1–5 days.** Their
  alphas are within ±3%/yr with |t| < 1, and they are no better in dev.
* **Ridge at H = 1 is the only interesting row, and it fails for two reasons.**
  Its alpha t is 1.8 and its DSR 0.78 (the 14-trial Sharpe hurdle on holdout is
  0.65). More telling, the same model had a Sharpe of −0.60 out-of-fold in dev. A
  real edge that is strongly negative for ten years and strongly positive for seven
  is a regime coincidence until shown otherwise. Under the protocol it gets no
  look at the live window.

## Audits (`audit_daily.py`)

* **P&L arithmetic:** an independent loop re-implementation of the position and
  cost timing matches the vectorised P&L to 0.0.
* **Timing placebo:** ridge (H = 1) with a deliberate one-day *leak* scores
  Sharpe 0.66, as registered 0.94, with one extra day of delay 0.76, with two
  0.38. A timing leak would make the leaked version jump, and it doesn't.
* **Shuffled-target placebo:** ridge refit 200 times on time-permuted dev targets
  gives holdout Sharpe 0.10 ± 0.40, and the real 0.94 sits at p = 0.02 of that.
  Taken alone that looks like signal, but it is one of 14 trials, and the dev
  sign is the opposite.
* **Instrument:** Yahoo GC=F against GLD differs by 0.35%/yr, and the largest
  daily differences are close-time mismatches, not roll jumps (checked before the
  run; Amendment 1).

## A defect in the pre-registered IC, and the corrected statistic

The protocol's IC is a Spearman correlation computed *within each month*, then
averaged. For slow sign signals (tsmom12 flips a few times a year) that
statistic only measures within-month timing around the flips, and it produces
large, meaningless values (tsmom12 H = 5: IC −0.33, t −10.2 alongside a
positive Sharpe). It doesn't change the decision, since every rule fails the
alpha criterion first. The appropriate statistic, **added post hoc and labelled
as such**, is the pooled predictive regression of the H-day forward return on
the standardised score with HAC errors:

| H | tsmom12 | tsmom1 | realrate | dollar | cot | ridge | gbm |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | −0.04 | −0.66 | 0.17 | −0.02 | −0.56 | 1.59 | 0.92 |
| 5 | 0.19 | −0.57 | 0.42 | 0.18 | −0.93 | 1.72 | 0.47 |

(t-statistics on holdout.) Nothing reaches 2.

## Where this leaves the project

Two pre-registered studies, 26 trials, the full 168-policy RL zoo, and one common
answer: public price, macro and positioning data do not predict gold returns
out of sample at horizons from 4 hours to 5 days, net of cost and beyond the
drift. That is consistent with the literature on liquid commodity futures
outside trend following, and the trend here is beta.

What would change the answer has to be information the market doesn't
aggregate instantly. The candidate the project is actually positioned for is
the news-geometry work: firm- or asset-level interpretive difficulty as a
predictor, first of *volatility and liquidity* (where the thesis evidence
lives) rather than direction. A volatility target is also a much easier
statistical problem: realised volatility is persistent, forecast errors are
smaller, and the economic use (sizing, option overlays) doesn't require
beating drift.
