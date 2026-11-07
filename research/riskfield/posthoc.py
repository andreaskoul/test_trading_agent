"""Risk-field research: post-hoc DESCRIPTIVE breakdowns after the one OOS read (not tests; nothing here changes a
verdict). Where does H-B1's gain come from, and does it hold every year?

    python research/riskfield/posthoc.py     # -> POSTHOC.md
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import beta as BT                                                                     # noqa: E402
import risk as K                                                                      # noqa: E402


def main():
    D = K.Data()
    B = BT.build(D)
    st = np.broadcast_to(D.stock, (D.T, D.N)) & B["thu"][:, None]
    full = [B["b21"], B["b63"], B["ols"]]
    mask = st & np.all([np.isfinite(r) for r in full + [B["B0"]]], 0)
    o = K.origins(D, 21, K.OOS) & B["thu"]
    fc = {"B0 (fund)": np.where(mask, B["B0"], np.nan),
          "daily OLS, raw": np.where(mask, B["ols"], np.nan),
          "HF 63, raw": np.where(mask, B["b63"], np.nan)}
    for nm, regs in (("calibrated daily OLS only", [B["ols"]]), ("calibrated HF 63 only", [B["b63"]]),
                     ("B1 (HF 21 + HF 63 + daily OLS)", full)):
        fc[nm], _ = K.forecasts(D, regs, B["tgt"], mask, 21, K.OOS[1])
    rows = []
    for nm, f in fc.items():
        e = np.where(o[:, None] & mask, (B["tgt"] - f) ** 2, np.nan)
        rows.append({"forecast": nm, "MSE": np.nanmean(e)})
    L = ["# Risk-field research: post-hoc breakdowns (descriptive, after the OOS read)", "",
         "Beta forecasts, OOS weekly decisions 2020-2025, same names and weeks. The target is the next 21 sessions'",
         "realised beta from 30-minute returns.", "", "| Forecast | MSE | vs fund |", "|---|---:|---:|"]
    b0 = rows[0]["MSE"]
    for r in rows:
        L.append(f"| {r['forecast']} | {r['MSE']:.4f} | {100 * (r['MSE'] / b0 - 1):+.1f}% |")
    # by year: B1 vs B0
    yr = D.S.year.values
    L += ["", "B1 against the fund's beta, by year (MSE):", "", "| Year | fund | B1 | change |", "|---|---:|---:|---:|"]
    f1 = fc["B1 (HF 21 + HF 63 + daily OLS)"]
    for y in range(2020, 2026):
        sel = (o & (yr == y))[:, None] & mask
        a, b = np.nanmean(np.where(sel, (B["tgt"] - fc["B0 (fund)"]) ** 2, np.nan)), np.nanmean(np.where(sel, (B["tgt"] - f1) ** 2, np.nan))
        L.append(f"| {y} | {a:.4f} | {b:.4f} | {100 * (b / a - 1):+.1f}% |")
    # last fit's coefficients
    X = np.stack([np.ones((D.T, D.N))] + full, -1)
    ok = mask & np.isfinite(B["tgt"]) & (np.arange(D.T)[:, None] + 21 < D.T)
    ok &= (D.S.values <= np.datetime64("2025-11-28"))[:, None]
    bta = np.linalg.lstsq(X[ok], B["tgt"][ok], rcond=None)[0]
    L += ["", f"B1 coefficients on all decisions with targets ended by 2025-12-31: intercept {bta[0]:.3f}, HF 21 "
          f"{bta[1]:.3f}, HF 63 {bta[2]:.3f}, daily OLS {bta[3]:.3f}."]
    # cross-sectional spread: how different are the betas?
    d = np.where(o[:, None] & mask, f1 - B["B0"], np.nan)
    L += [f"B1 minus fund beta, OOS: mean {np.nanmean(d):+.3f}, sd {np.nanstd(d):.3f}, 5th/95th percentiles "
          f"{np.nanpercentile(d, 5):+.3f} / {np.nanpercentile(d, 95):+.3f}."]
    open(os.path.join(HERE, "POSTHOC.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
