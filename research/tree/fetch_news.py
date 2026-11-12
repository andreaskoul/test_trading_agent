"""Layer 3, N4 data: Alpaca (Benzinga) news headlines 2015-2025 for every S&P 500 panel name. Coordinating session only.
Run through the redacting wrapper. Resumable: one parquet per name; a saved name is never re-downloaded (frozen at
first use, CLAUDE.md rule 4). Kept fields (documented API fields only): id, created_at, symbols, headline, source.

    python research/tree/fetch_news.py
"""
import json
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "fund"))
OUT = os.path.join(ROOT, ".cache", "tree", "news")
os.makedirs(OUT, exist_ok=True)
START, END = "2015-01-01T00:00:00Z", "2025-12-31T23:59:59Z"


def names():
    sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "quant-tf", "research", "quant_trials"))
    import sp500_test as T
    return sorted(c for c in pd.read_parquet(T.PX).columns if c != "SPY")


def get(broker, q):
    for wait in (0, 5, 15, 45, 90):
        time.sleep(wait)
        s, b = broker.api("GET", q, base=broker.DATA)
        if s == 200:
            return b
        print(f"status {s}, retry", flush=True)
    return None


def main():
    import broker
    todo, failed, calls = names(), [], 0
    for k, t in enumerate(todo):
        p = os.path.join(OUT, f"{t}.parquet")
        if os.path.exists(p):
            continue
        rows, token = [], None
        while True:
            q = f"/v1beta1/news?symbols={t}&start={START}&end={END}&limit=50&sort=asc" + (f"&page_token={token}" if token else "")
            b = get(broker, q)
            calls += 1
            if b is None:
                rows = None
                break
            rows += [(a["id"], a["created_at"], ",".join(a.get("symbols") or []), a.get("headline") or "", a.get("source") or "")
                     for a in b.get("news") or []]
            token = b.get("next_page_token")
            if not token:
                break
            time.sleep(0.3)
        if rows is None:
            failed.append(t)
            continue
        pd.DataFrame(rows, columns=["id", "created_at", "symbols", "headline", "source"]).to_parquet(p)
        if k % 50 == 0:
            print(f"{k + 1}/{len(todo)} names, {calls} calls", flush=True)
    meta = {"names": len(todo), "failed": failed, "calls_this_run": calls, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    json.dump(meta, open(os.path.join(OUT, "_meta.json"), "w"))
    print("done;", json.dumps(meta))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
