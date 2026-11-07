"""Risk-field research (PREREG.md §§3-5, 7): features, kernels, monthly-refitted pooled forecasts, losses.

    python research/riskfield/risk.py dev      # development statistics only (targets ending 2017-01-03..2019-12-31)

The OOS read is `oos.py`. Forecasts are made only for origins up to the period being evaluated.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel as P                                                                   # noqa: E402

DEV = (pd.Timestamp("2017-01-03"), pd.Timestamp("2019-12-31"))
OOS = (pd.Timestamp("2020-01-02"), pd.Timestamp("2025-12-31"))
HS = (5, 22)


# ------------------------------------------------------------------------------------------------------- features
def roll_mean(x, n, need):
    """Trailing mean over sessions t-n+1..t of the finite values; NaN with fewer than `need` finite values."""
    f = np.isfinite(x)
    c = np.vstack([np.zeros((1,) + x.shape[1:]), np.cumsum(np.where(f, x, 0), 0)])
    k = np.vstack([np.zeros((1,) + x.shape[1:]), np.cumsum(f, 0)])
    s, cnt = c[n:] - c[:-n], k[n:] - k[:-n]
    out = np.full(x.shape, np.nan)
    out[n - 1:] = np.where(cnt >= need, s / np.maximum(cnt, 1), np.nan)
    return out


def fwd_mean(x, h, need):
    """Mean over sessions t+1..t+h of the finite values; NaN with fewer than `need`."""
    m = roll_mean(x, h, need)
    out = np.full(x.shape, np.nan)
    out[:-h] = m[h:]
    return out


class Data:
    def __init__(self):
        H = P.load_hf()
        self.S, self.names = H["S"], list(H["names"])
        self.R = H["R"].astype(float)
        si = self.names.index("SPY")
        self.si = si
        rv, rq = H["rv"], H["rq"]
        self.rv = rv
        self.d = np.log(rv)
        self.w = np.log(roll_mean(rv, 5, 4))
        self.m = np.log(roll_mean(rv, 22, 17))
        self.q = np.sqrt(rq) / rv
        self.rvbar = {h: fwd_mean(rv, h, int(np.ceil(0.8 * h))) for h in HS}
        self.y = {h: np.log(self.rvbar[h]) for h in HS}
        T, N = rv.shape
        self.T, self.N = T, N
        self.stock = np.array([n != "SPY" for n in self.names])
        # earnings reaction sessions
        ev = pd.read_parquet(os.path.join(P.P8, "events.parquet"), columns=["ticker", "t0"])
        ev = ev[ev.t0 <= P.END]
        E = np.zeros((T, N))
        ni = pd.Index(self.names).get_indexer(ev.ticker)
        ti = np.searchsorted(self.S.values, ev.t0.values.astype("datetime64[ns]"))
        ok = (ni >= 0) & (ti < T)
        E[ti[ok], ni[ok]] = 1
        ce = np.vstack([np.zeros((1, N)), np.cumsum(E, 0)])
        self.E = {}
        for h in HS:
            x = np.zeros((T, N))
            x[:T - h] = (ce[h + 1:T + 1] - ce[1:T - h + 1]) > 0
            self.E[h] = x
        meta = pd.read_csv(os.path.join(P.ROOT, "data", "raw", "stocks", "sp500_current.csv")).set_index("Symbol")
        self.gics = np.array([meta["GICS Sector"].get(n, None) if n != "SPY" else None for n in self.names],
                             dtype=object)
        # daily close-to-close log returns from the bars (14 returns summed)
        self.r = np.where(np.isfinite(self.R).all(1), self.R.sum(1), np.nan)
        mstart = pd.Series(np.arange(T), index=self.S).groupby([self.S.year, self.S.month]).min().to_numpy()
        self.mstart = mstart
        self._K = {}

    # ---------------------------------------------------------------------------------------------- kernels
    def kernel(self, kind, tau):
        """Kernel used for sessions of the month starting at session tau (built from information to tau-1)."""
        key = (kind, tau)
        if key in self._K:
            return self._K[key]
        N = self.N
        if kind == "sector":
            W = np.zeros((N, N))
            for g in set(x for x in self.gics if x):
                ix = np.where(self.gics == g)[0]
                W[np.ix_(ix, ix)] = 1.0
            np.fill_diagonal(W, 0)
        elif kind == "text":
            W, _ = P.text_kernel(self.names, self.S[tau])
            W[~self.stock] = 0
            W[:, ~self.stock] = 0
        elif kind == "co":
            a = max(0, tau - 252)
            x = self.r[a:tau]
            xm = x[:, self.si]
            W = np.zeros((N, N))
            ok = (np.isfinite(x).sum(0) >= 200) & self.stock
            if ok.sum() > 20:
                X = x[:, ok]
                good = np.isfinite(X) & np.isfinite(xm)[:, None]
                Xm = np.where(good, xm[:, None], np.nan)
                b = np.nansum((X - np.nanmean(X, 0)) * (Xm - np.nanmean(Xm, 0)), 0) / np.nansum(
                    (Xm - np.nanmean(Xm, 0)) ** 2, 0)
                e = X - b * Xm
                e = np.where(good, e - np.nanmean(e, 0), 0.0)
                cnt = good.astype(float)
                C = (e.T @ e) / np.sqrt(np.outer((e ** 2).sum(0), (e ** 2).sum(0)))
                np.fill_diagonal(C, -np.inf)
                idx = np.where(ok)[0]
                top = np.argpartition(-C, 9, axis=1)[:, :10]
                for i, js in enumerate(top):
                    c = np.maximum(C[i, js], 0)
                    if c.sum() > 0:
                        W[idx[i], idx[js]] = c / c.sum()
                del cnt
        else:
            raise KeyError(kind)
        self._K[key] = W
        return W

    def field(self, kind, x):
        """F_K(x) per session with the month's kernel, renormalised over neighbours with a finite value (NaN when
        less than half the kernel weight has data, or the name has no kernel row)."""
        out = np.full(x.shape, np.nan)
        bounds = list(self.mstart) + [self.T]
        for a, b in zip(bounds[:-1], bounds[1:]):
            W = self.kernel(kind, a)
            if kind == "sector":
                W = W / np.maximum(W.sum(1, keepdims=True), 1e-12)
            rowm = W.sum(1)
            xs = x[a:b]
            f = np.isfinite(xs)
            num = np.nan_to_num(xs) @ W.T
            den = f.astype(float) @ W.T
            v = np.where((den >= 0.5 * rowm) & (rowm > 0), num / np.maximum(den, 1e-12), np.nan)
            out[a:b] = v
        return out

    # ------------------------------------------------------------------------------------------------ models
    def regressors(self, model, h):
        """List of T x N arrays (without intercept) for a model name."""
        bc = lambda v: np.broadcast_to(v[:, self.si:self.si + 1], (self.T, self.N))
        base = [self.d, self.w, self.m, bc(self.d), bc(self.w), bc(self.m), self.E[h]]
        if model == "M0":
            return base
        sec = [self.cached("fsec_w", lambda: self.field("sector", self.w)),
               self.cached("fsec_m", lambda: self.field("sector", self.m))]
        if model in ("MS", "MS_ew"):
            return base + sec
        if model == "MS_text":
            return base + sec + [self.cached("ftxt_w", lambda: self.field("text", self.w)),
                                 self.cached("ftxt_m", lambda: self.field("text", self.m))]
        if model == "MS_co":
            return base + sec + [self.cached("fco_w", lambda: self.field("co", self.w)),
                                 self.cached("fco_m", lambda: self.field("co", self.m))]
        if model == "MS_q":
            return base + sec + [self.d * self.q]
        if model in ("NB", "N1", "N1_placebo"):
            nz = self.cached("news", self.news)
            X = base + sec + [nz["lc"], nz["lc_ew"], nz["day"]]
            if model == "NB":
                return X
            u, uew = (nz["u"], nz["u_ew"]) if model == "N1" else (nz["u_pl"], nz["u_pl_ew"])
            return X + [u, uew]
        if model == "MS_reg":
            st = self.cached("state", self.state)
            X = base + sec
            return X + [st] + [x * st for x in X]
        raise KeyError(model)

    def cached(self, k, f):
        if not hasattr(self, "_c"):
            self._c = {}
        if k not in self._c:
            self._c[k] = f()
        return self._c[k]

    def news(self):
        """31 names (others NaN): log(1 + count), its 5-session EWMA (span 5), news-day dummy, unusualness and its
        EWMA; the placebo shuffles u across the 31 names within each day (seed 7)."""
        z = np.load(os.path.join(P.CACHE, "news.npz"))
        ix = pd.Index(self.names).get_indexer(z["names"])
        out = {k: np.full((self.T, self.N), np.nan) for k in ("lc", "lc_ew", "day", "u", "u_ew", "u_pl", "u_pl_ew")}
        n, u = z["n"][:, ix >= 0], z["u"][:, ix >= 0]
        ix = ix[ix >= 0]
        first = np.argmax(n > 0, 0)
        live = np.arange(self.T)[:, None] >= first[None, :]
        rng = np.random.default_rng(7)
        upl = np.array([row[rng.permutation(len(row))] for row in u])
        ew = lambda x: pd.DataFrame(x).ewm(span=5, adjust=False).mean().to_numpy()
        lc = np.log1p(n)
        for k, v in (("lc", lc), ("lc_ew", ew(lc)), ("day", (n > 0).astype(float)), ("u", u), ("u_ew", ew(u)),
                     ("u_pl", upl), ("u_pl_ew", ew(upl))):
            out[k][:, ix] = np.where(live, v, np.nan)
        return out

    def state(self):
        """1 when SPY's m is above the 80th percentile of its values over sessions t-755..t-1 (252+ history)."""
        m = self.m[:, self.si]
        s = np.zeros(self.T)
        for t in range(self.T):
            past = m[max(0, t - 755):t]
            past = past[np.isfinite(past)]
            if len(past) >= 252 and np.isfinite(m[t]):
                s[t] = float(m[t] > np.quantile(past, 0.8))
        return np.broadcast_to(s[:, None], (self.T, self.N))


