# Historical futures data: costed procurement assessment (2026-11-25)

**Status.** A desk assessment from published product and pricing pages only. The owner's instruction was
"Obtain quotations; no purchase yet". No vendor was contacted. No form was filled, no account or trial was opened,
no quote was requested and nothing was bought. Where a price is not published, it says **price on request**.
No return series was downloaded and no return statistic was computed. The power figures in §4 are design
arithmetic on assumed appraisal ratios.

Context: `research/xasset/SCOPE.md` on `origin/research/xasset-scope-20261125` (the scoping memo; spent samples
S1–S13; the recommended non-equity trend read on a 1962–2002 yield-and-FX proxy).

Access labels on every claim:
* **read-directly**: the vendor's own page, or the paper, was fetched and the passage read;
* **search-summary**: only a search engine's summary was seen;
* **blocked**: the page did not load (§7 lists each one);
* **reasoning**: my inference, which no source states.

Files:
* `PROCURE.json`: scorecard, costs, independence grades, decision and access log;
* `PROCURE_POWER.json`: every power and breadth figure;
* `procure_power.py`: the power arithmetic (reads no data);
* `procure_build.py`: assembles `PROCURE.json`;
* `procure_coverage.py` → `procure_coverage.json`: market lists and first-trade years parsed from the vendors'
  published coverage tables (metadata only).

Two checks, each of which could have failed:
1. `procure_power.py` reproduces the scoping memo's `power.py`: 71.8 / 31.4 years at AR 0.3, 5%. It passed.
2. The correlation model, calibrated on Moskowitz-Ooi-Pedersen (MOP 2012) Table 4, predicts a 58-market portfolio
   Sharpe ratio of 1.41 at a per-market Sharpe ratio of 0.4. MOP report "greater than one". The two are
   consistent, but this check is weak, because it can only fail in one direction.

---

## 1. Answer to the owner's question

**Does buying data add enough evidence to replace or supplement the 1962–2002 yield-and-FX proxy read?**

**Supplement, do not replace, and only on a condition.** The condition is how correlated trend returns are across
markets (§4).

**The design that gains.** One combined pre-registered read, 1962-01 .. 2002-06:
* the proxy's legs: US Treasuries from FRED, and H.10 currencies for 1972–1989;
* plus vendor futures on commodities and non-US rates from their first trade (grains from 1968–69, metals and softs
  from 1971–75, gilts and short sterling from 1982, the Bund from 1989–90).

Programme-level power (one-sided α = 0.10/40), at single-market appraisal ratio AR₁ = 0.2:

| Correlation of trend returns | Proxy alone | Combined, Portara list | Combined, Pinnacle list |
|---|---:|---:|---:|
| MOP Table 4 (implied average ≈ 0.07) | 0.29 | **0.78** | **0.76** |
| uniform ρ = 0.1 | 0.33 | 0.61 | 0.58 |
| uniform ρ = 0.2 | 0.23 | 0.35 | 0.34 |
| uniform ρ = 0.3 | 0.17 | 0.23 | 0.23 |

**What this means for the read** (design rule 3 gate: P ≥ 0.5 at δ = ½ × the literature AR, about 0.2; §4.3):
* At MOP's correlations the combined read passes the gate, so it can be an **admission test**. The proxy alone
  cannot pass at any correlation; it stays a rule-6 **precision estimate**.
* At ρ ≥ 0.2 neither design passes. The purchase then buys a modestly tighter precision estimate.

**Replacing the proxy with vendor data alone is dominated.**
* Vendor data alone, 1975–2002 or 1980–2002, gives up the 1962–1974 years.
* At ρ ≥ 0.2 a 50-market vendor read over 1980–2002 has *less* power than the 9-market proxy over 40.5 years
  (§4.1): 0.20 against 0.30 at AR₁ 0.2 and ρ 0.2.

**Cost.** Nearly all of the gain comes from about 25–30 commodities over 1969–2002. Their trend correlation is low
(0.07 in MOP), so breadth beyond about 30 adds little. Two routes:
* The cheapest published route, **Pinnacle Deep History plus CLC at $248 one-off**, buys almost the same power as
  the best-licensed one, **Portara at $330 a market** (≈ $13,200 for 40 markets at list, $8,800 at its current
  special).
