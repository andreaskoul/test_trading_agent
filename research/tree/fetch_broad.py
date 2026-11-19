"""Layer 3, L3.1 data (PREREG Layer 3, Amendment 1): the broad survivorship-free US universe. Coordinating session only.
Run through the redacting wrapper (needs the Alpaca keys). Resumable: finished chunks are kept.

    python research/tree/fetch_broad.py symbols    # Alpaca assets (active + inactive) + Nasdaq Trader flags -> symbols.json
    python research/tree/fetch_broad.py bars       # daily bars 2016-01-04 .. 2025-12-31, 50 symbols a request
    python research/tree/fetch_broad.py raw        # the same, unadjusted, for eligibility only (Amendment 4)
    python research/tree/fetch_broad.py fwd        # forward phase (Amendment 9): new bars since the last window,
    python research/tree/fetch_broad.py fwdraw     #   adjusted / raw, into .cache/tree/y2026/fwd_<end>/chunks{,_raw}
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


def sp500_names():
    sys.path.insert(0, HERE)
    import panel400  # noqa: F401  (sets the quant-tf path)
    import sp500_test as T
    return sorted(pd.read_parquet(T.PX).columns)            # includes SPY


def bars(adj="all", start=START, end=END, outdir=None, extra=()):
    """adj="all": returns and the model fields; adj="raw": eligibility only (price filter, dollar volume), PREREG L3 Am. 4.
    With outdir: the same download into another folder (Amendment 7: 2026, into .cache/tree/y2026/)."""
    import broker
    syms = sorted({s["symbol"] for s in json.load(open(os.path.join(OUT, "symbols.json")))["symbols"]} | set(extra))
    failed = []
    base = outdir or OUT
    sub = "chunks" if adj == "all" else "chunks_raw"
    os.makedirs(os.path.join(base, sub), exist_ok=True)
    os.makedirs(os.path.join(OUT, "chunks_raw"), exist_ok=True)
    dpath = os.path.join(OUT, "chunks", "_dropped.json")
    dropped = json.load(open(dpath)) if os.path.exists(dpath) else {}
    for i in range(0, len(syms), 50):
        p = os.path.join(base, sub, f"{i:06d}.parquet")
        if os.path.exists(p):
            continue
        chunk, token, rows = [c for c in syms[i:i + 50] if c not in dropped], None, []
        while chunk:
            q = (f"/v2/stocks/bars?symbols={','.join(chunk)}&timeframe=1Day&adjustment={adj}&feed=sip&limit=10000"
                 f"&start={start}&end={end}T23:59:59Z" + (f"&page_token={token}" if token else ""))
            for wait in (0, 5, 15, 45, 90):  # 429/5xx: back off and retry
                time.sleep(wait)
                s, b = broker.api("GET", q, base=broker.DATA)
                if s in (200, 400, 403):          # 403: plan limit (e.g. recent SIP data); retrying cannot help
                    break
                print(f"chunk {i}: status {s}, retry", flush=True)
            msg = (b or {}).get("message", "") if isinstance(b, dict) else ""
            if s == 400 and msg.startswith("invalid symbol: "):
                # the 69 failed chunks of the first run: symbols the bars endpoint rejects (CUSIP-like ids, *_DELISTED
                # renames). Drop the symbol, record it, restart the chunk.
                bad = msg.split(": ", 1)[1].strip()
                if bad not in chunk:
                    failed.append(i)
                    rows = None
                    break
                chunk = [c for c in chunk if c != bad]
                dropped[bad] = "invalid symbol (bars endpoint 400)"
                json.dump(dropped, open(dpath, "w"), indent=0)
                token, rows = None, []
                continue
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


def y2026(adj):
    """Amendment 7: 2025-01-02 to the fetch date, broad + S&P 500 panel names + SPY, frozen at first fetch."""
    out = os.path.join(ROOT, ".cache", "tree", "y2026")
    meta = os.path.join(out, f"_fetch_{adj}.json")
    # the last complete session before the fetch date: the data plan refuses recent SIP data (403), 2026-11-13
    end = json.load(open(meta))["end"] if os.path.exists(meta) else \
        str((pd.Timestamp.utcnow().normalize() - pd.tseries.offsets.BDay(1)).date())
    os.makedirs(out, exist_ok=True)
    json.dump({"end": end, "start": "2025-01-02", "adj": adj}, open(meta, "w"))
    bars(adj, "2025-01-02", end, out, extra=sp500_names())


Y26 = os.environ.get("H7_Y26", os.path.join(ROOT, ".cache", "tree", "y2026"))


def fetch_windows(adj, y26=None):
    """Complete fetch windows for `adj`, oldest first: the frozen y2026 fetch, then each fwd_<end> folder whose meta
    says complete. Returns [(folder, start, end)]. Raises if two windows overlap or leave a gap of sessions."""
    y26 = y26 or Y26
    out = []
    m0 = os.path.join(y26, f"_fetch_{adj}.json")
    if os.path.exists(m0):
        j = json.load(open(m0))
        out.append((y26, j["start"], j["end"]))
    for d in sorted(os.listdir(y26)) if os.path.isdir(y26) else []:
        p = os.path.join(y26, d, f"_fetch_{adj}.json")
        if d.startswith("fwd_") and os.path.exists(p):
            j = json.load(open(p))
            if j.get("complete"):
                out.append((os.path.join(y26, d), j["start"], j["end"]))
    out.sort(key=lambda w: w[2])
    for (_, _, e0), (f1, s1, _) in zip(out, out[1:]):
        if s1 != e0:                     # each forward window starts ON the previous end: one overlap session
            raise SystemExit(f"fetch windows do not chain: {f1} starts {s1}, previous ends {e0}")
    return out


def last_complete_session():
    """The last complete US session before today (UTC), as y2026() chooses it; FWD_END overrides (tests, catch-up)."""
    if os.environ.get("FWD_END"):
        return os.environ["FWD_END"]
    return str((pd.Timestamp.utcnow().tz_localize(None).normalize() - pd.tseries.offsets.BDay(1)).date())


def forward(adj):
    """Forward phase (PREREG Layer 3, Amendment 9): bars from the last complete window's end (one overlap session, on
    which h7_build chain-links the adjusted closes: adjustment=all is as of the fetch date, so a dividend or split in
    the new window rescales its bars, not the frozen ones) to the last complete session, into a NEW folder .cache/tree/y2026/fwd_<end>/chunks{,_raw}. Never touches the frozen y2026
    chunks or an earlier fwd folder (CLAUDE.md rule 4). Resumable: a half-finished fwd_<end> keeps its chunks and its
    start; its meta is marked complete only when every chunk succeeded (bars() exits 1 otherwise)."""
    wins = fetch_windows(adj)
    if not wins:
        raise SystemExit(f"no frozen y2026 fetch for {adj}: run y2026 first")
    prev_end = wins[-1][2]
    end = last_complete_session()
    if pd.Timestamp(end) <= pd.Timestamp(prev_end):
        print(f"{adj}: nothing to fetch (last window ends {prev_end}, last complete session {end})")
        return
    start = prev_end
    folder = os.path.join(Y26, f"fwd_{end}")
    meta = os.path.join(folder, f"_fetch_{adj}.json")
    if os.path.exists(meta):
        j = json.load(open(meta))
        if j["start"] != start or j["end"] != end:
            raise SystemExit(f"{meta} has window {j['start']}..{j['end']}, expected {start}..{end}; not touching it")
        if j.get("complete"):
            print(f"{adj}: {folder} already complete")
            return
    os.makedirs(folder, exist_ok=True)
    json.dump({"end": end, "start": start, "adj": adj, "complete": False}, open(meta, "w"))
    bars(adj, start, end, folder, extra=sp500_names())          # exits 1 on any failed chunk: meta stays incomplete
    json.dump({"end": end, "start": start, "adj": adj, "complete": True,
               "completed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, open(meta, "w"))
    print(f"{adj}: {folder} complete, {start}..{end}")


if __name__ == "__main__":
    {"symbols": symbols, "bars": bars, "raw": lambda: bars("raw"),
     "y2026": lambda: y2026("all"), "y2026raw": lambda: y2026("raw"),
     "fwd": lambda: forward("all"), "fwdraw": lambda: forward("raw")}[sys.argv[1]]()
