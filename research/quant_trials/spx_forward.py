"""Forward S&P 500 paper books (PREREG_quant_transformers.md Amendment 4). Never traded.

    python spx_forward.py weekly [--asof YYYY-MM-DD] [--dry]   # score the Thursday, write one append-only record
    python spx_forward.py ledger                               # books' P&L (% per year) and weekly ICs to date

Each record freezes everything a later reader needs: the models' tag, scores per name, every book's positions and
state, the sleeve's trend state and the DTB3 rate. The next week starts from the previous record's positions; a
recorded week is never recomputed. --dry writes to a scratch directory and allows past Thursdays (in-sample).
"""

import argparse
import glob
import io
import json
import os
import subprocess
import sys
import urllib.request

import numpy as np
import pandas as pd

import features as F
import panel as P
import spx_live as L
import sp500_transformers as X
import strategies as ST

REC = os.environ.get("SPX_REC", os.path.expanduser("~/.fund-runner/research/spx"))
DRY = os.path.join(P.CACHE, "spx_forward_dry")
BOOKS = {"fw_master_h5": ("master_h5", "S1", 5), "fw_master_h20": ("master_h20", "S1", 20),
         "fw_c2ft_h20": ("c2ft_h20", "S4", 20), "fw_ensemble": ("ensemble", "S1", 5),
         "fw_ridge_h20": ("ridge_h20", "S3", 20)}
ENSEMBLE = ("master_h5", "master_h20", "c2ft_h20")
MIN_COVERAGE = 0.95


def latest_models():
    tags = sorted(glob.glob(os.path.join(X.LIVE_MODELS, "live_*")))
    for t in reversed(tags):                                           # newest complete set
        need = [f"master_h5_seed{s}.pt" for s in X.SEEDS["master"]] + \
               [f"master_h20_seed{s}.pt" for s in X.SEEDS["master"]] + ["chronos2_ft"]
        if all(os.path.exists(os.path.join(t, n)) for n in need):
            return t
    sys.exit(f"no complete live model set under {X.LIVE_MODELS}")


def chronos_dir(tag):
    """The fine-tuned pipeline saved by chronos_finetune (its last checkpoint directory)."""
    base = os.path.join(tag, "chronos2_ft")
    cands = sorted(glob.glob(os.path.join(base, "**", "config.json"), recursive=True))
    if not cands:
        sys.exit(f"no Chronos-2-ft checkpoint under {base}")
    return os.path.dirname(cands[-1])


def dtb3_at(day):
    """DTB3 on the last date before `day`, from FRED at first use (frozen in the record thereafter)."""
    with urllib.request.urlopen("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3", timeout=60) as r:
        s = pd.read_csv(io.BytesIO(r.read()), na_values=".")
    s.columns = ["date", "v"]
    s = s.dropna().assign(date=lambda x: pd.to_datetime(x.date)).set_index("date")["v"] / 100
    s = s[s.index < day]
    if (day - s.index[-1]).days > 10:
        raise RuntimeError(f"DTB3 stale: last {s.index[-1].date()} for {day.date()}")
    return float(s.iloc[-1]), str(s.index[-1].date())


def records(path):
    return sorted(glob.glob(os.path.join(path, "spx_*.json")))


def zs(v):
    m = np.isfinite(v)
    out = np.full_like(v, np.nan)
    if m.sum() > 1:
        out[m] = (v[m] - v[m].mean()) / v[m].std()
    return out


