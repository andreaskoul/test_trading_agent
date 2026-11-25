# Literature prior: appraisal ratio of government-bond and currency trend following against the trend core (2026-11-25)

**Status.** This memo copies published figures and proposes a prior. It is not a test.
* No return series was built and no data of this project's were read.
* The only arithmetic is on copied figures (`lit_prior.py` → `LIT_PRIOR.json`). Every number it produces is
  labelled `reasoning`.
* It serves the design in `SCOPE.md` §7 on `origin/research/xasset-scope-20261125`: trend following in non-equity
  markets, a never-read 1962–2002 proxy sample, and an appraisal-ratio (AR) read against the 200-day 1.3×/0.7× core.
* Research only; nothing under `fund/` changes. The prior and the combination rule are proposals for the owner.

**Access labels.**
* `read`: I opened the source PDF and read the passage or exhibit cited.
* `digitised`: a bar height I measured from a figure in a PDF I opened. The method and its checks are in
  `digitise.py`; its output is `digitised.json`.
* `abstract-only` and `search-summary`: only an abstract, or only a search engine's summary, was seen.
* `repo`: a file in this repository.
* `reasoning`: my inference or arithmetic. No source states it.

Short names: **MOP** = Moskowitz, Ooi and Pedersen (2012); **HOP** = Hurst, Ooi and Pedersen (2017); **BLOPS** =
Babu, Levine, Ooi, Pedersen and Stamelos (2020); **HLWZ** = Huang, Li, Wang and Zhou (2020); **MP** = McLean and
Pontiff (2016). "SR" is an annualized Sharpe ratio unless marked monthly.

---

## 0. Sources and access log

| Source | File opened (sha256 prefix) | Read | Not read |
|---|---|---|---|
| MOP, "Time series momentum", *JFE* 104 (2012) 228–250 | pages.stern.nyu.edu/~lpederse/papers/TimeSeriesMomentum.pdf, the journal version (`7682f8e9`) | §2.1, §2.4, §3.1, §4.1–4.3; Tables 1–4; Fig. 2; footnote 9 | §5 onwards |
| HOP, "A Century of Evidence on Trend-Following Investing", *JPM* 44(1), Fall 2017 | fairmodel.econ.yale.edu/ec439/hurst.pdf, the journal reprint (`7b286a9f`) | the whole text; Exhibits 1–4, A1, B1 | Exhibits 6–11 (looked at, nothing copied) |
| BLOPS, "Trends Everywhere", *JOIM* 18(1) (2020) 52–68 | aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-Trends-Everywhere_JOIM.pdf (`16e9b7b7`) | §1–5; Tables 1–3; Fig. 2 Panels A–B; footnotes 4, 7, 8 | §6 onwards |
| HLWZ, "Time series momentum: Is it there?", *JFE* 135 (2020) 774–794 | down.aefweb.net/WorkingPapers/w717.pdf, which serves the journal version (`ec8209bd`) | abstract; Tables 1, 2, 9, 10; §5.1–5.2 | the bootstrap sections (Tables 4–8) in detail |
| MP, "Does Academic Research Destroy Stock Return Predictability?", *JF* 71(1) (2016) 5–32 | gwern.net/doc/economics/2016-mclean.pdf, a third-party mirror of the published article (`dda200d8`) | abstract; Table I (p. 11); Table II and its text (pp. 13–14) | the rest |

```
Query: "McLean Pontiff ... pdf"; "Huang Li Wang Zhou 'Time series momentum: Is it there?' pdf";
       "Babu Levine Ooi Pedersen Stamelos 'Trends Everywhere' pdf" (twice)   Date: 2026-11-25
Opened: the five PDFs above
Blocked: core.ac.uk/download/287750773.pdf (HTTP 403); ink.library.smu.edu.sg (Incapsula bot wall);
         aqr.com/-/media/.../Trends-Everywhere.pdf (guessed URL, 404; the real link came from the AQR article page)
Not attempted: alphaXiv and Elicit (the papers are SSRN/journal finance papers and the PDFs loaded directly);
               Kim, Tse and Wald (2016), cited by BLOPS and HLWZ (not read); Hurst, Ooi and Pedersen (2013);
               any paid database
Stopped: no
```

## 1. Copied figures

### 1.1 MOP 2012

* **Signal and scaling** (`read`, §4.1, eq. 5, p. 236): r = sign(past 12-month excess return) × 40%/σ_{t−1} × the
  next month's return.
  * σ² is 261 × the exponentially weighted squared daily return, with centre of mass 60 days, lagged one day (§2.4,
    eq. 1, p. 233).
  * Sample January 1985 – December 2009. Futures and forwards; the instruments start between 1965 and 1999 (Table 1,
    p. 232).
