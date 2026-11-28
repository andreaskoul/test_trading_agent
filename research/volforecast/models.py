"""Volatility models of PREREG_VOL.md §4, walk-forward. Every function returns forecasts of y_H (variance summed over
the H sessions after the origin) for origins <= `until`, estimated only from rows whose target closed before the
origin (end_H < origin). Nothing here computes a loss.

Per-asset rolling regressions are solved exactly at every origin from cumulative sums of the normal equations
(a daily refit), so the window rule is applied by position: origin p trains on rows p-H-WIN .. p-H-1.
"""
import math
import os
import sys
import warnings
from multiprocessing import Pool

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import features as FE  # noqa: E402

WIN, MINROWS = 1000, 500                       # "rolling 1000": expanding from 500 usable rows, then the last 1000
GARCH_REFIT = 5
SEED = 20261128
CLASS_MODELS = {"stock": ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S8"],
                "etf": ["S0", "S1", "S2", "S3", "S4", "S5", "S7"],
                "index": ["S0", "S1", "S2", "S6", "S7"],
                "crypto": ["S0", "S1", "S2", "S3", "S4", "S5", "S8"]}
COMBO = {c: [m for m in ms if m not in ("S0", "S1")] for c, ms in CLASS_MODELS.items()}


# ===================================================================================== window helpers
def _lagged_window_sums(A, H):
    """A: (T, ...) per-row contributions (0 for unusable rows). Returns S with S[p] = sum of A over rows
    p-H-WIN .. p-H-1 (training window of origin p); rows before the series start count as 0."""
    T = A.shape[0]
    C = np.concatenate([np.zeros((1,) + A.shape[1:]), np.cumsum(A, axis=0)])      # C[q] = sum A[0..q-1]
    hi = np.clip(np.arange(T) - H, 0, T)                                          # exclusive end: p-H
    lo = np.clip(np.arange(T) - H - WIN, 0, T)
    return C[hi] - C[lo]


def _window_range(yv, H):
    """Min and max of the valid target over each origin's training window (insanity filter)."""
    s = pd.Series(yv)
    mn = s.rolling(WIN, min_periods=1).min().shift(H + 1).values
    mx = s.rolling(WIN, min_periods=1).max().shift(H + 1).values
    return mn, mx


def rolling_ls(X, y, H, w=None):
    """Exact rolling (weighted) least squares at every origin. X (T, k), y (T,). Returns beta (T, k), n, the window
    sum of w*y (for the mean) and the residual variance s2 (for log models)."""
    T, k = X.shape
    ok = np.isfinite(X).all(1) & np.isfinite(y)
    if w is not None:
        ok &= np.isfinite(w) & (w > 0)
    ww = np.where(ok, 1.0 if w is None else w, 0.0)
    Xz = np.where(ok[:, None], X, 0.0)
    yz = np.where(ok, y, 0.0)
    XtX = _lagged_window_sums(Xz[:, :, None] * Xz[:, None, :] * ww[:, None, None], H)
    Xty = _lagged_window_sums(Xz * (yz * ww)[:, None], H)
    yy = _lagged_window_sums(yz ** 2 * ww, H)
    n = _lagged_window_sums(ok.astype(float), H)
    sy = _lagged_window_sums(yz * ok, H)
    beta = np.full((T, k), np.nan)
    use = n >= MINROWS
    if use.any():
        A = XtX[use] + 1e-12 * np.eye(k)[None]
        try:
            beta[use] = np.linalg.solve(A, Xty[use][:, :, None])[:, :, 0]
        except np.linalg.LinAlgError:
            for j in np.where(use)[0]:
                beta[j] = np.linalg.lstsq(XtX[j], Xty[j], rcond=None)[0]
    ssr = yy - 2 * np.einsum("tk,tk->t", beta, Xty) + np.einsum("tk,tkl,tl->t", beta, XtX, beta)
    s2 = ssr / np.maximum(n - k, 1)
    return beta, n, sy, s2


