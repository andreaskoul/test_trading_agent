# Cross-sectional US large caps: results

Protocol: [`PROTOCOL_stocks.md`](../PROTOCOL_stocks.md), committed at 17e5769 before any
stock price was downloaded.

```
python scripts/xs/fetch_stocks.py
python scripts/xs/stock_ladder.py     # pre-registered
python scripts/xs/audit_stocks.py     # decile re-computation, SPY check
```

## Data and survivorship

S&P 500 membership as it stood on each date (fja05680/sp500, pinned commit
a2430f2). 1,002 tickers were members at some point since 2003; Yahoo has
691 of them. The share of that week's members with a usable price:

| 2004 | 2008 | 2012 | 2016 | 2020 | 2024 | 2026 |
|---:|---:|---:|---:|---:|---:|---:|
| 52% | 60% | 68% | 75% | 86% | 95% | 99% |

Dev (2004–15) therefore sees mostly firms that survived; holdout (2016–26) is
much cleaner. The direction of the bias was written down in advance: it
**helps reversal and low-risk signals and hurts momentum**.

## Result: 0 of 14 pass

Holdout 2016-01 → 2026-03, dollar-neutral rank weights, 5 bp per side:

| signal | H | Sharpe | HAC t | β mkt | α mkt t | α FF6 t | FM t | cost/yr | Sharpe @2.5bp | dev Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mom12_1 | 1 | −0.15 | −0.6 | −0.40 | 0.8 | −1.4 | −0.3 | 0.9% | | −0.27 |
| rev1m | 1 | 0.11 | 0.5 | 0.41 | −1.1 | −0.7 | 1.3 | 3.3% | 0.22 | 0.11 |
| rev1w | 1 | 0.22 | 0.6 | 0.26 | 0.0 | −0.1 | 1.8 | 6.9% | 0.45 | 0.31 |
| lowvol | 1 | −0.37 | −1.4 | −0.76 | 0.9 | −0.7 | −1.3 | 0.8% | | −0.31 |
| high52 | 1 | −0.35 | −1.5 | −0.71 | 0.8 | −1.2 | −1.1 | 1.5% | | −0.50 |
| combo | 1 | −0.22 | −0.8 | −0.37 | 0.6 | −1.0 | −0.2 | 2.3% | | −0.34 |
| ridge | 1 | 0.30 | 1.1 | 0.66 | −1.2 | 0.2 | 1.9 | 3.7% | 0.41 | 0.09 |
| ridge | 4 | 0.37 | 1.4 | 0.61 | −0.9 | 0.9 | 1.9 | 1.3% | 0.40 | 0.12 |

(The coin flip is −2.3 at H = 1, which is all turnover cost. Full table: `stock_ladder_results.csv`.)

Reading it:

* **Dollar-neutral is not beta-neutral.** Low-vol and 52-week-high books run a
  market beta of −0.7 to −0.8 (long low-beta, short high-beta). In a bull market
  that is a large drag, and their alpha against the market is +0.8 to +0.9 t:
  there, but small.
* **Momentum in large caps is dead in both samples** (Sharpe −0.15 to −0.3,
  FF6 alpha negative in dev at t −4.1 against UMD). Survivorship was expected to
  hurt it in dev, but holdout is clean and it is still flat.
* **One-week reversal is the one robust gross effect.** The independent decile
  sort gives a top-minus-bottom spread of +17%/yr in dev (t 2.8) and +15%/yr in
  holdout (t 2.0). The Fama–MacBeth t-values are 3.3 and 1.8. But it turns the
  whole book over every week: 6.9% a year in costs at 5 bp. Even at 2.5 bp the
  Sharpe is 0.45, and it loads on the market (β 0.26) with no alpha. This is the
  classic liquidity-provision premium, and it goes to whoever has the cheapest
  execution.

## Audits

* The equal-weight universe tracks SPY: weekly correlation 0.94 over the
  holdout, 14.0% vs 14.7% a year.
* An independent decile-sort re-computation agrees in sign and rough size with
  every ladder row it checks (mom12_1, rev1m, rev1w, lowvol).
* Restricting to weeks with ≥ 90% coverage (2021 onward) changes no conclusion.
  mom12_1 rises to Sharpe 0.48 over that short stretch (t 1.1).