* **Costs:** none. Every figure is gross. The word "cost" appears only in references to other papers (`read`).
* **Fig. 2, "Sharpe ratio of 12-month time series momentum by instrument"** (p. 237). Caption: "annualized gross
  Sharpe ratio … January 1985 to December 2009" (`read`). Bar heights are `digitised` from the vector drawing, to
  about ±0.001:

| Fixed income (13) | SR | Currencies (12) | SR |
|---|---:|---|---:|
| 3 Yr Australian Bond | 0.132 | AUD-NZD | 0.087 |
| 10 Yr Australian Bond | 0.412 | AUD-USD | 0.384 |
| 2 Yr Euro-Schatz | 0.379 | EUR-JPY | 0.403 |
| 5 Yr Euro-Bobl | 0.505 | EUR-NOK | 0.427 |
| 10 Yr Euro-Bund | 0.535 | EUR-SEK | 0.051 |
| 30 Yr Euro-Buxl | 0.348 | EUR-CHF | 0.189 |
| 10 Yr CGB | 0.305 | EUR-GBP | 0.273 |
| 10 Yr JGB | 0.717 | AUD-JPY | 0.405 |
| 10 Yr Long Gilt | 0.319 | GBP-USD | 0.300 |
| 2 Yr US Treasury Note | **1.050** | EUR-USD | 0.276 |
| 5 Yr US Treasury Note | **0.568** | USD-CAD | 0.522 |
| 10 Yr US Treasury Note | **0.432** | USD-JPY | 0.529 |
| 30 Yr US Treasury Bond | **0.139** | | |
| **mean / median** | **0.449 / 0.412** | **mean / median** | **0.321 / 0.342** |

  Commodities (24) average 0.363 and equities (9) 0.527 (`digitised`).

* **Diversified portfolio** (`read`):
  * The intro gives "a Sharpe ratio greater than one on an annual basis" for 1985–2009 (p. 229).
  * 1966–1985: "a statistically significant return and an annualized Sharpe ratio of 1.1" (p. 237–238). Footnote 9
    calls this an out-of-sample study requested by the referee.
  * Table 3 Panel A (p. 238): the alpha on MSCI World, SMB, HML and UMD is 1.58% a month (t 7.99), the MSCI World
    beta 0.09 (t 1.89), at about 12% volatility.
* **Table 2** (p. 235), k = 12, h = 1, 1985–2009 (`read`). t-statistics of the alpha on MSCI World, the Barclays
  bond index, GSCI, SMB, HML and UMD:

  | Bond futures | Currency forwards | All assets |
  |---:|---:|---:|
  | 3.53 | 3.41 | 6.61 |

  As SRs of the alpha these are about 0.71, 0.68 and 1.32: t/√25 (`reasoning`).
* **Table 4** (p. 240), average pairwise correlation of 12-month TSMOM returns, 1985–2009 (`read`):
  * within an asset class: fixed income 0.38, currencies 0.10, commodities 0.07, equities 0.37;
  * across asset classes: FI–FX 0.05, FI–equity 0.21, FX–equity 0.20.
* **Table 1 volatilities** used for costs below (`read`):
  * US bonds 2y 1.86%, 5y 4.25%, 10y 9.30%, 30y 18.56%;
  * currencies 6.29% (CAD) to 12.33% (CHF).

### 1.2 HOP 2017

* **Strategy** (`read`, printed p. 16):
  * "an equal-weighted combination of 1-month, 3-month, and 12-month time-series momentum strategies for the 67
    markets", rebalanced monthly;
  * each position at the same volatility, with the portfolio at a 10% ex-ante target (a rolling 3-year covariance
    matrix, endnote 7);
  * January 1880 – December 2016, 3-year warm-up.
* **Data before futures** (`read`, Appendix A, p. 25):
  * bonds: "country-level cash bond returns from Datastream, Ibbotson, and Global Financial Data", scaled to a
    constant 4-year duration;
  * currencies: "spot exchange rates from Datastream and LIBOR short rates from Bloomberg" before 1989 (CAD 1992,
    NZD 1996).
  * Exhibit A1 (p. 26) draws the currency series from the early 1970s. Its time axis is not linear (1877 and 1880
    are far apart), so no start year was read off it.
