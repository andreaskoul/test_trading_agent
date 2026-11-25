"""Free-data inventory for the cross-asset trend read (FREE_DATA.md): fetch, freeze, coverage counts, breadth and power.

INVENTORY ONLY. Nothing here computes a return, a signal, a Sharpe ratio or a correlation of any price series, on
any date. For every kept file it records presence only: first and last dates, observations per year, month-end
coverage, roll counts (distinct contract labels per year), gaps, duplicate or non-monotonic dates, declared fields.
No price, yield or rate value is printed or written. The breadth and power arithmetic reuses procure_power.py and
reads only the market counts by year derived from these first dates.

    python -I research/xasset/free_coverage.py fetch      # download once into .cache/xasset-free, freeze sha256
    python -I research/xasset/free_coverage.py coverage   # -> research/xasset/free_coverage.json
    python -I research/xasset/free_coverage.py power      # -> research/xasset/FREE_POWER.json

`fetch` refuses to overwrite a frozen file and fails if a cached file's sha256 differs from FREE_MANIFEST.json.
`coverage` needs pandas; the Bank of England workbook also needs openpyxl (without it that source is recorded as
not inspected, never guessed). Generic User-Agent; no login, account or key is used by any request.
"""
import hashlib
import io
import json
import os
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = os.environ.get("XASSET_FREE_CACHE", os.path.join(ROOT, ".cache", "xasset-free"))
MANIFEST = os.path.join(HERE, "FREE_MANIFEST.json")
UA = {"User-Agent": "research-client/1.0"}
END = "2002-12-31"  # coverage counts stop here; the read window ends 2002-06 (SCOPE.md section 7)

