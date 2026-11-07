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
    # round 2 (Amendment 1)
    "H7": ("PEAD", +1, {"hist1y": ("crowd", 52, "events"), "hist3y": ("crowd", 156, "events")}),
    "H8": ("NREV-REV", +1, {"hist1y": ("season", 52, "events"), "hist3y": ("season", 156, "events")}),
    "H10": ("SECMOM", -1, {"L21": ("acorr21", 156, None), "L63": ("acorr63", 156, None)}),
    "H11": ("MOM", -1, {"w26": ("momvol26", 156, None), "w52": ("momvol52", 156, None)}),
    # round 3 (Amendment 2)
    "H12": ("NREVB-REVB", +1, {"hist1y": ("season", 52, "events"), "hist3y": ("season", 156, "events")}),
}
FACTORS = ("MOM", "REV", "SREV", "LOWVOL", "HIGH52")
EVENTS0 = pd.Timestamp("2012-03-01")                    # events start 2012-01: crowding and season from March 2012


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


def lagged_trailing(y, w):
    """At decision k: the sum of weekly returns of decisions k-1-w .. k-2. Decision k-1's week ends one session
    after decision k, so it is not yet known."""
    y = np.asarray(y, float)
    out = np.full(len(y), np.nan)
    for k in range(w + 1, len(y)):
        out[k] = np.nansum(y[k - 1 - w:k - 1])
    return out


def add_derived(D):
    for w in (26, 52):
        out = np.full(len(D), np.nan)
        y = D["MOM_gross"].to_numpy()
        for k in range(w + 1, len(D)):
            out[k] = np.std(y[k - 1 - w:k - 1], ddof=1)
        D[f"momvol{w}"] = out
    return D


def detector(D, col, hist, tf):
    x = D[col].to_numpy(float)
    if tf == "events":
        x = np.where(D["date"] >= EVENTS0, x, np.nan)
    p = pct_hist(x, hist)
    if tf == "panic":                                   # Daniel-Moskowitz: bear market and volatility above median
        p = np.where(np.isfinite(p), ((D["bear"].to_numpy() > 0) & (p > 0.5)).astype(float), np.nan)
    return p


def books():
    ks = ("REV", "SREV", "MOM", "PEAD", "NREV", "LOWVOL", "HIGH52", "SECMOM", "REVB", "NREVB",
          "NOV13", "NOVB13", "NOVREV13", "NOV26", "NOVB26", "NOVREV26")
    W = {k: np.load(os.path.join(OUT, f"book_{k}.npy")) for k in ks}
    H = {k: np.load(os.path.join(OUT, f"hedge_{k}.npy")) for k in ks}
    return W, H


def conditioned(D, W, H, book, sign, x, form):
    """Weekly gross and net returns, turnover and active share of the conditioned book and of the unconditioned one."""
    if "-" in book:
        A_, B_ = book.split("-")
        g = {"REV": D[f"{A_}_gross"].to_numpy(), "MOM": D[f"{B_}_gross"].to_numpy()}
        W = {"REV": W[A_], "MOM": W[B_]}
        H = {"REV": H[A_], "MOM": H[B_]}
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


def fmom(D, W, H, w, form, sign=+1):
    """H9: factor momentum. Returns b, t (pooled over factors, NW on weekly score sums) and the conditioned and
    unconditioned book results."""
    ys, xs, on = [], [], []
    for f in FACTORS:
        y = D[f"{f}_gross"].to_numpy()
        tr = lagged_trailing(y, w)
        ys.append(y); xs.append(pct_hist(tr, 156))
        on.append(np.where(np.isfinite(tr), ((tr > 0) if sign > 0 else (tr < 0)).astype(float), np.nan))
    Y, X, ON = np.column_stack(ys), np.column_stack(xs), np.column_stack(on)
    ok = np.isfinite(X).all(1)
    yv, xv = Y[ok].ravel(), X[ok].ravel()
    xc = xv - xv.mean()
    b = (xc * (yv - yv.mean())).sum() / (xc ** 2).sum()
    u = (yv - yv.mean()) - b * xc
    sc = (xc * u).reshape(-1, len(FACTORS)).sum(1)                                # weekly score sums
    L, T = 4, len(sc)
    S_ = (sc ** 2).sum() + sum(2 * (1 - l / (L + 1)) * (sc[l:] * sc[:-l]).sum() for l in range(1, L + 1))
    t = b / (np.sqrt(S_) / (xc ** 2).sum())
    a = (ON if form == "binary" else (X if sign > 0 else 1 - X)) / len(FACTORS)
    a = np.where(np.isfinite(a), a, 1 / len(FACTORS))
    gross = (a * Y).sum(1)
    Wt = sum(a[:, j][:, None] * W[f] for j, f in enumerate(FACTORS))
    Ht = sum(a[:, j] * H[f] for j, f in enumerate(FACTORS))
    u5 = np.full(len(D), 1 / len(FACTORS))
    cond = _net(gross, Wt, Ht, (a > 0).mean(1))
    unc = _net((u5[:, None] * Y).sum(1), sum(u5[:, None] * W[f] for f in FACTORS), sum(u5 * H[f] for f in FACTORS), np.ones(len(D)))
    return float(b), float(t), int(ok.sum()), cond, unc, ok