* **Costs** (`read`, Exhibit B1, p. 27). One-way, as % of notional, for 2003–2016; "twice as high from 1993 to
  2002 and six times as high from 1880 to 1992, based on Jones [2002]":

  | | 1880–1992 | 1993–2002 | 2003–2016 |
  |---|---:|---:|---:|
  | Bonds | 0.06% | 0.02% | 0.01% |
  | Currencies | 0.18% | 0.06% | 0.03% |
  | Equities | 0.34% | 0.11% | 0.06% |
  | Commodities | 0.58% | 0.19% | 0.10% |

  Roll costs are not included (p. 16, p. 27).
* **Exhibit 1** (p. 17), full sample 1880–2016, diversified (`read`):
  * excess return 18.0% gross of fee and cost; 11.0% gross of fee, net of cost; 7.3% net of 2/20 fee and cost;
  * realized volatility 9.7%;
  * SR net of fees and costs 0.76;
  * correlation with US equities −0.01 and with US 10-year bonds −0.03.
  * The decade correlations with US equities range from −0.34 (2000s) to 0.33 (1940s).
* **Exhibit 2** (p. 18), annualized gross SR of the **12-month** strategy (`read`):

  | 1880–2016 | 1880s | 1890s | 1900s | 1910s | 1920s | 1930s | 1940s | 1950s | 1960s | 1970s | 1980s | 1990s | 2000s | 2010–16 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | 1.32 | 1.03 | 1.35 | 1.52 | 0.99 | 1.77 | 1.09 | 1.54 | 1.55 | 1.01 | 1.91 | 1.46 | 1.38 | 1.10 | 0.73 |

* **Exhibit 3** (p. 19), "Sharpe ratio of time-series momentum (gross of fee, gross of cost) by asset", 1880–2016.
  * The caption does not say which signal; the paper's strategy is the 1/3/12 combination.
  * `digitised` from vector bars. Check: the 67-bar mean is 0.415, and the text (p. 18) says "an average Sharpe ratio
    of approximately 0.4".
* **Exhibit 4** (p. 20), the same measure for 1880–1984, "only assets that have at least 10 years of data before
  1985 … out of sample relative to … Moskowitz et al. [2012]" (`read`; bars `digitised`).

| Market | Ex. 3, 1880–2016 | Ex. 4, 1880–1984 |
|---|---:|---:|
| U.S. 2-Yr Treasury Note | 0.543 | 0.404 |
| U.S. 5-Yr Treasury Note | 0.642 | 0.680 |
| U.S. 10-Yr Treasury Note | 0.672 | 0.744 |
| U.S. 20-Yr Treasury Bond | 0.440 | 0.514 |
| Germany 2 / 5 / 10 / 30 | 0.281 / 1.042 / 0.888 / 0.505 | — / 1.334 / 1.198 / — |
| Australia 3 / 10 | 0.113 / 0.504 | — |
| Canada 10, France 10, Italy 10, Japan 10, U.K. 10 | 0.549, 0.244, 0.734, 0.572, 0.536 | 0.742, 0.128, 0.748, —, 0.579 |
| **Fixed income mean / median** | **0.551 / 0.543** (15) | **0.707 / 0.711** (10) |
| USD AUD, USD CAD, USD EUR, USD GBP, USD JPY | 0.380, 0.294, 0.329, 0.567, 0.616 | —, —, 0.971, 0.746, 0.782 |
| EUR JPY, EUR NOK, EUR SEK, EUR CHF, EUR GBP, JPY AUD, AUD NZD | 0.323, 0.362, 0.403, 0.292, 0.310, 0.243, 0.086 | 0.515, —, —, 0.633, 0.339, —, — |
| **Currencies mean / median** | **0.350 / 0.326** (12) | **0.664 / 0.690** (6) |
| Equities; commodities (means) | 0.482; 0.347 | 0.572; 0.504 |

### 1.3 BLOPS 2020 ("Trends Everywhere")

* **Method** (`read`, pp. 55–56):
  * the MOP construction: sign(12-month excess return) × 40%/σ, with EWMA σ at a 60-day centre of mass;
  * January 1985 – December 2017;
  * "We report strategy returns gross of transaction costs" (footnote 4).
* **Table 2** (p. 59), gross, 12-month TSMOM (`read`):

  | | Traditional assets (the MOP 58) | Alternative assets (82 new) | Equity factors | All |
  |---|---:|---:|---:|---:|
  | Median single-asset SR | 0.34 | 0.34 | 0.39 | 0.35 |
  | Diversified-portfolio SR | 1.17 | 1.34 | 0.95 | 1.60 |

