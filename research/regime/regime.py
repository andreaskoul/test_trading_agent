"""Regime-dependent edges in S&P 500 stocks (research/regime/PREREG.md): panel, base books, regime detectors.

    python research/regime/regime.py build      # -> .cache/regime/weekly.parquet (one row per decision)

Everything at decision t uses closes up to t only. Weekly books are entered at close t+1 and held to close t+6.
Nothing after 2025-12-31 is read.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QT = os.path.join(ROOT, ".cache", "quant_trials")
OUT = os.path.join(ROOT, ".cache", "regime")
END = pd.Timestamp("2025-12-31")
COST = 5e-4
TEXT = os.path.join(QT, "text")


# ------------------------------------------------------------------------------------------------------------ panel
def panel():
    px = pd.read_parquet(os.path.join(QT, "sp500_close.parquet"))
    px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
    px = px[px.index <= END]
    spy = px.pop("SPY")
    mem = pd.read_csv(os.path.join(ROOT, "data", "raw", "stocks", "sp500_membership.csv"), parse_dates=["date"])
    mem = mem[mem.date <= END].set_index("date")["tickers"].map(lambda s: set(s.split(",")))
    mem = mem.reindex(px.index, method="ffill")
    names = list(px.columns)
    elig = np.array([[t in s for t in names] for s in mem.values]) & np.isfinite(px.values)
    r = px.pct_change().values
    rm = spy.pct_change().values
    # shrunk beta over 252 sessions, as the S&P panel (sp500_test.build): winsorised returns, 2/3 beta + 1/3
    lo, hi = np.minimum(-2 * rm, 4 * rm)[:, None], np.maximum(-2 * rm, 4 * rm)[:, None]
    w = pd.DataFrame(np.clip(r, lo, hi), index=px.index)
    m = pd.Series(rm, index=px.index)
    beta = ((2 / 3) * w.rolling(252, min_periods=200).cov(m).div(m.rolling(252, min_periods=200).var(), axis=0)
            .fillna(1.0) + 1 / 3).values
    e = r - np.vstack([np.full((1, r.shape[1]), np.nan), beta[:-1]]) * rm[:, None]      # residual, beta of t-1
    meta = pd.read_csv(os.path.join(ROOT, "data", "raw", "stocks", "sp500_current.csv")).set_index("Symbol")
    gics = np.array([meta["GICS Sector"].get(t, None) or None for t in names], dtype=object)
    return dict(S=px.index, names=names, close=px.values, spy=spy.values, r=r, rm=rm, beta=beta, e=e, elig=elig, gics=gics)


def sectors_at(P, t):
    """Sector of every name at decision t: GICS where known; otherwise the sector whose equal-weight daily return the
    name's returns correlate with most over the trailing 252 sessions (past data only)."""
    g = P["gics"].copy()
    known = np.array([x is not None for x in g])
    a = max(0, t - 251)
    R = P["r"][a:t + 1]
    labs = sorted(set(g[known]))
    sec = np.column_stack([np.nanmean(np.where(P["elig"][a:t + 1][:, known & (g == s)], R[:, known & (g == s)], np.nan), 1)
                           for s in labs])
    for j in np.where(~known & P["elig"][t])[0]:
        x = R[:, j]
        ok = np.isfinite(x) & np.all(np.isfinite(sec), 1)
        if ok.sum() < 60:
            g[j] = "other"
            continue
        c = [np.corrcoef(x[ok], sec[ok, k])[0, 1] for k in range(len(labs))]
        g[j] = labs[int(np.nanargmax(c))]
    g[~known & ~P["elig"][t]] = "other"
    return g


# ------------------------------------------------------------------------------------------------------------ books
def zs(x):
    m = np.isfinite(x)
    out = np.full(x.shape, np.nan)
    if m.sum() > 10:
        out[m] = (x[m] - x[m].mean()) / x[m].std()
    return out


def decile_book(score, beta):
    """Long the top decile, short the bottom, 50% per side, equal weight; SPY sets beta to zero."""
    m = np.isfinite(score)
    w = np.zeros(score.shape)
    if m.sum() < 50:
        return w, 0.0
    q = np.nanquantile(score[m], [0.1, 0.9])
    L, Sh = m & (score >= q[1]), m & (score <= q[0])
    w[L], w[Sh] = 0.5 / L.sum(), -0.5 / Sh.sum()
    return w, -float(np.nansum(w * np.nan_to_num(beta, nan=1.0)))


