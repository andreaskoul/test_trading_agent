# Finetune Report

- Base policy : split=1, seed=13
- Holdout window: last 3832 bars (not seen during encoder pretrain or PPO training)

## Held-out metrics

| Metric | Before | After | Delta |
|:--|---:|---:|---:|
| Trades | 371 | 362 | -9 |
| Sharpe | +1.370 | +1.472 | +0.102 |
| Sortino | +4.685 | +4.342 | -0.343 |
| Max DD | -0.067 | -0.075 | -0.008 |
| Hit rate | 0.450 | 0.494 | +0.044 |
| Total return | +0.875 | +0.877 | +0.002 |