def scores_at(d, t, tag):
    """Every model's score at session t, plus Chronos-2's q10-q90 width; coverage per model."""
    from chronos import Chronos2Pipeline
    M, sector = X.market(d), X.sectors(d)
    sc = {}
    for m in ("master_h5", "master_h20"):
        runs = [X.master_predict(d, M, os.path.join(tag, f"{m}_seed{s}.pt"), [t])[t] for s in X.SEEDS["master"]]
        sc[m] = np.nanmean(runs, 0)
    pipe = Chronos2Pipeline.from_pretrained(chronos_dir(tag), device_map=str(X.device()))
    pipe.model.eval()
    w = {}
    cs = X.chronos_scores(d, [t], sector, pipe=pipe, widths=w)
    sc["c2ft_h20"] = cs[20][t]
    year = int(os.path.basename(tag).split("_")[1][:4]) + 1            # the refit year train_final used
    for h in X.HS:                                                     # ridge: refit on the same rows as the models
        tr, va, train, _ = X.windows(d["S"], year, h)
        sc[f"ridge_h{h}"] = X.ridge_fit_predict(d, d[f"y{h}"], tr, va, train, [t])[0][t]
    zz = np.stack([zs(sc[k]) for k in ENSEMBLE])
    sc["ensemble"] = np.where(np.isfinite(zz).all(0), zz.mean(0), np.nan)    # only names all three members score
    return sc, w[20][t]


def _vec(dct, names):
    ix = {n: i for i, n in enumerate(names)}
    v = np.zeros(len(names))
    for n, x in dct.items():
        v[ix[n]] = x
    return v


def period(d, a, b):
    """Holding returns from close(a+1) to close(b+1) between two records, or None if not yet observed."""
    S = d["S"]
    t, t2 = (int(np.searchsorted(S, pd.Timestamp(r["asof"]))) for r in (a, b))
    if t2 + 2 > len(S):
        return None
    lr = np.log1p(np.nan_to_num(d["r"][t + 2: t2 + 2])).sum(0)
    lm = float(np.log1p(np.nan_to_num(d["rm"][t + 2: t2 + 2])).sum())
    return np.expm1(lr), float(np.expm1(lm)), (S[t2 + 1] - S[t + 1]).days


def book_return(d, a, b, bk):
    """A book's return over one holding period, net of the turnover cost into the next record's positions."""
    names = list(d["names"])
    R, Rm, days = period(d, a, b)
    v, nb = a["books"][bk], b["books"][bk]
    w, w2 = _vec(v["weights"], names), _vec(nb["weights"], names)
    dw = float(np.abs(w2 - w).sum() + abs(nb["w_spy"] - v["w_spy"]))
    return float((w * np.nan_to_num(R)).sum() + v["w_spy"] * Rm) - ST.COST * dw, Rm, days, float(w.sum()) + v["w_spy"], dw


def expected_thursday(today=None):
    """The latest NYSE Thursday session strictly before `today` (UTC date): the decision this run must record."""
    import pandas_market_calendars as mcal
    today = pd.Timestamp(today or pd.Timestamp.now(tz="UTC").date())
    v = mcal.get_calendar("NYSE").valid_days(start_date=today - pd.Timedelta(days=14), end_date=today - pd.Timedelta(days=1))
    v = pd.DatetimeIndex(pd.to_datetime(v).tz_localize(None).normalize())
    th = v[v.weekday == 3]
    return th[-1] if len(th) else None


