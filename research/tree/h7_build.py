"""H7 build (PREREG Layer 3, Amendment 7): the inputs of the 2026 sealed test. Builds; never scores.

No step here computes a statistic that combines a 2026 prediction with a 2026 outcome. Checks are shapes, coverage
counts, correlations between prediction vectors, and anything on data up to 2025-12-31.

    python3 research/tree/h7_build.py status          # fetch status of .cache/tree/y2026
    QT_PY research/tree/h7_build.py sp_panel          # 1. S&P panel extended to the fetch date (quant-tf venv python)
    QT_PY research/tree/h7_build.py master 2026       # 2. MASTER 5-day refit, training through 2025 -> master_h5_2026.npy
    QT_PY research/tree/h7_build.py master 2025       #    fidelity: the 2025 refit (training through 2024), vs the October read
    python3 research/tree/h7_build.py broad_panel     # 3. broad panel extended to the fetch date
    python3 research/tree/h7_build.py trees 2026      # 4. broad trees refit -> trees_2026.npy + dollar-volume terciles
    python3 research/tree/h7_build.py trees 2025      #    fidelity: the 2025 refit vs the saved L3b read predictions
    python3 research/tree/h7_build.py weights         # 5. H7_WEIGHTS.json (k_a fixed 0.59, k_b by the equal-risk rule)

QT_PY = ~/.cache/quant-tf-venv/bin/python (torch). Outputs under .cache/tree/y2026/ and research/tree/H7_build/.
Nothing is written to the quant-tf cache.
"""
import glob
import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "3")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
QT = os.path.join(os.path.dirname(ROOT), "quant-tf")
QTR = os.path.join(QT, "research", "quant_trials")
sys.path.insert(0, HERE)
sys.path.insert(0, QTR)
Y26 = os.path.join(ROOT, ".cache", "tree", "y2026")
BROAD = os.path.join(ROOT, ".cache", "tree", "broad")
OUTD = os.path.join(HERE, "H7_build")
EXT_PX = os.path.join(Y26, "sp500_close_ext.parquet")
SP_PANEL = os.path.join(Y26, "sp_panel.npz")
BR_PANEL = os.path.join(Y26, "broad_panel.npz")
END25 = pd.Timestamp("2025-12-31")
MEMB = os.path.join(QT, "data", "raw", "stocks", "sp500_membership.csv")
CURRENT = os.path.join(QT, "data", "raw", "stocks", "sp500_current.csv")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def checks(key, val):
    """Append one check result to H7_build/CHECKS.json (the record BUILD.md is written from)."""
    p = os.path.join(OUTD, "CHECKS.json")
    allc = json.load(open(p)) if os.path.exists(p) else {}
    allc[key] = val
    json.dump(allc, open(p, "w"), indent=1, default=float)
    log(key, json.dumps(val, default=float)[:3000])


# ------------------------------------------------------------------------------------------------ data
def fetch_end():
    """Exclusive bound on the sessions kept: the day after the `end` in _fetch_*.json. The coordinator set `end` to the
    last complete session (2026-11-12) after the first attempt (end 2026-11-13, before the US close) was refused (403)
    with no bar saved; a bar after `end`, if any, is dropped and counted."""
    ends = [json.load(open(p))["end"] for p in glob.glob(os.path.join(Y26, "_fetch_*.json"))]
    assert len(set(ends)) == 1, ends
    return pd.Timestamp(ends[0]) + pd.Timedelta(days=1)


def read_chunks(sub):
    files = sorted(glob.glob(os.path.join(Y26, sub, "*.parquet")))
    b = pd.concat([f for f in (pd.read_parquet(p) for p in files) if len(f)])
    b["close"], b["volume"] = b["close"].astype(np.float64), b["volume"].astype(np.float64)
    b["date"] = pd.to_datetime(b["date"])
    return b, len(files)


