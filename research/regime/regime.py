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


# ------------------------------------------------------------------------------------------- round 2 (Amendment 1)
EVENTS = os.path.join(ROOT, ".cache", "p8", "events.parquet")


def build2(D):
    """Round-2 books and detectors, appended to the round-1 weekly frame (same decisions)."""
    P = panel()
    S, names = P["S"], P["names"]
    col = {t: j for j, t in enumerate(names)}
    ev = pd.read_parquet(EVENTS)
    ev = ev[(ev.universe == "sp500") & ev.ticker.isin(col) & (ev.t0 <= END)]
    tix = S.get_indexer(pd.DatetimeIndex(ev.t0))                    # report session index (t0 is a session)
    ev = ev.assign(ti=tix)[tix >= 0]
    print(f"events matched: {len(ev)} of S&P 500 rows; tickers {ev.ticker.nunique()}")
    lp = np.log(P["close"])
    vol60 = pd.DataFrame(P["r"]).rolling(60, min_periods=50).std().values
    hi252 = pd.DataFrame(P["close"]).rolling(252, min_periods=200).max().values
    cr = np.vstack([np.zeros((1, P["e"].shape[1])), np.nancumsum(np.nan_to_num(P["e"]), 0)])
    out = {k: [] for k in ("PEAD", "NREV", "LOWVOL", "HIGH52", "SECMOM")}
    rows = []
    for t in D["t"].to_numpy():
        el = P["elig"][t] & np.isfinite(P["close"][t + 1])
        R, Rm = hold_ret(P, t)
        g = sectors_at(P, t)
        e20 = ev[(ev.ti > t - 20) & (ev.ti <= t)]
        e5 = ev[(ev.ti > t - 5) & (ev.ti <= t)]
        row = {"crowd": float(sum(el[col[x]] for x in e5.ticker)), "season": float(sum(el[col[x]] for x in e20.ticker)) / max(el.sum(), 1)}
        # PEAD: latest report in the last 20 sessions, SUE quintiles
        sue = np.full(len(names), np.nan)
        for x, s_ in e20.sort_values("ti")[["ticker", "sue"]].itertuples(index=False):
            sue[col[x]] = s_
        sue[~el] = np.nan
        w = np.zeros(len(names)); wspy = 0.0
        if np.isfinite(sue).sum() >= 25:
            q = np.nanquantile(sue, [0.2, 0.8])
            L_, S_ = np.isfinite(sue) & (sue >= q[1]), np.isfinite(sue) & (sue <= q[0])
            w[L_], w[S_] = 0.5 / L_.sum(), -0.5 / S_.sum()
            wspy = -float(np.nansum(w * np.nan_to_num(P["beta"][t], nan=1.0)))
        out["PEAD"].append((w, wspy))
        # NREV: REV, sign flipped for names that reported in the formation week
        rev = -(cr[t + 1] - cr[t - 4])
        flip = np.zeros(len(names), bool)
        flip[[col[x] for x in e5.ticker]] = True
        out["NREV"].append(decile_book(zs(np.where(el, np.where(flip, -rev, rev), np.nan)), P["beta"][t]))
        out["LOWVOL"].append(decile_book(zs(np.where(el, -vol60[t], np.nan)), P["beta"][t]))
        out["HIGH52"].append(decile_book(zs(np.where(el, P["close"][t] / hi252[t], np.nan)), P["beta"][t]))
        # SECMOM: GICS sector equal-weight portfolios, 12-1 month log return; top 3 long, bottom 3 short
        secs = [s for s in sorted(set(g[el])) if s not in ("other", None) and (el & (g == s)).sum() >= 5]
        m12 = {}
        for s in secs:
            mm = el & (g == s)
            dr = np.nanmean(P["r"][t - 251:t - 19][:, mm], 1)
            m12[s] = np.nansum(np.log1p(dr))
        rk = sorted(secs, key=lambda s: m12[s])
        w = np.zeros(len(names))
        for s in rk[-3:]:
            mm = el & (g == s); w[mm] = 0.5 / 3 / mm.sum()
        for s in rk[:3]:
            mm = el & (g == s); w[mm] = -0.5 / 3 / mm.sum()
        out["SECMOM"].append((w, -float(np.nansum(w * np.nan_to_num(P["beta"][t], nan=1.0)))))
        for k in out:
            w, ws = out[k][-1]
            row[f"{k}_gross"] = float(np.nansum(w * R) + ws * Rm)
        rows.append(row)
    D2 = pd.DataFrame(rows, index=D.index)
    for k in out:
        np.save(os.path.join(OUT, f"book_{k}.npy"), np.array([w for w, _ in out[k]], dtype=np.float32))
        np.save(os.path.join(OUT, f"hedge_{k}.npy"), np.array([s for _, s in out[k]]))
    return pd.concat([D.drop(columns=[c for c in D2.columns if c in D.columns]), D2], axis=1)


