"""Desk 9 · Performance and attribution (PROTOCOL_fund.md).

Scores every finished week (Thursday -> next Thursday close) for every book,
with costs on turnover against the same book's previous week, and the
pre-registered stage tests. -> fund_state/<mode>/performance/*
"""

import glob
import io
import json
import os
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf

from common import MOCK, MODE, STATE

base = os.path.join(STATE, MODE)
OUT = os.path.join(base, "performance")
os.makedirs(OUT, exist_ok=True)
now = pd.Timestamp.now(tz="UTC").tz_localize(None)
FXT = {"EUR": ("EURUSD=X", True, "EZ"), "JPY": ("JPY=X", False, "JP"), "GBP": ("GBPUSD=X", True, "GB"),
       "CHF": ("CHF=X", False, "CH"), "AUD": ("AUDUSD=X", True, "AU"), "NZD": ("NZDUSD=X", True, "NZ"),
       "CAD": ("CAD=X", False, "CA"), "SEK": ("SEK=X", False, "SE"), "NOK": ("NOK=X", False, "NO"),
       "MXN": ("MXN=X", False, "MX"), "ZAR": ("ZAR=X", False, "ZA"), "PLN": ("PLN=X", False, "PL"),
       "HUF": ("HUF=X", False, "HU"), "CZK": ("CZK=X", False, "CZ"), "KRW": ("KRW=X", False, "KR"),
       "ILS": ("ILS=X", False, "IL"), "CLP": ("CLP=X", False, "CL")}
FX_COST = {**{c: 1e-4 for c in "EUR JPY GBP CHF AUD NZD CAD SEK NOK".split()},
           **{c: 3e-4 for c in "MXN PLN HUF CZK ILS KRW".split()}, "ZAR": 6e-4, "CLP": 6e-4}


def fred(fid):
    with urllib.request.urlopen(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fid}", timeout=60) as r:
        s = pd.read_csv(io.BytesIO(r.read()), na_values=".")
    s.columns = ["date", "v"]
    return s.assign(date=pd.to_datetime(s.date)).set_index("date")["v"].dropna() / 100


def at(frame, day):
    return frame.reindex(pd.date_range(frame.index.min(), day)).ffill(limit=3).loc[day]


def nw_t(x, L=2):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 3 or x.std() == 0:
        return np.nan
    e = x - x.mean(); s = e @ e / len(x)
    for k in range(1, min(L, len(x) - 1) + 1):
        s += 2 * (1 - k / (L + 1)) * (e[k:] @ e[:-k]) / len(x)
    return x.mean() / np.sqrt(s / len(x))