# ---- registered market lists (fixed before any coverage count) ----------------------------------------------------
PST_SHA = "bbf5cf823e16be1cca27493a94099eb8cf33f6e7"  # robcarver17/pysystemtrade develop, 2026-11-02
PST = f"https://raw.githubusercontent.com/robcarver17/pysystemtrade/{PST_SHA}/data/futures/"
# market -> (class, variants). Variants are minis/micros that pysystemtrade back-fills with full-size history;
# the market's first date is the earliest variant (flagged). Equity indices, the dollar index, GSCI and the
# high-yield index are excluded (core duplicates or index products).
PST_MARKETS = {
    "OJ": ("COM", ["OJ"]), "SOYOIL": ("COM", ["SOYOIL"]), "SUGAR11": ("COM", ["SUGAR11"]),
    "COTTON2": ("COM", ["COTTON2"]), "COCOA": ("COM", ["COCOA"]), "OATIES": ("COM", ["OATIES"]),
    "SOYMEAL": ("COM", ["SOYMEAL"]), "SILVER": ("COM", ["SILVER"]), "PLAT": ("COM", ["PLAT"]),
    "WHEAT": ("COM", ["WHEAT", "WHEAT_mini"]), "CORN": ("COM", ["CORN", "CORN_mini"]),
    "LIVECOW": ("COM", ["LIVECOW"]), "LEANHOG": ("COM", ["LEANHOG"]),
    "GOLD": ("COM", ["GOLD", "GOLD-mini", "GOLD_micro"]), "FEEDCOW": ("COM", ["FEEDCOW"]),
    "PALLAD": ("COM", ["PALLAD"]), "CANOLA": ("COM", ["CANOLA"]), "HEATOIL": ("COM", ["HEATOIL"]),
    "SOYBEAN": ("COM", ["SOYBEAN", "SOYBEAN_mini"]), "GASOILINE": ("COM", ["GASOILINE", "GASOILINE_micro"]),
    "GASOIL": ("COM", ["GASOIL"]), "RICE": ("COM", ["RICE"]),
    "CRUDE_W": ("COM", ["CRUDE_W", "CRUDE_W_mini", "CRUDE_W_micro"]), "SUGAR_WHITE": ("COM", ["SUGAR_WHITE"]),
    "COCOA_LDN": ("COM", ["COCOA_LDN"]), "BRENT_W": ("COM", ["BRENT_W"]), "GAS_US": ("COM", ["GAS_US", "GAS_US_mini"]),
    "WHEAT_ICE": ("COM", ["WHEAT_ICE"]), "COPPER": ("COM", ["COPPER", "COPPER-mini", "COPPER-micro"]),
    "REDWHEAT": ("COM", ["REDWHEAT"]), "MILK": ("COM", ["MILK"]), "MILKWET": ("COM", ["MILKWET"]),
    "MILLWHEAT": ("COM", ["MILLWHEAT"]),
    "CAD": ("FX", ["CAD", "CAD_micro"]), "CHF": ("FX", ["CHF", "CHF_micro"]), "GBP": ("FX", ["GBP", "GBP_micro"]),
    "JPY": ("FX", ["JPY", "JPY_mini"]), "AUD": ("FX", ["AUD", "AUD_micro"]),
    "US20": ("FI_US", ["US20"]), "US10": ("FI_US", ["US10"]), "US5": ("FI_US", ["US5"]), "US2": ("FI_US", ["US2"]),
    "SOFR": ("FI_US", ["SOFR"]), "FED": ("FI_US", ["FED"]),
    "GILT": ("FI_INTL", ["GILT"]), "EURIBOR": ("FI_INTL", ["EURIBOR", "EURIBOR-ICE"]), "CAD10": ("FI_INTL", ["CAD10"]),
    "CH10": ("FI_INTL", ["CH10"]), "JGB": ("FI_INTL", ["JGB", "JGB-mini", "JGB-SGX-mini"]),
}
CHRIS_SHA = "9bc6600cb5e71b6267fbe360e32df1d8c7c7aab2"  # webclinic017/first_trading_algo master, 2019-12-20
CHRIS = f"https://raw.githubusercontent.com/webclinic017/first_trading_algo/{CHRIS_SHA}/data/"
CHRIS_SYMS = {  # front-month continuous files in the Quandl CHRIS column layout; class by CME/ICE root
    "ZC": "COM", "ZW": "COM", "ZS": "COM", "ZM": "COM", "ZL": "COM", "ZO": "COM", "ZR": "COM", "CC": "COM",
    "CT": "COM", "KC": "COM", "SB": "COM", "OJ": "COM", "LB": "COM", "LE": "COM", "FC": "COM", "HE": "COM",
    "GC": "COM", "SI": "COM", "HG": "COM", "PL": "COM", "PA": "COM", "CL": "COM", "HO": "COM", "NG": "COM",
    "RB": "COM", "ZN": "FI_US", "A6": "FX", "B6": "FX", "D6": "FX", "E6": "FX", "J6": "FX", "N6": "FX", "S6": "FX",
}
BOJ = "https://www.stat-search.boj.or.jp/api/v1/getDataCode?format=csv&lang=en&db={db}&code={code}"
BBK = "https://api.statistiken.bundesbank.de/rest/data/BBSIS/M.I.ZST.ZI.EUR.S1311.B.A604.{m}.R.A.A._Z._Z.A?format=csv&lang=en"

SOURCES = {}
for _m, (_c, _vs) in PST_MARKETS.items():
    for _v in _vs:
        SOURCES[f"pst_multiple_{_v}.csv"] = PST + f"multiple_prices_csv/{_v}.csv"
        SOURCES[f"pst_adjusted_{_v}.csv"] = PST + f"adjusted_prices_csv/{_v}.csv"
SOURCES["pst_rollconfig.csv"] = PST + "csvconfig/rollconfig.csv"
SOURCES["pst_instrumentconfig.csv"] = PST + "csvconfig/instrumentconfig.csv"
for _s in CHRIS_SYMS:
    SOURCES[f"chris_{_s}.csv"] = CHRIS + f"{_s}.csv"
