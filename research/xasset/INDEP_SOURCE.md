# An independent free source for pre-2003 commodity futures: inventory (2026-11-25)

**Status.** An inventory, not a test. **No return, signal, Sharpe ratio or correlation was computed from any data.**
Downloads were used for presence only: dates, counts, declared fields, table headings. No pre-2003 price level was
printed: OCR text was inspected with every digit replaced by `9`, and the EIA workbooks were read for dates only.

Purpose: Amendment 1 of `PREREG_XASSET.md` says the search for a free source of pre-2003 commodity futures that is
independent of pysystemtrade's likely upstream (Quandl/CHRIS) goes on, and Pinnacle ($248) is proposed only if
"doubt" remains after it. Doubt means fewer than 15 commodities pass, or a shared upstream (≥ 99% of pre-2003
sessions identical to 4 significant digits on at least half the passing markets).

Files:
* `indep_coverage.py`: the counts (EIA dates, Internet Archive headings and row-like lines, CFTC columns). It reads
  the raw files in `.cache/xasset-indep` (not committed) and writes the `counts` section of `INDEP_SOURCE.json`,
  with a sha256 for every raw file.
* `INDEP_SOURCE.json`: sources, market mapping, doubt assessment, counts.

Access labels as in `FREE_DATA.md`: **read-directly**, **coverage-count**, **fetch-summary**, **search-summary**,
**blocked**, **reasoning**.

---

## 1. Answer

**Two free sources are independent of Quandl/CHRIS. Neither resolves the doubt condition on its own.**

1. **US EIA, NYMEX futures, contracts 1–4** (coverage-count). Daily. Primary publisher, US public domain. Covers
   **HEATOIL** (1980–2002) and **GAS_US** (1994–2002) in the registered universe. It also covers two markets
   excluded before any check: CRUDE_W (1983–) and the unleaded leg of GASOILINE (1984-12 to 2006).
2. **Exchange statistical yearbooks on the Internet Archive** (coverage-count). These are 39 public microfiche scans,
   not lending-only. Each table gives **daily prices per individual contract month**, published by the exchange
   itself. They cover 12 more registered markets for some years, and none continuously:
   * **CBOT** soybean oil, soybean meal and oats: 1979/80–1986.
   * **CME** live cattle, feeder cattle and live hogs: 1980, 1982–1987.
   * **COMEX** gold and silver: 1979–1986.
   * **NYMEX** platinum and palladium: 1978–79.
   * **CSCE** cocoa and sugar: 1988–1994.

   The OCR is poor, so values would have to be keyed from the page images.

**Which pysystemtrade markets can be checked independently before 2003:** 14 of the 18 that have a mirror. Those
are SOYOIL, SOYMEAL, OATIES, LIVECOW, FEEDCOW, LEANHOG, GOLD, SILVER, PLAT, PALLAD, HEATOIL, GAS_US, COCOA and
SUGAR11.
* Daily over the whole pre-2003 overlap: only 2 (HEATOIL, GAS_US).
* Sampled years only: 12.
* Not covered:
  * COTTON2 and OJ: no NY Cotton Exchange yearbook found.
  * RICE: no item found.
  * COPPER: pysystemtrade starts in 1995, after the yearbooks end.
  * REDWHEAT: pysystemtrade starts in 1995; the KCBT yearbooks run 1980–1992.
* None of the no-mirror markets has a free independent source (CANOLA, GASOIL, SUGAR_WHITE, COCOA_LDN, WHEAT_ICE,
  MILK, MILKWET, MILLWHEAT, BRENT_W).

**Is that enough to resolve the doubt?**
* **Limb 1 (fewer than 15 pass): no.** The new sources add no market beyond the 18 that have a mirror. The count
  still rests on the Amendment 1 mirror checks, which have not been rerun on this branch. Fifteen passes would need
  15 of those 18.
* **Limb 2 (shared upstream): partly, and only with a further amendment.**
  * As written, Amendment 1 measures independence as 4-significant-digit identity between pysystemtrade and the
    mirror. Two *correct, independent* copies of the same official settlement are also identical, so the measure
    cannot tell a shared upstream from two correct copies (reasoning).
  * A primary-source level audit can. If pysystemtrade's contract-labelled price equals the exchange or EIA value
    on sampled sessions, the identity reflects correct data, whatever the upstream.
  * That audit is a new check. It needs a dated amendment before the read, with mechanical criteria (suggested in
    §4).