def status():
    for sub in ("chunks", "chunks_raw"):
        fs = glob.glob(os.path.join(Y26, sub, "*.parquet"))
        print(sub, len(fs), "files")
    for p in glob.glob(os.path.join(Y26, "_fetch_*.json")):
        print(os.path.basename(p), open(p).read())


def chain(old, new, last_old):
    """Extend `old` (dates <= last_old) with `new` after last_old, chain-linked per column: the scale is old / new
    on the last date <= last_old where both are finite. Returns (extended frame, anchor dates per column)."""
    new = new.reindex(columns=old.columns)
    o = old.loc[:last_old]
    n = new.reindex(o.index)
    both = (o.notna() & n.notna()).to_numpy()
    has = both.any(0)
    lastpos = len(o) - 1 - np.argmax(both[::-1], 0)
    ar = np.arange(both.shape[1])
    with np.errstate(all="ignore"):
        scale = np.where(has, o.to_numpy()[lastpos, ar] / n.to_numpy()[lastpos, ar], 1.0)
    after = new.loc[new.index > last_old]
    ext = pd.concat([o, after * scale])
    live = after.notna().to_numpy().any(0)
    anchor = {c: (str(o.index[lastpos[i]].date()) if has[i] else None) for i, c in enumerate(old.columns) if live[i]}
    return ext, anchor


# ------------------------------------------------------------------------------------------------ step 1
def sp_membership(last):
    """Point-in-time membership through the file's last row (2026-08-18), carried forward to `last`. The file's last
    row equals sp500_current.csv (checked), so no current-list row is appended."""
    m = pd.read_csv(MEMB, parse_dates=["date"])
    return m[m.date <= last].set_index("date")["tickers"].map(lambda s: set(s.split(",")))


