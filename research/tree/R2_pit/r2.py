"""R2 (PREREG Layer 3, Amendment 10): the point-in-time broad universe, 2017-2026. Descriptive; every period is read.

    python3 research/tree/R2_pit/r2.py inputs     # sha256 of every input, frozen at first use -> R2_pit/INPUTS.json
    python3 research/tree/R2_pit/r2.py build hind # the hindsight universe rebuilt by this code; must equal y2026/broad_panel.npz
    python3 research/tree/R2_pit/r2.py build pit  # the point-in-time universe -> .cache/tree/r2/pit_panel.npz
    python3 research/tree/R2_pit/r2.py checks     # content checks (coverage, re-admitted share, price spot-checks, y5 clip)
    python3 research/tree/R2_pit/r2.py fit        # D_hgb_mh walk-forward 2017-2026, seeds 0-2, one file per year (resumable)
    python3 research/tree/R2_pit/r2.py report     # both universes side by side, paired by week -> RESULT.json
    python3 research/tree/R2_pit/r2.py edgar      # Form 25 / 25-NSE counts from EDGAR form indexes; delistings by year

Universe (Amendment 10): Amendment 1's rule, except that the exclusion is only of names that are S&P 500 members at t.
Membership at t: sp500_membership.csv point in time (h7_build.sp_membership, last row carried forward), by ticker,
extended to every ticker that shares a CIK with a member ticker in .cache/p8/edgar/ciks.json (typed `cik` field;
renamed members such as ANTM -> ELV are then excluded under both tickers). Everything else is the h7_build.broad_panel
code: Alpaca adjusted closes (2026 chain-linked onto 2025-12-31), unadjusted close/volume for eligibility only,
panel_broad's $5 / 252-session / top-1,500 by 63-session dollar volume rule (applied to the non-member pool),
panel400.fields on the S&P 500 panel plus the broad columns. The S&P 500 panel columns are unchanged.
"""
import glob
import hashlib
import json
import math
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "3")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
sys.path.insert(0, TREE)
import h7_build as HB  # noqa: E402
import harness as H  # noqa: E402
from holdout2 import load_module, nw  # noqa: E402

