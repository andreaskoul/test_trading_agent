# Branch Q2_xsattn (Layer 3, Amendment 3): attention across names and market-state gating

*Written by the branch agent; saved by the coordinating session because the agent's writes were refused.
**Development data only (2013-2019); nothing here is out of sample.***

**Verdict: no.** Attention across names (full self-attention, an ISAB set transformer with 16 induced points, a
mean-pooled DeepSets context) and market-state gating (gated experts, MASTER's input gate) never beat their declared
ablations. Nominated pair at seeds 0-9: pooling −0.0007 vs the same network without it (Newey-West t −0.41). Full
self-attention on the best network −0.0033 (t −1.76); market-state expert gate −0.0035 (t −1.01); MASTER's input
gate 0.0000.

**Best configuration:** `moe_unif_d128`, the network without any module: development IC 0.0232 (seeds 0-2), 0.0237
(seeds 0-9), t 2.19, 6 of 7 years positive, decile book +1.0 to +1.4 %/yr net. No module candidate is nominated.
Against D's trees (0.0236): +0.0001 (t 0.02); score rank correlation 0.73 and weekly-IC correlation 0.94, so it
re-learns the trees' signal from the same 27 inputs. James-Stein factor 0 (branch mean 0.0173, SE about 0.010).

## Set-up

* One Thursday = one set of names (about 384 with a target, up to about 500 eligible).
* Inputs: D_ensembles' 27 features, ranked across names each day. Optional: `hist` (last 60 daily hedged returns,
  each divided by that day's cross-sectional sd); `na` (22 missing-value indicators).
* Label: per-week cross-sectional rank of y5, standardised (MASTER / Qlib CSRankNorm analogue).
* Loss: listwise, minus the per-week Pearson correlation of output with ranked label (differentiable IC); squared
  error and ListNet also tried.
* Network: linear token embedding, `depth` pre-norm residual MLP blocks per name; one cross block (attention across
  names then feed-forward; the ablation keeps the feed-forward and drops only the attention); K expert heads, averaged
  or gated by a softmax over 7 causal market-state numbers (trend 21/63/252, log vol 21, vol change, dispersion,
  average correlation; standardised on rows ≤ train_end); `fgate` = MASTER's market-guided input scaling.
* Training: AdamW lr 1e-3, weight decay 1e-3, batches of 8 weeks, ≤30 epochs; epochs chosen on the last 52 training
  Thursdays only with a 2-week gap (3-epoch moving mean of validation IC, patience 8); refit on all training
  Thursdays for that many epochs; Mac GPU (MPS).

## All configurations (353 weeks; shrunk IC 0.0173 for every row)

| name | spec | IC | t | yrs+ /7 | decile net %/yr | net Sharpe |
|---|---|---|---|---|---|---|
| mlp_base | d64, depth 2, FF block, 1 head (ablation) | 0.0208 | 2.04 | 6 | +0.6 | 0.09 |
| mlp_isab | + ISAB attention | 0.0213 | 2.00 | 6 | +0.1 | 0.01 |
| mlp_sab | + full self-attention | 0.0221 | 2.07 | 6 | +0.8 | 0.11 |
| mlp_pool | + mean-pool context | 0.0222 | 2.10 | 6 | +1.5 | 0.21 |
| mlp_fgate | + MASTER input gate | 0.0208 | 2.15 | 6 | +1.4 | 0.21 |
| moe_unif | 4 heads, uniform (ablation) | 0.0225 | 2.14 | 6 | +0.3 | 0.04 |
| moe_gate | 4 heads, market-state gate | 0.0189 | 1.80 | 6 | +0.2 | 0.02 |
| moe_sab | moe_unif + self-attention | 0.0209 | 1.95 | 6 | 0.0 | 0.00 |
| hist_base | + 60-day history (ablation) | 0.0012 | 0.17 | 4 | −4.9 | −1.04 |
| hist_isab | hist_base + ISAB | 0.0090 | 1.24 | 4 | −4.1 | −0.77 |
| hist_sab | hist_base + self-attention | 0.0012 | 0.18 | 4 | −4.6 | −0.91 |
| moe_unif_na | + missing indicators | 0.0205 | 1.86 | 6 | +0.6 | 0.09 |
| moe_unif_listnet | ListNet loss | 0.0005 | 0.06 | 3 | −1.6 | −0.23 |
| moe_unif_mse | squared error on the rank | 0.0143 | 1.31 | 6 | −0.7 | −0.10 |
| **moe_unif_d128** | d128, depth 3, 4 uniform heads (ablation) | **0.0232** | 2.19 | 6 | +1.0 | 0.14 |
| d128_pool | + mean-pool context | 0.0222 | 2.09 | 6 | +1.1 | 0.16 |
| d128_sab | + full self-attention | 0.0199 | 1.87 | 6 | −0.4 | −0.06 |
| **moe_unif_d128_s10** | the same network, seeds 0-9 | **0.0237** | 2.19 | 6 | +1.4 | 0.19 |
| d128_pool_s10 | d128_pool, seeds 0-9 | 0.0230 | 2.10 | 6 | +1.0 | 0.13 |

Every configuration with IC above 0.01 is negative in 2016 (about −0.025) and strongest in 2015 (about +0.055).
Registered but not run: `moe_sab_na_inner3`, `moe_unif_na_inner3` (dropped before scoring, reason logged: the missing
indicators had lowered IC); `d128_sab_s10` (as registered, only the better module on d128 got a 10-seed run).

## Module vs ablation (paired weekly IC difference, Newey-West t, 4 lags)

| module | ablation | diff | NW t | yrs diff>0 |
|---|---|---|---|---|
| mlp_isab | mlp_base | +0.0005 | 0.24 | 2 |
| mlp_sab | mlp_base | +0.0013 | 0.63 | 4 |
| mlp_pool | mlp_base | +0.0014 | 0.46 | 5 |
| mlp_fgate | mlp_base | −0.0000 | −0.01 | 3 |
| moe_gate | moe_unif | −0.0035 | −1.01 | 3 |
| moe_sab | moe_unif | −0.0016 | −0.56 | 2 |
| hist_isab | hist_base | +0.0078 | 2.18 | 5 |
| hist_sab | hist_base | +0.0000 | 0.01 | 3 |
| d128_pool | moe_unif_d128 | −0.0010 | −0.49 | 3 |
| d128_sab | moe_unif_d128 | −0.0033 | −1.76 | 1 |
| **d128_pool_s10 (nominated pair)** | **moe_unif_d128_s10** | **−0.0007** | **−0.41** | 3 |

**Reading.** Attention across names adds about +0.001 on the small network (never t above 0.7) and subtracts on every
larger or multi-head network. The one significant pair (hist_isab vs hist_base, t 2.18) is attention partly repairing
a network the raw history broke; hist_isab is still 0.0118 below mlp_base. The market-state gate hurts and MASTER's
input gate does nothing, consistent with E_regime (only a hand-set momentum-off-in-panic rule survived). What
mattered: the listwise IC loss beats squared error on the rank by 0.008 (ListNet fails); 4 heads + d128 + depth 3
add about +0.002 (not significant); the raw 60-day history input costs 0.020.

## References (same weeks)

| reference | IC | best minus ref | NW t |
|---|---|---|---|
| D trees hgb_multihorizon (0.0236 bar) | 0.0236 | +0.0001 | 0.02 |
| D trees hgb, 5-session target | 0.0216 | +0.0021 | 0.55 |
| MASTER h5 reference (reference row, not an input) | 0.0125 | +0.0111 | 1.24 |

Reproduction: `repro.py` (seeds 0-2) gives IC 0.02320, matching the log (`repro.json`). MPS is not guaranteed
bit-deterministic; expect ±0.001.

## Caveats

* Development panel: 241 of 738 ever-eligible names unpriced; 23.5% of eligible name-weeks without a target.
  Attention sees only priced names; a cross-name module may be handicapped by the missing ones.
* S&P 500 names only; MASTER's cross-name gains were on CSI300/800 and may need broader universes.
* 19 configurations on the same 7 years; shrinkage removes the best's whole margin. Seed noise: 0.0232 → 0.0237.
* Returns: decile top-minus-bottom, 0.5 gross a side, 5 bp per side on names replaced, % per year.

## Process notes

* The first runs wrote RESULTS.jsonl to a nested relative path; moved, path made absolute, nothing lost.
* The old ledger script dropped mlp_base and moe_unif from `scored` and put spec strings in `pending`; rebuilt from
  RESULTS.jsonl, nothing re-scored.

Files: `model.py` (`fit_predict` = best; `make(**cfg)` any configuration), `run.py`, `analyze.py`, `analysis.json`,
`repro.py`, `repro.json`, `RESULTS.jsonl`, `STATE.json`. Predictions: `.cache/tree/preds/Q2_xsattn/`.