FACTORS = ["rev1w", "mom12_1", "lowvol"]      # from the screen's z-scores (Amendment 2 attribution)
rows, prev, ideas_rows, xs_rows, fac_rows, rt_rows = [], {}, [], [], [], []
for wd in sorted(glob.glob(os.path.join(base, "20*"))):
    asof = pd.Timestamp(os.path.basename(wd))
    t0, t1 = asof + pd.Timedelta(days=1), asof + pd.Timedelta(days=8)
    if now < t1 + pd.Timedelta(hours=23) or not os.path.exists(os.path.join(wd, "book.json")):
        continue
    book = json.load(open(os.path.join(wd, "book.json")))
    fx = json.load(open(os.path.join(wd, "fx.json"))) if os.path.exists(os.path.join(wd, "fx.json")) else {"books": {}}
    screen = pd.DataFrame(json.load(open(os.path.join(wd, "screen.json")))["rows"]).set_index("ticker")
    names = sorted(set(screen.index) | {t for b in book.get("books", {}).values() for t in b})
    p = yf.download([n.replace(".", "-") for n in names], start=t0 - pd.Timedelta(days=7), end=t1 + pd.Timedelta(days=1),
                    progress=False, auto_adjust=True, threads=True)["Close"]
    p = p.rename(columns=lambda c: c.replace("-", ".")); p.index = pd.to_datetime(p.index).tz_localize(None)
    ret = at(p, t1) / at(p, t0) - 1
    fxn = sorted({c for b in fx.get("books", {}).values() for c in b})
    if fxn:
        raw = yf.download([FXT[c][0] for c in fxn], start=t0 - pd.Timedelta(days=7), end=t1 + pd.Timedelta(days=1),
                          progress=False, auto_adjust=False)["Close"]
        raw.index = pd.to_datetime(raw.index).tz_localize(None)
        s = pd.DataFrame({c: raw[FXT[c][0]] if FXT[c][1] else 1 / raw[FXT[c][0]] for c in fxn})
        usd = fred("IR3TIB01USM156N")
        acc = pd.Series({c: (fred(f"IR3TIB01{FXT[c][2]}M156N").asof(t1) - usd.asof(t1)) / 52 for c in fxn})
        fret = np.log(at(s, t1) / at(s, t0)) + acc
    allbooks = {**{k: (v, ret, pd.Series(5e-4, index=ret.index)) for k, v in book.get("books", {}).items()},
                **{k: (v, fret, pd.Series(FX_COST)) for k, v in fx.get("books", {}).items() if fxn}}
    for k, (w, r, c) in allbooks.items():
        w = pd.Series(w, dtype=float)
        wp = prev.get(k, pd.Series(dtype=float))
        idx = w.index.union(wp.index)
        to = (w.reindex(idx, fill_value=0) - wp.reindex(idx, fill_value=0)).abs()
        gross = float((w * r.reindex(w.index).fillna(0)).sum()) if len(w) else 0.0
        cost = float((to * c.reindex(idx).fillna(c.mean())).sum())
        rows.append(dict(asof=str(asof.date()), book=k, gross=gross, cost=cost, net=gross - cost,
                         n_missing=int(r.reindex(w.index).isna().sum()) if len(w) else 0))
        prev[k] = w
    # ideation: do nominated names move more, and in the hypothesised direction?
    idea = json.load(open(os.path.join(wd, "ideation.json")))
    side = {x["ticker"]: +1 for x in (idea.get("llm") or {}).get("long_ideas", [])}
    side.update({x["ticker"]: -1 for x in (idea.get("llm") or {}).get("short_ideas", [])})
    xr = ret.reindex(screen.index) - ret.reindex(screen.index).mean()
    nom = xr.index.isin(list(side))
    ideas_rows.append(dict(asof=str(asof.date()), n_nom=int(nom.sum()),
                           abs_nom=float(xr[nom].abs().mean()) if nom.any() else np.nan, abs_rest=float(xr[~nom].abs().mean()),
                           signed_nom=float(np.mean([side[t] * xr.get(t, np.nan) for t in side if t in xr.index])) if side else np.nan))
    # factor returns over the S&P members: equal-weight market, and rank-weighted long-short
    # (sum |w| = 2) on each screen signal. The attribution regresses each book on these.
    rm = ret.reindex(screen.index).dropna()
    fr = {"asof": str(asof.date()), "mkt": float(rm.mean())}
    for f in FACTORS:
        if f in screen:
            z = screen[f].reindex(rm.index).rank(); z = z - z.mean()
            fr[f] = float((z / z.abs().sum() * 2 * rm).sum())
    fac_rows.append(fr)
    # red team calibration: did upheld views do better than weakened ones (in the analyst's direction)?
    rp = os.path.join(wd, "redteam.json")
    if os.path.exists(rp):
        rt = json.load(open(rp)); memos = json.load(open(os.path.join(wd, "analysts.json")))["memos"]
        for t, v in rt.get("reviews", {}).items():
            if v.get("status") == "ok" and t in xr.index and not np.isnan(xr.get(t, np.nan)):
                s0 = memos[t]["memo"]["score"]
                rt_rows.append(dict(asof=str(asof.date()), ticker=t, score=s0, verdict=v["review"]["verdict"],
                                    flaw=v["review"].get("flaw"), adjusted=v["review"]["adjusted_score"],
                                    signed_xret=float(np.sign(s0) * xr[t])))
    # cross-section over covered S&P names: return on (ridge rank, analyst score)
    sc = pd.Series(book.get("scores", {}).get("analyst", {}), dtype=float)
    x = pd.DataFrame({"r": ret.reindex(sc.index), "ridge": screen["ridge_bp"].reindex(sc.index), "a": sc}).dropna()
    if len(x) > 5:
        X = np.column_stack([np.ones(len(x)), (x.ridge.rank() - 1) / (len(x) - 1) - 0.5, x.a])
        b = np.linalg.lstsq(X, x.r.to_numpy(), rcond=None)[0]
        xs_rows.append(dict(asof=str(asof.date()), n=len(x), b_ridge=b[1], b_analyst=b[2]))

