"""Desk 1 · Screen (PROTOCOL_fund.md).

Whole S&P 500: Protocol 4 signal z-scores, frozen ridge forecast, 60-day beta
to SPY, GICS sector, and attention (Finnhub article count over the 7 days to
the cutoff). -> fund_state/<mode>/<asof>/screen.json

    FUND_ASOF=2026-09-23 python fund/screen.py
"""

import io
import json
import os
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf

from common import MODE, ROOT, STATE, asof_from_env, require, save

require("FINNHUB_API_KEY")
asof = asof_from_env()
MEMBERSHIP_URL = ("https://raw.githubusercontent.com/fja05680/sp500/master/"
                  "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv")
CURRENT_URL = "https://raw.githubusercontent.com/fja05680/sp500/master/sp500.csv"

try:
    with urllib.request.urlopen(MEMBERSHIP_URL, timeout=60) as r:
        mem = pd.read_csv(io.BytesIO(r.read()), parse_dates=["date"])
except Exception:
    mem = pd.read_csv(os.path.join(ROOT, "data/raw/stocks/sp500_membership.csv"), parse_dates=["date"])
members = sorted(mem[mem.date <= asof].iloc[-1].tickers.split(","))
try:
    with urllib.request.urlopen(CURRENT_URL, timeout=60) as r:
        meta = pd.read_csv(io.BytesIO(r.read()))
except Exception:
    meta = pd.read_csv(os.path.join(ROOT, "data/raw/stocks/sp500_current.csv"))
meta = meta.set_index("Symbol")[["Security", "GICS Sector", "GICS Sub-Industry"]]

# ---- prices, signals (definitions identical to scripts/xs/stock_ladder.py on the legacy-gold-agent branch)
ymap = {t: t.replace(".", "-") for t in members}
px = yf.download(list(ymap.values()) + ["SPY"], start=asof - pd.Timedelta(days=420), end=asof + pd.Timedelta(days=1),
                 interval="1d", progress=False, auto_adjust=True, threads=True)["Close"]
px = px.rename(columns={v: k for k, v in ymap.items()})
px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
px = px[px.index <= asof]
days = pd.date_range(px.index.min(), asof, freq="D")
d = px.reindex(days).ffill(limit=3)
wed = d[d.index.dayofweek == 2]
assert wed.index[-1] == asof, f"no Wednesday close for {asof.date()}"
lw = np.log(wed[members])
lr = np.log(px).diff()
sig = pd.DataFrame({
    "mom12_1": lw.shift(4).iloc[-1] - lw.shift(52).iloc[-1],
    "rev1m": -(lw.iloc[-1] - lw.shift(4).iloc[-1]),
    "rev1w": -(lw.iloc[-1] - lw.shift(1).iloc[-1]),
    "lowvol": -lr[members].rolling(60, min_periods=50).std().reindex(days).ffill(limit=3).loc[asof],
    "high52": wed[members].iloc[-1] / px[members].rolling(252, min_periods=200).max().reindex(days).ffill(limit=3).loc[asof],
}).dropna()
Z = (sig - sig.mean()) / sig.std()
spec = json.load(open(os.path.join(ROOT, "artefacts/llm/ridge_stocks.json")))
Z["ridge_bp"] = Z[spec["features"]].to_numpy() @ np.asarray(spec["coef"]) * 1e4 + spec["intercept"] * 1e4
Z["ridge_rank"] = Z["ridge_bp"].rank(ascending=False).astype(int)
last60 = lr.loc[:asof].tail(60)
Z["beta60"] = last60[Z.index].apply(lambda s: s.cov(last60["SPY"]) / last60["SPY"].var())
# Hedge beta (Amendment 4): Welch (2022) slope-winsorised beta over 252 days (each daily stock
# return clipped to lie between -2x and 4x the market's that day), shrunk one third toward 1.
# The 60-day OLS beta has a standard error of ~0.2 and was unstable in 2026 (median 0.31).
last252 = lr.loc[:asof].tail(252)
rm = last252["SPY"]
lo_, hi_ = np.minimum(-2 * rm, 4 * rm), np.maximum(-2 * rm, 4 * rm)
wins = last252[Z.index].clip(lower=lo_, upper=hi_, axis=0)
bw = wins.apply(lambda s: s.cov(rm) / rm[s.notna()].var())
Z["beta252w"] = bw
Z["beta_hedge"] = (2 / 3) * bw.fillna(1.0) + 1 / 3
Z["ret_1w_pct"] = (np.exp(-sig["rev1w"]) - 1) * 100
Z["ret_1m_pct"] = (np.exp(-sig["rev1m"]) - 1) * 100
Z["ret_12_1_pct"] = (np.exp(sig["mom12_1"]) - 1) * 100
Z["pct_below_52w_high"] = (1 - sig["high52"]) * 100
Z["vol60_ann_pct"] = -sig["lowvol"] * np.sqrt(252) * 100
Z = Z.join(meta, how="left")