* **Table 3 Panel B** (p. 61): 12-month TSMOM regressed on the equal-volatility passive portfolio (`read`).

  | Group | Annualized alpha | t-statistic |
  |---|---:|---:|
  | Traditional assets | 12.4% | 5.72 |
  | FI swaps | 19.6% | 4.13 |
  | Emerging FX | 9.6% | 2.29 |

* **Fig. 2** (p. 58), "gross Sharpe ratio of time series momentum by asset and factor, from 1985 to 2017". Bars are
  `digitised` from JPEG images, to about ±0.01. Check: the Panel A median is 0.33 against the printed 0.34, and the
  Panel B median 0.34 against 0.34.

  * Panel A, the same 58 contracts as MOP Fig. 2, over 1985–2017:
    * **fixed income mean 0.406, median 0.41** (US 2y 0.82, 5y 0.62, 10y 0.41, 30y 0.03; Japan 10y 0.74; Bund 0.51);
    * **currencies mean 0.293, median 0.29** (AUD-NZD −0.03; USD-JPY 0.57).
  * Panel B, new markets:
    * **17 two-year fixed-income swaps: mean 0.567, median 0.59.** The series start between 1987 and 2001 (Table 1,
      p. 54).
    * **24 emerging-market currency pairs: mean 0.178, median 0.20.** The series start in 1997–1999 (Table 1).
    * The palm-oil bar is below the image's resolution and is recorded as missing.

### 1.4 HLWZ 2020 (the critique)

* **Abstract** (`read`, p. 774): "asset-by-asset time series regressions reveal little evidence of TSM, both in-
  and out-of-sample … the TSM strategy is profitable, but its performance is virtually the same as that of a similar
  strategy that is based on historical sample mean and does not require predictability."
* **Sample:** 55 futures, 1985:01–2015:12. The out-of-sample R² uses 2000:01–2015:12 (Table 2, p. 779).
* **Table 2** (`read`):
  * slopes of the 12-month return in asset-by-asset regressions, by asset class;
  * the average out-of-sample R² is **+0.29%** for government bonds and **−0.75%** for currencies;
  * two bond contracts (two-year European and two-year US) and one currency (JPY/USD) have significant positive
    out-of-sample R².
* **Table 9** (p. 789), unscaled sign strategies, 1986:01–2015:12 (`read`). TSM = sign of the past 12-month return;
  TSH = sign of the historical mean.
  * The SRs are **monthly, not annualized**: the 2y US TSM row has a mean of 0.13 and an SR of 0.28, which fits only
    a monthly volatility of about 0.46% (`reasoning`).
  * Bonds, TSM SR: AU3 0.24, AU10 0.15, EU2 0.13, EU5 0.06, EU10 0.02, EU30 0.05, CA10 0.11, JP10 0.06, UK10 0.14,
    US2 0.28, US5 0.15, US10 0.09, US30 0.12.
  * Bonds, TSH SR: 0.28, 0.21, 0.10, 0.11, 0.09, 0.19, 0.17, 0.02, 0.12, 0.26, 0.19, 0.13, 0.20.
  * FX, TSM SR: AUD 0.02, EUR 0.03, CAD 0.11, JPY 0.14, NOK 0.02, NZD 0.07, SEK 0.01, CHF 0.05, GBP 0.00.
  * FX, TSH SR: −0.05, 0.03, −0.04, 0.03, −0.02, 0.01, −0.02, 0.06, −0.01.
  * Class means × √12 (`reasoning`):

    | | TSM | TSH |
    |---|---:|---:|
    | Bonds | 0.43 | 0.55 |
    | Currencies | 0.17 | −0.00 |

    In this sample, bond trend following earned **less** than holding bonds by their historical-mean sign: the
    profit was the 1986–2015 bond drift. Currency trend following beat its drift benchmark.
* **Table 10** (p. 791), portfolio level, volatility-weighted (Panel B; `read`):
  * the TSM long–short mean is 1.16% a month against 0.74% for TSH: difference 0.42, p = 0.07;
  * the Fama–French four-factor alpha difference is 0.32 (p = 0.08); against the Asness–Moskowitz–Pedersen
    three-factor model it is 0.10 (p = 0.56).
* **BLOPS's reply** (`read`, footnote 8, p. 67). The HLWZ test "is insufficient … because two portfolios may exhibit
  similar levels of alpha relative to a common set of factors, yet still have alpha relative to each other". Their
  Table 3 regresses TSMOM on the passive volatility-scaled portfolio directly (§1.3 above).

