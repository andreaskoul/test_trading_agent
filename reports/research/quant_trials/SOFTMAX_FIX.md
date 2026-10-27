# The softmax fix (Barron, Gnanapragasam & Tschannen, arXiv 2610.31642) on our models: result (2026-10-25)

PREREG_quant_transformers.md Amendment 3, part F. Only training and validation rows of the 2013 refit window were
used; no test year was touched. Raw numbers: `softmax_diag.json`.

**Verdict: the fix is not adopted for any model.** It would change nothing measurable. Timestral is inference-only,
so the fix does not apply to it.

## Port and tests
* `softmax_fix.py` implements `fixed_log_softmax`/`fixed_softmax`: the max-excluded log-sum-exp plus softplus,
  with the max entry's gradient formed as the negative sum of the others'.
* `test_softmax_fix.py` covers 5 contract tests:
  * matches torch below the cliff;
  * the top-class gradient survives past the cliff, against the exact value;
  * zero-sum gradients;
  * the attention-style gradient matches an exact reference;
  * attention-mask entries are not counted as margins.
* **Measured error of standard fp32 softmax** on the top entry's attention gradient:

  | Margin | Standard fp32 error | Fixed error |
  |---|---|---|
  | 10 | 0.2% | ~1e-7 at every margin |
  | 15 | 17% | ~1e-7 |
  | > 16.6 | 100% | ~1e-7 |

## F1: how often our models reach the cliff
Each row is one softmax row seen during training on the 2013 window. The margin m is the top logit minus the
log-sum-exp of the others.

| Model | Softmax site | Rows | Share with m > 15 | Max m | Rule (per site < 0.1%) |
|---|---|---|---|---|---|
| TFT h10 | attention (n = 71), variable selection (n = 7) | 25.0M | 0 | 2.0 | no-op |
| Chronos-2-ft | attention, eager (`layers.py:234`) | 34.9M | 0.029% | 35.0 | no-op |
| MASTER h5, 5 seeds | cross-stock attention (`master.py:132`) | 130–370M per seed | ≤ 0.00001% | 9.3–18.2 | below |
| MASTER h5, 5 seeds | **temporal attention over the 8-day window (`master.py:168`)** | 4.1–11.6M per seed | **1.3–4.7%** | **81–89** | **crossed** |
| MASTER h5, 5 seeds | feature gate (`master.py:155`) | 4.1–11.6M | 0 | < 0 | below |

**MASTER's temporal attention** often puts almost all of its weight on one of the 8 days. In fp32, the gradient
through that top weight is then lost: Softmax Collapse.

## F2: does fixing it change MASTER? Validation IC, 2013 window, 5 seeds

| Seed | 0 | 1 | 2 | 3 | 4 | Mean |
|---|---|---|---|---|---|---|
| Standard | 0.0375 | 0.0309 | 0.0303 | 0.0281 | 0.0488 | 0.0351 |
| Fixed | 0.0373 | 0.0304 | 0.0302 | 0.0278 | 0.0489 | 0.0349 |

* **Δ (fixed − standard): −0.0002**, seed SE 0.0001.
* **The rule** (Δ > 2 SE, and positive) **is not met.** F3 does not run: there is no fixed-softmax forward-book
  arm.
* **Reproducibility check:** standard seed 0 reproduces the signed read's first-refit validation IC exactly
  (0.03753097862995734).

**Why the fix doesn't matter here, though the collapse is real.** The lost gradient only pushes an
already-saturated attention to be more saturated. MASTER is trained with MSE and early-stopped on validation rank
IC, not driven to extreme confidence like the paper's grokking runs, so the missing push changes the fitted model
by noise only. The paper's fix targets cross-entropy training at large margins, where the lost gradient is the
signal; none of our models trains that way.
