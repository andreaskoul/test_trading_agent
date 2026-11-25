"""Assemble PROCURE.json: the vendor scorecard (published pages only), costs, independence grades, the access log and
the headline power figures copied programmatically from PROCURE_POWER.json (never retyped).

    python -I research/xasset/procure_power.py && python -I research/xasset/procure_build.py

Access labels: read-directly (the vendor's own page or file was fetched and the passage read), search-summary (only
a search engine's summary was seen), blocked (the page did not load), reasoning (inference; no source states it).
Grades: yes / partial / no / unknown. "price on request" means no price is published; nothing is guessed.
No vendor was contacted, no form was filled, no account was created, nothing was bought.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
COLUMNS = ["individual_contracts (Essential)", "roll_methodology (Essential)", "markets_40_50 (High)",
           "history_1980s (High)", "volume_oi_settlement (High)", "contract_specs_and_changes (Essential)",
           "python_access (High)", "cost_one_off_and_recurring (Essential)"]


def g(grade, note, access):
    return {"grade": grade, "note": note, "access": access}


VENDORS = [
    {"vendor": "Portara (CQG Data Factory reseller)", "rank": 1,
     "pages": ["https://portaracqg.com/pricing/", "https://portaracqg.com/license/",
               "https://portaracqg.com/historical-daily-futures-data/", "https://portaracqg.com/continuous-futures-data/"],
     "scores": {
         COLUMNS[0]: g("yes", "'Purchase individual or continuous daily data'; actual contracts are called 'Tenors' and carry a "
                              "'higher INITIAL licensing cost' on the subscription route", "read-directly"),
         COLUMNS[1]: g("yes", "zero, back, forward or ratio adjustment; per-market roll rules with a published roll audit log "
                              "(e.g. coffee 27 days before expiry)", "read-directly"),
         COLUMNS[2]: g("yes", "446 futures symbols in the daily table, about 276 distinct markets after merging session "
                              "variants (procure_coverage.json); 'over 10,000' instruments on request", "read-directly"),
         COLUMNS[3]: g("yes", "grains 1968, softs and metals 1971-74, currencies 1975-77, T-bond 1977, 10-year 1982, gilts "
                              "and short sterling 1982; 52 non-equity markets live by 1989", "read-directly"),
         COLUMNS[4]: g("partial", "settlement is one of five daily price points; a 'Volume Start Dates' table exists (not "
                                  "opened); open interest not confirmed on the pages read", "read-directly"),
         COLUMNS[5]: g("partial", "states that tick sizes change through history and that its continuous data are kept "
                                  "homogeneous; no contract-specification history table was read", "read-directly"),
         COLUMNS[6]: g("yes", "one-off delivery as CSV/ASCII by download link", "read-directly"),
         COLUMNS[7]: g("partial", "one-off: $330 per commodity for its full history ('on special: $220'); daily sold as the last "
                                  "30 years or the full history; pre-1960 index histories $795. The $330 line sits under "
                                  "1-minute wording: its application to daily data is to be confirmed in the quote. "
                                  "Subscription: price on request; individual-contract ('Tenor') daily: price on request; "
                                  "portfolio discounts: price on request", "read-directly")},
     "licence": g("best fit", "one-off licence is perpetual; use by up to five people in the organisation on own computers, "
                              "servers or cloud; research, backtesting and trading allowed; 'You may publish results, charts, "
                              "signals and performance figures derived from the Data'; may not pass the data, or anything "
                              "from which it could be substantially reconstructed, outside the organisation", "read-directly"),
     "survivorship": g("yes", "delisted markets are listed with end dates: Eurodollar to 2023-06-16, pork bellies to "
                              "2011-07-15, 10-year swap to 2013-09-16, MGE spring wheat to 2025-06-27", "read-directly"),
     "verdict": "Only vendor read whose licence lets the raw history be frozen permanently (rule 4) and derived results kept "
                "and published; deepest pre-1980 history. Most expensive retail option at list prices."},
    {"vendor": "Pinnacle Data (CLC and Deep History)", "rank": 2,
     "pages": ["http://www.pinnacledata.com/clc.html", "http://www.pinnacledata.com/extended-clc.html",
               "http://www.pinnacledata.com/orderDB.asp", "http://www.pinnacledata.com/disclaimer.asp"],
     "scores": {
         COLUMNS[0]: g("yes", "Deep History: 'ALL of the historical contracts for the 70 commodities we follow', 'approximately "
                              "8,000', 'some back to 1969' (the summary on the same page says about 10,000)", "read-directly"),
         COLUMNS[1]: g("yes", "CLC roll day published per market (e.g. 8th day of the delivery month for currencies, 22nd of "
                              "the prior month for grains); back, ratio or non-adjusted linking in its DataMaker software; "
                              "individual contracts allow the project's own roll", "read-directly"),
         COLUMNS[2]: g("yes", "CLC: '98 most popular commodities'; 65 distinct markets in the published start-date table", "read-directly"),
         COLUMNS[3]: g("yes", "grains and meats 1969-71, softs and metals 1973-75, currencies 1975-78, T-bond 1978; Bund, gilt, "
                              "short sterling 1989; mostly US exchanges", "read-directly"),
         COLUMNS[4]: g("yes", "CLC fields: open, high, low, settle, open interest, total volume, total open interest; Deep: OHLC, "
                              "total volume, contract open interest", "read-directly"),
         COLUMNS[5]: g("no", "no contract specifications or their history were found on the site", "read-directly"),
         COLUMNS[6]: g("yes", "ASCII and MetaStock files", "read-directly"),
         COLUMNS[7]: g("yes", "Deep History $149, Light History $49, CLC $99 (one-off); updates $20/month (3-month minimum) or "
                              "$216/year for one database", "read-directly")},
     "licence": g("unknown", "no licence text published; the site carries only a disclaimer of warranties. Terms must be "
                             "obtained in writing before purchase", "read-directly"),
     "survivorship": g("partial", "pork bellies (delisted) is in the CLC list; the Deutsche mark is spliced into the euro "
                                  "series; markets that died earlier are not listed", "read-directly"),
     "vendor_risk": g("high", "HTTPS certificate failed verification; the order page still warns Netscape users; "
                              "whether the data are maintained to date was not verified", "read-directly"),
     "verdict": "Cheapest route to individual contracts back to 1969 (about $250 one-off). US-centric; licence unknown; "
                "best used as a second source to reconcile against the primary vendor."},
    {"vendor": "Norgate Data (Futures package)", "rank": 3,
     "pages": ["https://norgatedata.com/futurespackage.php", "https://norgatedata.com/data-content-tables.php",
               "https://norgatedata.com/faq.php", "https://norgatedata.com/system-requirements.php"],
     "scores": {
         COLUMNS[0]: g("yes", "'Along with individual futures contracts, the service provides spot-month continuous "
                              "contracts'", "read-directly"),
         COLUMNS[1]: g("yes", "arithmetic back-adjustment; roll on the business day before last trade (cash-settled) or "
                              "before first notice (deliverable), major cycle only where minor months are thin", "read-directly"),
         COLUMNS[2]: g("yes", "'around 100 Futures markets drawn from 11 worldwide exchanges'; 94 distinct markets in the "
                              "content table, about 70 non-equity", "read-directly"),
         COLUMNS[3]: g("partial", "'back to around 1980': 27 non-equity markets by 1980, 43 by 1989; nothing before 1977; "
                                  "Eurex bonds only from 1999 (Bund 1999-01-04)", "read-directly"),
         COLUMNS[4]: g("yes", "close is the official settlement unless stated; volume and open interest, total-market on "
                              "continuous series", "read-directly"),
         COLUMNS[5]: g("partial", "a contract-details spreadsheet is linked (not opened); metadata include the 'lowest ever "
                                  "minimum price change increment'; no history of specification changes found", "read-directly"),
         COLUMNS[6]: g("partial", "Python package listed; the updater needs .NET Framework 4.8, i.e. Windows (a VM counts "
                                  "as an installation); the database cannot be queried from another machine", "read-directly"),
         COLUMNS[7]: g("yes", "USD 148.50 for 6 months, USD 270 for 12 months; recurring for as long as the data are kept", "read-directly")},
     "licence": g("poor fit", "personal use by individuals only, 'no alternative business/commercial licensing'; derived "
                              "results (trading results, model parameters, statistics) may be kept; all exported data, "
                              "snapshots and backups must be deleted when the subscription ends; not in a shared repository",
                  "read-directly"),
     "survivorship": g("no (market level)", "expired contracts of live markets are included, but no delisted market "
                                            "(Eurodollar, Deutsche mark, pork bellies) appears in the table", "read-directly (absence) / reasoning"),
     "verdict": "Best maintained low-cost subscription with a clear roll rule, but the delete-on-expiry rule conflicts with "
                "freezing inputs at first use unless the subscription is kept indefinitely; no 1970s; market-level "
                "survivorship; Windows only."},
    {"vendor": "CSI Data (Unfair Advantage)", "rank": 4,
     "pages": ["https://apps.csidata.com/OrderUA", "https://csidata.com/?page_id=14", "https://www.csidata.com/?page_id=824"],
     "scores": {
         COLUMNS[0]: g("yes", "contract-level data of active markets; continuous series computed from them", "read-directly"),
         COLUMNS[1]: g("yes", "user-defined rolls: calendar, days before expiry, volume or open-interest rules; back-adjusted, "
                              "ratio, Nth nearest, perpetual, Gann", "read-directly"),
         COLUMNS[2]: g("yes", "World Futures 'nearly 1,000+ futures'; 150 markets processed per day on Gold", "read-directly"),
         COLUMNS[3]: g("partial", "Gold: 30 years included plus up to 10 extra years ($30 a year) = 40 years, about 1986; "
                                  "'Full History options': price on request", "read-directly"),
         COLUMNS[4]: g("yes", "OHLC, volume and open interest, market totals; RTH settlements", "read-directly"),
         COLUMNS[5]: g("partial", "'Listings & Specifications' factsheets exist; the listing pages returned 403", "read-directly / blocked"),
         COLUMNS[6]: g("partial", "export to CSI, MetaStock, ASCII or Excel from the Windows UA program; no API found", "read-directly"),
         COLUMNS[7]: g("yes", "Gold World Futures: $200 one-time licensing fee + $899/year + extra history up to $300; Silver "
                              "World Futures: $120 + $689/year (10 years) or $79.50/month (5 years); history only, World "
                              "Futures: 20 years $500; full history: price on request", "read-directly")},
     "licence": g("poor fit", "'personal and private use'; may not 'create derivative works from' the data; 'creating "
                              "derivative(s), publication ... redistribution' counts as commercial; exports are encoded to "
                              "identify the account; licence revoked if updates lapse two months", "read-directly"),
     "survivorship": g("no", "'Inactive futures not included' (every package)", "read-directly"),
     "verdict": "Broad and flexible, but excludes inactive markets, caps published history at about 40 years, and its "
                "licence forbids derived works."},
    {"vendor": "CME DataMine (exchange, end of day)", "rank": 5,
     "pages": ["https://www.cmegroup.com/market-data/datamine-historical-data.html"],
     "scores": {
         COLUMNS[0]: g("yes", "contract-level end-of-day settlement, volume, open interest", "search-summary"),
         COLUMNS[1]: g("n/a", "raw exchange data; the project builds its own roll", "reasoning"),
         COLUMNS[2]: g("partial", "CME, CBOT, NYMEX, COMEX products only: no ICE, Eurex, LIFFE or Asian markets", "reasoning"),
         COLUMNS[3]: g("yes", "end of day from 1982-01-01 or contract inception", "search-summary"),
         COLUMNS[4]: g("yes", "official settlement, volume, open interest", "search-summary"),
         COLUMNS[5]: g("partial", "exchange product definitions; history not checked", "reasoning"),
         COLUMNS[6]: g("partial", "CSV delivery", "search-summary"),
         COLUMNS[7]: g("price on request", "'varies based upon data type and duration'", "search-summary")},
     "licence": g("unknown", "not read", "blocked"),
     "survivorship": g("yes", "exchange archive includes expired contracts", "reasoning"),
     "verdict": "Authoritative for US markets from 1982; too narrow alone; price on request; site blocked automated access."},
    {"vendor": "LSEG Datastream / Refinitiv", "rank": 6,
     "pages": ["https://www.lseg.com/en/data-catalogue/derivatives/reference/futures-reference-data"],
     "scores": {
         COLUMNS[0]: g("yes", "individual futures and continuous series", "search-summary"),
         COLUMNS[1]: g("partial", "'34,000 continuous series' with six calculation methods", "search-summary"),
         COLUMNS[2]: g("yes", "global", "search-summary"),
         COLUMNS[3]: g("yes", "futures time series from 1973", "search-summary"),
         COLUMNS[4]: g("yes", "settlement, open, high, low; volume and open interest per series", "search-summary"),
         COLUMNS[5]: g("partial", "reference data product exists", "search-summary"),
         COLUMNS[6]: g("partial", "Excel add-in (Windows) or Workspace; API terms not read", "search-summary"),
         COLUMNS[7]: g("price on request", "no published price; usually institutional or academic", "search-summary")},
     "licence": g("unknown", "academic licences are 'non-commercial research purposes only' (university pages)", "search-summary"),
     "survivorship": g("yes", "dead series retained", "reasoning"),
     "verdict": "Moskowitz-Ooi-Pedersen's main source ('mainly Datastream, Bloomberg, and various exchanges', read); "
                "not priced publicly; institutional."},
    {"vendor": "Bloomberg (upper bound)", "rank": 7, "pages": [],
     "scores": {c: g("yes" if i in (0, 2, 3, 4, 5, 6) else "price on request", "", "reasoning") for i, c in enumerate(COLUMNS)},
     "cost_note": g("~$31,980 a year per single terminal (third-party reports; Bloomberg publishes no price)", "", "search-summary"),
     "licence": g("poor fit", "terminal data are licensed for the subscriber's display use; bulk extraction and redistribution "
                              "are restricted", "reasoning"),
     "survivorship": g("yes", "expired contracts retrievable", "reasoning"),
     "verdict": "Upper bound on cost; not justified for one historical read."},
    {"vendor": "Barchart / cmdty", "rank": 8, "pages": ["https://www.barchart.com/ondemand/futures-end-of-day-data-api"],
     "scores": {c: g("unknown", "", "blocked") for c in COLUMNS},
     "notes": [g("no", "retail Premier downloads: daily data back to 2000-01-01; weekly/monthly from 1980; 250 CSV files a day",
                 "search-summary"),
               g("price on request", "enterprise historical data via sales", "search-summary")],
     "licence": g("unknown", "", "blocked"), "survivorship": g("unknown", "", "blocked"),
     "verdict": "Retail daily history starts in 2000 (spent era); enterprise product unpriced; pages blocked (HTTP 202 challenge)."},
    {"vendor": "Databento (CME, ICE, Eurex)", "rank": 9,
     "pages": ["https://databento.com/pricing", "https://databento.com/docs/venues-and-datasets/glbx-mdp3"],
     "scores": {
         COLUMNS[0]: g("yes", "all CME futures and options; instrument definitions", "read-directly"),
         COLUMNS[1]: g("partial", "raw contracts; continuous symbology not read", "reasoning"),
         COLUMNS[2]: g("yes", "CME Globex all products; 45+ venues", "read-directly"),
         COLUMNS[3]: g("no", "CME 'beginning in June 2010'; ICE datasets from 2018-07-02 (constant in the site's script, "
                             "inferred to be the ICE start)", "read-directly"),
         COLUMNS[4]: g("yes", "statistics schema: settlement price, open interest, cleared volume", "read-directly"),
         COLUMNS[5]: g("yes", "definition schema", "read-directly"),
         COLUMNS[6]: g("yes", "Python, C++ and Rust clients", "read-directly"),
         COLUMNS[7]: g("partial", "usage-based $/GB, $125 sign-up credit; per-GB rates are rendered by script (search: 'from "
                                  "$0.50/GB')", "read-directly / search-summary")},
     "licence": g("partial", "personal use with Databento as vendor of record; external distribution only on the Unlimited plan",
                  "read-directly"),
     "survivorship": g("yes", "expired instruments in definitions", "reasoning"),
     "verdict": "Excellent for the executable forward record; useless for the pre-2003 never-read window."},
    {"vendor": "Nasdaq Data Link (paid futures)", "rank": None,
     "pages": ["https://data.nasdaq.com/databases/SCF", "https://data.nasdaq.com/data/CHRIS-wiki-continuous-futures"],
     "scores": {}, "licence": g("n/a", "", "blocked"), "survivorship": g("n/a", "", "blocked"),
     "verdict": "No paid futures product located: both pages returned 404 (the scoping memo recorded CHRIS as 403)."},
    {"vendor": "Tick Data LLC", "rank": None, "pages": ["https://www.tickdata.com/product/historical-futures-data/"],
     "scores": {}, "licence": g("unknown", "", "read-directly"), "survivorship": g("unknown", "", "read-directly"),
     "verdict": "Intraday specialist ('over 280 global futures contracts'); price on request; not needed for monthly trend."},
    {"vendor": "WRDS (academic)", "rank": None, "pages": [],
     "scores": {}, "licence": g("n/a", "institutional subscription only", "reasoning"), "survivorship": g("n/a", "", "reasoning"),
     "verdict": "Gives Datastream to subscribing institutions; OptionMetrics (options) is not relevant to non-equity trend; "
                "not available to this fund."},
]

COSTS = {
    "basis": "Published prices only, USD, excluding tax, before any unpublished discount. 'markets' = the supplement list "
             "(commodities and non-US rates) of the recommended design; 40 is a liquid core, 75 is every such market "
             "Portara lists by 2002.",
    "Pinnacle Deep + CLC": {"one_off": 248, "recurring": 0, "five_year": 248, "access": "read-directly"},
    "Norgate (12-month renewals to keep the frozen copy)": {"one_off": 0, "recurring_per_year": 270, "five_year": 1350,
                                                           "plus": "a Windows licence for a VM (not costed)", "access": "read-directly"},
    "CSI Gold World Futures + 10 extra years": {"one_off": 200 + 300, "recurring_per_year": 899, "first_year": 1399,
                                                "five_year": 1399 + 4 * 899, "note": "history before ~1986: price on request",
                                                "access": "read-directly"},
    "Portara one-off, 40 markets": {"list": 40 * 330, "special": 40 * 220, "access": "read-directly"},
    "Portara one-off, 75 markets": {"list": 75 * 330, "special": 75 * 220, "access": "read-directly"},
    "Portara individual-contract daily ('Tenors')": "price on request",
    "CME DataMine": "price on request", "LSEG Datastream": "price on request", "Barchart enterprise": "price on request",
    "Bloomberg": {"per_year": 31980, "access": "search-summary (third-party)"},
}

INDEPENDENCE = [
    ("Commodities ex gold, 1968-2002", "independent", "never read before 2003; DBC (S1) starts 2006, WTI was a check only"),
    ("Gold, 1974-2002", "independent", "gold reads S7 (2006+), S8 (2012+), GLD in S1 (2004+)"),
    ("US Treasury futures, 1977-2002", "independent of spent reads; same markets and dates as the proxy",
     "if the proxy is read first, these become spent; in a single combined read they are one leg, not two"),
    ("Non-US bond and STIR futures, 1980-2002", "independent", "never read"),
    ("Currency futures, 1975-1989", "independent; same exposure as the proxy's H.10 leg", "as for US rates"),
    ("Currency futures, 1990-2003", "partly overlapping", "same currencies and dates as the cross-sectional FX "
     "confirmation read (S6, 1990-01..2003-12); time-series signals never read"),
    ("Commodities and non-US rates, 2003-2019", "partly overlapping", "S1 development (DBC, GLD, IEF, TLT, UUP; open, "
     "examined) and S7 gold development 2006-2018 share exposures and dates"),
    ("US rates, gold, broad commodities, dollar, 2003-2019", "not independent", "S1 instruments in S1 dates"),
    ("Currencies, 2004-2026", "not independent", "S6 development and holdout; UUP in S1"),
    ("Everything, 2020-2025", "not independent", "S1 test read once; the fund window S13"),
    ("Everything, 2026", "not independent", "sealed fund window"),
    ("Equity-index futures, all years", "not independent", "S2-S4: the US market 1926-2026 and three regions 1990-2025, "
     "including equity time-series momentum (S3)"),
    ("VIX futures, 2004-2026", "partly overlapping", "VIX level used as a state in S9; free from Cboe anyway"),
]

LOG = [
    ("Norgate futurespackage.php, data-content-tables.php, faq.php, system-requirements.php", "read-directly", "200"),
    ("Norgate licensing-agreement.php, python-package.php, data-faq.php (guessed paths)", "blocked", "404"),
    ("pypi.org/project/norgatedata", "blocked", "JavaScript challenge"),
    ("CSI apps.csidata.com/OrderUA (prices in the page's script), csidata.com page 14, licence page 824", "read-directly", "200"),
    ("CSI apps.csidata.com/factsheets.php (CME, CBT)", "blocked", "403"),
    ("pinnacledata.com over HTTPS", "blocked", "certificate failed verification"),
    ("pinnacledatacorp.yolasite.com", "blocked", "403"),
    ("pinnacledata.com over HTTP: index, clc, extended-clc, products, orderDB, disclaimer", "read-directly", "200"),
    ("portaracqg.com: home, pricing, license, historical-daily-futures-data, continuous-futures-data", "read-directly", "200"),
    ("databento.com/pricing", "read-directly (script bundle text); prices rendered client-side not obtained", "200"),
    ("databento.com/docs/venues-and-datasets/glbx-mdp3, ifus-impact, xeur-eobi", "read-directly", "200"),
    ("databento.com/licensing, /terms (guessed paths)", "blocked", "404"),
    ("barchart.com ondemand, web-services historical, my/price-history", "blocked", "HTTP 202 empty (bot challenge)"),
    ("cmegroup.com DataMine pages", "blocked", "403 / timeout"),
    ("data.nasdaq.com/databases/SCF, CHRIS page", "blocked", "404"),
    ("wrds-www.wharton.upenn.edu Datastream vendor page (guessed path)", "blocked", "404"),
    ("tickdata.com historical futures", "read-directly", "200"),
    ("firstratedata.com futures page", "not used", "served an unrelated stock listing"),
    ("Moskowitz-Ooi-Pedersen 2012 PDF (pages.stern.nyu.edu), Hurst-Ooi-Pedersen 2017 PDF (fairmodel.econ.yale.edu)",
     "read-directly", "200"),
    ("Searches: Norgate pricing; CSI price list; Pinnacle CLC price; Databento GLBX history and plan price; Barchart "
     "history and Premier limits; Nasdaq Data Link SCF/OWF; CME DataMine price; LSEG Datastream futures; Bloomberg "
     "terminal cost", "search-summary", "used only where labelled"),
]


def main():
    pw = json.load(open(os.path.join(HERE, "PROCURE_POWER.json")))
    ts = pw["time_varying"]
    key = {"proxy": "proxy_1962_2002 (rates + FX 1972-89)",
           "replace_1975": "portara_replace_1975_2002 (all non-equity; FX to 1989)",
           "replace_1980_norgate": "norgate_replace_1980_2002",
           "combined_portara": "combined_proxy_plus_portara_supplement_1962_2002",
           "combined_norgate": "combined_proxy_plus_norgate_supplement_1962_2002",
           "combined_pinnacle": "combined_proxy_plus_pinnacle_supplement_1962_2002",
           "supplement_only_portara": "portara_supplement_only_1970_2002 (commodities + non-US rates)"}
    head = {}
    for k, name in key.items():
        head[k] = {w: {a: {f: ts[name][w][a][f] for f in ("AR_eff", "power_0.10/40", "power_5%")} for a in ("0.1", "0.2", "0.3")}
                   for w in ("MOP (US curve rho 0.38)", "uniform rho 0.1", "uniform rho 0.2", "uniform rho 0.3")}
        head[k]["years"] = ts[name]["years"]
    out = {
        "date": "2026-11-25", "status": "procurement assessment; no vendor contacted; no purchase; no return statistic computed",
        "access_labels": ["read-directly", "search-summary", "blocked", "reasoning"],
        "columns": COLUMNS, "vendors": VENDORS, "costs": COSTS,
        "independence_by_segment": [{"segment": s, "grade": gr, "why": w} for s, gr, w in INDEPENDENCE],
        "power_headline": head,
        "mop_calibration": pw["mop_calibration"],
        "market_years": pw["market_years"],
        "decision": {
            "question": "Does procurement add enough incremental evidence to replace or supplement the 1962-2002 "
                        "yield-and-FX proxy experiment?",
            "answer": "Supplement, not replace, and only conditionally. One combined read 1962-2002 (proxy rates and FX "
                      "plus vendor commodities and non-US rates from their first trade) is the only design whose power at "
                      "the programme level clears 0.5 at a single-market AR of 0.2, and only if trend-return correlations "
                      "are near the 1985-2009 levels Moskowitz-Ooi-Pedersen report (uniform rho about 0.1 or less). At "
                      "rho 0.2-0.3 the gain is small and neither design is an admission test. Replacing the proxy with "
                      "vendor data alone (1975 or 1980 to 2002) is dominated by the combined read.",
            "recommended_quotes": ["Portara: one-off daily, individual contracts and back-adjusted series, for a "
                                   "pre-registered list of about 40 commodity and non-US rate markets, with open interest; "
                                   "licence for a single-owner paper fund", "Pinnacle: written licence terms for Deep History "
                                   "and confirmation that the data are maintained"],
        },
        "sources": {"pages_sha256_prefix": {
            "norgate_futurespackage": "e8291a1a44dd3965", "norgate_data_content_tables": "76450ab047e18b70",
            "norgate_faq": "75042f4ea5679378", "csi_orderua": "e38fcd029a533a68", "csi_licence": "21b06302d8150be8",
            "pinnacle_clc": "4c09c7073bb84230", "pinnacle_extended_clc": "abf08a3cd431149b", "pinnacle_order": "e3ae08486965d682",
            "portara_pricing": "d9bbc4c5e0676043", "portara_license": "896a1bd6a50080c6", "portara_daily": "642e83ba1e0329d0",
            "portara_continuous": "a8da28959d3d54ef", "databento_glbx_docs": "885ed1880c4f375c",
            "mop_2012_pdf": "7682f8e97eb4b775", "hop_2017_pdf": "7b286a9f6cf6925a"},
            "access_log": [{"what": w, "label": l, "status": s} for w, l, s in LOG]},
    }
    json.dump(out, open(os.path.join(HERE, "PROCURE.json"), "w"), indent=1)
    print(json.dumps(head["proxy"]["MOP (US curve rho 0.38)"]), json.dumps(head["combined_portara"]["MOP (US curve rho 0.38)"]))


if __name__ == "__main__":
    main()
