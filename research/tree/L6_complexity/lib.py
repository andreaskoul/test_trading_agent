"""Layer 6 T1 (research/tree/PREREG.md, "Layer 6"): shared pieces. The book, the state variables, random Fourier
feature ridge (dual), positions, selection. Plan: STATE.json (written before any result).
"""
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
sys.path.insert(0, os.path.join(TREE, "L4_exploit"))
sys.path.insert(0, TREE)
import run as L4  # noqa: E402  (research/tree/L4_exploit/run.py)

K = L4.K
CACHE = os.path.join(ROOT, ".cache", "tree", "l6")
RAW = os.path.join(CACHE, "raw")
COST, SIDE0, T_WIN, T_MIN, GAMMA = 5e-4, 0.3, 104, 52, 2.0
CGRID = (0.1, 0.5, 1, 2, 5, 10, 50, 100)
ZGRID = (1e-3, 1e-2, 1e-1, 1, 10, 1e2, 1e3)
NSEEDS, SEED0 = 10, 20261120


def log(*a):
    print(datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def state(**kw):
    p = os.path.join(HERE, "STATE.json")
    st = json.load(open(p))
    for k, v in kw.items():
        st[k] = st.get(k, []) + v if k == "done" else v
    st["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(st, open(p, "w"), indent=1)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def P_of(c):
    return int(2 * max(1, round(c * T_WIN / 2)))


# ---------------------------------------------------------------- panel and book
def panel():
    d = K.T.build()
    K.GROSS_SIDE = SIDE0
    rf = K.ST.dtb3()
    K.RF = rf
    return d, rf


def dev_scores(d):
    z = np.load(os.path.join(ROOT, ".cache", "tree", "dev.npz"), allow_pickle=False)
    S2 = pd.DatetimeIndex(z["S"])
    assert [str(n) for n in z["names"]] == list(d["names"])
    ix = d["S"].get_indexer(S2)
    assert (ix >= 0).all() and S2.max() <= pd.Timestamp("2019-12-31")
    p = np.full(d["r"].shape, np.nan)
    p[ix] = z["master_h5_ref"].astype(np.float64)
    p[d["S"] > pd.Timestamp("2019-12-31")] = np.nan
    return p


def read_scores():
    return np.load(os.path.join(K.QT, ".cache", "quant_trials", "sp500_tf_master_h5.npz"))["h5"].astype(np.float64)


def sim_book(d, pred, years, rf, mult=None):
    """L4 sim() with book_decile, returning also the book gross and the end row of each holding period.
    mult: optional per-decision exposure {row: pi} applied to w and w_spy through L4.cap_scale (the read)."""
    S, spy = d["S"], pd.Series(d["spy"])
    ma = spy.rolling(K.ST.TREND, min_periods=K.ST.TREND).mean().values
    th = np.where((S.weekday == 3) & (S.year >= min(years)) & (S.year <= max(years)))[0]
    nxt = {int(th[k]): int(th[k + 1]) for k in range(len(th) - 1)}
    rows, prev, prev_spy, prev_s = [], None, 0.0, None
    for t, R, Rm, days in K.ST.periods(d, years):
        ok = np.isfinite(pred[t]) & d["elig"][t]
        w = L4.book_decile(t, d, pred[t], ok, {})
        s = K.ST.UP if np.isfinite(ma[t]) and d["spy"][t] > ma[t] else K.ST.DOWN
        beta = np.nan_to_num(d["beta"][t], nan=1.0)
        w_spy = -float((w * beta).sum())
        m = 1.0 if mult is None else float(mult[t])
        k = L4.cap_scale(s, w, w_spy, m) if m != 1.0 else 1.0
        w, w_spy = w * k, w_spy * k
        dw = np.abs(w - (prev if prev is not None else 0)).sum() + abs(w_spy - prev_spy)
        book = float((w * np.nan_to_num(R)).sum() + w_spy * Rm) - COST * dw
        mrate = (float(rf.asof(S[t] - pd.Timedelta(days=1))) + K.ST.MARGIN_SPREAD) * days / 360
        sw = abs(s - (prev_s if prev_s is not None else s))
        sleeve = s * Rm - COST * sw
        total = sleeve + book - max(s + float(w.sum()) + w_spy - 1, 0) * mrate
        rows.append({"row": int(t), "end": nxt[int(t)] + 1, "date": S[t], "year": S[t].year, "days": days, "book": book,
                     "total": total, "spy": Rm, "turnover": dw, "book_cost": COST * dw, "core_cost": COST * sw, "k": k,
                     "gross": L4.gross_of(s, w, w_spy), "book_gross": float(np.abs(w).sum() + abs(w_spy)), "s": s})
        prev, prev_spy, prev_s = w, w_spy, s
    return pd.DataFrame(rows).set_index("date")


# ---------------------------------------------------------------- macro series (frozen)
def load_macro():
    """Returns {name: pd.Series indexed by availability date} and a provenance dict."""
    prov, out = {}, {}
    man_p = os.path.join(CACHE, "MANIFEST.json")
    man = json.load(open(man_p))
    for name, info in man["files"].items():
        p = os.path.join(ROOT, info["path"])
        assert sha(p) == info["sha256"], f"{name}: frozen file changed"
        prov[name] = info
        if name == "VIX":
            v = pd.read_csv(p, parse_dates=["date"]).set_index("date")["close"].astype(float)
            out[name] = v                                    # close of the session: available at that close
            continue
        s = pd.read_csv(p, na_values=".")
        s.columns = ["date", "v"]
        s["date"] = pd.to_datetime(s["date"])
        s = s.dropna().set_index("date")["v"].astype(float)
        if info["frequency"] == "daily":
            s.index = s.index + pd.Timedelta(days=1)         # usable from S[t] with obs date <= S[t] - 1 day
        else:                                                # monthly average dated the 1st: from 1st of next month + 7 days
            s.index = (s.index + pd.offsets.MonthBegin(1)) + pd.Timedelta(days=7)
        out[name] = s
    return out, prov


def macro_at(series, dates):
    s = series.sort_index()
    pos = s.index.searchsorted(dates, side="right") - 1
    v = np.where(pos >= 0, s.values[np.maximum(pos, 0)], np.nan)
    return v


# ---------------------------------------------------------------- state variables
def resid5(d):
    """MASTER's 5-session target recomputed from r, rm, beta (sp500_test.build resid(5)); row s completes at s + 6."""
    r, rm, beta, S = d["r"], d["rm"], d["beta"], d["S"]
    cr = np.vstack([np.zeros((1, r.shape[1])), np.cumsum(np.nan_to_num(r), 0)])
    cm = np.concatenate([[0], np.cumsum(np.nan_to_num(rm))])
    h = 5
    y = np.full(r.shape, np.nan)
    n = len(S) - 1 - h
    a = np.arange(n) + 2
    y[:n] = (cr[a + h] - cr[a]) - beta[:n] * (cm[a + h] - cm[a])[:, None]
    valid = d["valid"]
    ok = np.zeros_like(valid)
    ok[:n] = valid[1 + h:] & valid[:n]
    y[~(ok & d["elig"])] = np.nan
    with np.errstate(all="ignore"):
        return y - np.nanmean(y, 1, keepdims=True)


def weekly_ic(pred, y, elig, rows):
    out = np.full(len(rows), np.nan)
    for i, t in enumerate(rows):
        m = np.isfinite(pred[t]) & np.isfinite(y[t]) & elig[t]
        if m.sum() >= 50:
            out[i] = pd.Series(pred[t][m]).corr(pd.Series(y[t][m]), method="spearman")
    return out


def expanding_z(x, min_obs=26):
    x = np.asarray(x, float)
    z = np.zeros(len(x))
    vals = []
    for i, v in enumerate(x):
        if np.isfinite(v):
            vals.append(v)
        if np.isfinite(v) and len(vals) >= min_obs:
            a = np.asarray(vals)
            sd = a.std(ddof=1)
            z[i] = (v - a.mean()) / sd if sd > 0 else 0.0
    return z


def states(d, pred, book, macro, upto=None, start="2010-01-01"):
    """State matrix at every Thursday from `start` (rows th). book: DataFrame from sim_book (row, end, book).
    Returns th, raw DataFrame, standardised matrix Z (n_th x K), names."""
    S = d["S"]
    th = np.where((S.weekday == 3) & (S >= pd.Timestamp(start)))[0]
    if upto is not None:
        th = th[th <= upto]
    th = th[th >= 260]
    spy, rm, r = d["spy"], d["rm"], d["r"]
    raw = {}
    for n, L in (("spy_1w", 5), ("spy_4w", 20), ("spy_13w", 65), ("spy_52w", 260)):
        raw[n] = spy[th] / spy[th - L] - 1
    for n, L in (("rv21", 21), ("rv63", 63)):
        raw[n] = np.array([np.nanstd(rm[t - L + 1: t + 1], ddof=1) * math.sqrt(252) for t in th])
    disp = []
    for t in th:
        g = np.prod(1 + r[t - 4: t + 1], 0) - 1
        m = d["elig"][t] & np.isfinite(g)
        disp.append(float(np.std(g[m], ddof=1)) if m.sum() > 30 else np.nan)
    raw["disp5"] = np.array(disp)
    # book's own trailing returns: completed periods only (end <= t)
    brow, bend, bret = book.row.to_numpy(), book.end.to_numpy(), book.book.to_numpy()
    # MASTER realised IC: targets complete at s + 6
    y = resid5(d)
    srows = brow                                        # decisions carrying a score
    ic = weekly_ic(pred, y, d["elig"], srows)
    for n, L in (("book_4", 4), ("book_13", 13), ("book_52", 52)):
        v = []
        for t in th:
            done = bret[bend <= t]
            v.append(float(done[-L:].mean()) if len(done) else np.nan)
        raw[n] = np.array(v)
    for n, L in (("ic_4", 4), ("ic_13", 13), ("ic_52", 52)):
        v = []
        for t in th:
            done = ic[(srows + 6 <= t) & np.isfinite(ic)]
            v.append(float(done[-L:].mean()) if len(done) else np.nan)
        raw[n] = np.array(v)
    dates = S[th]
    if "DTB3" in macro:
        raw["tbill"] = macro_at(macro["DTB3"], dates)
    if "DGS10" in macro and "DTB3" in macro:
        raw["term"] = macro_at(macro["DGS10"], dates) - macro_at(macro["DTB3"], dates)
    if "BAA" in macro and "AAA" in macro:
        raw["credit"] = macro_at(macro["BAA"], dates) - macro_at(macro["AAA"], dates)
    if "VIX" in macro:
        v = macro["VIX"]
        raw["vix"] = macro_at(v[v.index <= S[-1]], dates)
    raw = pd.DataFrame(raw, index=dates)
    Z = np.column_stack([expanding_z(raw[c].to_numpy()) for c in raw.columns])
    return th, raw, Z, list(raw.columns), y, ic


# ---------------------------------------------------------------- random Fourier features, dual ridge
def forecasts(Zd, b, end, rows, f_rows, cgrid, zgrid, seeds):
    """Zd: states at the decision rows (n x K); b: book return of each decision; end: its completion row.
    f_rows: indices (into rows) to forecast. Returns F[seed, c, z, i] for i over f_rows, and training sizes."""
    n, Kd = Zd.shape
    Pmax = P_of(max(cgrid))
    F = np.full((len(seeds), len(cgrid), len(zgrid), len(f_rows)), np.nan)
    Tn = np.zeros(len(f_rows), int)
    train = []
    for j, i in enumerate(f_rows):
        idx = np.where(end <= rows[i])[0][-T_WIN:]
        train.append(idx)
        Tn[j] = len(idx)
    zg = np.asarray(zgrid, float)
    for si, sd in enumerate(seeds):
        rng = np.random.default_rng(SEED0 + sd)
        Om = rng.standard_normal((Pmax // 2, Kd)).T           # columns nested in P
        A = GAMMA * Zd @ Om
        Sn, Cs = np.sin(A), np.cos(A)
        G = np.zeros((n, n))
        m0 = 0
        for ci, c in sorted(enumerate(cgrid), key=lambda x: x[1]):
            m = P_of(c) // 2
            G += Sn[:, m0:m] @ Sn[:, m0:m].T + Cs[:, m0:m] @ Cs[:, m0:m].T
            m0 = m
            for j, i in enumerate(f_rows):
                idx = train[j]
                T = len(idx)
                if T < T_MIN:
                    continue
                Gt = G[np.ix_(idx, idx)]
                cm = Gt.mean(0)
                Gc = Gt - cm[None, :] - cm[:, None] + cm.mean()       # H G H: features centred in the window
                gc = G[i, idx] - cm - G[i, idx].mean() + cm.mean()
                lam, V = np.linalg.eigh(Gc)
                lam = np.maximum(lam, 0)
                g = gc @ V
                yb = b[idx].mean()                                    # unpenalised intercept (amendment)
                q = V.T @ (b[idx] - yb)
                F[si, ci, :, j] = yb + (g[None, :] * q[None, :] / (lam[None, :] + zg[:, None] * T)).sum(1)
    return F, Tn


def benchmarks(b, end, rows):
    """B_m and B_mv raw signals at each decision from the last 52 completed book periods (amendment)."""
    m, mv = np.full(len(rows), np.nan), np.full(len(rows), np.nan)
    for i, t in enumerate(rows):
        done = b[end <= t][-52:]
        if len(done) == 52:
            m[i] = done.mean()
            v = done.var(ddof=1)
            mv[i] = done.mean() / v if v > 0 else np.nan
    return m, mv


def positions(f):
    """pi = clip(f / expanding mean |f|, 0, 2) over the forecast sequence (NaN before the first forecast)."""
    f = np.asarray(f, float)
    pi = np.full(len(f), np.nan)
    acc, cnt = 0.0, 0
    for i, v in enumerate(f):
        if not np.isfinite(v):
            continue
        acc += abs(v)
        cnt += 1
        m = acc / cnt
        pi[i] = float(np.clip(v / m, 0, 2)) if m > 0 else 1.0
    return pi


def timed(pi, b, gross, pi_prev0=1.0):
    """x_t = pi_t b_t - 5 bp |dpi| G_t; pi_{-1} = pi_prev0."""
    prev = np.concatenate([[pi_prev0], pi[:-1]])
    return pi * b - COST * np.abs(pi - prev) * gross


def sharpe(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(x.mean() / x.std(ddof=1) * math.sqrt(52)) if len(x) > 2 and x.std() > 0 else float("nan")


def select(pis, xs, rows, end, years, S):
    """Annual nested selection. pis, xs: dict cfg -> arrays over decisions (aligned with rows). For each year Y the
    cfg with the best Sharpe of x over the 52 latest decisions with end <= first decision of Y. Returns pi, choice."""
    yr = S[rows].year
    pi = np.full(len(rows), np.nan)
    choice = {}
    for Y in years:
        iy = np.where(yr == Y)[0]
        if not len(iy):
            continue
        t0 = rows[iy[0]]
        fin = np.all(np.vstack([np.isfinite(xs[k]) for k in xs]), 0)
        inner = np.where((end <= t0) & fin)[0][-52:]           # 2015: only 50 such weeks exist (data start 2013)
        assert len(inner) >= 26, (Y, len(inner))
        best, bs = None, -np.inf
        for k in pis:
            xv = xs[k][inner]
            s = sharpe(xv)
            if np.isfinite(s) and s > bs:
                best, bs = k, s
        choice[int(Y)] = {"cfg": best, "inner_sharpe": bs, "inner_weeks": int(len(inner)), "inner_first": str(S[rows[inner[0]]].date()),
                          "inner_last": str(S[rows[inner[-1]]].date())}
        pi[iy] = pis[best][iy]
    return pi, choice


# ---------------------------------------------------------------- the pipeline (development; also the timing test)
BOOK_COLS = (("book_4", 4), ("book_13", 13), ("book_52", 52))


def book_states(b, end, th):
    out = {}
    for n, L in BOOK_COLS:
        out[n] = np.array([float(b[end <= t][-L:].mean()) if (end <= t).any() else np.nan for t in th])
    return out


def strategies(F, b, end, rows, gross, cgrid, zgrid):
    """Per configuration: seed-averaged forecast, pi, x (whole series)."""
    Fm = np.nanmean(F, 0) if F.ndim == 4 else F
    fs, pis, xs = {}, {}, {}
    for ci, c in enumerate(cgrid):
        for zi, z in enumerate(zgrid):
            k = (c, z)
            f = Fm[ci, zi]
            pi = positions(f)
            ok = np.isfinite(pi)
            x = np.full(len(f), np.nan)
            x[ok] = timed(pi[ok], b[ok], gross[ok])
            fs[k], pis[k], xs[k] = f, pi, x
    return fs, pis, xs


def bench_x(b, end, rows, gross):
    m, mv = benchmarks(b, end, rows)
    out = {}
    for name, sig in (("B_m", m), ("B_mv", mv)):
        pi = positions(sig)
        ok = np.isfinite(pi)
        x = np.full(len(b), np.nan)
        x[ok] = timed(pi[ok], b[ok], gross[ok])
        out[name] = {"signal": sig, "pi": pi, "x": x}
    return out


def candidate(pis, xs, b, gross, rows, end, S, sel_years):
    pi, choice = select(pis, xs, rows, end, sel_years, S)
    ok = np.isfinite(pi)
    x = np.full(len(b), np.nan)
    x[ok] = timed(pi[ok], b[ok], gross[ok])
    return pi, x, choice


def pipeline(d, pred, macro, rf, book_years, sel_years, cgrid=CGRID, zgrid=ZGRID, seeds=range(NSEEDS), upto=None,
             keep_F=False):
    book = sim_book(d, pred, book_years, rf)
    th, raw, Z, names, y, ic = states(d, pred, book, macro, upto=upto)
    rows, end, b, gross = (book.row.to_numpy(), book.end.to_numpy(), book.book.to_numpy(), book.book_gross.to_numpy())
    pos = np.searchsorted(th, rows)
    assert (th[pos] == rows).all()
    Zd = Z[pos]
    F, Tn = forecasts(Zd, b, end, rows, np.arange(len(rows)), cgrid, zgrid, list(seeds))
    fs, pis, xs = strategies(F, b, end, rows, gross, cgrid, zgrid)
    pi, x, choice = candidate(pis, xs, b, gross, rows, end, d["S"], sel_years)
    bx = bench_x(b, end, rows, gross)
    out = {"book": book, "th": th, "raw": raw, "Z": Z, "names": names, "rows": rows, "end": end, "b": b, "gross": gross,
           "Zd": Zd, "Tn": Tn, "fs": fs, "pis": pis, "xs": xs, "pi": pi, "x": x, "choice": choice, "bench": bx, "ic": ic}
    if keep_F:
        out["F"] = F
    return out