### 1.5 MP 2016 (decay)

* **Abstract** (`read`, p. 5): "Portfolio returns are 26% lower out-of-sample and 58% lower post-publication. The
  out-of-sample decline is an upper bound estimate of data mining effects. We estimate a 32% (58%–26%) lower return
  from publication-informed trading. Post-publication declines are greater for predictors with higher in-sample
  returns".
* **Table I** (p. 11): 97 predictors.
  * Mean monthly long–short returns: 0.582% in-sample, 0.402% out-of-sample before publication, 0.264% after
    publication.
  * Mean spans: 323, 56 and 156 months.
  * The sample ends in 2013.
* **Table II, column 1** (p. 13): post-sample −0.150 (SE 0.077); post-publication −0.337 (SE 0.090), both in %
  a month.
* **Not applicable as is** (`reasoning`). MP study cross-sectional US stock predictors, not futures trend following.
  Their finding that the decline grows with in-sample return and shrinks with arbitrage cost is checked against
  trend-specific evidence in §3.3.

## 2. Overlap with the 1962–2002 proxy and with this programme's spent samples

The proxy window is `SCOPE.md` §7: US Treasuries 1962-01 .. 2002-06, and eight currencies against USD 1972-01 ..
1989-12. "Share" is the fraction of the source's years that fall in the window. It is computed by `lit_prior.py`,
with currency series taken to start in 1971 (`reasoning`, from HOP A1 and MOP Table 1).

| Source (years) | Bonds: years in proxy window (share) | Currencies: years in window (share) | Spent samples (`SCOPE.md` §1) overlapped |
|---|---|---|---|
| MOP Fig. 2 (1985–2009) | 1985–2002 (0.70) | 1985–1989 (0.20) | S1: IEF/TLT/UUP trend, 2003–2009. S6: cross-sectional FX, 1990–2009 (dates and currencies; the exposure differs). S3: equity TSMOM only, so not these legs |
| MOP footnote 9 (1966–1985, diversified) | 1966–1985 (≈1.0) | 1972–1985 (≈1.0) | none |
| HOP Ex. 3 (1880–2016) | 1962–2002 (0.30; higher in market-years, because many bond series start after 1960) | 1972–1989 (0.39) | S1 2003–2016; S6 1990–2016 |
| HOP Ex. 4 (1880–1984) | 1962–1984 (0.22 by dates; about 0.30 assumed in market-years) | **1972–1984 (0.93)**: built the same way as the proxy, from spot rates and short rates | none |
| HOP Ex. 2, 1960s–1990s rows | inside the window | inside the window | 2000s and 2010–16 rows: S1, S6 |
| BLOPS Fig. 2A (1985–2017) | 1985–2002 (0.53) | 1985–1989 (0.15) | S1 2003–2017; S6 1990–2017 |
| BLOPS Fig. 2B FI swaps (1987–2017) and EM FX (1997–2017) | swap dates overlap 1987–2002, in different instruments and mostly other countries | **none** (other currencies, after 1989) | EM FX: none. Swaps: S1's dates only |
| HLWZ (1985/86–2015) | 1985–2002 (0.56) | 1985–1989 (0.16) | S1 2003–2015; S6 1990–2015 |
| MP (US stocks, to 2013) | — | — | none of these legs |

**Consequences** (`reasoning`):
* The literature's sources are nested, not independent of one another:
  * BLOPS Panel A contains MOP's years and contracts;
  * HOP Ex. 3 contains Ex. 4 and most of MOP's period;
  * HLWZ uses MOP's contracts over 1985–2015.
* Two figures must not enter a prior that the proxy then updates:
  * **HOP Ex. 4's currency figure (0.664)**, which is the proxy's own period, built the same way;
  * **MOP footnote 9 (1.1)**, all inside the window.
* Literature numbers from 2003 onwards overlap S1 in dates and instruments. If a later update also uses S1's
  recorded read, those years must not be counted twice. The same holds for currencies from 1990 against S6.

## 3. Proposed prior (`reasoning`)

The target is the true appraisal ratio of the registered sleeve against the core, **net of costs, gross of fees**:
AR = α/σ_ε from regressing the sleeve on the core. The core is the 200-day 1.3×/0.7× rule. Its full-sample SR is
0.578 over 1927–2026 (`repo`: `research/exposure/results.json`, P3).

Two targets are kept apart:
* **historical**: the AR inside the never-read 1962–2002 proxy sample. This is what the read estimates, and what
  rule 3's power is computed for.