def sp_panel():
    import sp500_test as T
    _build, _px, _end, _mem = T.build, T.PX, T.END, T.membership
    end = fetch_end()
    px0 = pd.read_parquet(T.PX)
    px0.index = pd.to_datetime(px0.index).tz_localize(None).normalize()
    b, nfiles = read_chunks("chunks")
    b = b[b.ticker.isin(px0.columns)]
    A = b.pivot_table(index="date", columns="ticker", values="close").sort_index()
    A = A[A.index < end]
    s26 = A["SPY"].dropna().index
    s26 = s26[s26 > END25]
    # calendar check on 2025: Alpaca SPY sessions vs yfinance sessions
    yf25 = px0.index[px0.index.year == 2025]
    al25 = A["SPY"].dropna().index
    al25 = al25[al25.year == 2025]
    cal = {"yf_2025_sessions": len(yf25), "alpaca_2025_sessions": len(al25),
           "only_yf": [str(d.date()) for d in yf25.difference(al25)], "only_alpaca": [str(d.date()) for d in al25.difference(yf25)],
           "sessions_2026": len(s26), "first_2026": str(s26[0].date()), "last_2026": str(s26[-1].date()),
           "fetch_end_meta": str((end - pd.Timedelta(days=1)).date()), "bars_after_fetch_end_dropped": int((b.date >= end).sum()),
           "adjusted_chunk_files": nfiles}
    # seam check on 2025 only: per-name correlation of daily returns, Alpaca adjusted vs yfinance
    y = px0.loc[yf25].pct_change(fill_method=None)
    a = A.reindex(yf25).pct_change(fill_method=None)
    cors, nobs = {}, {}
    for c in px0.columns:
        if c not in a:
            continue
        m = y[c].notna() & a[c].notna()
        if m.sum() >= 20:
            cors[c] = float(np.corrcoef(y[c][m], a[c][m])[0, 1])
            nobs[c] = int(m.sum())
    cs = pd.Series(cors)
    seam = {"names_compared": int(len(cs)), "quantiles": {str(q): float(cs.quantile(q)) for q in (0, .001, .01, .05, .25, .5)},
            "below_0.99": {k: [round(v, 4), nobs[k]] for k, v in cs[cs < 0.99].sort_values().items()},
            "spy": cors.get("SPY")}
    # extend
    A26 = A.reindex(A.index[(A.index <= END25) | A.index.isin(s26)])
    ext, anchor = chain(px0, A26, END25)
    ext = ext.loc[ext.index.isin(px0.index) | ext.index.isin(s26)]
    # no anchor = no yfinance close at all in the panel (the October download got nothing for the symbol; Alpaca's
    # bars under that symbol are partial, e.g. renamed tickers BK, MMC): the name stays without prices, as it was
    unanchored = sorted(c for c, v in anchor.items() if v is None)
    ext.loc[ext.index > END25, unanchored] = np.nan
    e26 = ext.loc[s26].drop(columns="SPY")
    gaps = {}
    for c in e26.columns[e26.notna().any()]:
        v = e26[c].notna().to_numpy()
        a_, b_ = np.argmax(v), len(v) - 1 - np.argmax(v[::-1])
        if (~v[a_:b_ + 1]).any():
            gaps[c] = int((~v[a_:b_ + 1]).sum())
    mem = sp_membership(ext.index.max())
    cur = set(pd.read_csv(CURRENT)["Symbol"].astype(str))
    last_row = mem.iloc[-1]
    members26 = set().union(*mem[mem.index > END25].values) | set(mem[mem.index <= END25].iloc[-1])
    notpanel = sorted(members26 - set(px0.columns))
    has26 = ext.loc[s26].notna().any()
    memb = {"file_last_date": str(mem.index.max().date()), "file_rows_2026": int((mem.index > END25).sum()),
            "last_row_equals_sp500_current": last_row == cur, "carried_forward_from": str(mem.index.max().date()),
            "names_member_in_2026_not_in_panel_no_prices": notpanel,
            "panel_names_with_2026_prices": int(has26.drop("SPY").sum()),
            "anchors_not_2025_12_31": {k: v for k, v in anchor.items() if v != "2025-12-31"},
            "unanchored_names_left_without_2026_prices": unanchored,
            "unanchored_that_are_2026_members": sorted(set(unanchored) & members26),
            "anchored_names_with_missing_sessions_inside_their_2026_span": gaps,
            "names_with_2026_prices_stopping_before_last_session": int((e26.notna().any() & e26.iloc[-1].isna()).sum())}
    # members on the last 2026 session without a 2026 price
    lastmem = mem.reindex(s26, method="ffill").iloc[-1]
    memb["members_last_session_in_panel_without_price_last_session"] = sorted(
        t for t in lastmem if t in ext.columns and not np.isfinite(ext.at[s26[-1], t]))
    ext.to_parquet(EXT_PX)
    # build on the extended prices by patching (as spx_live.py does), then the original build for the comparison
    T.PX, T.END, T.membership = EXT_PX, ext.index.max(), lambda: sp_membership(ext.index.max())
    d = _build()
    T.PX, T.END, T.membership = _px, _end, _mem
    d0 = _build()
    n0 = len(d0["S"])
    assert (d["S"][:n0] == d0["S"]).all() and d["names"] == d0["names"]
    eq = {}
    for k, v in d0.items():
        if not isinstance(v, np.ndarray) or k == "S":
            continue
        v1 = d[k][:n0]
        if k in ("y5", "y10", "y20"):
            f0 = np.isfinite(v)
            same = np.array_equal(v[f0], v1[f0])
            # rows whose target window runs into 2026: NaN in the original, finite now (counted, never looked at)
            newly = (~f0) & np.isfinite(v1)
            rows_new = np.where(newly.any(1))[0]
            eq[k] = {"equal_where_original_finite": bool(same), "cells_finite_only_in_extended": int(newly.sum()),
                     "rows_with_such_cells": [str(d0["S"][i].date()) for i in rows_new]}
        else:
            same = np.array_equal(v, v1, equal_nan=v.dtype.kind == "f")
            r = {"equal": bool(same)}
            if not same and v.dtype.kind == "f":
                r["max_abs_diff"] = float(np.nanmax(np.abs(v.astype(np.float64) - v1)))
                r["cells_nan_mismatch"] = int((np.isnan(v) != np.isnan(v1)).sum())
            eq[k] = r
    S = d["S"]
    th = np.where((S.weekday == 3) & (S > END25))[0]
    cov = {"sessions": [str(S[0].date()), str(S[-1].date()), len(S)], "names": len(d["names"]),
           "thursdays_2026": len(th),
           "eligible_per_2026_thursday": {"min": int(d["elig"][th].sum(1).min()), "max": int(d["elig"][th].sum(1).max())},
           "eligible_with_all_Z_per_2026_thursday_min": int((d["elig"][th] & np.isfinite(d["Z"][th]).all(-1)).sum(1).min())}
    arrs = {k: v for k, v in d.items() if isinstance(v, np.ndarray) and k != "S"}
    np.savez(SP_PANEL, S=np.asarray(S.values), names=np.array(d["names"]), **arrs)
    checks("step1_calendar", cal)
    checks("step1_seam_2025", seam)
    checks("step1_membership", memb)
    checks("step1_equal_to_original_build_le_2025", eq)
    checks("step1_coverage", cov)