def weekly(asof=None, dry=False):
    out = DRY if dry else REC
    if asof is None:                                                   # scheduled run: the calendar says which Thursday
        exp = expected_thursday()
        if exp is None or os.path.exists(os.path.join(out, f"spx_{exp.date()}.json")):
            print(f"nothing to record: last Thursday session {exp.date() if exp is not None else '-'} already recorded "
                  "(or a holiday week)")
            return None
        asof = str(exp.date())
    d = L.build()
    S = d["S"]
    if pd.Timestamp(asof) not in S:                                    # coverage vs expectation (CLAUDE.md rule 3)
        sys.exit(f"prices for {asof} are missing (data to {S[-1].date()}): no record written")
    tag = latest_models()
    trained_to = pd.Timestamp(os.path.basename(tag).split("_")[1])
    t = int(np.searchsorted(S, pd.Timestamp(asof)))
    if S[t].weekday() != 3:
        sys.exit(f"{asof}: not a Thursday session in the data")
    if S[t] <= trained_to and not dry:
        sys.exit(f"{S[t].date()} is inside the models' training data (to {trained_to.date()}): use --dry")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"spx_{S[t].date()}.json")
    if os.path.exists(path):
        sys.exit(f"{path} exists: records are append-only")
    chain = [json.load(open(p)) for p in records(out) if os.path.basename(p) < os.path.basename(path)]
    prev = chain[-1] if chain else None
    names = list(d["names"])
    elig = d["elig"][t]
    expected = int((elig & np.isfinite(d["e"][max(0, t - 59): t + 1]).all(0)).sum())
    sc, width = scores_at(d, t, tag)
    cov = {k: int(np.isfinite(v).sum()) for k, v in sc.items()}
    # members without 60 days of prices: listed, never silently dropped
    members = L.current_members()
    excluded = sorted(n for n in members if n not in names or not np.isfinite(d["e"][max(0, t - 59): t + 1,
                                                                                     names.index(n)]).all())
    spy = pd.Series(d["spy"])
    ma = float(spy.rolling(ST.TREND, min_periods=ST.TREND).mean().iloc[t])
    s = ST.UP if d["spy"][t] > ma else ST.DOWN
    rate, rate_date = (prev["dtb3"], prev["dtb3_date"]) if (prev and dry) else dtb3_at(S[t])
    vol = ST.vol60(d)[t]
    beta = np.nan_to_num(d["beta"][t], nan=1.0)
    books = {}
    for b, (m, strat, h) in BOOKS.items():
        pb = prev["books"][b] if prev else None
        pw = np.array([pb["base"].get(n, 0.0) for n in names]) if pb else None
        ok = np.isfinite(sc[m]) & elig
        base = ST.targets(sc[m], ok, pw, strat, vol, h)
        hist = list(pb["hist"]) if pb else []
        if strat == "S4" and len(chain) >= 2:
            # the last complete week (previous two records), unscaled. Live lags the backtest by one week: at a
            # Thursday decision the Friday close that ends the newest period is not yet known (Amendment 4).
            r_ = book_return(d, chain[-2], chain[-1], b)[0]
            hist.append(r_ / chain[-2]["books"][b]["scale"] if chain[-2]["books"][b]["scale"] > 0 else 0.0)
        scale = 1.0
        if strat == "S4" and len(hist) >= ST.VOL_WEEKS:
            v = np.std(hist[-ST.VOL_WEEKS:], ddof=1) * np.sqrt(52)
            scale = min(ST.VOL_CAP, ST.VOL_TARGET / v) if v > 0 else ST.VOL_CAP
        w = base * scale
        books[b] = {"model": m, "strategy": strat, "h": h, "scale": scale, "hist": hist,
                    "weights": {n: float(x) for n, x in zip(names, w) if x != 0},
                    "base": {n: float(x) for n, x in zip(names, base) if x != 0},
                    "w_spy": -float((w * beta).sum())}
    rec = {"asof": str(S[t].date()), "data_end": str(S[-1].date()), "models": os.path.basename(tag),
           "code": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=P.ROOT, text=True).strip(),
           "dry": dry, "expected_names": expected, "coverage": cov, "excluded_members": excluded,
           "sleeve": {"spy": float(d["spy"][t]), "ma200": ma, "s": s}, "dtb3": rate, "dtb3_date": rate_date,
           "scores": {k: {n: round(float(x), 6) for n, x in zip(names, v) if np.isfinite(x)} for k, v in sc.items()},
           "c2ft_width_h20": {n: round(float(x), 6) for n, x in zip(names, width) if np.isfinite(x)},
           "books": books}
    json.dump(rec, open(path, "w"), indent=1)
    print(f"written {path}")
    bad = {k: v for k, v in cov.items() if v < MIN_COVERAGE * expected}
    print(json.dumps({"asof": rec["asof"], "expected": expected, "coverage": cov, "excluded": excluded,
                      "sleeve": rec["sleeve"], "dtb3": rate,
                      "books": {b: {"long": sum(x > 0 for x in v["weights"].values()),
                                    "short": sum(x < 0 for x in v["weights"].values()),
                                    "w_spy": round(v["w_spy"], 3), "scale": round(v["scale"], 3)}
                                for b, v in books.items()}}, indent=1))
    if bad:                                                            # fail loudly, after saving (CLAUDE.md 9)
        sys.exit(f"coverage below {MIN_COVERAGE:.0%} of {expected}: {bad}")
    return path


