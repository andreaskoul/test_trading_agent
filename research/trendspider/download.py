"""Download 15-minute regular-session bars from Alpaca (SIP feed, split/dividend adjusted) for the replica.

Run through the redacting wrapper (CLAUDE.md rule 16):  python3 research/trendspider/download.py [SYM ...]

Writes .cache/trendspider/<SYM>_<tf>.csv (ts_utc, open, high, low, close, volume). Keys come from the environment only.
"""
import os, sys, time, json, urllib.request, urllib.parse
import pandas as pd

OUT = ".cache/trendspider"
SYMS = sys.argv[1:] or ["SSO", "SPY", "QLD", "UPRO"]
TF = os.environ.get("TF", "15Min")                       # TF=1Min for the intraday momentum test
TAG = {"15Min": "15m", "1Min": "1m"}[TF]


def get(sym):
    h = {"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"], "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"]}
    rows, tok = [], None
    while True:
        q = {"symbols": sym, "timeframe": TF, "start": "2016-01-01T00:00:00Z", "end": "2026-11-04T00:00:00Z",
             "limit": 10000, "adjustment": "all", "feed": "sip"}
        if tok:
            q["page_token"] = tok
        req = urllib.request.Request("https://data.alpaca.markets/v2/stocks/bars?" + urllib.parse.urlencode(q), headers=h)
        for attempt in range(4):
            try:
                d = json.load(urllib.request.urlopen(req, timeout=60))
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 ** (attempt + 1))
        rows += d["bars"].get(sym, [])
        tok = d.get("next_page_token")
        if not tok:
            break
    df = pd.DataFrame(rows).rename(columns={"t": "ts_utc", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    et = df["ts_utc"].dt.tz_convert("America/New_York")
    m = et.dt.hour * 60 + et.dt.minute
    df = df[(m >= 570) & (m < 960)]                      # bars starting 09:30 .. 15:45 ET: the regular session
    return df[["ts_utc", "open", "high", "low", "close", "volume"]]


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for s in SYMS:
        df = get(s)
        df.to_csv(f"{OUT}/{s}_{TAG}.csv", index=False)
        print(s, len(df), df.ts_utc.min(), df.ts_utc.max())
