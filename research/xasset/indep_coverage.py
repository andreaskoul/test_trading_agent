"""Inventory of free pre-2003 commodity futures sources independent of Quandl/CHRIS (INDEP_SOURCE.md).

Counts only. No price is printed, parsed into a statistic, or compared with any other source; no return, signal,
Sharpe ratio or correlation is computed. Raw files stay in .cache/xasset-indep (not committed); their sha256 values
are written to INDEP_SOURCE.json.

    python3 -I research/xasset/indep_coverage.py <cache_dir> <dir containing xlrd> > research/xasset/INDEP_SOURCE.json

<cache_dir> holds eia/*.xls (EIA hist_xls downloads), ia/<id>_djvu.txt and ia/<id>_meta.json (Internet Archive),
misc/cot.zip (CFTC deacot1986_2016.zip) and eia_pet_notes.htm.
"""
import csv
import hashlib
import io
import json
import os
import re
import sys
import zipfile

CACHE = sys.argv[1]
sys.path.insert(0, sys.argv[2])
import xlrd  # noqa: E402

# EIA series -> pysystemtrade instrument (registered status from xasset_lib.py)
EIA = {"RCLC": ("CRUDE_W", "excluded before any check: December-only hold cycle"),
       "EER_EPD2F_PE{n}_Y35NY_DPG": ("HEATOIL", "in the registered universe; mirrored (HO)"),
       "RNGC": ("GAS_US", "in the registered universe; mirrored (NG)"),
       "EER_EPMR_PE{n}_Y35NY_DPG": ("GASOILINE", "excluded before any check: RBOB/unleaded splice; EIA has the unleaded leg"),
       "EER_EPMRR_PE{n}_Y35NY_DPG": ("GASOILINE", "RBOB leg, 2005+ only"),
       "EER_EPLLPA_PE{n}_Y44MB_DPG": (None, "propane: not a pysystemtrade pre-2003 market")}

# Internet Archive 'statistical-reference-index' microfiche items (not access-restricted), exchange yearbooks
IA = {
    "micro_IA40706904_0312": ("CBOT", "1979", "soybean and oilseed"),
    "micro_IA40706904_0311": ("CBOT", "1980", "all CBOT"),
    "micro_IA40706907_0369": ("CBOT", "1981", "grains, forest products"),
    "micro_IA40706907_0368": ("CBOT", "1981", "interest rates, metals"),
    "micro_IA40706915_0073": ("CBOT", "1982", "interest rates, metals"),
    "micro_IA40706918_0011": ("CBOT", "1984", "grains, forest products, energy"),
    "micro_IA40706918_0010": ("CBOT", "1984", "interest rates, metals"),
    "micro_IA40706921_0007": ("CBOT", "1985", "grains"),
    "micro_IA40706921_0006": ("CBOT", "1985", "interest rates, metals, stock indices"),
    "micro_IA40706924_0153": ("CBOT", "1986", "all CBOT"),
    "micro_IA40706927_0287": ("CBOT", "1987", "supplement"),
    "micro_IA40706930_0466": ("CBOT", "1988", "supplement"),
    "micro_IA40706907_0371": ("CME", "1980", "all CME"),
    "micro_IA40706911_0202": ("CME", "1982", "all CME"),
    "micro_IA40706918_0013": ("CME", "1983", "all CME"),
    "micro_IA40706921_0008": ("CME", "1984", "all CME"),
    "micro_IA40706924_0154": ("CME", "1985-1986", "all CME"),
    "micro_IA40706927_0288": ("CME", "1987", "all CME"),
    "micro_IA40706901_0293": ("COMEX", "1979", "metals"),
    "micro_IA40706904_0314": ("COMEX", "1980", "metals"),
    "micro_IA40706907_0374": ("COMEX", "1981", "metals"),
    "micro_IA40706915_0078": ("COMEX", "1982-1983", "metals"),
    "micro_IA40706918_0017": ("COMEX", "1984", "metals"),
    "micro_IA40706924_0157": ("COMEX", "1985-1986", "metals"),
    "micro_IA40706901_0334": ("NYMEX", "1978-1979", "platinum, palladium, heating oil, potatoes"),
    "micro_IA40706904_0304": ("KCBT", "1980", "wheat"),
    "micro_IA40706907_0361": ("KCBT", "1981", "wheat"),
    "micro_IA40706918_0004": ("KCBT", "1984", "wheat"),
    "micro_IA40706921_0003": ("KCBT", "1985", "wheat"),
    "micro_IA40706924_0147": ("KCBT", "1986", "wheat"),
    "micro_IA40706927_0282": ("KCBT", "1987", "wheat"),
    "micro_IA40706937_0358": ("KCBT", "1990", "wheat"),
    "micro_IA40706944_0266": ("KCBT", "1992", "wheat"),
    "micro_IA40706930_0468": ("CSCE", "1988", "coffee, sugar, cocoa"),
    "micro_IA40706937_0360": ("CSCE", "1989", "coffee, sugar, cocoa"),
    "micro_IA40706941_0010": ("CSCE", "1990-1991", "coffee, sugar, cocoa"),
    "micro_IA40706944_0272": ("CSCE", "1992", "coffee, sugar, cocoa"),
    "micro_IA40706947_0352": ("CSCE", "1993", "coffee, sugar, cocoa"),
    "micro_IA40706951_0099": ("CSCE", "1994", "coffee, sugar, cocoa"),
}
# a "price-table heading" line: market name plus a price word, e.g. "LIVE CATTLE FUTURES PRICES",
# "DAILY SETTLEMENT PRICES OF ...", "Soybean Oil Futures Prices" (OCR misspellings are not caught: a lower bound)
KW = {"SOYMEAL": r"soybean meal", "SOYOIL": r"soybean oil", "OATIES": r"\boats\b", "WHEAT": r"\bwheat\b",
      "CORN": r"\bcorn\b", "SOYBEAN": r"\bsoybeans?\b(?! (meal|oil))", "LIVECOW": r"live cattle",
      "FEEDCOW": r"feeder cattle", "LEANHOG": r"(live|lean) hogs?", "GOLD": r"\bgold\b", "SILVER": r"\bsilver\b",
      "COPPER": r"\bcopper\b", "PLAT": r"platinum", "PALLAD": r"palladium", "HEATOIL": r"heating oi",
      "COCOA": r"\bcocoa\b", "SUGAR11": r"\bsugar\b", "COFFEE": r"\bcoffee\b"}
