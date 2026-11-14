"""After H7 (descriptive; every series here has already been read): where did the fund's 2026 loss come from, is
MASTER's 2026 IC outside its own history, and what do all out-of-sample weeks say about the broad trees book?

    python research/tree/h7_decomp.py      # -> H7_DECOMP.json
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
os.environ["H7_DRY"] = "1"                      # import h7_read's helpers without any lock or result file
import h7_read as R  # noqa: E402
import harness as H  # noqa: E402
from holdout2 import load_module, nw  # noqa: E402

K, Y = R.K, R.Y


def ann(x, days=None):
    x = np.asarray(x, float)
    return float(52 * 100 * x.mean())


def sharpe_se(x):
    """Weekly series -> annualised Sharpe and its standard error (Lo 2002, iid form: sqrt((1 + SR_w^2/2)/T))."""
    x = np.asarray(x, float)
    sw = x.mean() / x.std(ddof=1)
    return float(sw * math.sqrt(52)), float(math.sqrt((1 + sw * sw / 2) / len(x)) * math.sqrt(52))


def fund():
    d = R.npz(os.path.join(Y, "sp_panel.npz"))
    old = np.load(os.path.join(K.QT, ".cache", "quant_trials", "sp500_tf_master_h5.npz"))["h5"].astype(np.float64)
    new = np.load(os.path.join(Y, "master_h5_2026.npy")).astype(np.float64)
    pred = np.full(new.shape, np.nan)
    pred[: len(old)] = old
    is26 = d["S"].year == 2026
    pred[is26] = new[is26]
    K.YEARS = range(2020, 2027)
    K.RF = K.ST.dtb3()
    K.GROSS_SIDE = 0.3
    sec = K.sectors(d["names"])
    df = K.run(d, pred, "S0", 5e-4, sec, np.zeros(len(sec), int), K.panic_flags(d))
    df["sleeve"] = df.total - df.book                      # core sleeve net of its switching cost and the margin cost
    w = lambda c: df[c] * 7 / df.days                      # noqa: E731
    by = {}
    for y, g in df.groupby("year"):
        i = g.index
        by[int(y)] = {"total": ann(w("total")[i]), "core_sleeve": ann(w("sleeve")[i]), "master_book": ann(w("book")[i]),
                      "spy": ann(w("spy")[i]), "book_sharpe": sharpe_se(w("book")[i])[0], "weeks": int(len(g))}
    # MASTER weekly IC by year, and 2026 against 2020-2025
    S = d["S"]
    ics = {}
    for y in range(2020, 2027):
        rows = np.where((S.weekday == 3) & (S.year == y))[0]
        rows = rows[rows < len(S) - 7]
        ic = H.weekly_ic(pred, d, rows)
        ics[y] = ic[np.isfinite(ic)]
    a, b = np.concatenate([ics[y] for y in range(2020, 2026)]), ics[2026]
    z = (b.mean() - a.mean()) / math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    bk = (df.book * 7 / df.days)
    a2, b2 = bk[df.year < 2026].values, bk[df.year == 2026].values
    z2 = (b2.mean() - a2.mean()) / math.sqrt(a2.var(ddof=1) / len(a2) + b2.var(ddof=1) / len(b2))
    # core: exposure path in 2026
    spy = pd.Series(d["spy"])
    ma = spy.rolling(K.ST.TREND, min_periods=K.ST.TREND).mean().values
    th = np.where((S.weekday == 3) & (S.year == 2026))[0]
    up = np.array([d["spy"][t] > ma[t] for t in th])
    return {"by_year_pct_per_year": by,
            "master_ic_by_year": {y: [float(v.mean()), int(len(v))] for y, v in ics.items()},
            "master_ic_2026_vs_2020_2025": {"mean_2020_2025": float(a.mean()), "mean_2026": float(b.mean()), "z": float(z),
                                            "weekly_ic_sd": float(a.std(ddof=1))},
            "master_book_2026_vs_2020_2025": {"pct_2020_2025": ann(a2), "pct_2026": ann(b2), "z": float(z2)},
            "core_2026": {"thursdays": int(len(th)), "share_above_200d": float(up.mean()), "switches": int(np.abs(np.diff(up.astype(int))).sum())}}


def broad():
    M1 = load_module(os.path.join(HERE, "M1_dyntrade", "lib.py"), "m1lib_decomp")
    D = R.npz(os.path.join(Y, "broad_panel.npz"))
    isb = D.pop("isb").astype(bool)
    S = D["S"]
    old = np.load(os.path.join(ROOT, ".cache", "tree", "read3_pred_L3b_candidate.npy")).astype(np.float64)
    p = np.full(D["y5"].shape, np.nan)
    p[: old.shape[0], : old.shape[1]] = old                  # saved names come first, in saved order (BUILD.md)
    new = np.load(os.path.join(Y, "trees_2026.npy")).astype(np.float64)
    is26 = S.year == 2026
    p[is26] = new[is26]
    Ds = dict(D)
    Ds["elig"] = D["elig"] & isb[None, :]
    Dc = dict(Ds)
    Dc["y5"] = np.clip(Ds["y5"], -1.0, 1.0)
    s = np.where(Ds["elig"], p, np.nan)
    th = np.where((S.weekday == 3) & (S.year >= 2017))[0]
    rows = np.array([t for t in th if M1.mask(s, Dc, t).sum() >= 50])
    out = {}
    for cost in (5e-4, 14e-4):
        M1.COST = cost
        net = pd.Series(np.asarray(M1.simulate(M1.build("decile", s, Dc, rows), Dc, rows)["net"], float), index=S[rows])
        sr, se = sharpe_se(net.values)
        m, t, n = nw(net.values)
        out[f"{cost * 1e4:.0f}bp"] = {"sharpe_2017_2026": sr, "sharpe_se": se, "pct_per_year": ann(net.values), "nw_t": t, "weeks": n,
                                      "by_year_pct": {int(y): ann(g.values) for y, g in net.groupby(net.index.year)},
                                      "by_year_sharpe": {int(y): sharpe_se(g.values)[0] for y, g in net.groupby(net.index.year)}}
    ic = pd.Series(H.weekly_ic(p, Ds, rows), index=S[rows]).dropna()
    out["ic_by_year"] = {int(y): float(g.mean()) for y, g in ic.groupby(ic.index.year)}
    m, t, n = nw(ic.values)
    out["ic_2017_2026"] = {"mean": m, "nw_t": t, "weeks": n}
    return out


if __name__ == "__main__":
    res = {"note": "descriptive; all series already read", "fund": fund(), "broad_trees_book": broad()}
    json.dump(res, open(os.path.join(HERE, "H7_DECOMP.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