SOURCES.update({
    "bis_WS_CBPOL_csv_flat.zip": "https://data.bis.org/static/bulk/WS_CBPOL_csv_flat.zip",
    "bis_WS_XRU_csv_flat.zip": "https://data.bis.org/static/bulk/WS_XRU_csv_flat.zip",
    "boj_FM02_STRECLCOON.csv": BOJ.format(db="FM02", code="STRECLCOON"),
    "boj_FM08_FXERM06.csv": BOJ.format(db="FM08", code="FXERM06"),
    "boj_FM08_FXERM27.csv": BOJ.format(db="FM08", code="FXERM27"),
    "mof_jgbcme_all.csv": "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv",
    "bbk_svensson_M_R02XX.csv": BBK.format(m="R02XX"),
    "bbk_svensson_M_R05XX.csv": BBK.format(m="R05XX"),
    "bbk_svensson_M_R10XX.csv": BBK.format(m="R10XX"),
    "boe_glcnominalmonthedata.zip": "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/glcnominalmonthedata.zip",
    "statcan_10100122-eng.zip": "https://www150.statcan.gc.ca/n1/tbl/csv/10100122-eng.zip",
    "snb_zimoma.csv": "https://data.snb.ch/api/cube/zimoma/data/csv/en",
    "snb_rendoblim.csv": "https://data.snb.ch/api/cube/rendoblim/data/csv/en",
})


class InputDefect(Exception):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_manifest():
    return json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {"files": {}, "failed": {}}


