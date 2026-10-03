"""Shadow logger · review context (PROTOCOL_fund.md, Amendment 6). No LLM, no orders.
-> fund_state/<mode>/<asof>/reviews/context/<day>.json

After each daily review, for every held stock: the move since entry, the same move net of its SPDR
sector ETF, the sector ETF's move today, FRED releases today and in the next two days, whether
geopolitical risk (AI-GPR daily) is above the 90th percentile of its last year, the stock's 8-K
filings since the previous review, and its neighbours' headlines since then. It records what a
macro-aware review would have seen, so a later protocol has evidence; nothing reads it today.
"""

import glob
import json
import os
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

import broker
import infoflow
from common import MODE, STATE, require

require("HF_TOKEN")
ETF = {"Information Technology": "XLK", "Financials": "XLF", "Health Care": "XLV", "Consumer Discretionary": "XLY",
       "Consumer Staples": "XLP", "Energy": "XLE", "Industrials": "XLI", "Materials": "XLB", "Utilities": "XLU",
       "Real Estate": "XLRE", "Communication Services": "XLC"}
now = datetime.now(timezone.utc)
today = now.astimezone(broker.ET).date()
base = os.path.join(STATE, MODE)
execs = sorted(p for p in glob.glob(os.path.join(base, "20*", "execution.json")) if json.load(open(p)).get("status") == "submitted")
if not execs:
    raise SystemExit(print("review context: nothing held") or 0)
wd = os.path.dirname(execs[-1])
ex = json.load(open(execs[-1]))
S = pd.DataFrame(json.load(open(os.path.join(wd, "screen.json")))["rows"]).set_index("ticker")
nbh = json.load(open(os.path.join(wd, "neighbours.json")))["names"] if os.path.exists(os.path.join(wd, "neighbours.json")) else {}
prior = sorted(p for p in glob.glob(os.path.join(wd, "reviews", "context", "*.json")) if os.path.basename(p) < f"{today}.json")
since = pd.Timestamp(json.load(open(prior[-1]))["at"]) if prior else pd.Timestamp(ex["submitted_at_et"]).tz_convert("UTC")

s_, pos = broker.api("GET", "/v2/positions")
held = {p["symbol"]: p for p in pos or [] if p["symbol"] != "SPY"}
etfs = sorted({ETF[S.loc[t, "GICS Sector"]] for t in held if t in S.index and S.loc[t, "GICS Sector"] in ETF})
s_, snap = broker.api("GET", "/v2/stocks/snapshots?feed=iex&symbols=" + ",".join(etfs), base=broker.DATA) if etfs else (200, {})
day_move = {k: ((v.get("dailyBar") or {}).get("c") or 0) / ((v.get("prevDailyBar") or {}).get("c") or float("nan")) - 1
            for k, v in (snap or {}).items()}
ent = pd.Timestamp(ex["exec_day"])
px = yf.download(etfs, start=ent, end=ent + pd.Timedelta(days=1), progress=False, auto_adjust=False)["Close"] if etfs else pd.DataFrame()
etf_entry = (px.iloc[-1].to_dict() if isinstance(px, pd.DataFrame) else {etfs[0]: float(px.iloc[-1])}) if len(px) else {}

C = infoflow.context(now)
fred = sorted({(p["date"], p["release"]) for p in C[C["source"] == "fred"]["payload"]
               if str(today) <= p["date"] <= str((pd.Timestamp(today) + pd.offsets.BDay(2)).date())})
G = pd.DataFrame([p for k, p in zip(C["key"], C["payload"]) if str(k).startswith("ai_gpr_data_daily.csv|")])
gpr_spike = None
if len(G) and "GPR_AI" in G:
    G["Date"] = pd.to_datetime(G["Date"]); G = G.sort_values("Date")
    y = G[G["Date"] > G["Date"].max() - pd.Timedelta(days=365)]["GPR_AI"].astype(float)
    gpr_spike = {"latest": str(G["Date"].iloc[-1].date()), "value": float(y.iloc[-1]), "p90": float(y.quantile(0.9)),
                 "spike": bool(y.iloc[-1] > y.quantile(0.9))}
E = C[C["source"] == "edgar"].assign(acc=lambda d: pd.to_datetime(d["published_at"], utc=True, errors="coerce"))
E = E[E["acc"] > since]
N = infoflow.news(since, now)
names = {}
for t, p in held.items():
    sec = S.loc[t, "GICS Sector"] if t in S.index else None
    etf = ETF.get(sec)
    since_entry = float(p["current_price"]) / float(p["avg_entry_price"]) - 1
    etf_since = (float((snap or {}).get(etf, {}).get("dailyBar", {}).get("c") or float("nan")) / etf_entry[etf] - 1) if etf in etf_entry else None
    sign = 1 if float(p["qty"]) > 0 else -1
    nbs = [n["ticker"] for n in (nbh.get(t) or {}).get("neighbours", [])]
    nh = N[N["sym"].isin(nbs)].sort_values("published", ascending=False)
    names[t] = {"side": "long" if sign > 0 else "short", "since_entry": since_entry, "sector_etf": etf,
                "sector_since_entry": etf_since, "net_of_sector": since_entry - etf_since if etf_since is not None else None,
                "sector_today": day_move.get(etf),
                "filings": [{"accepted": f"{a:%Y-%m-%d %H:%M}", "form": q["form"], "items": q.get("items")}
                            for a, q in zip(E["acc"], E["payload"]) if q.get("ticker") == t],
                "neighbour_headlines": [f"{pub:%m-%d %H:%M} {s}: {h}" for pub, s, h in zip(nh["published"], nh["sym"], nh["t"])][:10]}
out_d = os.path.join(wd, "reviews", "context")
os.makedirs(out_d, exist_ok=True)
json.dump({"day": str(today), "at": now.isoformat(timespec="seconds"), "since": since.isoformat(), "releases_next_2d": fred,
           "gpr": gpr_spike, "names": names}, open(os.path.join(out_d, f"{today}.json"), "w"), indent=1, default=str)
print(f"review context {today}: {len(names)} names, {len(fred)} releases ahead, GPR spike {gpr_spike and gpr_spike['spike']}, "
      f"{len(E)} new 8-Ks")
