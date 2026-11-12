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

## Step 2a — exploitation round result (X4, development data, 2026-11-12)

* **No combination beats its best single piece by more than noise.** The best blend (MASTER + IPCA + trees, equal
  thirds) has IC .0247 against .0236 for the trees alone.
* **IPCA does not beat its declared control** on 2013–2019: +.0017 over the Fama-MacBeth ridge on the same 24
  characteristics (t 0.23), rank correlation 0.70. This is the control check the phase-2 finalist rule skipped. It
  weakens the reading of IPCA's S&P 400 pass as evidence for the IPCA method specifically: the ridge may do as well.
* **The no-trade band is the one robust gain:** +1.0 to +1.5%/yr on fast single signals (t 2.0–2.65), little on blends,
  negative on the slow short-volume signal.
* **Consequence for the registered read (L3.1):** none; candidates and controls were fixed before this result. The
  read reports IPCA against the ridge as a paired difference, which will show whether the gap stays at zero.

## Step 2b — overfitting diagnostics result (X5, development data, 2026-11-12)

* **PBO and the deflated Sharpe ratio would not have predicted which finalists survived** (rank correlations with
  retention +0.32, −0.20, −0.09). The best deflated Sharpe (the SDF, 0.995) kept 23%; IPCA, with the worst PBO (0.75),
  passed.
* **Why:** selection inside every branch was noise (PBO about 0.5; the in-sample best never beat the branch median out
  of sample). Survival depended on whether a branch's level was real, which these tools do not measure.
* **What did line up:** the shrunk IC forecast holdout IC better than the raw IC; finalists chosen by mean IC kept
  78–82%, those chosen by t over a higher-IC sibling kept −2% to 41%. Six points, found after looking.
* **Adopted (PREREG Layer 3, Amendment 2):** choose by mean IC, never t; rank by shrunk IC; at most two finalists with
  controls; report PBO and the deflated Sharpe ratio, not gate on them. For the pending read, power at the shrunk IC
  is about 70% for the trees and 42% for IPCA, so a failed IPCA read was registered in advance as uninformative.
