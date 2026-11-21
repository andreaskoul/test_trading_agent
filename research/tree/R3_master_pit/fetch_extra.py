"""R3: targeted Alpaca daily-bar fetch for the MASTER panel's missing names, 2016-01-01 .. 2024-12-31.

Run only through the redacting wrapper (keys from the environment; the key file is never opened):
    python3 ~/.claude/hooks/with_secrets.py 'python3 research/tree/R3_master_pit/fetch_extra.py NAMES_FILE'

Writes .cache/tree/r3/alpaca_extra.parquet (date, ticker, close [adjustment=all], volume) and alpaca_extra.json
(sha256, rows and first/last date per ticker, the symbols Alpaca returned nothing for). Read-only market data;
end date far in the past, so the 15-minute recent-data restriction does not apply.
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

OUT = os.path.join(".cache", "tree", "r3")
URL = "https://data.alpaca.markets/v2/stocks/bars"


def get(params):
    q = URL + "?" + urllib.parse.urlencode(params)
    h = {"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"], "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"]}
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(q, headers=h), timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and k < 4:
                time.sleep(2 ** k * 2)
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read()[:200]!r}")


def main():
    names = open(sys.argv[1]).read().strip().split(",")
    rows = []
    for i in range(0, len(names), 20):
        chunk = names[i:i + 20]
        params = {"symbols": ",".join(chunk), "timeframe": "1Day", "feed": "sip", "adjustment": "all",
                  "start": "2016-01-01", "end": "2024-12-31", "limit": 10000}
        while True:
            r = get(params)
            for t, bars in (r.get("bars") or {}).items():
                rows += [(b["t"][:10], t, float(b["c"]), float(b["v"])) for b in bars]
            if not r.get("next_page_token"):
                break
            params["page_token"] = r["next_page_token"]
        params.pop("page_token", None)
    df = pd.DataFrame(rows, columns=["date", "ticker", "close", "volume"]).drop_duplicates(["date", "ticker"])
    df["date"] = pd.to_datetime(df.date)
    p = os.path.join(OUT, "alpaca_extra.parquet")
    df.to_parquet(p, index=False)
    got = df.groupby("ticker").date.agg(["min", "max", "count"])
    meta = {"sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(), "requested": len(names),
            "returned": int(len(got)), "missing": sorted(set(names) - set(got.index)),
            "per_ticker": {t: [str(a.date()), str(b.date()), int(c)] for t, (a, b, c) in got.iterrows()}}
    json.dump(meta, open(os.path.join(OUT, "alpaca_extra.json"), "w"), indent=1)
    print(json.dumps({k: meta[k] for k in ("requested", "returned", "missing")}))


if __name__ == "__main__":
    main()