* What separates them is the licence and data quality, not breadth. Pinnacle publishes no licence. Portara's is
  perpetual and allows derived results to be published.

**Recommendation.**
* Ask the two vendors for the quotes in §6.
* Before buying, the owner may fix ρ as a registered design input. One option is to measure the cross-market
  correlation of trend returns on already-spent 2003–2025 data, which is not a test of alpha. Whether that use of
  spent data is acceptable is the owner's call; it was not done here.
* If the registered ρ is ≥ 0.2, do not buy for this read.

## 2. Vendor scorecard

The owner's columns. Grades: yes / partial / no / unknown. Labels: RD = read-directly, SS = search-summary,
B = blocked, R = reasoning. The ranking is for this use: a frozen, never-read pre-2003 history whose raw data can be
kept and whose derived results can be committed to a private repository.

| # | Vendor | Individual contracts (Ess.) | Transparent roll (Ess.) | ≥ 40–50 markets (High) | History into 1980s (High) | Vol / OI / settle (High) | Contract specs and changes (Ess.) | Python (High) | Cost: one-off / recurring (Ess.) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Portara** (CQG Data Factory) | yes: "individual or continuous daily data" (RD) | yes: zero, back, forward or ratio, with a roll audit log (RD) | yes: 446 symbols, about 276 markets (RD) | yes: 1968 grains; 52 non-equity markets by 1989 (RD) | partial: settlement yes; volume start dates vary; OI not confirmed (RD) | partial: tick-size history handled; no spec table read (RD) | yes: CSV (RD) | $330/market full history ($220 special); individual-contract daily, subscription and discounts on request (RD) |
| 2 | **Pinnacle** (CLC, Deep History) | yes: about 8,000 contracts, 70 commodities, "some back to 1969" (RD) | yes: roll day published per market (RD) | yes: 98 CLC, 65 in the date table (RD) | yes: 1969–78 for most; Bund and gilt 1989 (RD) | yes: OHLC, settle, OI, total volume (RD) | no: none found (RD) | yes: ASCII (RD) | Deep $149, CLC $99, Light $49; updates $216/yr (RD) |
| 3 | **Norgate** | yes (RD) | yes: arithmetic back-adjust, roll before last trade or first notice (RD) | yes: 94 markets, about 70 non-equity (RD) | partial: "around 1980"; 27 non-equity in 1980, 43 by 1989; Eurex only from 1999 (RD) | yes: close = settlement; volume, OI (RD) | partial: contract-details sheet; "lowest ever" tick field (RD) | partial: Python package, Windows-only updater (.NET 4.8) (RD) | USD 270 / 12 months, 148.50 / 6 months; recurring to keep the data (RD) |
| 4 | **CSI** (Unfair Advantage) | yes: active markets (RD) | yes: user-defined rules, many methods (RD) | yes: "nearly 1,000+" (RD) | partial: about 40 years at published prices, back to ~1986 (RD) | yes (RD) | partial: factsheets exist; listing pages 403 (RD/B) | partial: ASCII/Excel export from Windows UA (RD) | Gold World $200 one-time + $899/yr + ≤ $300 extra history; Silver $120 + $689/yr or $79.50/mo; full history on request (RD) |
| 5 | **CME DataMine** | yes (SS) | n/a: build own (R) | partial: CME Group only (R) | yes: end of day from 1982-01-01 (SS) | yes (SS) | partial (R) | partial: CSV (SS) | price on request (SS) |
| 6 | **LSEG Datastream** | yes (SS) | partial: 34,000 continuous series, six methods (SS) | yes (SS) | yes: from 1973 (SS) | yes (SS) | partial (SS) | partial: Excel add-in or Workspace (SS) | price on request; institutional (SS) |
| 7 | **Bloomberg** (upper bound) | yes (R) | partial (R) | yes (R) | yes (R) | yes (R) | yes (R) | yes (R) | ≈ $31,980/yr per terminal, third-party figure (SS) |
| 8 | **Barchart / cmdty** | unknown (B) | unknown (B) | unknown (B) | no for retail: daily from 2000-01-01 (SS) | unknown (B) | unknown (B) | unknown (B) | enterprise: price on request (SS) |
| 9 | **Databento** | yes (RD) | partial (R) | yes (RD) | **no**: CME from June 2010, ICE from 2018-07 (RD) | yes: settlement, OI, cleared volume (RD) | yes: definition schema (RD) | yes (RD) | $/GB usage, $125 credit; rates not rendered (RD/SS) |
| – | Nasdaq Data Link (paid futures) | the SCF and CHRIS pages return 404 (B): no paid futures product located | | | | | | | |
| – | Tick Data LLC | intraday specialist, 280+ futures (RD); price on request; not needed for monthly trend | | | | | | | |
| – | WRDS | institutional only (R); carries Datastream for subscribers; OptionMetrics options data is not relevant to non-equity trend | | | | | | | |

