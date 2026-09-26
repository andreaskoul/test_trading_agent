# Research summary (26–27 Sep 2026)

Five pre-registered studies. Every protocol was committed before its data met
a return. Every deviation is dated, and every post-hoc number is labelled.

| study | question | trials | pass | detail |
|---|---|---:|---:|---|
| Live window | Do the 168 RL policies trade profitably Apr–Sep 2026? | 168 | 0 | [live_oos](../live_oos/README.md) |
| 1 · hourly gold | Do simple models beat a coin flip at 4–26 hours? | 12 | 0 | [README](README.md) |
| 2 · daily gold | Do COT, real rates, the dollar or TSMOM add alpha over gold? | 14 | 0 | [daily](daily/README.md) |
| 3 · FX cross-section | Do carry, momentum, value or reversal rank 17 currencies? | 16 | 0 | [fx](fx/README.md) |
| 3b · FX confirmation | Do the 2004–26 patterns hold on untouched 1990–2003 data? | 3 | **carry** | [fx](fx/README.md) |
| 4 · US large caps | Do momentum, reversal, low-vol or 52-week-high rank S&P 500 members? | 14 | 0 | [stocks](stocks/README.md) |

## What was learned

1. **The original "edge" was built by the backtester.** Close-checked stops
   filled at the barrier price made random trades profitable (+2.5 bp gross,
   t ≈ 10). The macro features leaked same-day closes, and the S&P input was a
   monthly average dated at the start of its month. Together these produced
   about 80% of the apparent predictability.
2. **Clean single-asset direction is unpredictable** from price, macro and
   positioning data, from 4 hours to 5 days, after costs and after allowing for
   drift.
3. **Cross-sectionally, three effects exist in gross terms. Only one survives
   as a strategy:**
   * *FX carry*: Sharpe 0.63 (1990–2003), ≈ 0 (2004–15), 0.75 (2016–26),
     confirmed on untouched data. It is a risk premium with crash exposure.
   * *Weekly equity reversal*: +15–17%/yr gross decile spread in both samples,
     wiped out by weekly turnover at realistic costs.
   * *FX 1–3 month momentum/reversal*: its sign flips between eras, so it is
     not a signal.
4. **What's left needs information the market doesn't already have**: the
   firm-level news-geometry features belong in the stock cross-section, where
   Protocol 4's infrastructure (point-in-time membership, costs, FF6
   attribution, Fama–MacBeth) is ready for them.