def forecasts(D, regs, y, mask, h, last_origin, halflife=None):
    """Monthly-refitted pooled OLS (or exponentially weighted LS) forecasts of y for origins <= last_origin.
    Returns yhat (T x N) and s2 per origin (T)."""
    X = np.stack([np.ones((D.T, D.N))] + [np.asarray(r, float) for r in regs], -1)
    ok = mask & np.isfinite(y) & np.all(np.isfinite(X), -1)
    Xz = np.where(ok[..., None], X, 0.0)
    yz = np.where(ok, y, 0.0)
    XtX = np.einsum("tnp,tnq->tpq", Xz, Xz)
    Xty = np.einsum("tnp,tn->tp", Xz, yz)
    yty = (yz ** 2).sum(1)
    n = ok.sum(1).astype(float)
    feat = mask & np.all(np.isfinite(X), -1)
    yhat = np.full((D.T, D.N), np.nan)
    s2 = np.full(D.T, np.nan)
    bounds = list(D.mstart) + [D.T]
    for a, b in zip(bounds[:-1], bounds[1:]):
        if D.S[a] > last_origin:
            break
        tmax = a - 1 - h                    # rows whose target window t+1..t+h ended by session a-1
        if tmax < 200:
            continue
        wt = np.ones(tmax + 1) if halflife is None else 0.5 ** ((a - np.arange(tmax + 1)) / halflife)
        A = np.einsum("t,tpq->pq", wt, XtX[:tmax + 1])
        c = np.einsum("t,tp->p", wt, Xty[:tmax + 1])
        bta = np.linalg.solve(A + 1e-9 * np.eye(len(c)), c)
        sse = (wt * yty[:tmax + 1]).sum() - 2 * bta @ c + bta @ A @ bta
        dof = (wt * n[:tmax + 1]).sum() - len(c)
        bb = min(b, int(np.searchsorted(D.S, last_origin, side="right")))
        yhat[a:bb] = np.where(feat[a:bb], X[a:bb] @ bta, np.nan)
        s2[a:bb] = sse / dof
    return yhat, s2