def _finish(fc_avg, yv, H, n, sy):
    """Insanity filter on the H-average forecast, then x H. Amendment 1 (PREREG_VOL.md): one-sided. A non-finite,
    non-positive or below-window-minimum forecast is replaced by the window mean; the upper side of the BPQ (2016)
    filter is not applied (on the development read it erased the correct March 2020 forecasts)."""
    mn, _ = _window_range(yv, H)
    mean = sy / np.maximum(n, 1)
    bad = ~np.isfinite(fc_avg) | (fc_avg < mn) | (fc_avg <= 0)
    out = np.where(bad, mean, fc_avg)
    out[n < MINROWS] = np.nan
    return H * out


# ===================================================================================== S0, S1 (benchmarks)
def _compressed(g, mask_col="masked"):
    """Daily returns with masked (report) days dropped, as the fund's sigma_entry does."""
    r = g["ret"]
    keep = r.notna()
    if mask_col in g:
        keep &= ~g[mask_col].fillna(False).astype(bool)
    return r[keep]


def s0_fund(g, H):
    rc = _compressed(g)
    ew = rc.ewm(span=60, min_periods=60).std()
    sd = rc.rolling(252, min_periods=120).std()
    sig = np.maximum(ew, 0.75 * sd)
    return (H * sig ** 2).reindex(g.index).ffill()


def s1_ewma(g, H, lam=0.94):
    rc = _compressed(g)
    r2 = (rc ** 2).values
    v = np.empty(len(r2))
    if len(r2) < 30:
        return pd.Series(np.nan, index=g.index)
    v[0] = r2[:30].mean()
    for i in range(1, len(r2)):
        v[i] = lam * v[i - 1] + (1 - lam) * r2[i]
    s = pd.Series(v, index=rc.index)
    s.iloc[:30] = np.nan
    return (H * s).reindex(g.index).ffill()


# ===================================================================================== S2 GJR-GARCH(1,1)-t
def _garch_asset(args):
    """Rolling-1000 (expanding from 500) GJR-GARCH(1,1)-t, refit every 5 observations, filtered daily with fixed
    parameters. Returns the one-step conditional variance and the parameters (omega, alpha, gamma, beta) per origin."""
    key, r = args
    from arch import arch_model
    x = 100 * r.values
    T = len(x)
    s1 = np.full(T, np.nan)
    par = np.full((T, 4), np.nan)
    prev = None
    p = MINROWS - 1
    while p < T:
        lo = max(0, p + 1 - WIN)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                am = arch_model(x[lo:p + 1], mean="Constant", vol="GARCH", p=1, o=1, q=1, dist="t", rescale=False)
                res = am.fit(disp="off", show_warning=False, starting_values=prev,
                             options={"maxiter": 300})
                prm = res.params
                prev = prm.values
                mu, om, al, ga, be = (float(prm[k]) for k in ("mu", "omega", "alpha[1]", "gamma[1]", "beta[1]"))
                sig2 = float(res.conditional_volatility[-1]) ** 2
            except Exception:                                                     # noqa: BLE001
                p += GARCH_REFIT
                prev = None
                continue
        eps = x[p] - mu
        nxt = om + (al + ga * (eps < 0)) * eps ** 2 + be * sig2                   # sigma^2_{p+1|p}
        for q in range(p, min(p + GARCH_REFIT, T)):
            if q > p:
                eps = x[q] - mu
                nxt = om + (al + ga * (eps < 0)) * eps ** 2 + be * nxt
            s1[q] = nxt
            par[q] = (om, al, ga, be)
        p += GARCH_REFIT
    return key, pd.Series(s1 / 1e4, index=r.index), pd.DataFrame(par, index=r.index,
                                                                 columns=["om", "al", "ga", "be"])


def garch_states(P, workers=10):
    """One-step variances and parameters for every asset (computed once, used for every H)."""
    jobs = []
    for a, g in P.groupby(level="asset", sort=False):
        g = g.droplevel("asset")
        rc = _compressed(g)
        if len(rc) >= MINROWS:
            jobs.append((a, rc))
    out = {}
    with Pool(workers) as pool:
        for a, s1, par in pool.imap_unordered(_garch_asset, jobs, chunksize=1):
            out[a] = (s1, par)
    return out


def s2_garch(g, H, state):
    """Iterated closed form: sum_h sbar + rho^(h-1)(s1 - sbar), rho = alpha + gamma/2 + beta (Student-t symmetric)."""
    if state is None:
        return pd.Series(np.nan, index=g.index)
    s1, par = state
    om = par["om"] / 1e4
    rho = par["al"] + par["ga"] / 2 + par["be"]
    sbar = om / (1 - rho)
    geo = (1 - rho ** H) / (1 - rho)
    tot = np.where(rho < 0.9999, H * sbar + (s1 - sbar) * geo, H * s1)
    return pd.Series(tot, index=s1.index).reindex(g.index).ffill()


