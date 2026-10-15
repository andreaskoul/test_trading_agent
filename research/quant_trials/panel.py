"""Quant trials · Stage 0 panel (plan: ~/.claude/plans/can-you-assess-whether-breezy-dijkstra.md).

Builds, from the owner's thesis panel (caf_ml_v0, gemini-embedding-001 headline vectors) and yfinance prices,
a dense daily panel over NYSE sessions 2015-01-02 .. 2025-12-31 for the 31 names with 2016-2026 coverage:

    python research/quant_trials/panel.py text      # per-ticker session sums of headline vectors (slow, once)
    python research/quant_trials/panel.py prices    # OHLCV for the names + SPY + VIX
    python research/quant_trials/panel.py coverage  # headline counts by name and year -> reports/

Nothing at or after 2026-01-01 is ever loaded: Jan-Sep 2026 is the sealed P8 holdout. Text rows are cut on the
session they map to, prices on their date, and targets only exist where the whole window ends by 2025-12-31.

Session rule is m0's assign_session (caf_ml_v0/data/prep/m0.ipynb): naive timestamps are read as UTC, converted
to ET; a headline before 16:00 ET on a trading day belongs to that session, anything later to the next one.
"""

import os
import sys

import numpy as np
import pandas as pd

SRC = "/Users/apollogodofthesun/caf_ml_v0/transitions/data/16_26_y"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, ".cache", "quant_trials")
REPORT = os.path.join(ROOT, "reports", "research", "quant_trials")
START, END = pd.Timestamp("2015-01-02"), pd.Timestamp("2025-12-31")   # END: last day ever loaded
DIM = 3072

DROPPED = ("BA", "BAC", "CVS", "F", "GS", "MA", "MRK", "NFLX", "V", "WFC")   # thesis folders that stop in 2018
UNIVERSE = ("AAPL", "AMD", "AMZN", "AXP", "C", "CMCSA", "COF", "COP", "CRM", "CVX", "DIS", "EBAY", "GE", "GME",
            "GOOG", "HAL", "JPM", "KO", "META", "MS", "MSFT", "MU", "NVDA", "OXY", "PNC", "QCOM", "SLB", "TSLA",
            "UNH", "USB", "XOM")
SECTORS = {"energy": ("COP", "CVX", "HAL", "OXY", "SLB", "XOM"),
           "financials": ("AXP", "C", "COF", "JPM", "MS", "PNC", "USB"),
           "semis": ("AMD", "MU", "NVDA", "QCOM"),
           "tech": ("AAPL", "AMZN", "GOOG", "META", "MSFT", "CRM", "EBAY"),
           "media": ("CMCSA", "DIS")}


def sessions():
    """NYSE sessions START..END (tz-naive dates)."""
    import pandas_market_calendars as mcal
    v = mcal.get_calendar("NYSE").valid_days(start_date=START, end_date=END)
    return pd.DatetimeIndex(pd.to_datetime(v).tz_localize(None).normalize())


def assign_sessions(ts, S):
    """Vectorised m0 assign_session: UTC-read timestamps -> NYSE session (NaT past the calendar)."""
    ts = pd.to_datetime(ts, errors="coerce", utc=True, format="mixed")
    et = ts.dt.tz_convert("America/New_York")
    day = et.dt.tz_localize(None).dt.normalize()
    trading = day.isin(S)
    same = trading & (et.dt.hour < 16)
    pos = np.where(trading & ~same, S.searchsorted(day, side="right"), S.searchsorted(day, side="left"))
    out = pd.Series(pd.NaT, index=ts.index, dtype="datetime64[ns]")
    ok = day.notna() & (day >= S[0]) & (pos < len(S))           # before the calendar: dropped, not folded in
    out[ok] = S[pos[ok.values]]
    out[same & ok] = day[same & ok]
    return out


def build_text(t, S, variant="dedup"):
    """Per-session sum of headline vectors and counts for one ticker; saved as npz.

    Vectors come from the dedup CSV's inline `embedding` column, m0's Stage-1 input. The sqlite .db holds only
    the 2016-18 subset for 12 names; where both exist they agree to 1e-5 (checked on AAPL)."""
    sums, cnt, seen = {}, {}, set()
    f = f"{SRC}/{t}/{t}_headlines_16_26_y_{variant}.csv"
    for ch in pd.read_csv(f, usecols=["publishedDate", "headline_uuid", "embedding"], chunksize=5000):
        ch["session"] = assign_sessions(ch["publishedDate"], S)
        ch = ch[ch["session"].notna()]
        for uid, s, e in zip(ch["headline_uuid"], ch["session"], ch["embedding"]):
            if uid in seen or not isinstance(e, str):
                continue
            v = np.array(e.strip("[] ").split(","), dtype=np.float32)
            if v.size != DIM:
                continue
            seen.add(uid)
            if s in sums:
                sums[s] += v
                cnt[s] += 1
            else:
                sums[s] = v
                cnt[s] = 1
    keys = sorted(sums)
    out = os.path.join(CACHE, "text", f"{t}_{variant}.npz")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    np.savez(out, session=np.array(keys, dtype="datetime64[D]"), n=np.array([cnt[k] for k in keys], np.int32),
             sum=np.stack([sums[k] for k in keys]).astype(np.float32) if keys else np.zeros((0, DIM), np.float32))
    return len(keys), sum(cnt.values()), (min(keys).date(), max(keys).date()) if keys else None


def load_text(variant="dedup", names=UNIVERSE):
    """Dense (D, N, DIM) float32 session sums and (D, N) counts on the session calendar."""
    S = sessions()
    idx = {d: i for i, d in enumerate(S.values.astype("datetime64[D]"))}
    X = np.zeros((len(S), len(names), DIM), np.float32)
    n = np.zeros((len(S), len(names)), np.int32)
    for j, t in enumerate(names):
        p = os.path.join(CACHE, "text", f"{t}_{variant}.npz")
        if not os.path.exists(p):
            continue
        z = np.load(p)
        rows = np.array([idx[d] for d in z["session"]], int)
        assert (z["session"] <= np.datetime64(END.date())).all()
        X[rows, j] = z["sum"]
        n[rows, j] = z["n"]
    return S, X, n


def build_prices():
    import yfinance as yf
    tick = list(UNIVERSE) + ["SPY", "^VIX"]
    df = yf.download(tick, start="2014-01-01", end=(END + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                     auto_adjust=True, progress=False, group_by="column", threads=True)
    df = df[df.index <= END]
    os.makedirs(CACHE, exist_ok=True)
    df.to_parquet(os.path.join(CACHE, "prices.parquet"))
    return df


def load_prices():
    df = pd.read_parquet(os.path.join(CACHE, "prices.parquet"))
    assert df.index.max() <= END
    return df


def coverage():
    rows = {}
    for t in UNIVERSE:
        z = np.load(os.path.join(CACHE, "text", f"{t}_dedup.npz"))
        rows[t] = pd.Series(z["n"], index=pd.DatetimeIndex(z["session"])).groupby(lambda d: d.year).sum()
    df = pd.DataFrame(rows).T.fillna(0).astype(int)
    os.makedirs(REPORT, exist_ok=True)
    df.to_csv(os.path.join(REPORT, "coverage.csv"))
    return df


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "text":
        S = sessions()
        names = sys.argv[2:] or UNIVERSE
        for t in names:
            print(t, "dedup", build_text(t, S), flush=True)
    elif what == "prices":
        print(build_prices().shape)
    elif what == "coverage":
        print(coverage().to_string())
