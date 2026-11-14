"""H7: the 2026 sealed test of the combined fund (PREREG Layer 3, Amendments 7 and 7a). Coordinating session only.
Read once: H7.lock. Results -> H7_RESULT.json.

    python research/tree/h7_read.py

Inputs (built by h7_build.py, committed before this read; models fitted on targets ending before 2026):
  .cache/tree/y2026/sp_panel.npz, master_h5_2026.npy       fund side (S&P 500 panel extended to 2026-11-12)
  .cache/tree/y2026/broad_panel.npz, trees_2026.npy         broad side
  .cache/tree/y2026/trees_2025_refit.npy, the October MASTER scores for 2025: used only so that both books enter 2026
  already held (Amendment 7a), never scored.
Test: per arm, weekly increment = k x broad book net return (14 bp, y5 clipped at +-1) over the 2026 weeks; one-sided
Newey-West t (4 lags) of its mean > 0; Holm across H7a and H7b at alpha 0.05.
"""
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
Y = os.path.join(ROOT, ".cache", "tree", "y2026")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "research", "sharpe"))
import harness as H  # noqa: E402
import construct as K  # noqa: E402
from holdout2 import load_module, nw  # noqa: E402

LOCK, OUT = os.path.join(HERE, "H7.lock"), os.path.join(HERE, "H7_RESULT.json")
COST_BROAD = 14e-4


def npz(path):
    z = np.load(path, allow_pickle=False)
    D = {k: z[k] for k in z.files}
    D["S"] = pd.DatetimeIndex(D["S"])
    D["names"] = [str(n) for n in D["names"]]
    return D


def fund_weekly():
    d = npz(os.path.join(Y, "sp_panel.npz"))
    old = np.load(os.path.join(K.QT, ".cache", "quant_trials", "sp500_tf_master_h5.npz"))["h5"].astype(np.float64)
    new = np.load(os.path.join(Y, "master_h5_2026.npy")).astype(np.float64)
    pred = np.full(new.shape, np.nan)
    pred[: len(old)] = old
    is26 = d["S"].year == 2026
    pred[is26] = new[is26]
    K.YEARS = range(2025, 2027)
    K.RF = K.ST.dtb3()
    K.GROSS_SIDE = 0.3
    sec = K.sectors(d["names"])
    df = K.run(d, pred, "S0", 5e-4, sec, np.zeros(len(sec), int), K.panic_flags(d))
    t = [t for t, *_ in K.ST.periods(d, K.YEARS)]
    df["date"] = d["S"][t]
    df["wk_total"], df["wk_book"] = df.total * 7 / df.days, df.book * 7 / df.days
    rows26 = np.where((d["S"].weekday == 3) & is26)[0]
    rows26 = rows26[rows26 < len(d["S"]) - 7]
    ic = H.weekly_ic(pred, d, rows26)
    return df.set_index("date"), {"master_ic_2026": nw(ic)[:3], "rf_last_date": str(K.RF.index.max().date())}


