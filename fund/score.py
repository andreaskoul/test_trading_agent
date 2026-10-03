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

from common import MODE, STATE

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
STOCK_BOOKS = ("fund", "analyst", "quant", "core20", "random", "c1_wedclose", "c1_thuopen",
               "c2_selfconsistency", "c3_textonly", "c4_volscaled", "c5_reversal", "c7_noreview")
CHALLENGERS = ("c1_wedclose", "c1_thuopen", "c2_selfconsistency", "c3_textonly", "c4_volscaled", "c5_reversal", "c7_noreview")
rf = fred("DTB3")                                   # 3-month T-bill, for returns in excess of cash (Amendment 3)
rows, prev, ideas_rows, xs_rows, fac_rows, rt_rows, mon_rows = [], {}, [], [], [], [], []
for wd in sorted(glob.glob(os.path.join(base, "20*"))):
    asof = pd.Timestamp(os.path.basename(wd))
    if now < asof + pd.Timedelta(days=8, hours=23) or not os.path.exists(os.path.join(wd, "book.json")):
        continue
    book = json.load(open(os.path.join(wd, "book.json")))
    if book.get("status") not in ("ok", "degraded_hold"):   # missed deadline: the week is flat, so every book sells out
        for k in [k for k in prev if k in STOCK_BOOKS]:
            rows.append(dict(asof=str(asof.date()), book=k, gross=0.0, cost=float(prev[k].abs().sum() * 5e-4),
                             net=-float(prev[k].abs().sum() * 5e-4), excess=-float(prev[k].abs().sum() * 5e-4), n_missing=0))
            prev[k] = pd.Series(dtype=float)
        continue
    fx = json.load(open(os.path.join(wd, "fx.json"))) if os.path.exists(os.path.join(wd, "fx.json")) else {"books": {}}
    screen = pd.DataFrame(json.load(open(os.path.join(wd, "screen.json")))["rows"]).set_index("ticker")
    names = sorted(set(screen.index) | {t for b in book.get("books", {}).values() for t in b})
    shadow_p = os.path.join(wd, "shadow_book.json")
    shadow = json.load(open(shadow_p))["books"] if os.path.exists(shadow_p) else {}
    names = sorted(set(names) | {t for b in shadow.values() for t in b})
    px_all = yf.download([n.replace(".", "-") for n in names], start=asof - pd.Timedelta(days=7), end=asof + pd.Timedelta(days=14),
                         progress=False, auto_adjust=True, threads=True)
    p, po = px_all["Close"], px_all["Open"]
    for f_ in (p, po):
        f_.rename(columns=lambda c: c.replace("-", "."), inplace=True); f_.index = pd.to_datetime(f_.index).tz_localize(None)
    # entry at the close of the first trading day after the as-of Wednesday (the execution day),
    # exit at the first close on or after the next Thursday: holidays move both, never backwards
    if p.index.max() < asof + pd.Timedelta(days=8):
        continue
    t0, t1 = p.index[p.index > asof][0], p.index[p.index >= asof + pd.Timedelta(days=8)][0]
    ret = p.loc[t1] / p.loc[t0] - 1
    rf_w = float(rf.asof(t0)) * (t1 - t0).days / 360
    # C1 timing books (Amendment 4): the fund's weights entered at the as-of Wednesday close (notional,
    # not tradable after the decision) and at the execution day's open, each held one week
    w1 = p.index[p.index >= asof + pd.Timedelta(days=7)][0]
    ret_wed = p.loc[w1] / p.loc[asof] - 1 if asof in p.index else ret * np.nan
    ret_open = po.loc[t1] / po.loc[t0] - 1
    # a halted week is flat for the fund whatever the book said (Amendment 4: halt semantics)
    ex_p = os.path.join(wd, "execution.json")
    halted_wk = os.path.exists(ex_p) and str(json.load(open(ex_p)).get("reason") or "").startswith("HALT")
    fund_w = {} if halted_wk else book.get("books", {}).get("fund", {})
    fxn = sorted({c for b in fx.get("books", {}).values() for c in b})
    if fxn:
        raw = yf.download([FXT[c][0] for c in fxn], start=t0 - pd.Timedelta(days=7), end=t1 + pd.Timedelta(days=1),
                          progress=False, auto_adjust=False)["Close"]
        raw.index = pd.to_datetime(raw.index).tz_localize(None)
        s = pd.DataFrame({c: raw[FXT[c][0]] if FXT[c][1] else 1 / raw[FXT[c][0]] for c in fxn})
        usd = fred("IR3TIB01USM156N")
        acc = pd.Series({c: (fred(f"IR3TIB01{FXT[c][2]}M156N").asof(t1) - usd.asof(t1)) / 52 for c in fxn})
        fret = np.log(at(s, t1) / at(s, t0)) + acc
    c5bp = pd.Series(5e-4, index=ret.index)
    allbooks = {**{k: (fund_w if k == "fund" else v, ret, c5bp) for k, v in book.get("books", {}).items()},
                **{k: (v, ret, c5bp) for k, v in shadow.items()},
                "c1_wedclose": (fund_w, ret_wed, c5bp), "c1_thuopen": (fund_w, ret_open, c5bp),
                **{k: (v, fret, pd.Series(FX_COST)) for k, v in fx.get("books", {}).items() if fxn}}
    for k, (w, r, c) in allbooks.items():
        w = pd.Series(w, dtype=float)
        wp = prev.get(k, pd.Series(dtype=float))
        idx = w.index.union(wp.index)
        to = (w.reindex(idx, fill_value=0) - wp.reindex(idx, fill_value=0)).abs()
        gross = float((w * r.reindex(w.index).fillna(0)).sum()) if len(w) else 0.0
        cost = float((to * c.reindex(idx).fillna(c.mean())).sum())
        rows.append(dict(asof=str(asof.date()), book=k, gross=gross, cost=cost, net=gross - cost,
                         excess=gross - cost - (rf_w * float(w.sum()) if k in STOCK_BOOKS else 0.0),
                         n_missing=int(r.reindex(w.index).isna().sum()) if len(w) else 0))
        prev[k] = w
    # Amendment 5: the daily review can change the fund's weights mid-week. The fund is then scored
    # piecewise between review closes (5 bp/side on each change); c7_noreview keeps the weekly book
    # untouched for the whole week, so fund - c7_noreview is what the reviews added.
    revs = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(wd, "reviews", "*.json")))]
    revs = [r_ for r_ in revs if r_.get("status") == "submitted" and t0 < pd.Timestamp(r_["day"]) < t1]
    frow = next((x for x in rows[::-1] if x["asof"] == str(asof.date()) and x["book"] == "fund"), None)
    if frow is not None:
        rows.append({**frow, "book": "c7_noreview"})
        if revs and fund_w:
            wk_ = pd.Series(fund_w, dtype=float)
            pts = [t0] + [pd.Timestamp(r_["day"]) for r_ in revs] + [t1]
            g_, c_ = 0.0, frow["cost"]
            for j in range(len(pts) - 1):
                seg = p.loc[pts[j + 1]] / p.loc[pts[j]] - 1
                g_ += float((wk_ * seg.reindex(wk_.index).fillna(0)).sum())
                if j < len(revs):                       # apply review j's changes at its close
                    new = wk_.copy()
                    for t_, d_ in revs[j]["decisions"].items():
                        if d_.get("final") in ("exit", "reduce", "increase"):
                            new[t_] = float(revs[j]["target_weights"].get(t_, 0.0))
                    new["SPY"] = float(revs[j]["target_weights"].get("SPY", new.get("SPY", 0.0)))
                    idx_ = new.index.union(wk_.index)
                    c_ += float((new.reindex(idx_, fill_value=0) - wk_.reindex(idx_, fill_value=0)).abs().sum() * 5e-4)
                    wk_ = new
            frow.update(gross=g_, cost=c_, net=g_ - c_, excess=g_ - c_ - rf_w * float(wk_.sum()))
            prev["fund"] = wk_
        prev["c7_noreview"] = pd.Series(fund_w, dtype=float)
    # monitors (Amendment 4): coverage, score dispersion, zero share, failures, serving provider
    am = json.load(open(os.path.join(wd, "analysts.json")))["memos"] if os.path.exists(os.path.join(wd, "analysts.json")) else {}
    sc_ok = [m["memo"]["score"] for m in am.values() if m.get("status") == "ok"]
    mon_rows.append(dict(asof=str(asof.date()), status=book.get("status"), covered=len(am), memo_ok=len(sc_ok),
                         zero_share=float(np.mean([s_ == 0 for s_ in sc_ok])) if sc_ok else np.nan,
                         score_sd=float(np.std(sc_ok)) if sc_ok else np.nan,
                         fund_names=sum(k != "SPY" for k in fund_w), fund_stock_gross=float(sum(abs(v) for k, v in fund_w.items() if k != "SPY")),
                         spy_hedge=float(fund_w.get("SPY", 0.0)), halted=halted_wk,
                         providers="|".join(sorted({str((m.get("meta") or {}).get("provider")) for m in am.values() if m.get("meta")}))))
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
    fr = {"asof": str(asof.date()), "mkt": float(rm.mean()), "spy": float(ret.get("SPY", np.nan))}
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
        # Amendment 4: the score slope controlling for last week's return, hedge beta and sector
        z_ = pd.DataFrame({"r": ret.reindex(sc.index), "a": sc, "r1w": screen["ret_1w_pct"].reindex(sc.index),
                           "b": screen.get("beta_hedge", screen["beta60"]).reindex(sc.index),
                           "sec": screen["GICS Sector"].reindex(sc.index)}).dropna()
        b_adj = np.nan
        if len(z_) > 12:
            D = pd.get_dummies(z_["sec"], drop_first=True, dtype=float)
            X2 = np.column_stack([np.ones(len(z_)), z_.a, z_.r1w, z_.b, D.to_numpy()])
            b_adj = np.linalg.lstsq(X2, z_.r.to_numpy(), rcond=None)[0][1]
        xs_rows.append(dict(asof=str(asof.date()), n=len(x), b_ridge=b[1], b_analyst=b[2], b_analyst_adj=b_adj))