**Licence terms for research use and redistribution.** The question: can the data be kept (rule 4: freeze at first
use), and can derived results be committed to a private repository?

| Vendor | Terms | Fit |
|---|---|---|
| Portara | One-off licence "Perpetual"; up to five people, own computers, servers or cloud; "You may publish results, charts, signals and performance figures derived from the Data"; no passing the data, or anything from which it could be substantially reconstructed, outside the organisation (RD) | **Best.** Keep the raw files in `.cache` with a sha256; commit derived results |
| Pinnacle | No licence published; only a warranty disclaimer (RD) | **Unknown.** Get written terms first |
| Norgate | Personal use by individuals only, "no alternative business/commercial licensing". Derived results (trading results, model parameters, statistics) may be kept. All exported data and backups must be deleted at expiry. No shared repository (RD) | **Poor.** Freezing inputs needs a permanent subscription. Whether a single-owner paper fund counts as "personal use" is the owner's reading |
| CSI | "Personal and private use"; may not "create derivative works from" the data; "creating derivative(s), publication" counts as commercial; exports are encoded with the account's identity; the licence is revoked if updates lapse two months (RD) | **Poor** |
| Databento | Personal use with Databento as vendor of record; "External distribution" only on the Unlimited plan (RD) | n/a: history too short |
| Datastream, Bloomberg | Institutional or academic, non-commercial (SS); bulk extraction restricted (R) | Poor or not available |

**Survivorship (delisted contracts and markets).**
* **Portara** lists dead markets with end dates (RD): Eurodollar to 2023-06-16, pork bellies to 2011-07-15, the
  10-year swap to 2013-09-16.
* **Pinnacle** keeps pork bellies and splices the Deutsche mark into its euro series (RD).
* **Norgate** keeps expired contracts of live markets, but lists no delisted market: no Eurodollar, Deutsche mark
  or pork bellies (RD, absence). That is market-level survivorship.
* **CSI**: "Inactive futures not included" (RD).

**Vendor risk at Pinnacle** (RD):
* the HTTPS certificate failed verification;
* the order page still warns Netscape users;
* the data's maintenance to date was not verified;
* the page gives about 8,000 Deep contracts in one place and about 10,000 in another.

## 3. Costs (published prices only, USD, before tax and unpublished discounts)

"Markets" are the supplement list of §1: commodities and non-US rates.

| Route | One-off | Recurring | Five-year total | Note |
|---|---:|---:|---:|---|
| Pinnacle Deep + CLC | 248 | 0 (updates optional, $216/yr) | 248 | licence unknown (RD) |
| Norgate, renewed to keep the frozen copy | 0 | 270/yr | 1,350 | plus a Windows licence for a VM (not costed) (RD) |
| CSI Gold World Futures + 10 extra years | 500 | 899/yr | 4,995 | back to ~1986 only; earlier history on request (RD) |
| Portara one-off, 40 markets | 13,200 list / 8,800 special | 0 | same | individual-contract daily on request (RD) |
| Portara one-off, 75 markets | 24,750 list / 16,500 special | 0 | same | (RD) |
| CME DataMine, LSEG Datastream, Barchart enterprise | price on request | price on request | – | (SS) |
| Bloomberg | – | ≈ 31,980/yr | ≈ 160,000 | third-party figure (SS) |

## 4. Breadth and power

