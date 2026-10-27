"""H4 geopolitical drift (PREREG_thesis_tree.md §4; operational definition: Amendment 5 C).

    python research/p8/h4.py build     # -> .cache/p8/h4_rows.parquet (all years; no statistic)
    python research/p8/h4.py fit       # fit-sample statistic (2012-2021), descriptive

Innovations: for GPRD_THREAT and GPRD_ACT (Caldara-Iacoviello daily file, SHA-256 1e8799c8...6dea), e_t = residual
of an AR(5) on log(1 + index), coefficients estimated once on the fit sessions (2012-2021) and fixed. Shock day:
a session with e_t above the fit-sample 95th percentile, in either sub-index (a day in both counts once). The index
is dated by publication day; a shock on a non-session day is assigned to the next session (the market's first
chance to react). Event (shock session d, sector s): R0 = sector residual return on d; target = sum of the sector
residual over d+1 .. d+20. Sector residual = r_ETF - beta r_SPY, beta per §1 (Welch-winsorised, 252 sessions
ending 21 before d, shrunk 1/3 toward 1). Registered sign: positive (drift). FE: year; cluster: sector (Webb).
"""
import hashlib
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inference as I                                            # noqa: E402
import prices as PX                                              # noqa: E402
import residuals as RS                                           # noqa: E402

GPR = os.path.join(PX.CACHE, "gpr", "gpr_daily.dta")
SHA = "1e8799c8d2f56978fdaf9000f71f7a242c97be02f40cf8c5b79d644ca2886dea"
ROWS = os.path.join(PX.CACHE, "h4_rows.parquet")
FIT = (pd.Timestamp("2012-01-01"), pd.Timestamp("2021-12-31"))
ETFS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]


def innovations(sessions):
    assert hashlib.sha256(open(GPR, "rb").read()).hexdigest() == SHA, "GPR file differs from the frozen copy"
    G = pd.read_stata(GPR).set_index("date")
    out = {}
    for col in ("GPRD_THREAT", "GPRD_ACT"):
        y = np.log1p(G[col].astype(float))
        X = pd.concat({f"l{k}": y.shift(k) for k in range(1, 6)}, axis=1)
        fit = (y.index >= FIT[0]) & (y.index <= FIT[1])
        Z = pd.concat([y, X], axis=1).dropna()
        Zf = Z[(Z.index >= FIT[0]) & (Z.index <= FIT[1])]
        A = np.column_stack([np.ones(len(Zf)), Zf.iloc[:, 1:].values])
        coef = np.linalg.lstsq(A, Zf.iloc[:, 0].values, rcond=None)[0]
        eps = Z.iloc[:, 0] - np.column_stack([np.ones(len(Z)), Z.iloc[:, 1:].values]) @ coef
        out[col] = eps
    E = pd.DataFrame(out)
    # calendar day -> the first session on or after it
    idx = sessions.searchsorted(E.index, side="left")
    E = E[idx < len(sessions)]
    E["session"] = sessions[idx[idx < len(sessions)]]
    thr = {c: float(E.loc[(E.index >= FIT[0]) & (E.index <= FIT[1]), c].quantile(0.95)) for c in ("GPRD_THREAT", "GPRD_ACT")}
    shocks = E[(E["GPRD_THREAT"] > thr["GPRD_THREAT"]) | (E["GPRD_ACT"] > thr["GPRD_ACT"])]
    kind = shocks.groupby("session").apply(
        lambda g: "both" if ((g["GPRD_THREAT"] > thr["GPRD_THREAT"]).any() and (g["GPRD_ACT"] > thr["GPRD_ACT"]).any())
        else ("threat" if (g["GPRD_THREAT"] > thr["GPRD_THREAT"]).any() else "act"))
    return kind, thr


def build():
    R = RS.returns()
    kind, thr = innovations(R.index)
    pos = {d: i for i, d in enumerate(R.index)}
    rows = []
    for d, k in kind.items():
        i = pos[d]
        if i + 20 >= len(R) or d > pd.Timestamp("2025-12-31") or d < pd.Timestamp("2012-01-01"):
            continue
        for etf in ETFS:
            if etf not in R or d < RS.ETF_START.get(etf, pd.Timestamp("1990-01-01")):
                continue
            lo, hi = i - 21 - 252, i - 21
            if lo < 0:
                continue
            w = R.iloc[lo:hi]
            rm, y = w["SPY"], w[etf]
            ok = rm.notna() & y.notna()
            if ok.sum() < 200:
                continue
            l_, h_ = np.minimum(-2 * rm, 4 * rm), np.maximum(-2 * rm, 4 * rm)
            yw = y.clip(lower=l_, upper=h_)[ok]
            b = float(np.cov(yw, rm[ok])[0, 1] / rm[ok].var()) * 2 / 3 + 1 / 3
            seg = R.iloc[i: i + 21]
            ers = (seg[etf] - b * seg["SPY"]).values
            if not np.isfinite(ers).all():
                continue
            rows.append({"day": d, "year": d.year, "kind": k, "sector": etf, "R0": float(ers[0]),
                         "drift20": float(ers[1:].sum())})
    D = pd.DataFrame(rows)
    D.attrs["thr"] = thr
    return D


def stat(D, B=9999):
    return I.event_test(D["drift20"], D["R0"], D["year"].astype(str), D["sector"], direction=1, B=B)


def spread(D, cost=0.002):
    out = []
    for _, g in D.groupby("day"):
        if len(g) < 6:
            continue
        q = pd.qcut(g["R0"].rank(method="first"), 3, labels=False)
        out.append(g["drift20"][q == 2].mean() - g["drift20"][q == 0].mean() - cost)
    return float(np.mean(out))


if __name__ == "__main__":
    if sys.argv[1] == "build":
        D = build()
        D.to_parquet(ROWS)
        print(D.groupby(["year", "kind"])["day"].nunique().unstack(fill_value=0).to_string())
        print(f"rows {len(D):,}; shock sessions {D['day'].nunique()}")
    elif sys.argv[1] == "fit":
        D = pd.read_parquet(ROWS)
        F = D[(D["day"] >= FIT[0]) & (D["day"] <= FIT[1])]
        o = stat(F)
        print(f"H4 fit 2012-21 pooled: n {o['n']:,} ({F['day'].nunique()} shock days), beta {o['beta']:+.4f}, "
              f"t {o['t']:+.2f}, p_wild {o['p_wild']:.4f}, p_ri {o['p_ri']:.4f}, clusters {o['clusters']}; "
              f"net tercile spread {spread(F) * 1e4:+.1f} bp")
        for k in ("threat", "act"):
            x = F[F["kind"].isin([k, "both"])]
            o = stat(x)
            print(f"  descriptive, {k} days (incl. both): n {o['n']:,}, beta {o['beta']:+.4f}, t {o['t']:+.2f}, p {o['p']:.4f}")
