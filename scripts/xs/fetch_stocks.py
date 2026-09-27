"""Prices for every ticker that was an S&P 500 member at any point since 2003,
plus Fama–French daily factors. PROTOCOL_stocks.md.

    python scripts/xs/fetch_stocks.py   # -> data/raw/stocks/{prices_adj,ff_daily,yahoo_coverage}.*
"""

import io
import os
import time
import urllib.request
import zipfile

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "raw", "stocks")

mem = pd.read_csv(os.path.join(OUT, "sp500_membership.csv"), parse_dates=["date"])
mem = mem[mem.date >= "2003-01-01"]
tickers = sorted({t for s in mem.tickers for t in s.split(",")})
ymap = {t: t.replace(".", "-") for t in tickers}

frames, missing = [], []
batches = [tickers[i:i + 80] for i in range(0, len(tickers), 80)]
for k, b in enumerate(batches):
    for attempt in range(3):
        try:
            d = yf.download([ymap[t] for t in b], start="2003-01-01", end="2026-09-26", interval="1d",
                            progress=False, auto_adjust=True, threads=True)["Close"]
            break
        except Exception as exc:          # transient Yahoo errors
            print("retry", k, exc); time.sleep(5)
    if isinstance(d, pd.Series):
        d = d.to_frame(ymap[b[0]])
    d = d.rename(columns={v: t for t, v in ymap.items()})
    frames.append(d)
    print(f"batch {k + 1}/{len(batches)}: {d.notna().any().sum()}/{len(b)} with data", flush=True)
px = pd.concat(frames, axis=1)
px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
px = px.loc[:, px.notna().any()].astype("float32")
px.to_parquet(os.path.join(OUT, "prices_adj.parquet"))

cov = pd.DataFrame({"ticker": tickers})
cov["on_yahoo"] = cov.ticker.isin(px.columns)
cov["yahoo_first"] = cov.ticker.map(lambda t: px[t].first_valid_index() if t in px else pd.NaT)
cov["yahoo_last"] = cov.ticker.map(lambda t: px[t].last_valid_index() if t in px else pd.NaT)
cov.to_csv(os.path.join(OUT, "yahoo_coverage.csv"), index=False)
print("tickers", len(tickers), "on yahoo", int(cov.on_yahoo.sum()))

# Fama-French 5 factors + momentum, daily, in decimal
ff = []
for f in ("F-F_Research_Data_5_Factors_2x3_daily_CSV.zip", "F-F_Momentum_Factor_daily_CSV.zip"):
    with urllib.request.urlopen(f"https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{f}", timeout=120) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    txt = z.open(z.namelist()[0]).read().decode("latin-1").splitlines()
    start = next(i for i, l in enumerate(txt) if l.strip().startswith(",") or l.lower().startswith(",mkt") or ",Mom" in l or ",Mkt-RF" in l)
    rows = [l.split(",") for l in txt[start + 1:] if l.strip() and l.split(",")[0].strip().isdigit()]
    hdr = [h.strip() for h in txt[start].split(",")]
    df = pd.DataFrame(rows, columns=hdr)
    df.index = pd.to_datetime(df.iloc[:, 0].str.strip(), format="%Y%m%d")
    ff.append(df.iloc[:, 1:].astype(float) / 100)
ff = pd.concat(ff, axis=1).dropna()
ff.to_parquet(os.path.join(OUT, "ff_daily.parquet"))
print("FF", ff.shape, ff.index.min().date(), ff.index.max().date(), list(ff.columns))