def load_sp():
    z = np.load(SP_PANEL, allow_pickle=False)
    d = {k: z[k] for k in z.files if k not in ("S", "names")}
    d["S"] = pd.DatetimeIndex(z["S"])
    d["names"] = [str(n) for n in z["names"]]
    return d


# ------------------------------------------------------------------------------------------------ step 2
def master(year):
    import torch
    torch.set_num_threads(3)
    import sp500_test as T
    import sp500_transformers as X
    d = load_sp() if year == 2026 else T.build()        # 2025 fidelity: the original build (equal <= 2025, step 1)
    S, M = d["S"], X.market(d)
    cfg, seeds = X.FINAL["master_h5"], X.SEEDS["master"]
    z = np.load(os.path.join(QT, ".cache", "quant_trials", "sp500_tf_master_h5.npz"))
    assert json.loads(str(z["meta"]))["chosen"]["settings"] == cfg
    tr, va, train, q = X.windows(S, year, 5)
    y = d["y5"].astype(np.float64).copy()
    y[train[-1] + 1:] = np.nan                          # no target after the training window can be read
    days = X.thursdays(S, np.where(S.year == year)[0])
    sd = os.path.join(Y26, "master_seeds")
    os.makedirs(sd, exist_ok=True)
    runs, info = [], {}
    for s in seeds:
        p = os.path.join(sd, f"{year}_seed{s}.npy")
        if not os.path.exists(p):
            sc, inf = X.master_fit_predict(d, y, tr, va, days, cfg, s, M)
            np.save(p, sc[days].astype(np.float32))
            json.dump(inf, open(p + ".json", "w"), default=float)
            log("seed", s, inf)
        runs.append(np.load(p).astype(np.float64))
        info[s] = json.load(open(p + ".json"))
    with np.errstate(all="ignore"):
        pred = np.full((len(S), len(d["names"])), np.nan)
        pred[days] = np.nanmean(runs, 0)
    meta = {"year": year, "cfg": cfg, "seeds": list(seeds), "train_rows": [str(S[train[0]].date()), str(S[train[-1]].date())],
            "fit_rows": [str(S[tr[0]].date()), str(S[tr[-1]].date())], "val_rows": [str(S[va[0]].date()), str(S[va[-1]].date())],
            "pred_thursdays": len(days), "per_seed": info, "shape": list(pred.shape),
            "names_scored_per_thursday": {"min": int(np.isfinite(pred[days]).sum(1).min()),
                                          "max": int(np.isfinite(pred[days]).sum(1).max())}}
    if year == 2026:
        np.save(os.path.join(Y26, "master_h5_2026.npy"), pred.astype(np.float32))
        meta["seed_pair_rank_corr_mean"] = seed_corr(runs)
        checks("step2_master_2026", meta)
    else:
        ref = z["h5"].astype(np.float64)
        assert ref.shape == pred.shape
        rc = [pd.Series(pred[t]).corr(pd.Series(ref[t]), method="spearman") for t in days]
        meta.update({"rank_corr_with_october_read_2025": {"mean": float(np.nanmean(rc)), "min": float(np.nanmin(rc)),
                                                          "max": float(np.nanmax(rc))},
                     "seed_pair_rank_corr_mean": seed_corr(runs)})
        np.save(os.path.join(Y26, "master_h5_2025_refit.npy"), pred.astype(np.float32))
        checks("step2_master_2025_fidelity", meta)