def umd_variants():
    return {"H16": {"L21": ("mvol21", "panic"), "L63": ("mvol63", "panic")},
            "H17": {"w126": ("umdvol126", "vol"), "w252": ("umdvol252", "vol")}}


def umd_detector(U, col, kind):
    """(regression detector, linear scale, binary scale) at each decision; past data only."""
    p = pct_hist(U[col].to_numpy(float), 156)
    ok = np.isfinite(p)
    if kind == "panic":
        bear = U["bear"].to_numpy() > 0
        x = np.where(ok, (bear & (p > 0.5)).astype(float), np.nan)
        lin = np.where(ok, np.where(bear, 1 - p, 1.0), 1.0)
        bin_ = np.where(ok, 1 - x, 1.0)
    else:
        x = p
        lin = np.where(ok, 1 - p, 1.0)
        bin_ = np.where(ok, (p <= 0.5).astype(float), 1.0)
    return x, lin, bin_


def umd_books(U, s_):
    g = U["UMD_gross"].to_numpy()
    to_c = 2 * np.abs(np.diff(np.r_[0.0, s_]))                         # legs 100% + 100%: scale changes trade 2|ds|
    to_u = 2 * np.abs(np.diff(np.r_[0.0, np.ones(len(U))]))
    return ({"gross": s_ * g, "net": s_ * g - COST * to_c, "to": to_c, "active": s_},
            {"gross": g, "net": g - COST * to_u, "to": to_u, "active": np.ones(len(U))})


def _pick(rows, choice, h):
    R = pd.DataFrame([r for r in rows if r["H"] == h])
    top_v = R.loc[R["t_dir"].idxmax(), "variant"]
    pick = R[R["variant"] == top_v].loc[lambda r: r["c_sharpe"].idxmax()]
    choice[h] = {"variant": top_v, "form": pick["form"], "t_dir": float(pick["t_dir"]),
                 "finalist": bool(pick["t_dir"] >= 1.5 and pick["c_net_mean_bp"] > pick["u_net_mean_bp"])}


