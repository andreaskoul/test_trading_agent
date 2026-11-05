"""Technicals desk · intraday and options measures of "priced in" (pre-registration 2 in
reports/research/technicals_backtest.md). Uses the events and Lifecycle-barrier outcomes of backtest_levels.py.

    python fund/backtest_intraday.py intraday   # news-day 5-minute SIP bars from Alpaca (free once 15 min old)
    python fund/backtest_intraday.py iv         # implied / historical vol before the news day, DoltHub (free)
    python fund/backtest_intraday.py test       # the five pre-registered tests -> appended to the report

Alpaca keys come from the environment, or from the local runner's secrets file.
"""

import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_levels as B             # noqa: E402

ET = ZoneInfo("America/New_York")
IDIR = os.path.join(B.BT, "intraday")
os.makedirs(IDIR, exist_ok=True)
DOLT = "https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master"


def keys():
    if os.environ.get("ALPACA_API_KEY"):
        return os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"]
    import importlib.util
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local", "runner.py")
    spec = importlib.util.spec_from_file_location("runner", p)
    r = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, ["runner.py"]
    spec.loader.exec_module(r)
    sys.argv = argv
    s = r.load_secrets()
    return s["ALPACA_API_KEY"], s["ALPACA_SECRET_KEY"]


def events():
    T = pd.read_parquet(os.path.join(B.BT, "trades.parquet"))
    return T[["ticker", "news_day", "entry_day", "side", "lc_pnl", "full_pnl"]].copy()


# ----------------------------------------------------------------------------- intraday bars
def intraday():
    k, s = keys()
    H = {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s}
    E = events()
    E = E[E.news_day >= "2016-01-04"]
    todo = [(t, d) for t, d in zip(E.ticker, E.news_day)
            if not os.path.exists(os.path.join(IDIR, f"{t}_{d.date()}.json"))]
    print(f"{len(todo)} news days to fetch ({len(E)} events from 2016)")
    last = 0.0
    for n, (t, d) in enumerate(todo):
        a = datetime_utc(d, 9, 30)
        z = datetime_utc(d, 16, 0)
        q = urllib.parse.urlencode({"timeframe": "5Min", "start": a, "end": z, "feed": "sip", "limit": 200,
                                    "adjustment": "split"})
        url = f"https://data.alpaca.markets/v2/stocks/{urllib.parse.quote(t)}/bars?{q}"
        for attempt in range(4):
            time.sleep(max(0.0, 0.34 - (time.time() - last)))          # <= ~175 requests a minute
            last = time.time()
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
                    bars = json.load(r).get("bars") or []
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(20); continue
                bars = None; break
            except Exception:
                time.sleep(5)
        else:
            bars = None
        json.dump({"bars": bars}, open(os.path.join(IDIR, f"{t}_{d.date()}.json"), "w"))
        if n % 500 == 0:
            print(f"{n}/{len(todo)}", flush=True)
    print("intraday done")


def datetime_utc(d, h, m):
    return pd.Timestamp(d.date()).replace(hour=h, minute=m).tz_localize(ET).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------- implied volatility
def dolt(sql, tries=3):
    for k in range(tries):
        try:
            with urllib.request.urlopen(f"{DOLT}?{urllib.parse.urlencode({'q': sql})}", timeout=90) as r:
                d = json.load(r)
            if d.get("query_execution_status") in ("Success", "RowLimit"):
                return d.get("rows", []), d["query_execution_status"]
        except Exception:
            pass
        time.sleep(5 * (k + 1))
    return None, "failed"


def iv():
    p = os.path.join(B.BT, "iv.parquet")
    have = pd.read_parquet(p) if os.path.exists(p) else pd.DataFrame(columns=["ticker", "news_day"])
    done = set(zip(have.ticker, pd.to_datetime(have.news_day)))
    E = events()
    E = E[E.news_day >= "2019-02-15"]
    rows = []
    for d, G in E.groupby("news_day"):
        syms = [t for t in G.ticker if (t, d) not in done]
        if not syms:
            continue
        lo, hi = (d - pd.Timedelta(days=7)).date(), (d - pd.Timedelta(days=1)).date()
        sql = ("SELECT date, act_symbol, iv_current, hv_current FROM volatility_history WHERE date BETWEEN "
               f"'{lo}' AND '{hi}' AND act_symbol IN ({','.join(repr(s.replace('.', '/')) for s in syms)})")
        res, st = dolt(sql)
        got = {}
        for r in res or []:
            got.setdefault(r["act_symbol"], []).append(r)
        for t in syms:
            xs = sorted(got.get(t.replace(".", "/"), []), key=lambda r: r["date"])
            x = xs[-1] if xs else None
            rows.append({"ticker": t, "news_day": d, "iv_date": x["date"] if x else None,
                         "iv": float(x["iv_current"]) if x and x["iv_current"] else np.nan,
                         "hv": float(x["hv_current"]) if x and x["hv_current"] else np.nan, "status": st})
        if len(rows) >= 200:
            have = pd.concat([have, pd.DataFrame(rows)], ignore_index=True); have.to_parquet(p); rows = []
            print(f"{len(have)} IV rows", flush=True)
    have = pd.concat([have, pd.DataFrame(rows)], ignore_index=True)
    have.to_parquet(p)
    print(f"IV for {have.iv.notna().sum()}/{len(have)} events")


