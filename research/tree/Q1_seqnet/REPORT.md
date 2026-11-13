# Branch Q1_seqnet (Layer 3, Amendment 3): sequence networks on 60-session histories

*Written by the branch agent; saved by the coordinating session because the agent's writes were refused.
**Development data only (2013-2019, 353 Thursdays); nothing here is out of sample.***

**Verdict: no.** Sequence encoders (GRU, LSTM, causal dilated TCN, small time-axis transformer) on each name's last 60
sessions add nothing measurable to direct characteristics. The best configuration beats the declared control, but
the gain comes from the richer inputs (D trees' 27) and the IC loss, not the sequence model. It does not beat the D
trees. If anything is carried forward, it is the cheap static form `mlp_D27_ic` (IC 0.0202, 3.5 minutes per
walk-forward); the GRU costs 3-9× the compute and adds nothing.

**Best: `gru60_D27_ic_es`** (`model.py`): GRU (32 units) over 60 sessions of residual returns, raw returns, market
return and rank of absolute residual return (volume proxy), joined with an MLP on D's 27 inputs; IC loss (negative
per-week correlation of standardised outputs with the rank target); inner early stopping (≤ 12 epochs, best epoch by
IC on the last 52 training Thursdays with an 8-row gap; validation year never used).

| | IC | Difference | Newey-West t (4 lags) |
|---|---|---|---|
| Best, seeds 0-2 | 0.0225 (t 2.27, 6 of 7 years positive) | | |
| Best, seeds 0-9 (`model.py`) | **0.0206** (t 2.16) | | |
| vs control (0.0141), seeds 0-2 | | +0.0084 | 1.81 |
| vs control, seeds 0-9 | | +0.0065 | 1.19 |
| vs the same network without the encoder (`mlp_D27_ic_es`), seeds 0-9 | | +0.0003 | 0.05 |
| vs D trees, 5-session (0.0216), seeds 0-9 | | −0.0010 | −0.18 |
| vs D trees, multi-horizon (0.0236), seeds 0-9 | | −0.0030 | −0.54 |

About 0.002 of the 3-seed IC was seed luck; 0.0206 is the honest estimate. `model.py` check (`REPRO.json`, 2013-2014,
seeds 0-2): IC 0.00922 vs 0.00922 and 0.03531 vs 0.03533; rank differences ≤ 0.001 (MPS floating point).

## All configurations

Declared control: `B_arch/model.py` (mlp_Z_xattn) on the same rows. Static inputs: Z (5), D's 27, or D 27 + C 32
(DC). Targets: per-date ranks of the 5-session return. Seeds 0-2 except `_s10`.

| name | spec | IC | t | years +/7 | decile net %/yr | shrunk (iid) | shrunk (paired) | diff vs control | NW t |
|---|---|---|---|---|---|---|---|---|---|
| ref_control | B_arch mlp_Z_xattn (control) | 0.0141 | 1.52 | 6 | −0.4 | 0.0171 | 0.0156 | – | – |
| gru60_Z_mse | GRU + Z, MSE | 0.0144 | 1.57 | 6 | −0.1 | 0.0171 | 0.0158 | +0.0003 | 0.08 |
| lstm60_D27_mse | LSTM + 27, MSE | 0.0161 | 1.61 | 5 | −2.4 | 0.0171 | 0.0166 | +0.0021 | 0.37 |
| mlp_D27_ic | no encoder, 27 inputs, IC loss | 0.0202 | 1.86 | 6 | 0.7 | 0.0171 | 0.0186 | +0.0062 | 1.13 |
| lstm60_D27_ic | LSTM + 27, IC loss | 0.0208 | 1.92 | 6 | 0.6 | 0.0171 | 0.0189 | +0.0068 | 1.40 |
| tcn60_D27_ic | TCN + 27, IC loss | 0.0093 | 0.98 | 5 | −4.1 | 0.0171 | 0.0133 | −0.0047 | −0.82 |
| tfm60_D27_ic | time-axis transformer + 27, IC loss | 0.0095 | 1.11 | 6 | −3.2 | 0.0171 | 0.0134 | −0.0045 | −0.86 |
| gru60_D27_ic | GRU + 27, IC loss | 0.0217 | 2.07 | 6 | 0.3 | 0.0171 | 0.0194 | +0.0076 | 1.66 |
| **gru60_D27_ic_es** | + inner early stopping | **0.0225** | 2.27 | 6 | −0.6 | 0.0171 | 0.0198 | +0.0084 | 1.81 |
| gru60_D27_ic_mh | + 10- and 21-session heads | 0.0219 | 2.04 | 6 | 0.0 | 0.0171 | 0.0195 | +0.0079 | 1.62 |
| gru60_D27_ic_inorm | + per-window scaling of return channels | 0.0207 | 2.00 | 6 | 0.3 | 0.0171 | 0.0189 | +0.0067 | 1.48 |
| gru60_D27_ic_miss | + missing-value indicator channel | 0.0205 | 1.95 | 6 | 0.7 | 0.0171 | 0.0188 | +0.0065 | 1.49 |
| gru60_DC_ic | static D 27 + C 32 | 0.0197 | 1.89 | 6 | 0.3 | 0.0171 | 0.0184 | +0.0056 | 1.38 |
| gru60_D27_ic_vol | + FINRA abnormal-volume channel (2012+) | 0.0181 | 1.76 | 6 | 0.2 | 0.0171 | 0.0176 | +0.0041 | 0.97 |
| gru60_D27_ic_reg | weight decay 1e-2, dropout 0.3 | 0.0215 | 2.18 | 6 | 0.2 | 0.0171 | 0.0193 | +0.0075 | 1.73 |
| gru60_D27_listnet | ListNet loss | −0.0038 | −0.42 | 4 | −2.4 | 0.0171 | 0.0069 | −0.0178 | −1.05 |
| mlp_D27_ic_es | no encoder, same early stopping | 0.0202 | 1.84 | 5 | 2.0 | 0.0171 | 0.0187 | +0.0062 | 1.00 |
| gru60_D27_ic_es_s10 | best, seeds 0-9, via `model.py` | 0.0206 | 2.16 | 6 | 0.1 | 0.0171 | 0.0188 | +0.0065 | 1.19 |

