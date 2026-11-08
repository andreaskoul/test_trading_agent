"""Risk-field round 10: equity options from Alpaca (historical daily bars of expired contracts, from 2024-02).

    python3 ~/.claude/hooks/with_secrets.py 'python research/riskfield/options.py download'   # needs the Alpaca keys
    python research/riskfield/options.py iv        # -> .cache/riskfield/opt_iv.parquet (no statistic)

Contracts: the Trading API's /v2/options/contracts (typed fields: underlying, type, strike, expiration). Kept:
monthly expirations (the third Friday) 2024-03 .. 2026-01, strikes within +-15% of the underlying's close 45 calendar
days before expiry. Bars: /v1beta1/options/bars, daily, from 75 days before expiry. Underlying: Alpaca daily stock
bars (vwap). Nothing after 2025-12-31 is kept (2026 is the owner's sealed window).
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import panel as PN                                                                    # noqa: E402

RAW = os.path.join(PN.CACHE, "options")
END = pd.Timestamp("2025-12-31")
_L, _LAST = threading.Lock(), [0.0]
GAP = 0.32


def _get(url):
    h = {"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"], "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"]}
    for attempt in range(6):
        with _L:
            w = _LAST[0] + GAP - time.time()
            if w > 0:
                time.sleep(w)
            _LAST[0] = time.time()
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404, 422):
                raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:150]}") from None
            time.sleep(5 * 2 ** min(attempt, 3))
        except Exception:                                                # noqa: BLE001
            time.sleep(5 * 2 ** min(attempt, 3))
    raise RuntimeError("request failed 6 times")


def monthly_expiries():
    out = []
    for m in pd.period_range("2024-03", "2026-01", freq="M"):
        d = pd.Timestamp(m.start_time)
        fr = [d + pd.Timedelta(days=i) for i in range(31) if (d + pd.Timedelta(days=i)).month == d.month
              and (d + pd.Timedelta(days=i)).weekday() == 4]
        out.append(fr[2])
    return out


def underlyings():
    px = pd.read_parquet(os.path.join(PN.QT, "sp500_close_live.parquet"))
    px.index = pd.to_datetime(px.index)
    mem = pd.read_csv(os.path.join(PN.ROOT, "data", "raw", "stocks", "sp500_membership.csv"), parse_dates=["date"])
    m = mem[(mem.date >= "2023-12-01") & (mem.date <= END)]
    names = set().union(*[set(s.split(",")) for s in m.tickers])
    last = mem[mem.date <= "2024-02-01"].iloc[-1].tickers.split(",")
    names |= set(last)
    return sorted(n for n in names if n in px.columns), px


def contracts(u):
    rows, tok = [], None
    for status in ("inactive", "active"):
        tok = None
        while True:
            q = {"underlying_symbols": u, "status": status, "expiration_date_gte": "2024-03-01",
                 "expiration_date_lte": "2026-01-31", "limit": 10000}
            if tok:
                q["page_token"] = tok
            d = _get("https://paper-api.alpaca.markets/v2/options/contracts?" + urllib.parse.urlencode(q))
            rows += [(c["symbol"], c["underlying_symbol"], c["type"], float(c["strike_price"]), c["expiration_date"])
                     for c in d.get("option_contracts", [])]
            tok = d.get("next_page_token")
            if not tok:
                break
    return rows


def bars(symbols, start, end):
    rows, tok = [], None
    while True:
        q = {"symbols": ",".join(symbols), "timeframe": "1Day", "start": start, "end": end, "limit": 10000}
        if tok:
            q["page_token"] = tok
        d = _get("https://data.alpaca.markets/v1beta1/options/bars?" + urllib.parse.urlencode(q))
        for s, bs in (d.get("bars") or {}).items():
            rows += [(s, b["t"][:10], b["o"], b["c"], b["vw"], b["v"], b["n"]) for b in bs]
        tok = d.get("next_page_token")
        if not tok:
            return rows


def stock_bars(symbols, start, end):
    rows = []
    for i in range(0, len(symbols), 100):
        tok = None
        while True:
            q = {"symbols": ",".join(symbols[i:i + 100]), "timeframe": "1Day", "start": start, "end": end, "feed": "sip",
                 "adjustment": "split", "limit": 10000}
            if tok:
                q["page_token"] = tok
            d = _get("https://data.alpaca.markets/v2/stocks/bars?" + urllib.parse.urlencode(q))
            for s, bs in (d.get("bars") or {}).items():
                rows += [(s, b["t"][:10], b["c"], b["vw"], b["v"]) for b in bs]
            tok = d.get("next_page_token")
            if not tok:
                break
    return rows


def download():
    os.makedirs(RAW, exist_ok=True)
    names, px = underlyings()
    print(f"underlyings {len(names)}")
    sp = os.path.join(RAW, "stock_daily.parquet")
    if not os.path.exists(sp):
        S = pd.DataFrame(stock_bars(names + ["SPY"], "2023-12-01", "2026-01-31"), columns=["ticker", "date", "close", "vwap", "volume"])
        S.to_parquet(sp)
        print("stock bars", len(S))
    S = pd.read_parquet(sp)
    S["date"] = pd.to_datetime(S.date)
    close = S.pivot(index="date", columns="ticker", values="close")
    cp = os.path.join(RAW, "contracts.parquet")
    if not os.path.exists(cp):
        with ThreadPoolExecutor(4) as ex:
            got = [r for part in ex.map(contracts, names) for r in part]
        C = pd.DataFrame(got, columns=["symbol", "underlying", "type", "strike", "expiry"])
        C.to_parquet(cp)
        print("contracts listed", len(C))
    C = pd.read_parquet(cp)
    C["expiry"] = pd.to_datetime(C.expiry)
    exps = set(monthly_expiries())
    C = C[C.expiry.isin(exps)]
    # strike filter: within +-15% of the close 45 calendar days before expiry
    ref = []
    for e in sorted(exps):
        d = close.index[close.index <= e - pd.Timedelta(days=45)]
        ref.append((e, close.loc[d[-1]] if len(d) else None))
    refmap = {e: r for e, r in ref}
    keep = []
    for e, g in C.groupby("expiry"):
        r = refmap.get(e)
        if r is None:
            continue
        spot = g.underlying.map(r)
        keep.append(g[(g.strike >= 0.85 * spot) & (g.strike <= 1.15 * spot)])
    C = pd.concat(keep)
    C.to_parquet(os.path.join(RAW, "contracts_kept.parquet"))
    print(f"contracts kept {len(C)} over {C.underlying.nunique()} underlyings and {C.expiry.nunique()} expiries")
    jobs = []
    for e, g in C.groupby("expiry"):
        st = (e - pd.Timedelta(days=75)).date().isoformat()
        en = min(e, END + pd.Timedelta(days=0)).date().isoformat()
        if pd.Timestamp(st) > END:
            continue
        syms = g.symbol.tolist()
        jobs += [(syms[i:i + 100], st, en) for i in range(0, len(syms), 100)]
    print("bar requests (groups)", len(jobs))
    with ThreadPoolExecutor(4) as ex:
        rows = [r for part in ex.map(lambda j: bars(*j), jobs) for r in part]
    B = pd.DataFrame(rows, columns=["symbol", "date", "open", "close", "vwap", "volume", "trades"])
    B = B[pd.to_datetime(B.date) <= END]
    B.to_parquet(os.path.join(RAW, "bars.parquet"))
    print(f"option bars {len(B)}; contracts with bars {B.symbol.nunique()}; dates {B.date.min()}..{B.date.max()}")


if __name__ == "__main__":
    {"download": download}[sys.argv[1]]()