def seed_corr(runs):
    out = []
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            out.append(np.nanmean([pd.Series(a).corr(pd.Series(b), method="spearman") for a, b in zip(runs[i], runs[j])]))
    return float(np.mean(out))


# ------------------------------------------------------------------------------------------------ step 3
def read_old(sub, excl):
    files = sorted(glob.glob(os.path.join(BROAD, sub, "*.parquet")))
    b = pd.concat([f for f in (pd.read_parquet(p) for p in files) if len(f)])
    b["close"], b["volume"] = b["close"].astype(np.float64), b["volume"].astype(np.float64)
    b = b[~b.ticker.isin(excl)]
    b["date"] = pd.to_datetime(b["date"])
    return b


def broad_panel():
    import panel_broad as PB
    import panel400 as P4
    import read3 as R3
    end = fetch_end()
    px5 = pd.read_parquet(EXT_PX)
    px5.index = pd.to_datetime(px5.index).tz_localize(None).normalize()
    spy = px5.pop("SPY")
    S = px5.index
    S0 = S[S <= END25]
    names5 = list(px5.columns)
    # the S&P 400 names already read (panel400.build's construction, on its own 2009-2025 sessions)
    ev = pd.read_parquet(os.path.join(P4.P8, "events.parquet"), columns=["ticker", "universe"])
    s400 = sorted(set(ev[ev.universe == "sp400"].ticker) - set(names5))
    b4 = pd.read_parquet(os.path.join(P4.P8, "alpaca_bars.parquet"), columns=["date", "ticker", "close"])
    b4 = b4[b4.ticker.isin(s400)]
    px4 = b4.pivot(index="date", columns="ticker", values="close").reindex(S0)
    read400 = list(px4.columns[px4.notna().sum() > 300])
    excl = set(names5) | set(read400) | {"SPY"}
    old = read_old("chunks", excl)
    oldr = read_old("chunks_raw", excl)
    new, _ = read_chunks("chunks")
    newr, _ = read_chunks("chunks_raw")
    new, newr = new[~new.ticker.isin(excl) & (new.date < end)], newr[~newr.ticker.isin(excl) & (newr.date < end)]
    c_old = old.pivot_table(index="date", columns="ticker", values="close").reindex(S0)
    c_new = new.pivot_table(index="date", columns="ticker", values="close").reindex(S)
    cols = sorted(set(c_old.columns) | set(c_new.columns))
    c_old = c_old.reindex(columns=cols)
    close, anchor = chain(c_old, c_new.reindex(columns=cols), END25)
    close = close.reindex(S)
    # unadjusted, eligibility only: never chain-linked; <= 2025 from the broad fetch, 2026 from the y2026 fetch
    rc = pd.concat([oldr[oldr.date <= END25], newr[newr.date > END25]])
    rclose = rc.pivot_table(index="date", columns="ticker", values="close").reindex(S).reindex(columns=cols)
    rvol = rc.pivot_table(index="date", columns="ticker", values="volume").reindex(S).reindex(columns=cols)
    elig_b = PB.eligibility(rclose, rvol)
    keep = elig_b.any(0)
    D0, isb0 = R3.load_panel()
    old_b = [n for n, f in zip(D0["names"], isb0) if f]
    kept = [c for c, k in zip(cols, keep) if k]
    newnames = sorted(set(kept) - set(old_b))
    lost = sorted(set(old_b) - set(kept))
    order = [c for c in old_b if c in set(kept)] + newnames           # the saved panel's order, then new names
    ci = pd.Index(cols)
    idx = ci.get_indexer(order)
    elig_b = elig_b[:, idx]
    closeb = close[order]
    dv_b = (rclose * rvol).rolling(PB.DV_WIN, min_periods=PB.DV_WIN).mean()[order].to_numpy()
    mem = sp_membership(S.max()).reindex(S, method="ffill")
    elig5 = np.array([[t in s for t in names5] for s in mem.values])
    px = pd.concat([px5, closeb], axis=1)
    elig = np.concatenate([elig5, elig_b], 1)
    D = P4.fields(px, spy, elig)
    D["names"] = names5 + order
    isb = np.array([False] * len(names5) + [True] * len(order))
    D["dv"] = np.concatenate([np.full((len(S), len(names5)), np.nan), dv_b], 1).astype(np.float32)
    D["y5_delist"] = PB.delist_target(D, isb)
    # check against the saved panel, dates <= 2025-12-31, on the saved panel's names
    n0 = len(D0["S"])
    assert (D["S"][:n0] == D0["S"]).all()
    j = pd.Index(D["names"]).get_indexer(D0["names"])
    eq = {"saved_names_missing_in_extended": lost, "new_broad_names_eligible_only_in_2026": len(newnames)}
    for k in ("elig", "Z", "valid", "r", "e", "beta", "rm", "spy", "dv", "y5", "y5_delist"):
        v0 = D0[k]
        v1 = D[k][:n0] if v0.ndim == 1 else D[k][:n0][:, j]
        if k in ("y5", "y5_delist"):
            f0 = np.isfinite(v0)
            newly = (~f0) & np.isfinite(v1)
            eq[k] = {"equal_where_saved_finite": bool(np.array_equal(v0[f0], v1[f0])),
                     "cells_finite_in_saved_nan_in_extended": int((f0 & ~np.isfinite(v1)).sum()),
                     "cells_finite_only_in_extended": int(newly.sum()),
                     "rows_with_such_cells": [str(D0["S"][i].date()) for i in np.where(newly.any(1))[0]]}
            if not eq[k]["equal_where_saved_finite"]:
                bad = f0 & np.isfinite(v1) & (v0 != v1)
                eq[k]["cells_differing"] = int(bad.sum())
                eq[k]["rows_differing"] = sorted({str(D0["S"][i].date()) for i in np.where(bad.any(1))[0]})[:20]
        else:
            same = np.array_equal(v0, v1, equal_nan=v0.dtype.kind == "f")
            r = {"equal": bool(same)}
            if not same and v0.dtype.kind == "f":
                r["max_abs_diff"] = float(np.nanmax(np.abs(v0.astype(np.float64) - v1)))
                r["cells_nan_mismatch"] = int((np.isnan(v0) != np.isnan(v1)).sum())
            elif not same:
                r["cells_differing"] = int((v0 != v1).sum())
            eq[k] = r
    th = np.where((S.weekday == 3) & (S > END25))[0]
    nb = D["elig"][th][:, isb].sum(1)
    cov = {"sessions": [str(S[0].date()), str(S[-1].date()), len(S)], "names": len(D["names"]), "broad_names": int(isb.sum()),
           "eligible_broad_per_2026_thursday": {"mean": float(nb.mean()), "min": int(nb.min()), "max": int(nb.max())},
           "eligible_sp500_per_2026_thursday_min": int(D["elig"][th][:, ~isb].sum(1).min()),
           "broad_anchor_not_2025_12_31": int(sum(1 for c in order if anchor.get(c) not in (None, "2025-12-31") and c in anchor)),
           "broad_with_2026_prices_no_anchor": int(sum(1 for c in order if c in anchor and anchor[c] is None))}
    arrs = {k: v for k, v in D.items() if isinstance(v, np.ndarray)}
    np.savez(BR_PANEL, S=np.asarray(S.values), names=np.array(D["names"]), isb=isb, **arrs)
    checks("step3_equal_to_saved_panel_le_2025", eq)
    checks("step3_coverage", cov)


