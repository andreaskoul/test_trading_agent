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
    sc["ensemble"] = np.nanmean(np.stack([zs(sc[k]) for k in ENSEMBLE]), 0)
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
    dw = np.abs(w2 - w).sum() + abs(nb["w_spy"] - v["w_spy"])
    return float((w * np.nan_to_num(R)).sum() + v["w_spy"] * Rm) - ST.COST * dw, Rm, days, float(w.sum()) + v["w_spy"]


def weekly(asof=None, dry=False):
    d = L.build()
    S = d["S"]
    tag = latest_models()
    trained_to = pd.Timestamp(os.path.basename(tag).split("_")[1])
    t = int(np.searchsorted(S, pd.Timestamp(asof))) if asof else int(np.where(S.weekday == 3)[0][-1])
    if t >= len(S) or S[t].weekday() != 3 or (asof and S[t] != pd.Timestamp(asof)):
        sys.exit(f"{asof}: not a Thursday session in the data")
    if S[t] <= trained_to and not dry:
        sys.exit(f"{S[t].date()} is inside the models' training data (to {trained_to.date()}): use --dry")
    out = DRY if dry else REC
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
            r_, *_ = book_return(d, chain[-2], chain[-1], b)
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
    """Per book: weekly P&L from each record's positions (close(t+1) to the next record's close(t+1)), the S4 state
    update, and IC once each target window has matured. Returns tables; nothing in a record is changed."""
    path = path or REC
    recs = [json.load(open(p)) for p in records(path)]
    if len(recs) < 2:
        print("fewer than two records: no realised week yet")
        return
    d = L.build()
    S, names = d["S"], list(d["names"])
    ix = {n: i for i, n in enumerate(names)}
    rows, ics = [], []
    for a, b in zip(recs[:-1], recs[1:]):
        if period(d, a, b) is None:
            break
        s = a["sleeve"]["s"]
        for bk in a["books"]:
            book, Rm, days, net = book_return(d, a, b, bk)
            mrate = (a["dtb3"] + ST.MARGIN_SPREAD) * days / 360
            total = s * Rm - ST.COST * abs(b["sleeve"]["s"] - s) + book - max(s + net - 1, 0) * mrate
            rows.append({"bk": bk, "asof": a["asof"], "book": book, "total": total, "spy": Rm, "s": s,
                         "mrate": mrate, "days": days})
    for r in recs:
        t = int(np.searchsorted(S, pd.Timestamp(r["asof"])))
        for bk, v in r["books"].items():
            for hh in sorted({v["h"], 5, 20}):
                y = d[f"y{hh}"][t]
                if t + 1 + hh >= len(S) or not np.isfinite(y).sum():
                    continue
                sc = np.full(len(names), np.nan)
                for n, x in r["scores"][v["model"]].items():
                    sc[ix[n]] = x
                ok = np.isfinite(sc) & np.isfinite(y)
                if ok.sum() > 30:
                    ics.append({"book": bk, "asof": r["asof"], "h": hh,
                                "ic": float(pd.Series(sc[ok]).rank().corr(pd.Series(y[ok]).rank()))})
    pl, ic = pd.DataFrame(rows), pd.DataFrame(ics)
    summ = []
    for bk, g in pl.groupby("bk"):
        n = len(g)
        st = ST.stats(g.assign(year=0, turnover=0.0))
        hb = BOOKS[bk][2]
        gi = ic[(ic.book == bk) & (ic.h == hb)].ic if len(ic) else pd.Series(dtype=float)
        summ.append({"book": bk, "weeks": n, "cum_pct": (np.prod(1 + g.total) - 1) * 100,
                     "pct_per_yr": st["book_sleeve_pct_yr"] if n >= 26 else np.nan,
                     "vs_spy_pct_yr": st["vs_spy_pct_yr"] if n >= 26 else np.nan,
                     "vs_risk_matched_pct_yr": st["vs_risk_matched_pct_yr"] if n >= 26 else np.nan,
                     "ic_weeks": len(gi), "ic": gi.mean() if len(gi) else np.nan,
                     "ic_t": F.nw_t(gi.values, max(X.HS[0] - 1, hb - 1)) if len(gi) > 3 else np.nan})
    out = pd.DataFrame(summ)
    print(out.round(4).to_string(index=False))
    return out, pl, ic


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
