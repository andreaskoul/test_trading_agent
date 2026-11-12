# Branch M6: self-supervised return embeddings

*Saved by the coordinating session from the agent's hand-back (its file write was refused).*

3-layer 1-D CNN encoder, 16-dim embedding of the last 60 volatility-scaled hedged returns, pre-trained without labels on windows ending at or before train_end: masked reconstruction (mae), contrastive InfoNCE (con), co-movement / Stock2Vec (com). Frozen embedding ranked and used in a pooled ridge; control = the same ridge without it.

| config | IC | t | years positive | decile net %/yr | net Sharpe |
|---|---:|---:|---:|---:|---:|
| ctrl_Z | 0.0195 | 1.97 | 6 | +1.2 | +0.17 |
| com16_emb | -0.0007 | -0.10 | 4 | -4.5 | -0.95 |
| com16_embZ | 0.0097 | 1.09 | 4 | -3.0 | -0.47 |
| com16_peerZ | 0.0197 | 2.01 | 6 | +1.0 | +0.15 |
| mae16_emb | 0.0058 | 0.96 | 5 | -1.1 | -0.26 |
| mae16_embZ | 0.0176 | 1.87 | 6 | +0.3 | +0.05 |
| con16_emb | 0.0100 | 1.76 | 6 | -0.1 | -0.02 |
| con16_embZ | 0.0191 | 2.08 | 6 | +1.7 | +0.25 |
| ctrl_C | 0.0164 | 1.67 | 6 | +0.2 | +0.03 |
| con16_embC | 0.0168 | 1.82 | 6 | +0.2 | +0.04 |
| con16_peerC | 0.0161 | 1.64 | 6 | +0.2 | +0.04 |
| con16_peerZ | 0.0185 | 1.89 | 6 | +0.4 | +0.06 |

Embedding minus control (paired weekly IC, Newey-West t): mae+Z -0.0019 (-0.88); con+Z -0.0004 (-0.12); com+Z -0.0098 (-2.16); com peer+Z +0.0002 (0.15); con peer+Z -0.0010 (-1.05); con+C +0.0004 (0.19); con peer+C -0.0003 (-0.50).
Increment over MASTER: com16_peerZ +0.0071 (t 0.87); con16_embZ +0.0066 (t 0.79), both from the characteristics, not the embedding.

**Verdict: no finalist.** The embeddings carry a weak signal alone (contrastive IC 0.010) that the characteristics already contain; co-movement embeddings hurt. One encoder size, linear heads only.
