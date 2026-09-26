# Baseline ladder and RL zoo on the causal rebuild

Protocol: [`PROTOCOL.md`](PROTOCOL.md), committed (39f19d9, 23:16 +03:00) before any
result below existed. Pre-registered results come first, exploratory ones are marked.

Reproduce:
```
python scripts/build_extended_data.py --force-macro-refresh
python scripts/11_baseline_ladder.py      # pre-registered
python scripts/13_leak_probe.py 1b424ff   # exploratory
python scripts/12_rl_zoo_holdout.py && python scripts/14_rl_zoo_stats.py   # exploratory
```

## What changed in the data

* **S&P 500, 2012–2015, was a monthly average stamped on the 1st of the month** and
  forward-filled (GitHub `s-and-p-500` dataset). On 2 Jan 2013 the feature already
  held January's average. That is up to a month of look-ahead over ~40% of the
  training span. Replaced with Yahoo daily closes.
* Every macro close is lagged one day to when it is actually known (it was used from
  00:00 UTC of its own date).
* The HMM regime is the forward filter everywhere (`HMMRegimeModel.posterior` now
  filters; the smoother is `smoothed_posterior`, kept only for comparison).
* OHLC is passed through for bracket fills. The 22-column schema is unchanged.

## Pre-registered result: nothing passes

Holdout = GC futures 2023-07 → 2026-03 (2.7 years). Cost ≈ 1.4 bp per round trip.
bp per trade:

| rule | H | gross | net | net HAC t | IC (monthly) | IC t | DSR | pass |
|---|---:|---:|---:|---:|---:|---:|---:|:-:|
| tod | 4 | −0.05 | −1.43 | −1.9 | 0.013 | 0.9 | 0.00 | no |
| mom | 4 | +0.95 | −0.47 | −1.0 | 0.017 | 1.4 | 0.00 | no |
| rev | 4 | −0.77 | −2.19 | −4.2 | −0.006 | −0.5 | 0.00 | no |
| trend | 4 | 0.00 | −1.42 | −2.9 | −0.006 | −0.5 | 0.00 | no |
| ridge | 4 | +0.41 | −1.01 | −0.6 | 0.010 | 0.7 | 0.02 | no |
| gbm | 4 | −6.78 | −8.38 | −1.0 | 0.001 | 0.1 | 0.09 | no |
| tod | 26 | −0.65 | −2.03 | −2.3 | 0.045 | **3.4** | 0.00 | no |
| mom | 26 | +1.30 | −0.13 | −0.2 | 0.009 | 0.5 | 0.00 | no |
| rev | 26 | −1.07 | −2.50 | −3.3 | −0.009 | −0.9 | 0.00 | no |
| trend | 26 | +0.14 | −1.29 | −1.8 | −0.009 | −0.6 | 0.00 | no |
| ridge | 26 | −0.07 | −1.50 | −1.2 | 0.016 | 1.2 | 0.00 | no |
| gbm | 26 | +3.07 | +1.56 | 0.2 | 0.042 | 2.3 | 0.36 | no |
| *coin flip* | 4 / 26 | | −1.32 / −1.22 | | | | | |
| *always long* | 4 / 26 | | −0.48 / +0.07 | | | | | |

(Full table with dev out-of-fold rows: `ladder_results.csv`.)

What this says, from the bottom up:

* **The gross edges are a fraction of the cost.** The best gross numbers (momentum,
  +1.0 to +1.3 bp) are gold's 2023–26 uptrend, and they are still under 1.4 bp. The
  models aren't wrong about direction so much as there is almost nothing to be right
  about at a 4–26 hour horizon with these inputs.
* **The test had the power to find an edge.** Per-trade SD is about 33 bp. With
  3,000–4,500 holdout trades the standard error is about 0.5 bp, so a net edge of
  about 1.2 bp would have been detected with 80% power. This is not a
  sample-too-small null.
* **One signal replicates, and it can't pay for itself:** time of day.
  Dev IC t = 2.1, holdout IC t = 3.4 at H = 26. The rank ordering is real, but the
  best hours still don't clear the cost. It is more useful for *when* to execute
  than as a strategy.
* gbm H = 26 is +1.6 bp net on only 145 trades (t = 0.2, DSR 0.36). That is noise.

**Decision under the protocol: do not retrain the RL on these inputs.**

## Exploratory: how much the leak was worth

Same ridge rule and code, old parquets against rebuilt ones (`leak_probe.csv`):

| features | H | dev OOF IC (t) | holdout IC (t) |
|---|---:|---:|---:|
| old (leaky) | 4 | 0.061 (7.9) | 0.048 (2.7) |
| new (causal) | 4 | 0.011 (1.3) | 0.010 (0.7) |
| old (leaky) | 26 | 0.064 (7.4) | 0.059 (2.6) |
| new (causal) | 26 | 0.018 (2.2) | 0.016 (1.2) |

About 80% of the apparent predictability was look-ahead. The main channel is the
dollar: `dxf_chg5` correlates −0.049 with the same-horizon gold outcome when it
contains today's close, and −0.007 once lagged. Gold and the dollar move together
within the day, so knowing today's dollar close tells you today's gold move. The old
holdout used the same leaky macros, which is why it looked fine.

## Exploratory: the 168 existing RL policies on the same holdout

Causal features, filtered regimes, bracket fills, H = 4
(`rl_zoo_holdout_per_model.csv`):

* Median net −1.18 bp and gross +0.23 bp per trade; coin flip −1.40 ± 0.49.
* 4 of 168 net positive, none with t > 2, 85 with t < −2. Best DSR 0.02.
* Equal-weight zoo: −5.3 bp/day, HAC t = −7.0.
* **The share of long trades explains the zoo.** Regressing each policy's net mean
  on its long fraction gives R² = 0.66: −2.92 + 2.62 × long_frac. At 50% long that
  predicts −1.61 bp (the coin flip); at 100% long, −0.30 bp (always long). The
  residual SD across policies is 0.47 bp, the same as the coin flip's sampling SD
  (0.49). Once you know how often a policy was long, what is left is what 168 coin
  flips would give you.
* 81% of policies do worse than simply being long throughout.

## What would have to change

The learner is not the bottleneck; the information set is. Candidates, each needing
its own pre-registration:

1. **Inputs that carry information the price doesn't already have**, e.g. the
   news-geometry work, or flows/positioning (CFTC COT, ETF flows) at a daily horizon
   where cost is small relative to the move.
2. **Lower frequency.** At 1–5 days the typical move is 2–5× larger (√time) while the round-trip
   cost stays about 1.4 bp. The cost hurdle shrinks in proportion.
3. **Use time of day for execution**, not as a strategy: schedule entries of a daily
   strategy in the hours the ladder ranks best.
4. Stop the hourly cron until one of the above passes a pre-registered holdout.