def ledger(path=None):
    """Per book: the weekly P&L of each record's positions (close(t+1) to the next record's close(t+1)) and, once a
    target window has matured, the weekly IC. Each realised row is computed once and frozen in ledger.json (prices
    are dividend-adjusted and revised later: CLAUDE.md rule 4); later runs only append. Writes ledger.json and SPX.md
    next to the records and returns (summary, P&L rows, IC rows)."""
    path = path or REC
    recs = [json.load(open(p)) for p in records(path)]
    lpath = os.path.join(path, "ledger.json")
    led = json.load(open(lpath)) if os.path.exists(lpath) else {"pl": [], "ic": []}
    have_pl = {(r["bk"], r["asof"]) for r in led["pl"]}
    have_ic = {(r["book"], r["asof"], r["h"]) for r in led["ic"]}
    d = L.build()
    S, names = d["S"], list(d["names"])
    ix = {n: i for i, n in enumerate(names)}
    stamp = str(S[-1].date())
    for a, b in zip(recs[:-1], recs[1:]):
        if period(d, a, b) is None:
            break
        s = a["sleeve"]["s"]
        for bk in a["books"]:
            if (bk, a["asof"]) in have_pl:
                continue
            book, Rm, days, net, dw = book_return(d, a, b, bk)
            mrate = (a["dtb3"] + ST.MARGIN_SPREAD) * days / 360
            total = s * Rm - ST.COST * abs(b["sleeve"]["s"] - s) + book - max(s + net - 1, 0) * mrate
            t, t2 = (int(np.searchsorted(S, pd.Timestamp(r["asof"]))) for r in (a, b))
            led["pl"].append({"bk": bk, "asof": a["asof"], "to": b["asof"], "start": str(S[t + 1].date()),
                              "end": str(S[t2 + 1].date()), "book": book, "total": total, "spy": Rm, "s": s,
                              "s_next": b["sleeve"]["s"], "net": net, "turnover": dw, "mrate": mrate, "days": days,
                              "computed_with_data_to": stamp})
    for r in recs:
        t = int(np.searchsorted(S, pd.Timestamp(r["asof"])))
        rec_only = {f"rec_ridge_h{h}": {"model": f"ridge_h{h}", "h": h} for h in (5, 10)}   # recorded, not booked
        for bk, v in {**r["books"], **rec_only}.items():
            for hh in (sorted({v["h"], 5, 20}) if bk in r["books"] else [v["h"]]):
                if (bk, r["asof"], hh) in have_ic or t + 1 + hh >= len(S):
                    continue
                y = d[f"y{hh}"][t]
                sc = np.full(len(names), np.nan)
                for n, x in r["scores"][v["model"]].items():
                    sc[ix[n]] = x
                ok = np.isfinite(sc) & np.isfinite(y)
                if ok.sum() > 30:
                    led["ic"].append({"book": bk, "asof": r["asof"], "h": hh, "n": int(ok.sum()),
                                      "ic": float(pd.Series(sc[ok]).rank().corr(pd.Series(y[ok]).rank())),
                                      "computed_with_data_to": stamp})
    json.dump(led, open(lpath, "w"), indent=1)
    pg = page(recs, led, stamp)
    json.dump(pg, open(os.path.join(path, "page.json"), "w"), indent=1, allow_nan=False)
    out = pd.DataFrame([{"book": b["key"], "weeks": b["weeks"], "cum_pct": _pc(b["cum"]), "pct_per_yr": _pc(b["ann"]),
                         "vs_spy_pct_yr": _pc(b["vs_spy"]), "vs_risk_matched_pct_yr": _pc(b["vs_rm"]),
                         "ic_weeks": b["ic"][str(b["h"])]["n"], "ic": b["ic"][str(b["h"])]["mean"],
                         "ic_t": b["ic"][str(b["h"])]["t"], "status": b["status"]} for b in pg["books"]])
    with open(os.path.join(path, "SPX.md"), "w") as f:
        f.write("# Forward S&P 500 paper books (PREREG_quant_transformers.md Amendment 4; never traded)\n\n"
                f"Records: {len(recs)} (first {pg['first'] or '-'}, last {pg['last'] or '-'}); prices to {stamp}. "
                "Book + the dynamic SPY sleeve, broker costs. Returns annualised (% per year) only from 26 weeks; the "
                "verdict is on weekly IC at each book's horizon (NW t), reviewed at 52 weeks; a book with IC < 0 and "
                "t < -1 at 26 weeks is retired.\n\n" + out.round(4).to_markdown(index=False) + "\n")
    print(out.round(4).to_string(index=False))
    return out, pd.DataFrame(led["pl"]), pd.DataFrame(led["ic"])


