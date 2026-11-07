"""Development search (research/regime/PREREG.md): one specification per hypothesis, chosen on decisions up to
2019-12-31 only, and the finalists for the single OOS read.

    python research/regime/search.py dev        # development table (never reads a decision after 2019)
    python research/regime/search.py oos        # the OOS read: refuses unless FROZEN.json is committed
"""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regime import COST, OUT, ROOT, pct_hist  # noqa: E402

DEV_END, OOS0, OOS1 = pd.Timestamp("2019-12-31"), pd.Timestamp("2020-01-01"), pd.Timestamp("2025-12-31")
FROZEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FROZEN.json")

# hypothesis -> (book, predicted sign of b, detector variants: name -> (column, history in weeks, transform))
HYP = {
    "H1": ("REV", +1, {"L21": ("vol21", 156, None), "L63": ("vol63", 156, None)}),
    "H2": ("SREV", +1, {"L21": ("scorr21", 156, None), "L63": ("scorr63", 156, None)}),
    "H3": ("MOM", -1, {"L21": ("vol21", 156, "panic"), "L63": ("vol63", 156, "panic")}),
    "H4": ("REV", +1, {"hist1y": ("newshom", 52, None), "hist3y": ("newshom", 156, None)}),
    "H5": ("MOM", -1, {"hist1y": ("newsshift", 52, None), "hist3y": ("newsshift", 156, None)}),
    "H6": ("REV-MOM", +1, {"hist1y": ("hmm", 52, None), "hist3y": ("hmm", 156, None)}),
}


def nw_t(y, x=None, L=4):
    """NW t of the slope of y on x (or of the mean of y when x is None)."""
    y = np.asarray(y, float)
    X = np.column_stack([np.ones(len(y))] + ([] if x is None else [np.asarray(x, float)]))
    ok = np.all(np.isfinite(X), 1) & np.isfinite(y)
    X, y = X[ok], y[ok]
    n = len(y)
    if n < 30:
        return np.nan, np.nan, n
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    u = y - X @ b
    XtXi = np.linalg.inv(X.T @ X)
    Om = (X * u[:, None]).T @ (X * u[:, None])
    for l in range(1, L + 1):
        G = (X[l:] * u[l:, None]).T @ (X[:-l] * u[:-l, None])
        Om += (1 - l / (L + 1)) * (G + G.T)
    V = XtXi @ Om @ XtXi
    j = X.shape[1] - 1
    return float(b[j]), float(b[j] / np.sqrt(V[j, j])), n


def detector(D, col, hist, tf):
    p = pct_hist(D[col].to_numpy(float), hist)
    if tf == "panic":                                   # Daniel-Moskowitz: bear market and volatility above median
        p = np.where(np.isfinite(p), ((D["bear"].to_numpy() > 0) & (p > 0.5)).astype(float), np.nan)
    return p


def books():
    W = {k: np.load(os.path.join(OUT, f"book_{k}.npy")) for k in ("REV", "SREV", "MOM")}
    H = {k: np.load(os.path.join(OUT, f"hedge_{k}.npy")) for k in ("REV", "SREV", "MOM")}
    return W, H


def conditioned(D, W, H, book, sign, x, form):
    """Weekly gross and net returns, turnover and active share of the conditioned book and of the unconditioned one."""
    if book == "REV-MOM":
        g = {k: D[f"{k}_gross"].to_numpy() for k in ("REV", "MOM")}
        if form == "binary":
            a = np.where(x > 0.5, 1.0, 0.0)
        else:
            a = x.copy()
        a = np.where(np.isfinite(x), a, 0.5)              # no detector yet: the static blend
        cw = {"REV": a, "MOM": 1 - a}
        uw = {"REV": np.full(len(D), 0.5), "MOM": np.full(len(D), 0.5)}
        out = {}
        for lab, c in (("cond", cw), ("unc", uw)):
            gross = c["REV"] * g["REV"] + c["MOM"] * g["MOM"]
            Wt = c["REV"][:, None] * W["REV"] + c["MOM"][:, None] * W["MOM"]
            Ht = c["REV"] * H["REV"] + c["MOM"] * H["MOM"]
            out[lab] = _net(gross, Wt, Ht, np.ones(len(D)))
        return out
    s = np.where(np.isfinite(x), (x > 0.5) if sign > 0 else (x < 0.5), True).astype(float) if form == "binary" else \
        np.where(np.isfinite(x), x if sign > 0 else 1 - x, 1.0)
    if np.all(np.isin(np.unique(x[np.isfinite(x)]), [0.0, 1.0])):     # a 0/1 detector (panic): on/off either form
        s = np.where(np.isfinite(x), (x == 1) if sign > 0 else (x == 0), True).astype(float)
    gross = D[f"{book}_gross"].to_numpy()
    return {"cond": _net(s * gross, s[:, None] * W[book], s * H[book], s),
            "unc": _net(gross, W[book], H[book], np.ones(len(D)))}


