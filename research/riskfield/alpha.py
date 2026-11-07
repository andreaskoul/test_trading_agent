"""Risk-field research (PREREG.md §6): McKean-Vlasov drift signals on point-in-time S&P 500 members, weekly."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "regime"))
import panel as PN                                                                    # noqa: E402
import regime as RG                                                                   # noqa: E402
from intl import dk_t                                                                 # noqa: E402

DEV = (pd.Timestamp("2011-06-01"), pd.Timestamp("2019-12-31"))
OOS = (pd.Timestamp("2020-01-01"), pd.Timestamp("2025-12-31"))


def co_kernel(e, elig_rows, k=10):
    """Top-k positive correlations of daily residual returns over the window (>= 200 finite sessions)."""
    N = e.shape[1]
    f = np.isfinite(e)
    ok = (f.sum(0) >= 200) & elig_rows
    W = np.zeros((N, N))
    idx = np.where(ok)[0]
    if len(idx) < 20:
        return W
    X = e[:, idx]
    g = np.isfinite(X)
    X = np.where(g, X - np.nanmean(X, 0), 0.0)
    C = (X.T @ X) / np.sqrt(np.outer((X ** 2).sum(0), (X ** 2).sum(0)))
    np.fill_diagonal(C, -np.inf)
    top = np.argpartition(-C, k - 1, axis=1)[:, :k]
    for i, js in enumerate(top):
        c = np.maximum(C[i, js], 0)
        if c.sum() > 0:
            W[idx[i], idx[js]] = c / c.sum()
    return W


def fld(W, x):
    rowm = W.sum(1)
    f = np.isfinite(x)
    num, den = W @ np.nan_to_num(x), W @ f.astype(float)
    return np.where((den >= 0.5 * rowm) & (rowm > 0), num / np.maximum(den, 1e-12), np.nan)


def rskew(H, t_hf):
    """Amendment 4: realised skewness over the 65 intraday returns of HF sessions t-4..t (NaN if any missing)."""
    r = H.R[t_hf - 4:t_hf + 1, 1:, :].reshape(-1, H.N)
    ok = np.isfinite(r).all(0)
    r = np.where(ok, r, 0.0)
    s2 = (r ** 2).sum(0)
    return np.where(ok & (s2 > 0), np.sqrt(r.shape[0]) * (r ** 3).sum(0) / np.where(s2 > 0, s2, 1) ** 1.5, np.nan)


def build(period_end, H=None, contagion=False):
    """Weekly rows to decisions <= period_end: signals A1..A3, next-week residual return, book returns."""
    P = RG.panel()
    S, names = P["S"], P["names"]
    n = len(S)
    cr = np.vstack([np.zeros((1, P["e"].shape[1])), np.nancumsum(np.nan_to_num(P["e"]), 0)])
    fin = np.vstack([np.zeros((1, P["e"].shape[1])), np.cumsum(np.isfinite(P["e"]), 0)])
    dec = [t for t in range(260, n - 6) if S[t].weekday() == 3 and S[t] <= period_end]
    month = None
    rows, books = [], {k: [] for k in ("A1", "A2", "A3")}
    zrows = {"A2": [], "A3": [], "A4": [], "C1": [], "C2": [], "C3": []}
    if contagion:                                                    # Amendment 6: news-day shocks
        z = np.load(os.path.join(PN.CACHE, "news_days.npz"))
        assert list(z["names"]) == list(names) and len(z["S"]) == n, "news calendar does not match the panel"
        e0 = np.nan_to_num(P["e"])
        cs_all = np.vstack([np.zeros((1, e0.shape[1])), np.cumsum(np.where(z["earn"] | z["uns"], e0, 0.0), 0)])
        cs_uns = np.vstack([np.zeros((1, e0.shape[1])), np.cumsum(np.where(z["uns"], e0, 0.0), 0)])
    hix = pd.Index(H.names).get_indexer(names) if H is not None else None
    betas = []
    for t in dec:
        if (S[t].year, S[t].month) != month:                      # kernels from information to the previous session
            month = (S[t].year, S[t].month)
            tau = t
            while tau > 0 and (S[tau - 1].year, S[tau - 1].month) == month:
                tau -= 1
            Wt, has = PN.text_kernel(names, S[tau])
            Wc = co_kernel(P["e"][tau - 252:tau], P["elig"][tau - 1])
        el = P["elig"][t] & np.isfinite(P["close"][t + 1]) & (fin[t + 1] - fin[t - 20] >= 18)
        m21 = np.where(el, cr[t + 1] - cr[t - 20], np.nan)
        m5 = np.where(el, cr[t + 1] - cr[t - 4], np.nan)
        sig = {"A1": np.where(el & has, fld(Wt, m21), np.nan),
               "A2": np.where(el & has, fld(Wt, m5) - m5, np.nan),
               "A3": np.where(el, fld(Wc, m5) - m5, np.nan)}
        if contagion:
            sa, su = cs_all[t + 1] - cs_all[t - 4], cs_uns[t + 1] - cs_uns[t - 4]
            sa_el, su_el = np.where(P["elig"][t], sa, np.nan), np.where(P["elig"][t], su, np.nan)
            sig["C1"] = np.where(el & has, fld(Wt, np.where(has, sa_el, np.nan)), np.nan)
            sig["C2"] = np.where(el, fld(Wc, sa_el), np.nan)
            sig["C3"] = np.where(el & has, fld(Wt, np.where(has, su_el, np.nan)), np.nan)
        if H is not None:
            th = H.S.get_indexer([S[t]])[0]
            a4 = np.full(len(names), np.nan)
            if th >= 4:
                sk = rskew(H, th)
                a4[hix >= 0] = -sk[hix[hix >= 0]]
            sig["A4"] = np.where(el, a4, np.nan)
            books.setdefault("A4", [])
        for k in ("C1", "C2", "C3"):
            if k in sig:
                books.setdefault(k, [])
        y = np.where(el, cr[t + 7] - cr[t + 2], np.nan)          # sum of e over t+2..t+6
        R, Rm = RG.hold_ret(P, t)
        row = {"t": t, "date": S[t]}
        for k, s in sig.items():
            z = RG.zs(s)
            w, wspy = RG.decile_book(z, P["beta"][t])
            row[f"{k}_gross"] = float(np.nansum(w * R) + wspy * Rm)
            row[f"{k}_n"] = int(np.isfinite(z).sum())
            books[k].append((w, wspy))
            row[f"{k}_z"] = z
            if k in zrows:
                zrows[k].append(z)
        betas.append(P["beta"][t])
        row["R"], row["Rm"] = R, Rm
        row["y"] = y
        rows.append(row)
    D = pd.DataFrame(rows)
    for k in books:
        prev, to = None, []
        for w, wspy in books[k]:
            to.append(np.nan if prev is None else float(np.abs(w - prev[0]).sum() + abs(wspy - prev[1])))
            prev = (w, wspy)
        D[f"{k}_net"] = D[f"{k}_gross"] - RG.COST * pd.Series(to).fillna(1.0).to_numpy()
    for k in [x for x in ("A2", "A3", "A4", "C1", "C2", "C3") if zrows[x]]:   # Amendments 2, 4, 6: banded books
        bk = RG.banded(zrows[k], betas)
        g = [float(np.nansum(w * r.R) + h * r.Rm) for (w, h), (_, r) in zip(bk, D.iterrows())]
        to = [1.0] + [float(np.abs(a[0] - b[0]).sum() + abs(a[1] - b[1])) for a, b in zip(bk[1:], bk[:-1])]
        D[f"{k}B_gross"] = g
        D[f"{k}B_net"] = np.array(g) - RG.COST * np.array(to)
        D[f"{k}B_to"] = to
        D[f"{k}B_z"] = D[f"{k}_z"]
        D[f"{k}B_n"] = D[f"{k}_n"]
    return D


def stats(D, k, period):
    X = D[(D.date >= period[0]) & (D.date <= period[1])]
    blocks = [(np.full(len(r.y), i), r.y, r[f"{k}_z"]) for i, (_, r) in enumerate(X.iterrows())]
    b, t, nobs = dk_t(blocks)
    net = X[f"{k}_net"].to_numpy()
    return {"b": b, "t": t, "n": nobs, "weeks": len(X), "net_mean_bp": float(net.mean() * 1e4),
            "net_pct_yr": float((np.prod(1 + net) ** (52 / len(net)) - 1) * 100),
            "sharpe": float(net.mean() / net.std(ddof=1) * np.sqrt(52)), "names": float(X[f"{k}_n"].mean())}
