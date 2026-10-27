# Protocol 8 family H (historical, no LLM): result

**Verdict: no H signal enters Protocol 8.** The registered decision rule (§6) makes this final for family H:
* no deterministic network-and-filings book;
* no α or half-life from H8 for the §8 horizon mechanics (Amendment 4 §2).

The LLM thesis desk (R3) is decided separately, on ≥ 2 forward seasons (R5).

| step | what | outcome |
|---|---|---|
| Pre-registration | PREREG_thesis_tree.md and Amendments 4–6, each pushed before the statistics it governs | — |
| Fit sample (2012–21, descriptive) | `fit_results.md` | no registered effect; H1 indistinguishable from its placebo; H3b and H5 (S&P 400) of the opposite sign |
| Not runnable | H2b (TNIC needs a licensed gvkey link); H2 (32.5 S&P 400 suppliers a year with a named S&P 500 customer, against the registered 100) | p = 1 |
| Validation read (2022–25), made once | `VALIDATION_READ.md` (lock 08:03:49Z, b2e2cfd) | **S&P 400 H1 passes** (β −0.170, t −2.70, Holm p 0.032, halves ok, net +79 bp). S&P 500 H5 misses Holm (0.053). H4 has the opposite sign (t −2.76) |
| Post-read diagnostic | `VALIDATION_NOTES.md` | the H1 placebo mean is −0.043 (5 seeds): about ¾ of the validation effect is peer-specific |
| **Sealed read (Jan–Sep 2026), made once** | `SEALED_READ.md` (lock 08:23:03Z, f47edb4) | **H1 S&P 400 fails:** β **+0.041**, t +0.29, p 0.61, net spread −17 bp, 833 events |

**Reading.**
* The single validation survivor has the wrong sign on the sealed window.
  * Its fit-sample estimate was also null (t −0.57).
  * Of three samples, only 2022–25 shows the effect. That is the pattern of a sample-specific effect.
* The sealed rule required only the sign (Amendment 4), so the failure is not a matter of power.
  * With 833 events the sealed estimate is imprecise, se ≈ 0.14.
  * The point estimate is nevertheless on the wrong side of zero.
* Family-wise, the design behaved as its power analysis predicted (P8_readiness §1): no signal was strong enough to
  pass validation and the sealed read together.

**What survives as evidence for the fund (descriptive, not tests).**
* **Earnings information** (`decay_earnings.md`, fit sample) is priced over about 10–40 sessions, then fades or
  reverses. This supports Amendment 8's earnings horizons (base 20, up to 30), not multi-month holds.
* **Geopolitical shock days:** sector moves reverse over the next 20 sessions in 2022–25 (t −2.76). They do not
  drift.
* **H5 Lazy Prices** came close in the S&P 500, 2022–25 (t +2.83, Holm p 0.053). It is not a P8 component.
  * A new test of it would need a new pre-registration.
  * Its sample must be one not yet examined: forward months from November 2026.

**Data and code** (branch `research/p8-family-h`): prices with delisted names (`D1_coverage.md`), 8-K release
times and first-filed split-normalised EPS (`D5_D6_coverage.md`), the residual engine, the validated inference
engine (`inference_validation.txt`), filings text and the parser check (`sections_validation.md`), and the H tests
`research/p8/h*.py`.
