"""ETF coverage inventory for the two registrations (PREREG_ETF_TREND_FORWARD.md, research/etf_flow/PREREG_ETF_FLOW.md).

COVERAGE ONLY. Nothing here computes a return, a signal, a volatility, a correlation or any statistic of a price
series. For each ticker it records presence: first and last dates, rows, NYSE sessions expected against sessions
present (missing and extra days), missing closes, zero-volume days, split events, dividend events, whether an
adjusted close is served, Yahoo's firstTradeDate, and median daily volume and median dollar volume (close x shares,
a level, not a return) over fixed windows. No price value is printed.

    ~/.fund-runner/venv-research/bin/python -I research/etf_forward/etf_coverage.py fetch     # once; freeze sha256
    ~/.fund-runner/venv-research/bin/python -I research/etf_forward/etf_coverage.py coverage  # -> ETF_COVERAGE.json

`fetch` refuses to overwrite a frozen file; `coverage` refuses a file whose sha256 differs from ETF_MANIFEST.json.
yfinance with auto_adjust=False (Close and Adj Close both kept), actions=True. No login, account or key; the
library's default browser-like client is used (no personal details in any request).
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = os.environ.get("ETF_COV_CACHE", os.path.join(ROOT, ".cache", "etf-coverage"))
MANIFEST = os.path.join(HERE, "ETF_MANIFEST.json")
OUT = os.path.join(HERE, "ETF_COVERAGE.json")

# Fixed before any download. Forward-sleeve candidates and flow-study instruments (one download serves both).
TICKERS = {
    "SPY": "equity target (flow) / core",
    "SHY": "Treasury 1-3y", "IEI": "Treasury 3-7y", "IEF": "Treasury 7-10y", "TLT": "Treasury 20y+",
    "FXE": "EUR", "FXY": "JPY", "FXB": "GBP", "FXF": "CHF", "FXA": "AUD", "FXC": "CAD", "UUP": "dollar index",
    "DBC": "commodity basket", "GLD": "gold", "USO": "WTI crude", "SLV": "silver", "DBA": "agriculture",
    "DBB": "base metals", "UNG": "natural gas", "PDBC": "commodity basket (no K-1)", "GSG": "GSCI",
    "HYG": "high-yield credit", "LQD": "investment-grade credit",
}
START, LAST_FULL = "2002-07-01", "2026-11-24"
WINDOWS = {"liq_2025_11_2026_10": ("2025-11-01", "2026-10-31"), "liq_first_year_2007_05_2008_04": ("2007-05-01", "2008-04-30")}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _epoch_s(v):
    """firstTradeDate as integer epoch seconds (coverage() reads it with unit='s'); None if absent/unknown.
    yfinance serves it as an int on some versions and a pandas Timestamp on others; neither must reach json.dump raw."""
    if v is None:
        return None
    if hasattr(v, "timestamp"):                                      # pandas/py Timestamp or datetime
        return int(v.timestamp())
    try:
        return int(v)
    except (TypeError, ValueError):
        return str(v)


def fetch():
    import pandas as pd
    import yfinance as yf
    os.makedirs(CACHE, exist_ok=True)
    man = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {"files": {}}
    for t in TICKERS:
        p = os.path.join(CACHE, f"{t}.csv")
        if os.path.exists(p):
            rec = man["files"].get(t)
            if rec and rec.get("sha256") == sha(p):
                continue                                             # already frozen and recorded: keep
            if rec and rec.get("sha256") and rec["sha256"] != sha(p):
                sys.exit(f"{p}: sha256 differs from the manifest")   # a frozen file changed: refuse
            df0 = pd.read_csv(p, index_col=0)                        # CSV present but unrecorded (e.g. a prior
            man["files"][t] = {"sha256": sha(p), "rows": int(len(df0)), "columns": list(df0.columns),  # crashed run):
                               "rebuilt_from_cache_utc": datetime.now(timezone.utc).isoformat()}        # rebuild entry
            print(f"{t}: {len(df0)} rows (manifest entry rebuilt from cache)")
            continue
        tk = yf.Ticker(t)
        df = tk.history(start=START, end="2026-11-25", auto_adjust=False, actions=True)
        meta = tk.history_metadata or {}
        if df is None or df.empty:
            man["files"][t] = {"defect": "no_rows_served"}
            continue
        df.index = df.index.tz_localize(None).normalize() if df.index.tz is not None else df.index
        df.to_csv(p)
        man["files"][t] = {"sha256": sha(p), "rows": int(len(df)), "fetched_utc": datetime.now(timezone.utc).isoformat(),
                           "firstTradeDate": _epoch_s(meta.get("firstTradeDate")), "instrumentType": meta.get("instrumentType"),
                           "exchangeName": meta.get("exchangeName"), "columns": list(df.columns)}
        print(f"{t}: {len(df)} rows frozen")
    man["source"] = "yfinance Ticker.history(auto_adjust=False, actions=True), start " + START
    json.dump(man, open(MANIFEST, "w"), indent=1)


def coverage():
    import pandas as pd
    import pandas_market_calendars as mcal
    man = json.load(open(MANIFEST))
    cal = mcal.get_calendar("NYSE").valid_days(start_date=START, end_date=LAST_FULL)
    cal = pd.DatetimeIndex(pd.to_datetime(cal).tz_localize(None).normalize())
    out = {"written_utc": datetime.now(timezone.utc).isoformat(), "last_full_session": LAST_FULL, "tickers": {}}
    for t, role in TICKERS.items():
        m = man["files"].get(t, {})
        if "sha256" not in m:
            out["tickers"][t] = {"role": role, "defect": m.get("defect", "not_fetched")}
            continue
        p = os.path.join(CACHE, f"{t}.csv")
        if sha(p) != m["sha256"]:
            sys.exit(f"{t}: sha256 differs from the manifest")
        df = pd.read_csv(p, index_col=0)
        df.index = pd.to_datetime(df.index, utc=True).tz_localize(None).normalize()
        df = df[df.index <= LAST_FULL]
        first, last = df.index.min(), df.index.max()
        exp = cal[(cal >= first) & (cal <= last)]
        missing = exp.difference(df.index)
        extra = df.index.difference(cal)
        vol = df["Volume"]
        splits = df.loc[df.get("Stock Splits", pd.Series(0, index=df.index)).fillna(0) != 0, "Stock Splits"]
        divs = df.loc[df.get("Dividends", pd.Series(0, index=df.index)).fillna(0) != 0].index
        r = {"role": role, "first": str(first.date()), "last": str(last.date()), "rows": int(len(df)),
             "firstTradeDate_yahoo": (str(pd.Timestamp(m["firstTradeDate"], unit="s").date())
                                      if isinstance(m.get("firstTradeDate"), (int, float)) else m.get("firstTradeDate")),
             "sessions_expected": int(len(exp)), "sessions_missing": int(len(missing)),
             "missing_dates_first20": [str(x.date()) for x in missing[:20]], "extra_non_session_rows": int(len(extra)),
             "close_missing": int(df["Close"].isna().sum()), "adj_close_served": "Adj Close" in df.columns,
             "adj_close_missing": int(df["Adj Close"].isna().sum()) if "Adj Close" in df.columns else None,
             "zero_volume_days": int((vol.fillna(0) == 0).sum()),
             "zero_volume_days_since_2020": int((vol[vol.index >= "2020-01-01"].fillna(0) == 0).sum()),
             "splits": [{"date": str(d.date()), "ratio": float(x)} for d, x in splits.items()],
             "dividend_events": int(len(divs)), "dividend_first": str(divs.min().date()) if len(divs) else None,
             "dividend_last": str(divs.max().date()) if len(divs) else None,
             "listed_at_last_full_session": bool(last == pd.Timestamp(LAST_FULL))}
        for k, (a, b) in WINDOWS.items():
            w = df[(df.index >= a) & (df.index <= b)]
            r[k] = None if w.empty else {"sessions": int(len(w)), "median_shares": float(w["Volume"].median()),
                                         "median_dollar_volume_musd": round(float((w["Close"] * w["Volume"]).median()) / 1e6, 2)}
        out["tickers"][t] = r
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"written {OUT}")


if __name__ == "__main__":
    {"fetch": fetch, "coverage": coverage}[sys.argv[1]]()
