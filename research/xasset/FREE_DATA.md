# Free historical data for the cross-asset trend read: inventory before any purchase (2026-11-25)

**Status.** An inventory, not a test. **No return, signal, Sharpe ratio or correlation was computed from any data,
on any date.** Downloads were used for presence only: first and last dates, observations per year, month-end
coverage, distinct contract labels per year, gaps, duplicate dates, declared fields and titles. §8 lists the few
pre-2003 *levels* that header previews printed by accident.

Context: `SCOPE.md` (spent samples S1–S13, the 1962–2002 proxy design), `PROCURE.md` (paid vendors; the power and
breadth model in `procure_power.py`), `VALIDATE.md` (the FRED/H.10 proxy: US Treasuries 1962–2002; GBP, AUD, CAD
with carry 1972–2002).

Files:
* `free_coverage.py`: `fetch` freezes every kept file with its sha256 (`FREE_MANIFEST.json`, 184 files, 0 failed;
  the raw files sit in `.cache/xasset-free`, not committed); `coverage` writes `free_coverage.json` (counts only);
  `power` writes `FREE_POWER.json` using `procure_power.py`'s functions.
* `FREE_DATA.json`: the machine-readable version of this memo.

Access labels: **read-directly** (the page or file itself was read); **coverage-count** (the file was downloaded
and only its dates and counts were parsed); **fetch-summary** (a fetch tool's summary of the page); **search-summary**
(a search engine's summary only); **blocked**; **reasoning** (my inference).

One check that could fail: `free_coverage.py power` recomputes PROCURE's proxy, Portara and Pinnacle rows from
`procure_coverage.json`. It reproduces `PROCURE_POWER.json` exactly (0.288, 0.775, 0.763). It passed.

---

## 1. Answer

**A free combination matches the cheaper paid route on power.** The combination is:
* pysystemtrade's shipped futures files: 33 commodity markets from 1969–1995, with the held and adjacent contract
  each day;
* the registered FRED/H.10 proxy for US rates and currencies;
* central-bank short rates that close the yen and franc carry gaps (BoJ end-of-month call rate from 1960, SNB call
  money from 1972, BIS policy rates).

Programme-level power at the 1962-01 .. 2002-06 window, single-market appraisal ratio AR₁ = 0.2:

| Design | Mean N | MOP correlations | ρ = 0.07 | ρ = 0.1 | ρ = 0.2 |
|---|---:|---:|---:|---:|---:|
| Proxy alone (registered) | 6.8 | 0.29 | 0.38 | 0.33 | 0.23 |
| **Free A**: proxy + pysystemtrade commodities and non-US rate futures | 24.8 | **0.75** | **0.68** | **0.56** | 0.33 |
| Free B: A + non-US yield proxies (UK, DE, JP, CA, CH) + DEM | 27.7 | 0.74 | 0.70 | 0.57 | 0.33 |
| Free C: B + a Quandl-CHRIS mirror (earlier grains, coffee, lumber; defective splice) | 31.0 | 0.82 | 0.76 | 0.64 | 0.38 |
| Paid: proxy + Pinnacle supplement ($248) | 26.3 | 0.76 | 0.70 | 0.58 | 0.34 |
| Paid: proxy + Portara supplement (≈ $8,800–13,200) | 37.4 | 0.78 | 0.74 | 0.61 | 0.35 |

At the 5% level the same rows give 0.73 for the proxy, 0.97 for free A, and 0.97 for both paid routes at MOP
correlations; 0.76, 0.91, 0.91 and 0.93 at ρ = 0.1. The full grid (AR₁ 0.1/0.2/0.3) is in `FREE_POWER.json`.

**The power gate** is design rule 3: P ≥ 0.5 at the programme threshold (one-sided α = 0.10/40, z = 2.81):
* free A passes at MOP correlations, at ρ = 0.07 and at ρ = 0.1;
* nothing passes at ρ = 0.2, free or paid;
* the proxy alone passes at none.

**What breadth buys.** The commodity block does the work, as in PROCURE §4.3:
* Extra bond proxies add nothing under MOP correlations. Fixed-income trends correlate at 0.38, and with equal
  weights a fourth correlated bond market slightly dilutes the book (0.748 → 0.742).
* Extra EMS currencies add little: 0.757 with them.

**Recommendation** (owner's decision):
* **Do not buy for this read yet.** Pre-register free A as the primary data and Pinnacle as an *audit* source, not a
  breadth source. Free A's power is within 0.02 of Pinnacle's at every correlation in the table.
* What money would still buy:
  * a licence that is clearly written down (Portara);
  * a second vendor to reconcile against (§6);
  * Portara's extra ~13 markets on average, which are worth +0.03 power at MOP correlations.
* Each is a data-quality purchase, not a power purchase.
* Two caveats limit the free route, so the owner should rule on both:
  * pysystemtrade's upstream provenance and licence are undocumented (§2);
  * its mini/micro back-fills need a reconciliation contract.

## 2. The best free source: pysystemtrade's shipped futures CSVs

`robcarver17/pysystemtrade` at commit `bbf5cf8` (develop, 2026-11-02), directory `data/futures/`.
Access: coverage-count; README and `docs/data.md` read-directly.

* **What it is.**
  * 252 instruments. Each has a *multiple prices* file: per day the held contract (PRICE), the adjacent contract
    (CARRY) and the next held contract (FORWARD), each with its contract label.
  * Each also has a Panama (additive) back-adjusted series, built on the shipped roll calendar (`rollconfig.csv`:
    hold cycle and roll offset per instrument).
  * These are futures prices. Excess returns therefore need no cash leg, and the CARRY column gives the roll yield
    directly.
* **Coverage before 2003** (`free_coverage.json`, `pysystemtrade`). Of 252 instruments, 99 start before 2003. After
  merging mini/micro variants and excluding equity indices, the dollar index, GSCI and the high-yield index, **49
  markets** remain:
  * **33 commodities**: OJ 1969-12; soy oil, sugar #11, cotton, cocoa, oats, soy meal, silver, platinum, wheat and
    corn in 1970; live cattle 1971; hogs 1974; gold 1975; feeder cattle, palladium 1977; canola 1978; heating oil
    1980; soybeans 1981; gasoline 1985; gasoil 1986; rice 1988; WTI 1988; white sugar, London cocoa, Brent 1989;
    natural gas 1990; ICE wheat 1994; copper, KC wheat 1995; milk 1996; class IV milk 2000; milling wheat 2002.
  * **5 currencies**: CAD and CHF 1972-09, GBP 1975, JPY 1977, AUD 1987.
  * **US rates**: US20 1978, US10 1982, Eurodollar (inside the SOFR file) 1984, US5 1989, Fed funds 1990, US2 2000.
  * **Non-US rates**: gilt 1983, Euribor 1989 (before 1999 presumably Euromark: reasoning), Canada 10y 1993; JGB 1999 and Swiss 10y 2001.
* **Density.** Daily, one 23:00 stamp per date, about 250 observations a year from each market's first year. The
  median gap is 1 day; the largest gaps are 4–26 days. There are no duplicate or out-of-order dates. CARRY is
  present on all pre-2003 days for gold, JPY, gilt, cocoa and WTI; missing on 7.9% for corn and 0.4% for US10.
  Distinct held contracts per year are 3–13, by cycle.
* **Licence.**
  * The repository is GPL-3.0 (read-directly).
  * `docs/data.md` says the author cannot put raw data on GitHub because "there would also be licensing issues
    with me basically just copying and pasting raw data that belongs to someone else". It also says the multiple
    prices were ones he "built myself".
  * The upstream source of the pre-2003 history is not stated.
  * Treat the licence as **unclear**: private research use only; raw files kept in `.cache`, never committed.
* **Defects** (typed; each needs a contract before use):
  1. *Back-filled variants.*
     * The mini and micro files carry longer histories than the full-size contract: corn mini 1970-08 against
       corn 1972-10; wheat mini 1970-08 against 1973-12; soybean mini 1981-08 against 1985-09; WTI mini 1988-11
       against 1990-10.
     * The extra history's source is undocumented.
     * Rule to register: a market's history is its full-size file, or the variant only where it reconciles with
       the full-size file on their common dates (level equality on matched contracts, counted, not a return
       statistic).
  2. *Splices.* The SOFR file holds Eurodollar from 1984. RBOB holds unleaded gasoline from 1985.
  3. *Deferred hold cycles.* The current `rollconfig.csv` holds December only for corn and crude. That is not
     MOP's front contract. The registration must fix whether to use the shipped series or rebuild it from the
     multiple prices with a front-month cycle (rebuilding needs only PRICE/FORWARD).
  4. Settlement versus close is not declared. There is no volume or open interest.
  5. The shipped CSVs stopped in March 2024 (`docs/data.md`). This does not affect the read.
* **Mirror.** `bug-or-feature/pst-csv-data` updates a subset (no licence; not used).

## 3. Other free sources, by role

**Currencies: spot and short-rate differential, 1972–1989**

| Source | Access | Coverage (presence only) | Use, defects |
|---|---|---|---|
| BIS bilateral USD rates, `WS_XRU` bulk | coverage-count | Daily from 1953 for DEM, FRF, NLG, BEF, CHF, SEK, DKK; ITL 1955; ESP 1962; JPY 1969-12; AUD, NZD 1971. Monthly end-of-period from 1953–57. Legacy currencies in euro units | Adds DEM (and the EMS block as a sensitivity) to the proxy's eight. Fixing time per country not declared |
| BIS central-bank policy rates, `WS_CBPOL` | coverage-count | Monthly **end of period** and daily: JP, CH, SE, DK, GB from 1946; DE 1948–98; US 1954; CA 1960; AU 1976; NZ 1985; NO 1986 | Carry fallback. Typed defect `policy_rate_not_market_rate`: discount rates for CH before 2000, SE before 1987, DK before 1992, DE before 1979 |
| Bank of Japan API (no key) | coverage-count | Collateralised overnight call rate, **end of month**, 1960-01 .. 2026-10 (802 months). USD/JPY spot end of month from 1973. USD/JPY 3-month spot-forward spread, end of month, 1971-01 .. 2010-02 | **Closes VALIDATE's JPY carry gap** (OECD 3-month only from 2002-04). The forward spread is a direct carry series |
| SNB data portal | coverage-count | CHF call money (tomorrow-next) monthly from 1972-01; CHF Libor 3M from 1989 | **Closes the CHF gap** (OECD 3-month only from 1999-07). Averaging convention not declared; needs a range contract (VALIDATE found an out-of-range OECD Swiss call-money value) |

With these, all eight proxy currencies have a short-rate differential over 1972–1989, plus DEM. That is not a
breadth gain. It removes the typed carry defect in SCOPE §7.

**Non-US government bonds (yield proxies, month end)**

| Market | Source | First month | Short rate | Defects |
|---|---|---|---|---|
| UK | BoE GLC nominal spot curve, month end, 0.5–25y | 1970-01 (2, 5, 10y: 396/396 month-ends to 2002) | OECD 3m 1957 / BIS | Fitted zero-coupon curve; database under OGL v3 (fetch-summary), yield-curve terms not named |
| Germany | Bundesbank Svensson term structure, 2/5/10y | 1972-09 (364 months to 2002) | OECD 3m 1960 | Month-end versus average not declared in the CSV |
| Japan | MoF JGB par yields, daily | 1–9y 1974-09-24; 10y 1986-07 | BoJ call, end of month | Missing values coded "-" |
| Canada | StatCan 10-10-0122 | 3m T-bill 1962-01; long benchmark 1976-01; 10y 1982-06 | 3m T-bill | **Last Wednesday**, not month end (inside VALIDATE's 7-day rule) |
| Switzerland | SNB Confederation spot yields | 1988-01 | SNB call money | Monthly; convention not declared |

* **Australia.** The RBA historical tables were **blocked** (403).
* **Not usable:**
  * OECD `IRLTLT01` (monthly averages, SCOPE);
  * ECB convergence yields (DE from 1990-01, "A" = average; coverage-count).
* **Bond futures for validation** on spent 2003+ data, as VALIDATE did for Treasuries: gilt (pysystemtrade, from
  1983); Bund, JGB, Canada 10y and Swiss 10y (2006, 1999–2001, 1993, 2001).

**Commodities other than pysystemtrade**

| Source | Access | Coverage | Verdict |
|---|---|---|---|
| `webclinic017/first_trading_algo` `data/*.csv` at `9bc6600` (Quandl CHRIS layout) | coverage-count | Front-month only, unadjusted. Grains and soy complex 1959-07; live cattle 1964; OJ 1967; cocoa 1968; hogs 1969; lumber, feeder cattle 1973; gold 1974-12; coffee 1975; heating oil 1979; WTI 1983 .. 2019-11. Copper and silver sparse (60–84 rows a year); cotton sparse in the 1970s; sugar has a 672-day gap | **Defective splice.** There is no second contract, so roll jumps can only be removed by dropping roll-day returns. No licence, no provenance. Use for a 2003–2019 reconciliation, or as free C's sensitivity only |
| World Bank Pink Sheet; IMF primary commodity prices | repo (SCOPE §2a) / reasoning | Monthly from 1960 / 1980 | **Monthly averages of spot**: fail the point-in-time contract; no roll yield (§5) |
| Hugging Face `paperswithbacktest/Commodities-Daily-Price`, `Bonds-Daily-Price`, `All-Daily-Rates` | fetch-summary; files 401 | Commodities from 1983-02 (32 unadjusted front-month series); 209 sovereign yields from 1969-04 | **Gated**: approval tied to a paid subscription. Not free |
| Hugging Face `lynx1231/historical-*-futures-data-sample` | coverage-count | Commodities 2023-01 ..; energy 2013-11 ..; rates 2025-06 .. | Vendor evaluation samples; too recent |

## 4. Free breadth for 1962/1969–2002

Markets with an excess-return construction, counted in the first full calendar year after the first observation
(`FREE_POWER.json`, `N_by_year`). The FX legs stop at 1989; US futures are not added to the proxy's US leg.

| Year | Proxy | Free A | Free B | Free C | Pinnacle combined | Portara combined |
|---:|---:|---:|---:|---:|---:|---:|
| 1965 | 2 | 2 | 2 | 7 | 2 | 2 |
| 1970 | 2 | 3 | 4 | 11 | 9 | 9 |
| 1975 | 10 | 24 | 28 | 31 | 27 | 27 |
| 1980 | 12 | 29 | 34 | 38 | 32 | 36 |
| 1985 | 12 | 33 | 37 | 40 | 37 | 45 |
| 1989 | 12 | 36 | 41 | 43 | 42 | 53 |
| 1995 | 4 | 35 | 38 | 41 | 36 | 61 |
| 2002 | 4 | 41 | 42 | 44 | 38 | 79 |

**By class:**
* **Rates:** the US curve (proxy) plus 5 non-US yield proxies by 1988 and Euribor 1989. Free A carries only gilt
  1983, Euribor 1989 and Canada 1993.
* **Currencies with differentials:** 8 + DEM over 1973–1989, up to 13 with the EMS block.
* **Commodities:** 14 by 1975, 17 by 1980, 26 by 1990, 32 in 2002 on pysystemtrade's stricter full-year rule. The
  vendors' start-year rule gives 17, 20 and 27 at Pinnacle.

**Free A's shortfall is 1969–1974.** pysystemtrade has 1 commodity in 1970; the vendors have 7. The CHRIS mirror
fills that gap only with a defective splice.

## 5. Spot commodity prices are not futures excess returns

* **The identity** (cost of carry, reasoning):
  * A collateralised future earns about Δ*S*/*S* + (*y* − *u* − *r*) a year, with *y* the convenience yield and
    *u* storage.
  * Spot minus cash earns Δ*S*/*S* − *r*.
  * The gap is the net convenience yield *y* − *u*, i.e. the roll yield the spot proxy omits. It is positive in
    backwardation and negative in contango.
* **Size of the sign bias** (reasoning):
  * For a 12-month trend sign with annual spot changes of about 25% volatility, a carry of *c* flips the sign in
    about *c* / (0.25·√(2π)) of months: about 8% at *c* = 5%/yr, 16% at 10%, 32% at 20%.
  * VALIDATE's 90% sign-agreement gate would fail for any market whose |carry| is above about 6%/yr. In the
    energies and grains it often is.
  * The bias also has a sign: spot trend is long in contango markets whose futures lose money.
* **Averaging.** Monthly-average spot (World Bank, IMF) adds positive autocorrelation to monthly changes (Working
  1960, cited from memory, not read), which biases a trend test upward.
* **Can a 2003+ futures check validate a spot proxy?**
  * It can be run on spent data, exactly as VALIDATE did: pysystemtrade futures 2003–2024 against FRED daily WTI
    and Henry Hub spot, or the World Bank monthly file, with VALIDATE's five thresholds.
  * It would not carry over. The bias *is* the basis, and the basis regime of 2003–2024 (persistent energy contango
    after financialisation) differs from 1960–2002 (reasoning).
  * Bonds and FX validated because their carry is a known rate. Commodity carry is not.
* **Conclusion.** Free futures from 1969–70 remove the need for spot in the main read. Spot stays a labelled
  benchmark, for pre-1969 years only.

## 6. Independence against the spent samples (SCOPE §1)

| Segment | Grade |
|---|---|
| Commodities ex gold, 1959/1969–2002 (pysystemtrade, CHRIS mirror) | **independent**: S1's DBC starts 2006; WTI only a check |
| Gold 1975–2002 | **independent**: S7/S8/GLD are 2004+ |
| Non-US bond yields and futures before 2003 | **independent** |
| Currencies 1972–1989 (BIS, BoJ, SNB, pysystemtrade futures) | independent; same exposure as the proxy's H.10 leg, so one leg, never two |
| Currencies 1990–2003 | partly overlapping (S6 cross-sectional confirmation) |
| US rate futures 1978–2002 | same markets and dates as the proxy: they replace it or audit it, never add |
| Everything 2003+ | spent or partly spent (S1, S6, S7, S13) |

**Reconciliation without reading the sample.** One option: compare pysystemtrade with the CHRIS mirror (and later a
paid vendor) on 2003–2019, which is spent, with returns allowed. Before 2003, the comparison would count equal
settlement levels on matched contract-dates. That is not a return statistic, but whether it may be run is the
owner's call. It was not run here.

## 7. Search and access log

```
Hugging Face public API /api/datasets?search=, 2026-11-25 (hits): futures 83, commodity 100, commodities 53,
  treasury 43, "bond yields" 0, "bond yield" 0, fx 100, currency 60, forex 76, "exchange rates" 15, macro 100,
  "VIX futures" 0, "continuous contract" 0, CTA 100 (name matches), "trend following" 0, "interest rates" 5,
  "gold price" 39, "crude oil" 13, CHRIS 100 (name matches), quandl 1, "historical futures" 5, "futures daily" 0,
  "commodity futures" 2, "futures contracts" 0, "yield curve" 3, "government bond" 0, "macro history" 2,
  macrohistory 0, "global macro" 3, "economic data" 74, fred 100 (name matches), "interest rate" 12,
  "exchange rate" 31; author=paperswithbacktest (61 datasets).
  Relevant: paperswithbacktest (gated, paid: 401 on README and files), lynx1231 samples (recent),
  gold monthly averages 1970- (khaledAlhelwane, CC-BY, averages), US Treasury yield copies (duplicate FRED).
  Not tried: Kaggle (needs an account).
GitHub (gh search repos / code), 2026-11-25: "futures historical data csv", "continuous futures",
  "back-adjusted futures", "commodity futures data", "quandl CHRIS", "CHRIS futures", "wiki continuous futures",
  "futures contracts historical", "time series momentum futures", "trend following futures data",
  "commodities for the long run", "Global Macro Database", "macrohistory", "pst-csv-data", "futures-data",
  "CTA replication", "carry trade data", "government bond yields history"; code: CHRIS column headers
  ("Previous Day Open Interest", "Prev. Day Open Interest"), "Wiki Continuous Futures", "CME_C2".
  Found: pysystemtrade data/futures (used), webclinic017 CHRIS-layout mirror (used), bug-or-feature/pst-csv-data
  (subset, not used), KMueller-Lab/Global-Macro-Database (annual; search-summary), scattered single contracts.
  Replication packages with raw futures data: none found (Gorton-Rouwenhorst, Wright international curves:
  search-summary, no file located).
Institutions (generic User-Agent, no key): BIS bulk WS_CBPOL, WS_XRU (200; WS_XRU_D 404); BoJ API FM01, FM02,
  FM08 metadata and series (200); MoF JGB csv (200); Bundesbank BBSIS Svensson (200; a guessed BBK01 money-market
  key 404); BoE GLC month-end and daily zips (200); StatCan 10-10-0122 (200); SNB zimoma, rendoblim (200);
  ECB IRS (200); IMF SDMX dataflow list (200, IFS not inspected); BoC Valet (200, V122487 empty for 1960 query);
  RBA f02histhist.xls, f01hist.xls (403 blocked).
Terms pages: BIS terms (fetch-summary: statistics terms not on the page), BoE legal (fetch-summary: database under
  OGL v3), SNB terms (blocked: page did not render), BoJ terms (404).
```

## 8. Disclosures and not claimed

* **Values seen by accident.** Header previews printed levels, not returns; no statistic was computed from them:
  * the first Bundesbank 10y Svensson value (1972-09);
  * SNB Confederation spot yields for 1988-01;
  * the SNB call-money value for 1972-01;
  * the first MoF JGB row (1974-09-24).
* **No claim that the pysystemtrade or CHRIS-mirror data are correct.** Their quality is untested beyond presence,
  density and duplicate-date counts. Their provenance is undocumented.
* **Licences.** Institutional terms were only partly read (§7). Every source is used privately, with raw files
  uncommitted.
* **The power figures are design arithmetic** on an assumed AR₁ and literature correlations. They are upper bounds
  under the iid SE (PROCURE §4.1). The free counts use first dates only, and markets are assumed usable from their
  first full year.
