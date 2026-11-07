"""Risk-field research, round 6 (PREREG.md Amendment 9): an earnings-drift book with a text-neighbour fundamental
field, and the earnings-announcement premium.

    python research/riskfield/round6.py dev     # development 2012-2021 -> DEV6_RESULT.md/json
    python research/riskfield/round6.py read    # ONCE; refuses if OOS6_READ.lock exists -> OOS6_RESULT.md/json
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "regime"))
import panel as PN                                                                    # noqa: E402
import regime as RG                                                                   # noqa: E402
from intl import dk_t                                                                 # noqa: E402
from oos import holm                                                                  # noqa: E402

DEV = (pd.Timestamp("2012-01-01"), pd.Timestamp("2021-12-31"))
OOS = (pd.Timestamp("2022-01-01"), pd.Timestamp("2025-12-31"))
HOLD = 20
COST = 5e-4


def dk_multi(blocks, lags=5):
    """Pooled OLS with group (week) fixed effects of y on several x; Driscoll-Kraay t per coefficient.
    blocks: list of (week id, y, X n x k)."""
    ys, Xs, ds = [], [], []
    for d, y, X in blocks:
        ok = np.isfinite(y) & np.all(np.isfinite(X), 1)
        if ok.sum() < 3:
            continue
        ys.append(y[ok] - y[ok].mean()); Xs.append(X[ok] - X[ok].mean(0)); ds.append(np.full(ok.sum(), d))
    y, X, d = np.concatenate(ys), np.vstack(Xs), np.concatenate(ds)
    A = X.T @ X
    b = np.linalg.solve(A, X.T @ y)
    u = y - X @ b
    sc = pd.DataFrame(X * u[:, None]).groupby(d).sum().sort_index().to_numpy()
    Sg = sc.T @ sc + sum((1 - l / (lags + 1)) * (sc[l:].T @ sc[:-l] + sc[:-l].T @ sc[l:]) for l in range(1, lags + 1))
    Ai = np.linalg.inv(A)
    V = Ai @ Sg @ Ai
    return b, b / np.sqrt(np.diag(V)), len(y)


def cluster_mean_t(y, g, lags=5):
    """Mean of y with a t clustered by group g (weeks, in time order) and Newey-West across groups."""
    m = y.mean()
    s = pd.Series(y - m).groupby(g).sum().sort_index().to_numpy()
    v = s @ s + 2 * sum((1 - l / (lags + 1)) * (s[l:] @ s[:-l]) for l in range(1, lags + 1))
    return float(m), float(m / (np.sqrt(v) / len(y)))


def load():
    P = RG.panel()
    S, names = P["S"], P["names"]
    ev = pd.read_parquet(os.path.join(PN.P8, "events.parquet"), columns=["ticker", "universe", "t0", "sue"])
    ev = ev[(ev.universe == "sp500") & (ev.t0 <= PN.END)].dropna(subset=["sue"])
    ni = pd.Index(names).get_indexer(ev.ticker)
    ti = np.searchsorted(S.values, ev.t0.values.astype("datetime64[ns]"))
    ok = (ni >= 0) & (ti < len(S) - 2) & (ti > 2)
    ev = ev[ok].assign(j=ni[ok], ti=ti[ok]).reset_index(drop=True)
    ev = ev[S[ev.ti].values == ev.t0.values.astype("datetime64[ns]")]       # t0 must be a session of the panel
    cr = np.vstack([np.zeros((1, len(names))), np.nancumsum(np.nan_to_num(P["e"]), 0)])
    ev["car"] = cr[ev.ti + 2, ev.j] - cr[ev.ti - 1, ev.j]
    ev["e0"] = P["e"][ev.ti, ev.j]
    return P, ev.reset_index(drop=True), cr


def run(period):
    P, ev, cr = load()
    S, names, n = P["S"], P["names"], len(P["S"])
    last = int(np.searchsorted(S.values, np.datetime64(period[1]), side="right")) - 1
    dec = [t for t in range(260, n) if S[t].weekday() == 3 and S[t] >= period[0] and t + HOLD + 1 <= last]
    month, W = None, None
    blocks1, blocks2, cohorts = [], [], []
    by_t = ev.groupby("ti")
    ti_arr, j_arr, sue_arr = ev.ti.to_numpy(), ev.j.to_numpy(), ev.sue.to_numpy()
    for w, t in enumerate(dec):
        if (S[t].year, S[t].month) != month:
            month = (S[t].year, S[t].month)
            tau = t
            while tau > 0 and (S[tau - 1].year, S[tau - 1].month) == month:
                tau -= 1
            W, _ = PN.text_kernel(names, S[tau])
        E = ev[(ev.ti >= t - 5) & (ev.ti + 1 <= t)]
        E = E[np.isfinite(P["close"][t + 1, E.j]) & np.isfinite(P["close"][t, E.j])]
        if len(E) < 10:
            cohorts.append(None)
            continue
        E = E.drop_duplicates("j", keep="last")
        zf = lambda x: (x - x.mean()) / x.std() if x.std() > 0 else x * np.nan
        comp = (zf(E.sue.to_numpy()) + zf(E.car.to_numpy()))
        # field: text neighbours' latest SUE with t0 in [t-62, t]
        rec = (ti_arr >= t - 62) & (ti_arr <= t)
        v = np.full(len(names), np.nan)
        order = np.argsort(ti_arr[rec])
        v[j_arr[rec][order]] = sue_arr[rec][order]                        # latest wins
        Wr = W[E.j.to_numpy()]
        has = np.isfinite(v)
        den = Wr @ has.astype(float)
        F = np.where(den > 0, (Wr @ np.nan_to_num(v)) / np.where(den > 0, den, 1), np.nan)
        D20 = cr[t + HOLD + 2, E.j] - cr[t + 2, E.j]
        blocks1.append((w, D20, zf(comp)))
        X = np.column_stack([zf(comp), np.where(np.isfinite(F), (F - np.nanmean(F)) / np.nanstd(F), np.nan)])
        blocks2.append((w, D20, X))
        # cohorts: E1 on z(comp); E2 on z(comp) + z(F) (names without F use z(comp) alone)
        sig2 = zf(comp) + np.nan_to_num(X[:, 1])
        c = {}
        for k, sg in (("E1", zf(comp)), ("E2", sig2)):
            q = np.nanquantile(sg, [1 / 3, 2 / 3])
            L, Sh = sg >= q[1], sg <= q[0]
            wts = np.zeros(len(E))
            wts[L], wts[Sh] = 0.5 / max(L.sum(), 1), -0.5 / max(Sh.sum(), 1)
            hedge = -float((wts * P["beta"][t, E.j]).sum())
            a = t + 1
            marks = [a + 5 * k_ for k_ in range(5)]
            px = pd.DataFrame(P["close"][a:a + HOLD + 1][:, E.j]).ffill().to_numpy()
            sub = []
            for m0, m1 in zip(marks[:-1], marks[1:]):
                R = px[m1 - a] / px[m0 - a] - 1
                Rm = P["spy"][m1] / P["spy"][m0] - 1
                sub.append(float((wts * R).sum() + hedge * Rm))
            gross_units = np.abs(wts).sum() + abs(hedge)
            sub[0] -= COST * gross_units
            sub[-1] -= COST * gross_units
            c[k] = sub
        cohorts.append(c)
    res = {}
    b, t1, nobs = dk_t(blocks1)
    res["E1"] = {"b": b, "t": t1, "n": nobs, "bp_per_sd": b * 1e4}
    bb, tt, nobs2 = dk_multi(blocks2)
    res["E2"] = {"b": float(bb[1]), "t": float(tt[1]), "n": nobs2, "bp_per_sd": float(bb[1] * 1e4), "b_comp": float(bb[0]),
                 "t_comp": float(tt[0])}
    for k in ("E1", "E2"):                                              # staggered book: 4 cohorts x 1/4
        wk = np.zeros(len(dec) + 4)
        for w, c in enumerate(cohorts):
            if c is None:
                continue
            for k_, r in enumerate(c[k]):
                wk[w + k_] += r / 4
        wk = wk[:len(dec)]
        res[k]["book"] = {"net_pct_yr": float((np.prod(1 + wk) ** (52 / len(wk)) - 1) * 100), "net_mean_bp_wk": float(wk.mean() * 1e4),
                          "sharpe": float(wk.mean() / wk.std(ddof=1) * np.sqrt(52)), "weeks": len(wk),
                          "active_weeks": int(sum(c is not None for c in cohorts))}
    E4 = ev[(ev.t0 >= period[0]) & (ev.t0 <= period[1])].dropna(subset=["e0"])
    wkid = (E4.t0 - pd.Timestamp("2000-01-03")).dt.days // 7
    m, t4 = cluster_mean_t(E4.e0.to_numpy(), wkid.to_numpy())
    res["E4"] = {"mean_bp": m * 1e4, "t": t4, "n": len(E4), "net_bp": m * 1e4 - 10}
    return res


def table(r, title):
    L = [f"# Risk-field research, round 6 (earnings drift with a fundamental field): {title}", "",
         "| Test | slope bp per sd (20 sessions) | DK t | book net %/yr | book Sharpe | events |", "|---|---:|---:|---:|---:|---:|"]
    for k in ("E1", "E2"):
        a = r[k]
        L.append(f"| {k} | {a['bp_per_sd']:.1f} | {a['t']:.2f} | {a['book']['net_pct_yr']:.2f} | {a['book']['sharpe']:.2f} | {a['n']} |")
    L += ["", f"E2 regression: composite {r['E2']['b_comp'] * 1e4:.1f} bp per sd (t {r['E2']['t_comp']:.2f}); field {r['E2']['bp_per_sd']:.1f} bp per sd (t {r['E2']['t']:.2f}).",
          f"E4 announcement premium: mean e(t0) {r['E4']['mean_bp']:.1f} bp (t {r['E4']['t']:.2f}), net of a 10 bp round trip {r['E4']['net_bp']:.1f} bp, {r['E4']['n']} events."]
    return L


def gate(r):
    fin = [k for k in ("E1", "E2") if r[k]["t"] >= 1.5 and r[k]["book"]["net_mean_bp_wk"] > 0]
    if r["E4"]["t"] >= 1.5 and r["E4"]["net_bp"] > 0:
        fin.append("E4")
    return fin


def dev():
    r = run(DEV)
    r["finalists"] = gate(r)
    json.dump(r, open(os.path.join(HERE, "DEV6_RESULT.json"), "w"), indent=1, default=float)
    L = table(r, "development 2012-2021") + ["", f"**Finalists:** {', '.join(r['finalists']) or 'none'}"]
    open(os.path.join(HERE, "DEV6_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


def read():
    lock = os.path.join(HERE, "OOS6_READ.lock")
    if os.path.exists(lock):
        raise SystemExit("already read: " + open(lock).read())
    fin = json.load(open(os.path.join(HERE, "DEV6_RESULT.json")))["finalists"]
    if not fin:
        raise SystemExit("no finalists: nothing to read")
    r = run(OOS)
    res = {}
    for k in fin:
        ok = r[k]["book"]["net_mean_bp_wk"] > 0 if k != "E4" else r[k]["net_bp"] > 0
        res[k] = {"p": float(norm.sf(r[k]["t"])), "ok": bool(ok)}
    holm(res)
    for k in res:
        res[k]["pass"] = bool(res[k]["p_holm"] < 0.05 and res[k]["ok"])
    at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    json.dump({"read_at": at, "finalists": fin, "stats": r, "results": res}, open(os.path.join(HERE, "OOS6_RESULT.json"), "w"),
              indent=1, default=float)
    open(lock, "w").write(f"read {at}\n")
    L = table(r, f"out-of-sample read 2022-2025 (one read, {at})") + ["", "Only finalists count.", ""] + [
        f"* **{k}**: p one-sided {v['p']:.4f}, Holm {v['p_holm']:.4f}, {'**pass**' if v['pass'] else 'fail'}" for k, v in res.items()]
    open(os.path.join(HERE, "OOS6_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"dev": dev, "read": read}[sys.argv[1]]()
