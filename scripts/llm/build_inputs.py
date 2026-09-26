"""Build the weekly LLM inputs as of the latest Wednesday close (PROTOCOL_llm.md).

    python scripts/llm/build_inputs.py [--asof YYYY-MM-DD]
    -> reports/llm_forward/inputs/<asof>_{stocks,fx}.json

Signal definitions are copied from scripts/xs/{stock,fx}_ladder.py and must
stay identical to them; the frozen ridge coefficients come from
artefacts/llm/ridge_{stocks,fx}.json.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "reports", "llm_forward", "inputs")
os.makedirs(OUT, exist_ok=True)
MEMBERSHIP_URL = ("https://raw.githubusercontent.com/fja05680/sp500/master/"
                  "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv")
FX = {"EUR": ("EURUSD=X", True, "EZ"), "JPY": ("JPY=X", False, "JP"), "GBP": ("GBPUSD=X", True, "GB"),
      "CHF": ("CHF=X", False, "CH"), "AUD": ("AUDUSD=X", True, "AU"), "NZD": ("NZDUSD=X", True, "NZ"),
      "CAD": ("CAD=X", False, "CA"), "SEK": ("SEK=X", False, "SE"), "NOK": ("NOK=X", False, "NO"),
      "MXN": ("MXN=X", False, "MX"), "ZAR": ("ZAR=X", False, "ZA"), "PLN": ("PLN=X", False, "PL"),
      "HUF": ("HUF=X", False, "HU"), "CZK": ("CZK=X", False, "CZ"), "KRW": ("KRW=X", False, "KR"),
      "ILS": ("ILS=X", False, "IL"), "CLP": ("CLP=X", False, "CL")}

ap = argparse.ArgumentParser()
ap.add_argument("--asof", default=None, help="a Wednesday; default = latest Wednesday with a close")
ap.add_argument("--max-news", type=int, default=5)
args = ap.parse_args()

today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
asof = pd.Timestamp(args.asof) if args.asof else today - pd.Timedelta(days=(today.dayofweek - 2) % 7)
assert asof.dayofweek == 2, "asof must be a Wednesday"


def xs_z(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std()


def ridge(Z: pd.DataFrame, spec: dict) -> pd.Series:
    return Z[spec["features"]].to_numpy() @ np.asarray(spec["coef"]) + spec["intercept"]


# ------------------------------------------------------------------ stocks
try:
    with urllib.request.urlopen(MEMBERSHIP_URL, timeout=60) as r:
        mem = pd.read_csv(io.BytesIO(r.read()), parse_dates=["date"])
    mem_src = "fja05680/sp500 (live)"
except Exception:
    mem = pd.read_csv(os.path.join(ROOT, "data/raw/stocks/sp500_membership.csv"), parse_dates=["date"])
    mem_src = "pinned copy"
row = mem[mem.date <= asof].iloc[-1]
members = sorted(row.tickers.split(","))
ymap = {t: t.replace(".", "-") for t in members}
px = yf.download(list(ymap.values()), start=asof - pd.Timedelta(days=420), end=asof + pd.Timedelta(days=1),
                 interval="1d", progress=False, auto_adjust=True, threads=True)["Close"]
px = px.rename(columns={v: k for k, v in ymap.items()})
px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
px = px[px.index <= asof]
days = pd.date_range(px.index.min(), asof, freq="D")
d = px.reindex(days).ffill(limit=3)
wed = d[d.index.dayofweek == 2]
assert wed.index[-1] == asof, f"no Wednesday row for {asof.date()}"
lw = np.log(wed)
sig = pd.DataFrame({
    "mom12_1": lw.shift(4).iloc[-1] - lw.shift(52).iloc[-1],
    "rev1m": -(lw.iloc[-1] - lw.shift(4).iloc[-1]),
    "rev1w": -(lw.iloc[-1] - lw.shift(1).iloc[-1]),
    "lowvol": -np.log(px).diff().rolling(60, min_periods=50).std().reindex(days).ffill(limit=3).loc[asof],
    "high52": wed.iloc[-1] / px.rolling(252, min_periods=200).max().reindex(days).ffill(limit=3).loc[asof],
}).dropna()
Z = sig.apply(xs_z)
spec_s = json.load(open(os.path.join(ROOT, "artefacts/llm/ridge_stocks.json")))
Z["ridge_forecast_bp"] = ridge(Z, spec_s) * 1e4
Z["ridge_rank"] = Z["ridge_forecast_bp"].rank(ascending=False).astype(int)


def news(t):
    try:
        items = yf.Ticker(ymap[t]).news or []
    except Exception:
        return t, []
    out = []
    for it in items:
        c = it.get("content", it)
        ts = pd.Timestamp(c.get("pubDate") or c.get("displayTime") or 0).tz_localize(None) \
            if isinstance(c.get("pubDate"), str) else None
        if ts is None or not (asof - pd.Timedelta(days=7) <= ts.normalize() <= asof):
            continue                                   # only news published by the as-of date
        out.append({"date": str(ts.date()), "publisher": (c.get("provider") or {}).get("displayName"),
                    "title": c.get("title"), "summary": (c.get("summary") or "")[:300]})
    return t, sorted(out, key=lambda x: x["date"], reverse=True)[: args.max_news]


with ThreadPoolExecutor(8) as ex:
    headlines = dict(ex.map(news, Z.index))
stocks = {"asof": str(asof.date()), "universe": "S&P 500 members as of asof", "membership_source": mem_src,
          "n": int(len(Z)), "ridge_spec": spec_s, "news_window_days": 7,
          "rows": [{"ticker": t, **{k: round(float(v), 3) for k, v in Z.loc[t].items()},
                    "headlines": headlines.get(t, [])} for t in Z.index]}
json.dump(stocks, open(os.path.join(OUT, f"{asof.date()}_stocks.json"), "w"), indent=1)
print("stocks", len(Z), "names;", sum(bool(h) for h in headlines.values()), "with news")

# ------------------------------------------------------------------ FX
raw = yf.download([v[0] for v in FX.values()], start=asof - pd.Timedelta(days=6 * 365), end=asof + pd.Timedelta(days=1),
                  interval="1d", progress=False, auto_adjust=False, threads=True)["Close"]
raw.index = pd.to_datetime(raw.index).tz_localize(None).normalize()
spot = pd.DataFrame({c: (raw[t] if usd else 1 / raw[t]) for c, (t, usd, _) in FX.items()})
spot = spot[spot.index <= asof]


def fred(fid):
    with urllib.request.urlopen(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fid}", timeout=60) as r:
        s = pd.read_csv(io.BytesIO(r.read()), na_values=".")
    s.columns = ["date", "v"]
    return s.assign(date=pd.to_datetime(s.date)).set_index("date")["v"].dropna() / 100


rates = pd.DataFrame({c: fred(f"IR3TIB01{cc}M156N") for c, (_, _, cc) in FX.items()})
rates["USD"] = fred("IR3TIB01USM156N")
mr = rates.reindex(pd.date_range(rates.index.min(), asof + pd.DateOffset(months=3), freq="MS")).ffill()
dnow = mr[list(FX)].sub(mr["USD"], axis=0)
dsig = dnow.copy(); dsig.index = dsig.index + pd.DateOffset(months=2)
fdays = pd.date_range(spot.index.min(), asof, freq="D")
fw = spot.reindex(fdays).ffill(limit=3)
fw = fw[fw.index.dayofweek == 2]
acc = dnow.reindex(fw.index, method="ffill") / 52
xw = np.log(fw).diff() + acc
fsig = pd.DataFrame({
    "carry": dsig.reindex(fw.index, method="ffill").iloc[-1],
    "mom12": xw.shift(4).rolling(48, min_periods=40).sum().iloc[-1],
    "mom3": xw.rolling(13, min_periods=11).sum().iloc[-1],
    "mom1": xw.rolling(4, min_periods=4).sum().iloc[-1],
    "rev1w": -xw.iloc[-1],
    "value": -(np.log(fw).iloc[-1] - np.log(fw.shift(260)).iloc[-1]),
}).dropna()
FZ = fsig.apply(xs_z)
spec_f = json.load(open(os.path.join(ROOT, "artefacts/llm/ridge_fx.json")))
FZ["ridge_forecast_bp"] = ridge(FZ, spec_f) * 1e4
FZ["ridge_rank"] = FZ["ridge_forecast_bp"].rank(ascending=False).astype(int)
FZ["carry_raw_pct"] = fsig["carry"] * 100
fx = {"asof": str(asof.date()), "universe": "17 currencies vs USD (Protocol 3)", "n": int(len(FZ)),
      "ridge_spec": spec_f, "note": "spot from Yahoo (H.10 is published with a lag)",
      "rows": [{"ccy": c, **{k: round(float(v), 3) for k, v in FZ.loc[c].items()}} for c in FZ.index]}
json.dump(fx, open(os.path.join(OUT, f"{asof.date()}_fx.json"), "w"), indent=1)
print("fx", len(FZ), "currencies; asof", asof.date())
