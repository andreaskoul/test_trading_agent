"""H5 Lazy Prices (PREREG_thesis_tree.md §4; operational definition: Amendment 5 C).

    python research/p8/h5.py sims     # filing-level similarities -> .cache/p8/h5_sims.parquet (no statistic)
    python research/p8/h5.py build    # month x firm rows -> .cache/p8/h5_rows.parquet
    python research/p8/h5.py fit      # fit-sample FM (signal months 2012-01 .. 2021-09): the replication check

Similarity (Cohen, Malloy & Nguyen 2020, Sim_Cosine): term-frequency vectors of a section (lower-cased alphabetic
tokens of >= 3 letters, no stop-list), cosine between a filing and the same-form filing a year earlier:
10-K vs the previous 10-K filed 300-430 days before; 10-Q vs the 10-Q whose period ended 365 +- 20 days before.
Sections: 10-K Item 7 and Item 1A; 10-Q Part I Item 2 (research/p8/sections.py; a section missing in either filing
is skipped). Filing similarity = mean over the sections present in both.
Signal at month-end m: the similarity of firm i's latest filing filed on or before the last day of m.
Target: e_{i,m+1} + e_{i,m+2} + e_{i,m+3} (monthly residuals). Universe: S&P 500 member at the month's last
session (point in time), else the current S&P 400 list. Registered sign: positive (non-changers outperform).
"""
import math
import os
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inference as I                                            # noqa: E402
import monthly as MO                                             # noqa: E402
import prices as PX                                              # noqa: E402
import sections as SE                                            # noqa: E402
import text as TX                                                # noqa: E402

SIMS = os.path.join(PX.CACHE, "h5_sims.parquet")
ROWS = os.path.join(PX.CACHE, "h5_rows.parquet")
TOK = re.compile(r"[a-z]{3,}")


def tf(s):
    return Counter(TOK.findall(s.lower()))


def cos(a, b):
    if not a or not b:
        return np.nan
    num = sum(v * b.get(k, 0) for k, v in a.items())
    return num / math.sqrt(sum(v * v for v in a.values()) * sum(v * v for v in b.values()))


def firm_sims(fl):
    """All filings of one CIK -> rows (accession, filed, form, sim, n_sections)."""
    secs = {}
    for f in fl:
        t = SE.load(f["cik"], f["accession"])
        if t is None:
            continue
        s = SE.extract(t, f["form"])
        secs[f["accession"]] = {k: tf(v) for k, v in s.items() if v is not None and k in ("7", "1A", "Q2")}
    rows = []
    for f in fl:
        if f["accession"] not in secs:
            continue
        fd = pd.Timestamp(f["filed"])
        if f["form"] == "10-K":
            prev = [g for g in fl if g["form"] == "10-K" and 300 <= (fd - pd.Timestamp(g["filed"])).days <= 430]
        else:
            pr = pd.Timestamp(f["period"]) if f["period"] else None
            prev = [g for g in fl if g["form"] == "10-Q" and pr is not None and g["period"]
                    and abs((pr - pd.Timestamp(g["period"])).days - 365) <= 20]
        prev = [g for g in prev if g["accession"] in secs]
        if not prev:
            continue
        g = max(prev, key=lambda z: z["filed"])
        a, b = secs[f["accession"]], secs[g["accession"]]
        common = [k for k in a if k in b]
        vals = [cos(a[k], b[k]) for k in common]
        vals = [v for v in vals if np.isfinite(v)]
        if vals:
            rows.append({"cik": f["cik"], "accession": f["accession"], "filed": f["filed"], "form": f["form"],
                         "sim": float(np.mean(vals)), "n_sections": len(vals)})
    return rows


def sims():
    F = TX.filings()
    by = {}
    for f in F:
        by.setdefault(f["cik"], []).append(f)
    out = []
    with ProcessPoolExecutor(6) as ex:
        for rows in ex.map(firm_sims, list(by.values()), chunksize=4):
            out += rows
    S = pd.DataFrame(out)
    S["filed"] = pd.to_datetime(S["filed"])
    S.to_parquet(SIMS)
    print(f"{len(S):,} filing similarities, {S['cik'].nunique()} firms; mean sim {S['sim'].mean():.3f}")
    print(S.groupby([S["filed"].dt.year, "form"]).size().unstack().to_string())


def build():
    import json
    S = pd.read_parquet(SIMS).sort_values("filed")
    Em = pd.read_parquet(MO.OUT)
    C = json.load(open(os.path.join(PX.CACHE, "edgar", "ciks.json")))
    sessions = pd.DatetimeIndex(pd.read_parquet(os.path.join(PX.CACHE, "alpaca_bars.parquet"))["date"].unique()).union(
        pd.read_parquet(os.path.join(PX.CACHE, "yf_sp500_close.parquet")).index)
    mem = PX.members(sessions)
    sp400 = set(pd.read_csv(os.path.join(PX.ROOT, "data", "raw", "stocks", "sp400_current.csv"))["Symbol"])
    tick_of = {}
    for t, x in C.items():
        if x["cik"]:
            tick_of.setdefault(x["cik"], []).append(t)
    months = list(Em.index)
    rows = []
    for a, m in enumerate(months[:-3]):
        end = pd.Period(m).end_time.normalize()
        last = mem.index[mem.index <= end]
        if not len(last):
            continue
        m500 = set(mem.loc[last[-1]])
        latest = S[S["filed"] <= end].groupby("cik").tail(1)
        y3 = Em.iloc[a + 1: a + 4]
        for r in latest.itertuples():
            for t in sorted(tick_of.get(r.cik, [])):
                u = "sp500" if t in m500 else ("sp400" if t in sp400 else None)
                if u is None or t not in Em.columns:
                    continue
                y = y3[t]
                if y.isna().any():
                    continue
                rows.append({"month": m, "ticker": t, "cik": r.cik, "universe": u, "signal": r.sim,
                             "age_days": (end - r.filed).days, "target": float(y.sum())})
                break
    D = pd.DataFrame(rows)
    D.to_parquet(ROWS)
    print(f"rows {len(D):,}; months {D['month'].nunique()}; firms {D['ticker'].nunique()}")


def stat(D):
    return I.fm_test(D, "signal", "target", month="month", firm="ticker", direction=1)


if __name__ == "__main__":
    if sys.argv[1] == "sims":
        sims()
    elif sys.argv[1] == "build":
        build()
    elif sys.argv[1] == "fit":
        D = pd.read_parquet(ROWS)
        F = D[(D["month"] >= "2012-01") & (D["month"] <= "2021-09")]
        for u in ("sp500", "sp400"):
            o = stat(F[F["universe"] == u])
            print(f"H5 fit {u}: months {o['months']}, slope {o['slope'] * 1e4:+.1f} bp per sd (3-month target), "
                  f"NW t {o['t']:+.2f}, p {o['p']:.4f}; L/S gross {o['ls_gross'] * 1e4:+.1f} bp, net {o['ls_net'] * 1e4:+.1f}")
            # descriptive robustness: the signal's within-month rank (the registered OLS slope is sensitive to the
            # similarity's long left tail: min 0.31 vs median 0.991)
            x = F[F["universe"] == u].copy()
            x["signal"] = x.groupby("month")["signal"].rank(pct=True)
            r = stat(x)
            print(f"   rank-signal robustness: slope {r['slope'] * 1e4:+.1f} bp per sd, t {r['t']:+.2f}")
