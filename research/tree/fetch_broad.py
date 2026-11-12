"""Layer 3, L3.1 data (PREREG Layer 3, Amendment 1): the broad survivorship-free US universe. Coordinating session only.
Run through the redacting wrapper (needs the Alpaca keys). Resumable: finished chunks are kept.

    python research/tree/fetch_broad.py symbols    # Alpaca assets (active + inactive) + Nasdaq Trader flags -> symbols.json
    python research/tree/fetch_broad.py bars       # daily bars 2016-01-04 .. 2025-12-31, 50 symbols a request
"""
import io
import json
import os
import sys
import time
import urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, ".cache", "tree", "broad")
sys.path.insert(0, os.path.join(ROOT, "fund"))
EXCH = {"NYSE", "NASDAQ", "AMEX"}
START, END = "2016-01-04", "2025-12-31"
os.makedirs(os.path.join(OUT, "chunks"), exist_ok=True)


def nasdaq_flags():
    """Typed flags from Nasdaq Trader's symbol directories: {symbol: (etf, test_issue)}."""
    flags = {}
    for name, sym, etf, test in (("nasdaqlisted.txt", "Symbol", "ETF", "Test Issue"), ("otherlisted.txt", "ACT Symbol", "ETF", "Test Issue")):
        raw = urllib.request.urlopen(f"https://www.nasdaqtrader.com/dynamic/SymDir/{name}", timeout=60).read().decode()
        d = pd.read_csv(io.StringIO(raw), sep="|")
        d = d[d[sym].notna() & ~d[sym].astype(str).str.startswith("File Creation Time")]
        for _, r in d.iterrows():
            flags[str(r[sym])] = (str(r[etf]) == "Y", str(r[test]) == "Y")
    return flags


def symbols():
    import broker
    assets = []
    for status in ("active", "inactive"):
        s, b = broker.api("GET", f"/v2/assets?status={status}&asset_class=us_equity")
        assert s == 200 and isinstance(b, list), (status, s)
        assets += b
    flags = nasdaq_flags()
    keep, drop = [], {"exchange": 0, "etf_or_test": 0}
    for a in assets:
        if a.get("exchange") not in EXCH:
            drop["exchange"] += 1
            continue
        f = flags.get(a["symbol"])
        if f and (f[0] or f[1]):
            drop["etf_or_test"] += 1
            continue
        keep.append({"symbol": a["symbol"], "exchange": a["exchange"], "status": a["status"]})
    meta = {"assets_read": len(assets), "kept": len(keep), "dropped": drop, "nasdaq_flags": len(flags),
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    json.dump({"meta": meta, "symbols": keep}, open(os.path.join(OUT, "symbols.json"), "w"), indent=0)
    print(json.dumps(meta))


def bars():
    import broker
    syms = sorted({s["symbol"] for s in json.load(open(os.path.join(OUT, "symbols.json")))["symbols"]})
    failed = []
    for i in range(0, len(syms), 50):
        p = os.path.join(OUT, "chunks", f"{i:06d}.parquet")
        if os.path.exists(p):
            continue
        chunk, token, rows = syms[i:i + 50], None, []
        while True:
            q = (f"/v2/stocks/bars?symbols={','.join(chunk)}&timeframe=1Day&adjustment=all&feed=sip&limit=10000"
                 f"&start={START}&end={END}T23:59:59Z" + (f"&page_token={token}" if token else ""))
            for wait in (0, 5, 15, 45, 90):  # retries: the first run lost 69 of 191 chunks to non-200 answers
                time.sleep(wait)
                s, b = broker.api("GET", q, base=broker.DATA)
                if s == 200:
                    break
                print(f"chunk {i}: status {s}, retry", flush=True)
            if s != 200:
                failed.append(i)
                rows = None
                break
            for t, xs in (b.get("bars") or {}).items():
                rows += [(x["t"][:10], t, float(x["c"]), float(x["v"])) for x in xs]
            token = b.get("next_page_token")
            if not token:
                break
        if rows is not None:
            pd.DataFrame(rows, columns=["date", "ticker", "close", "volume"]).to_parquet(p)
        if i % 1000 == 0:
            print(f"{min(i + 50, len(syms))}/{len(syms)} symbols", flush=True)
    print(f"done; failed chunks: {failed}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    {"symbols": symbols, "bars": bars}[sys.argv[1]]()
