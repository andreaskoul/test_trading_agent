"""Fetch the daily data for PROTOCOL_daily.md into data/raw/daily/.

    python scripts/daily/fetch_daily_data.py

Raw series only, stamped with their own date. Availability lags are
applied in build_daily_features.py so they are visible in one place.
"""

import io
import os
import urllib.request
import zipfile

import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "raw", "daily")
os.makedirs(OUT, exist_ok=True)
START, END = "2003-01-01", "2026-09-26"

for sym, name in (("GC=F", "gc"), ("DX-Y.NYB", "dxy"), ("GLD", "gld")):
    d = yf.download(sym, start=START, end=END, interval="1d", progress=False, auto_adjust=False, threads=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
    d.to_parquet(os.path.join(OUT, f"{name}.parquet"))
    print(name, len(d), d.index.min().date(), d.index.max().date())

for fid in ("DFII10", "T10YIE", "VIXCLS"):
    with urllib.request.urlopen(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fid}", timeout=60) as r:
        s = pd.read_csv(io.BytesIO(r.read()), na_values=".")
    s.columns = ["date", "value"]
    s = s.assign(date=pd.to_datetime(s.date)).set_index("date")["value"].dropna()
    s = s[(s.index >= START) & (s.index < END)]
    s.to_frame(fid.lower()).to_parquet(os.path.join(OUT, f"{fid.lower()}.parquet"))
    print(fid, len(s), s.index.min().date(), s.index.max().date())

# CFTC disaggregated futures-only, gold (COMEX) = 088691
files = ["fut_disagg_txt_hist_2006_2016.zip"] + [f"fut_disagg_txt_{y}.zip" for y in range(2017, 2027)]
frames = []
for f in files:
    req = urllib.request.Request(f"https://www.cftc.gov/files/dea/history/{f}",
                                 headers={"User-Agent": "Mozilla/5.0 (research script)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    d = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
    d = d[d["CFTC_Contract_Market_Code"].astype(str).str.strip() == "088691"]
    frames.append(d[["Report_Date_as_YYYY-MM-DD", "Open_Interest_All",
                     "M_Money_Positions_Long_All", "M_Money_Positions_Short_All"]])
cot = pd.concat(frames)
cot.columns = ["report_date", "oi", "mm_long", "mm_short"]
cot["report_date"] = pd.to_datetime(cot["report_date"])
cot = cot.drop_duplicates("report_date").sort_values("report_date").set_index("report_date")
cot.to_parquet(os.path.join(OUT, "cot_gold.parquet"))
print("COT", len(cot), cot.index.min().date(), cot.index.max().date(),
      "weekdays:", cot.index.dayofweek.value_counts().to_dict())