def hold_ret(P, t):
    """Holding returns close t+1 -> close t+6 per name (a name that stops trading inside the week: to its last
    close), and SPY's."""
    c = P["close"]
    a, b = t + 1, t + 6
    seg = c[a:b + 1]
    last = pd.DataFrame(seg).ffill().values[-1]
    R = last / seg[0] - 1
    return R, P["spy"][b] / P["spy"][a] - 1


# -------------------------------------------------------------------------------------------------------- detectors
def avg_corrs(E, groups):
    """Average pairwise correlation within groups and across groups of the columns of E (sessions x names)."""
    ok = np.all(np.isfinite(E), 0) & (np.nanstd(E, 0) > 0)
    E, groups = E[:, ok], groups[ok]
    Z = (E - E.mean(0)) / E.std(0)
    L, N = Z.shape
    tot = (Z.sum(1) ** 2).sum() / L
    within, pairs_w, ng2 = 0.0, 0.0, 0.0
    for gname in np.unique(groups):
        Zg = Z[:, groups == gname]
        n = Zg.shape[1]
        within += (Zg.sum(1) ** 2).sum() / L - n
        pairs_w += n * (n - 1)
        ng2 += n * n
    across = (tot - N) - within
    return within / max(pairs_w, 1), across / max(N * N - ng2, 1)


def news_weekly(S, dec):
    """Per decision: D4 news homogeneity and D5 news shift from the 31-name panel (weekly centroids)."""
    files = sorted(glob.glob(os.path.join(TEXT, "*_dedup.npz")))
    W = {}
    for f in files:
        z = np.load(f)
        s = pd.DatetimeIndex(z["session"].astype("datetime64[ns]"))
        W[os.path.basename(f).split("_")[0]] = (s, z["n"], z["sum"])
    dim = next(iter(W.values()))[2].shape[1]
    rows = []
    for k, t in enumerate(dec):
        lo = S[dec[k - 1]] if k else S[t] - pd.Timedelta(days=7)
        rows.append({})
        for f, (s, n, sm) in W.items():
            m = (s > lo) & (s <= S[t])
            if n[m].sum() > 0:
                rows[-1][f] = sm[m].sum(0) / n[m].sum()
    firms = sorted(W)
    C = np.full((len(dec), len(firms), dim), np.nan, dtype=np.float32)
    for k, row in enumerate(rows):
        for j, f in enumerate(firms):
            if f in row:
                C[k, j] = row[f]
    hom, shift = np.full(len(dec), np.nan), np.full(len(dec), np.nan)
    unit = lambda v: v / np.linalg.norm(v, axis=-1, keepdims=True)
    for k in range(52, len(dec)):
        base = np.nanmean(C[k - 52:k], 0)                                    # each firm's trailing 52-week centroid
        X = C[k] - base
        ok = np.all(np.isfinite(X), 1) & (np.linalg.norm(np.nan_to_num(X), axis=1) > 0)
        if ok.sum() >= 8:
            U = unit(X[ok])
            G = U @ U.T
            n = ok.sum()
            hom[k] = (G.sum() - n) / (n * (n - 1))
        cur = np.nanmean(C[k], 0)
        past = np.nanmean(np.nanmean(C[k - 13:k], 1), 0)
        if np.all(np.isfinite(cur)) and np.all(np.isfinite(past)):
            shift[k] = 1 - float(unit(cur) @ unit(past))
    return hom, shift


def hmm_prob(S, rm, dec):
    """D6: filtered P(high-volatility state) at each decision from a 2-state Gaussian HMM on weekly SPY return and
    log realised volatility, refit each January on all prior weeks (forward filter only)."""
    from hmmlearn.hmm import GaussianHMM
    lr = np.log1p(np.nan_to_num(rm))
    wk_ret = np.array([lr[d - 4:d + 1].sum() for d in dec])
    wk_vol = np.log(np.array([lr[d - 4:d + 1].std() for d in dec]) + 1e-5)
    X = np.column_stack([wk_ret, wk_vol])
    yrs = S[dec].year
    p = np.full(len(dec), np.nan)
    for y in sorted(set(yrs)):
        tr = np.where(yrs < y)[0]
        if len(tr) < 104:
            continue
        mdl = GaussianHMM(2, covariance_type="full", n_iter=200, random_state=0).fit(X[tr])
        hi = int(np.argmax(mdl.means_[:, 1]))
        idx = np.where(yrs <= y)[0]
        alpha = _forward(mdl, X[: idx[-1] + 1])          # forward filter: P(state at k) uses weeks up to k only
        for k in np.where(yrs == y)[0]:
            p[k] = alpha[k, hi]
    return p


