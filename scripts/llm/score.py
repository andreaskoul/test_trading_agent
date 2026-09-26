"""Score logged decisions once their week has happened (PROTOCOL_llm.md).

    python scripts/llm/score.py [--mock]
    -> reports/llm_forward/scores.csv (+ a running summary on stdout)

Position set at the Thursday close after the as-of Wednesday, held to the
next Thursday close. Equal weight inside each leg (+1/n, -1/n). Cost =
turnover against the same book's previous week times the per-side cost
(5 bp stocks; Protocol 3 per-currency costs for FX).
"""

import argparse
import glob
import io
import json
import os
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser(); ap.add_argument("--mock", action="store_true"); args = ap.parse_args()
DEC = os.path.join(ROOT, "reports", "llm_forward", "mock" if args.mock else "decisions")
OUTF = os.path.join(ROOT, "reports", "llm_forward", "scores_mock.csv" if args.mock else "scores.csv")
FXT = {"EUR": ("EURUSD=X", True, "EZ"), "JPY": ("JPY=X", False, "JP"), "GBP": ("GBPUSD=X", True, "GB"),
       "CHF": ("CHF=X", False, "CH"), "AUD": ("AUDUSD=X", True, "AU"), "NZD": ("NZDUSD=X", True, "NZ"),
       "CAD": ("CAD=X", False, "CA"), "SEK": ("SEK=X", False, "SE"), "NOK": ("NOK=X", False, "NO"),
       "MXN": ("MXN=X", False, "MX"), "ZAR": ("ZAR=X", False, "ZA"), "PLN": ("PLN=X", False, "PL"),
       "HUF": ("HUF=X", False, "HU"), "CZK": ("CZK=X", False, "CZ"), "KRW": ("KRW=X", False, "KR"),
       "ILS": ("ILS=X", False, "IL"), "CLP": ("CLP=X", False, "CL")}
FX_COST = {**{c: 1e-4 for c in "EUR JPY GBP CHF AUD NZD CAD SEK NOK".split()},
           **{c: 3e-4 for c in "MXN PLN HUF CZK ILS KRW".split()}, "ZAR": 6e-4, "CLP": 6e-4}
now = pd.Timestamp.now(tz="UTC").tz_localize(None)


def px_at(frame, day):
    return frame.reindex(pd.date_range(frame.index.min(), day)).ffill(limit=3).loc[day]


def fred(fid):
    with urllib.request.urlopen(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fid}", timeout=60) as r:
        s = pd.read_csv(io.BytesIO(r.read()), na_values=".")
    s.columns = ["date", "v"]
    return s.assign(date=pd.to_datetime(s.date)).set_index("date")["v"].dropna() / 100


rows, prev = [], {}
for f in sorted(glob.glob(os.path.join(DEC, "*.json"))):
    d = json.load(open(f))
    asof = pd.Timestamp(d["asof"])
    t0, t1 = asof + pd.Timedelta(days=1), asof + pd.Timedelta(days=8)
    if now < t1 + pd.Timedelta(hours=23):                     # week not finished yet
        continue
    for universe in ("stocks", "fx"):
        e = d[universe]
        books = {"llm": e["llm"] if e["status"] == "ok" else None, "quant": e["quant"], "random": e["random"]}
        names = sorted({x if isinstance(x, str) else x["id"] for b in books.values() if b
                        for side in ("longs", "shorts") for x in b[side]})
        if universe == "stocks":
            p = yf.download([n.replace(".", "-") for n in names], start=t0 - pd.Timedelta(days=7),
                            end=t1 + pd.Timedelta(days=1), progress=False, auto_adjust=True)["Close"]
            p = p.rename(columns=lambda c: c.replace("-", ".")); p.index = p.index.tz_localize(None)
            ret = px_at(p, t1) / px_at(p, t0) - 1
            cost = pd.Series(5e-4, index=ret.index)
        else:
            raw = yf.download([FXT[c][0] for c in names], start=t0 - pd.Timedelta(days=7), end=t1 + pd.Timedelta(days=1),
                              progress=False, auto_adjust=False)["Close"]
            raw.index = raw.index.tz_localize(None)
            s = pd.DataFrame({c: raw[FXT[c][0]] if FXT[c][1] else 1 / raw[FXT[c][0]] for c in names})
            usd = fred("IR3TIB01USM156N")
            acc = pd.Series({c: (fred(f"IR3TIB01{FXT[c][2]}M156N").asof(t1) - usd.asof(t1)) / 52 for c in names})
            ret = np.log(px_at(s, t1) / px_at(s, t0)) + acc
            cost = pd.Series(FX_COST)[names]
        for book, b in books.items():
            if b is None:                                   # no_decision week counts as flat
                rows.append(dict(asof=d["asof"], universe=universe, book=book, gross=0.0, cost=0.0, net=0.0, n_missing=0))
                prev[(universe, book)] = pd.Series(dtype=float); continue
            L = [x if isinstance(x, str) else x["id"] for x in b["longs"]]
            S = [x if isinstance(x, str) else x["id"] for x in b["shorts"]]
            w = pd.concat([pd.Series(1 / len(L), index=L), pd.Series(-1 / len(S), index=S)])
            r = ret.reindex(w.index)
            gross = float((w * r.fillna(0)).sum())
            wp = prev.get((universe, book), pd.Series(dtype=float))
            to = (w.reindex(w.index.union(wp.index), fill_value=0) - wp.reindex(w.index.union(wp.index), fill_value=0)).abs()
            c = float((to * cost.reindex(to.index).fillna(cost.mean())).sum())
            rows.append(dict(asof=d["asof"], universe=universe, book=book, gross=gross, cost=c, net=gross - c,
                             n_missing=int(r.isna().sum())))
            prev[(universe, book)] = w

R = pd.DataFrame(rows)
R.to_csv(OUTF, index=False)
if len(R):
    P = R.pivot_table(index=["universe", "asof"], columns="book", values="net")
    for u, g in P.groupby(level=0):
        dlt = (g["llm"] - g["quant"]).dropna()
        t = dlt.mean() / dlt.std(ddof=1) * np.sqrt(len(dlt)) if len(dlt) > 2 else np.nan
        print(f"{u}: {len(g)} weeks | mean net %/wk llm {g['llm'].mean() * 100:.3f} quant {g['quant'].mean() * 100:.3f} "
              f"random {g['random'].mean() * 100:.3f} | llm-quant t {t:.2f} (formal read at 52 weeks)")
else:
    print("no finished weeks yet")