# ---- attention: Finnhub article count, 7 days to the cutoff (one call per firm;
# the per-call cap is undocumented, so very high counts may be censored: ranks survive)
lo, hi = (asof - pd.Timedelta(days=6)).date(), asof.date()
counts, heads = {}, {}
for i, t in enumerate(Z.index):
    url = (f"https://finnhub.io/api/v1/company-news?symbol={ymap[t]}&from={lo}&to={hi}"
           f"&token={os.environ['FINNHUB_API_KEY']}")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                items = json.load(r)
            counts[t] = len(items)
            heads[t] = [x.get("headline") for x in sorted(items, key=lambda x: x["datetime"])[-2:]]
            break
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise SystemExit("Finnhub key refused")
            time.sleep(15 * (attempt + 1))
        except Exception:
            time.sleep(3)
    time.sleep(1.05)                        # free tier: 60 calls / minute
Z["news_7d"] = pd.Series(counts, dtype=float).reindex(Z.index)
la = np.log1p(Z["news_7d"])
Z["attention_z"] = (la - la.mean()) / la.std()
os.makedirs(os.path.join(STATE, MODE), exist_ok=True)
hist_p = os.path.join(STATE, MODE, "attention_history.parquet")
hist = pd.read_parquet(hist_p) if os.path.exists(hist_p) else pd.DataFrame(columns=["asof", "ticker", "attention_z"])
past = hist[pd.to_datetime(hist["asof"]) < asof].groupby("ticker").attention_z.agg(["mean", "count"])
own = past["mean"].where(past["count"] >= 4)
Z["attention_shock"] = (Z["attention_z"] - own.reindex(Z.index).fillna(0.0)).astype(float)
new_hist = pd.concat([hist[pd.to_datetime(hist["asof"]) != asof],
                      pd.DataFrame({"asof": str(asof.date()), "ticker": Z.index, "attention_z": Z["attention_z"].to_numpy()})])
new_hist.to_parquet(hist_p)
Z["latest_headlines"] = pd.Series(heads).reindex(Z.index)

# ---- earnings inside the holding period (Thursday close -> next Thursday close), Amendment 3:
# after the close on entry day, any day in between, or before the open on exit day
t0, t1 = asof + pd.Timedelta(days=1), asof + pd.Timedelta(days=8)
earn = {}
try:
    with urllib.request.urlopen(f"https://finnhub.io/api/v1/calendar/earnings?from={t0.date()}&to={t1.date()}"
                                f"&token={os.environ['FINNHUB_API_KEY']}", timeout=60) as r:
        for e in json.load(r).get("earningsCalendar", []):
            d, h = pd.Timestamp(e["date"]), (e.get("hour") or "").lower()
            if (t0 < d < t1) or (d == t0 and h != "bmo") or (d == t1 and h not in ("amc",)):
                earn[e["symbol"].replace("-", ".")] = f"{e['date']} {h or 'time n/a'}"
except Exception as exc:
    print(f"screen: earnings calendar unavailable ({exc!r})")
Z["earnings_in_holding_week"] = pd.Series(earn, dtype=object).reindex(Z.index).fillna("none")
print(f"screen: {int((Z['earnings_in_holding_week'] != 'none').sum())} members report earnings in the holding week")

save(asof, "screen.json", {"asof": str(asof.date()), "n": int(len(Z)), "news_window": [str(lo), str(hi)],
                           "ridge_spec": spec, "rows": json.loads(Z.reset_index(names="ticker").to_json(orient="records"))})
print(f"screen {asof.date()}: {len(Z)} members, attention for {Z.news_7d.notna().sum()}, "
      f"median beta60 {Z.beta60.median():.2f}, hedge beta {Z.beta_hedge.median():.2f}")