def _forward(mdl, X):
    from scipy.stats import multivariate_normal as mvn
    B = np.column_stack([mvn(mdl.means_[i], mdl.covars_[i]).pdf(X) for i in range(mdl.n_components)])
    a = np.zeros_like(B)
    a[0] = mdl.startprob_ * B[0]
    a[0] /= a[0].sum()
    for k in range(1, len(X)):
        a[k] = (a[k - 1] @ mdl.transmat_) * B[k]
        a[k] /= a[k].sum()
    return a


def pct_hist(x, n):
    """Percentile of x[k] against x[k-n:k] (expanding before n values exist; at least 26)."""
    out = np.full(len(x), np.nan)
    for k in range(len(x)):
        h = x[max(0, k - n):k]
        h = h[np.isfinite(h)]
        if len(h) >= 26 and np.isfinite(x[k]):
            out[k] = (h < x[k]).mean()
    return out


# ------------------------------------------------------------------------------------------------------------ build
def build():
    P = panel()
    S, n = P["S"], len(P["S"])
    dec = np.array([t for t in range(260, n - 6) if S[t].weekday() == 3])
    lp = np.log(P["close"])
    rows, books = [], {"REV": [], "SREV": [], "MOM": []}
    cr = np.vstack([np.zeros((1, P["e"].shape[1])), np.nancumsum(np.nan_to_num(P["e"]), 0)])
    for t in dec:
        el = P["elig"][t] & np.isfinite(P["close"][t + 1])
        g = sectors_at(P, t)
        rev = -(cr[t + 1] - cr[t - 4])
        r5 = P["close"][t] / P["close"][t - 5] - 1
        sec_mean = {s: np.nanmean(np.where(el & (g == s), r5, np.nan)) for s in set(g[el])}
        srev = -(r5 - np.array([sec_mean.get(s, np.nan) for s in g]))
        mom = lp[t - 20] - lp[t - 252]
        R, Rm = hold_ret(P, t)
        row = {"t": int(t), "date": S[t], "rm_hold": Rm}
        for k, sc in (("REV", rev), ("SREV", srev), ("MOM", mom)):
            sc = np.where(el, sc, np.nan)
            w, wspy = decile_book(zs(sc), P["beta"][t])
            row[f"{k}_gross"] = float(np.nansum(w * R) + wspy * Rm)
            books[k].append((w, wspy))
        # detectors
        for L in (21, 63):
            row[f"vol{L}"] = float(np.nanstd(P["rm"][t - L + 1:t + 1]) * np.sqrt(252))
            E = P["e"][t - L + 1:t + 1][:, el]
            wi, ac = avg_corrs(E, g[el])
            row[f"scorr{L}"], row[f"wcorr{L}"], row[f"acorr{L}"] = wi - ac, wi, ac
        row["bear"] = float(P["spy"][t] / P["spy"][t - 252] - 1 < 0)
        rows.append(row)
    D = pd.DataFrame(rows)
    for k in books:                                       # turnover of the unconditioned book (week to week)
        prev = None
        to = []
        for w, wspy in books[k]:
            to.append(np.nan if prev is None else float(np.abs(w - prev[0]).sum() + abs(wspy - prev[1])))
            prev = (w, wspy)
        D[f"{k}_to"] = to
        np.save(os.path.join(OUT, f"book_{k}.npy"), np.array([w for w, _ in books[k]], dtype=np.float32))
        np.save(os.path.join(OUT, f"hedge_{k}.npy"), np.array([s for _, s in books[k]]))
    D["newshom"], D["newsshift"] = news_weekly(S, dec)
    D["hmm"] = hmm_prob(S, P["rm"], dec)
    return D


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    if sys.argv[1:] == ["build"]:
        D = build()
        D.to_parquet(os.path.join(OUT, "weekly.parquet"))
        print(D.describe().T.to_string())