* **forward**: the AR of a sleeve traded from now on. It sets the size of any forward record.

### 3.1 Per-market centre, with the proxy's own years removed

1. **Remove the window-year premium.** In HOP Ex. 2, the 12-month strategy's decades inside the window (1960s–1990s)
   average 1.44; the decades outside average 1.29. Window years ran k = 1.118 times better.
   * Each source's class mean is divided by 1 + f·(k − 1), with f its window share (§2).
   * This is a portfolio-level ratio, applied to single bond and currency markets: an assumption.
2. **Bonds.** Two year-disjoint pieces:
   * HOP Ex. 4, before 1985: 0.707 → 0.683 with f ≈ 0.30;
   * MOP, 1985–2009: 0.449 → 0.415 with f = 0.70.
   * Equal-weighted centre **0.549**. Its uncertainty is sd 0.134, half the difference between the two eras. The
     sampling SEs, inflated by 1/√(1 − f), are 0.103 and 0.239, which agree.
3. **Currencies.**
   * MOP 0.321 (f = 0.20) → 0.314.
   * HOP Ex. 4 FX carries only 1 − 0.93 of its weight, so it moves nothing.
   * Centre **0.321**, sd 0.094: the sampling SE of a 12-asset mean at a TSMOM correlation of 0.10 over 25 years,
     inflated for f.
4. **Bias before publication.** I apply MP's 26% out-of-sample decline only to the part of the centre that comes
   from MOP's own fitting sample:
   * half for bonds, giving a factor of 0.87;
   * 98% for currencies, giving 0.746.
   * HOP's pre-1985 markets are already out of sample for MOP, and they were *stronger*. The new markets in BLOPS
     are mixed: FI swaps 0.567 against 0.406 for traditional bonds; EM FX 0.178 against 0.293.
   * **Per-market historical gross SR: bonds 0.478, currencies 0.239.**
5. **Spread across bond markets.**
   * In MOP Fig. 2 the bond bars have an sd of 0.233. The iid sampling sd implied by each bar's years is 0.247.
   * So no true spread between bond markets is detectable, and the US 10-year is given the class centre.
   * HOP's US 10-year figures (0.67, 0.74) are higher; MOP's and BLOPS's (0.43, 0.41) are near the centre.

### 3.2 From market SR to AR against the core

* **Correlation with the core:** ρ ~ N(0, 0.15).
  * Centre: HOP Ex. 1's −0.01 with US equities, and MOP Table 3's market beta of 0.09 (both include equity legs).
  * Spread: HOP Ex. 1's decade range of −0.34 to 0.33.
  * AR = (SR − ρ·0.578)/√(1 − ρ²).
* **Costs in SR units** = (2 × 1.5 sign flips + 0.5 rebalancing) × the one-way cost ÷ volatility.
  * One-way costs from HOP B1; volatilities from MOP Table 1. The turnover is an assumption, drawn ×U(0.5, 2) in the
    Monte Carlo.
  * Before 1993: US 2y 0.113, 5y 0.049, 10y 0.023, 30y 0.011; currencies 0.05–0.10.
  * From 2003: under 0.02 for all.
* **Sleeve** = equal risk across the markets available. Correlations:
  * within US maturities ~N(0.70, 0.10). This is an assumption; MOP's 0.38 mixes countries.
  * within USD pairs ~N(0.35, 0.15). Also an assumption; MOP's 0.10 includes crosses.
  * bonds against currencies 0.05 (MOP Table 4).
* **Composition and time weights:**
  * 1962–71: 2 rates;
  * 1972–89: 4 rates and 8 currencies;
  * 1990–2002: 4 rates, at about a third of the pre-1993 cost (HOP B1: ×2 from 1993).
* **Monte Carlo:** 20,000 draws over every uncertain input above, seed 20261125.

### 3.3 Decay after publication (forward target only)

| Evidence | Ratio of later to earlier SR | Access |
|---|---:|---|
| MP: post-publication over in-sample | 0.42 | `read` |
| MP: out-of-sample, before publication, over in-sample | 0.74 | `read` |
| Bonds: implied 2010–17 per-market mean (0.272) over MOP 1985–2009 (0.449) | 0.606 | `digitised` + `reasoning` |
| Currencies: implied 2010–17 (0.205) over MOP (0.321) | 0.639 | `digitised` + `reasoning` |
| HOP Ex. 2: 2010–16 (0.73) over the mean of the 1980s, 1990s and 2000s | 0.556 | `read` + `reasoning` |