# ===================================================================================== S3-S5, S7 (per-asset HAR)
def _har_X(g, kind):
    if kind == "har":
        cols = [g["rv_d"], g["rv_w"], g["rv_m"]]
    elif kind == "harq":
        cols = [g["rv_d"], g["rv_d"] * np.sqrt(g["rq_d"]), g["rv_w"], g["rv_m"]]
    elif kind == "log":
        cols = [np.log(g["rv_d"]), np.log(g["rv_w"]), np.log(g["rv_m"])]
    elif kind == "range":
        cols = [g["pk_d"], g["pk_w"], g["pk_m"], g["on2_d"]]
    X = np.column_stack([np.ones(len(g))] + [np.asarray(c, float) for c in cols])
    X[~np.isfinite(X)] = np.nan
    return X


def har_family(g, H, model):
    yH = g[f"y{H}"].values.astype(float) / H                                       # the H-average target
    yv = np.where(np.isfinite(yH), yH, np.nan)
    if model == "S5":
        X = _har_X(g, "log")
        ly = np.log(np.where(yv > 0, yv, np.nan))
        beta, n, _, s2 = rolling_ls(X, ly, H)
        _, _, sy, _ = rolling_ls(X, yv, H)                                          # window mean of the level
        fc = np.exp(np.einsum("tk,tk->t", X, beta) + s2 / 2)
        return pd.Series(_finish(fc, yv, H, n, sy), index=g.index)
    X = _har_X(g, {"S3": "har", "S4": "harq", "S7": "range"}[model])
    if model == "S4":
        beta, n, sy, _ = rolling_ls(X, yv, H)
        return pd.Series(_finish(np.einsum("tk,tk->t", X, beta), yv, H, n, sy), index=g.index)
    # S3, S7: WLS with weights 1/yhat^2, yhat = the rolling-OLS fitted value at each row's own origin
    b0, n0, _, _ = rolling_ls(X, yv, H)
    yhat = np.einsum("tk,tk->t", X, b0)
    level = (g["rv_w"] if model == "S3" else g["pk_w"] + g["on2_w"]).values.astype(float)
    yhat = np.where(np.isfinite(yhat) & (yhat > 0), yhat, level)
    w = 1.0 / yhat ** 2
    beta, n, sy, _ = rolling_ls(X, yv, H, w=w)
    _, n, sy, _ = rolling_ls(X, yv, H)                                              # unweighted counts and mean
    return pd.Series(_finish(np.einsum("tk,tk->t", X, beta), yv, H, n, sy), index=g.index)


# ===================================================================================== S6 pooled centred HExpGl
S6_COLS = ["ew1", "ew5", "ew25", "ew125"]


def s6_pooled(P, H, until):
    """Pooled OLS without intercept on centred EWMA factors plus the centred market factor; expanding, refit daily
    from sums accumulated by the date each training target closes."""
    lr = P["lr"].astype(float)
    X = np.column_stack([P[c].astype(float) - lr for c in S6_COLS] +
                        [P["mkt_ew5"].astype(float) - P["mkt_lr"].astype(float)])
    yl = P[f"y{H}"].astype(float).values / H
    y = yl - lr.values
    elig = (P["n_hist"].values >= 252) & np.isfinite(X).all(1)
    train = elig & np.isfinite(y)
    end = pd.to_datetime(P[f"end{H}"]).values
    k = X.shape[1]
    D = pd.DataFrame({"end": end[train]})
    Xt, yt, ylt = X[train], y[train], yl[train]
    grp = D.groupby("end").indices
    ends = np.array(sorted(grp))
    XtX = np.array([np.einsum("ni,nj->ij", Xt[grp[e]], Xt[grp[e]]) for e in ends])
    Xty = np.array([Xt[grp[e]].T @ yt[grp[e]] for e in ends])
    cnt = np.array([len(grp[e]) for e in ends], float)
    sy = np.array([ylt[grp[e]].sum() for e in ends])
    mn = np.array([ylt[grp[e]].min() for e in ends])
    mx = np.array([ylt[grp[e]].max() for e in ends])
    cXtX, cXty, ccnt, csy = XtX.cumsum(0), Xty.cumsum(0), cnt.cumsum(), sy.cumsum()
    cmn, cmx = np.minimum.accumulate(mn), np.maximum.accumulate(mx)
    dates = P.index.get_level_values("date").values
    out = np.full(len(P), np.nan)
    origins = np.unique(dates[elig & (dates <= np.datetime64(until))])
    for d in origins:
        j = np.searchsorted(ends, d, side="left") - 1                              # targets closed strictly before d
        if j < 0 or ccnt[j] < MINROWS:
            continue
        b = np.linalg.solve(cXtX[j] + 1e-12 * np.eye(k), cXty[j])
        rows = np.where((dates == d) & elig)[0]
        fc = lr.values[rows] + X[rows] @ b
        mean = csy[j] / ccnt[j]
        fc = np.where((fc < cmn[j]) | (fc <= 0) | ~np.isfinite(fc), mean, fc)           # Amendment 1: one-sided
        out[rows] = H * fc
    return pd.Series(out, index=P.index)