if __name__ == "__main__" and sys.argv[1:] == ["build2"]:
    D = pd.read_parquet(os.path.join(OUT, "weekly.parquet"))
    D = build2(D)
    D.to_parquet(os.path.join(OUT, "weekly.parquet"))
    dev_ = D[D["date"] <= pd.Timestamp("2019-12-31")]                 # sanity on development rows only
    print(dev_[[c for c in D.columns if c.endswith("_gross") or c in ("crowd", "season")]].describe().T.round(4).to_string())


# ------------------------------------------------------------------------------------------- round 3 (Amendment 2)
def banded(scores, beta_rows, inner=0.1, outer=0.3):
    """Path-dependent band book per decision: enter at the top/bottom `inner` quantile, keep while inside `outer`."""
    out, L, Sh = [], set(), set()
    for sc, beta in zip(scores, beta_rows):
        m = np.isfinite(sc)
        w = np.zeros(sc.shape)
        if m.sum() < 50:
            out.append((w, 0.0)); L, Sh = set(), set(); continue
        qi = np.nanquantile(sc[m], [inner, 1 - inner]); qo = np.nanquantile(sc[m], [outer, 1 - outer])
        L = {j for j in np.where(m & (sc >= qi[1]))[0]} | {j for j in L if m[j] and sc[j] >= qo[1]}
        Sh = {j for j in np.where(m & (sc <= qi[0]))[0]} | {j for j in Sh if m[j] and sc[j] <= qo[0]}
        if L and Sh:
            w[list(L)], w[list(Sh)] = 0.5 / len(L), -0.5 / len(Sh)
        out.append((w, -float(np.nansum(w * np.nan_to_num(beta, nan=1.0)))))
    return out


def novelty_panel(S, dec, names):
    """H13: per decision and firm (31 names): formation-week news centroid's novelty against the trailing 13- and
    26-week centroids of the same firm (weeks with news only)."""
    out = {13: np.full((len(dec), len(names)), np.nan), 26: np.full((len(dec), len(names)), np.nan)}
    col = {t: j for j, t in enumerate(names)}
    for f in sorted(glob.glob(os.path.join(TEXT, "*_dedup.npz"))):
        tk = os.path.basename(f).split("_")[0]
        if tk not in col:
            continue
        z = np.load(f)
        s = pd.DatetimeIndex(z["session"].astype("datetime64[ns]"))
        C = np.full((len(dec), z["sum"].shape[1]), np.nan, dtype=np.float32)
        for k, t in enumerate(dec):
            lo = S[dec[k - 1]] if k else S[t] - pd.Timedelta(days=7)
            m = (s > lo) & (s <= S[t])
            if z["n"][m].sum() > 0:
                C[k] = z["sum"][m].sum(0) / z["n"][m].sum()
        for w in (13, 26):
            for k in range(w, len(dec)):
                if not np.all(np.isfinite(C[k])):
                    continue
                past = C[k - w:k]
                past = past[np.all(np.isfinite(past), 1)]
                if len(past) < w // 2:
                    continue
                c, p = C[k], past.mean(0)
                out[w][k, col[tk]] = 1 - float(c @ p / (np.linalg.norm(c) * np.linalg.norm(p)))
    return out