C2 = os.path.join(ROOT, ".cache", "tree", "r2")
PREDS = os.path.join(ROOT, ".cache", "tree", "preds", "R2_pit")
Y26 = HB.Y26
RESULT = os.path.join(HERE, "RESULT.json")
STATE = os.path.join(HERE, "STATE.json")
CIKS = os.path.join(ROOT, ".cache", "p8", "edgar", "ciks.json")
YEARS = tuple(range(2017, 2027))
os.makedirs(C2, exist_ok=True)
os.makedirs(PREDS, exist_ok=True)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def state(done=None, running=None, nxt=None):
    s = json.load(open(STATE)) if os.path.exists(STATE) else {"task": "R2 point-in-time broad universe (Amendment 10)", "done": []}
    if done:
        s["done"] = s.get("done", []) + [done]
    if running is not None:
        s["running"] = running
    if nxt is not None:
        s["next"] = nxt
    s["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(s, open(STATE, "w"), indent=1)


def result(key, val):
    r = json.load(open(RESULT)) if os.path.exists(RESULT) else {}
    r[key] = val
    json.dump(r, open(RESULT, "w"), indent=1, default=float)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha_dir(folder):
    h = hashlib.sha256()
    files = sorted(glob.glob(os.path.join(folder, "*.parquet")))
    for p in files:
        h.update(os.path.basename(p).encode())
        h.update(sha(p).encode())
    return h.hexdigest(), len(files)


# ------------------------------------------------------------------------------------------------ inputs (rule 4)
def inputs():
    """Every input's sha256, frozen at first use: a later run whose hash differs is an input defect (exit 1)."""
    import sp500_test as T
    p = os.path.join(HERE, "INPUTS.json")
    cur = {"broad/chunks": sha_dir(os.path.join(HB.BROAD, "chunks")), "broad/chunks_raw": sha_dir(os.path.join(HB.BROAD, "chunks_raw")),
           "y2026/chunks": sha_dir(os.path.join(Y26, "chunks")), "y2026/chunks_raw": sha_dir(os.path.join(Y26, "chunks_raw")),
           "sp500_close_ext.parquet": sha(HB.EXT_PX), "sp500_close.parquet": sha(T.PX), "sp500_membership.csv": sha(HB.MEMB),
           "ciks.json": sha(CIKS), "p8/events.parquet": sha(os.path.join(ROOT, ".cache", "p8", "events.parquet")),
           "p8/alpaca_bars.parquet": sha(os.path.join(ROOT, ".cache", "p8", "alpaca_bars.parquet")),
           "y2026/broad_panel.npz": sha(HB.BR_PANEL), "y2026/trees_2026.npy": sha(os.path.join(Y26, "trees_2026.npy")),
           "read3_pred_L3b_candidate.npy": sha(os.path.join(ROOT, ".cache", "tree", "read3_pred_L3b_candidate.npy")),
           "broad/chunks/_dropped.json": sha(os.path.join(HB.BROAD, "chunks", "_dropped.json")),
           "broad/symbols.json": sha(os.path.join(HB.BROAD, "symbols.json"))}
    cur = {k: (list(v) if isinstance(v, tuple) else v) for k, v in cur.items()}
    if os.path.exists(p):
        old = json.load(open(p))["sha256"]
        bad = {k: (old.get(k), v) for k, v in cur.items() if old.get(k) != v}
        if bad:
            print(json.dumps(bad, indent=1))
            sys.exit("input_defect: inputs changed since first use")
        log("inputs unchanged since", json.load(open(p))["at"])
        return
    json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sha256": cur}, open(p, "w"), indent=1)
    log("inputs frozen", len(cur))


# ------------------------------------------------------------------------------------------------ membership
def cik_groups():
    C = json.load(open(CIKS))
    by = {}
    for t, v in C.items():
        if v.get("cik"):
            by.setdefault(int(v["cik"]), set()).add(t)
    return {t: g for g in by.values() if len(g) > 1 for t in g}


def member_mask(S, cols):
    """(len(S), len(cols)) bool: the column's ticker is an S&P 500 member at t, or shares a CIK with one."""
    mem = HB.sp_membership(S.max())
    grp = cik_groups()
    ci = {c: j for j, c in enumerate(cols)}
    rows = {}
    for d, s in mem.items():
        v = np.zeros(len(cols), bool)
        ext = set(s)
        for t in s:
            ext |= grp.get(t, set())
        for t in ext:
            j = ci.get(t)
            if j is not None:
                v[j] = True
        rows[d] = v
    M = pd.DataFrame(np.array(list(rows.values())), index=list(rows.keys()))
    M = M.reindex(S, method="ffill").fillna(False).to_numpy().astype(bool)
    return M


def eligibility_pit(rclose, rvol, excl):
    """panel_broad.eligibility with the pool restricted, each session, to names not excluded at t."""
    import panel_broad as PB
    dv = (rclose * rvol).rolling(PB.DV_WIN, min_periods=PB.DV_WIN).mean()
    hist = rclose.notna().cumsum()
    ok = (rclose > PB.MIN_PX) & (hist >= PB.HIST) & dv.notna()
    if excl is not None:
        ok = ok & ~pd.DataFrame(excl, index=rclose.index, columns=rclose.columns)
    rank = dv.where(ok).rank(axis=1, ascending=False)
    return (rank <= PB.TOP).to_numpy()


# ------------------------------------------------------------------------------------------------ build
def build(mode):
    import panel_broad as PB
    import panel400 as P4
    assert mode in ("pit", "hind")
    end = HB.fetch_end()
    px5 = pd.read_parquet(HB.EXT_PX)
    px5.index = pd.to_datetime(px5.index).tz_localize(None).normalize()
    spy = px5.pop("SPY")
    S = px5.index
    S0 = S[S <= HB.END25]
    names5 = list(px5.columns)
    ev = pd.read_parquet(os.path.join(P4.P8, "events.parquet"), columns=["ticker", "universe"])
    s400 = sorted(set(ev[ev.universe == "sp400"].ticker) - set(names5))
    b4 = pd.read_parquet(os.path.join(P4.P8, "alpaca_bars.parquet"), columns=["date", "ticker", "close"])
    b4 = b4[b4.ticker.isin(s400)]
    px4 = b4.pivot(index="date", columns="ticker", values="close").reindex(S0)
    read400 = list(px4.columns[px4.notna().sum() > 300])
    hind_excl = set(names5) | set(read400) | {"SPY"}
    excl = hind_excl if mode == "hind" else {"SPY"}
    log(mode, "reading chunks")
    old = HB.read_old("chunks", excl)
    oldr = HB.read_old("chunks_raw", excl)
    new, _ = HB.read_chunks("chunks")
    newr, _ = HB.read_chunks("chunks_raw")
    new, newr = new[~new.ticker.isin(excl) & (new.date < end)], newr[~newr.ticker.isin(excl) & (newr.date < end)]
    c_old = old.pivot_table(index="date", columns="ticker", values="close").reindex(S0)
    c_new = new.pivot_table(index="date", columns="ticker", values="close").reindex(S)
    cols = sorted(set(c_old.columns) | set(c_new.columns))
    c_old = c_old.reindex(columns=cols)
    close, anchor = HB.chain(c_old, c_new.reindex(columns=cols), HB.END25)
    close = close.reindex(S)
    rc = pd.concat([oldr[oldr.date <= HB.END25], newr[newr.date > HB.END25]])
    rclose = rc.pivot_table(index="date", columns="ticker", values="close").reindex(S).reindex(columns=cols)
    rvol = rc.pivot_table(index="date", columns="ticker", values="volume").reindex(S).reindex(columns=cols)
    log(mode, "eligibility on", len(cols), "tickers")
    memx = member_mask(S, cols) if mode == "pit" else None
    elig_b = eligibility_pit(rclose, rvol, memx) if mode == "pit" else PB.eligibility(rclose, rvol)
    keep = elig_b.any(0)
    order = [c for c, k in zip(cols, keep) if k]
    idx = pd.Index(cols).get_indexer(order)
    elig_b = elig_b[:, idx]
    closeb = close[order]
    dvd = (rclose * rvol)[order]
    dv_b = dvd.rolling(PB.DV_WIN, min_periods=PB.DV_WIN).mean().to_numpy()
    mem = HB.sp_membership(S.max()).reindex(S, method="ffill")
    elig5 = np.array([[t in s for t in names5] for s in mem.values])
    px = pd.concat([px5, closeb], axis=1)
    elig = np.concatenate([elig5, elig_b], 1)
    log(mode, "fields on", px.shape)
    D = P4.fields(px, spy, elig)
    isb = np.array([False] * len(names5) + [True] * len(order))
    D["dv"] = np.concatenate([np.full((len(S), len(names5)), np.nan), dv_b], 1).astype(np.float32)
    # re-admission type per broad column (hindsight exclusion list)
    rtype = np.array([0] * len(names5) + [1 if c in set(names5) else (2 if c in set(read400) else 0) for c in order], np.int8)
    arrs = {k: v for k, v in D.items() if isinstance(v, np.ndarray)}
    out = os.path.join(C2, f"{mode}_panel.npz")
    np.savez(out, S=np.asarray(S.values), names=np.array(names5 + order), isb=isb, rtype=rtype, **arrs)
    np.save(os.path.join(C2, f"{mode}_dvd.npy"), dvd.to_numpy().astype(np.float64))
    if memx is not None:
        np.save(os.path.join(C2, "pit_member_mask_cols.npy"), memx[:, idx])
    log(mode, "saved", out, "broad names", len(order))
    if mode == "hind":
        verify_hind()
    state(done=f"build {mode}")


def load(mode):
    z = np.load(os.path.join(C2, f"{mode}_panel.npz"), allow_pickle=False)
    D = {k: z[k] for k in z.files if k not in ("S", "names", "isb", "rtype")}
    D["S"] = pd.DatetimeIndex(z["S"])
    D["names"] = [str(n) for n in z["names"]]
    return D, z["isb"].astype(bool), z["rtype"]


def load_y26():
    z = np.load(HB.BR_PANEL, allow_pickle=False)
    D = {k: z[k] for k in z.files if k not in ("S", "names", "isb")}
    D["S"] = pd.DatetimeIndex(z["S"])
    D["names"] = [str(n) for n in z["names"]]
    return D, z["isb"].astype(bool)


def verify_hind():
    """This code with the hindsight exclusion must give exactly the H7 broad panel (column order aside)."""
    D, isb, _ = load("hind")
    R, risb = load_y26()
    assert (D["S"] == R["S"]).all()
    assert D["names"][:850] == R["names"][:850]
    j = pd.Index(D["names"]).get_indexer(R["names"])
    out = {"names_mine": len(D["names"]), "names_h7": len(R["names"]), "h7_names_missing_here": int((j < 0).sum()),
           "isb_equal": bool((isb[j] == risb).all())}
    for k in ("elig", "Z", "valid", "r", "e", "beta", "dv", "y5", "rm", "spy"):
        a, b = (D[k], R[k]) if D[k].ndim == 1 else (D[k][:, j], R[k])
        out[k] = bool(np.array_equal(a, b, equal_nan=a.dtype.kind == "f"))
    result("build_hind_equals_h7_broad_panel", out)
    log("verify_hind", out)
    if not all(v for k, v in out.items() if isinstance(v, bool)):
        sys.exit("hindsight rebuild differs from y2026/broad_panel.npz")


# ------------------------------------------------------------------------------------------------ content checks
def thursdays(S, lo=2017):
    return np.where((S.weekday == 3) & (S.year >= lo))[0]


def checks():
    import sp500_test as T  # noqa: F401
    D, isb, rtype = load("pit")
    Hh, hisb, _ = load("hind")
    S = D["S"]
    th = thursdays(S)
    th = th[th < len(S) - 7]
    eb = D["elig"][:, isb]
    ra = rtype[isb]
    names_b = [n for n, f in zip(D["names"], isb) if f]
    hnames_b = set(n for n, f in zip(Hh["names"], hisb) if f)
    out = {"broad_columns": int(isb.sum()), "of_which_sp500_panel_tickers": int((ra == 1).sum()),
           "of_which_current_sp400_read": int((ra == 2).sum()), "other": int((ra == 0).sum())}
    by = {}
    for y in YEARS:
        r = th[S[th].year == y]
        e = eb[r]
        hasy = e & np.isfinite(D["y5"][r][:, isb])
        hasz = e & np.isfinite(D["Z"][r][:, isb]).all(-1)
        by[y] = {"thursdays": int(len(r)), "eligible_mean": float(e.sum(1).mean()), "eligible_min": int(e.sum(1).min()),
                 "eligible_max": int(e.sum(1).max()), "expected_per_thursday": 1500,
                 "with_y5_mean": float(hasy.sum(1).mean()), "with_all_Z_mean": float(hasz.sum(1).mean()),
                 "share_readmitted": float((e & (ra > 0)[None, :]).sum() / e.sum()),
                 "share_readmitted_sp500_panel": float((e & (ra == 1)[None, :]).sum() / e.sum()),
                 "share_readmitted_sp400": float((e & (ra == 2)[None, :]).sum() / e.sum()),
                 "share_not_in_hindsight_broad_columns": float((e & ~np.isin(names_b, list(hnames_b))[None, :]).sum() / e.sum())}
    out["by_year"] = by
    # common / re-admitted / hindsight-only per Thursday
    out["per_thursday_overlap"] = overlap_counts(D, isb, Hh, hisb, th)
    # y5 clip, as Amendment 5
    yb = D["y5"][th][:, isb][eb[th]]
    yb = yb[np.isfinite(yb)]
    out["y5_beyond_pm1"] = {"count": int((np.abs(yb) > 1).sum()), "of": int(len(yb))}
    # spot-check: three re-admitted S&P 500 panel tickers with the most re-admitted Thursdays; their Alpaca returns
    # (broad column) against the panel's yfinance returns (S&P column), on the sessions both have, 2016-2025
    cnt = (eb[th] & (ra == 1)[None, :]).sum(0)
    top = np.argsort(-cnt)[:3]
    spot = {}
    bcol = np.where(isb)[0]
    sel = (S >= "2016-01-05") & (S <= HB.END25)
    for k in top:
        n = names_b[k]
        a = D["r"][sel, bcol[k]].astype(np.float64)
        b = D["r"][sel, D["names"].index(n)].astype(np.float64)
        m = np.isfinite(a) & np.isfinite(b)
        d = np.abs(a[m] - b[m])
        spot[n] = {"readmitted_thursdays": int(cnt[k]), "common_sessions": int(m.sum()), "corr": float(np.corrcoef(a[m], b[m])[0, 1]),
                   "abs_diff_median": float(np.median(d)), "abs_diff_p99": float(np.quantile(d, 0.99)), "abs_diff_max": float(d.max()),
                   "share_within_1e-4": float((d < 1e-4).mean()), "share_within_1e-3": float((d < 1e-3).mean()),
                   "worst_day": str(S[sel][m][np.argmax(d)].date())}
    out["spot_check_alpaca_vs_panel_returns"] = spot
    out["missing_bars"] = missing_bars(D, isb)
    result("content_checks", out)
    log(json.dumps(out, default=float)[:4000])
    state(done="checks")


def bmap(D, isb):
    return {n: j for j, (n, f) in enumerate(zip(D["names"], isb)) if f}


def overlap_counts(D, isb, Hh, hisb, th):
    pm, hm = bmap(D, isb), bmap(Hh, hisb)
    common = sorted(set(pm) & set(hm))
    pj, hj = np.array([pm[n] for n in common]), np.array([hm[n] for n in common])
    c = (D["elig"][th][:, pj] & Hh["elig"][th][:, hj]).sum(1)
    p = D["elig"][th][:, isb].sum(1)
    h = Hh["elig"][th][:, hisb].sum(1)
    return {"common_mean": float(c.mean()), "pit_only_mean": float((p - c).mean()), "hind_only_mean": float((h - c).mean()),
            "pit_mean": float(p.mean()), "hind_mean": float(h.mean())}


def missing_bars(D, isb):
    """Re-admission candidates that have no Alpaca bars: S&P 500 panel tickers priced (yfinance) on non-member sessions
    2016-2025 that are not Alpaca broad columns, and S&P 400 read names that are not Alpaca symbols."""
    import panel400 as P4
    S = D["S"]
    names5 = D["names"][:850]
    sym = {s["symbol"] for s in json.load(open(os.path.join(HB.BROAD, "symbols.json")))["symbols"]}
    sel = (S >= "2016-01-04") & (S <= HB.END25)
    nonmem = D["valid"][sel][:, :850] & ~D["elig"][sel][:, :850]
    cnt = nonmem.sum(0)
    inb = set(n for n, f in zip(D["names"], isb) if f)
    miss = {n: int(c) for n, c in zip(names5, cnt) if c > 0 and n not in sym}
    ev = pd.read_parquet(os.path.join(P4.P8, "events.parquet"), columns=["ticker", "universe"])
    s400 = sorted(set(ev[ev.universe == "sp400"].ticker) - set(names5))
    return {"sp500_panel_names_priced_off_membership_without_alpaca_symbol": miss,
            "their_name_sessions": int(sum(miss.values())),
            "sp500_panel_names_priced_off_membership_with_alpaca_symbol": int(sum(1 for n, c in zip(names5, cnt) if c > 0 and n in sym)),
            "of_which_ever_broad_eligible": int(sum(1 for n, c in zip(names5, cnt) if c > 0 and n in inb)),
            "sp400_names_not_alpaca_symbols": [n for n in s400 if n not in sym],
            "note": "Amendment 1's universe is Alpaca assets on NYSE/NASDAQ/AMEX; a name with no Alpaca asset is outside the "
                    "rule, not missing data. No fetch was needed: every re-admitted ticker that is an Alpaca asset has bars."}


# ------------------------------------------------------------------------------------------------ fit
def fit():
    D, isb, _ = load("pit")
    model = load_module(os.path.join(TREE, "finalists", "D_hgb_mh", "model.py"), "r2_trees")
    for y in YEARS:
        p_ = os.path.join(PREDS, f"pit_{y}.npz")
        if os.path.exists(p_):
            log("year", y, "done already")
            continue
        state(running=f"fit {y}")
        t0 = time.time()
        p = H.walk_forward(model.fit_predict, seeds=(0, 1, 2), years=(y,), D=D)
        rows = H.thursdays(D, y)
        te = H.train_end(D, y)
        np.savez(p_, rows=rows, pred=p[rows].astype(np.float32))
        pb = np.where(D["elig"] & isb[None, :], p, np.nan)[rows]
        meta = {"year": y, "train_end_row": str(D["S"][te].date()), "last_target_end": str(D["S"][te + 6].date()),
                "thursdays": int(len(rows)), "broad_scored_min": int(np.isfinite(pb).sum(1).min()),
                "broad_scored_max": int(np.isfinite(pb).sum(1).max()), "seconds": round(time.time() - t0)}
        log("year", y, meta)
        r = json.load(open(RESULT)) if os.path.exists(RESULT) else {}
        f = r.get("fit", {})
        f[str(y)] = meta
        result("fit", f)
        state(done=f"fit {y}", running="")
    state(nxt=["report"])


def pit_preds(D):
    p = np.full(D["y5"].shape, np.nan)
    for y in YEARS:
        z = np.load(os.path.join(PREDS, f"pit_{y}.npz"))
        p[z["rows"]] = z["pred"].astype(np.float64)
    return p


def hind_preds(Hh):
    """H7_DECOMP's predictions (read3 L3b candidate <= 2025, trees_2026 for 2026), on the y2026 panel's columns, mapped
    by name onto this code's hindsight panel (verified equal to the y2026 panel)."""
    R, _ = load_y26()
    old = np.load(os.path.join(ROOT, ".cache", "tree", "read3_pred_L3b_candidate.npy")).astype(np.float64)
    p = np.full(R["y5"].shape, np.nan)
    p[: old.shape[0], : old.shape[1]] = old
    new = np.load(os.path.join(Y26, "trees_2026.npy")).astype(np.float64)
    is26 = R["S"].year == 2026
    p[is26] = new[is26]
    j = pd.Index(R["names"]).get_indexer(Hh["names"])
    assert (j >= 0).all()
    return p[:, j], p, R


# ------------------------------------------------------------------------------------------------ report
def sharpe_se(x):
    import h7_decomp as DC
    return DC.sharpe_se(x)


def ann(x):
    return float(52 * 100 * np.asarray(x, float).mean())


def series_stats(x, idx):
    x = np.asarray(x, float)
    sr, se = sharpe_se(x)
    m, t, n = nw(x)
    s = pd.Series(x, index=idx)
    return {"pct_per_year": ann(x), "sharpe": sr, "sharpe_se_lo": se, "nw_t": t, "weeks": n,
            "by_year_pct_per_year": {int(y): ann(g.values) for y, g in s.groupby(s.index.year)},
            "by_year_sharpe": {int(y): sharpe_se(g.values)[0] for y, g in s.groupby(s.index.year)}}


def ic_stats(ic, idx):
    s = pd.Series(ic, index=idx).dropna()
    m, t, n = nw(s.values)
    return {"mean": m, "nw_t": t, "weeks": n, "by_year": {int(y): float(g.mean()) for y, g in s.groupby(s.index.year)}}


def cost_inputs_from(D, isb, rows, dvd_b):
    """h9_forward.cost_inputs, the same statements, with the daily raw dollar volume of the broad columns taken from
    this build (dvd_b: len(S) x n_broad) instead of re-reading the chunks."""
    import h9_forward as F
    n = len(D["names"])
    bcol = np.where(isb)[0]
    r = D["r"]
    SIG, ADV, HSA = np.zeros((len(rows), n)), np.full((len(rows), n), np.nan), np.zeros((len(rows), n))
    FB = np.zeros((len(rows), n), np.int8)
    for j, t in enumerate(rows):
        rr = r[t - F.SIG_WIN + 1:t + 1].astype(np.float64)
        with np.errstate(all="ignore"):
            s = np.nanstd(rr, 0, ddof=1)
        ok = np.isfinite(rr).sum(0) >= 40
        s[~ok] = np.nanmedian(s[ok])
        SIG[j] = s
        w = dvd_b[t - F.ADV_WIN + 1:t + 1]
        with np.errstate(all="ignore"):
            adv_b = np.nanmedian(np.where(w > 0, w, np.nan), 0)
        adv = np.full(n, np.nan)
        adv[bcol] = adv_b
        dvt = D["dv"][t].astype(np.float64)
        m1_ = ~np.isfinite(adv) & np.isfinite(dvt) & (dvt > 0)
        adv[m1_] = dvt[m1_]
        FB[j][m1_] = 1
        el = D["elig"][t] & isb
        m2_ = ~np.isfinite(adv)
        adv[m2_] = np.nanpercentile(adv[el & ~m2_], 10)
        FB[j][m2_] = 2
        ADV[j] = adv
        HSA[j] = F.half_spread(dvt, el)
    return SIG, ADV, HSA, FB


def books(D, isb, p, dvd_b, label):
    """F0 decile book: M1.simulate at 5 bp and 14 bp flat (as h7_decomp), and Amendment 9's cost model (h9_forward)."""
    import h9_forward as F
    M1 = load_module(os.path.join(TREE, "M1_dyntrade", "lib.py"), f"m1lib_r2_{label}")
    S = D["S"]
    Ds = dict(D)
    Ds["elig"] = D["elig"] & isb[None, :]
    Dc = dict(Ds)
    Dc["y5"] = np.clip(Ds["y5"], -1.0, 1.0)
    s = np.where(Ds["elig"], p, np.nan)
    th = thursdays(S)
    rows = np.array([t for t in th if M1.mask(s, Dc, t).sum() >= 50])
    W = M1.build("decile", s, Dc, rows)
    out = {}
    for cost in (5e-4, 14e-4):
        M1.COST = cost
        out[f"{cost * 1e4:.0f}bp"] = np.asarray(M1.simulate(W, Dc, rows)["net"], float)
    SIG, ADV, HSA, FB = cost_inputs_from(D, isb, rows, dvd_b)
    sim = F.simulate(W, Dc, rows, SIG, ADV, HSA, FB)
    out["a9"] = np.array([x["net"] for x in sim])
    extra = {"a9_cost_spread_pct_per_year": ann([x["cost_spread"] for x in sim]),
             "a9_cost_impact_pct_per_year": ann([x["cost_impact"] for x in sim]),
             "gross_pct_per_year": ann([x["gross"] for x in sim]),
             "turnover_per_week": float(np.mean([x["turnover"] for x in sim])),
             "adv_fallback_traded_per_week": float(np.mean([x["adv_fallback_traded"] for x in sim]))}
    ic = H.weekly_ic(p, Ds, rows)
    return rows, out, ic, extra, (SIG, ADV, HSA, FB)


def ic_on(p, D, rows, mask):
    """Weekly IC of p on D's y5 over mask[t] (bool per column) & D elig."""
    Dm = dict(D)
    el = np.zeros_like(D["elig"])
    el[rows] = D["elig"][rows] & mask
    Dm["elig"] = el
    return H.weekly_ic(p, Dm, rows)


def report():
    D, isb, rtype = load("pit")
    Hh, hisb, _ = load("hind")
    S = D["S"]
    assert (S == Hh["S"]).all()
    pp = pit_preds(D)
    hp, hp_y26, R = hind_preds(Hh)
    pd_ = np.load(os.path.join(C2, "pit_dvd.npy"))
    hd_ = np.load(os.path.join(C2, "hind_dvd.npy"))
    log("books: hindsight")
    hrows, hnet, hic, hextra, hcost = books(Hh, hisb, hp, hd_, "hind")
    log("books: point in time")
    prows, pnet, pic, pextra, _ = books(D, isb, pp, pd_, "pit")
    # reproduction of H7_DECOMP.json (same predictions, same code paths)
    dec = json.load(open(os.path.join(TREE, "H7_DECOMP.json")))["broad_trees_book"]
    rep = {"weeks": [int(len(hrows)), dec["14bp"]["weeks"]],
           "ic_mean": [float(np.nanmean(hic)), dec["ic_2017_2026"]["mean"]],
           "sharpe_5bp": [sharpe_se(hnet["5bp"])[0], dec["5bp"]["sharpe_2017_2026"]],
           "sharpe_14bp": [sharpe_se(hnet["14bp"])[0], dec["14bp"]["sharpe_2017_2026"]],
           "pct_14bp": [ann(hnet["14bp"]), dec["14bp"]["pct_per_year"]]}
    rep["max_abs_diff"] = max(abs(a - b) for a, b in rep.values())
    rep["exact"] = bool(rep["max_abs_diff"] < 1e-12)
    # cost inputs: this code vs h9_forward.cost_inputs (chunks re-read) on the hindsight panel
    import h9_forward as F
    R["dv"] = R["dv"]
    risb = np.load(HB.BR_PANEL)["isb"].astype(bool)
    jr = pd.Index(R["names"]).get_indexer(Hh["names"])
    rows_r = hrows
    SIGr, ADVr, HSAr, FBr, dvcheck = F.cost_inputs(R, risb, rows_r)
    rep["a9_cost_inputs_equal_h9_forward"] = {k: bool(np.allclose(a[:, jr], b, rtol=1e-9, atol=0, equal_nan=True))
                                              for k, a, b in (("SIG", SIGr, hcost[0]), ("ADV", ADVr, hcost[1]), ("HSA", HSAr, hcost[2]))}
    rep["a9_fallback_equal"] = bool((FBr[:, jr] == hcost[3]).all())
    rep["h9_dv_reproduction_check"] = dvcheck
    result("hindsight_reproduces_H7_DECOMP", rep)
    log("reproduction", rep)
    # weekly series side by side
    hi, pi_ = pd.DatetimeIndex(S[hrows]), pd.DatetimeIndex(S[prows])
    res = {"label": "descriptive; out of sample but spent (every period already read); returns in % per year",
           "hindsight": {"ic": ic_stats(hic, hi), "books": {k: series_stats(v, hi) for k, v in hnet.items()}, "book_extra": hextra},
           "pit": {"ic": ic_stats(pic, pi_), "books": {k: series_stats(v, pi_) for k, v in pnet.items()}, "book_extra": pextra}}
    # paired by week
    common_w = sorted(set(hrows) & set(prows))
    hpos = {t: i for i, t in enumerate(hrows)}
    ppos = {t: i for i, t in enumerate(prows)}
    ci = pd.DatetimeIndex(S[common_w])
    pair = {"weeks": len(common_w), "weeks_hind_only": len(set(hrows) - set(prows)), "weeks_pit_only": len(set(prows) - set(hrows))}
    a = np.array([pic[ppos[t]] for t in common_w]) - np.array([hic[hpos[t]] for t in common_w])
    pair["ic_pit_minus_hind"] = ic_stats(a, ci)
    for k in hnet:
        dlt = np.array([pnet[k][ppos[t]] for t in common_w]) - np.array([hnet[k][hpos[t]] for t in common_w])
        st = series_stats(dlt, ci)
        st["corr_weekly"] = float(np.corrcoef([pnet[k][ppos[t]] for t in common_w], [hnet[k][hpos[t]] for t in common_w])[0, 1])
        pair[f"book_{k}_pit_minus_hind"] = st
    res["paired"] = pair
    # IC on common names, re-admitted only, hindsight-only
    pm, hm = bmap(D, isb), bmap(Hh, hisb)
    common = sorted(set(pm) & set(hm))
    pj, hj = np.array([pm[n] for n in common]), np.array([hm[n] for n in common])
    wk = np.array(common_w)
    both = D["elig"][:, pj] & Hh["elig"][:, hj]                  # both universes' broad-eligible, same ticker, same week
    mp = np.zeros(D["elig"].shape, bool)
    mh = np.zeros(Hh["elig"].shape, bool)
    mp[:, pj], mh[:, hj] = both, both
    # the common set is also required to have a score and a target in both panels
    fin = np.zeros(both.shape, bool)
    fin[wk] = (np.isfinite(pp[wk][:, pj]) & np.isfinite(D["y5"][wk][:, pj]) & np.isfinite(hp[wk][:, hj]) & np.isfinite(Hh["y5"][wk][:, hj]))
    mp[:, pj] &= fin
    mh[:, hj] &= fin
    icp_c = ic_on(pp, D, wk, mp[wk])
    ich_c = ic_on(hp, Hh, wk, mh[wk])
    res["ic_common_names"] = {"pit_model": ic_stats(icp_c, ci), "hind_model": ic_stats(ich_c, ci),
                              "pit_minus_hind": ic_stats(icp_c - ich_c, ci),
                              "names_per_week_mean": float(mp[wk].sum(1).mean())}
    ra = np.zeros(D["elig"].shape[1], bool)
    ra[np.where(isb)[0]] = rtype[isb] > 0
    readm = np.broadcast_to(ra, D["elig"].shape)[prows]
    icr = ic_on(pp, D, prows, readm)
    res["ic_readmitted_only_pit_model"] = ic_stats(icr, pi_)
    res["ic_readmitted_only_pit_model"]["names_per_week_mean"] = float((D["elig"][prows] & readm & np.isfinite(pp[prows]) & np.isfinite(D["y5"][prows])).sum(1).mean())
    for typ, lab in ((1, "sp500_panel_tickers"), (2, "current_sp400")):
        rt = np.zeros(D["elig"].shape[1], bool)
        rt[np.where(isb)[0]] = rtype[isb] == typ
        res[f"ic_readmitted_{lab}_pit_model"] = ic_stats(ic_on(pp, D, prows, np.broadcast_to(rt, D["elig"].shape)[prows]), pi_)
    # PIT names not re-admitted and not common (entered the top 1,500 because re-admitted names displaced none... or
    # because the pool changed): PIT eligible, not re-admitted, not hindsight-eligible that week
    other = np.zeros(D["elig"].shape, bool)
    other[prows] = D["elig"][prows] & isb[None, :] & ~readm
    other[:, pj] &= ~Hh["elig"][:, hj]
    res["ic_pit_new_not_readmitted_pit_model"] = ic_stats(ic_on(pp, D, prows, other[prows]), pi_)
    honly = np.zeros(Hh["elig"].shape, bool)
    honly[hrows] = Hh["elig"][hrows] & hisb[None, :]
    honly[:, hj] &= ~D["elig"][:, pj]
    res["ic_hindsight_only_names_hind_model"] = ic_stats(ic_on(hp, Hh, hrows, honly[hrows]), hi)
    res["ic_hindsight_only_names_hind_model"]["names_per_week_mean"] = float(honly[hrows].sum(1).mean())
    # the same model's predictions agreeing across universes (no outcome): per-week rank corr on the common names
    rc = []
    for t in common_w:
        m = mp[t, pj]
        if m.sum() >= 50:
            rc.append(pd.Series(pp[t, pj][m]).corr(pd.Series(hp[t, hj][m]), method="spearman"))
    res["score_rank_corr_common_names"] = {"mean": float(np.mean(rc)), "min": float(np.min(rc)), "weeks": len(rc)}
    result("comparison", res)
    log(json.dumps(res, default=float)[:6000])
    state(done="report", nxt=["edgar"])


# ------------------------------------------------------------------------------------------------ data completeness
UA = "research-script admin@example.com"


def edgar_index():
    """EDGAR full-index form.gz per quarter 2016Q1..2026Q4 (to date), frozen at first fetch (sha256 recorded)."""
    import gzip
    import urllib.request
    d = os.path.join(C2, "edgar")
    os.makedirs(d, exist_ok=True)
    man_p = os.path.join(d, "MANIFEST.json")
    man = json.load(open(man_p)) if os.path.exists(man_p) else {}
    rows = []
    for y in range(2016, 2027):
        for q in (1, 2, 3, 4):
            if y == 2026 and q == 4 and False:
                pass
            f = os.path.join(d, f"form_{y}Q{q}.gz")
            if not os.path.exists(f):
                url = f"https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.gz"
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": UA})
                    b = urllib.request.urlopen(req, timeout=120).read()
                except Exception as exc:                                 # a quarter not yet published: recorded
                    man[f"{y}Q{q}"] = {"error": repr(exc)[:200]}
                    continue
                open(f, "wb").write(b)
                man[f"{y}Q{q}"] = {"sha256": sha(f), "bytes": len(b), "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                time.sleep(0.3)
            elif man.get(f"{y}Q{q}", {}).get("sha256") not in (None, sha(f)):
                sys.exit(f"input_defect: {f} changed since first fetch")
            if f"{y}Q{q}" not in man:            # fetched by a run that stopped before saving the manifest
                man[f"{y}Q{q}"] = {"sha256": sha(f), "bytes": os.path.getsize(f), "fetched": "first run (manifest written on rerun)"}
            txt = gzip.decompress(open(f, "rb").read()).decode("latin-1").splitlines()
            # fixed-width file: header line "Form Type   Company Name   CIK   Date Filed   File Name", then dashes
            hdr = next(i for i, l in enumerate(txt) if l.startswith("Form Type"))
            h = txt[hdr]
            c_comp, c_cik, c_date, c_file = h.index("Company Name"), h.index("CIK"), h.index("Date Filed"), h.index("File Name")
            assert txt[hdr + 1].startswith("---")
            n_q = 0
            for l in txt[hdr + 2:]:
                form = l[:c_comp].strip()
                if form in ("25-NSE", "25", "25-NSE/A", "25/A"):
                    # long company names overflow the fixed columns: CIK, date and file name are the last three tokens
                    tok = l[c_comp:].split()
                    rows.append((form, " ".join(tok[:-3]), int(tok[-3]), tok[-2][:10], y, q))
                n_q += 1
            man[f"{y}Q{q}"]["lines"] = n_q
    json.dump(man, open(man_p, "w"), indent=1)
    df = pd.DataFrame(rows, columns=["form", "company", "cik", "date", "y", "q"])
    df["date"] = pd.to_datetime(df.date)
    df.to_parquet(os.path.join(C2, "form25.parquet"))
    return df, man


def edgar():
    df, man = edgar_index()
    D, isb, rtype = load("pit")
    Hh, hisb, _ = load("hind")
    S = D["S"]
    out = {"index_quarters": {k: {kk: v.get(kk) for kk in ("sha256", "lines", "error")} for k, v in man.items()}}
    f25 = {}
    for y in range(2016, 2027):
        g = df[df.date.dt.year == y]
        f25[y] = {"25-NSE_filings": int((g.form == "25-NSE").sum()), "25-NSE_unique_cik": int(g[g.form == "25-NSE"].cik.nunique()),
                  "25_filings": int((g.form == "25").sum()), "25_unique_cik": int(g[g.form == "25"].cik.nunique()),
                  "either_unique_cik": int(g[g.form.isin(["25-NSE", "25"])].cik.nunique())}
    out["form25_by_year"] = f25
    out["form25_note"] = ("All filers: Form 25-NSE (exchange) and 25 (issuer) cover every delisted class of security on a "
                          "national exchange (common stock, preferreds, warrants, units, notes, ETFs). The index has no "
                          "security-class field, so this is an upper bound on common-stock delistings, not a match.")
    # our delistings: eligible broad names on the year's first Thursday whose last bar is in that year (A1's measure);
    # names eligible at any time in the year whose last bar is in that year; whole Alpaca universe with bars
    for lab, DD, ib in (("pit", D, isb), ("hindsight", Hh, hisb)):
        v = DD["valid"][:, ib]
        last = np.where(v.any(0), len(S) - 1 - np.argmax(v[::-1], 0), -1)
        lasty = np.where(last >= 0, S[np.clip(last, 0, None)].year, 0)
        e = DD["elig"][:, ib]
        by = {}
        for y in range(2017, 2027):
            r = np.where((S.weekday == 3) & (S.year == y))[0]
            first = e[r[0]]
            anyy = e[r].any(0)
            by[y] = {"eligible_first_thursday": int(first.sum()), "of_them_last_bar_in_year": int((first & (lasty == y)).sum()),
                     "share": float((first & (lasty == y)).sum() / first.sum()),
                     "eligible_in_year": int(anyy.sum()), "of_them_last_bar_in_year_any": int((anyy & (lasty == y)).sum())}
        out[f"delistings_{lab}"] = by
    # whole Alpaca universe: tickers with bars, last bar per year (adjusted chunks <= 2025, y2026 after)
    lastbar = {}
    for folder in (os.path.join(HB.BROAD, "chunks"), os.path.join(Y26, "chunks")):
        for p in sorted(glob.glob(os.path.join(folder, "*.parquet"))):
            b = pd.read_parquet(p, columns=["date", "ticker"])
            if len(b):
                for t, d in b.groupby("ticker").date.max().items():
                    lastbar[t] = max(lastbar.get(t, ""), str(d)[:10])
    lb = pd.Series(lastbar)
    lb = pd.to_datetime(lb)
    end = HB.fetch_end() - pd.Timedelta(days=1)
    out["alpaca_universe_last_bar_by_year"] = {int(y): int(((lb.dt.year == y) & (lb < end - pd.Timedelta(days=7))).sum())
                                               for y in range(2016, 2027)}
    out["alpaca_universe_tickers_with_bars"] = int(len(lb))
    out["delisted_59"] = delisted_59(df, D)
    result("data_completeness", out)
    log(json.dumps(out, default=float)[:6000])
    state(done="edgar", nxt=["final report"])


def delisted_59(df, D):
    """The *_DELISTED symbols the bars endpoint rejects, mapped to a year from typed sources only: the base ticker's CIK
    in ciks.json -> its Form 25/25-NSE filing dates; the S&P 500 panel's last yfinance close for the base ticker.
    The current reuse of the base ticker at Alpaca (first bar) is given as an upper bound."""
    dropped = json.load(open(os.path.join(HB.BROAD, "chunks", "_dropped.json")))
    dl = sorted(k for k in dropped if k.endswith("_DELISTED"))
    C = json.load(open(CIKS))
    import sp500_test as T
    px5 = pd.read_parquet(T.PX)
    px5.index = pd.to_datetime(px5.index).tz_localize(None)
    first = {}
    for p in sorted(glob.glob(os.path.join(HB.BROAD, "chunks", "*.parquet"))):
        b = pd.read_parquet(p, columns=["date", "ticker"])
        if len(b):
            for t, d in b.groupby("ticker").date.min().items():
                first[t] = min(first.get(t, "9999"), str(d)[:10])
    rows, by = [], {}
    for s in dl:
        base = s[: -len("_DELISTED")]
        cik = (C.get(base) or {}).get("cik")
        f25 = sorted(df[(df.cik == cik) & df.form.isin(["25-NSE", "25"])].date.dt.strftime("%Y-%m-%d").unique()) if cik else []
        yfl = px5[base].last_valid_index() if base in px5 else None
        yr = int(f25[-1][:4]) if f25 else (int(yfl.year) if yfl is not None else None)
        how = "form25_by_cik" if f25 else ("sp500_panel_last_close" if yfl is not None else "unmapped")
        rows.append({"symbol": s, "cik": cik, "form25_dates": f25[-3:], "panel_last_close": str(yfl.date()) if yfl is not None else None,
                     "base_ticker_reused_first_bar": first.get(base), "year": yr, "how": how})
        by[str(yr)] = by.get(str(yr), 0) + 1
    return {"count": len(dl), "by_year": by, "rows": rows,
            "unmapped_note": "unmapped = no CIK in ciks.json and no S&P 500 panel price; the bars endpoint rejects the "
                             "symbol, so no typed date is available here"}


def renames():
    """Disclosure only (no change to the universe): S&P 500 members whose ticker changed and that ciks.json does not
    group, so the current Alpaca ticker (carrying the old ticker's history) is admitted while the firm was a member.
    The list is written from general knowledge of index ticker changes (not a typed source); counted, not fixed."""
    D, isb, rt = load("pit")
    S = D["S"]
    th = thursdays(S)
    bm = bmap(D, isb)
    known = {"META": ("FB", None, "2022-06-09"), "LHX": ("HRS", None, "2019-07-01"), "GL": ("TMK", None, "2019-08-08"),
             "BKR": ("BHGE", None, "2019-10-18"), "FISV": ("FI", "2023-06-07", "2025-11-11"), "DD": ("DWDP", None, "2019-06-03"),
             "GEN": ("SYMC", None, "2019-11-05"), "TNL": ("WYN", None, "2018-06-01"), "BBWI": ("LB", None, "2021-08-03"),
             "CPRI": ("KORS", None, "2019-01-02"), "BKNG": ("PCLN", None, "2018-02-27"), "WBD": ("DISCA", None, "2022-04-11")}
    out, tot = {}, 0
    for c, (o, lo, hi) in known.items():
        if c not in bm:
            out[c] = "not a PIT broad column"
            continue
        w = D["elig"][th, bm[c]] & (S[th] < pd.Timestamp(hi))
        if lo:
            w &= S[th] >= pd.Timestamp(lo)
        out[c] = {"member_as": o, "eligible_thursdays_while_member_under_old_ticker": int(w.sum())}
        tot += int(w.sum())
    res = {"by_ticker": out, "total_name_weeks": tot, "pit_broad_eligible_name_weeks": int(D["elig"][th][:, isb].sum())}
    result("residual_unmapped_renames", res)
    log(res)


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"inputs": inputs, "build": lambda: build(sys.argv[2]), "checks": checks, "fit": fit, "report": report,
     "edgar": edgar, "renames": renames}[cmd]()
