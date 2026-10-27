"""P8 report events: one row per firm-quarter with its report session t0 (§1), universe, GICS levels and SUE.

    python research/p8/events.py     # -> .cache/p8/events.parquet and a coverage line per year

A report is a quarterly EPS period (first-filed, split-normalised; edgar.quarters) matched to the firm's first
8-K item 2.02 accepted 1-100 days after the period end. t0 (§1): accepted before 16:00 ET on a session -> that
session; after 16:00 or on a non-session day -> the next session. Reports without an 8-K 2.02 are not events
(§1: they are excluded from CAR tests). Universe: S&P 500 member at t0 (point in time), else the current S&P 400
list (flagged sp400). GICS levels from research/p8/gics.py (today's classification; Amendment 4 D3).
Never past 2025-12-31 (the sealed window is not read here).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edgar as ED                                               # noqa: E402
import prices as PX                                              # noqa: E402

OUT = os.path.join(PX.CACHE, "events.parquet")
T0_LAST = pd.Timestamp("2025-12-31")   # the sealed read (research/p8/sealed.py) sets 2026-09-30 and OUT/ED.TAG


def t0_of(acc, sessions):
    d = pd.Timestamp(acc.date())
    after_close = acc.hour * 60 + acc.minute >= 16 * 60
    i = sessions.searchsorted(d, side="right" if after_close else "left")
    return sessions[i] if i < len(sessions) else None


def sue_series(g):
    """SUE per quarter end for one firm (§1): (EPS_q - EPS_q-4) / sd(EPS_q-k - EPS_q-k-4, k = 1..8), >= 6 of 8,
    winsorised at +-10. Quarters are matched by end date within 20 days of 91-day steps."""
    ends = list(g.index)
    out = {}
    for e in ends:
        def back(k):
            tgt = e - pd.Timedelta(days=91 * k)
            m = [x for x in ends if abs((x - tgt).days) <= 20]
            return g[m[0]] if m else np.nan
        d = [back(k) - back(k + 4) for k in range(1, 9)]
        d = [x for x in d if np.isfinite(x)]
        cur = g[e] - back(4)
        if np.isfinite(cur) and len(d) >= 6 and np.std(d, ddof=1) > 0:
            out[e] = float(np.clip(cur / np.std(d, ddof=1), -10, 10))
    return out


def build(sessions):
    Q = pd.read_parquet(os.path.join(ED.CACHE, f"eps_quarterly{ED.TAG}.parquet")).sort_values(["cik", "end"])
    rel = pd.read_parquet(os.path.join(ED.CACHE, f"releases_202{ED.TAG}.parquet"))
    C = json.load(open(os.path.join(ED.CACHE, "ciks.json")))
    gics = json.load(open(os.path.join(PX.CACHE, "gics.json")))["firms"]
    by_cik = {}
    for t, x in C.items():
        if x["cik"]:
            by_cik.setdefault(x["cik"], []).append(t)
    mem = PX.members(sessions)
    sp400 = set(pd.read_csv(os.path.join(PX.ROOT, "data", "raw", "stocks", "sp400_current.csv"))["Symbol"])
    rel_by = {c: np.sort(g["accepted_et"].values) for c, g in rel.groupby("cik")}
    rows = []
    for c, g in Q.groupby("cik"):
        s = g.set_index("end")["eps"]
        sue = sue_series(s)
        acc_all = rel_by.get(c, np.array([], dtype="datetime64[ns]"))
        for e in s.index:
            lo, hi = np.datetime64(e + pd.Timedelta(days=1)), np.datetime64(e + pd.Timedelta(days=100))
            a = acc_all[(acc_all >= lo) & (acc_all <= hi)]
            if not len(a):
                continue
            t0 = t0_of(pd.Timestamp(a[0]), sessions)
            # the membership series starts in 2012: earlier reports cannot be placed in a universe
            if t0 is None or not (pd.Timestamp("2012-01-01") <= t0 <= T0_LAST):
                continue
            names = sorted(by_cik.get(c, []))
            mem_t0 = set(mem.loc[t0]) if t0 in mem.index and isinstance(mem.loc[t0], list) else set()
            in500 = [t for t in names if t in mem_t0]
            in400 = [t for t in names if t in sp400]
            tick, uni = (in500[0], "sp500") if in500 else ((in400[0], "sp400") if in400 else (None, None))
            if tick is None:
                continue
            gi = gics.get(tick) or next((gics[t] for t in names if t in gics), None)
            rows.append({"cik": c, "ticker": tick, "universe": uni, "period_end": e, "accepted_et": pd.Timestamp(a[0]),
                         "t0": t0, "season": str(t0.to_period("Q")), "sue": sue.get(e, np.nan),
                         "sub": gi["sub"] if gi else None, "industry": gi["industry_code"] if gi else None,
                         "sector": gi["sector"] if gi else None})
    E = pd.DataFrame(rows).drop_duplicates(["cik", "t0"])
    E.to_parquet(OUT)
    return E


if __name__ == "__main__":
    import residuals as RS
    R = RS.returns()
    E = build(R.index)
    E["year"] = E["t0"].dt.year
    print(E.groupby(["year", "universe"]).size().unstack().to_string())
    print(f"events {len(E):,}; with SUE {E['sue'].notna().mean():.1%}; with GICS {E['industry'].notna().mean():.1%}")
