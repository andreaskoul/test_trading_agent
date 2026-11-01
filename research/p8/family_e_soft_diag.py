"""Post-read diagnostics for rule A (descriptive; they cannot change the registered decision in E_SOFT_READ.json).

    python3 research/p8/family_e_soft_diag.py      -> reports/research/p8/E_SOFT_DIAG.md

Same rows as the locked read (the read's functions, unchanged), plus the fit-window rows. E3 selected nothing on its fit
window (no parameter, horizon or sign was chosen there), so fit and holdout are exchangeable samples of the same rule
and their pooled estimate is the efficient one; it is reported beside the registered holdout read, never instead.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import family_e as FE                                            # noqa: E402
import family_e_soft as FS                                       # noqa: E402
import prices as PX                                              # noqa: E402

FIT8 = (pd.Timestamp("2016-01-01"), pd.Timestamp("2021-12-31"))


def stats(y, t0):
    y = pd.Series(np.asarray(y, float)) * 1e4
    m, t, n, G = FE.week_t(y.values, t0)
    se = m / t if t else np.nan
    q = y.quantile([0.01, 0.99]).values
    return {"n": n, "weeks": G, "mean": m, "se": se, "t": t, "median": float(y.median()),
            "wins1": float(y.clip(*q).mean()), "pos": float((y > 0).mean()), "sd": float(y.std())}


def line(name, s):
    return (f"| {name} | {s['n']} | {s['mean']:+.1f} | {s['se']:.1f} | {s['t']:+.2f} | {s['median']:+.1f} | "
            f"{s['wins1']:+.1f} | {s['pos']:.3f} | {s['sd']:.0f} |")


def main():
    read = json.load(open(os.path.join(PX.OUT, "E_SOFT_READ.json")))
    L = read["lag_min"]
    R = FS.returns_soft()
    A = FS.eightk_rows(FE.V0, FE.V1)
    F = FS.finnhub_rows(R, L, *FS.HOLD)
    A0 = FS.eightk_rows(*FIT8)
    F0 = FS.finnhub_rows(R, L, *FS.FIT)
    F_noL = FS.finnhub_rows(R, 0, *FS.HOLD)
    head = "| sample | n | mean bp | se | t (week) | median | 1-99% winsorised | share > 0 | sd bp |\n|---|---|---|---|---|---|---|---|---|"
    out = ["# Rule A: post-read diagnostics (descriptive; the decision is E_SOFT_READ.md)", "",
           f"Read: {read['lock']}. Rows rebuilt with the read's own functions. Standard errors clustered by week (CR1).", "",
           "## 1. The registered holdout, by source and slice", "", head,
           line("pooled holdout", stats(pd.concat([A.y, F.y]), pd.concat([A.t0, F.t0]))),
           line("8-K 2022-25", stats(A.y, A.t0)), line("Finnhub 2026-05..10", stats(F.y, F.t0))]
    for it in ["5.02", "1.01"]:
        g = A[A["type"].astype(str).str.contains(it, regex=False)]
        out.append(line(f"8-K item {it}", stats(g.y, g.t0)))
    for yr in range(2022, 2026):
        g = A[pd.to_datetime(A.t0).dt.year == yr]
        out.append(line(f"8-K {yr}", stats(g.y, g.t0)))
    for ty, g in F.groupby("type"):
        if len(g) >= 30:
            out.append(line(f"Finnhub {ty}", stats(g.y, g.t0)))
    out.append(line("Finnhub, L = 0 (no serving lag)", stats(F_noL.y, F_noL.t0)))
    out += ["", "## 2. Fit windows (nothing was selected on them for E3)", "", head,
            line("8-K 2016-21", stats(A0.y, A0.t0)), line("Finnhub 2025-11..2026-04", stats(F0.y, F0.t0)),
            line("8-K 2016-25 (fit + holdout)", stats(pd.concat([A0.y, A.y]), pd.concat([A0.t0, A.t0]))),
            line("Finnhub 2025-11..2026-10", stats(pd.concat([F0.y, F.y]), pd.concat([F0.t0, F.t0]))),
            line("all E3 rows", stats(pd.concat([A0.y, A.y, F0.y, F.y]), pd.concat([A0.t0, A.t0, F0.t0, F.t0])))]
    agree, n = FS.applicability()
    out += ["", "## 3. Desk agreement", "", f"{agree}/{n}; rows written to the JSON."]
    json.dump({"holdout": {"8k": stats(A.y, A.t0), "finnhub": stats(F.y, F.t0)},
               "fit": {"8k": stats(A0.y, A0.t0), "finnhub": stats(F0.y, F0.t0)},
               "agree": [agree, n]}, open(os.path.join(PX.OUT, "E_SOFT_DIAG.json"), "w"), indent=1, default=float)
    open(os.path.join(PX.OUT, "E_SOFT_DIAG.md"), "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