def broad_books():
    M1 = load_module(os.path.join(HERE, "M1_dyntrade", "lib.py"), "m1lib_h7")
    M1.COST = COST_BROAD
    D = npz(os.path.join(Y, "broad_panel.npz"))
    isb = D.pop("isb").astype(bool)
    S = D["S"]
    p = np.load(os.path.join(Y, "trees_2025_refit.npy")).astype(np.float64)
    new = np.load(os.path.join(Y, "trees_2026.npy")).astype(np.float64)
    is26 = S.year == 2026
    p[is26] = new[is26]
    elig_b = D["elig"] & isb[None, :]
    top2 = np.zeros_like(elig_b)
    th = np.where((S.weekday == 3) & (S.year >= 2025))[0]
    for t in th:
        e = elig_b[t] & np.isfinite(D["dv"][t])
        if e.sum():
            pr = pd.Series(D["dv"][t][e]).rank(pct=True).to_numpy()
            top2[t, np.where(e)[0][pr >= 1 / 3]] = True
    tz = np.load(os.path.join(Y, "trees_dv_tercile_2026.npz"), allow_pickle=False)
    agree = float(np.mean([(top2[r] == (tz["tercile"][i] >= 2)).all() for i, r in enumerate(tz["rows"])]))
    out, info = {}, {"tercile_file_agrees_share_of_weeks": agree}
    for arm, el in (("H7a", elig_b), ("H7b", top2)):
        Ds = dict(D)
        Ds["elig"] = el
        Dc = dict(Ds)
        Dc["y5"] = np.clip(Ds["y5"], -1.0, 1.0)
        s = np.where(el, p, np.nan)
        rows = np.array([t for t in th if M1.mask(s, Dc, t).sum() >= 50])
        W = M1.build("decile", s, Dc, rows)
        sim = M1.simulate(W, Dc, rows)
        ser = pd.DataFrame({"net": sim["net"], "gross": sim["gross"], "turn": sim["turn"]}, index=S[rows])
        out[arm] = ser[ser.index.year == 2026]
        r26 = rows[S[rows].year == 2026]
        ic = H.weekly_ic(p, Ds, r26)
        info[arm] = {"trees_ic_2026": nw(ic)[:3], "names_per_week": float(np.mean([M1.mask(s, Dc, t).sum() for t in r26])),
                     "turnover_per_week": float(out[arm].turn.mean())}
    # reported: IC by dollar-volume tercile (all eligible broad names)
    r26 = np.array([t for t in th if S[t].year == 2026 and t < len(S) - 7])
    by = {}
    for k, (lo, hi) in enumerate(((0, 1 / 3), (1 / 3, 2 / 3), (2 / 3, 1.0001))):
        q = np.zeros_like(elig_b)
        for t in r26:
            e = elig_b[t] & np.isfinite(D["dv"][t])
            pr = pd.Series(D["dv"][t][e]).rank(pct=True).to_numpy()
            q[t, np.where(e)[0][(pr >= lo) & (pr < hi)]] = True
        Dt = dict(D)
        Dt["elig"] = q
        by[k + 1] = nw(H.weekly_ic(p, Dt, r26))[:2]
    info["trees_ic_by_dv_tercile"] = by
    return out, info


def stats(x):
    x = np.asarray(x, float)
    v = np.cumprod(1 + x)
    dd = float((v / np.maximum.accumulate(np.concatenate([[1], v]))[1:] - 1).min())
    return {"pct_per_year": float(52 * 100 * x.mean()), "net_sharpe": float(x.mean() / x.std(ddof=1) * math.sqrt(52)),
            "worst_fall_pct": 100 * dd, "weeks": int(len(x))}


def main():
    if os.path.exists(LOCK):
        sys.exit("H7 was already read: " + open(LOCK).read())
    open(LOCK, "w").write(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    k = json.load(open(os.path.join(HERE, "H7_WEIGHTS.json")))
    F, finfo = fund_weekly()
    B, binfo = broad_books()
    F26 = F[F.index.year == 2026]
    res = {"fund_info": finfo, "broad_info": binfo, "weights": {"H7a": k["k_a"], "H7b": k["k_b"]}, "arms": {}}
    p = {}
    for arm, kk in (("H7a", k["k_a"]), ("H7b", k["k_b"])):
        j = F26.join(B[arm], how="inner")
        inc = kk * j.net.values
        mean, t, n = nw(inc)
        p[arm] = float(0.5 * math.erfc(t / math.sqrt(2)))
        res["arms"][arm] = {"weeks": n, "period": [str(j.index[0].date()), str(j.index[-1].date())],
                            "increment_pct_per_year": float(52 * 100 * mean), "t": t, "p_one_sided": p[arm],
                            "broad_book": stats(j.net.values), "broad_book_gross_pct_per_year": float(52 * 100 * j.gross.mean()),
                            "fund_alone": stats(j.wk_total.values), "combined": stats(j.wk_total.values + inc),
                            "corr_broad_vs_fund": float(np.corrcoef(j.wk_total.values, j.net.values)[0, 1]),
                            "spy_pct_per_year": float(52 * 100 * (j.spy * 7 / j.days).mean())}
    ok, holm = True, {}
    for i, a in enumerate(sorted(p, key=p.get)):
        ok = ok and p[a] <= 0.05 / (len(p) - i)
        holm[a] = bool(ok)
    res["holm_pass"] = holm
    ic_a = binfo["H7a"]["trees_ic_2026"][0]
    res["broken_rule"] = {a: bool(ic_a <= 0 and res["arms"][a]["increment_pct_per_year"] < 0) for a in p}
    res["run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(res, open(OUT, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
