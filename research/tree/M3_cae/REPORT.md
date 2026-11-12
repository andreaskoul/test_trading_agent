# Branch M3: conditional autoencoder (Gu, Kelly and Xiu 2021)

*Saved by the coordinating session from the agent's final hand-back (its file write was refused).*

Beta network: ranked characteristics to K betas (CA0 linear, CA1 one hidden layer, CA2 two). Factor network: the week's characteristic-managed portfolios mapped linearly to K factors. Prediction beta x mean training factor. Early stopping on the reconstruction loss of the last 15% of training weeks.

| config | IC | t | years positive | decile net %/yr | net Sharpe |
|---|---:|---:|---:|---:|---:|
| ca2_c32_k3 | 0.0213 | 2.00 | 6 | +1.6 | +0.21 |
| ca1_c32_k3_alpha | 0.0177 | 1.92 | 5 | +0.4 | +0.06 |
| ca1_z5_k3 | 0.0189 | 1.87 | 6 | +1.0 | +0.13 |
| ca0_z5_k3 | 0.0154 | 1.59 | 6 | +0.1 | +0.02 |
| ca1_c32_k1 | 0.0145 | 1.19 | 5 | -0.3 | -0.04 |
| ca1_c32_k5 | 0.0094 | 1.15 | 5 | -0.7 | -0.13 |
| ca0_c32_k3 | 0.0100 | 1.07 | 5 | -0.2 | -0.03 |
| ca1_c32_k3 | 0.0010 | 0.12 | 4 | -2.9 | -0.48 |

Increment over MASTER (INCREMENT.jsonl): ca2_c32_k3 +0.0087 (t 0.91, corr 0.19), ca1_z5_k3 +0.0063 (t 0.78).

**Verdict: no finalist.** The factor structure does not beat direct prediction. Neighbouring settings swing by two standard errors (0.001 to 0.021 with 32 characteristics); a best-of-8 at t 2.0 is what selection alone gives. The 5-seed ensemble never ran.