def _net(gross, Wt, Ht, active):
    to = np.r_[np.abs(Wt[0]).sum() + abs(Ht[0]), np.abs(np.diff(Wt, axis=0)).sum(1) + np.abs(np.diff(Ht))]
    return {"gross": gross, "net": gross - COST * to, "to": to, "active": active}


def summary(x, mask):
    r = x["net"][mask]
    g = x["gross"][mask]
    sd = r.std(ddof=1)
    v = np.cumprod(1 + r)
    return {"net_pct_yr": (v[-1] ** (52 / len(r)) - 1) * 100, "gross_pct_yr": ((np.cumprod(1 + g)[-1]) ** (52 / len(g)) - 1) * 100,
            "sharpe": r.mean() / sd * np.sqrt(52) if sd > 0 else np.nan, "net_mean_bp": r.mean() * 1e4,
            "max_dd_pct": (v / np.maximum.accumulate(v) - 1).min() * 100, "turnover_wk": x["to"][mask].mean(),
            "active_share": x["active"][mask].mean(), "weeks": int(mask.sum())}


def dev():
    D = pd.read_parquet(os.path.join(OUT, "weekly.parquet"))
    keep = D["date"] <= DEV_END
    D = D[keep].reset_index(drop=True)                  # nothing after 2019 is read below
    W, H = books()
    W = {k: v[keep.to_numpy()] for k, v in W.items()}
    H = {k: v[keep.to_numpy()] for k, v in H.items()}
    assert D["date"].max() <= DEV_END
    rows, choice = [], {}
    for h, (book, sign, var) in HYP.items():
        y = D["REV_gross"] - D["MOM_gross"] if book == "REV-MOM" else D[f"{book}_gross"]
        best = None
        for vn, (col, hist, tf) in var.items():
            x = detector(D, col, hist, tf)
            b, t, n = nw_t(y.to_numpy(), x)
            m = np.isfinite(x)
            for form in ("binary", "linear"):
                c = conditioned(D, W, H, book, sign, x, form)
                sc, su = summary(c["cond"], m), summary(c["unc"], m)
                rows.append({"H": h, "variant": vn, "form": form, "b": b, "t": t, "n": n, "t_dir": sign * t,
                             **{f"c_{k}": v for k, v in sc.items()}, **{f"u_{k}": v for k, v in su.items()}})
        R = pd.DataFrame([r for r in rows if r["H"] == h])
        top_v = R.loc[R["t_dir"].idxmax(), "variant"]                   # the detector variant by development t
        Rv = R[R["variant"] == top_v]
        pick = Rv.loc[Rv["c_sharpe"].idxmax()]                          # then the form by development net Sharpe
        choice[h] = {"variant": top_v, "form": pick["form"], "t_dir": float(pick["t_dir"]),
                     "finalist": bool(pick["t_dir"] >= 1.5 and pick["c_net_mean_bp"] > pick["u_net_mean_bp"])}
    T = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    cols = ["H", "variant", "form", "n", "b", "t_dir", "c_net_pct_yr", "u_net_pct_yr", "c_sharpe", "u_sharpe",
            "c_net_mean_bp", "u_net_mean_bp", "c_gross_pct_yr", "c_turnover_wk", "c_active_share", "c_max_dd_pct"]
    print(T[cols].round(3).to_string(index=False))
    print(json.dumps(choice, indent=1))
    T.to_csv(os.path.join(OUT, "dev_table.csv"), index=False)
    json.dump(choice, open(os.path.join(OUT, "dev_choice.json"), "w"), indent=1)


if __name__ == "__main__":
    if sys.argv[1:] == ["dev"]:
        dev()
    elif sys.argv[1:] == ["oos"]:
        raise SystemExit("the OOS read is implemented after FROZEN.json is committed")
