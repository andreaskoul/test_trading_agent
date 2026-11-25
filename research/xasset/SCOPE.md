# Cross-asset trend and crisis-alpha book: data inventory and test design (scoping memo, 2026-11-25)

**Status.** This is an inventory and a design memo, not a test. No strategy return, Sharpe ratio, signal result or
correlation of any return series was computed for it. Downloads were limited to coverage checks: first and last
date, row counts, calendar gaps, column names. Several sources could not be reached; they are listed in §9. Section
§0 records two places where a few data values were printed by accident.

Research only. Nothing under `fund/` changes. Instruments, hedges and net exposure are the owner's strategic policy
(CLAUDE.md rule 17). This memo proposes; the owner decides.

Access labels used below:
* `repo`: read from files in this repository or its branches;
* `read`: the source page or file itself was opened and the relevant part read;
* `fetch-summary`: the page was opened by a fetch tool and its answer is a summary of that page;
* `search-summary`: only a search engine's summary was seen;
* `reasoning`: my inference, which no source states.

Machine-readable version: `SCOPE.json`. Power arithmetic: `power.py` → `POWER.json`, which reads no data.

---

## 0. Disclosures about this scoping run

* **Values seen by accident.** No statistic was computed from any of them, and none is used below.
  * A structure-printing script printed one row of the AQR *Commodities for the Long Run* file: the 1899-12 month,
    ten numbers.
  * Two shell previews showed the first three daily levels of Cboe VIX9D (January 2011) and the first rows of two
    VIX futures contract files (May 2004, January 2013).
* **Published literature numbers** in the Moskowitz-Ooi-Pedersen and Hurst-Ooi-Pedersen PDFs were visible while
  their method sections were read. They are published results, not this project's data.