### 4.1 Model and parameters

**Power.** As in the scoping memo, Lo (2002): T = (z_α + z_β)² (1 + S²/2) / S², with SE = √((1 + S²/2)/T). It ignores
serial correlation and beta-estimation error, so the years are lower bounds and the powers upper bounds.

**Breadth.** An equal-risk trend portfolio of N markets, each with appraisal ratio AR₁ and pairwise trend-return
correlation ρ:

> AR_N = AR₁ · √(N / (1 + (N−1)ρ)); N_eff = N / (1 + (N−1)ρ); AR_N → AR₁/√ρ as N → ∞.

**Where the parameter ranges come from.**

*Single-market appraisal ratio, AR₁ from 0.1 to 0.3:*
* Hurst-Ooi-Pedersen (HOP 2017), 67 markets, 1880–2016: "an average Sharpe ratio of approximately 0.4" per market,
  gross of costs (RD).
* MOP 2012, 58 markets, 1985–2009: "All 58 futures contracts exhibit positive time series momentum returns and 52
  are statistically different from zero at the 5% significance level" (RD). Over 25 years that implies a gross
  per-market Sharpe ratio of at least about 1.96/√25 ≈ 0.39 for 52 of the 58 (R).
* Design rule 3 halves the literature value: δ ≈ 0.2 (repo, via SCOPE.md).
* Costs (HOP's ×6 multiplier before 1993, RD), residualisation against the trend core, and post-publication decay
  all lower it further (R).
* The range 0.1–0.3 therefore brackets δ.

*Correlation of trend returns, ρ from 0.1 to 0.3:*
* MOP Table 4 (RD), average pairwise correlation of 12-month trend returns within each asset class: commodities
  0.07, currencies 0.10, equities 0.37, fixed income 0.38.
* Correlations between the asset-class trend portfolios range from 0.05 to 0.21.
* Backed out to instrument level with MOP's counts, the cross-class correlations are 0.014–0.018 among commodities,
  fixed income and currencies. The implied uniform ρ for MOP's 58 markets is **0.065**.
* HOP (RD) find that correlations vary over time and rise in "risk-on/risk-off" periods, and that performance is
  worse when correlations are high.
* Hence ρ = 0.1 matches the literature average. ρ = 0.2–0.3 stands for a stressed or concentrated universe (R).

### 4.2 N = 9 (the proxy) against N = 40–60 (a vendor set), uniform ρ

Columns:
* **mult** = AR_N/AR₁;
* **cap** = 1/√ρ;
* **AR_N** at AR₁ = 0.1 / 0.2 / 0.3;
* **Years, 0.10/40** = years for 80% power at α = 0.10/40, at AR₁ = 0.1 / 0.2 / 0.3;
* **Years, 5%** = years for 80% power at the 5% level, at AR₁ = 0.2.

| ρ | N | N_eff | mult (cap) | AR_N | Years, 0.10/40 | Years, 5% |
|---:|---:|---:|---|---|---|---:|
| 0.1 | 9 | 5.0 | 2.24 (3.16) | 0.22 / 0.45 / 0.67 | 273 / 73 / 36 | 34.0 |
| 0.1 | 40 | 8.2 | 2.86 | 0.29 / 0.57 / 0.86 | 170 / 47 / 25 | 22.0 |
| 0.1 | 50 | 8.5 | 2.91 | 0.29 / 0.58 / 0.87 | 164 / 46 / 24 | 21.3 |
| 0.1 | 60 | 8.7 | 2.95 | 0.30 / 0.59 / 0.89 | 160 / 45 / 24 | 20.9 |
| 0.2 | 9 | 3.5 | 1.86 (2.24) | 0.19 / 0.37 / 0.56 | 391 / 103 / 49 | 47.7 |
| 0.2 | 40 | 4.6 | 2.13 | 0.21 / 0.43 / 0.64 | 300 / 80 / 39 | 37.1 |
| 0.2 | 50 | 4.6 | 2.15 | 0.22 / 0.43 / 0.65 | 294 / 79 / 39 | 36.5 |
| 0.2 | 60 | 4.7 | 2.17 | 0.22 / 0.43 / 0.65 | 291 / 78 / 38 | 36.1 |
| 0.3 | 9 | 2.7 | 1.63 (1.83) | 0.16 / 0.33 / 0.49 | 510 / 132 / 63 | 61.5 |
| 0.3 | 40 | 3.2 | 1.78 | 0.18 / 0.36 / 0.53 | 429 / 112 / 54 | 52.2 |
| 0.3 | 50 | 3.2 | 1.79 | 0.18 / 0.36 / 0.54 | 425 / 111 / 53 | 51.6 |
| 0.3 | 60 | 3.2 | 1.79 | 0.18 / 0.36 / 0.54 | 422 / 110 / 53 | 51.3 |

**Going from 9 to 50 markets** raises AR_N by 30%, 16% and 10% at ρ = 0.1, 0.2 and 0.3. The years needed fall by
roughly 40%, 25% and 17%.

**Fifty markets over 40 years are not 2,000 independent years.**
* A portfolio-level test has T calendar years of observations. Breadth only raises the signal per year, and never
  above the cap 1/√ρ (3.2×, 2.2× and 1.8×).
* The independent market-years are N_eff·T: **339, 185 and 127** for 50 × 40 at ρ = 0.1, 0.2 and 0.3, against a
  naive 2,000. The proxy's 9 × 40.5 gives 203, 140 and 107.
* Even these overstate the information: correlations rise in crises (HOP), and the iid SE ignores serial
  dependence.

**At equal windows** (uniform ρ, power at 0.10/40, AR₁ 0.2):

| Sample | ρ = 0.1 | ρ = 0.2 | ρ = 0.3 |
|---|---:|---:|---:|
| Proxy, N = 9, 40.5 years | 0.46 | 0.30 | 0.22 |
| Vendor, N = 50, 1980–2002, 22.5 years | 0.40 | 0.20 | 0.12 |
| Vendor, N = 50, 1975–2002, 27.5 years | 0.51 | 0.26 | 0.16 |
| Vendor, N = 60, 1980–2025, 45.9 years (mostly spent: §5) | 0.81 | 0.50 | 0.33 |

The only sample with clearly more power is the long one, and it is the one the project has already spent.

### 4.3 Time-varying breadth from the vendors' own coverage tables

**How N(t) is counted.**
* By class, from the published first-trade years (`procure_coverage.json`). Session variants and mini or micro
  copies are merged.
* Equity-index futures are excluded: they duplicate the core.
* Currencies stop at 1989, to stay off the cross-sectional currency reads (S6).
* The proxy's N(t) follows SCOPE.md §7:
  * 5- and 10-year Treasuries from 1962, the 2-year from 1976, the 30-year from 1977;
  * eight currencies 1972–1989.
  * Its time-average is 6.8 markets, not 9.

**Correlations.** Within-class and cross-class values from MOP Table 4. Rows marked "uniform" use a single ρ.

**Results.** Each cell gives the effective AR at AR₁ = 0.2, then power at 0.10/40 for AR₁ = 0.1 / 0.2 / 0.3:

| Sample (end 2002-06) | Years | Mean N | MOP correlations | Uniform ρ 0.1 | Uniform ρ 0.2 | Uniform ρ 0.3 |
|---|---:|---:|---|---|---|---|
| Proxy (registered design) | 40.5 | 6.8 | 0.365; .05 / .29 / .67 | 0.39; .06 / .33 / .72 | 0.33; .04 / .23 / .57 | 0.30; .03 / .17 / .47 |
| Replace: Portara, all non-equity, 1975– | 27.5 | 49.0 | 0.67; .13 / .64 / .93 | 0.57; .09 / .49 / .85 | 0.43; .04 / .25 / .60 | 0.35; .03 / .16 / .42 |
| Replace: Norgate, all non-equity, 1980– | 22.5 | 39.4 | 0.69; .11 / .55 / .87 | 0.57; .07 / .38 / .75 | 0.43; .04 / .19 / .48 | 0.35; .02 / .12 / .33 |
| Vendor supplement alone (Portara commodities + non-US rates), 1970– | 32.5 | 37.7 | 0.63; .15 / .69 / .95 | 0.55; .10 / .55 / .90 | 0.42; .05 / .30 / .68 | 0.35; .04 / .19 / .50 |
| **Combined: proxy + Portara supplement**, 1962– | 40.5 | 37.4 | 0.61; .18 / **.78** / .98 | 0.52; .12 / .61 / .94 | 0.40; .06 / .35 / .75 | 0.34; .04 / .23 / .59 |
| **Combined: proxy + Pinnacle supplement** | 40.5 | 26.3 | 0.60; .175 / **.76** / .98 | 0.50; .11 / .58 / .92 | 0.39; .06 / .34 / .74 | 0.33; .04 / .23 / .57 |
| Combined: proxy + Norgate supplement | 40.5 | 25.7 | 0.56; .15 / .70 / .96 | 0.48; .10 / .53 / .90 | 0.38; .05 / .31 / .70 | 0.33; .04 / .21 / .55 |

**Sensitivity.** Raising the correlation within the US curve to 0.7 (R) cuts the proxy's power at AR₁ 0.2 from 0.29
to 0.23. The combined designs barely move. At the 5% level the combined Portara read has power 0.97 against the
proxy's 0.73 (AR₁ 0.2, MOP correlations). The full grid is in `PROCURE_POWER.json`.

**What the table says.**
* At AR₁ = 0.1 no design reaches even 0.2 power at the programme level.
* At AR₁ = 0.2 and MOP-level correlations, the combined read is the only one that clears 0.5 with margin.
* The commodity block does the work: within-class ρ is 0.07, so about 28 commodities (Pinnacle) buy almost
  everything 54 (Portara) do.

## 5. Independence of vendor history, by segment (against S1–S13 of SCOPE.md §1)

| Segment | Grade | Why |
|---|---|---|
| Commodities other than gold, 1968–2002 | **independent** | never read before 2003; DBC (S1) starts in 2006; WTI was only a check |
| Gold, 1974–2002 | **independent** | the gold reads are S7 (2006+), S8 (2012+) and GLD in S1 (2004+) |
| US Treasury futures, 1977–2002 | independent of spent reads; **same markets and dates as the proxy** | if the proxy is read first, they become spent. In one combined read they are one leg, never two |
| Non-US bond and short-rate futures, 1980–2002 | **independent** | never read |
| Currency futures, 1975–1989 | independent; same exposure as the proxy's H.10 leg | as for US rates |
| Currency futures, 1990–2003 | partly overlapping | same currencies and dates as the cross-sectional FX confirmation (S6, 1990-01 .. 2003-12); time-series signals never read |
| Commodities and non-US rates, 2003–2019 | partly overlapping | S1 development (DBC, GLD, IEF, TLT, UUP; open and examined) and S7 gold development 2006–2018 |
| US rates, gold, broad commodities and the dollar, 2003–2019 | not independent | S1's instruments in S1's dates |
| Currencies, 2004–2026 | not independent | S6 development and holdout; UUP in S1 |
| Everything, 2020–2025 | not independent | S1 test read once; the fund window S13 |
| Everything, 2026 | not independent | sealed fund window |
| Equity-index futures, all years | not independent | S2–S4: the US market 1926–2026 and three regions 1990–2025, including equity time-series momentum (S3) |
| VIX futures, 2004–2026 | partly overlapping | VIX level used as a state (S9); the contracts are free from Cboe anyway |

**What a purchase actually adds:**
* commodities and non-US rates before 2003;
* executable, roll-correct futures returns for US rates and currencies from 1975–77, which can replace the yield
  proxy inside the same read.

Everything from 2003 onwards is spent or partly spent, whoever sells it.

## 6. Quotations for the owner to request (not sent)

Generic text; no names or account details. Each request asks for a quotation only.

1. **Portara.** One-off daily history, for a list of about 40 commodity and non-US interest-rate futures to be fixed
   before purchase:
   * individual contracts and back-adjusted continuous series, with settlement, volume and open interest;
   * full history from inception;
   * confirm that the published $330 per commodity applies to daily data, and the portfolio discount;
   * confirm that a single-owner paper-trading research fund falls under the one-off licence.
2. **Pinnacle Data.**
   * Written licence terms for Deep History and CLC: retention after purchase, and committing derived statistics to a
     private repository.
   * Confirmation that the data are maintained and current.
   * The count of Deep History contracts (the site says both 8,000 and 10,000).
3. **CSI** (optional). The price of full World Futures history before 1986, and whether inactive markets can be
   licensed.
4. **CME DataMine** (optional, as an audit source for US markets). End-of-day settlement, volume and open interest
   for CBOT, CME, NYMEX and COMEX from 1982 to 2002.

**Before any purchase**, the pre-registration should fix:
* the market list;
* the splice rule (proxy before the first futures date, futures after);
* the content contract (CLAUDE.md rules 1–3): row counts against the expected contract calendar, and settlement
  inside the high–low range;
* reconciliation of two vendors on overlapping markets, which is why Pinnacle is worth having even next to Portara;
* freezing at first use, with sha256 values recorded and the raw files kept out of the repository.

## 7. Access log

| What | Label | Status |
|---|---|---|
| Norgate futurespackage, data-content-tables, faq, system-requirements | read-directly | 200 |
| Norgate licensing-agreement.php, python-package.php, data-faq.php (guessed paths) | blocked | 404 |
| pypi.org/project/norgatedata | blocked | JavaScript challenge |
| CSI OrderUA (prices sit in the page's script), page 14, licence page 824 | read-directly | 200 |
| CSI factsheets.php (CME, CBT) | blocked | 403 |
| pinnacledata.com over HTTPS | blocked | certificate failed verification |
| pinnacledatacorp.yolasite.com | blocked | 403 |
| pinnacledata.com over HTTP: index, clc, extended-clc, products, orderDB, disclaimer | read-directly | 200 |
| portaracqg.com: home, pricing, license, historical-daily-futures-data, continuous-futures-data | read-directly | 200 |
| databento.com/pricing | read-directly (script bundle text); client-rendered prices not obtained | 200 |
| Databento docs: glbx-mdp3, ifus-impact, xeur-eobi | read-directly | 200 |
| databento.com/licensing, /terms (guessed paths) | blocked | 404 |
| barchart.com: ondemand, web-services historical, my/price-history | blocked | HTTP 202, empty (bot challenge) |
| cmegroup.com DataMine pages | blocked | 403 / timeout |
| data.nasdaq.com/databases/SCF; CHRIS page | blocked | 404 |
| WRDS Datastream vendor page (guessed path) | blocked | 404 |
| tickdata.com historical futures | read-directly | 200 |
| firstratedata.com futures page | not used | served an unrelated stock listing |
| MOP 2012 PDF (Stern), HOP 2017 PDF (Yale) | read-directly | 200 |
| Searches: Norgate pricing; CSI price list; Pinnacle CLC price; Databento GLBX history and plan price; Barchart history and download limits; Nasdaq Data Link SCF/OWF; CME DataMine price; LSEG Datastream futures; Bloomberg terminal cost | search-summary | used only where labelled |

Page sha256 prefixes are in `PROCURE.json` (`sources`). The pages themselves are not committed; they are vendor
content.

## 8. Not claimed

* **No claim about any strategy's return, Sharpe ratio or appraisal ratio.** Every AR in §4 is assumed.
* **No claim that a vendor's data are clean.** Quality is untested until a purchase and a content contract.
* **No price beyond what was published.** Where none was published, it says "on request". Portara's $330 is printed
  next to 1-minute wording; whether it applies to daily data is to be confirmed in the quote.
* **Coverage counts are approximate.** They are parsed from vendor tables. Session variants and mini contracts were
  merged by rule, and some duplicates may remain (for example two gilt entries at Portara, two yen spellings at
  Pinnacle). Portara's "over 10,000" instruments beyond the published table were not counted.
* **The ICE start date at Databento** (2018-07-02) is a constant in the site's script, inferred to be ICE's start.
* **Bloomberg's figure is a third-party report.** Its coverage grades are reasoning.
* **Whether the paper account can trade futures** was not checked, as in SCOPE.md. A forward record of a commodity
  sleeve needs that.
* **Correlations are the literature's, gross, 1985–2009.** The project's own values are unknown until a design input
  is registered.
