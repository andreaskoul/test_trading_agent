# Branch B, network architecture: report (INTERIM, 6 of ~12 configurations scored; round 2 running)

Fixed loss: MSE on the per-date z-scored 5-session hedged return (clipped +-3). AdamW, 6 epochs, Thursdays only.

| name | IC | t | years + /7 | decile net %/yr |
|---|---|---|---|---|
| mlp_Z_xattn | 0.0141 | 1.52 | 6 | -0.4 |
| mlp_Z | 0.0135 | 1.47 | 6 | -1.0 |
| mlp_Z_gate | 0.0117 | 1.48 | 6 | -1.4 |
| gru_e20 | 0.0109 | 1.45 | 5 | -1.1 |
| cnn_e60 | 0.0053 | 0.85 | 3 | -3.6 |
| tfm_e60 | 0.0015 | 0.23 | 4 | -3.5 |

Interim best: mlp_Z_xattn (model.py). Nothing is distinguishable from noise or from the MASTER reference (0.0125).