R = pd.DataFrame(rows); I = pd.DataFrame(ideas_rows); X = pd.DataFrame(xs_rows)
F = pd.DataFrame(fac_rows); RT = pd.DataFrame(rt_rows)
pd.DataFrame(mon_rows).to_csv(os.path.join(OUT, "monitor.csv"), index=False)
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

# ---- Go-live gate (Amendment 3). Four pre-registered looks with O'Brien-Fleming boundaries
# (K = 4, two-sided alpha 0.05) on the NW t of the fund book's weekly return in excess of cash,
# after model costs. Between looks the verdict does not change, except for a risk halt.
LOOKS = {13: 4.049, 26: 2.863, 39: 2.337, 52: 2.024}
CH_LOOKS = {13: 5.442, 26: 3.848, 39: 3.142, 52: 2.721}     # same design at alpha 0.05/7 (seven challengers, Amendment 5)


def alpha_t(y, Fx, cols):
    """NW t of the intercept of y on factor columns (weeks aligned); nan if too short."""
    d = pd.concat([y.rename("y"), Fx[cols]], axis=1, join="inner").dropna()
    if len(d) < len(cols) + 4:
        return np.nan
    X_ = np.column_stack([np.ones(len(d))] + [d[c] for c in cols])
    b_ = np.linalg.lstsq(X_, d["y"].to_numpy(), rcond=None)[0]
    return nw_t(d["y"].to_numpy() - X_[:, 1:] @ b_[1:])
