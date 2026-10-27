# Notes on the validation read (written after it; nothing here changes a pass or a failure)

## The registered result (VALIDATION_READ.md, commit 00b5b31)

* **Passes:** S&P 400, **H1 sympathy reversal**.
  * β −0.170, t −2.70; p_wild 0.0023, p_RI 0.0045; Holm p 0.032.
  * Both halves negative (−0.106 in 2022–23, −0.230 in 2024–25).
  * Net tercile spread +79 bp per event, after 20 bp.
* **Near miss:** S&P 500, H5 Lazy Prices. p 0.0075, Holm p 0.053 (7 × 0.0075 > 0.05). The halves and the net spread
  (+118 bp) were in order. Under the pre-registration it does not pass, and it is not re-read.
* **Opposite sign:** H4, t −2.76. Sector moves on geopolitical shock days reverse over the next 20 sessions; they do
  not drift.

## Post-read diagnostic: H1's placebo on validation (descriptive)

Peers are drawn at random from other sub-industries of the same season, with the same count, using five seeds and
B = 1,999. The code is `research/p8/h1_placebo_validation.py`.

| seed | β | t |
|---|---|---|
| 1 | −0.012 | −0.14 |
| 2 | −0.073 | −1.02 |
| 3 | −0.073 | −0.79 |
| 4 | −0.051 | −0.82 |
| 5 | −0.004 | −0.05 |

* The placebo mean is −0.043 and no seed is significant. The same-sub-industry peers give −0.170.
* About three quarters of the effect is peer-specific (−0.13 beyond the placebo mean). The rest is the firm's
  generic short-term reversal, which the registered statistic does not remove.
* On the fit sample the two were not distinguishable (−0.049 vs −0.099).

## Caveats that travel with the pass
1. **Sample.** The S&P 400 is today's list (survivors), and the GICS sub-industries that define the peers are
   today's (Amendment 4 D3).
2. **Fit vs validation.** The fit-sample statistic was weak (2017–21: β −0.049, t −0.57). The effect is stronger in
   2022–25, so it may be regime-dependent.
3. **Capacity.** A median of 3 peers per event; mid-caps; a 3-day window around the late firm's report. The net
   spread already deducts 10 bp per leg. Mid-cap costs may be higher (Amendment 4 takes 2 × the S&P 500 cost
   for §8's margin).

## Next registered step
The sealed read (Amendment 4 §1): S&P 400 H1 only, on reports with t0 in Jan–Sep 2026. It passes if β < 0 and the
net tercile spread > 0. It is made once, with data never loaded before.