# ------------------------------------------------------------------------------------------- page (shadow page)
MIN_ANN, STOP_N, REVIEW_N, ALPHA = 26, 26, 52, 0.05
ROLE = {"fw_master_h5": "the only pre-registered pass", "fw_master_h20": "exploratory",
        "fw_c2ft_h20": "exploratory; represents the time-series cluster", "fw_ensemble": "exploratory; members chosen "
        "after seeing results", "fw_ridge_h20": "control"}
LABEL = {"fw_master_h5": "MASTER, 5-day", "fw_master_h20": "MASTER, 20-day", "fw_c2ft_h20": "Chronos-2 fine-tuned, 20-day",
         "fw_ensemble": "Ensemble of the three", "fw_ridge_h20": "Ridge on five price factors, 20-day (control)"}


def _pc(x):
    return None if x is None else x * 100


def _f(x):
    """JSON-safe float: NaN and infinities become null."""
    return None if x is None or not np.isfinite(x) else float(x)


def series_stats(total, spy, s, mrate, days, turnover=None):
    """strategies.stats in fractions (not %), on aligned weekly arrays; annualised figures only from MIN_ANN weeks.
    Annualising: (prod(1 + r)) ** (365.25 / sum(days)) - 1. Sharpe: weekly-equivalent r * 7 / days, mean / sd * sqrt(52).
    Max drawdown from the running peak (starting at 1). Risk-matched S&P: sbar * spy - max(sbar - 1, 0) * mrate, with
    sbar the mean sleeve over the same weeks."""
    total, spy, s, mrate, days = (np.asarray(v, float) for v in (total, spy, s, mrate, days))
    n = len(total)
    if not n:
        return {"weeks": 0, "cum": None, "ann": None, "vs_spy": None, "vs_rm": None, "sharpe": None, "max_dd": None,
                "turnover_ann": None}
    yrs = days.sum() / 365.25
    ann = lambda x: float(np.prod(1 + x) ** (1 / yrs) - 1)
    sbar = s.mean()
    rm = sbar * spy - max(sbar - 1, 0) * mrate
    v = np.cumprod(1 + total)
    dd = float((v / np.maximum.accumulate(np.concatenate([[1.0], v]))[1:] - 1).min())
    wk = total * 7 / days
    sd = wk.std(ddof=1) if n > 1 else 0.0
    full = n >= MIN_ANN
    return {"weeks": n, "cum": float(v[-1] - 1), "ann": ann(total) if full else None,
            "vs_spy": ann(total) - ann(spy) if full else None, "vs_rm": ann(total) - ann(rm) if full else None,
            "sharpe": float(wk.mean() / sd * np.sqrt(52)) if full and sd > 0 else None, "max_dd": dd,
            "turnover_ann": float(np.sum(turnover) / yrs) if (full and turnover is not None) else None}