def load_broad():
    z = np.load(BR_PANEL, allow_pickle=False)
    D = {k: z[k] for k in z.files if k not in ("S", "names", "isb")}
    D["S"] = pd.DatetimeIndex(z["S"])
    D["names"] = list(z["names"])
    return D, z["isb"]


def terciles(D, isb, rows):
    """Per row: 1, 2, 3 = dollar-volume tercile (63-session mean, unadjusted) among eligible broad names with a dv
    (3 = highest), as read3.extras; 0 = not an eligible broad name. H7b keeps terciles 2 and 3."""
    q = np.zeros((len(rows), len(isb)), np.int8)
    for i, t in enumerate(rows):
        e = D["elig"][t] & isb & np.isfinite(D["dv"][t])
        if e.sum():
            pr = pd.Series(D["dv"][t][e]).rank(pct=True).to_numpy()
            q[i, np.where(e)[0]] = np.where(pr < 1 / 3, 1, np.where(pr < 2 / 3, 2, 3))
    return q


# ------------------------------------------------------------------------------------------------ step 4
def trees(year):
    import harness as H
    from holdout2 import load_module
    D, isb = load_broad()
    model = load_module(os.path.join(HERE, "finalists", "D_hgb_mh", "model.py"), "h7_trees")
    te = H.train_end(D, year)
    p = H.walk_forward(model.fit_predict, seeds=(0, 1, 2), years=(year,), D=D)
    rows = H.thursdays(D, year)
    S = D["S"]
    pb = np.where(D["elig"] & isb[None, :], p, np.nan)
    meta = {"year": year, "train_end_row": str(S[te].date()), "last_target_end": str(S[te + 6].date()),
            "pred_thursdays": len(rows), "shape": list(p.shape),
            "broad_names_scored_per_thursday": {"min": int(np.isfinite(pb[rows]).sum(1).min()),
                                                "max": int(np.isfinite(pb[rows]).sum(1).max())}}
    if year == 2026:
        np.save(os.path.join(Y26, "trees_2026.npy"), p.astype(np.float32))
        q = terciles(D, isb, rows)
        np.savez(os.path.join(Y26, "trees_dv_tercile_2026.npz"), rows=rows, dates=np.asarray(S[rows].values),
                 names=np.array(D["names"]), tercile=q)
        meta["tercile_counts_per_thursday_min"] = {k: int((q == k).sum(1).min()) for k in (1, 2, 3)}
        # agreement of the two 2026 prediction vectors (no outcome involved)
        mh = os.path.join(Y26, "master_h5_2026.npy")
        if os.path.exists(mh):
            m = np.load(mh)
            spn = len(m[0])
            rc = [pd.Series(p[t][:spn]).corr(pd.Series(m[t]), method="spearman") for t in rows]
            meta["rank_corr_trees_vs_master_on_sp500_names_2026"] = float(np.nanmean(rc))
        checks("step4_trees_2026", meta)
    else:
        import read3 as R3
        D0, _ = R3.load_panel()
        ref = np.load(os.path.join(ROOT, ".cache", "tree", "read3_pred_L3b_candidate.npy")).astype(np.float64)
        j = pd.Index(D["names"]).get_indexer(D0["names"])
        a, b = p[rows][:, j], ref[rows]
        fin = np.isfinite(a) & np.isfinite(b)
        rc = [pd.Series(x).corr(pd.Series(y), method="spearman") for x, y in zip(a, b)]
        meta.update({"nan_pattern_equal": bool((np.isfinite(a) == np.isfinite(b)).all()),
                     "max_abs_diff_vs_saved_L3b_2025": float(np.abs(a[fin] - b[fin]).max()),
                     "rank_corr_vs_saved_L3b_2025": {"mean": float(np.nanmean(rc)), "min": float(np.nanmin(rc))}})
        np.save(os.path.join(Y26, "trees_2025_refit.npy"), p.astype(np.float32))
        checks("step4_trees_2025_fidelity", meta)


