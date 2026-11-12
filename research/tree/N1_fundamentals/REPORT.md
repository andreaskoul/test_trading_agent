# Branch N1: accounting fundamentals on top of MASTER

*Saved by the coordinating session from the agent's hand-back (its file write was refused).*

Development 2013-2019, 353 weeks. Base MASTER IC 0.0125. Gate: increment t >= 1.5. 9 configurations plus 15 single
characteristics (`RESULTS.jsonl`, `RESULTS_DML.jsonl`).

| configuration | IC | increment | incr. t | years + of 7 | corr MASTER | net %/yr | net Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|
| comp_blend70 (registered no-fit composite, 0.7/0.3) | .0152 | +.0027 | 1.61 | 5 | .93 | -0.5 | -0.08 |
| comp_blend50 (0.5/0.5) | .0156 | +.0031 | 0.84 | 5 | .71 | +0.5 | +0.10 |
| fm_ridge (MASTER weight fitted) | .0180 | +.0055 | 1.01 | 5 | .57 | +0.4 | +0.08 |
| hgb_blend (trees on fundamentals + Z, 0.7) | .0165 | +.0039 | 2.27 | 6 | .93 | -0.2 | -0.03 |
| hgb_zonly_blend70 (check: Z only) | .0148 | +.0023 | 1.23 | 6 | .94 | -0.4 | -0.06 |
| hgb_fundonly_blend70 | .0135 | +.0009 | 0.59 | 4 | .91 | +0.1 | +0.01 |
| **fm_fixed70** (Fama-MacBeth fundamentals, fixed 0.7) | **.0172** | **+.0047** | **2.29** | **6** | .91 | +0.4 | +0.07 |
| comp_lit7_blend70 | .0149 | +.0023 | 1.38 | 5 | .93 | -0.4 | -0.06 |

Double ML (composite; MASTER and Z partialled out with cross-fitted trees): theta 0.0097, t 2.10, positive 5 of 7
years; MASTER and Z explain none of the composite's variance.

Singles (no MASTER): composite IC .0102 (t 2.14), 4.5% of its top decile replaced weekly; payout/assets .0118 (t 2.04);
SUE .0091 (2.01); R&D/assets .0197 (2.20, 29% coverage); CFO/assets .0102 (1.77); accruals .0083 (1.59); gross
profitability .0028; asset growth and leverage wrong sign. All correlations with MASTER |r| <= 0.06.

**Verdict:** fundamentals add to MASTER. Finalist `model.py` = fm_fixed70 (increment t 2.29), chosen after seeing 9
configurations; the registered no-fit fallback comp_blend70 has t 1.61. Caveats: about 600 of 850 names matched; no
price level, so no book-to-market or yield; the holdout read needs the builder extended past 2019 filings.