* "Implied 2010–17" is the year-weighted difference (33 × BLOPS − 25 × MOP)/8, over the same 58 contracts. It
  ignores the change in volatility between periods.
* The forward factor is the mean of the four ratios: **0.555, sd 0.10**. It is applied to the MOP-era level, with
  modern costs (HOP B1, 2003–2016).
* Forward sleeve: 4 US maturities and 6 G10 currency futures.

### 3.4 Result

| Target (AR against the core, net of costs) | Centre | sd | 5–95% |
|---|---:|---:|---|
| Single market, US 10-year, **historical 1962–2002** | **0.45** | **0.15** | 0.21–0.71 |
| Single market, class average (the mean of the US maturities' costs), historical | 0.42 | 0.16 | 0.17–0.68 |
| **Rates + FX sleeve, historical 1962–2002** (the proxy design) | **0.48** | **0.15** | 0.24–0.74 |
| Single market, US 10-year, **forward** | **0.25** | **0.10** | 0.09–0.42 |
| Rates + FX sleeve, **forward** | **0.36** | **0.12** | 0.17–0.56 |

* All rows are `reasoning`, from `LIT_PRIOR.json` → `prior_AR_vs_core`.
* The sleeve adds little over a single market in the proxy:
  * the four US maturities are close to one bet;
  * currencies are present for only 18 of 40.5 years, at a low per-pair SR (0.24) and the highest costs.
* HLWZ's finding is a reason to doubt the bond leg's alpha. In 1986–2015 bond trend following did not beat holding
  the bond drift (§1.4).
  * Against an equity-only regressor, drift counts as alpha.
  * The proxy's 1962–1981 bond bear market tests the signal without that tailwind.
  * **I would not raise the centre for bonds above the per-market figure even if the proxy is strong in 1982–2002.**

## 4. Combining the literature and the proxy without double counting

**Recommended rule (to be registered before the read):**

1. **Prior = §3.4's historical row.** It is built only from out-of-window information:
   * the in-window share of each source is divided out, using the window premium k;
   * a source's weight is cut to its out-of-window share 1 − f;
   * HOP Ex. 4 currencies and MOP footnote 9 are excluded.
2. **Proxy likelihood.** The proxy's estimate â with standard error SE_p:
   * the iid SE is √((1 + â²/2)/T), 0.166 at T = 40.5 years and the prior centre;
   * register a HAC/block-bootstrap SE as the one that binds, since the iid SE is a lower bound (`SCOPE.md` §4).
3. **Posterior.** Normal–normal: m₁ = (m₀/s₀² + â/SE_p²)/(1/s₀² + 1/SE_p²). With the numbers above, the proxy carries
   about 46% of the weight (`LIT_PRIOR.json` → `combination`). The prior is about as informative as 40 years of
   proxy, which is why its overlap has to be taken out.
4. **Two sensitivity rows, reported and not decisive:**
   * (a) **proxy alone** (flat prior);
   * (b) **replication framing**: compare â with the literature's in-window figures (HOP Ex. 2 1960s–1990s for the
     whole portfolio; HOP Ex. 4 US Treasuries and currencies), as a replication, never pooled with them.
5. **Spent samples.** A later update that adds S1's recorded read (2020–2025) or any 2003+ data cannot also use a
   prior that contains 2003–2017 literature years.
   * Then the prior's bonds piece B is restricted to MOP's 1985–2002 share. In practice the prior is cut back to
     HOP's pre-1985 piece, and the decay evidence is not counted again.

**Alternatives considered** (`reasoning`):
* *Variance inflation alone* (keep the centres, divide each source's precision by 1 − f). It leaves the in-window
  years inside the centre, and those years were better than average (k = 1.12). Steps 1 and 2 above do both.
* *Literature only for non-overlapping years.* This is exact in principle. Published figures cannot be split by
  year, except the year-weighted difference used for 2010–17, so the k-scaling stands in for it.

## 5. What this means for the registered read (`reasoning`)

* **Which δ.** Rule 3 of `DESIGN_RULES.md` reads: "δ = ½ × the fit-window estimate (the usual haircut for decay and
  selection), or the literature value when there is no fit" (`repo`). The sentence can be read two ways:
  * `SCOPE.md` §4 reads it as ½ × the literature value;
  * the second clause can also be read as the literature value itself.
  * The owner should rule on it. This memo's §3.4 centre is a third, explicit alternative.
