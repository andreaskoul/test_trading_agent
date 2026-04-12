# Finetune Report

- Base policy : algo=ppo, split=4, seed=7
- Holdout window: last 3832 bars (not seen during encoder pretrain or PPO training)

## Held-out metrics

| Metric | Before | After | Delta |
|:--|---:|---:|---:|
| Trades | 350 | 374 | +24 |
| Sharpe | +1.090 | +1.164 | +0.074 |
| Sortino | +2.954 | +3.282 | +0.328 |
| Max DD | -0.073 | -0.080 | -0.007 |
| Hit rate | 0.457 | 0.457 | +0.000 |
| Total return | +0.587 | +0.637 | +0.050 |