def fetch():
    man = load_manifest()
    os.makedirs(CACHE, exist_ok=True)
    for name, url in SOURCES.items():
        p = os.path.join(CACHE, name)
        if name in man["files"]:
            if not os.path.exists(p):
                raise InputDefect(f"{name}: frozen file missing from {CACHE}; refusing to fetch a new vintage")
            if sha256(p) != man["files"][name]["sha256"]:
                raise InputDefect(f"{name}: sha256 differs from FREE_MANIFEST.json")
            continue
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as f:
                data = f.read()
            if f.headers.get("Content-Encoding") == "gzip" or data[:2] == b"\x1f\x8b":
                import gzip
                data = gzip.decompress(data)
        except Exception as e:  # recorded, never hidden
            man["failed"][name] = {"source": url, "error": repr(e)[:300]}
            print("FAILED", name, repr(e)[:120])
            continue
        open(p, "wb").write(data)
        man["files"][name] = {"source": url, "bytes": len(data), "sha256": sha256(p),
                              "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        man["failed"].pop(name, None)
        time.sleep(0.05)
    man["note"] = ("Frozen at first fetch (CLAUDE.md rule 4). Files live in .cache/xasset-free and are not committed: "
                   "third-party data. Inventory use only; see free_coverage.py.")
    json.dump(man, open(MANIFEST, "w"), indent=1, sort_keys=True)
    print(len(man["files"]), "frozen;", len(man["failed"]), "failed")


def path(name):
    man = load_manifest()
    if name not in man["files"]:
        raise InputDefect(f"{name}: not frozen")
    p = os.path.join(CACHE, name)
    if sha256(p) != man["files"][name]["sha256"]:
        raise InputDefect(f"{name}: sha256 differs from FREE_MANIFEST.json")
    return p


# ---- presence statistics (dates and counts only) ------------------------------------------------------------------
def presence(dates, end=END, start="1962-01-01"):
    """dates: pandas DatetimeIndex of observations with a value. Returns counts only."""
    import pandas as pd
    d = pd.DatetimeIndex(dates).sort_values()
    out = {"first": str(d.min().date()) if len(d) else None, "last": str(d.max().date()) if len(d) else None,
           "n_total": int(len(d))}
    w = d[(d >= start) & (d <= end)]
    out["n_1962_2002"] = int(len(w))
    if len(w):
        months = pd.PeriodIndex(w, freq="M")
        last_days = w[(w + pd.offsets.MonthEnd(0) - w).days <= 7]  # an observation in the month's last 7 days
        out["months_with_obs"] = int(months.nunique())
        out["months_with_month_end_obs"] = int(pd.PeriodIndex(last_days, freq="M").nunique())
        out["first_month_end_obs"] = str(pd.PeriodIndex(last_days, freq="M").min()) if len(last_days) else None
        gaps = pd.Series(w[1:] - w[:-1]).dt.days if len(w) > 1 else pd.Series(dtype=float)
        out["median_gap_days"] = float(gaps.median()) if len(gaps) else None
        out["max_gap_days"] = int(gaps.max()) if len(gaps) else None
        out["obs_per_year"] = {str(k): int(v) for k, v in pd.Series(1, index=w).groupby(w.year).sum().items()}
    return out


def pst_cov():
    import pandas as pd
    res = {}
    for market, (cls, variants) in PST_MARKETS.items():
        vr = {}
        for v in variants:
            m = pd.read_csv(path(f"pst_multiple_{v}.csv"))
            dt = pd.to_datetime(m["DATETIME"])
            r = {"columns": list(m.columns), "duplicate_dates": int(dt.duplicated().sum()),
                 "non_monotonic": int((dt.diff().dt.total_seconds() < 0).sum())}
            r["PRICE"] = presence(dt[m["PRICE"].notna()])
            r["CARRY"] = presence(dt[m["CARRY"].notna()])
            r["FORWARD"] = presence(dt[m["FORWARD"].notna()])
            pre = m[(dt <= END)]
            yrs = pd.to_datetime(pre["DATETIME"]).dt.year
            r["distinct_price_contracts_per_year"] = {str(k): int(v) for k, v in
                                                     pre.groupby(yrs)["PRICE_CONTRACT"].nunique().items()}
            r["carry_contract_differs_share_pre2003"] = (
                round(float((pre["CARRY_CONTRACT"] != pre["PRICE_CONTRACT"]).mean()), 3) if len(pre) else None)
            a = pd.read_csv(path(f"pst_adjusted_{v}.csv"))
            col = [c for c in a.columns if c != "DATETIME"][0]
            r["ADJUSTED"] = presence(pd.to_datetime(a["DATETIME"])[a[col].notna()])
            r["ADJUSTED"]["value_column"] = col
            vr[v] = r
        firsts = {v: vr[v]["ADJUSTED"]["first"] for v in variants}
        first_v = min(firsts, key=lambda v: firsts[v])
        res[market] = {"class": cls, "variants": vr, "first_adjusted": firsts[first_v], "first_variant": first_v,
                       "first_from_minor_variant": first_v != variants[0]}
    return res


def chris_cov():
    import pandas as pd
    res = {}
    for s, cls in CHRIS_SYMS.items():
        d = pd.read_csv(path(f"chris_{s}.csv"))
        dt = pd.to_datetime(d["Date"])
        px = "Settle" if "Settle" in d.columns else "Last"
        res[s] = {"class": cls, "columns": list(d.columns), "price_column": px,
                  "duplicate_dates": int(dt.duplicated().sum()),
                  "order": "descending" if dt.iloc[0] > dt.iloc[-1] else "ascending",
                  "settle": presence(dt[d[px].notna()])}
    return res


def bis_cov():
    import pandas as pd
    out = {}
    z = zipfile.ZipFile(path("bis_WS_CBPOL_csv_flat.zip"))
    d = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
    d = d[d["OBS_VALUE:Observation Value"].notna()]
    want = ["US", "JP", "CH", "DE", "GB", "CA", "AU", "SE", "NO", "DK", "FR", "IT", "NL", "BE", "ES", "NZ", "XM"]
    pol = {}
    for (f, a), g in d.groupby(["FREQ:Frequency", "REF_AREA:Reference area"]):
        if a[:2] in want and f.startswith("M"):
            pol[a] = {"title": str(g["TITLE:Title"].iloc[0]).strip(),
                      "compilation": str(g["COMPILATION:Compilation"].dropna().iloc[0])[:400] if g["COMPILATION:Compilation"].notna().any() else None,
                      "first": str(g["TIME_PERIOD:Time period or range"].min()),
                      "last": str(g["TIME_PERIOD:Time period or range"].max()), "n": int(len(g))}
    out["policy_rates_monthly_end_of_period"] = pol
    z = zipfile.ZipFile(path("bis_WS_XRU_csv_flat.zip"))
    d = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
    d = d[d["OBS_VALUE:Observation Value"].notna()]
    fx = {}
    for (f, a, c), g in d.groupby(["FREQ:Frequency", "REF_AREA:Reference area", "COLLECTION:Collection"]):
        if a[:2] in want and (f.startswith("D") or (f.startswith("M") and c.startswith("E"))):
            key = f"{a} | {f} | {c}"
            if f.startswith("D"):
                fx[key] = presence(pd.to_datetime(g["TIME_PERIOD:Time period or range"]))
            else:
                fx[key] = {"first": str(g["TIME_PERIOD:Time period or range"].min()),
                           "last": str(g["TIME_PERIOD:Time period or range"].max()), "n": int(len(g)),
                           "currency": str(g["CURRENCY:Currency"].iloc[0])}
    out["fx_usd_rates"] = fx
    return out


def boj_cov():
    import csv
    out = {}
    for name in ("boj_FM02_STRECLCOON.csv", "boj_FM08_FXERM06.csv", "boj_FM08_FXERM27.csv"):
        rows = list(csv.reader(open(path(name), encoding="utf-8", errors="replace")))
        hdr = next(i for i, r in enumerate(rows) if r and r[0] == "SERIES_CODE")
        body = [r for r in rows[hdr + 1:] if len(r) >= 8]
        # layout (typed by the header row): SERIES_CODE, NAME_OF_TIME_SERIES, UNIT, FREQUENCY, CATEGORY,
        # LAST_UPDATE, SURVEY_DATES, VALUES; one row per month. Keep names and dates only.
        ix = {k: rows[hdr].index(k) for k in ("NAME_OF_TIME_SERIES", "UNIT", "FREQUENCY", "SURVEY_DATES", "VALUES")}
        have = [r[ix["SURVEY_DATES"]] for r in body if r[ix["VALUES"]].strip() not in ("", "NA")]
        out[name] = {"name": body[0][ix["NAME_OF_TIME_SERIES"]], "unit": body[0][ix["UNIT"]],
                     "frequency": body[0][ix["FREQUENCY"]], "first": min(have), "last": max(have), "n": len(have),
                     "n_1962_2002": sum(1 for x in have if x <= "200212")}
    return out


def mof_cov():
    import pandas as pd
    d = pd.read_csv(path("mof_jgbcme_all.csv"), skiprows=1, na_values="-")
    dt = pd.to_datetime(d["Date"], format="%Y/%m/%d", errors="coerce")
    return {"unparsed_dates": int(dt.isna().sum()),
            "maturities": {c: presence(dt[d[c].notna()]) for c in d.columns[1:]}}


def bbk_cov():
    import pandas as pd
    out = {}
    for m in ("R02XX", "R05XX", "R10XX"):
        p = path(f"bbk_svensson_M_{m}.csv")
        lines = open(p, encoding="utf-8-sig").read().splitlines()
        title = lines[1].split(",", 1)[1].strip().strip('"').rstrip(",")
        body = [l.split(",") for l in lines if l[:4].isdigit() and len(l.split(",")) > 1]
        have = [b[0] for b in body if b[1] not in ("", ".")]
        out[m] = {"title": title, "first": min(have) if have else None, "last": max(have) if have else None,
                  "n": len(have), "n_1962_2002": sum(1 for x in have if x <= "2002-12")}
    return out


def boe_cov():
    try:
        import openpyxl  # noqa: F401
        import pandas as pd
    except ImportError:
        return {"status": "not inspected: openpyxl not installed"}
    z = zipfile.ZipFile(path("boe_glcnominalmonthedata.zip"))
    out = {"files": z.namelist()}
    for n in z.namelist():
        if "1970" not in n:
            continue
        x = pd.ExcelFile(io.BytesIO(z.read(n)))
        out["sheets"] = x.sheet_names
        for sh in x.sheet_names:
            if "spot" not in sh.lower():
                continue
            d = x.parse(sh, header=None)
            dcol = d.iloc[:, 0]
            dates = pd.to_datetime(dcol, errors="coerce")
            hdr_row = next(i for i in range(10) if str(d.iloc[i, 0]).strip().lower().startswith("years"))
            mats = [c for c in d.iloc[hdr_row, 1:].tolist() if c == c]
            body = d[dates.notna()]
            bd = pd.to_datetime(body.iloc[:, 0])
            per_mat = {}
            for j, mat in enumerate(d.iloc[hdr_row, 1:].tolist(), start=1):
                if mat in (2, 5, 10, 20, 25) or mat in (2.0, 5.0, 10.0, 20.0, 25.0):
                    per_mat[str(mat)] = presence(bd[pd.to_numeric(body.iloc[:, j], errors="coerce").notna()])
            out[sh] = {"maturities_years": [mats[0], mats[-1]] if mats else None, "n_maturities": len(mats),
                       "rows_with_dates": int(len(body)), "selected": per_mat}
    return out


def statcan_cov():
    import pandas as pd
    z = zipfile.ZipFile(path("statcan_10100122-eng.zip"))
    d = pd.read_csv(z.open("10100122.csv"), usecols=["REF_DATE", "Rates", "VECTOR", "VALUE"], low_memory=False)
    d = d[d["VALUE"].notna()]
    keep = {"v122531": "Treasury bills: 3 month", "v122541": "T-bill auction average yield 3 month",
            "v122540": "benchmark 5 year", "v122543": "benchmark 10 years", "v122544": "benchmark long term",
            "v122487": "marketable bonds average yield over 10 years", "v122501": "same, average of Wednesdays"}
    out = {}
    for v in keep:
        g = d[d["VECTOR"] == v]
        out[v] = {"label": str(g["Rates"].iloc[0]), "first": str(g["REF_DATE"].min()), "last": str(g["REF_DATE"].max()),
                  "n": int(len(g)), "n_1962_2002": int((g["REF_DATE"] <= "2002-12").sum())}
    meta = z.read("10100122_MetaData.csv").decode("utf-8", "replace")
    out["metadata_title_line"] = meta.splitlines()[1][:300] if len(meta.splitlines()) > 1 else None
    return out


def snb_cov():
    import pandas as pd
    out = {}
    for name, keys in (("snb_zimoma.csv", ["1TGT", "3M0", "EG3M"]), ("snb_rendoblim.csv", ["2J", "5J", "10J"])):
        d = pd.read_csv(path(name), sep=";", skiprows=3)
        d = d[d["Value"].notna()]
        out[name] = {k: {"first": str(d.loc[d["D0"] == k, "Date"].min()), "last": str(d.loc[d["D0"] == k, "Date"].max()),
                         "n": int((d["D0"] == k).sum()),
                         "n_1962_2002": int(((d["D0"] == k) & (d["Date"] <= "2002-12")).sum())} for k in keys}
    return out


def coverage():
    out = {"written_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "note": "Presence counts only; no value, return or statistic of any series. See module docstring."}
    for k, fn in (("pysystemtrade", pst_cov), ("chris_mirror", chris_cov), ("bis", bis_cov), ("boj", boj_cov),
                  ("mof_jgb", mof_cov), ("bundesbank", bbk_cov), ("boe", boe_cov), ("statcan", statcan_cov),
                  ("snb", snb_cov)):
        try:
            out[k] = fn()
        except InputDefect as e:
            out[k] = {"input_defect": str(e)}
        print(k, "done")
    json.dump(out, open(os.path.join(HERE, "free_coverage.json"), "w"), indent=1, sort_keys=True)


# ---- breadth and power (design arithmetic; reads only first dates) ------------------------------------------------
def power():
    sys.path.insert(0, HERE)
    import procure_power as pp
    cov = json.load(open(os.path.join(HERE, "free_coverage.json")))
    pcov = json.load(open(os.path.join(HERE, "procure_coverage.json")))
    pst = cov["pysystemtrade"]

    def y(s):  # first full calendar year of trading after the first observation
        return int(s[:4]) + (0 if s[5:7] == "01" else 1)

    pst_start = {m: y(v["first_adjusted"]) for m, v in pst.items()}
    pst_class = {m: v["class"] for m, v in pst.items()}
    chris = cov["chris_mirror"]
    def chris_first_dense(v):
        """First year from which every year to 2002 has >= 200 settlement observations (sparse files excluded)."""
        o = v["settle"].get("obs_per_year", {})
        yrs = [yr for yr in range(1959, 2003) if all(o.get(str(z), 0) >= 200 for z in range(yr, 2003))]
        return min(yrs) + 1 if yrs else 9999  # +1: the first full year after the first dense year starts

    chris_start = {s: chris_first_dense(v) for s, v in chris.items()}
    # CHRIS root -> pysystemtrade market (same contract); used only to move a first date earlier
    CHRIS_TO_PST = {"ZC": "CORN", "ZW": "WHEAT", "ZS": "SOYBEAN", "ZM": "SOYMEAL", "ZL": "SOYOIL", "ZO": "OATIES",
                    "ZR": "RICE", "CC": "COCOA", "CT": "COTTON2", "SB": "SUGAR11", "OJ": "OJ", "LE": "LIVECOW",
                    "FC": "FEEDCOW", "HE": "LEANHOG", "GC": "GOLD", "SI": "SILVER", "HG": "COPPER", "PL": "PLAT",
                    "PA": "PALLAD", "CL": "CRUDE_W", "HO": "HEATOIL", "NG": "GAS_US", "RB": "GASOILINE"}
    CHRIS_NEW = {"KC": "COM", "LB": "COM"}  # coffee and lumber: absent from pysystemtrade before 2003

    def pst_counts(year, classes, fx_stop=1989):
        c = {}
        for m, s in pst_start.items():
            cl = pst_class[m]
            if cl in classes and s <= year and not (cl == "FX" and year > fx_stop):
                c[cl] = c.get(cl, 0) + 1
        return c

    def add(a, b):
        out = dict(a)
        for k, v in b.items():
            out[k] = out.get(k, 0) + v
        return out

    # Free yield proxies for non-US government bonds (first full year with month-end yields and a local short rate)
    # UK: BoE GLC month-end from 1970 + OECD 3m 1957; DE: Bundesbank Svensson from 1972-09 + OECD 3m 1960;
    # JP: MoF par yields from 1974-09 + BoJ end-of-month call rate 1960; CA: StatCan benchmark long term from 1976
    # (last Wednesday) + 3m T-bill 1962; CH: SNB Confederation yields from 1988 + SNB call money 1972.
    INTL_YIELD = {"UK": 1970, "DE": 1973, "JP": 1975, "CA": 1976, "CH": 1988}
    INTL_FUT_SAME = {"GILT": "UK", "CAD10": "CA", "CH10": "CH", "JGB": "JP"}  # futures on the same exposure

    def intl_yield_counts(year):
        n = sum(1 for s in INTL_YIELD.values() if s <= year)
        n += sum(1 for m in ("EURIBOR",) if pst_start[m] <= year)  # the STIR has no yield duplicate here
        return {"FI_INTL": n} if n else {}

    # Extra free currencies 1973-1989 with a short-rate differential (BIS daily spot; OECD 3m or BIS end-of-period
    # policy rate): DEM; the EMS block (FRF, NLG, BEF, ITL) is a sensitivity only, being DEM-pegged in the main.
    def fx_extra(year, ems=False):
        if not 1973 <= year <= 1989:
            return {}
        return {"FX": 1 + (4 if ems else 0)}

    def proxy(year):
        return pp.proxy_counts(year)

    def comb_free_fut(year):  # proxy + pysystemtrade commodities and non-US rate futures (the PROCURE supplement)
        return add(proxy(year), pst_counts(year, {"COM", "FI_INTL"}))

    def comb_free_full(year, ems=False):  # + non-US yield proxies replacing same-exposure futures, + extra FX
        c = add(proxy(year), pst_counts(year, {"COM"}))
        c = add(c, intl_yield_counts(year))
        c = add(c, fx_extra(year, ems))
        return c

    def comb_free_full_chris(year):  # + CHRIS mirror: earlier first dates and coffee, lumber (defective splice)
        c = comb_free_full(year)
        n = 0
        for s, m in CHRIS_TO_PST.items():
            if chris_start[s] <= year < pst_start[m]:
                n += 1
        for s in CHRIS_NEW:
            if chris_start[s] <= year:
                n += 1
        if n:
            c["COM"] = c.get("COM", 0) + n
        return c

    def vendor(vname):
        mk = pcov[vname]["markets"]
        supp = lambda cls, yr: cls in ("COM", "FI_INTL")
        return lambda yr: add(proxy(yr), pp.vendor_counts(mk, yr, supp))

    samples = {
        "proxy alone (registered design)": proxy,
        "free A: proxy + pysystemtrade commodity and non-US rate futures": comb_free_fut,
        "free B: A with non-US yield proxies (UK, DE, JP, CA, CH) and DEM": comb_free_full,
        "free B + EMS currencies (FRF, NLG, BEF, ITL), sensitivity": lambda yr: comb_free_full(yr, ems=True),
        "free C: B + CHRIS-mirror earlier starts, coffee, lumber (defective splice)": comb_free_full_chris,
        "paid: proxy + Portara supplement": vendor("portara"),
        "paid: proxy + Pinnacle supplement": vendor("pinnacle_clc"),
    }
    withins = {"MOP block (FI within 0.38)": {**pp.MOP_WITHIN, "FI_US": 0.38, "FI_INTL": 0.38},
               "uniform 0.07": 0.07, "uniform 0.1": 0.1, "uniform 0.2": 0.2}
    levels = {"0.10/40 (z 2.81)": 0.10 / 40, "5%": 0.05}
    out = {"method": "procure_power.window_ar over 1962.0-2002.5; Lo (2002) iid SE; AR_N = AR_1 N / sqrt(sum rho_ij)",
           "assumed_AR1": [0.1, 0.2, 0.3], "samples": {}}
    for name, fn in samples.items():
        row = {"N_by_year": {str(yr): fn(yr) for yr in (1962, 1965, 1970, 1975, 1980, 1985, 1989, 1990, 1995, 2002)}}
        for wn, w in withins.items():
            row[wn] = {}
            for a in (0.1, 0.2, 0.3):
                s, nbar, t = pp.window_ar(fn, 1962.0, 2002.5, w, a)
                row[wn][str(a)] = {"AR_eff": round(s, 3), "N_avg": round(nbar, 1), "years": round(t, 1),
                                   **{f"power_{k}": round(pp.power_at(s, t, v), 3) for k, v in levels.items()}}
        out["samples"][name] = row
    # check that can fail: the Portara and Pinnacle rows must reproduce PROCURE_POWER.json (MOP block, AR1 0.2)
    ref = json.load(open(os.path.join(HERE, "PROCURE_POWER.json")))["time_varying"]
    chk = {}
    for mine, theirs in (("paid: proxy + Portara supplement", "combined_proxy_plus_portara_supplement_1962_2002"),
                         ("paid: proxy + Pinnacle supplement", "combined_proxy_plus_pinnacle_supplement_1962_2002"),
                         ("proxy alone (registered design)", "proxy_1962_2002 (rates + FX 1972-89)")):
        a = out["samples"][mine]["MOP block (FI within 0.38)"]["0.2"]["power_0.10/40 (z 2.81)"]
        b = ref[theirs]["MOP (US curve rho 0.38)"]["0.2"]["power_0.10/40"]
        chk[mine] = {"this": a, "PROCURE_POWER.json": b, "match": abs(a - b) < 1e-3}
    out["reproduction_check"] = chk
    out["first_full_years"] = {"pysystemtrade": pst_start, "chris_mirror": chris_start, "intl_yield_proxies": INTL_YIELD}
    json.dump(out, open(os.path.join(HERE, "FREE_POWER.json"), "w"), indent=1)
    for name, r in out["samples"].items():
        print(f"{name[:70]:70s}", {wn[:12]: (r[wn]["0.2"]["N_avg"], r[wn]["0.2"]["power_0.10/40 (z 2.81)"],
                                             r[wn]["0.2"]["power_5%"]) for wn in withins})
    print(json.dumps(chk))


if __name__ == "__main__":
    {"fetch": fetch, "coverage": coverage, "power": power}[sys.argv[1]]()