**Recommendation** (owner's decision):
* Do not buy Pinnacle yet. First rerun the Amendment 1 gate.
* If doubt remains on limb 2 only, register a primary-source audit: EIA daily for 2 markets, keyed yearbook samples
  for up to 12.
* If limb 1 fails (fewer than 15 pass), these free sources cannot fix it. Pinnacle (or Portara) would then be the
  only route to more commodity markets with a second source.
* Pinnacle's own upstream is undocumented (PROCURE §2). A purchase would not itself prove independence from
  Barchart or CSI, which may be the common upstream of modern vendors (search-summary: Quandl distributed Barchart
  futures data).

## 2. Sources found independent of Quandl/CHRIS

### 2.1 US EIA: NYMEX futures prices, contracts 1–4

* **URL.** <https://www.eia.gov/dnav/pet/pet_pri_fut_s1_d.htm>; workbooks at
  `https://www.eia.gov/dnav/pet/hist_xls/<id>d.xls` and `https://www.eia.gov/dnav/ng/hist_xls/RNGC<n>d.xls`
  (HTTP 200, no key).
* **Fields.** "The futures prices shown are the official daily closing prices at 2:30 p.m. from the trading floor of
  the New York Mercantile Exchange (NYMEX) for a specific delivery month" (definitions page, read-directly).
  Settlement is not named.
* **Contract identity.** Position, not label:
  * "Contract 1: A futures contract specifying the earliest delivery date … After a contract expires, Contract 1
    for the remainder of that calendar month is the second following month. Contract 2-4 represent the successive
    delivery months" (read-directly).
  * Each date maps to a delivery month mechanically from the published expiry rule. No row carries a contract code.
    The natural-gas definitions page was not read; the petroleum page was.
* **Licence.** "U.S. government publications are in the public domain" (EIA copyrights page, fetch-summary). The
  same page warns that third-party material may be protected, and does not name NYMEX.
* **Upstream.** NYMEX, as stated by EIA; the workbook says "Source: U.S. Energy Information Administration".
  Independent of Quandl/CHRIS in its publication chain: Quandl republished EIA, not the reverse (reasoning).
* **Coverage** (coverage-count; `counts.eia`). Daily, with no duplicate or out-of-order dates. Every series ends on
  2024-04-05.

| Series | Market (pysystemtrade) | First date | Sessions before 2003 | Obs/yr before 2003 (full years) | Max gap before 2003 |
|---|---|---|---:|---|---:|
| RCLC1 / RCLC3 | WTI (CRUDE_W, excluded) | 1983-04-04 / 1983-03-30 | 4,878 / 4,889 | 235–252 | 6–7 d |
| RCLC2 / RCLC4 | WTI | 1985-01-02 | 4,280 / 4,241 | 217–251 | 7 d |
| EER_EPD2F_PE1 / PE3 | NY Harbor No. 2 heating oil (HEATOIL) | 1980-01-02 | 4,822 / 5,015 | 162–251 | 14 d |
| EER_EPD2F_PE2 / PE4 | heating oil | 1994-02-02 / 1994-01-14 | 1,608 / 1,759 | 162–207 | 11–15 d |
| RNGC1–4 | Henry Hub natural gas (GAS_US) | 1993-12-20 .. 1994-01-19 | 2,131–2,179 | 227–251 | 7–8 d |
| EER_EPMR_PE1 / PE3 | NY Harbor regular (unleaded) gasoline (GASOILINE leg, excluded) | 1985-01-02 / 1984-12-03 | 3,977 / 3,978 | 184–248 | 9–12 d |
| EER_EPMR_PE2 / PE4 | gasoline | 1994 | 1,858 / 1,852 | 194–225 | 11–12 d |
| EER_EPMRR_PE1–4 | RBOB | 2005-10-03 | 0 | – | – |
| EER_EPLLPA_PE1–4 | Mont Belvieu propane (not a pysystemtrade pre-2003 market) | 1993-12 .. 1994-03 | 1,734–1,874 | 178–231 | 13–26 d |

**Defects** (typed; each needs a contract before use):
* Contract 2/4 for heating oil and gasoline exist only from 1994.
* Heating oil has thin years before 1994 (minimum 162 observations a year).
* "Closing price" is not declared to be the settlement.
* The contract month is implied by the expiry rule, not carried per row.

### 2.2 Exchange statistical yearbooks (Internet Archive, Statistical Reference Index microfiche)

* **URL.** `https://archive.org/details/<identifier>`; 39 items in `counts.internet_archive`, each with its OCR text
  sha256.
* **Access.** All 39 have `access-restricted-item` unset: no account needed, PDF and OCR text downloadable.
  * Print copies of the CBOT annuals for 1973 and 1975–1977, and duplicates for 1981–1983, are lending-only
    (`inlibrary`): **blocked** under the no-account rule.
  * The CRB Commodity Year Book is in the same collection for 1980–1995. It was not inspected; it is mostly monthly
    and annual statistics (reasoning).
* **Layout** (read-directly on digit-masked OCR):

| Exchange | Editions found (public) | Table | Price |
|---|---|---|---|
| CBOT | 1979 (soy complex), 1980, 1981, 1984, 1985, 1986; metals/rates 1981, 1982, 1984, 1985; supplements 1987, 1988 (no price headings found) | per contract month, daily Open/High/Low/Close ("WHEAT FUTURES PRICES", "SOYBEAN OIL FUTURES PRICES") | "Close"; settlement versus close not declared |
| CME | 1980, 1982, 1983, 1984, 1985–86, 1987 | "Daily Price Range, Volume & … Daily Settlement Prices"; "DAILY SETTLEMENT PRICES OF THE AUGUST … LIVE CATTLE, LIVE HOGS" | settlement, defined as "established at the close … generally the last sale" |
| COMEX | 1979, 1980, 1981, 1982–83, 1984, 1985–86 | "GOLD / SILVER / COPPER CLOSING AND SETTLEMENT FUTURES PRICES", by delivery month | closing and settlement |
| NYMEX | 1978–79 | "Platinum / Palladium / No. 2 Heating Oil Futures Prices: Open, High, Low, Last, Volume, Open Interest" | last |
| KCBT | 1980, 1981, 1984–1987, 1990, 1992 | "DATE SETTLEMENT CHANGE OPENING RANGE HIGH LOW CLOSING RANGE VOLUME …" | settlement |
| CSCE | 1988, 1989, 1990–91, 1992, 1993, 1994 | contents: "Daily Opening / High-Low / Closing / Settlement Prices" | settlement |

* **Licence.** None stated. These are exchange-compiled publications. Prices are facts; whether that frees them for
  reuse is a legal question, not answered here (reasoning). Keep scans and any transcription in `.cache`, never
  committed.
* **Upstream.** The exchanges themselves: primary, and independent of Quandl/CHRIS by construction.
* **Coverage counts** (`counts.internet_archive`). Two counts are recorded:
  * price-heading lines that name a market: a lower bound, since misspelt OCR is missed;
  * "row-like" lines: a day number followed by at least 5 tokens.

  They show the tables are present. They do not show that the values are legible. Some editions OCR badly: CSCE
  1989 has 10 row-like lines, CBOT 1985 grains 103 and CME 1984 352, so their tables are effectively images.
* **Defects:**
  * the OCR cannot be parsed into prices (mangled fractions, split columns), so values must be keyed from page
    images;
  * the years are sparse;
  * CBOT's silver and gold are different contracts from COMEX's (pysystemtrade uses COMEX);
  * live hogs before the 1996–97 change to lean hogs are a different contract specification from today's LEANHOG.

## 3. Sources checked and not usable

| Source | Access | Finding |
|---|---|---|
| CFTC Commitments of Traders, `deacot1986_2016.zip` | coverage-count | Weekly 1986-01-15 .. 2016-12-27, 129 columns, **0 price or settlement columns** |
| CFTC "Futures Contracts Traded", "Volume of Futures Trading" (IA microfiche) | search-summary | volume only |
| FRED | fetch-summary (curl timed out) | no NYMEX/CME/CBOT futures price series; futures-titled series start 2003+ (VXTYN) or 2024+; DCOILWTICO is EIA spot |
| USDA ERS season-average price forecast inputs | search-summary | daily futures, but from 2003/04 only |
| USDA ERS feed-grain and oil-crop yearbooks; NASS Agricultural Prices | search-summary / reasoning | cash and received prices, not futures |
| farmdoc (Illinois) basis files | search-summary | weekly cash and basis from 1975; futures reference not confirmed |
| World Gold Council Goldhub | fetch-summary | averages from 1978; LBMA daily history removed 2025-03-18 at ICE's request; spot, not futures |
| ICE Report Center | fetch-summary | end-of-day packages sold by subscription |
| CME DataMine | blocked (PROCURE §7) | paid |
| stooq continuous futures CSV | blocked | JavaScript browser check |
| AQR "Commodities for the Long Run" data | fetch-summary; file **not downloaded** | portfolio-level monthly excess returns only. **Hazard**: it shows pre-2003 commodity returns |
| AQR time-series momentum datasets | reasoning; **not opened** | **Hazard**: trend-strategy returns over the registered markets and years; opening them would spend the sample |
| Replication packages: Gorton-Rouwenhorst 2006, Bhardwaj-Gorton-Rouwenhorst 2015, Koijen-Moskowitz-Pedersen-Vrugt 2018, Erb-Harvey 2006, Szymanowska et al. 2014 | search-summary | no contract-level price file located; GR name the CRB and the LME as data sources |
| GitHub (`gh search repos` / `code`) | search-summary | "CBOT statistical annual", "commodity research bureau yearbook csv", "futures settlement 1985 csv individual contract", "EIA RCLC1", "CLZ1990", "futures data", "commodity futures", "settlement prices", and others: nothing new and non-Quandl |
| Hugging Face API | search-summary | nymex 0, cbot 4, comex 4, eia 17, settlement 70, "futures prices" 0, crb 18, "commodity prices" 32 hits; none relevant |

**pysystemtrade's upstream, for the record** (read-directly, `docs/data.md`):
* the docs name Barchart, and also Norgate, as the route to individual-contract history;
* they say some mini-contract histories "have been calculated from main-size contracts".

That is consistent with the back-fills in FREE_DATA §2. The shipped CSVs' own pre-2003 source is still not stated.

## 4. What an independent audit would look like (for an amendment; not run)

This is a suggestion only. It must be fixed before any value is keyed or compared.
* **Markets:** the 14 in §1, and only those that pass the Amendment 1 checks.
* **EIA (HEATOIL, GAS_US).** Map each session's contract 1–4 to its delivery month with the published rule. Compare
  with pysystemtrade's PRICE or CARRY column on the *same contract label*, never the nearest column. Use every
  common pre-2003 session except ±`ROLL_WINDOW_DAYS` around EIA expiries. Pass: ≥ 95% agree within one tick.
* **Yearbooks.**
  * Before keying, draw a random sample with a registered seed: about 20 sessions per edition per market.
  * Key the price for pysystemtrade's contract label from the page image, by two independent keyings with
    disagreements resolved from the image.
  * Pass: ≥ 95% agree within one tick, or the exchange's closing range at CBOT.
* **What it proves.** It shows level agreement with a primary source on the contracts traded. It is a level check,
  not a return statistic, and it is the same kind of check Amendment 1 already allows before 2003.
* **What it costs.** No money. Roughly 14 markets × 3–7 editions × 20 sessions ≈ 1,000–2,000 keyed values.

## 5. Disclosures and not claimed

* **No pre-2003 price was seen.** Masked OCR excerpts and EIA date counts only. Two exceptions: section headings,
  and contract specifications (tick sizes, limits) with their digits masked.
* **No claim about which markets will pass.** The Amendment 1 gate has not been rerun.
* **No claim that either source is error-free.** The EIA "closing" price may differ from settlement on some days.
  Yearbook typography and OCR are untested.
* **Licences** are as read. The yearbooks carry no licence. The EIA terms do not name NYMEX.
* **Raw files** are frozen with their sha256 in `INDEP_SOURCE.json` and kept in `.cache/xasset-indep`, not
  committed: 24 EIA workbooks, 39 OCR texts, the CFTC zip and the EIA notes page. The Internet Archive metadata
  files are kept but not hashed.