PRICE_HEAD = re.compile(r"(?i)(futures|settlement|closing|daily).{0,25}price|price.{0,25}(futures|settle|close)")
ROW = re.compile(r"^\s*\d{1,2}\s+(\S+\s+){5,}")  # a day-of-month number then >= 5 tokens: a daily table row


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def eia():
    out = {}
    d = os.path.join(CACHE, "eia")
    for f in sorted(os.listdir(d)):
        if not f.endswith(".xls"):
            continue
        p = os.path.join(d, f)
        b = xlrd.open_workbook(p)
        s = b.sheet_by_name("Data 1")
        c = b.sheet_by_name("Contents")
        src = [str(c.cell_value(r, 1)).strip() for r in range(c.nrows) if str(c.cell_value(r, 0)).startswith("Source")]
        dates = [xlrd.xldate.xldate_as_datetime(s.cell_value(r, 0), b.datemode).date()
                 for r in range(3, s.nrows)
                 if isinstance(s.cell_value(r, 0), float) and s.cell_value(r, 1) not in ("", None)]
        pre = [x for x in dates if x.year < 2003]
        yrs = {}
        for x in pre:
            yrs[x.year] = yrs.get(x.year, 0) + 1
        inner = [v for k, v in yrs.items() if dates[0].year < k]
        out[f] = {"sha256": sha(p), "series_id": s.cell_value(1, 1), "name": s.cell_value(2, 1),
                  "workbook_source_line": src, "first": str(dates[0]), "last": str(dates[-1]), "n": len(dates),
                  "n_pre2003": len(pre), "pre2003_obs_per_full_year_min": min(inner, default=None),
                  "pre2003_obs_per_full_year_max": max(inner, default=None),
                  "duplicate_dates": len(dates) - len(set(dates)), "sorted": dates == sorted(dates),
                  "max_gap_days_pre2003": max(((b2 - a).days for a, b2 in zip(pre, pre[1:])), default=None)}
    return out


def ia():
    out = {}
    d = os.path.join(CACHE, "ia")
    for f, (ex, yr, scope) in IA.items():
        p = os.path.join(d, f + "_djvu.txt")
        t = open(p, errors="ignore").read()
        meta = json.load(open(os.path.join(d, f + "_meta.json")))["metadata"]
        lines = t.splitlines()
        heads = [ln.lower() for ln in lines if PRICE_HEAD.search(ln)]
        hits = {k: sum(1 for ln in heads if re.search(v, ln)) for k, v in KW.items()}
        out[f] = {"exchange": ex, "edition": yr, "scope": scope, "title": meta.get("title"),
                  "pages": int(meta.get("imagecount") or 0), "access_restricted": meta.get("access-restricted-item"),
                  "collection": meta.get("collection"), "ocr_text_sha256": sha(p), "ocr_text_bytes": os.path.getsize(p),
                  "price_heading_lines": len(heads), "daily_row_like_lines": sum(1 for ln in lines if ROW.match(ln)),
                  "price_heading_hits_by_market": {k: v for k, v in hits.items() if v},
                  "url": f"https://archive.org/details/{f}"}
    return out


def cot():
    p = os.path.join(CACHE, "misc", "cot.zip")
    z = zipfile.ZipFile(p)
    name = z.namelist()[0]
    r = csv.reader(io.TextIOWrapper(z.open(name), encoding="latin-1"))
    h = next(r)
    i = h.index("As of Date in Form YYYY-MM-DD")
    ds = [row[i] for row in r]
    return {"sha256": sha(p), "file": name, "columns": len(h),
            "price_or_settlement_columns": [c for c in h if re.search(r"(?i)price|settl", c)],
            "first": min(ds), "last": max(ds), "rows": len(ds)}


def notes():
    p = os.path.join(CACHE, "eia_pet_notes.htm")
    t = open(p, errors="ignore").read()
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))
    m = re.search(r"The futures prices shown are.*?product listed\.", t)
    c1 = re.search(r"Contract 1 A futures contract.*?Contract 2-4 Represent the successive delivery months following "
                   r"Contract 1\.", t)
    return {"sha256": sha(p), "url": "https://www.eia.gov/dnav/pet/TblDefs/pet_pri_fut_tbldef2.asp",
            "explanatory_note": m.group(0) if m else None, "contract_definition": c1.group(0) if c1 else None}


if __name__ == "__main__":
    json.dump({"eia": eia(), "eia_notes": notes(), "internet_archive": ia(), "cftc_cot": cot()},
              sys.stdout, indent=1, default=str)
