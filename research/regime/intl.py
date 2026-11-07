"""Round 5 (PREREG Amendment 5): the single international replication read of H16 and H14.

    python research/regime/intl.py read     # ONCE; refuses if INT_READ.lock exists; writes INT_RESULT.md/json

Europe, Japan, Asia Pacific ex Japan (Ken French daily developed-market factors), every weekly decision with 156
weeks of detector history, to 2025-12-31. Specifications frozen from the US; nothing is chosen on these data.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regime import COST, OUT, kf_daily, pct_hist  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REGIONS = {"Europe": ("Europe_5_Factors_Daily_CSV.zip", "Europe_Mom_Factor_Daily_CSV.zip"),
           "Japan": ("Japan_5_Factors_Daily_CSV.zip", "Japan_Mom_Factor_Daily_CSV.zip"),
           "AsiaPacExJapan": ("Asia_Pacific_ex_Japan_5_Factors_Daily_CSV.zip", "Asia_Pacific_ex_Japan_MOM_Factor_Daily_CSV.zip")}
FAC = ("SMB", "HML", "RMW", "CMA", "WML")


def region_weekly(name):
    f5, fm = REGIONS[name]
    F = kf_daily(f5)
    M = kf_daily(fm).iloc[:, 0].rename("WML")
    X = pd.concat([F, M], axis=1, join="inner").dropna()
    X["MKT"] = X["Mkt-RF"] + X["RF"]
    S = X.index
    L = np.log1p(X[["MKT", *FAC]].to_numpy())
    C = np.vstack([np.zeros((1, L.shape[1])), np.cumsum(L, 0)])
    rows = []
    for t in range(252, len(S) - 6):
        if S[t].weekday() != 3:
            continue
        r = {"date": S[t], "bear": float(C[t + 1, 0] - C[t - 251, 0] < 0), "mvol21": float(np.std(L[t - 20:t + 1, 0]))}
        for j, f in enumerate(FAC):
            r[f] = float(np.exp(C[t + 7, j + 1] - C[t + 1, j + 1]) - 1)        # close t+1 -> close t+6
        rows.append(r)
    D = pd.DataFrame(rows)
    p = pct_hist(D["mvol21"].to_numpy(), 156)
    D["panic"] = np.where(np.isfinite(p), ((D["bear"] > 0) & (p > 0.5)).astype(float), np.nan)
    for f in FAC:                                   # own trailing 26-week return, decisions k-27..k-2; percentile
        y = D[f].to_numpy()
        tr = np.full(len(y), np.nan)
        for k in range(27, len(y)):
            tr[k] = y[k - 27:k - 1].sum()
        D[f"pct_{f}"] = pct_hist(tr, 156)
    return D


def dk_t(blocks):
    """Pooled slope with group fixed effects and a Driscoll-Kraay t: blocks = list of (dates, y, x)."""
    ys, xs, ds = [], [], []
    for d, y, x in blocks:
        ok = np.isfinite(y) & np.isfinite(x)
        ys.append(y[ok] - y[ok].mean()); xs.append(x[ok] - x[ok].mean()); ds.append(np.asarray(d)[ok])
    y, x, d = np.concatenate(ys), np.concatenate(xs), np.concatenate(ds)
    b = (x * y).sum() / (x * x).sum()
    u = y - b * x
    sc = pd.Series(x * u).groupby(d).sum().sort_index().to_numpy()       # score sums by week
    S_ = (sc ** 2).sum() + sum(2 * (1 - l / 5) * (sc[l:] * sc[:-l]).sum() for l in range(1, 5))
    return float(b), float(b / (np.sqrt(S_) / (x * x).sum())), int(len(y))


def stats(r):
    r = r[np.isfinite(r)]
    v = np.cumprod(1 + r)
    return {"weeks": int(len(r)), "net_pct_yr": float((v[-1] ** (52 / len(r)) - 1) * 100), "net_mean_bp": float(r.mean() * 1e4),
            "sharpe": float(r.mean() / r.std(ddof=1) * np.sqrt(52)), "max_dd_pct": float((v / np.maximum.accumulate(v) - 1).min() * 100)}


def read():
    lock = os.path.join(HERE, "INT_READ.lock")
    if os.path.exists(lock):
        raise SystemExit("already read: " + open(lock).read())
    R = {n: region_weekly(n) for n in REGIONS}
    b16, b14, books16, books14, per = [], [], {}, {}, {}
    for n, D in R.items():
        D = D[D["date"] <= pd.Timestamp("2025-12-31")]
        ok = np.isfinite(D["panic"].to_numpy()) & np.all(np.isfinite(D[[f"pct_{f}" for f in FAC]].to_numpy()), 1)
        D = D[ok].reset_index(drop=True)
        d = D["date"].to_numpy()
        # H16-INT
        s = 1 - D["panic"].to_numpy()
        g = D["WML"].to_numpy()
        c16 = s * g - COST * 2 * np.abs(np.diff(np.r_[1.0, s]))
        b16.append((d, g, D["panic"].to_numpy()))
        books16[n] = pd.DataFrame({"date": d, "cond": c16, "unc": g})
        # H14-INT
        A = np.column_stack([(1 - D[f"pct_{f}"].to_numpy()) / 5 for f in FAC])
        Y = np.column_stack([D[f].to_numpy() for f in FAC])
        cost = COST * 2 * np.vstack([np.abs(A[:1] - 0.2), np.abs(np.diff(A, axis=0))]).sum(1)
        c14 = (A * Y).sum(1) - cost
        u14 = Y.mean(1)
        for j, f in enumerate(FAC):
            b14.append((d, Y[:, j], D[f"pct_{f}"].to_numpy()))
        books14[n] = pd.DataFrame({"date": d, "cond": c14, "unc": u14})
        per[n] = {"weeks": len(D), "from": str(D["date"].min().date()), "to": str(D["date"].max().date()),
                  "panic_weeks": int(D["panic"].sum()),
                  "H16": {"b_t": dk_t([b16[-1]])[:2], "cond": stats(c16), "unc": stats(g)},
                  "H14": {"b_t": dk_t(b14[-5:])[:2], "cond": stats(c14), "unc": stats(u14)}}
    res = {}
    for h, blocks, bk in (("H16-INT", b16, books16), ("H14-INT", b14, books14)):
        b, t, n_ = dk_t(blocks)
        pool = pd.concat(bk.values()).groupby("date")[["cond", "unc"]].mean().sort_index()
        res[h] = {"b": b, "t": t, "t_dir": -t, "p_one_sided": float(norm.sf(-t)), "n": n_,
                  "cond": stats(pool["cond"].to_numpy()), "unc": stats(pool["unc"].to_numpy()),
                  "years": pool.groupby(pool.index.year).agg(lambda r: (np.prod(1 + r) - 1) * 100).round(2).reset_index().to_dict("records")}
    ps = sorted((res[h]["p_one_sided"], h) for h in res)
    run = 0.0
    for i, (p_, h) in enumerate(ps):
        run = max(run, min(1.0, (len(ps) - i) * p_))
        res[h]["p_holm"] = run
        res[h]["holm_pass"] = run < 0.05
        res[h]["worth_forward"] = bool(run < 0.05 and res[h]["cond"]["sharpe"] > res[h]["unc"]["sharpe"] and res[h]["cond"]["net_mean_bp"] > 0)
    at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    json.dump({"read_at": at, "results": res, "regions": per}, open(os.path.join(HERE, "INT_RESULT.json"), "w"), indent=1, default=float)
    open(lock, "w").write(f"read {at}\n")
    L = ["# Regime-edge research: international replication (one read)", "", f"Read {at}. Europe, Japan, Asia Pacific ex Japan.", "",
         "| | pooled n | b | t (predicted) | p one-sided | p Holm | cond. net %/yr | uncond. net %/yr | cond. Sharpe | uncond. Sharpe | worst fall cond./uncond. | worth forward |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for h, r in res.items():
        L.append(f"| {h} | {r['n']} | {r['b']:.5f} | {r['t_dir']:.2f} | {r['p_one_sided']:.4f} | {r['p_holm']:.4f} | {r['cond']['net_pct_yr']:.2f} | "
                 f"{r['unc']['net_pct_yr']:.2f} | {r['cond']['sharpe']:.2f} | {r['unc']['sharpe']:.2f} | {r['cond']['max_dd_pct']:.1f}% / {r['unc']['max_dd_pct']:.1f}% | "
                 f"{'**yes**' if r['worth_forward'] else 'no'} |")
    L += ["", "Each region alone (descriptive):", "", "| region | weeks | panic weeks | H16 t (b<0 predicted) | H16 Sharpe cond./uncond. | H14 t | H14 Sharpe cond./uncond. |",
          "|---|---:|---:|---:|---|---:|---|"]
    for n, p in per.items():
        L.append(f"| {n} ({p['from'][:4]}–{p['to'][:4]}) | {p['weeks']} | {p['panic_weeks']} | {-p['H16']['b_t'][1]:.2f} | {p['H16']['cond']['sharpe']:.2f} / {p['H16']['unc']['sharpe']:.2f} | "
                 f"{-p['H14']['b_t'][1]:.2f} | {p['H14']['cond']['sharpe']:.2f} / {p['H14']['unc']['sharpe']:.2f} |")
    open(os.path.join(HERE, "INT_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__" and sys.argv[1:] == ["read"]:
    read()
