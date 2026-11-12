# Layer 3: process log

*One entry per step, written when the step is done. Plan: `PHASE3_PLAN.md`. Registrations: `PREREG.md`.*

## Step 1 — power calculation (2026-11-12, before any layer-3 registration)

**What was done.** Weekly rank ICs of the two cleanest out-of-sample series in the project were decomposed into
cross-sectional sampling noise (about 1/√N) and time variation (`LAYER3_POWER.json`):

| Series | Weeks | Names | Mean IC | sd of weekly IC | Share of variance from time variation |
|---|---:|---:|---:|---:|---:|
| IPCA, S&P 400 read | 353 | 332 | 0.0183 | 0.174 | 90% |
| MASTER, S&P 500 2020–2025 | 303 | 463 | 0.0326 | 0.183 | 94% |

**Finding.** The noise in a mean IC is almost all the market's week-to-week variation in what pays, not the number
of names. Power at one-sided α 0.025 (Holm's first step with two finalists), Newey–West inflation 1.1:

| Read | True IC 0.015 | True IC 0.02 |
|---|---:|---:|
| 350 weeks, 330 names | 31% | 50% |
| 350 weeks, 1,000 names | 33% | 53% |
| 465 weeks (2017–2025), 1,000 names | 42% | 65% |

**Correction to the plan.** `PHASE3_PLAN.md` L3.1 said the broad universe cuts the standard error "by about √3".
That was wrong: it cuts it by about 3%. Power comes from weeks. The broad universe is still the right next sample,
for a different reason: it is fresh and survivorship-free. The read window is moved to 2017–2025 (the first year
with a full year of history in Alpaca's bars), which raises power for a true IC of 0.02 from 53% to 65%.

**Consequence for the policy.** Even a real IC of 0.02 fails a two-finalist read about a third of the time. A failed
read of a candidate with a strong prior (IPCA, the trees) is weak evidence against it; forward weeks remain necessary.

## Step 2 — exploitation round and overfitting diagnostics launched; universe build started (2026-11-12)

**Agents (development data only, each with `STATE.json`):**
* **X4_exploit:** fixed-weight combinations of validated pieces (MASTER + IPCA, + trees, + short volume) and the
  no-trade band against plain deciles; IPCA against its declared control on 2013–2019. Weights written into its plan
  before scoring.
* **X5_overfit:** probability of backtest overfitting (CSCV), deflated Sharpe ratio and shrunk ICs for each branch,
  then a calibration check: would they have predicted which of the six finalists survived? Output: a mechanical
  selection rule for later reads.

**Universe (coordinating session, data for the sealed read):**
* Symbols: 33,565 Alpaca US-equity assets (active and inactive) read; 22,507 dropped for exchange (not NYSE, NASDAQ,
  AMEX); 1,390 dropped as ETF or test issue by Nasdaq Trader's typed flags; **9,668 kept**.
* Daily bars 2016–2025 downloading in 194 chunks of 50 symbols, resumable.
* `panel_broad.py` written: applies the registered eligibility rule each session (top 1,500 by 63-session dollar
  volume, price above $5, 252 sessions of history, read names excluded). To share code with the S&P 400 panel,
  `panel400.build` was refactored into `fields()`; the S&P 400 panel was checked **bit-identical** before and after
  (SHA-1 of every array), so the phase-2 read is unaffected.