* **Spent results** quoted in §1 (for example the cross-asset sleeve's p 0.154) are copied from the repository's
  own recorded reads.

## 1. Spent samples

The searches were `git ls-tree` file names and `git grep` content on `origin/main` and every `origin/research/*`
branch. The keywords were trend, TSMOM, time-series momentum, Moskowitz, crisis alpha, managed futures, cross-asset,
TLT, IEF, GLD, DBC, VXX, BXM, carry, bond, commodity, gold, VIX, currency, FX, option and futures. Access for every
row is `repo`.

| # | Study (branch: path) | Instruments | Dates and frequency | What was read | Outcome |
|---|---|---|---|---|---|
| S1 | Cross-asset trend sleeve X1 (`research/tree-layer3`: `research/tree/L4_explore`) | IEF, TLT, GLD, DBC, UUP (yfinance), long/short, 12-month sign, 10% risk each, sleeve gross cap 2, 5 bp | Daily prices, weekly sleeve. Development 2003-07-31 .. 2019-12-19 (831 weeks), open; test 2020–2025 (302 weeks) | **Test read once** (`READ_X1.lock` 2026-11-19T14:32:08Z), whole-fund level against B0 | Fail: ΔSharpe +0.115, SE 0.113, p 0.154; DSR 0.617. Development statistics were also examined |
| S2 | Leveraged trend core (`main`: `research/exposure`) | French daily US market (CRSP VW) and RF; SPY | 1926-07-01 .. 2026-09-30 daily; SPY 2016-03 .. 2026-11 | One read, full sample (2026-11-04) | 200-day 1.3×/0.7× passed; it became the core |
| S3 | Adaptive exposure rules (`main`: `research/sharpe/PREREG.md`, `READ.lock`, `READ_US.lock`, `READ_NN.lock`; `research/adaptive-core`) | French developed markets Europe, Japan, Asia Pacific ex Japan; US century. Rules include equity-index **time-series momentum over 1–12 months** (MOP 2012), ensembles, fixed-share, volatility, MLP/CNN | Daily, 1990-07 .. 2025-12 (evaluated 1993-06 ..); US 1926–2026 | Read once (2026-11-09/10) | Fail against the 200-day rule. "The three regions are closed to further exposure rules" (§6) |
| S4 | Regime edge (`main`: `research/regime`) | S&P 500 factor books; French 49 industries and UMD (1926–2025); regional momentum | Weekly. US development ≤ 2019, OOS 2020–2025 once; long-history development 1927–1999, OOS 2000–2025; international 1992–2025 (`INT_READ.lock` 2026-11-07) | Read once | Momentum-off-in-panic (H16) survived; H14 failed |
| S5 | Capital-efficient core (`main`: `research/sharpe/PREREG_CAPITAL.md`, `READ_CAPITAL.lock`) | Synthetic 2× fund on the French market; SSO, SPY; whole-fund ledger | 1927–2026 daily; 2006-07 .. 2026; fund 2020–2025 weekly | Read once (2026-11-21) | 2× fund financing beats margin by +0.25 %/yr |
| S6 | Cross-sectional FX (`research/cross-sectional`: `reports/research/PROTOCOL_fx*.md`, `fx/README.md`) | 17 currencies against USD: Fed H.10 (FRED) for 12, Yahoo for 5; OECD 3-month rates. Signals: carry, 12-1 cross-sectional momentum, 3- and 1-month momentum, reversal, value, combo, ridge | Weekly. Development 2004-01 .. 2015-12; holdout 2016-01 .. 2026-03, one pass; confirmation 1990-01 .. 2003-12 (12 currencies), one pass | Holdout and confirmation each read once (2026-09) | 0 of 16 pass. Carry failed only the DSR. Reversal was not confirmed |
| S7 | Daily gold (`research/daily-horizon`: `reports/research/PROTOCOL_daily.md`) | GC futures and GLD. Features: CFTC COT, real rates, DXY, VIX; rules include `tsmom12` = sign(250-day return) | Daily. Development 2006-06-13 .. 2018-12-31; holdout 2019-01-01 .. 2026-03-31, one pass | Holdout read once (2026-09-26) | 0 of 14 pass |
| S8 | Intraday gold (`research/baseline-ladder`) | XAUUSD spot, GC=F | 60-minute bars. Development 2012-05 .. 2022-03; holdout 2023-01 .. 2026-03 | Holdout read once | ML ladder; not a trend test |
| S9 | Complexity timing (`research/tree-layer3`: `L6_complexity`) | State variables: ^VIX (2008–2025), DTB3, DGS10, BAA − AAA, used to time the MASTER book | Weekly, development 2015–2019 | Development only; the gate failed; no read | The VIX **level** 2008–2025 has been used as a predictor, not as a traded instrument |
| S10 | TrendSpider SSO critique (`main`: `research/trendspider`) | SPY, SSO, 15-minute bars | 2016–2026 | Reads spent (2026-11-04) | Fail |
| S11 | Risk-field round 10 (`research/f2-forward-book`: `research/riskfield/options.py`, `PREREG.md` Amendment 14) | Alpaca single-stock option bars (expired contracts) | Daily. Development 2024-03 .. 2024-12; OOS 2025 | Read | Option signals failed development |
| S12 | Event risk (`main`: `research/eventrisk`) | Macro announcement days (FOMC, CPI, payrolls) for hedged equity variance | 2016–2025 | Read | Macro days fail |
| S13 | Fund window | Whole fund (core plus MASTER book), weekly | 2020–2025 reused by many reads; 2026 sealed | Many | Not fresh for any new book |

**What this leaves.** The following have never been read as traded instruments in this project:
* US Treasuries before 2003;
* currencies before 1990, and any time-series (rather than cross-sectional) currency signal;
* commodities other than DBC, gold and WTI-as-a-check;
* credit ETFs, international bond ETFs and FX ETFs;
* VIX futures;
* Cboe option benchmark indices.

Unread is not the same as independent. §2 grades each one.

## 2. Free data not yet spent

Two owner rules apply to every row:
* **Tradability:** *executable* means prices of instruments we could trade. *Proxy* means it is built from market
  yields or spot rates of tradable instruments, with an approximation error. *Benchmark* means a paper index or
  academic factor. A benchmark can set a prior; it cannot be the test.
* **Independence** is graded over markets × dates × economic exposure against §1:
  * *independent*: no spent market, and no spent exposure in those dates;
  * *partly overlapping*: shares dates or an exposure, but not both with the same market;
  * *not independent*: mostly the same markets or exposures as a spent read, in the same dates.

All dates below come from this run's coverage checks (`repo`-style checks of downloaded files on 2026-11-25), unless
marked otherwise.

### 2a. ETF-only universe

Every inception date is Yahoo's `firstTradeDate` metadata (fetched 2026-11-25). No prices were downloaded.

| Exposure | Tickers (first Yahoo trade date) | Tradability | Independence |
|---|---|---|---|
| US Treasuries | SHY, IEF, TLT 2002-07-30; IEI 2007-01-11 | executable | **not independent**: IEF and TLT are S1's instruments, 2003–2025 |
| Aggregate, TIPS | AGG 2003-09-29; BND 2007-04-10; TIP 2003-12-05 | executable | not independent: US rates are spent through S1 |
| Credit | LQD 2002-07-30; HYG 2007-04-11; JNK 2007-12-04; EMB 2007-12-19 | executable | partly overlapping: US rates are spent and HY carries equity beta; credit itself is unread |
| International bonds | BWX 2007-10-11 | executable | partly overlapping: it moves with the dollar (UUP in S1) |
| Gold, silver | GLD 2004-11-18; IAU 2005-01-28; SLV 2006-04-28 | executable | **not independent**: GLD in S1, gold in S7 and S8 |
| Commodities | DBC 2006-02-06; GSG 2006-07-21; DBA, DBB 2007-01-05; USO 2006-04-10; UNG 2007-04-18; PDBC 2014-11-07 | executable | DBC is not independent (S1). Sector funds are partly overlapping with DBC |
| Dollar and currencies | UUP, UDN 2007-03-01; FXE 2005-12-12; FXY 2007-02-13; FXB, FXF, FXA, FXC 2006-06-26; CEW 2009-06-02 | executable | not independent: UUP is in S1; the currencies are in S6, 2004–2026 |
| Volatility | VIXY, VIXM 2011-01-04; SVXY 2011-10-04; VXX (Series B) 2018-01-25 | executable | partly overlapping: US equity volatility, and the VIX level in S9 |
| Equity ex-US | EFA 2001-08-27; EEM 2003-04-14; VEU 2007-03-08 | executable | not independent: French regions 1990–2025 (S3, S4) |
| Managed-futures funds (benchmarks of the strategy itself) | DBMF 2019-05-08; KMLM 2020-12-02; CTA 2022-03-08 | executable, but a fund of the strategy | not independent: inside the fund window (S13) |

**Longer proxies for the ETF exposures.** All are from FRED `fredgraph.csv`, fetched 2026-11-25, `read` for
coverage.

| Series | First .. last | Frequency, issues | Independence |
|---|---|---|---|
| DGS1, DGS5, DGS10, DGS20 | 1962-01-02 .. 2026-11-23 | Daily. DGS20 has a gap: 2,411 missing values (the 20-year was not issued 1987–1993; `reasoning`) | Proxy for Treasuries. 1962–2002 is **independent** of S1. Rates were used only as states (S9, 2008–2025) |
| DGS2 | 1976-06-01 .. | daily | as above |
| DGS7 | 1969-07-01 .. | daily | as above |
| DGS30 | 1977-02-15 .. | daily; the 2002–2006 suspension of the 30-year should be checked (`reasoning`) | as above |
| DTB3; TB3MS; DGS3MO | 1954-01-04 ..; 1934-01 ..; 1981-09-01 .. | daily; monthly **average**; daily | cash leg |
| GS10, GS1 | 1953-04 .. | monthly **averages**, so they fail a point-in-time contract for return construction | |
| AAA, BAA | 1919-01 .. | monthly averages; DBAA is daily from 1986-01-02 | Proxy for credit. Before 2003, independent |
| ICE BofA indices (BAMLCC0A0CMTRIV, BAMLHYH0A0HYM2TRIV, BAMLH0A0HYM2) | **2023-11-27** .. 2026-11-23 | FRED now carries only about 3 years | unusable for history |
| OECD long yields IRLTLT01 (DE 1956-05; GB, FR 1960-01; CA 1955-01; AU 1969-07; JP 1989-01; IT 1991-03) | .. 2026-10 | Monthly; the averaging convention was not checked (`reasoning`: MEI series are usually monthly averages) | Proxy for international bonds. Before 2003, independent of S1 |
| H.10 FX, daily (JPY, GBP, CHF, CAD, AUD, SEK, NOK, DKK) | 1971-01-04 .. 2026-11-20 | Daily noon-NY. EUR from 1999-01-04. DEM is monthly only (EXGEUS, 1971 .. 2001-12) | **1971–1989 independent**; 1990–2026 spent cross-sectionally (S6) |
| OECD 3-month rates IR3TIB01 | GB 1957; DE 1960; CA 1956; AU 1968; FR 1970; **CH 1999-07; JP 2002-04** | Monthly | Before 1999 the Swiss franc and yen have no carry accrual; a typed defect to solve before use |
| DTWEXBGS; TWEXBMTH | 2006-01-02 ..; 1973-01 .. 2019-12 | daily; monthly | dollar index |
| DCOILWTICO; WTISPLC | 1986-01-02 ..; 1946-01 .. | daily; monthly | oil spot (S1 used WTI as a check) |
| LBMA gold (GOLDAMGBD228NLBM, GOLDPMGBD228NLBM) | — | **404**: removed from FRED | gold needs another source |
| VIXCLS | 1990-01-02 .. 2026-11-23 | daily | VIX level; partly overlapping (S9) |

**Other free long proxies:**
* **World Bank Pink Sheet, monthly** (`thedocs.worldbank.org/.../CMO-Historical-Data-Monthly.xlsx`, `read` for
  structure).
  * 1960M01 .. 2024M12. The file's header says "Updated on January"; this URL is an old vintage.
  * 71 commodities, gold included.
  * **These are monthly average spot prices.** Averaging induces positive autocorrelation, which biases any trend
    test upward (`reasoning`, a standard result). They fail a content contract for momentum returns.
* **Jordà-Schularick-Taylor Macrohistory R6** (`macrohistory.net`, `read` for structure).
  * The file served is Stata, despite its .xlsx name: 18 countries, 1870–2020, annual.
  * Variables include `bond_tr`, `eq_tr`, `bill_rate`, `xrusd` and `ltrate`.
  * Benchmark-grade: annual total-return reconstructions, not executable. It ends in 2020.
* **Shiller `ie_data.xls`** (Yale and the newer site): downloaded, **not inspected** (no xls reader installed).
  Monthly US long rate from 1871 per the file's documentation (`reasoning`, not read here).

### 2b. Futures universe

| Source | URL | Access | Coverage | Frequency, issues | Tradability | Independence |
|---|---|---|---|---|---|---|
| AQR, *Time Series Momentum: Factors, Monthly* | aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Time-Series-Momentum-Factors-Monthly.xlsx | `read` (structure, header text) | 1985-01-31 .. 2026-05-29; 497 months; columns TSMOM, TSMOM^CM, ^EQ, ^FI, ^FX | Monthly. "A 12-month time series momentum strategy with a 1-month holding period". "AQR reconstructs the full history each time" (revisions, so freeze at first use, rule 4). The Definitions and Data Sources tabs are embedded images, not read | **benchmark** (factor returns only, no raw prices) | not independent: covers S1's exposures 2003–2025 and S3's equity TSMOM |
| AQR, *Century of Factor Premia, Monthly* (Ilmanen, Israel, Lee, Moskowitz, Thapar 2021) | …/Century-of-Factor-Premia-Monthly.xlsx | `read` (structure) | 1926-07 .. 2026-02, 1,196 months. Columns: value, momentum (**cross-sectional**), carry and defensive for equity indices, fixed income, currencies (from 1974-02) and commodities (1,123 months), plus "Market" per asset class | Monthly, gross of costs; full history rebuilt at each update | benchmark | partly overlapping: long; the equity-index columns overlap S2–S4 |
| AQR, *Value and Momentum Everywhere* | …/Value-and-Momentum-Everywhere-Factors-Monthly.xlsx | `read` (structure) | 1972-01 .. 2026-08, 656 months; value and momentum per asset class (EQ, FX, FI, COM) | Monthly; rank-weighted cross-sectional | benchmark | partly overlapping |
| AQR, *Commodities for the Long Run* (Levine, Ooi, Richardson, Sasseville 2018) | …/Commodities-for-the-Long-Run-Index-Level-Data-Monthly.xlsx | `read` (structure) | 1877-02 .. 2025-05 (date rows from 1900-01). **Portfolio-level only**: equal-weight excess return, spot, carry, a long/short portfolio, backwardation and inflation states | Monthly; futures-based | benchmark | before 2003, independent of S1's DBC and S7's gold in dates |
| AQR data library terms | aqr.com/Terms-of-Use; About-the-AQR-Data-Library | `fetch-summary` | — | Citation asked ("AQR Capital Management, LLC"). The general terms prohibit reproducing or redistributing site content without consent. Data are updated monthly with about a two-month lag, and the whole history is revised | Committing AQR files to the repo would be redistribution: keep them in `.cache`, record a sha256, do not commit | |
| Hurst-Ooi-Pedersen 2017, *A Century of Evidence on Trend-Following Investing* | fairmodel.econ.yale.edu/ec439/hurst.pdf | `read` (method pages; Appendix B) | 67 markets, 1880–2016 | **No dataset is published** (search found none; `search-summary`) | literature prior only | — |
| Yahoo continuous front-month futures | query1.finance.yahoo.com chart API, metadata only | `read` (metadata) | ES, NQ, ZN, ZB, ZF, GC, SI, HG, CL, NG, ZC, ZW, CC, KC, 6E, 6J, 6B and others from 2000 (ZT 2000-06; 6C 2000-05; BZ 2007-07; RTY 2017-07; NKD 2004-02). DX-Y.NYB from 1971; ^SPGSCI from 1984 (index level; its total- or excess-return type was not checked) | Daily. **Front-month splice without roll adjustment**: returns across rolls are wrong. S7 found GC differs from GLD by 0.35 %/yr. No individual contracts | executable markets, defective series | not independent: 2003–2025 covers S1's rates, gold, commodities and dollar |
| Cboe VIX futures, per contract | cboe.com/us/futures/market_statistics/historical_data/product/list/VX/ (JSON); cdn.cboe.com/data/us/futures/market_statistics/historical_data/VX/VX_<expiry>.csv; archive cdn.cboe.com/resources/futures/archive/volume-and-price/CFE_<MYY>_VX.csv | `read` | Listing: 2013-01 .. 2027-01 expiries, 635 contracts (monthly and weekly). Archive verified for the May 2004 contract (first trade 2004-03-26) | Daily OHLC, settle, volume, open interest. Before 2007 the prices are on the old ×10 scale (`reasoning` from the 2004 file's levels; check against the Cboe notice) | **executable, contract-level** | partly overlapping: US equity volatility exposure; the VIX level was used as a state (S9, 2008–2025); VX returns never read |
| Stooq continuous futures | stooq.com/q/d/l/?s=gc.f | **blocked** (JavaScript challenge; S1 also recorded Stooq as blocked) | — | — | — | — |
| Nasdaq Data Link CHRIS | data.nasdaq.com/api/v3/datasets/CHRIS/CME_CL1.csv | **blocked** (HTTP 403). Whether CHRIS is still published was not settled (`search-summary` inconclusive) | — | — | — | — |
| Pinnacle CLC, CSI, Norgate, CME DataMine | — | not attempted: paid products (`reasoning`) | — | — | — | — |

**No free source of raw, roll-adjusted, long-history futures prices was found in what loaded.** Stooq and Nasdaq
were blocked; the paid vendors were not tried. Long futures history is therefore available only as AQR factor
returns (benchmark) or as proxies built from yields and spot rates (§2a).

### 2c. Options universe

The Cboe index files are `cdn.cboe.com/api/global/us_indices/daily_prices/<SYM>_History.csv` (307 redirect to
cdn-api.cboe.com), `read` for coverage on 2026-11-25.

| Series | First .. last | Rows | Issues | Tradability | Independence |
|---|---|---|---|---|---|
| PUT (cash-secured ATM put write) | **daily only from 2007**; 7 stray rows 1991–2004 | 5,013 | Index history from 1986 is not in this file. The older `resources/spx/putdailyprice.csv` is **403** | benchmark | partly overlapping: S&P 500 exposure = the core's market (S2), but a different payoff; never read |
| BXM (buy-write) | 2002-03-22 .. 2026-11-24 | 6,207 | `bxmarchive.csv` and `bxmcurrent.csv` are **403** (pre-2002 history not reached) | benchmark | partly overlapping |
| BXMD, CNDR, BFLY | 1986-06-20 .. 2026-11 | 10,180 | daily | benchmark | partly overlapping |
| PPUT (5% OTM protective put) | 1986-06-30 .. 2026-11-24 | 10,175 | daily | benchmark | partly overlapping |
| CLL (collar) | 2008-08-26 .. | 4,549 | | benchmark | partly overlapping |
| VXTH (VIX tail hedge) | 2006-03-31 .. | 5,192 | | benchmark | partly overlapping |
| VIX | 1990-01-02 .. 2026-11-23 | 9,322 | OHLC | not tradable itself | partly overlapping (S9) |
| VIX3M | 2009-09-18 .. | 4,323 | | implied series | partly overlapping |
| VIX9D | 2011-01-04 .. | — | | implied series | partly overlapping |
| VVIX | 2006-03-06 .. | 5,154 | sparse in 2006 (21-day gaps) | implied series | partly overlapping |
| SKEW | 1990-01-02 .. | 9,276 | a 13-day gap in 2000-09 | implied series | partly overlapping |
| SPVXSTR (S&P VIX short-term futures index), VXST | — | — | **403** | — | — |
| Option prices (SPX, SPY) | — | — | No free history found. The project's Alpaca option bars start in 2024-02 (S11) | executable but only about 2 years | — |

**Methodology, `search-summary` only.** PUT holds one- and three-month T-bills and sells ATM SPX puts monthly.
The puts settle at the SOQ (special opening quotation) on the third-Friday expiry. The strike is the listed strike
nearest to, but not above, the S&P 500 value before 11:00 ET. The full methodology PDF
(`cdn.cboe.com/resources/indices/governance/Cboe_SP_500_PutWrite_Indices_Methodology.pdf`) was not opened.

## 3. Full implementation costs, by universe

Figures marked `reasoning` are prior knowledge, not checked in this run. The pre-registration must copy each one
from the issuer, the exchange or the account's own fills, at a named date.

| Item | ETF universe | Futures universe | Options universe |
|---|---|---|---|
| Spread and commission | Liquid Treasury, gold and credit ETFs: about 1–3 bp a side. DBC, UUP and FX ETFs are wider (`reasoning`). Measured on this account: 1.57 bp a side on the 7B book and SPY fills (allocation Amendment 2, `repo`) | About 1 tick plus about $1–2.5 a contract. One tick on 10-year notes is about 1.4 bp of notional (`reasoning`). HOP: costs ×2 for 1993–2002 and ×6 for 1880–1992, after Jones 2002 (`read`, Appendix B) | SPX options: wide relative to premium, especially OTM puts. Exchange and clearing fees per contract (`reasoning`). The paper account has no measured option fills |
| Holding cost | Expense ratios, `reasoning`, to verify: IEF and TLT about 0.15%, GLD about 0.40%, DBC about 0.85%, UUP about 0.77%, VIXY about 0.85% a year | None. The futures price carries the financing | None for listed options. Index benchmarks ignore any margin cost |
| Roll | Embedded in commodity and VIX ETPs: they roll futures, and contango is a cost inside the price | Explicit: quarterly for rates, FX and equity indices; monthly for energy and VIX. Each roll is two extra trades on the held size, plus calendar-spread slippage. HOP note that their simulation omits roll costs (`read`) | Monthly re-strike (PUT, BXM): one round trip a month |
| Collateral and financing | Longs above 1× NAV are financed at the margin rate, rf + 2.43% (`strategies.MARGIN_SPREAD`, `repo`). Short sales earn a rebate below rf and pay borrow (FX and commodity ETFs can be hard to borrow; `reasoning`) | Collateral in T-bills earns rf, so the futures return is an excess return. Total return = excess + rf on the NAV held | Cash-secured puts hold T-bills equal to the strike (PUT design, `search-summary`) |
| Margin | Reg T: 50% initial; the broker sets maintenance | Exchange initial margin, of the order of 2–15% of notional by contract (`reasoning`; take it from the exchange at registration). Maintenance about 90% of initial. Daily variation margin in cash | Short options: Reg T or portfolio margin. A short put's margin can jump in a crash |
| Settlement and exercise | T+1 | Rates and FX: physical delivery, so trade only front or next and roll before first notice. Equity and VIX: cash settled. VIX futures settle on the VRO, the Wednesday opening quotation (`reasoning`) | SPX: European, cash-settled. Monthlies are AM-settled at the SOQ, SPXW weeklies PM-settled. SPY: American, physical delivery, early-exercise and dividend-assignment risk |
| Account | Possible in the current paper account | Not checked whether the account offers futures (`reasoning`: a futures-capable broker may be needed) | The account offers equity options; index-option access not checked |
| Size granularity | Fine | Coarse at small NAV; micro contracts exist (MES, MGC, MCL, micro FX and yield) (`reasoning`) | One SPX contract ≈ $100 × index level, very large for a small fund |

## 4. Power for positive residual alpha

Computed by `power.py` → `POWER.json` (the method is in the file's docstring).
* The standard error is Lo's (2002) iid formula, the one the project already uses in `PREREG_CAPITAL.md`:
  SE = √((1 + S²/2)/T). It applies to the appraisal ratio AR, because the AR is the Sharpe ratio of the residual.
* The iid SE ignores two things that make the real SE larger: the estimation error of the betas, and serial
  correlation. The years below are therefore **lower bounds**.
* The program-level α is DESIGN_RULES.md rule 2: 0.10/N. N was 38 on 2026-11-02 and has grown since; it must be
  recounted from `DATA_USE.md` at registration.

**Years needed for a one-sided test.** Each cell gives years for 80% power, then 50% power (the gate of design rule 3).

| AR | 5% | 0.10/40 (z 2.81) | 0.10/60 |
|---:|---:|---:|---:|
| 0.3 | 71.8 / 31.4 | 154.6 / 91.5 | 165.6 / 100.0 |
| 0.4 | 41.7 / 18.3 | 89.9 / 53.2 | 96.3 / 58.2 |
| 0.6 | 20.3 / 8.9 | 43.6 / 25.8 | 46.8 / 28.2 |

**Power each candidate sample gives** (the AR is the true one, against the held sleeves):

| Sample | Years | Tradability / independence | 5%: AR 0.3 / 0.4 / 0.6 | 0.10/40: AR 0.3 / 0.4 / 0.6 |
|---|---:|---|---|---|
| Forward record, 1 year | 1 | executable / independent | 0.09 / 0.10 / 0.14 | 0.01 / 0.01 / 0.01 |
| Forward record, 3 years | 3 | executable / independent | 0.13 / 0.16 / 0.25 | 0.01 / 0.02 / 0.03 |
| Forward record, 5 years | 5 | executable / independent | 0.16 / 0.22 / 0.34 | 0.02 / 0.03 / 0.06 |
| ETFs not used by X1, 2007-04 .. 2025-12 | 18.7 | executable / partly or not independent | 0.35 / 0.51 / 0.77 | 0.06 / 0.13 / 0.34 |
| Yahoo continuous futures, 2000-09 .. 2026-11 | 26.2 | defective series / not independent | 0.44 / 0.63 / 0.88 | 0.10 / 0.20 / 0.51 |
| Cboe VIX futures contracts, 2004-03 .. 2026-11 | 22.7 | executable / partly overlapping | 0.40 / 0.58 / 0.84 | 0.08 / 0.17 / 0.43 |
| **Proxy, rates + FX, 1972-01 .. 2002-06** | 30.5 | proxy / independent (FX leg 1972–1989) | 0.49 / 0.69 / 0.92 | 0.12 / 0.25 / 0.60 |
| **Proxy, rates from 1962-01 (FX from 1972)** | 40.5 | proxy / independent | 0.59 / 0.79 / 0.97 | 0.17 / 0.36 / 0.76 |
| Cboe BXMD, CNDR, PPUT, BFLY, 1986–2026 | 40.4 | benchmark / partly overlapping | 0.59 / 0.79 / 0.97 | 0.17 / 0.36 / 0.76 |
| AQR TSMOM, 1985–2026 | 41.4 | benchmark / not independent | 0.60 / 0.80 / 0.97 | 0.18 / 0.37 / 0.77 |
| AQR Century, 1926–2026 | 99.6 | benchmark / partly overlapping | 0.90 / 0.99 / 1.00 | 0.55 / 0.85 / 1.00 |
| JST annual, 1870–2020 | 151 | benchmark / partly overlapping | 0.98 / 1.00 / 1.00 | 0.79 / 0.97 / 1.00 |

**Reading the table.** These are design inputs, not results.
* **No executable sample can power a test of an appraisal ratio below about 0.6 at the program level.** Only the
  century-long benchmarks can, and benchmarks set priors.
* A forward record gives under 35% power at the 5% level for an AR of 0.6 even after 5 years. As in the allocation
  pre-registration, it is a **posterior update, not a pass/fail test**.
* The best never-read sample in years and independence is the 1962/1972–2002 proxy. It can reach design rule 3's
  P ≥ 0.5 only if the plausible AR is about 0.55 or more (the 0.10/40 columns: P 0.60 at AR 0.6 over 30.5 years).
  * Rule 3 sets the plausible AR at δ = ½ × the literature value.
  * The literature values must be copied at registration from HOP's per-asset Sharpe exhibits (fixed income and
    currencies) and MOP Fig. 2 (per-contract Sharpe ratios). They were not extracted in this scoping run.
  * If δ is below about 0.55, rule 6 applies: the proxy read becomes a **precision estimate**, not an admission test.
* **Breadth reduces δ** (`reasoning`). Before 2003 the free data hold about one US rates factor across four
  maturities, a handful of international yields (if they pass a point-in-time contract) and eight currencies until
  1989. That is far fewer independent bets than MOP's 58 markets or HOP's 67.

## 5. Constrained allocation and exposure definitions for derivatives under the 1.9× cap

Today's 1.9× cap is a gross notional limit on a cash equity and ETF book under a margin account (`repo`: the
capital and allocation studies). Derivatives need an explicit research definition. Five candidates:

| Name | Definition | Behaviour |
|---|---|---|
| X_N, notional gross | Σ\|qᵢ·mᵢ·Fᵢ\| / NAV. ETFs at market value; a leveraged ETF at market value × its leverage | Simple. A volatility-balanced bond sleeve needs several × NAV in 2-year notes, so a notional cap makes it infeasible. S1's decomposition shows the cap binding and shrinking the fund (mean scale 0.707) |
| X_Δ, delta-adjusted gross | Σ\|Δᵢ·qᵢ·mᵢ·Sᵢ\| / NAV. Equals X_N for futures and ETFs | Needed for options. A deep OTM put counts little until the market falls |
| X_σ, volatility-equivalent gross | Σ\|Δ-notionalᵢ\|·σᵢ/σ_SPY / NAV, with σ from the same ex-ante EWMA as the signal | Puts every sleeve in "SPY units". A 2-year note at about 1.5–2% volatility counts roughly 0.1 per unit of notional (`reasoning`) |
| X_M, margin-to-equity | Σ initial marginᵢ / NAV (exchange margin for futures; Reg T or portfolio margin for options) | The CTA convention. Moves with exchange decisions, not with the fund's risk |
| X_S, stress loss | max over a fixed scenario grid of −ΔNAV/NAV, with options fully revalued | The only one that sees short-convexity risk. Proposed grid: equity −20% and +10% with VIX +30 points; 10-year yield ±100 bp; dollar ±10%; commodities ±25%; each asset's worst 5-day move in its registered history |

**Proposal (owner's decision).**
* **The 1.9× cap binds on X_σ for non-equity sleeves and on X_Δ for equity.** The equity side keeps today's meaning:
  core plus book plus any equity-index delta, counted at notional.
  * The constraint is X_Δ(equity) + Σ X_σ(non-equity) ≤ 1.9.
  * Non-equity positions count at their SPY-volatility equivalent. This keeps the cap a risk limit instead of a
    notional accident.
* **Companion hard limits**, registered and reported in every week:
  * X_M ≤ 0.25;
  * X_S ≤ a level the owner sets (for example 30% of NAV);
  * X_N reported but not binding.
* **Why not X_N alone.** It would forbid the very sleeve being tested: low-volatility bonds and FX need notional
  above NAV.
* **Why not X_S alone.** Its scenario grid is a choice that could be tuned. It should be a guard, not the cap.

**Allocation in the test.** These are allocation Amendment 2's terms, `repo`.
* Weights ≥ 0, the core at its policy weight, the 1.9× cap (measured as above).
* Criterion 3 is the maximum fund excess Sharpe with the candidate minus the same without it, under those constraints.

## 6. Mechanisms, ranked by expected appraisal ratio against the fund

The fund is the 200-day S&P core at 1.3×/0.7× plus the MASTER stock book (`repo`). The ranks are priors from
literature and from this project's spent reads (`reasoning` unless a source is named). None was computed from data.

| Rank | Mechanism | Why it might add residual alpha | Why it might not | Data that could test it unspent |
|---|---|---|---|---|
| 1 | Multi-asset time-series momentum, non-equity legs only | Low equity beta. MOP §4.3, "Performance over time and in extreme markets", and Fig. 4, "The time series momentum smile"; HOP's "smile" against US equity, 1880–2016 (`read`, headings and captions only) | Equity-index TSMOM duplicates the core, so equities must be excluded. Huang-Li-Wang-Zhou 2020 find per-asset TSMOM weak, and the strategy close to a historical-mean strategy (`search-summary` of the abstract). The 5-ETF version failed in this project (S1) | Proxy 1962/1972–2002: rates, FX |
| 2 | Cross-asset value | Negatively correlated with momentum (AMP 2013, `reasoning`); a different return source from the core | Needs valuation inputs (real yields, PPP), each with point-in-time issues; slow; long losing spells | OECD and FRED yields and CPI before 2003; AQR Century and VME as priors |
| 3 | Cross-asset carry | A documented premium in every asset class (Koijen-Moskowitz-Pedersen-Vrugt 2018, `reasoning`) | Carry crashes with equities, so its correlation with the core in the core's worst weeks is likely positive. FX carry is spent (S6) | Bond carry (term spread) before 2003; commodity carry only as an AQR benchmark |
| 4 | Macro-conditioned allocation | — | Timing rules have failed repeatedly here (S3, S4, S9). The states 2008–2025 are spent. Many free parameters | Low |
| 5 | Volatility risk premium (PUT, BXM, short VIX futures) | A large standalone premium in the literature (`reasoning`) | Equity beta of the order of 0.5 (`reasoning`), so little survives the core's beta. Short convexity in exactly the core's worst weeks | VX contracts 2004–2026; Cboe indices 1986–2026 (benchmark) |
| 6 | Defensive convexity (long puts, PPUT, VXTH, long VIX futures) | Pays in crashes | A negative standalone premium. With weights ≥ 0 and the core fixed at policy, it can help only if the core may lever up against it, which is not allowed. The 200-day rule already sheds exposure in down-trends | as for rank 5 |

## 7. Recommended design: one pre-registered test

**Name.** Non-equity time-series momentum on a never-read pre-2003 proxy sample, as a residual-alpha read against
the trend core.

* **Universe**, fixed before any return is built:
  * US Treasuries at 2, 5, 10 and 30 years. Build synthetic constant-maturity total returns from FRED daily
    end-of-month yields: price change from duration and convexity, plus yield accrual, minus the DTB3 cash rate. DGS2
    enters in 1976 and DGS30 in 1977.
  * The JPY, GBP, CHF, CAD, AUD, SEK, NOK and DKK spot rates against USD from H.10 daily end-of-month, plus the
    interest differential, **1972-01 .. 1989-12 only** (1990 onwards is S6's).
  * The CHF and JPY carry accrual before 1999/2002 is a typed defect. Either a named FRED short rate fills it before
    registration, or those two enter excluding carry and the defect is counted.
  * International 10-year yields enter only if an end-of-month (not monthly-average) series is found. Otherwise they
    are excluded; monthly averages fail the contract.
  * **No equity indices** (they duplicate the core). **No commodities or gold**: the only free long series are
    monthly averages (World Bank) or AQR portfolios (benchmark).
* **Sample.** 1962-01 .. 2002-06 for rates, with FX inside 1972–1989: about 40 years, never read as instruments.
  * A 3-year warm-up for volatility, after HOP.
  * Markets enter when their data exist.
  * Nothing after 2002-06 is touched: S1's development data start in 2003-07.
* **Signal**, from the literature with no free parameter. The Moskowitz-Ooi-Pedersen 2012 TSMOM (`read`: §2.1
  data, §2.4 eq. 1, §4.1 eq. 5):
  * position = sign(past 12-month excess return) × 40%/σ_{t−1};
  * σ² is 261 × the exponentially weighted squared daily excess return, with centre of mass 60 days, lagged one day;
  * monthly rebalancing, 1-month hold, equal weight across available markets;
  * the sleeve is scaled to 10% ex-ante volatility.
  * **Correction to the brief:** MOP's main signal is the full 12-month return (k = 12, h = 1), not "12-1"; the AQR
    factor file states the same. One specification, so the read adds one to N.
* **Cost model.**
  * Rates and FX at 1 bp a side of notional for the modern era, as Protocol 3 used for G10 FX, with HOP's multipliers
    (`read`): ×6 before 1993, ×2 for 1993–2002.
  * Roll trades counted quarterly, as if implemented in futures.
  * A sensitivity at 0.5× and 2× is reported, not decided on.
  * Collateral earns DTB3, so returns are excess returns.
* **The held sleeves.** The 200-day core at 1.3×/0.7× on the French daily market (spent, but used only as the
  regressor) and cash.
  * The MASTER book has no history before 2013. Its correlation with the candidate can only be measured forward.
    This limit is stated in the registration.
* **Admission.** All of the following must hold.
  * Allocation Amendment 2 (on `origin/research/allocation-20261124`, `repo`):
    1. AR > 0 with the one-sided 90% block-bootstrap lower bound above 0;
    2. residual alpha after costs > 0 on the same months;
    3. constrained marginal contribution > 0, with weights ≥ 0, the core at policy and the 1.9× cap on the
       measure of §5;
    4. correlation in the core's worst 10% of months reported, not decisive.
  * DESIGN_RULES.md:
    * the one-sided p ≤ 0.10/N (N recounted);
    * rule 3's power P ≥ 0.5 at δ = ½ of the literature AR, committed with the power table. **If P < 0.5, the read is
      registered as a rule-6 precision estimate instead**;
    * both cost hurdles in AR units.
* **What a pass earns.** A forward shadow record in executable form: futures (ZT/ZF/ZN/ZB and 6J/6B/6S/6C/6A/6E) or
  the matching ETFs (SHY/IEI/IEF/TLT and FXY/FXB/FXF/FXC/FXA/FXE). It is sized by the allocation pre-registration's
  posterior rule. A pass is a proposal; trading is a separate owner decision.
* **The owner must authorise, for research only:**
  1. Treasury and currency instruments, long and short, as a sleeve beside the S&P core;
  2. the derivative exposure definition of §5 for the 1.9× cap;
  3. that a proxy (yield- and spot-built) sample may serve as the test, with tradable instruments only in the
     forward record. This is a reading of the owner's rule "a benchmark can give a prior, not the test". The proxy is
     built from prices of tradable instruments; it is not a benchmark index. The owner should rule on it explicitly.

## 8. The three universes, ranked by expected evidence quality per unit of effort

1. **Futures, via pre-2003 yield and spot proxies (with AQR files as priors).**
   * The longest never-read, independent history: about 40 years of rates and 18 of FX.
   * Moderate effort: build synthetic returns, plus end-of-month and carry contracts.
   * The weaknesses are breadth (no free commodity or international-bond history at end-of-month) and that the proxy
     is not itself executable.
2. **Options and volatility.**
   * VIX futures contract files, 2004–2026, are free, executable and contract-level: low to moderate effort.
   * The Cboe benchmark indices from 1986 can set priors.
   * But the exposure is S&P 500 volatility, the core's market, so the evidence is partly overlapping. The two
     mechanisms it can test (volatility premium, convexity) rank lowest on expected residual alpha (§6).
3. **ETF-only.**
   * Lowest effort, lowest evidence.
   * The executable history 2002–2025 is spent (S1) or overlaps spent markets (S6, S7).
   * Only a forward record is independent, and it has under 35% power after 5 years.

## 9. Search and access log

```
Query: git ls-tree / git grep keywords (see §1) on origin/main and all origin/research/*   Date: 2026-11-25
Opened: research/tree/L4_explore/REPORT.md, PREREG.md (Layer 4, Layer 6), LAYER3_LOG.md §34, L6_lit, L6_complexity,
        L6_regime; PROTOCOL_fx.md, PROTOCOL_fx_confirm.md, fx/README.md; PROTOCOL_daily.md; baseline-ladder PROTOCOL.md;
        research/exposure/PREREG.md; research/sharpe/PREREG.md, PREREG_CAPITAL.md; research/regime/PREREG.md, INT_RESULT.md;
        riskfield PREREG Amendment 14; eventrisk PREREG; DATA_USE.md; DESIGN_RULES.md; PREREG_ALLOCATION.md (incl. Amendment 2)
Blocked: none
Stopped: no
Conclusion: the spent samples are S1-S13 in §1.
```

```
Query: coverage downloads (curl, generic User-Agent)   Date: 2026-11-25
Opened: Cboe index CSVs (12 symbols + VIX9D); Cboe VX listing JSON and two contract files; Yahoo chart metadata
        (about 85 tickers); FRED fredgraph.csv (about 60 series); AQR TSMOM, Century, VME, Commodities-for-the-Long-Run
        xlsx; World Bank Pink Sheet monthly xlsx (an old vintage); JST R6; MOP 2012 PDF (§2.1, §2.4, §4.1, read);
        HOP 2017 PDF (method pages and Appendix B, read)
Blocked: stooq.com (JavaScript challenge); data.nasdaq.com CHRIS (403); prices.lbma.org.uk (403);
         cdn.cboe.com/resources/spx/{putdailyprice,bxmarchive,bxmcurrent}.csv (403); Cboe SPVXSTR, VXST (403);
         FRED GOLDAMGBD228NLBM, GOLDPMGBD228NLBM, DEXGEUS, DEXFRUS, DEXITUS, DEXNEUS, DEXBEUS, LTGOV (404)
Not inspected: Shiller ie_data.xls (no xls reader); the AQR Definitions and Data Sources tabs (images)
Stopped: no
```

```
Query: "AQR data set 'A Century of Evidence on Trend-Following Investing' download monthly returns"; AQR Terms of Use;
       About the AQR Data Library; "Huang Li Wang Zhou 'Time series momentum: Is it there?' ... abstract";
       "Nasdaq Data Link CHRIS ... discontinued"; "Cboe S&P 500 PutWrite Index PUT methodology ..."   Date: 2026-11-25
Opened: AQR Terms of Use and About pages (fetch-summary)
Search summaries only: HOP dataset (none found); Huang et al. abstract; CHRIS status (inconclusive); PUT methodology
Stopped: no
```

## 10. Not claimed

* No claim about any strategy's return, Sharpe ratio, appraisal ratio or correlation; none was computed.
* No claim that the proxy sample is executable. It approximates constant-maturity bond and FX-forward returns. Its
  tracking error against ETFs and futures can only be measured on 2003 onwards, which is spent. That measurement is
  a data check, not a test.
* No claim that free long futures data do not exist. Only that none loaded among the sources tried, with Stooq and
  Nasdaq blocked and the paid vendors not tried.
* Expense ratios, margins, tick costs, the VIX futures settlement and the account's product access are `reasoning`,
  to be verified at registration.
* The mechanism ranks in §6 are priors, not evidence.
