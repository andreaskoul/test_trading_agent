"""X1 inputs: daily closes for IEF, TLT, GLD, DBC, UUP and SPY from first listing to 2025-12-31 (yfinance, no key).
Frozen once to .cache/tree/l4x/<T>.csv with sha256 in MANIFEST.json; a frozen file is never re-downloaded.
Then the content contract (STATE.json plan.X1.data). Exit non-zero on any defect.

    python3 research/tree/L4_explore/fetch_x1.py
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
CACHE = os.path.join(ROOT, ".cache", "tree", "l4x")
TICK = {"IEF": "2002-07", "TLT": "2002-07", "GLD": "2004-11", "DBC": "2006-02", "UUP": "2007-02", "SPY": "1993-01"}
END = "2025-12-31"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def freeze():
    os.makedirs(CACHE, exist_ok=True)
    mpath = os.path.join(CACHE, "MANIFEST.json")
    man = json.load(open(mpath)) if os.path.exists(mpath) else {}
    import yfinance as yf
    for t in TICK:
        p = os.path.join(CACHE, f"{t}.csv")
        if os.path.exists(p):
            assert man[t]["sha256"] == sha(p), f"{t}: frozen file changed"
            continue
        df = yf.Ticker(t).history(start="1993-01-01", end="2026-01-01", auto_adjust=False, actions=True)
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        df = df[df.index <= END][["Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]]
        df.to_csv(p, index_label="Date")
        man[t] = {"sha256": sha(p), "rows": int(len(df)), "first": str(df.index[0].date()), "last": str(df.index[-1].date()),
                  "source": "yfinance Ticker.history(auto_adjust=False, actions=True)", "frozen_utc": pd.Timestamp.utcnow().isoformat()}
        json.dump(man, open(mpath, "w"), indent=1)
    return man


def load(t):
    return pd.read_csv(os.path.join(CACHE, f"{t}.csv"), parse_dates=["Date"], index_col="Date")


def contract(man):
    rep, bad = {}, []
    cal = load("SPY").index
    for t, ym in TICK.items():
        df = load(t)
        r = {"rows": len(df), "first": str(df.index[0].date()), "last": str(df.index[-1].date())}
        lag = (df.index[0] - pd.Timestamp(ym + "-01")).days
        r["first_vs_listing_days"] = int(lag)
        if not (-1 <= lag <= 40):
            bad.append(f"{t}: first date {df.index[0].date()} not in listing month {ym}")
        exp = cal[(cal >= df.index[0]) & (cal <= pd.Timestamp(END))]
        miss = exp.difference(df.index)
        r["expected_sessions"], r["missing_sessions"] = int(len(exp)), int(len(miss))
        if len(miss):
            bad.append(f"{t}: {len(miss)} sessions missing, e.g. {list(miss[:3].date)}")
        if df.index[-1] != pd.Timestamp(END):
            bad.append(f"{t}: last date {df.index[-1].date()}")
        c, a = df["Close"], df["Adj Close"]
        if c.isna().any() or a.isna().any() or (c <= 0).any() or (a <= 0).any():
            bad.append(f"{t}: NaN or non-positive close")
        ret = a.pct_change().dropna()
        r["max_abs_daily_ret"] = float(ret.abs().max())
        if ret.abs().max() >= 0.25:
            bad.append(f"{t}: daily return {ret.abs().max():.3f}")
        ratio = a / c
        dl = np.log(ratio).diff().abs()
        div = df["Dividends"] > 0
        near = div | div.shift(1, fill_value=False) | div.shift(-1, fill_value=False)
        jumps = dl[dl > 1e-4]
        unexplained = jumps.index[~near.reindex(jumps.index).values]
        r["ratio_jumps"], r["ratio_jumps_without_dividend"] = int(len(jumps)), int(len(unexplained))
        ok, n = 0, 0
        for d in df.index[div]:
            i = df.index.get_loc(d)
            if i == 0:
                continue
            n += 1
            implied = c.iloc[i - 1] * (1 - ratio.iloc[i - 1] / ratio.iloc[i])
            dv = df["Dividends"].iloc[i]
            ok += abs(implied - dv) <= max(0.05 * dv, 0.01)
        r["dividend_events"], r["dividend_consistent"] = n, int(ok)
        if n and ok / n < 0.95:
            bad.append(f"{t}: only {ok}/{n} dividends consistent with Adj Close/Close")
        if len(unexplained) > 0.05 * max(len(jumps), 1):
            bad.append(f"{t}: {len(unexplained)} Adj/Close ratio changes without a dividend")
        r["sha256"] = man[t]["sha256"]
        rep[t] = r
    return rep, bad


if __name__ == "__main__":
    man = freeze()
    rep, bad = contract(man)
    out = {"contract": rep, "defects": bad}
    json.dump(out, open(os.path.join(HERE, "X1_DATA_CHECK.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))
    sys.exit(1 if bad else 0)
