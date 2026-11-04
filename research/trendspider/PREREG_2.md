# Pre-registration 2: the short side, robustness, and intraday momentum (long and short)

Written 2026-11-04, after the first read (`PREREG.md`, results in `results/read.json`) and **before any code for
the tests below exists**. Research only: nothing is traded, and `fund/` is not touched. Each confirmatory read is
made once. Data: the Alpaca 15-minute regular-session bars already downloaded (SIP feed, split and dividend adjusted,
2016-01-04 → 2026-11-03).

The owner's rule is that every strategy must be able to go short. This round therefore tests short and long/short
versions, not only long ones.

## B. The TrendSpider rules mirrored to the short side (new hypothesis; confirmatory)
The **mirror** applies the published rules upside down, with nothing tuned:
* Filter: SMA(50) < SMA(200) and ADX(10) > 20.
* Setup A: close < the lowest low of the 14 bars ending one bar ago, on volume ≥ 2 × SMA20(volume).
* Setup B: the day-anchored VWAP crosses *below* the close, RSI(14) < 50, on volume ≥ 1.5 × SMA20(volume). This
  mirrors the replica variant `plus/vwap_over`.
* Exits, on a short P&L: stop at a 3.5% loss, target at a 15% gain, trailing stop 7% above the lowest close since
  entry, and time exits after 25 bars if losing and after 60 bars if up less than 1%.
* Fills at the next bar's open.

Costs: 2 bp per side, plus a **borrow fee of 3% a year** accrued on the short notional per session held. This is an
assumption, stated in advance; leveraged ETFs can be costlier to borrow.

Books, on SSO:
* **B1 short-only:** the mirror alone.
* **B2 long/short:** the long replica and the mirror. One position at a time. A new entry is taken only when flat;
  the two filters exclude each other.

Window: **2016-03-01 → 2026-11-03**, the whole sample, read once. The mirror's rules have never been run on any of it.

Pass criteria:
* **B1** passes if its mean daily return is > 0 with a one-sided stationary-bootstrap p < 0.05 (Politis–Romano,
  mean block 10 days, 5,000 draws, seed 20261104).
* **B2** passes if its Sharpe ratio is above both the long-only replica's and SPY buy-and-hold's over the window, and
  the bootstrap p of the Sharpe difference B2 − SPY is < 0.10.

Descriptive only: the same mirror and long/short books on SPY.

## C. Robustness of the published long rules (descriptive; that read is spent)
* Costs: 0, 1, 2, 5 and 10 bp per side, 2016-03 → 2026-11.
* Bar length: 30- and 60-minute bars resampled from the 15-minute bars, same rule counts.
* **Walk-forward selection.** Every 6 months from 2018-03:
  * pick the best-Sharpe configuration of the 300-variant grid (seed 20261104, as in read 1) on the previous 2 years;
  * trade it for the next 6 months;
  * chain the out-of-sample segments to 2026-11.

  This asks whether choosing parameters on recent history works at all.
* A stationary-bootstrap 90% interval for the Sharpe difference (replica − SPY), 2016-03 → 2026-11.

## D. Intraday momentum on SPY (Zarattini, Aziz & Barbon 2024), long and short
**Rules, as in the paper's final model** ("current band + VWAP, dynamic"):
* **Noise area.**
  * σ(t, HH:MM) is the mean over the previous 14 sessions of |close at HH:MM ÷ that day's 9:30 open − 1|.
  * Upper = max(open_t, close_{t−1}) × (1 + σ).
  * Lower = min(open_t, close_{t−1}) × (1 − σ).
* **Decisions** at HH:00 and HH:30 only, from 10:00 to 15:30 ET, on the close of the 15-minute bar ending then.
  * Flat: go long if close > max(Upper, VWAP); go short if close < min(Lower, VWAP). The paper's VWAP stop is
    evaluated at the same mark, so entering on its wrong side would be closed at once.
  * Long: if close < Lower, flip short; otherwise exit if close < max(Upper, VWAP).
  * Short: if close > Upper, flip long; otherwise exit if close > min(Lower, VWAP).
  * Every position closes at the session's last close.
* **Sizing.**
  * Shares = equity_{t−1} × min(4, 2% ÷ σ_SPY) ÷ open_t.
  * σ_SPY is the sample standard deviation of the previous 14 daily close-to-close returns.
* **Costs**, as in the paper: $0.0035 commission plus $0.001 slippage per share, each side.
* **Fills** at the decision bar's close (the paper). Variant: the next bar's open.
* **Approximation, stated in advance:** VWAP and the noise area use 15-minute bars, not the paper's 1-minute bars.
  Decisions and stops are only made at half-hour marks in the paper too, so the rule timing is the same.

**Windows.**
* **D-confirmatory:** 2025-01-02 → 2026-11-03. This is after every version of the paper's sample (May 2007 →
  December 2024; first version May 2024).
* **D-replication**, descriptive: 2016-03 → 2024-12, inside the paper's sample.

**Pass criterion (D-confirmatory):** the mean daily return of the full long/short model is > 0 with a Newey–West
(5 lags) one-sided t ≥ 1.65.
* Power, stated in advance: with about 460 sessions, a true Sharpe ratio of 1.33 (the paper's) gives t ≈ 1.8, so
  power is only about 55%.
* A fail is therefore weak evidence against the strategy; a pass is moderate evidence for it.

**Reported beside it** (descriptive):
* the **long-only** and **short-only** legs;
* fills at the next bar's open;
* costs doubled;
* the full model without volatility sizing (1× notional);
* SPY buy-and-hold, and a risk-matched SPY at the strategy's volatility;
* "SPY held plus the intraday overlay" as a core-satellite illustration. Its gross exposure can reach 5×, so it is
  never a recommendation by itself.

No result changes these rules after the fact. Each confirmatory number (B1, B2, D) is computed once.
