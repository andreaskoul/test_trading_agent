# Live window, out of sample: 1 Apr – 25 Sep 2026

All 168 policies in `artefacts/ppo_manifest.json` (84 PPO, 84 GRPO; 28 CPCV
splits × 3 seeds) were trained on 2012–2022 XAUUSD spot. Nothing after
31 Mar 2026 was used for training, model selection or tuning, so this is the
one clean test the project has. 2,824 hourly GC=F bars; gold fell 8.8%.

Reproduce: `TRADING_PROFILE=live python scripts/09_live_oos_eval.py && python scripts/10_live_oos_stats.py`

## How to read it

A trade is the unit of observation: unit notional, net of the cron's own cost
model (1 bp round-trip spread plus vol-scaled slippage, ~1.5 bp total). Each
trade the engine produced is priced three ways:

| execution | entry | exit |
|---|---|---|
| **engine** (what the code books, and what the training env rewarded) | close of the signal bar | barrier checked on the **close**, filled at the **barrier price** |
| **next** (market orders, what an hourly cron can do) | next bar open | next bar open after the close crosses |
| **bracket** (resting TP/SL orders) | next bar open | TP/SL on bar high/low, stop first if both touch, gaps fill at the open |

The engine rule is the problem. A stop only fires once a bar *closes*
through it, by which point the price is on average 21 bp past the stop, yet
the loss is booked at the stop level. 35% of trades exit this way, so that
alone adds about +7.5 bp per trade (the mirror effect on take-profits costs
about 3.5 bp). Wicks that touch the stop and recover are also never stopped
out. Under the engine rule a **coin flip earns +2.14 bp per trade after
costs**. Under either realistic rule it loses
1.5–1.9 bp, which is roughly the cost.

## Results (causal information set)

| | engine | next | bracket |
|---|---:|---:|---:|
| coin-flip benchmark, bp/trade | +2.14 | −1.46 | −1.89 |
| always-short benchmark, bp/trade | +3.75 | +0.51 | +0.76 |
| **deployed model** (m0, PPO split0 seed7), n=103 | −0.40 | −7.99 | −6.44 |
| HAC t | −0.13 | −1.56 | −2.13 |
| PSR(SR>0) | 0.46 | 0.09 | 0.06 |
| DSR (N=168) | 0.08 | 0.006 | 0.002 |
| p, sign-flip null | 0.38 | 0.87 | 0.90 |
| p, random-entry null | 0.74 | 0.88 | 0.86 |
| **zoo** median bp/trade | +1.97 | −2.07 | −2.45 |
| share of models with mean > 0 | 89% | 19% | 8% |
| models with HAC t > 2 | 20% | 0% | 0% |
| equal-weight daily P&L, HAC t | +4.53 | −3.42 | −3.30 |
| ex-post best model (m16 GRPO, 98% short), bp/trade | +9.02 | +7.11 | +4.27 |
| its DSR | 0.84 | 0.51 | 0.32 |

* The deployed model has no edge under any execution rule. It was not
  selected on anything: the manifest has no `sharpe` field, so the cron
  takes the first entry.
* The zoo's apparent edge under the engine rule (89% positive, t = 4.5) is
  the same size as the coin-flip's. The median model's result under the
  engine rule is indistinguishable from random entry.
* The best ex-post model is a short-gold bet in a year gold fell. Once you
  price it realistically and deflate for 168 trials, DSR is 0.32.
* Look-ahead (macro closes used on their own date, smoothed HMM regime,
  full-sample vol rank) changes little here: deployed n 103 → 116, zoo
  median +1.97 → +1.80 bp under the engine rule. The execution rule is what
  matters.

## Implications

The training env (`src/env/trading_env.py`, `embedding_env.py`) uses the
same close-check / barrier-fill rule, so every policy was rewarded in a world
where random trades are profitable, and trading more often helps. The earlier
holdout pass (Sharpe 1.09, bootstrap p = 0.001, but permutation p = 0.55)
matches that: the bootstrap tests whether the mean is positive, which the
execution rule guarantees; the permutation tests whether the timing matters,
and it didn't.

Before retraining: switch the env to bracket fills on high/low with next-open
entry, recompute the coin-flip benchmark under the new rule (it should be
≈ −cost), and only then compare policies against it.
