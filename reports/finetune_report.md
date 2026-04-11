# Finetune Report

- Base policy : split=5, seed=29
- Holdout window: last 3832 bars (not seen during encoder pretrain or PPO training)

## Held-out metrics

| Metric | Before | After | Delta |
|:--|---:|---:|---:|
| Trades | 370 | 345 | -25 |
| Sharpe | -0.439 | +0.713 | +1.151 |
| Sortino | -0.896 | +2.078 | +2.974 |
| Max DD | -0.191 | -0.087 | +0.104 |
| Hit rate | 0.373 | 0.438 | +0.065 |
| Total return | -0.174 | +0.311 | +0.485 |