R = pd.DataFrame(rows); I = pd.DataFrame(ideas_rows); X = pd.DataFrame(xs_rows)
F = pd.DataFrame(fac_rows); RT = pd.DataFrame(rt_rows)
F.to_csv(os.path.join(OUT, "factors.csv"), index=False)
RT.to_csv(os.path.join(OUT, "redteam.csv"), index=False)
R.to_csv(os.path.join(OUT, "weekly_books.csv"), index=False)
I.to_csv(os.path.join(OUT, "ideation.csv"), index=False)
X.to_csv(os.path.join(OUT, "cross_section.csv"), index=False)
lines = [f"# Fund performance ({MODE}), {R['asof'].nunique() if len(R) else 0} scored weeks",
         "", "Formal read at 52 weeks, decision at 104 (PROTOCOL_fund.md). Anything earlier is not evidence.", ""]
if len(R):
    P = R.pivot_table(index="asof", columns="book", values="net")
    lines += ["| book | weeks | mean net %/wk | cum % |", "|---|---:|---:|---:|"]
    lines += [f"| {k} | {P[k].count()} | {P[k].mean() * 100:.3f} | {((1 + P[k].fillna(0)).prod() - 1) * 100:.2f} |" for k in P]
    lines += ["", "| test | weeks | mean diff %/wk | NW t |", "|---|---:|---:|---:|"]
    for a, b in (("fund", "quant"), ("analyst", "quant"), ("fund", "analyst"), ("fx", "fx_quant")):
        if a in P and b in P:
            dlt = (P[a] - P[b]).dropna()
            lines.append(f"| {a} − {b} | {len(dlt)} | {dlt.mean() * 100:.3f} | {nw_t(dlt):.2f} |")
if len(X):
    lines += ["", f"Cross-section: mean analyst-score slope {X.b_analyst.mean() * 1e4:.1f} bp/point, NW t {nw_t(X.b_analyst):.2f} ({len(X)} weeks)"]
if len(I):
    lines += [f"Ideation: nominated |excess ret| {I.abs_nom.mean() * 100:.2f}% vs rest {I.abs_rest.mean() * 100:.2f}%; "
              f"signed (hypothesis direction) {I.signed_nom.mean() * 100:.2f}%/wk"]
if len(RT):
    g = RT.groupby("verdict").signed_xret.agg(["count", "mean"])
    lines += ["Red team (signed excess return in the analyst's direction): " + "; ".join(
        f"{v} n={int(r['count'])} {r['mean'] * 100:+.2f}%" for v, r in g.iterrows())
        + ". Weakening is right when weakened names do worse than upheld ones."]
# Attribution (Amendment 2): book net return on market and factor returns; the intercept is
# what the news desk adds beyond the exposures the quant signals already explain.
if len(R) and len(F) >= 8:
    Fi = F.set_index("asof")
    lines += ["", "| book | weeks | alpha %/wk | NW t | beta mkt | " + " | ".join(FACTORS) + " |",
              "|---|---:|---:|---:|---:|" + "---:|" * len(FACTORS)]
    for k in ("fund", "analyst", "quant", "random"):
        if k not in P:
            continue
        d = pd.concat([P[k], Fi], axis=1, join="inner").dropna()
        if len(d) < 8:
            continue
        X_ = np.column_stack([np.ones(len(d))] + [d[c] for c in ["mkt"] + FACTORS])
        b, *_ = np.linalg.lstsq(X_, d[k].to_numpy(), rcond=None)
        resid = d[k].to_numpy() - X_[:, 1:] @ b[1:]            # alpha + noise: NW t on its mean
        lines.append(f"| {k} | {len(d)} | {b[0] * 100:.3f} | {nw_t(resid):.2f} | " + " | ".join(f"{x:.2f}" for x in b[1:]) + " |")
open(os.path.join(OUT, "summary.md"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