def ic_stats(x, h):
    """Mean weekly IC, NW t with lag max(4, h - 1) (Amendment 4), one-sided normal p."""
    from scipy import stats as sps
    x = np.asarray(x, float)
    t = F.nw_t(x, max(4, h - 1)) if len(x) > 3 else np.nan
    return {"n": int(len(x)), "mean": _f(x.mean()) if len(x) else None, "t": _f(t),
            "p": _f(float(sps.norm.sf(t))) if np.isfinite(t) else None}


def page(recs, led, stamp):
    """Everything the shadow page shows, computed here once; the page only formats it."""
    pl, ic = pd.DataFrame(led["pl"]), pd.DataFrame(led["ic"])
    last = recs[-1] if recs else None
    out = {"generated": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "data_to": stamp,
           "records": len(recs), "first": recs[0]["asof"] if recs else None, "last": last["asof"] if last else None,
           "models": last["models"] if last else None,
           "policy": {"up": ST.UP, "down": ST.DOWN, "trend": ST.TREND, "cost_side": ST.COST,
                      "margin_spread": ST.MARGIN_SPREAD, "vol_target": ST.VOL_TARGET, "vol_cap": ST.VOL_CAP},
           "rules": {"min_weeks_annualised": MIN_ANN, "stop_weeks": STOP_N, "review_weeks": REVIEW_N, "alpha": ALPHA},
           "latest": None, "weeks": [], "lines": {"dates": [], "series": {}}, "bench": {}, "books": []}
    if last:
        out["latest"] = {"asof": last["asof"], "sleeve": last["sleeve"], "dtb3": last["dtb3"],
                         "dtb3_date": last["dtb3_date"], "expected_names": last["expected_names"],
                         "coverage": last["coverage"], "excluded": last["excluded_members"]}
    first_bk = next(iter(BOOKS))
    W = pl[pl.bk == first_bk].sort_values("asof") if len(pl) else pd.DataFrame()
    if len(W):                                                          # the weeks every book shares
        for bk in BOOKS:
            assert list(pl[pl.bk == bk].sort_values("asof")["asof"]) == list(W["asof"]), f"{bk}: weeks differ"
        out["weeks"] = W[["asof", "to", "start", "end", "days", "spy", "s", "s_next", "mrate"]].to_dict("records")
        spy, s, s2, mr, dy = (W[c].to_numpy(float) for c in ("spy", "s", "s_next", "mrate", "days"))
        sbar = float(s.mean())
        timing = s * spy - ST.COST * np.abs(s2 - s) - np.maximum(s - 1, 0) * mr
        rm = sbar * spy - max(sbar - 1, 0) * mr
        cum = lambda r: [0.0] + list(np.cumprod(1 + np.asarray(r, float)) - 1)
        out["lines"]["dates"] = [W["start"].iloc[0]] + list(W["end"])
        out["lines"]["series"] = {"spy": cum(spy), "risk_matched": cum(rm), "sleeve": cum(timing)}
        out["bench"] = {"sbar": sbar, "spy": series_stats(spy, spy, s, mr, dy),
                        "risk_matched": series_stats(rm, spy, s, mr, dy), "sleeve": series_stats(timing, spy, s, mr, dy)}
    ridge_ic = {}
    for h in X.HS:                                                      # the control's IC at every horizon
        key = "fw_ridge_h20" if h == 20 else f"rec_ridge_h{h}"
        g = ic[(ic.book == key) & (ic.h == h)].sort_values("asof") if len(ic) else pd.DataFrame()
        ridge_ic[h] = dict(zip(g["asof"], g["ic"])) if len(g) else {}
    books = []
    for bk, (m, strat, hb) in BOOKS.items():
        g = pl[pl.bk == bk].sort_values("asof") if len(pl) else pl
        st = series_stats(g.total, g.spy, g.s, g.mrate, g.days, g.turnover) if len(g) else series_stats([], [], [], [], [])
        ics = {}
        for h in sorted({hb, 5, 20}):
            gi = ic[(ic.book == bk) & (ic.h == h)].sort_values("asof") if len(ic) else pd.DataFrame()
            ics[str(h)] = ic_stats(gi.ic if len(gi) else [], h)
            common = [a for a in (gi["asof"] if len(gi) else []) if a in ridge_ic[h]]
            if bk != "fw_ridge_h20" and common:
                own = dict(zip(gi["asof"], gi["ic"]))
                ics[str(h)]["vs_ridge"] = _f(float(np.mean([own[a] - ridge_ic[h][a] for a in common])))
                ics[str(h)]["vs_ridge_weeks"] = len(common)
        gi = ic[(ic.book == bk) & (ic.h == hb)].sort_values("asof") if len(ic) else pd.DataFrame()
        x = gi.ic.to_numpy(float) if len(gi) else np.array([])
        if len(x) >= STOP_N:                                            # evaluated once, on the first 26 IC weeks
            s26 = ic_stats(x[:STOP_N], hb)
            status = "retired (stop rule)" if (s26["mean"] < 0 and s26["t"] is not None and s26["t"] < -1) else "running"
        else:
            status = f"running ({len(x)} of {STOP_N} IC weeks before the stop-rule check)"
        L = last["books"][bk] if last else None
        wts = sorted(L["weights"].items(), key=lambda kv: -kv[1]) if L else []
        cumser = [0.0] + list(np.cumprod(1 + g.total.to_numpy(float)) - 1) if len(g) else []
        if len(g):
            out["lines"]["series"][bk] = cumser
        books.append({"key": bk, "label": LABEL[bk], "role": ROLE[bk], "model": m, "strategy": strat, "h": hb, **st,
                      "ic": ics, "status": status, "positions": [{"t": t_, "w": w_} for t_, w_ in wts],
                      "w_spy": L["w_spy"] if L else None, "scale": L["scale"] if L else None,
                      "n_long": sum(w_ > 0 for _, w_ in wts), "n_short": sum(w_ < 0 for _, w_ in wts),
                      "gross_long": float(sum(w_ for _, w_ in wts if w_ > 0)),
                      "gross_short": float(sum(w_ for _, w_ in wts if w_ < 0)),
                      "weekly": g[["asof", "to", "start", "end", "book", "total", "turnover"]].to_dict("records")
                      if len(g) else []})
    # the 52-week review: Holm over the four non-control books on their first 52 IC weeks (one-sided)
    cand = []
    for b in books:
        if b["key"] == "fw_ridge_h20":
            continue
        gi = ic[(ic.book == b["key"]) & (ic.h == b["h"])].sort_values("asof") if len(ic) else pd.DataFrame()
        if len(gi) >= REVIEW_N:
            first = gi.iloc[:REVIEW_N]
            st52 = ic_stats(first.ic.to_numpy(float), b["h"])
            common = [(a, x) for a, x in zip(first["asof"], first["ic"]) if a in ridge_ic[b["h"]]]
            st52["vs_ridge"] = _f(float(np.mean([x - ridge_ic[b["h"]][a] for a, x in common]))) if common else None
            cand.append((b, st52))
    if len(cand) == len(books) - 1 and all(c[1]["p"] is not None for c in cand):
        order = sorted(cand, key=lambda c: c[1]["p"])                  # Holm step-down: max_j<=i min(1, (k-j+1) p_(j))
        k = len(order)
        run = 0.0
        for i, (b, st52) in enumerate(order):
            run = max(run, min(1.0, st52["p"] * (k - i)))
            beats = st52["vs_ridge"] is not None and st52["vs_ridge"] > 0
            b["review"] = {**st52, "p_holm": run, "beats_ridge": beats, "supported": bool(run < ALPHA and beats)}
    out["books"] = books
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("weekly", "ledger"))
    ap.add_argument("--asof")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.cmd == "weekly":
        weekly(a.asof, a.dry)
    else:
        ledger(DRY if a.dry else None)