EXEC = os.path.join(base, "execution")
books_ok = {os.path.basename(d): json.load(open(os.path.join(d, "book.json"))).get("status") in ("ok", "degraded_hold")
            for d in sorted(glob.glob(os.path.join(base, "20*"))) if os.path.exists(os.path.join(d, "book.json"))}
first = min([a for a, ok in books_ok.items() if ok], default=None)
Pe = R[R.book == "fund"].set_index("asof")["excess"].sort_index() if len(R) else pd.Series(dtype=float, index=pd.Index([], dtype=str))
Pe = Pe[Pe.index >= first] if first else Pe.iloc[:0]
n = len(Pe)
Z = nw_t(Pe) if n >= 3 else np.nan
Pn = R.pivot_table(index="asof", columns="book", values="net") if len(R) else pd.DataFrame()
dq = nw_t((Pn["fund"] - Pn["quant"]).dropna()) if {"fund", "quant"} <= set(Pn) else np.nan
xs_t = nw_t(X.b_analyst) if len(X) else np.nan
weeks = [a for a in books_ok if first and a >= first and pd.Timestamp(a) + pd.Timedelta(days=8, hours=23) <= now]
on_time = np.mean([books_ok[a] for a in weeks]) if weeks else np.nan
exs = {a: json.load(open(os.path.join(base, a, "execution.json"))) for a in weeks if os.path.exists(os.path.join(base, a, "execution.json"))}
executed = np.mean([exs.get(a, {}).get("status") == "submitted" and (exs[a].get("reconciled") or {}).get("n_not_filled", 1) == 0
                    for a in weeks]) if weeks else np.nan
