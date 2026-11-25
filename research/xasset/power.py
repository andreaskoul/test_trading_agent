"""Power arithmetic for the cross-asset scoping memo (SCOPE.md section 3). No data is read.

Lo (2002) iid standard error of an annualised Sharpe ratio (or appraisal ratio, the Sharpe ratio of the residual)
estimated over T years: SE = sqrt((1 + S^2 / 2) / T). One-sided test at level alpha with power 1 - beta needs
S / SE >= z_alpha + z_beta, so T = (z_alpha + z_beta)^2 (1 + S^2 / 2) / S^2.

Two levels: the conventional 5% asked for in the brief, and the programme admission level of DESIGN_RULES.md rule 2,
alpha = 0.10 / N, shown at N = 40 and N = 60 (the registered N must be recounted from DATA_USE.md at registration).
The iid SE ignores serial correlation and the estimation error of the betas in the appraisal ratio; both make the
real SE larger, so the years below are lower bounds.

    python research/xasset/power.py      # -> research/xasset/POWER.json
"""
import json
import os
from statistics import NormalDist

N01 = NormalDist()
RATIOS = [0.3, 0.4, 0.6]
LEVELS = {"5% one-sided": 0.05, "programme 0.10/40": 0.10 / 40, "programme 0.10/60": 0.10 / 60}
# candidate samples: (key, years, label). Years are calendar spans from SCOPE.json coverage rows.
SAMPLES = [
    ("forward_1y", 1.0, "forward record, 1 year"),
    ("forward_3y", 3.0, "forward record, 3 years"),
    ("forward_5y", 5.0, "forward record, 5 years"),
    ("etf_unread_2007_2025", 18.7, "ETFs not used by X1, 2007-04..2025-12"),
    ("yahoo_cont_futures_2000_2026", 26.2, "Yahoo continuous futures, 2000-09..2026-11"),
    ("vx_futures_2004_2026", 22.7, "CBOE VIX futures contracts, 2004-03..2026-11"),
    ("proxy_1972_2002", 30.5, "proxy: FRED CMT + OECD yields + H.10 FX + commodities, 1972-01..2002-06"),
    ("proxy_1962_2002", 40.5, "proxy without FX before 1972, 1962-01..2002-06"),
    ("cboe_option_indices_1986_2026", 40.4, "CBOE BXMD/CNDR/PPUT/BFLY, 1986-06..2026-11 (benchmark)"),
    ("aqr_tsmom_1985_2026", 41.4, "AQR TSMOM factors, 1985-01..2026-05 (benchmark)"),
    ("aqr_century_1926_2026", 99.6, "AQR Century of Factor Premia, 1926-07..2026-02 (benchmark)"),
    ("jst_annual_1870_2020", 151.0, "Jorda-Schularick-Taylor annual, 1870..2020 (benchmark, annual)"),
]


def se(s, t):
    return ((1 + s * s / 2) / t) ** 0.5


def years_needed(s, alpha, power):
    z = N01.inv_cdf(1 - alpha) + N01.inv_cdf(power)
    return z * z * (1 + s * s / 2) / (s * s)


def power_at(s, t, alpha):
    return N01.cdf(s / se(s, t) - N01.inv_cdf(1 - alpha))


def main():
    out = {"method": __doc__.strip().splitlines()[2:6], "years_needed": {}, "power": {}}
    for lv, a in LEVELS.items():
        out["years_needed"][lv] = {
            f"S={s}": {"power_80": round(years_needed(s, a, 0.8), 1), "power_50": round(years_needed(s, a, 0.5), 1)}
            for s in RATIOS}
    for key, t, label in SAMPLES:
        out["power"][key] = {"years": t, "label": label,
                             **{lv: {f"S={s}": round(power_at(s, t, a), 3) for s in RATIOS} for lv, a in LEVELS.items()}}
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "POWER.json")
    with open(p, "w") as f:
        json.dump(out, f, indent=1)
    for lv in LEVELS:
        print(lv, out["years_needed"][lv])
    for key in out["power"]:
        r = out["power"][key]
        print(f"{key:34s} T={r['years']:6.1f}  5%: {r['5% one-sided']}  prog/40: {r['programme 0.10/40']}")


if __name__ == "__main__":
    main()
