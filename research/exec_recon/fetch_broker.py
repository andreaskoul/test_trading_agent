"""Read-only snapshot of the Alpaca paper account and SIP market data for the execution reconciliation.

    python3 ~/.claude/hooks/with_secrets.py 'python3 research/exec_recon/fetch_broker.py <out_dir> <symbols_file>'

GET requests only (the helper refuses any other method). Nothing is placed, cancelled or changed. Raw answers are
saved as JSON in <out_dir>; only counts are printed. Keys come from ALPACA_API_KEY / ALPACA_SECRET_KEY.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BASE = "https://paper-api.alpaca.markets"           # fund/broker.py: BASE (paper)
DATA = "https://data.alpaca.markets"                # fund/broker.py: DATA
H = {"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"], "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"]}
ET = ZoneInfo("America/New_York")
OUT, SYMS = sys.argv[1], sorted(set(open(sys.argv[2]).read().split()))
os.makedirs(OUT, exist_ok=True)
START = "2026-09-29T00:00:00Z"


def get(base, path):
    """One GET; returns (status, parsed json). Only GET is possible here."""
    for attempt in range(4):
        req = urllib.request.Request(base + path, method="GET", headers=H)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt * 2); continue
            try:
                return e.code, json.loads(e.read())
            except ValueError:
                return e.code, None
        except Exception as exc:
            if attempt == 3:
                return 0, {"message": repr(exc)}
            time.sleep(2 ** attempt * 2)


def save(name, obj):
    json.dump(obj, open(os.path.join(OUT, name), "w"), indent=0, default=str)


log = {}
for name, path in (("account", "/v2/account"), ("positions", "/v2/positions"), ("clock", "/v2/clock"),
                   ("calendar", "/v2/calendar?start=2026-09-28&end=2026-11-25")):
    s, r = get(BASE, path); save(f"{name}.json", r); log[name] = s

# every order since the start, oldest first, paged by submitted_at
orders, after = {}, START
while True:
    s, r = get(BASE, f"/v2/orders?status=all&limit=500&direction=asc&nested=false&after={after}")
    if s != 200 or not r:
        log["orders_last_status"] = s; break
    new = [o for o in r if o["id"] not in orders]
    for o in r:
        orders[o["id"]] = o
    if len(r) < 500 or not new:
        break
    after = r[-1]["submitted_at"]
save("orders.json", list(orders.values())); log["orders"] = len(orders)

# fill activities (each execution with its own time and price), and every other activity
for name, path in (("fills", "/v2/account/activities/FILL"), ("activities", "/v2/account/activities")):
    acts, tok = [], None
    while True:
        q = f"{path}?direction=asc&page_size=100&after={START}" + (f"&page_token={tok}" if tok else "")
        s, r = get(BASE, q)
        if s != 200 or not r:
            log[f"{name}_last_status"] = s; break
        acts += r
        if len(r) < 100:
            break
        tok = r[-1]["id"]
    save(f"{name}.json", acts); log[name] = len(acts)

# the broker's daily equity curve, raw timestamps
for name, q in (("history_3m", "period=3M&timeframe=1D"), ("history_1a", "period=1A&timeframe=1D"),
                ("history_5d_15m", "period=5D&timeframe=15Min&intraday_reporting=market_hours")):
    s, r = get(BASE, f"/v2/account/portfolio/history?{q}"); save(f"{name}.json", r); log[name] = s

# SIP daily bars, raw, with the end as an explicit time at least 16 minutes in the past (recent-SIP rule)
end = min(datetime.now(timezone.utc) - timedelta(minutes=20), datetime(2026, 11, 25, tzinfo=timezone.utc))
endq = end.strftime("%Y-%m-%dT%H:%M:%SZ")
bars, st = {}, []
for i in range(0, len(SYMS), 50):
    tok = None
    while True:
        q = (f"/v2/stocks/bars?symbols={','.join(SYMS[i:i + 50])}&timeframe=1Day&feed=sip&adjustment=raw"
             f"&start=2026-08-01T00:00:00Z&end={endq}&limit=10000" + (f"&page_token={tok}" if tok else ""))
        s, r = get(DATA, q); st.append(s)
        for k, v in ((r or {}).get("bars") or {}).items():
            bars.setdefault(k, []).extend(v)
        tok = (r or {}).get("next_page_token")
        if not tok:
            break
save("daily_bars.json", bars); log["daily_bars"] = {"symbols": len(bars), "status": sorted(set(st)), "end": endq}

# SIP minute bars 15:50-16:00 ET on each session with fund orders (arrival price at the send, the last trade)
days = sorted({o["submitted_at"][:10] for o in orders.values() if o.get("submitted_at")})
mins, st = {}, []
for d in days:
    syms = sorted({o["symbol"] for o in orders.values() if (o.get("submitted_at") or "")[:10] == d})
    d0 = date.fromisoformat(d)
    a = datetime(d0.year, d0.month, d0.day, 15, 50, tzinfo=ET).astimezone(timezone.utc)
    b = min(datetime(d0.year, d0.month, d0.day, 16, 5, tzinfo=ET).astimezone(timezone.utc), end)
    if b <= a:
        continue
    for i in range(0, len(syms), 50):
        tok = None
        while True:
            q = (f"/v2/stocks/bars?symbols={','.join(syms[i:i + 50])}&timeframe=1Min&feed=sip&adjustment=raw"
                 f"&start={a:%Y-%m-%dT%H:%M:%SZ}&end={b:%Y-%m-%dT%H:%M:%SZ}&limit=10000"
                 + (f"&page_token={tok}" if tok else ""))
            s, r = get(DATA, q); st.append(s)
            for k, v in ((r or {}).get("bars") or {}).items():
                mins.setdefault(d, {}).setdefault(k, []).extend(v)
            tok = (r or {}).get("next_page_token")
            if not tok:
                break
save("minute_bars.json", mins); log["minute_bars"] = {"days": len(mins), "status": sorted(set(st))}
log["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
save("fetch_log.json", log)
print(json.dumps(log))