fills = pd.read_csv(os.path.join(EXEC, "fills.csv")) if os.path.exists(os.path.join(EXEC, "fills.csv")) else pd.DataFrame()
slip = float(fills.loc[fills["leg"] != "flatten", "slip_bp"].abs().median()) if len(fills) else np.nan
halted = os.path.exists(os.path.join(base, "HALT"))
ops_ok = bool(on_time >= 0.9 and executed >= 0.9 and slip <= 10)
look = max([L for L in LOOKS if n >= L], default=None)
Fx = F.set_index("asof") if len(F) else pd.DataFrame(columns=["spy", "rev1w"])
Px = R.pivot_table(index="asof", columns="book", values="excess") if len(R) else pd.DataFrame()
promote = []
if look:                                            # the verdict uses exactly the first `look` weeks
    cut = Pe.index[look - 1]
    Z_l = nw_t(Pe.iloc[:look])
    A_l = alpha_t(Pe.iloc[:look], Fx, ["spy", "rev1w"])          # Amendment 4: alpha net of SPY and reversal
    dq_l = alpha_t((Pn["fund"] - Pn["quant"]).dropna().loc[:cut], Fx, ["rev1w"]) if {"fund", "quant"} <= set(Pn) else np.nan
    xs_l = nw_t(X.set_index("asof").b_analyst_adj.loc[:cut]) if len(X) and "b_analyst_adj" in X else np.nan
    mean_l = Pe.iloc[:look].mean()
    for k in CHALLENGERS:                           # promotion: challenger - champion at the challenger boundary
        if k in Px:
            t_k = nw_t((Px[k] - Px["fund"]).dropna().loc[first:cut])
            if t_k >= CH_LOOKS[look]:
                promote.append(f"{k} (t {t_k:.2f})")
if halted:
    verdict = "HALTED: a risk stop fired (see fund_state/live/HALT). Review, then resume by hand."
elif look and min(Z_l, dq_l, xs_l) <= -2:
    verdict = f"STOP (look at {look} weeks): the fund is significantly worse than cash, than the quant book after reversal, or its scores predict the wrong way."
