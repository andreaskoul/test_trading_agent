"""Risk-field round 3 (PREREG.md Amendment 6): news-day calendar for the contagion tests. No statistic here.

    python research/riskfield/shocks.py      # -> .cache/riskfield/news_days.npz (sessions x names of the close panel)

A firm's news day is the first session that can react to the news:
* **earnings:** `.cache/p8/events.parquet` t0, and 8-Ks carrying Item 2.02;
* **unscheduled:** every other 8-K (not 8-K/A) with at least one item other than 9.01 (exhibits), 2.02 (results) or
  5.07 (shareholder votes, scheduled).

The 8-K's typed `items` field and `acceptanceDateTime` come from the SEC bulk submissions (`.cache/p8/edgar/
submissions.zip`). Accepted at or after 16:00 ET, or on a non-session day: the next session.
"""
import json
import os
import sys
import zipfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "regime"))
import panel as PN                                                                    # noqa: E402
import regime as RG                                                                   # noqa: E402

OUT = os.path.join(PN.CACHE, "news_days.npz")
SKIP = {"9.01", "2.02", "5.07"}


def filings(z, cik):
    """All 8-K rows of one CIK from the bulk archive (recent block and the older -NNN files)."""
    name = f"CIK{cik:010d}.json"
    if name not in z.NameToInfo:
        return []
    d = json.loads(z.read(name))
    blocks = [d["filings"]["recent"]] + [json.loads(z.read(f["name"])) for f in d["filings"].get("files", [])
                                         if f["name"] in z.NameToInfo]
    rows = []
    for b in blocks:
        for f, acc, it in zip(b["form"], b["acceptanceDateTime"], b["items"]):
            if f == "8-K":
                rows.append((acc, it or ""))
    return rows


def main():
    P = RG.panel()
    S, names = P["S"], P["names"]
    tc = PN.ticker_cik()
    z = zipfile.ZipFile(os.path.join(PN.P8, "edgar", "submissions.zip"))
    earn = np.zeros((len(S), len(names)), bool)
    uns = np.zeros((len(S), len(names)), bool)
    Sv = S.values
    def session_of(ts):
        et = ts.tz_convert("America/New_York")
        day = np.datetime64(et.tz_localize(None).normalize())
        k = int(np.searchsorted(Sv, day))
        if k < len(Sv) and Sv[k] == day and et.hour * 60 + et.minute >= 960:
            k += 1
        return k
    n8, nu, ne = 0, 0, 0
    for j, tk in enumerate(names):
        cik = tc.get(tk)
        if not cik:
            continue
        for acc, it in filings(z, cik):
            ts = pd.Timestamp(acc)
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            k = session_of(ts)
            if k >= len(S) or S[k] < pd.Timestamp("2010-01-01"):
                continue
            items = {x.strip() for x in it.split(",") if x.strip()}
            n8 += 1
            if "2.02" in items:
                earn[k, j] = True
                ne += 1
            elif items - SKIP:
                uns[k, j] = True
                nu += 1
    ev = pd.read_parquet(os.path.join(PN.P8, "events.parquet"), columns=["ticker", "t0"])
    ev = ev[ev.t0 <= PN.END]
    ni = pd.Index(names).get_indexer(ev.ticker)
    ti = np.searchsorted(Sv, ev.t0.values.astype("datetime64[ns]"))
    ok = (ni >= 0) & (ti < len(S))
    earn[ti[ok], ni[ok]] = True
    uns &= ~earn                                     # a day with results is an earnings day
    np.savez_compressed(OUT, S=S.values.astype("datetime64[D]"), names=np.array(names), earn=earn, uns=uns)
    yrs = pd.Series(uns.sum(1), index=S).groupby(S.year).sum()
    print(f"8-Ks read {n8} (2.02: {ne}, unscheduled: {nu}); earnings days {int(earn.sum())}, unscheduled news days "
          f"{int(uns.sum())}; per year unscheduled: {yrs.to_dict()}")


if __name__ == "__main__":
    main()