* **Power**, Lo iid, P = Φ(δ/SE − z), at T = 40.5 years (`LIT_PRIOR.json` → `power_rule3_Lo_iid`):

  | δ | One-sided 5% | 0.10/40 | 0.10/60 |
  |---|---:|---:|---:|
  | ½ × literature, single market: 0.225 (MOP bond mean 0.449 ÷ 2) | 0.41 | **0.08** | 0.06 |
  | ½ × literature, sleeve: 0.332 (MOP-level sleeve 0.664 ÷ 2) | 0.66 | **0.23** | 0.19 |
  | Prior centre, US 10-year: 0.454 | 0.87 | **0.48** | 0.43 |
  | Prior centre, sleeve: 0.481 | 0.90 | **0.54** | 0.49 |

* At the programme level, ½ × literature leaves the read **below P = 0.5**: it would be a rule-6 precision estimate.
  The prior centre puts it **at the boundary**: 0.54 at N = 40 and 0.49 at N = 60.
  * Since the iid SE understates the true SE, I would register the read as a **precision estimate under rule 6**
    whichever δ is chosen.
  * Report the posterior of §4, not a pass or fail.
  * N must be recounted from `DATA_USE.md` at registration.

## 6. Discrepancies and limits found while copying

* **MOP text against MOP Table 4** (p. 240). The text says within-class correlations range "to 0.10 and 0.07 for
  commodities and currencies". The table gives commodities 0.07 and currencies 0.10. The table is used here.
* **The two MOP exhibits list different currency sets.** Fig. 2 has 12 pairs, including crosses (EUR-JPY, AUD-NZD,
  …). Table 1 lists 9 USD forwards. HLWZ's 9 USD pairs follow Table 1.
* **HOP's long US bond has three names.** Ex. 3 and Ex. 4 label it "U.S. 20-Yr Treasury Bond", Exhibit A1 "U.S.
  30-Yr Treasury Bond", and Appendix A "U.S. long bond" (scaled at a 20-year duration).
* **HOP's per-asset exhibits are gross of cost; its net results are only for the diversified portfolio.** Exhibit 1
  shows costs taking 7.0 points of the 18.0% gross excess return over 1880–2016, at about 10% volatility. That is
  large relative to the per-market SRs, and the pre-1993 ×6 multiplier drives it. The §3.2 cost model is far
  smaller per market; it is an assumption, and the proxy read must compute its own costs.
* **HLWZ Table 9 is not comparable to the others as printed.** Its SRs are monthly and unscaled. The ×√12 conversion
  here is mine.
* **Digitisation precision.**
  * The vector figures (MOP, HOP) are exact to about 0.001.
  * The BLOPS JPEGs are about ±0.01 (Heating Oil reads 0.41 or 0.42 depending on rounding). The palm-oil bar is
    unreadable.
  * Bar-to-label order was read from the rendered pages. The labels are glyph outlines, not text.
* **The two digitised class means each rest on one figure** (MOP 2012 Fig. 2; HOP Ex. 3–4). If the authors' own
  tabulations are ever published, they replace these numbers.

## 7. Not claimed

* No return, SR or AR of any strategy on this project's data was computed. The figures in §1 are published results;
  the figures in §3–5 are arithmetic on them under the stated assumptions.
* No claim that the window premium k, measured on the whole HOP portfolio, holds for bonds and currencies alone.
* No claim that MP's decline rates hold for futures trend following. §3.3 sets them beside the trend-specific
  ratios.
* No claim about Kim, Tse and Wald (2016), HOP's dataset (not public: `SCOPE.md` §2b) or the full HLWZ bootstrap
  results. None was read.
* The correlation, turnover and cost assumptions in §3.2 are mine, not the sources'. They are drawn over wide ranges
  in the Monte Carlo; the ranges themselves are assumptions.

## Files

* `digitise.py`: reproduces `digitised.json` from the three PDFs, whose sha256 hashes it checks.
  * It exits non-zero on a wrong file, a bar-count/label mismatch, an off-calibration tick, a HOP Ex. 3 mean not near
    the text's 0.4, a non-positive MOP bar, or a BLOPS median off Table 2.
  * Failure controls run on 2026-11-25, each of which made it exit 1:
    * the wrong PDF passed in;
    * an extra label planted;
    * the text mean changed to 0.5;
    * the zero line shifted by 15 px.
* `lit_prior.py`: reads `digitised.json`, the typed copies of printed tables and the core's SR; writes
  `LIT_PRIOR.json`. It reads no market data.
* The PDFs are not committed (copyright). Their URLs and hashes are in §0 and `digitise.py`.