# ===================================================================================== S8 pooled boosted trees
def s8_features(cls):
    base = ["rv_d", "rv_w", "rv_m"] + S6_COLS + ["lr"]
    if cls == "stock":
        return base + ["mkt_rv_d", "mkt_rv_w", "mkt_rv_m", "lvix"]
    return base + ["mkt_rv_d", "mkt_rv_w", "mkt_rv_m"]


def s8_trees(P, H, until, cls):
    """HistGradientBoosting (library defaults), gamma deviance (= 2 x QLIKE), retrained each January on every row
    whose target closed before 1 January; forecasts the year's origins."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    cols = s8_features(cls)
    X = P[cols].astype(float).values
    yl = P[f"y{H}"].astype(float).values / H
    end = pd.to_datetime(P[f"end{H}"]).values
    dates = P.index.get_level_values("date").values
    out = np.full(len(P), np.nan)
    years = range(pd.Timestamp(dates.min()).year + 1, pd.Timestamp(until).year + 1)
    for Y in years:
        cut = np.datetime64(f"{Y}-01-01")
        tr = (end < cut) & np.isfinite(yl) & (yl > 0)
        if tr.sum() < 5 * MINROWS:
            continue
        m = HistGradientBoostingRegressor(loss="gamma", random_state=SEED)
        m.fit(X[tr], yl[tr])
        te = (dates >= cut) & (dates < np.datetime64(f"{Y + 1}-01-01")) & (dates <= np.datetime64(until))
        if te.any():
            fc = m.predict(X[te])
            lo, hi, mean = yl[tr].min(), yl[tr].max(), yl[tr].mean()
            fc = np.where((fc < lo) | (fc <= 0) | ~np.isfinite(fc), mean, fc)             # Amendment 1: one-sided
            out[te] = H * fc
    return pd.Series(out, index=P.index)


# ===================================================================================== all models for one class / H
def forecasts(P, cls, H, until, garch=None):
    """DataFrame (asset, date) x models of y_H forecasts for origins <= until."""
    ms = CLASS_MODELS[cls]
    cols = {m: [] for m in ms if m not in ("S6", "S8")}
    for a, g in P.groupby(level="asset", sort=False):
        g = g.droplevel("asset")
        for m in cols:
            if m == "S0":
                s = s0_fund(g, H)
            elif m == "S1":
                s = s1_ewma(g, H)
            elif m == "S2":
                s = s2_garch(g, H, (garch or {}).get(a))
            else:
                s = har_family(g, H, m)
            s.index = pd.MultiIndex.from_product([[a], s.index], names=["asset", "date"])
            cols[m].append(s)
    F = pd.DataFrame({m: pd.concat(v) for m, v in cols.items()}).reindex(P.index)
    if "S6" in ms:
        F["S6"] = s6_pooled(P, H, until)
    if "S8" in ms:
        F["S8"] = s8_trees(P, H, until, cls)
    F = F[ms]
    F = F[F.index.get_level_values("date") <= pd.Timestamp(until)]
    F["C1"] = F[COMBO[cls]].mean(axis=1, skipna=False)
    return F
