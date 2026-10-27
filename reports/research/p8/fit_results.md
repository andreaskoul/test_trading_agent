# P8 family H: fit-sample results (2012–2021), descriptive only

These numbers decide nothing. They come from the fit sample, which §1 reserves for estimation. They are recorded
here so the validation read can be compared with them, and so that the operational choices are visibly fixed
first: Amendment 5 (281fa94) was pushed before any of these statistics existed.

The inference is the registered one: B = 9,999, one-sided in the registered direction, and p = max(p_wild, p_RI)
for event tests.

| test | universe | n | statistic | t | p (wild / RI) | net spread | placebo t |
|---|---|---|---|---|---|---|---|
| H1 sympathy reversal (−) | S&P 500 | 8,727 | β −0.0010 | −0.03 | 0.48 / 0.48 | −38 bp | −0.82 |
| H1 | S&P 400 (2017–21) | 4,699 | β −0.049 | −0.57 | 0.29 / 0.29 | −17 bp | −1.33 |
| H3a funnel lead-lag (+) | S&P 500 | 119 months | −5.7 bp per sd | −1.04 | 0.84 | L/S net −19 bp/month | −1.16 |
| H3a | S&P 400 (2017–21) | 60 months | +6.7 bp per sd | +0.58 | 0.29 | net −10 bp/month | +0.53 |
| H3b bullwhip (+), SUE at t0 | S&P 500 | 4,984 | β −0.78 | −2.47 | 0.99 / 0.99 | CAR net −6 bp | +0.08 |
| H3b | S&P 400 | 3,846 | β −0.018 | −0.25 | 0.60 / 0.60 | CAR net −9 bp | +0.78 |
| H4 geopolitical drift (+) | 11 sectors | 3,369 (333 days) | β +0.142 | +0.91 | 0.41 / 0.21 | −15 bp | — |

**Notes, recorded before any validation read.**
* **H1.**
  * The placebo (random peers from other sub-industries) is as negative as the true peers. Any negative slope
    is therefore generic short-term reversal of the firm's own residual return, not sympathy.
  * The S&P 500 β moved from −0.021 to −0.001 when the pre-2016 residual switched from market-only to sector
    (`yf_etf_close.parquet`). The result is sensitive to the residual definition.
* **H3a.** The true stage structure and the shuffled-stage placebo give almost the same slope (S&P 500: −5.7 vs
  −6.3 bp). The funnel's stage order adds nothing over chance on fit data.
* **H3b.** The registered primary (SUE at the same report) has the opposite sign (t −2.47), and the
  registered secondary (the next report's SUE) has the registered sign (t +2.04). That is consistent with a lag
  of one more quarter.
  * Winsorising the ratios at 1/99% weakens the primary to t −1.39. It is fragile.
  * **The primary is not changed.** Changing it because of this table would be a specification search. Only the
    owner can amend it, explicitly and before the validation read.
* **H4.** Threat and act days behave alike (t +0.85, +0.97).
* **Coverage limits** (also stated in Amendment 5 A):
  * the S&P 400 enters at 2017 (Alpaca prices from 2016, plus a 273-session beta window);
  * GICS (sub-industry, chains) exists only for firms on today's lists, so the GICS-based tests (H1, H3a, H3b)
    cover surviving firms only;
  * 162 delisted symbols have no CIK.

## H5 Lazy Prices: fit sample, and the replication check (Amendment 5)

| universe | months | slope (3-month target) | t | p | L/S net | rank-signal robustness |
|---|---|---|---|---|---|---|
| S&P 500 | 117 | +0.7 bp per sd | +0.10 | 0.46 | +13 bp | −6.3 bp, t −0.71 |
| S&P 400 (2017–21) | 59 | −52.6 bp per sd | −1.98 | 0.97 | −113 bp | −52.9 bp, t −2.37 |

**Replication outcome.**
* **S&P 500:** the published sign reproduces, but only barely, and not in the rank version.
* **S&P 400:** the sign does not reproduce.

**Code audit** (the registered reading of a failed replication is "the code is wrong"):
* one filing's similarity, recomputed by hand: identical (0.985953);
* signal timing: 400 random rows checked against their filings, 0 mismatches;
* signals at most 120 days old: no change (S&P 400 t −2.07).

**Diagnosis.**
* The S&P 400 reversal comes from 2020: −244 bp per sd. Every other year lies between −39 and +14 bp.
* Amendment 2 already flags 2020–21 as the COVID regime.
* The S&P 400 sample is also today's list (survivors), which favours firms whose large changes went well.

No code error was found. H5 goes to the validation read with this replication outcome attached. Its similarity
measure is the published term-frequency cosine (Amendment 5).

## H2 link momentum: the registered power gate fails

* **Links extracted:** 1,896 named ≥ 10% customer links (exact registrant-name match), from 1,477 10-Ks of 225
  suppliers.
* **Gate:** S&P 400 suppliers per year with a named S&P 500 customer average **32.5** (range 29–36), against the
  registered ≥ 100.
* **Recall check:** about half of S&P 400 10-Ks (183/350 in 2019, 206/387 in 2023) contain a "10% customer"
  sentence. In a random sample of 12 of those sentences, none names a ≥ 10% customer ("no individual customer…",
  "our top five customers…", "one customer accounted for 10%"). SFAS 131 requires the amount, not the name.
* **Conclusion:** the gate's failure is a property of the disclosures, not of the extraction.
* **Result:** H2 is reported as underpowered and enters Holm with p = 1 (registered). The S2 precision check is
  then moot and was not run.
