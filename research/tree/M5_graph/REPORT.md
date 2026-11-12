# Branch M5: peer graph on 10-K text neighbours

*Saved by the coordinating session from the agent's hand-back (its file write was refused).*

Year y's 10-K text-neighbour graph used for sessions in year y. Hand-built peer features in branch C's Fama-MacBeth ridge (R*), and GraphSAGE / graph attention in plain torch (G*), each paired with the same model without edges.

| config | IC | t | years positive | decile net %/yr | net Sharpe |
|---|---:|---:|---:|---:|---:|
| R0_C24_fm | 0.0208 | 2.30 | 6 | -1.1 | -0.17 |
| R1_peerrev_alone | 0.0061 | 1.11 | 6 | -0.0 | -0.01 |
| R2_Z5_peer | 0.0095 | 1.16 | 6 | -0.3 | -0.05 |
| R3_C24_peer | 0.0177 | 2.11 | 6 | -0.5 | -0.09 |
| G0_mlp_C24 | 0.0129 | 1.51 | 6 | -2.7 | -0.48 |
| G1_sage_C24 | 0.0063 | 0.77 | 5 | -3.6 | -0.64 |
| R4_C24_peermomrev | 0.0186 | 2.21 | 6 | -0.4 | -0.08 |
| G4_mlp_Z5 | 0.0155 | 1.81 | 6 | -1.0 | -0.18 |
| G5_sage_Z5 | 0.0085 | 1.04 | 6 | -1.9 | -0.33 |
| G2_gat_C24 | 0.0135 | 1.56 | 6 | -2.2 | -0.40 |
| G6_mlp_C24_reg | 0.0135 | 1.47 | 5 | +0.3 | +0.04 |
| G7_sage_C24_reg | 0.0115 | 1.33 | 5 | -1.3 | -0.24 |
| G3_sage2_C24 | 0.0041 | 0.50 | 4 | -3.7 | -0.64 |

Graph minus its no-graph control (paired weekly IC): R4 -0.0022 (t -1.04), R3 -0.0030 (-0.92), G1 -0.0066 (-2.00), G2 +0.0005 (+0.24), G3 -0.0088 (-2.41), G5 -0.0070 (-1.58), G7 -0.0020 (-1.11).
Increment over MASTER: R4 +0.0060 (t 0.76), R3 +0.0052 (t 0.66).

**Verdict: no finalist.** Edges lowered IC in 6 of 7 pairs; graph attention only matched its control by weighting the stock itself. Consistent with research/riskfield: text-neighbour contagion is intraday, not weekly.
