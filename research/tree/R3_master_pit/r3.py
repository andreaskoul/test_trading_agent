"""R3: survivorship bound on MASTER h5's 2020-2025 book (descriptive; reused 2020-2025 window). Plan: STATE.json.

    QT_PY research/tree/R3_master_pit/r3.py build        # P1-P4: repaired panel + checks -> .cache/tree/r3/panel_*.npz
    QT_PY research/tree/R3_master_pit/r3.py worker [min]  # P5: one fit worker (resumable; launch 4 via workers.sh)
    QT_PY research/tree/R3_master_pit/r3.py report       # P6-P7 -> RESULT.json

QT_PY = ~/.cache/quant-tf-venv/bin/python. quant-tf and L4 files are imported read-only.
"""
import fcntl
import glob
import json
import os
import sys
import time

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "3")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
QT = "/Users/apollogodofthesun/test_trading_agent/.claude/worktrees/quant-tf"
QTR = os.path.join(QT, "research", "quant_trials")
sys.path.insert(0, QTR)
sys.path.insert(0, os.path.join(TREE, "L4_arch"))
CACHE = os.path.join(ROOT, ".cache", "tree", "r3")
ALP = [os.path.join(ROOT, ".cache", "tree", "broad", "chunks"), os.path.join(ROOT, ".cache", "tree", "y2026", "chunks")]
END = pd.Timestamp("2025-12-31")
STATE = os.path.join(HERE, "STATE.json")
ARMS, YEARS, SEEDS = ("ORIG", "REPAIRED"), range(2020, 2026), (0, 1, 2, 3, 4)
LABEL = "reused 2020-2025 window; survivorship bound"
VERSION = "v2_"
os.makedirs(CACHE, exist_ok=True)


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), *a, flush=True)