# ----------------------------------------------------------------------------- features and the test
def features():
    E = events()
    out = []
    for t, d, side in zip(E.ticker, E.news_day, E.side):
        f = os.path.join(IDIR, f"{t}_{d.date()}.json")
        rec = {"ticker": t, "news_day": d}
        bars = json.load(open(f))["bars"] if os.path.exists(f) else None
        if bars and len(bars) >= 40:
            x = pd.DataFrame(bars)
            x["t"] = pd.to_datetime(x["t"]).dt.tz_convert(ET)
            x = x[(x.t.dt.time >= pd.Timestamp("09:30").time()) & (x.t.dt.time < pd.Timestamp("16:00").time())]
            if len(x) >= 40:
                close = float(x.c.iloc[-1])
                vwap = float((x.vw * x.v).sum() / x.v.sum()) if x.v.sum() > 0 else np.nan
                at = lambda hh, mm: float(x[x.t.dt.time <= pd.Timestamp(f"{hh}:{mm:02d}").time()].c.iloc[-1])
                rec.update(i_close=close, i_vwap=vwap, i_1500=at(14, 55), i_1000=at(9, 55))
        out.append(rec)
    F = pd.DataFrame(out)
    b = {t: B.load(t) for t in F.ticker.unique()}
    atr, cc = [], []
    for t, d in zip(F.ticker, F.news_day):
        g = b[t]
        if g is None or d not in g.index:
            atr.append(np.nan); cc.append(np.nan); continue
        ch_atr = B.LV.Chart(g.loc[:d]).atr
        i = g.index.get_loc(d)
        atr.append(float(ch_atr.iloc[i - 1])); cc.append(float(g["adj close"].iloc[i] / g["adj close"].iloc[i - 1] - 1))
    F["atr"], F["ret_day"] = atr, cc
    return F


def test():
    E = events().merge(features(), on=["ticker", "news_day"], how="left")
    p = os.path.join(B.BT, "iv.parquet")
    if os.path.exists(p):
        V = pd.read_parquet(p)[["ticker", "news_day", "iv", "hv"]]
        V["news_day"] = pd.to_datetime(V["news_day"])
        E = E.merge(V, on=["ticker", "news_day"], how="left")
    else:
        E["iv"] = E["hv"] = np.nan
    s = E.side
    # intraday bars are split-adjusted (Alpaca adjustment=split), like the daily bars the ATR comes from
    E["I1"] = s * (E.i_close - E.i_vwap) / E.atr
    E["I2"] = s * (E.i_close - E.i_1500) / E.atr
    E["I3"] = s * (E.i_close - E.i_1000) / E.atr
    E["O1"] = E.ret_day.abs() / (E.iv / math.sqrt(252))
    E["O2"] = E.iv / E.hv
    pred = {"I1": 1, "I2": 1, "I3": 1, "O1": 1, "O2": -1}
    names = {"I1": "close vs VWAP", "I2": "last hour", "I3": "open drive kept", "O1": "surprise vs implied",
             "O2": "anticipation (IV/HV)"}
    L = ["", "## Results of pre-registration 2 (computed 2026-10-08)", "",
         "Top − bottom tercile of each variable, signed by its predicted direction; Lifecycle-barrier P&L per event; "
         "t on weekly spreads. Pass: holdout t ≥ 2.58.", "",
         "| variable | period | events | top bp | bottom bp | weekly spread bp | t | weeks |",
         "|---|---|---:|---:|---:|---:|---:|---:|"]
    verdict = {}
    for v in ("I1", "I2", "I3", "O1", "O2"):
        for lab, lo, hi in (("2016/19–2021", "2016-01-01", "2021-12-31"), ("**2022–2025**", "2022-01-01", "2025-12-31")):
            S = E[(E.entry_day >= lo) & (E.entry_day <= hi) & E[v].notna() & np.isfinite(E[v])].copy()
            if len(S) < 60:
                L.append(f"| {names[v]} | {lab} | {len(S)} | | | | | |"); continue
            S["terc"] = pd.qcut(S[v].rank(method="first"), 3, labels=False)
            top, bot = (2, 0) if pred[v] > 0 else (0, 2)
            w = S[S.terc.isin([top, bot])].groupby(["entry_day", "terc"]).lc_pnl.mean().unstack().dropna()
            sp = w[top] - w[bot]
            tt = sp.mean() / sp.std(ddof=1) * math.sqrt(len(sp)) if len(sp) > 2 else float("nan")
            L.append(f"| {names[v]} | {lab} | {len(S):,} | {S[S.terc == top].lc_pnl.mean() * 1e4:+.1f} | "
                     f"{S[S.terc == bot].lc_pnl.mean() * 1e4:+.1f} | {sp.mean() * 1e4:+.1f} | {tt:+.2f} | {len(sp)} |")
            if lo.startswith("2022"):
                verdict[v] = tt
    passed = [names[v] for v, tt in verdict.items() if tt >= 2.58]
    L += ["", f"**Passed (holdout t ≥ 2.58): {', '.join(passed) if passed else 'none'}.**", ""]
    cov = {v: int(E[v].notna().sum()) for v in pred}
    L.append("Coverage (events with the variable): " + ", ".join(f"{names[v]} {n:,}" for v, n in cov.items()) + ".")
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(B.ROOT, "reports", "research", "technicals_backtest.md"), "a").write(txt)
    E.to_parquet(os.path.join(B.BT, "intraday_features.parquet"))


if __name__ == "__main__":
    {"intraday": intraday, "iv": iv, "test": test}[sys.argv[1]]()
