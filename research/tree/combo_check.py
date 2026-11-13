"""Layer 3, exploitation step: would adding the broad-universe trees book to the fund raise its Sharpe above 1?
DESCRIPTIVE ONLY. Both inputs are out-of-sample series that have already been read once:
  * the whole fund 2020-2025 (200-session S&P core 1.3x/0.7x + MASTER decile book, gross 0.6, 5 bp), as in
    oos_returns.py (research/sharpe/construct.py, S0);
  * the broad survivorship-free trees book (L3b candidate predictions from read3.py, M1 decile book, target clipped
    at +-1 per Amendment 5), at 5, 10 and 20 bp.
Nothing here is a test: the combination weights below are either fixed by a rule stated before running (equal risk
to the fund's existing stock book) or the ex-post optimum (an upper bound). Coordinating session only.

    python research/tree/combo_check.py      # -> COMBO_CHECK.json
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
sys.path.insert(0, os.path.join(ROOT, "research", "sharpe"))
import construct as K  # noqa: E402
import read3 as R3  # noqa: E402
from holdout2 import load_module, rows_for  # noqa: E402


def fund_weekly():
    K.YEARS = range(2020, 2026)
    d = K.T.build()
    K.RF = K.ST.dtb3()
    K.GROSS_SIDE = 0.3                                                     # gross 0.6, as the fund reference
    p = np.load(os.path.join(K.QT, ".cache", "quant_trials", "sp500_tf_master_h5.npz"))["h5"].astype(np.float64)
    sec = K.sectors(d["names"])
    df = K.run(d, p, "S0", 5e-4, sec, np.zeros(len(sec), int), K.panic_flags(d))
    t = [t for t, *_ in K.ST.periods(d, K.YEARS)]
    df["date"] = pd.DatetimeIndex(d["S"])[t]
    df["wk_total"], df["wk_book"] = df.total * 7 / df.days, df.book * 7 / df.days
    return df.set_index("date")


def broad_weekly(cost):
    M1 = load_module(os.path.join(HERE, "M1_dyntrade", "lib.py"), "m1lib_combo")
    M1.COST = cost
    D, isb = R3.load_panel()
    Ds = dict(D)
    Ds["elig"] = D["elig"] & isb[None, :]
    Ds["y5"] = np.clip(D["y5"], -1.0, 1.0)
    p = np.load(os.path.join(ROOT, ".cache", "tree", "read3_pred_L3b_candidate.npy")).astype(np.float64)
    s = np.where(Ds["elig"], p, np.nan)
    rows = rows_for(D, R3.YEARS)
    rows = np.array([t for t in rows if M1.mask(s, Ds, t).sum() >= 50])
    W = M1.build("decile", s, Ds, rows)
    net = np.asarray(M1.simulate(W, Ds, rows)["net"], float)
    return pd.Series(net, index=pd.DatetimeIndex(D["S"])[rows])


def sharpe(x):
    x = np.asarray(x, float)
    return float(x.mean() / x.std(ddof=1) * math.sqrt(52))


def main():
    F = fund_weekly()
    out = {"note": "descriptive; both series out of sample and already read; not a test", "period": None, "by_cost": {}}
    for cost in (5e-4, 1e-3, 2e-3):
        B = broad_weekly(cost)
        j = F.join(B.rename("broad"), how="inner")
        out["period"] = [str(j.index[0].date()), str(j.index[-1].date()), int(len(j))]
        f, bk, b = j.wk_total.values, j.wk_book.values, j.broad.values
        k_eq = bk.std(ddof=1) / b.std(ddof=1)                               # rule: equal risk to the existing stock book
        ks = np.linspace(0, 6, 601)
        sh = [sharpe(f + k * b) for k in ks]
        k_opt = float(ks[int(np.argmax(sh))])
        res = {"fund_sharpe": sharpe(f), "fund_pct_per_year": float(52 * 100 * f.mean()),
               "broad_book_sharpe": sharpe(b), "broad_book_pct_per_year": float(52 * 100 * b.mean()),
               "corr_broad_vs_fund": float(np.corrcoef(f, b)[0, 1]),
               "corr_broad_vs_fund_stock_book": float(np.corrcoef(bk, b)[0, 1]),
               "corr_broad_vs_spy": float(np.corrcoef(j.spy.values, b)[0, 1]),
               "equal_risk": {"k": float(k_eq), "sharpe": sharpe(f + k_eq * b), "pct_per_year": float(52 * 100 * (f + k_eq * b).mean())},
               "ex_post_optimum_upper_bound": {"k": k_opt, "sharpe": float(max(sh))},
               "projection_independent": float(math.sqrt(sharpe(f) ** 2 + sharpe(b) ** 2))}
        out["by_cost"][f"{cost * 1e4:.0f}bp"] = res
        print(f"{cost * 1e4:.0f}bp", json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in res.items()}))
    json.dump(out, open(os.path.join(HERE, "COMBO_CHECK.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