def build3(D):
    P = panel()
    S, names = P["S"], P["names"]
    col = {t: j for j, t in enumerate(names)}
    dec = D["t"].to_numpy()
    ev = pd.read_parquet(EVENTS)
    ev = ev[(ev.universe == "sp500") & ev.ticker.isin(col) & (ev.t0 <= END)]
    ev = ev.assign(ti=S.get_indexer(pd.DatetimeIndex(ev.t0)))
    cr = np.vstack([np.zeros((1, P["e"].shape[1])), np.nancumsum(np.nan_to_num(P["e"]), 0)])
    rev_s, nrev_s, betas, r5res, el_rows = [], [], [], [], []
    for t in dec:
        el = P["elig"][t] & np.isfinite(P["close"][t + 1])
        rev = -(cr[t + 1] - cr[t - 4])
        flip = np.zeros(len(names), bool)
        flip[[col[x] for x in ev[(ev.ti > t - 5) & (ev.ti <= t)].ticker]] = True
        rev_s.append(zs(np.where(el, rev, np.nan)))
        nrev_s.append(zs(np.where(el, np.where(flip, -rev, rev), np.nan)))
        betas.append(P["beta"][t]); r5res.append(-rev); el_rows.append(el)
    rows = []
    books = {"REVB": banded(rev_s, betas), "NREVB": banded(nrev_s, betas)}
    # H13: novelty books on the 31 names with news in the formation week
    nov = novelty_panel(S, dec, names)
    fm = {13: [], 26: []}
    for w in (13, 26):
        books[f"NOV{w}"], books[f"NOVB{w}"], books[f"NOVREV{w}"] = [], [], []
    for k, t in enumerate(dec):
        R, Rm = hold_ret(P, t)
        yres = R - P["beta"][t] * Rm
        row = {}
        for w in (13, 26):
            nv = nov[w][k]
            m = np.isfinite(nv) & el_rows[k] & np.isfinite(r5res[k]) & np.isfinite(yres)
            wN, wB, wR, wspyN, wspyB, wspyR, b2 = np.zeros(len(names)), np.zeros(len(names)), np.zeros(len(names)), 0.0, 0.0, 0.0, np.nan
            if m.sum() >= 8:
                x1 = r5res[k][m]; x1 = (x1 - x1.mean()) / (x1.std() or 1)
                rk = (pd.Series(nv[m]).rank().to_numpy() - 0.5) / m.sum()
                X = np.column_stack([np.ones(m.sum()), x1, x1 * (rk - 0.5)])
                b2 = float(np.linalg.lstsq(X, yres[m], rcond=None)[0][2])
                idx = np.where(m)[0]
                for score, wv in ((x1 * (2 * rk - 1), wN), (x1 * np.sign(rk - 0.5), wB), (-x1, wR)):
                    o = np.argsort(score); n3 = max(1, m.sum() // 3)
                    wv[idx[o[-n3:]]] = 0.5 / n3; wv[idx[o[:n3]]] = -0.5 / n3
                bt = np.nan_to_num(P["beta"][t], nan=1.0)
                wspyN, wspyB, wspyR = -float((wN * bt).sum()), -float((wB * bt).sum()), -float((wR * bt).sum())
            books[f"NOV{w}"].append((wN, wspyN)); books[f"NOVB{w}"].append((wB, wspyB)); books[f"NOVREV{w}"].append((wR, wspyR))
            row[f"nov_b2_{w}"], row[f"nov_n_{w}"] = b2, int(m.sum())
        for kname in books:
            wv, ws = books[kname][k]
            row[f"{kname}_gross"] = float(np.nansum(wv * R) + ws * Rm)
        rows.append(row)
    for kname in books:
        np.save(os.path.join(OUT, f"book_{kname}.npy"), np.array([w for w, _ in books[kname]], dtype=np.float32))
        np.save(os.path.join(OUT, f"hedge_{kname}.npy"), np.array([s for _, s in books[kname]]))
    D3 = pd.DataFrame(rows, index=D.index)
    return pd.concat([D.drop(columns=[c for c in D3.columns if c in D.columns]), D3], axis=1)


KF49 = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/49_Industry_Portfolios_daily_CSV.zip"


def kf_industries():
    """Ken French 49 industries, value-weighted daily returns (fractions), 1926-07 .. 2025-12-31; cached raw zip."""
    import io, urllib.request, zipfile
    p = os.path.join(OUT, "49_Industry_Portfolios_daily_CSV.zip")
    if not os.path.exists(p):
        urllib.request.urlretrieve(KF49, p)
    raw = zipfile.ZipFile(p).read(zipfile.ZipFile(p).namelist()[0]).decode("latin-1").splitlines()
    start = next(i for i, l in enumerate(raw) if l.strip().startswith(",") or l.lower().startswith(" ,agric") or "Agric" in l)
    rows = []
    for l in raw[start + 1:]:
        parts = [x.strip() for x in l.split(",")]
        if not parts[0].isdigit() or len(parts[0]) != 8:
            break                                                    # the first (value-weighted) table ends here
        rows.append(parts)
    hdr = [x.strip() for x in raw[start].split(",")][1:]
    df = pd.DataFrame([r[1:] for r in rows], index=pd.to_datetime([r[0] for r in rows]), columns=hdr).astype(float)
    df = df.where(df > -99) / 100
    return df[df.index <= END]


def build_kf():
    R = kf_industries()
    S = R.index
    X = R.to_numpy()
    lr = np.log1p(X)
    cum = np.vstack([np.zeros((1, X.shape[1])), np.nancumsum(np.nan_to_num(lr), 0)])
    resid = X - np.nanmean(X, 1, keepdims=True)
    dec = [t for t in range(260, len(S) - 6) if S[t].weekday() == 3]
    rows, W = [], []
    for t in dec:
        m12 = cum[t - 20] - cum[t - 251]                              # 12-1 month log return
        ok = np.isfinite(X[t - 251:t + 7]).all(0)
        w = np.zeros(X.shape[1])
        if ok.sum() >= 30:
            o = np.argsort(np.where(ok, m12, np.nan))
            o = [j for j in o if ok[j]]
            w[o[-7:]], w[o[:7]] = 0.5 / 7, -0.5 / 7
        Rh = np.exp(cum[t + 7] - cum[t + 1]) - 1                      # close t+1 -> close t+6
        row = {"date": S[t], "IMOM_gross": float(np.nansum(w * Rh))}
        for L in (21, 63):
            E = resid[t - L + 1:t + 1][:, ok]
            C = np.corrcoef(E.T)
            n = C.shape[0]
            row[f"iacorr{L}"] = float((C.sum() - n) / (n * (n - 1)))
        rows.append(row); W.append(w)
    D = pd.DataFrame(rows)
    np.save(os.path.join(OUT, "book_IMOM.npy"), np.array(W, dtype=np.float32))
    D.to_parquet(os.path.join(OUT, "kf_weekly.parquet"))
    return D


if __name__ == "__main__" and sys.argv[1:] == ["build3"]:
    D = pd.read_parquet(os.path.join(OUT, "weekly.parquet"))
    D = build3(D)
    D.to_parquet(os.path.join(OUT, "weekly.parquet"))
    dev_ = D[D["date"] <= pd.Timestamp("2019-12-31")]
    print(dev_[[c for c in D.columns if c.startswith(("REVB", "NREVB", "NOV")) or c.startswith("nov_n")]].describe().T.round(4).to_string())
    K = build_kf()
    kd = K[K["date"] <= pd.Timestamp("1999-12-31")]
    print("KF weeks", len(K), "dev", len(kd), K["date"].min().date(), K["date"].max().date())
    print(kd.describe().T.round(4).to_string())


# ------------------------------------------------------------------------------------------- round 4 (Amendment 3)
KF_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"


def kf_daily(fname):
    """A Ken French daily CSV (zip) as fractions by date, first table only, up to 2025-12-31; raw zip cached."""
    import urllib.request, zipfile
    p = os.path.join(OUT, fname)
    if not os.path.exists(p):
        urllib.request.urlretrieve(KF_URL + fname, p)
    raw = zipfile.ZipFile(p).read(zipfile.ZipFile(p).namelist()[0]).decode("latin-1").splitlines()
    start = next(i for i, l in enumerate(raw) if l.count(",") >= 1 and not l.split(",")[0].strip().isdigit()
                 and any(c.isalpha() for c in l.split(",")[1]) and i + 1 < len(raw) and raw[i + 1].split(",")[0].strip().isdigit())
    hdr = [x.strip() for x in raw[start].split(",")][1:]
    rows = []
    for l in raw[start + 1:]:
        parts = [x.strip() for x in l.split(",")]
        if not (parts[0].isdigit() and len(parts[0]) == 8):
            break
        rows.append(parts)
    df = pd.DataFrame([r[1:] for r in rows], index=pd.to_datetime([r[0] for r in rows]), columns=hdr).astype(float)
    df = df.where(df > -99) / 100
    return df[df.index <= END]


def build_umd():
    U = kf_daily("F-F_Momentum_Factor_daily_CSV.zip").iloc[:, 0].rename("UMD")
    F = kf_daily("F-F_Research_Data_Factors_daily_CSV.zip")
    X = pd.concat([U, F["Mkt-RF"] + F["RF"]], axis=1, join="inner").rename(columns={0: "MKT"}).dropna()
    X.columns = ["UMD", "MKT"]
    S = X.index
    lu, lm = np.log1p(X["UMD"].to_numpy()), np.log1p(X["MKT"].to_numpy())
    cu, cm = np.r_[0, np.cumsum(lu)], np.r_[0, np.cumsum(lm)]
    rows = []
    for t in range(260, len(S) - 6):
        if S[t].weekday() != 3:
            continue
        row = {"date": S[t], "UMD_gross": float(np.exp(cu[t + 7] - cu[t + 1]) - 1), "bear": float(cm[t + 1] - cm[t - 251] < 0)}
        for L in (21, 63):
            row[f"mvol{L}"] = float(np.std(lm[t - L + 1:t + 1]))
        for L in (126, 252):
            row[f"umdvol{L}"] = float(np.std(lu[t - L + 1:t + 1]))
        rows.append(row)
    D = pd.DataFrame(rows)
    D.to_parquet(os.path.join(OUT, "umd_weekly.parquet"))
    return D


if __name__ == "__main__" and sys.argv[1:] == ["build4"]:
    D = build_umd()
    d = D[D["date"] <= pd.Timestamp("1999-12-31")]
    print("UMD weeks", len(D), D["date"].min().date(), D["date"].max().date(), "dev", len(d))
    print(d.describe().T.round(4).to_string())
