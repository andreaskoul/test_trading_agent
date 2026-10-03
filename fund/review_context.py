"""Amendment 6 · Review context logger (fund/AMENDMENT6_PLAN.md, part 7). No LLM, no orders.

Runs after the daily review has traded. For each held name it records what a macro-aware review
would have seen, so a later protocol can test whether it would have helped:
  * move since entry, the same move net of the GICS sector ETF, and the sector ETF's move today;
  * scheduled major US releases between the previous review and today; AI-GPR spike days in the last week;
  * the name's new SEC 8-K filings since the previous review; its neighbours (neighbours.json of the week).
-> fund_state/<mode>/<asof>/review_context/<day>.json (outside reviews/, which review.py and score.py read)

    python fund/review_context.py
"""

import glob
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

from a6_common import MAJOR, SECTOR_ETF, filings, latest, load_context
from common import MODE, STATE

now = datetime.now(timezone.utc)
today = str(now.astimezone(ZoneInfo("America/New_York")).date())
base = os.path.join(STATE, MODE)
execs = sorted(p for p in glob.glob(os.path.join(base, "20*", "execution.json")) if json.load(open(p)).get("status") == "submitted")
if not execs:
    raise SystemExit(print("review context: no executed week") or 0)
wd = os.path.dirname(execs[-1])
ex = json.load(open(execs[-1]))
rp = os.path.join(wd, "reviews", f"{today}.json")
if not os.path.exists(rp):
    raise SystemExit(print(f"review context: no review for {today}") or 0)
rv = json.load(open(rp))
since = pd.Timestamp(rv["news_since"]).tz_convert(None) if pd.Timestamp(rv["news_since"]).tzinfo else pd.Timestamp(rv["news_since"])
held = [t for t in rv.get("weights_before", {}) if t != "SPY"]
S = pd.DataFrame(json.load(open(os.path.join(wd, "screen.json")))["rows"]).set_index("ticker")
nbp = os.path.join(wd, "neighbours.json")
nb = json.load(open(nbp))["names"] if os.path.exists(nbp) else {}
sector = {t: S["GICS Sector"].get(t) for t in held}
etfs = sorted({SECTOR_ETF[s] for s in sector.values() if s in SECTOR_ETF})
px = yf.download([t.replace(".", "-") for t in held] + etfs, start=pd.Timestamp(ex["exec_day"]) - pd.Timedelta(days=5),
                 end=pd.Timestamp(today) + pd.Timedelta(days=1), progress=False, auto_adjust=True)["Close"]
px = px.rename(columns=lambda c: c.replace("-", "."))
px.index = pd.to_datetime(px.index).tz_localize(None)
e0 = px.index[px.index <= pd.Timestamp(ex["exec_day"])]
mv = lambda c: float(px[c].dropna().iloc[-1] / px[c].loc[e0[-1]] - 1) if c in px and len(e0) and px[c].notna().any() else np.nan
day = lambda c: float(px[c].dropna().iloc[-1] / px[c].dropna().iloc[-2] - 1) if c in px and px[c].notna().sum() >= 2 else np.nan

C = load_context(since - pd.Timedelta(days=8), pd.Timestamp(now).tz_convert(None))
rel = sorted({(p["date"], p["release"]) for p in latest(C, "fred")["p"]
              if str(since.date()) <= p["date"] <= today and MAJOR.search(p["release"] or "")})
g = latest(C, "gpr")
g = g[g["key"].str.startswith("ai_gpr_data_daily.csv|")]
spikes = []
if len(g):
    s = pd.Series({pd.Timestamp(p["Date"]): p.get("GPR_AI") for p in g["p"]}, dtype=float).sort_index().dropna()
    past = s[(s.index > s.index[-1] - pd.Timedelta(days=372)) & (s.index <= s.index[-1] - pd.Timedelta(days=7))]
    spikes = [str(d.date()) for d, v in s.iloc[-7:].items() if v > past.mean() + 2 * past.std()]
names = {}
for t in held:
    etf = SECTOR_ETF.get(sector[t])
    names[t] = {"weight": rv["weights_before"][t], "final": rv["decisions"].get(t, {}).get("final"),
                "move_since_entry": mv(t), "sector_etf": etf, "sector_move_since_entry": mv(etf) if etf else np.nan,
                "move_net_of_sector": mv(t) - mv(etf) if etf else np.nan, "sector_move_today": day(etf) if etf else np.nan,
                "new_8k": filings(C, t, since, pd.Timestamp(now).tz_convert(None)),
                "neighbours": [x["ticker"] for x in (nb.get(t) or {}).get("neighbours", [])]}
os.makedirs(os.path.join(wd, "review_context"), exist_ok=True)
json.dump({"asof": os.path.basename(wd), "day": today, "since": str(since), "releases_in_window": rel, "gpr_spike_days": spikes,
           "names": names}, open(os.path.join(wd, "review_context", f"{today}.json"), "w"), indent=1, default=str)
print(f"review context {today}: {len(names)} held names; releases {rel}; GPR spikes {spikes}; "
      f"{sum(bool(v['new_8k']) for v in names.values())} names with new 8-Ks")