def dev():
    D = pd.read_parquet(os.path.join(OUT, "weekly.parquet"))
    keep = D["date"] <= DEV_END
    D = D[keep].reset_index(drop=True)                  # nothing after 2019 is read below
    W, H = books()
    W = {k: v[keep.to_numpy()] for k, v in W.items()}
    H = {k: v[keep.to_numpy()] for k, v in H.items()}
    assert D["date"].max() <= DEV_END
    D = add_derived(D)
    rows, choice = [], {}
    for h, (book, sign, var) in HYP.items():
        y = D[f"{book.split('-')[0]}_gross"] - D[f"{book.split('-')[1]}_gross"] if "-" in book else D[f"{book}_gross"]
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
    for w in (26, 52):                                                   # H9 factor momentum
        for form in ("binary", "linear"):
            b, t, n, c_, u_, ok = fmom(D, W, H, w, form)
            sc, su = summary(c_, ok), summary(u_, ok)
            rows.append({"H": "H9", "variant": f"w{w}", "form": form, "b": b, "t": t, "n": n, "t_dir": t,
                         **{f"c_{k}": v for k, v in sc.items()}, **{f"u_{k}": v for k, v in su.items()}})
    R = pd.DataFrame([r for r in rows if r["H"] == "H9"])
    top_v = R.loc[R["t_dir"].idxmax(), "variant"]
    pick = R[R["variant"] == top_v].loc[lambda r: r["c_sharpe"].idxmax()]
    choice["H9"] = {"variant": top_v, "form": pick["form"], "t_dir": float(pick["t_dir"]),
                    "finalist": bool(pick["t_dir"] >= 1.5 and pick["c_net_mean_bp"] > pick["u_net_mean_bp"])}
    for h, sign in (("H14", -1),):                                       # H14 factor reversal
        for w in (26, 52):
            for form in ("binary", "linear"):
                b, t, n, c_, u_, ok = fmom(D, W, H, w, form, sign)
                sc, su = summary(c_, ok), summary(u_, ok)
                rows.append({"H": h, "variant": f"w{w}", "form": form, "b": b, "t": t, "n": n, "t_dir": sign * t,
                             **{f"c_{k}": v for k, v in sc.items()}, **{f"u_{k}": v for k, v in su.items()}})
        _pick(rows, choice, h)
    for w in (13, 26):                                                   # H13 novel vs stale news (FM slope)
        b2 = D[f"nov_b2_{w}"].to_numpy()
        ok = np.isfinite(b2) & (D[f"nov_n_{w}"].to_numpy() >= 8)
        b, t, n = nw_t(b2[ok])
        for form, kb in (("linear", f"NOV{w}"), ("binary", f"NOVB{w}")):
            c_ = _net(D[f"{kb}_gross"].to_numpy(), W[kb], H[kb], ok.astype(float))
            u_ = _net(D[f"NOVREV{w}_gross"].to_numpy(), W[f"NOVREV{w}"], H[f"NOVREV{w}"], ok.astype(float))
            sc, su = summary(c_, ok), summary(u_, ok)
            rows.append({"H": "H13", "variant": f"w{w}", "form": form, "b": b, "t": t, "n": n, "t_dir": t,
                         **{f"c_{k}": v for k, v in sc.items()}, **{f"u_{k}": v for k, v in su.items()}})
    _pick(rows, choice, "H13")
    K = pd.read_parquet(os.path.join(OUT, "kf_weekly.parquet"))       # H15: industries, development 1927-1999
    kd = K["date"] <= pd.Timestamp("1999-12-31")
    K = K[kd].reset_index(drop=True)
    WI = np.load(os.path.join(OUT, "book_IMOM.npy"))[kd.to_numpy()]
    for L in (21, 63):
        x = pct_hist(K[f"iacorr{L}"].to_numpy(), 156)
        b, t, n = nw_t(K["IMOM_gross"].to_numpy(), x)
        m = np.isfinite(x)
        for form in ("binary", "linear"):
            s_ = np.where(m, (x < 0.5).astype(float) if form == "binary" else 1 - x, 1.0)
            g = K["IMOM_gross"].to_numpy()
            c_ = _net(s_ * g, s_[:, None] * WI, np.zeros(len(K)), s_)
            u_ = _net(g, WI, np.zeros(len(K)), np.ones(len(K)))
            sc, su = summary(c_, m), summary(u_, m)
            rows.append({"H": "H15", "variant": f"L{L}", "form": form, "b": b, "t": t, "n": n, "t_dir": -t,
                         **{f"c_{k}": v for k, v in sc.items()}, **{f"u_{k}": v for k, v in su.items()}})
    _pick(rows, choice, "H15")
    U = pd.read_parquet(os.path.join(OUT, "umd_weekly.parquet"))       # H16, H17: UMD, development 1927-1999
    U = U[U["date"] <= pd.Timestamp("1999-12-31")].reset_index(drop=True)
    for h, var in umd_variants().items():
        for vn, (col, kind) in var.items():
            x, sc_lin, sc_bin = umd_detector(U, col, kind)
            b, t, n = nw_t(U["UMD_gross"].to_numpy(), x)
            m = np.isfinite(x)
            for form, s_ in (("binary", sc_bin), ("linear", sc_lin)):
                c_, u_ = umd_books(U, s_)
                sc, su = summary(c_, m), summary(u_, m)
                rows.append({"H": h, "variant": vn, "form": form, "b": b, "t": t, "n": n, "t_dir": -t,
                             **{f"c_{k}": v for k, v in sc.items()}, **{f"u_{k}": v for k, v in su.items()}})
        _pick(rows, choice, h)
    T = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    cols = ["H", "variant", "form", "n", "b", "t_dir", "c_net_pct_yr", "u_net_pct_yr", "c_sharpe", "u_sharpe",
            "c_net_mean_bp", "u_net_mean_bp", "c_gross_pct_yr", "c_turnover_wk", "c_active_share", "c_max_dd_pct"]
    print(T[cols].round(3).to_string(index=False))
    print(json.dumps(choice, indent=1))
    T.to_csv(os.path.join(OUT, "dev_table.csv"), index=False)
    json.dump(choice, open(os.path.join(OUT, "dev_choice.json"), "w"), indent=1)