**Shrinkage** (X5's James-Stein formula): branch mean 0.0171. With iid noise every configuration shrinks fully to the
mean; with paired noise the factor is 0.49 and the best shrinks to 0.0198. Best's weekly IC sd 0.186 vs branch median
0.191 (not flagged).

**Paired comparisons (NW t, 4 lags):** GRU vs same network without it (6 epochs) +0.0014 (t 0.56); LSTM vs without
+0.0006 (t 0.26); best (seeds 0-2) vs no-encoder with the same early stopping +0.0022 (t 0.55); static MLP with IC
loss vs control +0.0062 (t 1.13); best (seeds 0-2) vs D trees +0.0009 (t 0.19). Not used for selection: best (seeds
0-9) has rank correlation 0.58 with D trees and 0.66 with the control; a 50/50 rank blend with D trees has IC 0.0237
(t 2.41).

## Findings

1. **Encoders add nothing distinguishable**: every gain from adding one to the matched static network is < 0.0025 IC,
   t ≤ 0.6. The static MLP with IC loss already reaches 0.0202.
2. **TCN and the transformer hurt** (about 0.0095 IC), at one size and one regularisation setting only.
3. **Losses**: IC loss beats MSE (LSTM 0.0161 → 0.0208); ListNet failed (−0.0038), not investigated or re-tuned.
4. **Other variants did not help** (vs gru60_D27_ic 0.0217): multi-horizon heads 0.0219; per-window scaling 0.0207
   (the expected null); missing indicator 0.0205; D 27 + C 32 0.0197; FINRA volume 0.0181 (exists only from 2012);
   heavier regularisation 0.0215; early stopping 0.0225 at 3 seeds, 0.0206 at 10 (seed noise).
5. **The D trees are not beaten** (−0.0010 and −0.0030 at seeds 0-9; not significant).

## Caveats

* Development panel survivorship gap (241 of 738 names unpriced; 23.5% of eligible name-weeks without a target); all
  ICs on the same rows, so paired differences beat levels.
* Run times 4-19 minutes; early stopping 28 and the seeds 0-9 run 56 (above target; shared machine; Python under
  Rosetta).
* ListNet's first attempt crashed before scoring (an operation not implemented on MPS); fixed with a shared softmax
  shift that does not change the loss; the crashed attempt logged nothing.
* The old ledger script rewrote STATE.json once; `run.py` now rebuilds it from RESULTS.jsonl.

Files: `model.py`, `seq.py`, `run.py`, `configs.json`, `report.py`, `repro.py`, `REPRO.json`, `RESULTS.jsonl`,
`STATE.json`, `log_*.json`. Predictions: `.cache/tree/preds/Q1_seqnet/<name>.npy`.