def update_state(fn):
    with open(STATE + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        st = json.load(open(STATE))
        fn(st)
        st["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        json.dump(st, open(STATE + ".tmp", "w"), indent=1, default=float)
        os.replace(STATE + ".tmp", STATE)


def checks(key, val):
    p = os.path.join(HERE, "CHECKS.json")
    allc = json.load(open(p)) if os.path.exists(p) else {}
    allc[key] = val
    json.dump(allc, open(p, "w"), indent=1, default=float)
    log(key, json.dumps(val, default=float)[:1500])


# ------------------------------------------------------------------------------------------------ build
def build_from(px):
    """sp500_test.build() with the price frame passed in (code otherwise copied unchanged)."""
    import sp500_test as T
    px = px.copy()
    assert px.index.max() <= T.END
    spy = px.pop("SPY")
    S = px.index
    mem = T.membership().reindex(S, method="ffill")
    names = list(px.columns)
    elig = np.array([[t in s for t in names] for s in mem.values])
    close = px.values
    lp = np.log(px)
    r = px.pct_change().values
    rm = spy.pct_change().values
    sig = {"mom12_1": (lp.shift(20) - lp.shift(252)).values, "rev1m": -(lp - lp.shift(20)).values,
           "rev1w": -(lp - lp.shift(5)).values,
           "lowvol": -np.log(px).diff().rolling(60, min_periods=50).std().values,
           "high52": (px / px.rolling(252, min_periods=200).max()).values}
    spec = json.load(open(os.path.join(T.ROOT, "artefacts", "llm", "ridge_stocks.json")))
    Zraw = np.stack([sig[c] for c in spec["features"]], -1)
    Z = Zraw.copy()
    Z[~elig] = np.nan
    with np.errstate(all="ignore"):
        Z = (Z - np.nanmean(Z, 1, keepdims=True)) / np.nanstd(Z, 1, keepdims=True)
    frozen = Z @ np.asarray(spec["coef"])
    lo, hi = np.minimum(-2 * rm, 4 * rm)[:, None], np.maximum(-2 * rm, 4 * rm)[:, None]
    w = pd.DataFrame(np.clip(r, lo, hi), index=S)
    m = pd.Series(rm, index=S)
    beta = (2 / 3) * w.rolling(252, min_periods=200).cov(m).div(m.rolling(252, min_periods=200).var(), axis=0) \
        .fillna(1.0).values + 1 / 3
    cr = np.vstack([np.zeros((1, r.shape[1])), np.cumsum(np.nan_to_num(r), 0)])
    cm = np.concatenate([[0], np.cumsum(np.nan_to_num(rm))])
    raw = {}

    def resid(h):
        y = np.full(r.shape, np.nan)
        for d in range(len(S) - 1 - h):
            a, b = d + 2, d + 2 + h
            y[d] = (cr[b] - cr[a]) - beta[d] * (cm[b] - cm[a])
        valid = np.isfinite(close)
        ok = np.zeros_like(valid)
        ok[: len(S) - 1 - h] = valid[1 + h:] & valid[: len(S) - 1 - h]
        y[~(ok & elig)] = np.nan
        raw[h] = y.copy()
        with np.errstate(all="ignore"):
            return y - np.nanmean(y, 1, keepdims=True)
    e = r - np.vstack([np.full((1, r.shape[1]), np.nan), beta[:-1]]) * rm[:, None]
    d = {"S": S, "names": names, "Z": Z.astype(np.float32), "frozen": frozen, "y20": resid(20), "y5": resid(5),
         "y10": resid(10), "elig": elig, "e": e.astype(np.float32), "spy": spy.values, "rm": rm, "r": r,
         "beta": beta, "valid": np.isfinite(close)}
    return d, {"Zraw": Zraw, "y5raw": raw[5]}


ZV = {}


def read_alpaca(names):
    out = []
    for k, folder in enumerate(ALP):
        fs = sorted(glob.glob(os.path.join(folder, "*.parquet")))
        b = pd.concat([x for x in (pd.read_parquet(f) for f in fs) if len(x)])
        b = b[b.ticker.isin(names)].copy()
        ZV[folder] = int((b["volume"] <= 0).sum())
        b = b[b["volume"] > 0]                          # v2: a zero-volume bar is not a trade (SBNY after its halt)
        b["date"] = pd.to_datetime(b["date"])
        b["close"] = b["close"].astype(np.float64)
        out.append(b.pivot_table(index="date", columns="ticker", values="close").sort_index())
    return out


def corr_ret(a, b):
    ra, rb = a.pct_change(fill_method=None), b.pct_change(fill_method=None)
    m = ra.notna() & rb.notna()
    return (float(np.corrcoef(ra[m], rb[m])[0, 1]) if m.sum() >= 20 else None), int(m.sum())


def build():
    import sp500_test as T
    px0 = pd.read_parquet(T.PX)
    px0.index = pd.to_datetime(px0.index).tz_localize(None).normalize()
    S = px0.index
    d0, raw0 = build_from(px0)
    # P4 a: the copy equals the original build on every array
    ref = T.build()
    same = {}
    for k, v in ref.items():
        if isinstance(v, np.ndarray):
            same[k] = bool(np.array_equal(v, d0[k], equal_nan=v.dtype.kind == "f"))
    same["S"] = bool((ref["S"] == d0["S"]).all())
    same["names"] = ref["names"] == d0["names"]
    assert all(same.values()), same
    names = d0["names"]
    # P2: the missing set
    th = np.where((S.weekday == 3) & (S.year >= 2020))[0]
    el, y5 = d0["elig"][th], d0["y5"][th]
    miss = el & ~np.isfinite(y5)
    cnt = miss.sum(0)
    mset = [names[i] for i in np.where(cnt > 0)[0]]
    p2 = {"eligible_name_weeks_2020_2025": int(el.sum()), "missing_name_weeks": int(miss.sum()),
          "missing_names": len(mset), "coordinator_expected": [79, 11589, 152654]}
    assert (len(mset), int(miss.sum()), int(el.sum())) == (79, 11589, 152654), p2
    # source check: Alpaca vs yfinance on all panel names present in both (broad 2016-2025)
    br, y26 = read_alpaca(set(names) | {"SPY"})
    cs = {}
    for c in br.columns:
        if c in px0 and px0[c].notna().sum() > 100:
            v, n = corr_ret(px0[c].reindex(S), br[c].reindex(S))
            if v is not None and n >= 250:
                cs[c] = v
    cs = pd.Series(cs)
    src = {"names_compared_broad_vs_yf": int(len(cs)),
           "quantiles": {str(q): float(cs.quantile(q)) for q in (0, .01, .05, .1, .25, .5)},
           "share_above_0.999": float((cs > 0.999).mean()), "below_0.99": {k: round(v, 4) for k, v in cs[cs < 0.99].sort_values().items()}}
    # v2 (coordinator 2026-11-22): the targeted Alpaca fetch 2016-01-01..2024-12-31 for the 60 names with no or
    # 2025-only bars (.cache/tree/r3/alpaca_extra.parquet; sha256 in alpaca_extra.json), joined to the broad bars
    import hashlib
    xj = json.load(open(os.path.join(CACHE, "alpaca_extra.json")))
    xp = os.path.join(CACHE, "alpaca_extra.parquet")
    sha = hashlib.sha256(open(xp, "rb").read()).hexdigest()
    assert sha == xj["sha256"], (sha, xj["sha256"])
    xb = pd.read_parquet(xp)
    xb["date"] = pd.to_datetime(xb["date"])
    xb["close"] = xb["close"].astype(np.float64)
    ZV["alpaca_extra"] = {"rows": int((xb["volume"] <= 0).sum()), "by_ticker": xb[xb["volume"] <= 0].ticker.value_counts().to_dict()}
    xb = xb[xb["volume"] > 0]
    assert not xb.duplicated(["date", "ticker"]).any()
    ex = xb.pivot_table(index="date", columns="ticker", values="close").sort_index()
    ex = ex[ex.index <= pd.Timestamp("2024-12-31")]
    exc = {"sha256_ok": True, "tickers": int(ex.shape[1]), "requested": xj["requested"], "returned": xj["returned"],
           "missing": xj["missing"], "zero_volume_bars_dropped": ZV, "per_ticker_counts_match_json": all(int(ex[t].notna().sum()) + ZV["alpaca_extra"]["by_ticker"].get(t, 0) == xj["per_ticker"][t][2] for t in ex.columns if t in xj["per_ticker"]),
           "overlap_with_broad": sorted(set(ex.columns) & set(br.columns))}
    for t in exc["overlap_with_broad"]:
        exc.setdefault("overlap_corr", {})[t] = list(corr_ret(br[t], ex[t].reindex(br.index)))
    br = br.combine_first(ex) if not exc["overlap_with_broad"] else br.combine_first(ex)  # broad bar stands where both
    # identity check of the fetch on renamed tickers: old ticker's Alpaca history vs the successor's yfinance closes
    REN = {"FB": "META", "ANTM": "ELV", "ABC": "COR", "PKI": "RVTY", "WLTW": "WTW", "COG": "CTRA", "BLL": "BALL",
           "FBHS": "FBIN", "NLOK": "GEN", "CDAY": "DAY", "FLT": "CPAY", "PEAK": "DOC", "RE": "EG", "DISCA": "WBD",
           "VIAC": "PARA", "HFC": "DINO", "ADS": "BFH", "CTL": "LUMN", "ARNC": "HWM", "UTX": "RTX", "GPS": "GAP"}
    ren = {}
    mem0 = T.membership().reindex(S, method="ffill")
    for o, n_ in REN.items():
        if o in ex and n_ in px0:
            eo = np.array([o in s_ for s_ in mem0.values])       # the old ticker's own S&P span only
            span = S[eo] if eo.any() else S[:0]
            ren[f"{o}->{n_}"] = list(corr_ret(px0[n_].reindex(span), ex[o].reindex(span))) + ([str(span[0].date()), str(span[-1].date())] if len(span) else [])
    exc["rename_identity_ret_corr_vs_successor_yf"] = ren
    checks(VERSION + "extra_fetch_checks", exc)
    # P3: fill
    mem = T.membership().reindex(S, method="ffill")
    px = px0.copy()
    table, flagged = {}, {}
    for n in mset:
        el_n = np.array([n in s for s in mem.values])
        last_el = int(np.where(el_n)[0].max())
        cap = S[min(len(S) - 1, last_el + 10)]
        rec = {"missing_weeks": int(cnt[names.index(n)]), "eligible": [str(S[el_n].min().date()), str(S[last_el].date())]}
        a = br[n].dropna() if n in br else pd.Series(dtype=float, index=pd.DatetimeIndex([]))
        b = y26[n].dropna() if n in y26 else pd.Series(dtype=float, index=pd.DatetimeIndex([]))
        b = b[b.index <= END]
        rec["bars_after_cap_dropped"] = int((a.index > cap).sum() + (b.index > cap).sum())
        a, b = a[a.index <= cap], b[b.index <= cap]     # v2: cap before chaining (a later re-use of the ticker unread)
        if len(a) and len(b):                           # chain y2026 onto broad on the first common session
            common = a.index.intersection(b.index)
            if len(common):
                c_, nobs = corr_ret(a.reindex(common), b.reindex(common))
                rec["broad_vs_y26_ret_corr"] = [c_, nobs]
                if c_ is not None and c_ < 0.999:
                    flagged[n] = f"broad vs y2026 Alpaca return corr {c_:.4f}"
                scale = a[common[0]] / b[common[0]]
                al = pd.concat([a, b[b.index > a.index.max()] * scale])
            else:                                       # no common session: append, junction return checked
                al = pd.concat([a, b[b.index > a.index.max()]]).sort_index()
                jr = float(al[b.index[b.index > a.index.max()][0]] / a.iloc[-1] - 1) if (b.index > a.index.max()).any() else 0.0
                rec["junction_return_alpaca_extra_to_y26"] = [str(a.index.max().date()), jr]
                if abs(jr) > 0.15:
                    flagged[n] = f"junction return {jr:.3f} between fetches"
        else:
            al = a if len(a) else b
        if not len(al):
            rec["status"] = "no Alpaca bars"
            table[n] = rec
            continue
        rec["alpaca_span"] = [str(al.index.min().date()), str(al.index.max().date()), int(len(al))]
        off = al.index.difference(S)
        rec["bars_off_yf_calendar"] = int(len(off))
        yf = px0[n]
        ovu = yf.notna() & yf.index.isin(al.index)
        if ovu.sum():                                    # information: overlap before the cap (another security?)
            rec["yf_overlap_uncapped_ret_corr"] = list(corr_ret(yf[ovu], al.reindex(yf.index[ovu])))
            rec["yf_overlap_uncapped_span"] = [str(yf.index[ovu].min().date()), str(yf.index[ovu].max().date())]
        al = al[al.index.isin(S) & (al.index <= cap)]
        ov = yf.notna() & yf.index.isin(al.index)
        if ov.sum():                                     # chain-link onto yfinance where both exist
            c_, nobs = corr_ret(yf[ov], al.reindex(yf.index[ov]))
            rec["yf_overlap_ret_corr"] = [c_, nobs]
            if c_ is None or c_ < 0.999:
                flagged[n] = f"yfinance overlap return corr {c_} on {nobs} days"
            al = al * (yf[ov].iloc[-1] / al[yf.index[ov][-1]])
        if not len(al):
            rec["status"] = "Alpaca bars only after last eligible session + 10"
            table[n] = rec
            continue
        pos = S.get_indexer(al.index)
        brk = np.where(np.diff(pos) > 5)[0]
        if len(brk):                                     # v2: keep the last contiguous run before the cap only
            rec["earlier_fragments_dropped"] = {"bars": int(brk[-1] + 1), "run_starts": str(al.index[brk[-1] + 1].date())}
            al = al.iloc[brk[-1] + 1:]
            pos = pos[brk[-1] + 1:]
        rec["max_gap_sessions"] = int(np.diff(pos).max()) if len(pos) > 1 else 0
        rec["last_bar_vs_last_eligible_sessions"] = int(pos.max() - last_el)
        if rec["max_gap_sessions"] > 5:
            flagged[n] = f"gap of {rec['max_gap_sessions']} sessions"
        if (al <= 0).any():
            flagged[n] = "non-positive close"
        if n in flagged:
            rec["status"] = "flagged, not filled: " + flagged[n]
            table[n] = rec
            continue
        fill = px[n].isna() & px.index.isin(al.index)
        px.loc[fill, n] = al.reindex(px.index[fill]).values
        rec["cells_filled"] = int(fill.sum())
        rec["filled_span"] = [str(px.index[fill].min().date()), str(px.index[fill].max().date())]
        rec["status"] = "filled"
        table[n] = rec
    d1, raw1 = build_from(px)
    filled = [n for n, r in table.items() if r["status"] == "filled"]
    fi = np.array([names.index(n) for n in filled], int)
    keep = np.setdiff1d(np.arange(len(names)), fi)
    # P4 b: per-name fields identical for names not filled
    eqn = {}
    for k in ("r", "beta", "e", "valid", "elig"):
        a, b = d0[k][:, keep], d1[k][:, keep]
        eqn[k] = bool(np.array_equal(a, b, equal_nan=a.dtype.kind == "f"))
    eqn["Zraw"] = bool(np.array_equal(raw0["Zraw"][:, keep], raw1["Zraw"][:, keep], equal_nan=True))
    eqn["y5_before_demean"] = bool(np.array_equal(raw0["y5raw"][:, keep], raw1["y5raw"][:, keep], equal_nan=True))
    eqn["spy_rm"] = bool(np.array_equal(d0["spy"], d1["spy"], equal_nan=True) and np.array_equal(d0["rm"], d1["rm"], equal_nan=True))
    assert all(eqn.values()), eqn
    xs = {}
    for k in ("Z", "y5"):
        a, b = d0[k][:, keep].astype(np.float64), d1[k][:, keep].astype(np.float64)
        xs[k] = {"nan_pattern_equal": bool((np.isnan(a) == np.isnan(b)).all()),
                 "max_abs_diff": float(np.nanmax(np.abs(a - b))), "mean_abs_diff": float(np.nanmean(np.abs(a - b)))}
    # coverage against expected (2020-2025 Thursdays)
    import sp500_transformers as X
    ok_in = np.zeros((len(th), len(names)), bool)
    Zf = np.isfinite(d1["Z"]).all(-1)
    for j, t in enumerate(th):
        ok_in[j] = d1["elig"][t] & Zf[t - X.LOOK + 1: t + 1].all(0)
    y5f = np.isfinite(d1["y5"][th])
    for n in mset:
        i = names.index(n)
        mi = miss[:, i]
        table[n]["weeks_now_with_y5"] = int((mi & y5f[:, i]).sum())
        table[n]["weeks_now_scoreable_and_y5"] = int((mi & y5f[:, i] & ok_in[:, i]).sum())
    cov = {"missing_name_weeks": int(miss.sum()), "now_with_y5": int((miss & y5f).sum()),
           "now_scoreable_by_master_and_y5": int((miss & y5f & ok_in).sum()),
           "names_filled": len(filled), "names_flagged": flagged,
           "names_no_alpaca": sorted(n for n, r in table.items() if r["status"] == "no Alpaca bars"),
           "remaining_missing_name_weeks": int((miss & ~y5f).sum()),
           "eligible_2020_2025_name_weeks_with_y5_orig": int((el & np.isfinite(y5)).sum()),
           "eligible_2020_2025_name_weeks_with_y5_repaired": int((d1["elig"][th] & y5f).sum())}
    cov["share_of_missing_weeks_filled_with_y5"] = cov["now_with_y5"] / cov["missing_name_weeks"]
    cov["share_of_missing_weeks_scoreable"] = cov["now_scoreable_by_master_and_y5"] / cov["missing_name_weeks"]
    for arm, d in (("ORIG", d0), ("REPAIRED", d1)):
        arrs = {k: v for k, v in d.items() if isinstance(v, np.ndarray)}
        out = os.path.join(CACHE, f"panel_{arm}.npz")
        if arm == "ORIG" and os.path.exists(out):       # in use by running workers; identical by P4a: left as is
            continue
        np.savez(out + ".tmp.npz", S=np.asarray(S.values), names=np.array(names), **arrs)
        os.replace(out + ".tmp.npz", out)
    px.to_parquet(os.path.join(CACHE, "sp500_close_repaired.parquet"))
    json.dump({"filled": filled, "version": VERSION}, open(os.path.join(CACHE, "filled_names.json"), "w"))
    checks(VERSION + "P4a_copy_equals_original_build", same)
    checks(VERSION + "P2_missing_set", p2)
    checks(VERSION + "source_alpaca_vs_yfinance_2016_2025", src)
    checks(VERSION + "P3_per_name", table)
    checks(VERSION + "P4b_per_name_fields_equal_unfilled", eqn)
    checks(VERSION + "P4c_cross_sectional_fields_unfilled_names", xs)
    checks(VERSION + "P4d_coverage_vs_expected", cov)
    if cov["now_with_y5"] == 0:
        sys.exit("no missing name-week repaired: stop")


def load(arm):
    z = np.load(os.path.join(CACHE, f"panel_{arm}.npz"), allow_pickle=False)
    d = {k: z[k] for k in z.files if k not in ("S", "names")}
    d["S"] = pd.DatetimeIndex(z["S"])
    d["names"] = [str(n) for n in z["names"]]
    return d


# ------------------------------------------------------------------------------------------------ fits
def tasks():
    return [f"{arm}_y{y}_s{s}" for arm in ARMS for y in YEARS for s in SEEDS]   # ORIG first (useful whatever the repair)


def pred_path(t):
    return os.path.join(CACHE, f"pred_{t}.npz")


def claim(t):
    lp = os.path.join(CACHE, f"lock_{t}")
    if os.path.exists(lp):
        try:
            pid = int(open(lp).read().strip() or 0)
        except ValueError:
            pid = 0
        if pid and pid != os.getpid():
            try:
                os.kill(pid, 0)
                return False
            except OSError:
                pass
    with open(lp, "w") as f:
        f.write(str(os.getpid()))
    return True


def worker(minutes):
    import arch as A
    deadline = time.time() + minutes * 60
    data = {}
    while time.time() < deadline:
        if A.disk_free_gb() < 4:
            log(f"free disk {A.disk_free_gb():.1f} GB < 4: stop")
            sys.exit(3)
        pending = [t for t in tasks() if not os.path.exists(pred_path(t))]
        if not pending:
            log("all tasks done")
            return
        t = next((t for t in pending if claim(t)), None)
        if t is None:
            log("every pending task is claimed by a live worker")
            return
        arm, y, s = t.split("_")
        year, seed = int(y[1:]), int(s[1:])
        if arm not in data:
            data = {arm: load(arm)}                      # one panel in memory at a time
        d = data[arm]
        S = d["S"]
        days = A.thursdays(S, np.where(S.year == year)[0])
        update_state(lambda st: st.setdefault("running_fits", {}).__setitem__(t, {"pid": os.getpid(), "since": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
        ck = os.path.join(CACHE, f"ckpt_{t}.pt")
        status, out, info = A.fit(d, "base", seed, year, days, ck, deadline=deadline)
        if status == "paused":
            log(f"{t} paused at epoch {info['epoch']}")
            update_state(lambda st: st.get("running_fits", {}).pop(t, None))
            continue
        np.savez_compressed(pred_path(t) + ".tmp.npz", scores=out.astype(np.float32), rows=days,
                            n_names=len(d["names"]), info=json.dumps(info))
        os.replace(pred_path(t) + ".tmp.npz", pred_path(t))
        if os.path.exists(ck):
            os.remove(ck)
        log(f"{t} done: epochs {info['epochs']} best {info['best_epoch']} val_ic {info['val_ic']:.4f} "
            f"train {info['train_sec'] / 60:.1f} min")

        def fin(st):
            st.get("running_fits", {}).pop(t, None)
            st.setdefault("fits", {})[t] = {k: info[k] for k in ("epochs", "best_epoch", "val_ic", "train_sec", "session_sec", "stopped_by_rule")}
            st["fits_done"] = len(st["fits"])
        update_state(fin)
        os.remove(os.path.join(CACHE, f"lock_{t}"))
    log("deadline reached")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        build()
    elif cmd == "worker":
        worker(float(sys.argv[2]) if len(sys.argv) > 2 else 1e6)
    elif cmd == "report":
        import report
        report.main()