elif look and Z_l >= LOOKS[look] and A_l >= LOOKS[look] and ops_ok:
    verdict = f"GO (look at {look} weeks): t {Z_l:.2f} and alpha t {A_l:.2f} both cross {LOOKS[look]:.2f}, and operations pass."
elif look == 52:
    verdict = ("NO-GO at 52 weeks: no boundary crossed, so no real money. The paper record continues to the "
               "104-week decision of Protocol 6.")
elif look and ops_ok and mean_l > 0:
    verdict = f"GO-SMALL allowed (look at {look} weeks): operations pass, no stop, positive mean. Tuition capital only."
else:
    verdict = f"CONTINUE ({n} weeks scored; next look at {min([L for L in LOOKS if L > n], default='-')} weeks)."
g = [f"# Go-live gate ({MODE})", "", f"**{verdict}**", "",
     (f"At the {look}-week look: excess t {Z_l:.2f}, alpha t (SPY, rev1w) {A_l:.2f}, fund − quant alpha t (rev1w) {dq_l:.2f}, "
      f"adjusted score slope t {xs_l:.2f}. Challengers promoted: {', '.join(promote) or 'none'}. "
      "The rows below are running values; only a look changes the verdict." if look else
      "No look yet. The rows below are running values and change no decision."), "",
     "| item | value | rule |", "|---|---:|---|",
     f"| weeks scored since first live book ({first}) | {n} | looks at 13 / 26 / 39 / 52 |",
     f"| fund excess return, mean %/wk | {Pe.mean() * 100 if n else float('nan'):.3f} | after 5 bp/side and cash |",
     f"| NW t (lags 2) | {Z:.2f} | GO if ≥ {LOOKS[look] if look else LOOKS[13]:.2f} at this look; STOP if ≤ −2 |",
     f"| fund − quant NW t | {dq:.2f} | STOP if ≤ −2 |",
     f"| analyst-score slope NW t | {xs_t:.2f} | adjusted version: STOP if ≤ −2 |",
     f"| decisions on time | {on_time:.0%} | ≥ 90% |",
     f"| weeks fully executed | {executed:.0%} | ≥ 90% |",
     f"| median abs slippage vs close | {slip:.1f} bp | ≤ 10 bp |",
     f"| risk halt | {'yes' if halted else 'no'} | 10% drawdown or 5% weekly loss on broker NAV |"]
nav_p = os.path.join(EXEC, "nav.csv")
if os.path.exists(nav_p) and n:
    N_ = pd.read_csv(nav_p)
    g += ["", f"Broker (paper) NAV {N_['equity'].iloc[-1]:,.0f} vs {N_['equity'].iloc[0]:,.0f} at the start of its history; "
          f"model fund net cumulative {((1 + Pn['fund'].fillna(0)).prod() - 1) * 100:.2f}%."]
open(os.path.join(OUT, "gate.md"), "w").write("\n".join(g) + "\n")
if len(Px):
    g += ["", "Challengers (shadow, never traded): excess return minus the fund's, %/wk, running",
          "| book | weeks | mean diff | NW t | promotion boundary at next look |", "|---|---:|---:|---:|---:|"]
    nxt = min([L for L in LOOKS if L > n], default=52)
    for k in CHALLENGERS:
        if k in Px:
            d_ = (Px[k] - Px["fund"]).dropna()
            d_ = d_[d_.index >= first] if first else d_
            g.append(f"| {k} | {len(d_)} | {d_.mean() * 100 if len(d_) else float('nan'):.3f} | {nw_t(d_):.2f} | {CH_LOOKS[nxt]:.2f} |")
json.dump({"verdict": verdict.split(" ")[0].rstrip(":"), "n": n, "t": Z, "look": look, "ops_ok": ops_ok, "promote": promote},
          open(os.path.join(OUT, "gate.json"), "w"), default=float)
print("\n".join(g))
