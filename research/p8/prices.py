"""P8 data foundation D1: daily adjusted closes for every S&P 500 member since 2012 and the current S&P 400,
point in time by symbol, with coverage measured against the member-days expected (CLAUDE.md rule 3).

    python research/p8/prices.py fetch      # Alpaca SIP bars 2016-01-04 .. 2025-12-31 (needs Alpaca keys)
    python research/p8/prices.py coverage   # report: member-day coverage by year, Alpaca vs yfinance cache

Alpaca's bars carry delisted symbols up to their last session (checked 2026-10-26: ATVI, CELG, SIVB, ...), so
2016+ is near survivorship-free for the S&P 500. 2012-2015 comes from the yfinance cache and stays biased (fit only).
The sealed window (2026) is never fetched here.
"""
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "fund"))
CACHE = os.path.join(ROOT, ".cache", "p8")
OUT = os.path.join(ROOT, "reports", "research", "p8")
START, END = "2016-01-04", "2025-12-31"          # never past the validation sample
EXTRA_BARS = []                                   # empty except in the sealed read
os.makedirs(CACHE, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def members(sessions=None):
    """Membership per session. The file has one row per date on which membership changed, so each row holds
    until the next one; with `sessions`, it is carried forward to every session."""
    m = pd.read_csv(os.path.join(ROOT, "data", "raw", "stocks", "sp500_membership.csv"), parse_dates=["date"])
    m = m.set_index("date")["tickers"].str.split(",")
    if sessions is not None:
        m = m.reindex(m.index.union(sessions)).ffill().reindex(sessions)
    return m[m.index >= "2012-01-01"]


def universe():
    m = members()
    sp500 = sorted({t for ts in m for t in ts})
    sp400 = pd.read_csv(os.path.join(ROOT, "data", "raw", "stocks", "sp400_current.csv"))["Symbol"].tolist()
    return sp500, sorted(set(sp400) - set(sp500))


def aliases(broker):
    """Ticker changes (same CUSIP) from Alpaca's corporate actions. Alpaca files a renamed company's whole bar
    history under its current symbol, so an old symbol (BLL) returns nothing and its history is under BALL.
    Returns {old: current}, following chains (A -> B -> C gives A: C)."""
    out, token, lo = {}, None, "2016-01-01"
    for y0 in range(2016, 2027):                    # the endpoint takes at most a year per request
        token = None
        while True:
            q = (f"/v1/corporate-actions?types=name_change&start={y0}-01-01&end={min(y0, 2026)}-12-31&limit=1000"
                 + (f"&page_token={token}" if token else ""))
            st, b = broker.api("GET", q, base=broker.DATA)
            assert st == 200, f"corporate actions unavailable ({st})"
            for x in (b.get("corporate_actions") or {}).get("name_changes", []):
                if x["old_symbol"] != x["new_symbol"]:
                    out[x["old_symbol"]] = x["new_symbol"]
            token = b.get("next_page_token")
            if not token:
                break
    for k in list(out):
        seen, v = {k}, out[k]
        while v in out and v not in seen:
            seen.add(v); v = out[v]
        out[k] = v
    return out


def fetch():
    import json
    import broker
    sp500, sp400 = universe()
    al = aliases(broker)
    json.dump(al, open(os.path.join(CACHE, "aliases.json"), "w"), indent=0, sort_keys=True)
    base = set(sp500) | set(sp400) | {"SPY", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"}
    names = sorted(base | {al[t] for t in base if t in al})
    print(f"{len(al)} ticker changes; {len(names)} symbols to fetch", flush=True)
    rows, failed = [], []
    for i in range(0, len(names), 50):
        chunk, token = names[i:i + 50], None
        while True:
            q = (f"/v2/stocks/bars?symbols={','.join(chunk)}&timeframe=1Day&adjustment=all&feed=sip&limit=10000"
                 f"&start={START}&end={END}T23:59:59Z" + (f"&page_token={token}" if token else ""))
            s, b = broker.api("GET", q, base=broker.DATA)
            if s != 200:
                failed += chunk
                break
            for t, xs in (b.get("bars") or {}).items():
                rows += [(x["t"][:10], t, float(x["c"]), float(x["v"])) for x in xs]
            token = b.get("next_page_token")
            if not token:
                break
        print(f"{min(i + 50, len(names))}/{len(names)} symbols, {len(rows):,} bars", flush=True)
    if failed:
        raise SystemExit(f"Alpaca bars failed for {len(failed)} symbols (first: {failed[:5]}); nothing saved")
    D = pd.DataFrame(rows, columns=["date", "ticker", "close", "volume"])
    D["date"] = pd.to_datetime(D["date"])
    D.to_parquet(os.path.join(CACHE, "alpaca_bars.parquet"))
    print(f"saved {len(D):,} bars, {D['ticker'].nunique()} symbols")


def panel():
    """Alpaca closes with each old symbol's column filled from its current symbol (same CUSIP)."""
    import json
    B = pd.read_parquet(os.path.join(CACHE, "alpaca_bars.parquet"))
    for extra in EXTRA_BARS:                           # the sealed read appends 2026 bars (research/p8/sealed.py)
        X = pd.read_parquet(os.path.join(CACHE, extra))
        B = pd.concat([B, X[X["date"] > B["date"].max()]])
    A = B.pivot(index="date", columns="ticker", values="close")
    al = json.load(open(os.path.join(CACHE, "aliases.json")))
    cols = {}
    for old, new in al.items():
        if new in A.columns:
            # the same-CUSIP history first: an old symbol can later be reused by an unrelated company
            cols[old] = A[new].combine_first(A[old]) if old in A.columns else A[new]
    return pd.concat([A.drop(columns=[c for c in cols if c in A.columns]), pd.DataFrame(cols)], axis=1)


def coverage():
    A = panel()
    yfp = os.path.join(CACHE, "yf_sp500_close.parquet")
    Y = pd.read_parquet(yfp) if os.path.exists(yfp) else pd.DataFrame()
    days = A.index
    sessions = (Y.index[(Y.index < days[0])] if len(Y) else pd.DatetimeIndex([])).union(days)
    m = members(sessions)
    lines = ["# P8 data foundation D1: S&P 500 price coverage (member-days with a close)", "",
             f"Alpaca SIP bars (adjusted for splits and dividends) {START} .. {END}; yfinance cache for 2012-2015.",
             "Expected = every (session, member) pair: `data/raw/stocks/sp500_membership.csv` (one row per change date) carried forward to each session.", "",
             "| year | member-days | Alpaca | yfinance cache | either |", "|---|---|---|---|---|"]
    miss = {}
    for y in range(2012, 2026):
        tot = a = yv = e = 0
        for d, ts in m[m.index.year == y].items():
            for t in ts:
                tot += 1
                ha = d in days and t in A.columns and pd.notna(A.at[d, t])
                hy = len(Y) and d in Y.index and t in Y.columns and pd.notna(Y.at[d, t])
                a += bool(ha); yv += bool(hy); e += bool(ha or hy)
                if not (ha or hy):
                    miss[t] = miss.get(t, 0) + 1
        lines.append(f"| {y} | {tot:,} | {a / tot:.1%} | {yv / tot:.1%} | {e / tot:.1%} |")
    top = sorted(miss.items(), key=lambda x: -x[1])[:40]
    lines += ["", "Symbols with the most missing member-days (either source):", "",
              ", ".join(f"{t} ({n})" for t, n in top), ""]
    open(os.path.join(OUT, "D1_coverage.md"), "w").write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    {"fetch": fetch, "coverage": coverage}[sys.argv[1]]()
