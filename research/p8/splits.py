"""P8 data foundation: stock splits, to put first-filed per-share values in one share unit (Amendment 4, D6).

    python research/p8/splits.py fetch    # Alpaca corporate actions 2016-2025 (needs keys) + Yahoo splits 2009-2025
    python research/p8/splits.py check    # agreement of the two sources on 2016-2025

First-filed values are kept (no restatements), but a value filed before a k-for-1 split is in pre-split shares.
SEC financial statements issued after a split are restated for it, so the filing date tells which unit a value is
in: EPS_norm = EPS x F(filed) / F(last), shares_norm = shares x F(last) / F(filed), with
F(t) = product of (new / old) over splits with ex-date <= t. SUE is a ratio of EPS differences, so one common
scale leaves it unchanged; only the mix of units across a split is removed.
Sources (declared fields only): Alpaca forward/reverse splits (2016+); Yahoo's split history (yfinance
`Ticker.splits`), kept only for ratios p/q of integers <= 25, which drops spin-offs Yahoo records as fractional
splits (on 2016-2025 the two agree on 136 of the 140 events both list).
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices as PX                                              # noqa: E402

P = os.path.join(PX.CACHE, "splits.parquet")


def fetch():
    sys.path.insert(0, os.path.join(PX.ROOT, "fund"))
    import broker
    import yfinance as yf
    rows = []
    for y in range(2016, 2026):
        token = None
        while True:
            q = (f"/v1/corporate-actions?types=forward_split,reverse_split&start={y}-01-01&end={y}-12-31&limit=1000"
                 + (f"&page_token={token}" if token else ""))
            s, b = broker.api("GET", q, base=broker.DATA)
            assert s == 200, f"corporate actions unavailable ({s})"
            ca = b.get("corporate_actions") or {}
            for kind in ("forward_splits", "reverse_splits"):
                for x in ca.get(kind, []):
                    rows.append({"symbol": x["symbol"], "ex_date": x["ex_date"], "ratio": float(x["new_rate"]) / float(x["old_rate"]),
                                 "source": "alpaca"})
            token = b.get("next_page_token")
            if not token:
                break
    sp500, sp400 = PX.universe()
    al = json.load(open(os.path.join(PX.CACHE, "aliases.json")))
    names = sorted(set(sp500) | set(sp400) | {al[t] for t in set(sp500) | set(sp400) if t in al})
    for i, t in enumerate(names):
        try:
            s = yf.Ticker(t.replace(".", "-")).splits
        except Exception:
            continue
        for d, r in s.items():
            d = pd.Timestamp(d).tz_localize(None) if pd.Timestamp(d).tzinfo else pd.Timestamp(d)
            if pd.Timestamp("2009-01-01") <= d <= pd.Timestamp("2025-12-31") and r > 0:
                rows.append({"symbol": t, "ex_date": str(d.date()), "ratio": float(r), "source": "yahoo"})
        if i % 200 == 0:
            print(f"yahoo {i}/{len(names)}", flush=True)
    S = pd.DataFrame(rows)
    S["ex_date"] = pd.to_datetime(S["ex_date"])
    S.to_parquet(P)
    print(f"{(S.source == 'alpaca').sum()} Alpaca and {(S.source == 'yahoo').sum()} Yahoo split events")


def clean(r, top=25, tol=1e-4):
    """A real split or stock dividend has a ratio p/q of small integers (2, 3/2, 21/20). Yahoo also records spin-offs
    as fractional 'splits' (APTV 2017, BDX 2022: 1.0987-like ratios); those do not restate EPS and are dropped."""
    return any(abs(r - p / q) < tol for q in range(1, top + 1) for p in range(1, top + 1))


def table():
    """Splits per symbol: Alpaca's, plus Yahoo's clean-ratio events Alpaca lacks (pre-2016 history, stock dividends);
    one event per symbol and ex-date, Alpaca preferred."""
    S = pd.read_parquet(P)
    a = S[S.source == "alpaca"]
    y = S[(S.source == "yahoo") & S["ratio"].apply(clean)]
    return pd.concat([a, y]).drop_duplicates(["symbol", "ex_date"], keep="first")


def check():
    S = pd.read_parquet(P)
    sp500, sp400 = PX.universe()
    u = set(sp500) | set(sp400)
    a = S[(S.source == "alpaca") & S.symbol.isin(u)].set_index(["symbol", "ex_date"])["ratio"]
    y = S[(S.source == "yahoo") & (S.ex_date >= "2016-01-01") & S.symbol.isin(u)].set_index(["symbol", "ex_date"])["ratio"]
    both = a.index.intersection(y.index)
    agree = sum(abs(a[k] - y[k]) / y[k] < 0.01 for k in both)
    print(f"2016-2025, universe: Alpaca {len(a)}, Yahoo {len(y)}, same symbol and ex-date {len(both)}, same ratio {agree}")
    print("Alpaca only:", sorted(set(a.index) - set(y.index))[:15])
    print("Yahoo only:", sorted(set(y.index) - set(a.index))[:15])


if __name__ == "__main__":
    {"fetch": fetch, "check": check}[sys.argv[1]]()
