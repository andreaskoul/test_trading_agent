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