# ------------------------------------------------------------------------------------------------ step 5
def weights():
    import combo_check as CC
    import read3 as R3
    from holdout2 import load_module, rows_for
    COST = 14e-4
    F = CC.fund_weekly()
    M1 = load_module(os.path.join(HERE, "M1_dyntrade", "lib.py"), "m1lib_h7w")
    M1.COST = COST
    D, isb = R3.load_panel()
    p = np.load(os.path.join(ROOT, ".cache", "tree", "read3_pred_L3b_candidate.npy")).astype(np.float64)
    rows0 = rows_for(D, R3.YEARS)

    def book(top2):
        Ds = dict(D)
        el = D["elig"] & isb[None, :]
        if top2:
            q = terciles(D, isb, rows0)
            m = np.zeros_like(el)
            m[rows0] = q >= 2
            el = el & m
        Ds["elig"] = el
        Ds["y5"] = np.clip(D["y5"], -1.0, 1.0)
        s = np.where(Ds["elig"], p, np.nan)
        rows = np.array([t for t in rows0 if M1.mask(s, Ds, t).sum() >= 50])
        W = M1.build("decile", s, Ds, rows)
        net = np.asarray(M1.simulate(W, Ds, rows)["net"], float)
        return pd.Series(net, index=pd.DatetimeIndex(D["S"])[rows])
    out = {}
    for arm, top2 in (("H7a_all_eligible", False), ("H7b_top_two_dv_terciles", True)):
        B = book(top2)
        j = F.join(B.rename("broad"), how="inner")
        bk, b = j.wk_book.values, j.broad.values
        out[arm] = {"k_equal_risk_at_14bp": float(bk.std(ddof=1) / b.std(ddof=1)), "weeks": int(len(j)),
                    "period": [str(j.index[0].date()), str(j.index[-1].date())],
                    "sd_fund_stock_book_weekly": float(bk.std(ddof=1)), "sd_broad_book_weekly": float(b.std(ddof=1))}
    res = {"k_a": 0.59, "k_b": round(out["H7b_top_two_dv_terciles"]["k_equal_risk_at_14bp"], 4),
           "method": ("Equal-risk rule (combo_check.py): k = sd(weekly fund stock-book return) / sd(weekly broad book "
                      "net return), on the inner join of the two weekly series, 2020-2025 (spent data). Fund stock book: "
                      "combo_check.fund_weekly() wk_book (MASTER 5-day decile book, gross 0.6, 5 bp; per-period return "
                      "scaled to 7 days). Broad book: L3b candidate predictions (.cache/tree/read3_pred_L3b_candidate.npy), "
                      "M1 decile book, y5 clipped at +-1 (Amendment 5), 14 bp a unit traded, weeks with >= 50 names. "
                      "k_a = 0.59 is fixed by the registration (COMBO_CHECK.json equal-risk k, 0.5928 at 5 bp; 0.5926 "
                      "at 10 bp; 0.5921 at 20 bp). k_b: the same rule with the broad book restricted each week to "
                      "eligible broad names in dollar-volume terciles 2 and 3 (63-session mean of unadjusted close x "
                      "volume, ranked among eligible broad names with a dollar volume, as read3.extras)."),
           "detail": out, "computed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    json.dump(res, open(os.path.join(HERE, "H7_WEIGHTS.json"), "w"), indent=1)
    checks("step5_weights", res)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "status":
        status()
    elif cmd == "sp_panel":
        sp_panel()
    elif cmd == "master":
        master(int(sys.argv[2]))
    elif cmd == "broad_panel":
        broad_panel()
    elif cmd == "trees":
        trees(int(sys.argv[2]))
    elif cmd == "weights":
        weights()