def qlike(rvbar, F):
    x = rvbar / F
    return x - np.log(x) - 1


def nw_t(x, lags):
    x = x[np.isfinite(x)]
    u = x - x.mean()
    T = len(u)
    v = (u @ u) / T + 2 * sum((1 - l / (lags + 1)) * (u[l:] @ u[:-l]) / T for l in range(1, lags + 1))
    return float(x.mean()), float(x.mean() / np.sqrt(v / T)), int(T)


def origins(D, h, period):
    """Origins whose target window t+1..t+h lies inside the period."""
    lo, hi = period
    ix = np.arange(D.T)
    end = np.minimum(ix + h, D.T - 1)
    return (D.S.values >= np.datetime64(lo)) & (D.S[end].values <= np.datetime64(hi)) & (ix + h < D.T) & (
        D.S.values >= np.datetime64(lo))


def compare(D, cand, bench, h, period, cand_hl=None):
    """Loss difference bench - cand on the common sample; returns mean, NW t, days, and the daily series."""
    rc, rb = D.regressors(cand, h), D.regressors(bench, h)
    mask = np.broadcast_to(D.stock, (D.T, D.N)) & np.all([np.isfinite(r) for r in rc + rb], 0)
    last = period[1]
    yc, sc = forecasts(D, rc, D.y[h], mask, h, last, cand_hl)
    yb, sb = forecasts(D, rb, D.y[h], mask, h, last)
    Fc, Fb = np.exp(yc + sc[:, None] / 2), np.exp(yb + sb[:, None] / 2)
    rvb = D.rvbar[h]
    L = qlike(rvb, Fb) - qlike(rvb, Fc)
    o = origins(D, h, period)
    L[~o] = np.nan
    ok = np.isfinite(L)
    daily = np.where(ok.sum(1) > 0, np.nansum(L, 1) / np.maximum(ok.sum(1), 1), np.nan)
    daily[~o] = np.nan
    mean, t, n = nw_t(daily, h + 5)
    return {"gain": mean, "t": t, "days": n, "names_per_day": float(np.nanmean(np.where(o, ok.sum(1), np.nan))),
            "qlike_bench": float(np.nanmean(np.where(o[:, None], qlike(rvb, Fb), np.nan)))}, daily


RTESTS = {"R1": ("MS_text", "MS", None), "R2": ("MS_co", "MS", None), "R3": ("MS_ew", "MS", 252),
          "R4": ("MS_q", "MS", None), "R5": ("MS_reg", "MS", None), "N1": ("N1", "NB", None)}