def oos():
    """The single OOS read of the frozen finalists (PREREG Amendment 4)."""
    from scipy.stats import norm
    here = os.path.dirname(os.path.abspath(__file__))
    lock = os.path.join(here, "OOS_READ.lock")
    if os.path.exists(lock):
        raise SystemExit("OOS already read: " + open(lock).read())
    st = subprocess.run(["git", "status", "--porcelain", FROZEN], capture_output=True, text=True, cwd=here).stdout.strip()
    sha = subprocess.run(["git", "log", "-1", "--format=%H", "--", FROZEN], capture_output=True, text=True, cwd=here).stdout.strip()
    if st or not sha:
        raise SystemExit("FROZEN.json is not committed and unchanged")
    Fz = json.load(open(FROZEN))
    D = add_derived(pd.read_parquet(os.path.join(OUT, "weekly.parquet")))
    W, H = books()
    res, years = {}, {}
    o0, o1 = OOS0, OOS1

    def record(h, y, x, cond, unc, dates, mask, sign):
        b, t, n = nw_t(y[mask], x[mask])
        sc, su = summary(cond, mask), summary(unc, mask)
        res[h] = {"b": b, "t": t, "t_dir": sign * t, "p_one_sided": float(norm.sf(sign * t)), "n": n,
                  "cond": sc, "unc": su}
        yr = pd.DatetimeIndex(dates[mask]).year
        years[h] = pd.DataFrame({"year": yr, "cond": cond["net"][mask], "unc": unc["net"][mask]}).groupby("year").agg(
            cond_net_pct=("cond", lambda r: (np.prod(1 + r) - 1) * 100), unc_net_pct=("unc", lambda r: (np.prod(1 + r) - 1) * 100),
            weeks=("cond", "size")).round(2)

    dates = D["date"].to_numpy()
    om = ((D["date"] >= o0) & (D["date"] <= o1)).to_numpy()
    for h, A_, B_ in (("H8", "NREV", "REV"), ("H12", "NREVB", "REVB")):
        x = detector(D, "season", 156, "events")
        y = (D[f"{A_}_gross"] - D[f"{B_}_gross"]).to_numpy()
        c = conditioned(D, W, H, f"{A_}-{B_}", +1, x, "linear")
        record(h, y, x, c["cond"], c["unc"], dates, om & np.isfinite(x), +1)
    b, t, n, c_, u_, ok = fmom(D, W, H, 26, "linear", -1)
    # the pooled b over the OOS weeks only: recompute on the OOS rows
    ys, xs = [], []
    for f in FACTORS:
        yv = D[f"{f}_gross"].to_numpy()
        ys.append(yv); xs.append(pct_hist(lagged_trailing(yv, 26), 156))
    Y, X = np.column_stack(ys), np.column_stack(xs)
    mk = om & np.isfinite(X).all(1)
    yv, xv = Y[mk].ravel(), X[mk].ravel()
    xc = xv - xv.mean(); bb = (xc * (yv - yv.mean())).sum() / (xc ** 2).sum()
    u = (yv - yv.mean()) - bb * xc
    scw = (xc * u).reshape(-1, len(FACTORS)).sum(1)
    S_ = (scw ** 2).sum() + sum(2 * (1 - l / 5) * (scw[l:] * scw[:-l]).sum() for l in range(1, 5))
    tt = bb / (np.sqrt(S_) / (xc ** 2).sum())
    record("H14", np.zeros(len(D)), np.zeros(len(D)), c_, u_, dates, mk, -1)
    res["H14"].update({"b": float(bb), "t": float(tt), "t_dir": float(-tt), "p_one_sided": float(norm.sf(-tt)), "n": int(mk.sum())})
    U = pd.read_parquet(os.path.join(OUT, "umd_weekly.parquet"))
    x, lin, bin_ = umd_detector(U, "mvol21", "panic")
    c_, u_ = umd_books(U, bin_)
    um = ((U["date"] >= pd.Timestamp("2000-01-01")) & (U["date"] <= o1)).to_numpy() & np.isfinite(x)
    record("H16", U["UMD_gross"].to_numpy(), x, c_, u_, U["date"].to_numpy(), um, -1)
    # Holm, one-sided
    fam = Fz["holm_family"]
    ps = sorted((res[h]["p_one_sided"], h) for h in fam)
    run = 0.0
    for i, (p_, h) in enumerate(ps):
        run = max(run, min(1.0, (len(fam) - i) * p_))
        res[h]["p_holm"] = run
    for h in fam:
        r = res[h]
        r["holm_pass"] = r["p_holm"] < Fz["alpha"]
        r["worth_forward"] = bool(r["holm_pass"] and r["cond"]["sharpe"] > r["unc"]["sharpe"] and r["cond"]["net_mean_bp"] > 0)
    # descriptive (Amendment 3): H16's frozen rule on the S&P 500 MOM book, 2020-2025, using the UMD-panel state
    pan = pd.Series(np.where(np.isfinite(x), x, 0.0), index=U["date"]).reindex(D["date"], method="ffill").fillna(0).to_numpy()
    s_ = 1 - pan
    mom_c = _net(s_ * D["MOM_gross"].to_numpy(), s_[:, None] * W["MOM"], s_ * H["MOM"], s_)
    mom_u = _net(D["MOM_gross"].to_numpy(), W["MOM"], H["MOM"], np.ones(len(D)))
    desc = {"cond": summary(mom_c, om), "unc": summary(mom_u, om), "panic_weeks": int(pan[om].sum())}
    out = {"frozen_commit": sha, "read_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "results": res,
           "years": {h: years[h].reset_index().to_dict("records") for h in years}, "h16_rule_on_sp500_mom": desc}
    json.dump(out, open(os.path.join(here, "OOS_RESULT.json"), "w"), indent=1, default=float)
    open(lock, "w").write(f"read {out['read_at']} from FROZEN.json at {sha}\n")
    L = ["# Regime-edge research: the single OOS read", "", f"Frozen specification: commit {sha[:10]}; read {out['read_at']}.", "",
         "| | OOS window | weeks | b | t (predicted direction) | p one-sided | p Holm | cond. net %/yr | uncond. net %/yr | cond. Sharpe | uncond. Sharpe | worth forward |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for h in fam:
        r = res[h]; w_ = "2000–2025" if h == "H16" else "2020–2025"
        L.append(f"| {h} | {w_} | {r['n']} | {r['b']:.5f} | {r['t_dir']:.2f} | {r['p_one_sided']:.4f} | {r['p_holm']:.4f} | "
                 f"{r['cond']['net_pct_yr']:.2f} | {r['unc']['net_pct_yr']:.2f} | {r['cond']['sharpe']:.2f} | {r['unc']['sharpe']:.2f} | {'**yes**' if r['worth_forward'] else 'no'} |")
    L += ["", "By year (net % in the year):", ""]
    for h in fam:
        L += [f"**{h}**", "", years[h].to_markdown(), ""]
    L += [f"H16's rule on the S&P 500 MOM book, 2020–2025 (descriptive): conditioned net {desc['cond']['net_pct_yr']:.2f}%/yr, "
          f"Sharpe {desc['cond']['sharpe']:.2f}; unconditioned {desc['unc']['net_pct_yr']:.2f}%/yr, Sharpe {desc['unc']['sharpe']:.2f}; "
          f"panic weeks {desc['panic_weeks']}."]
    open(os.path.join(here, "OOS_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    if sys.argv[1:] == ["dev"]:
        dev()
    elif sys.argv[1:] == ["oos"]:
        oos()
