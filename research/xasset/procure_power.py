"""Breadth and power arithmetic for the futures procurement decision (PROCURE.md section 4). Reads no return data.

1. Lo (2002) iid standard error, as in power.py on research/xasset-scope-20261125: SE = sqrt((1 + S^2/2) / T);
   a one-sided test at level alpha with power 1 - beta needs T = (z_a + z_b)^2 (1 + S^2/2) / S^2 years.
2. Breadth. An equal-risk portfolio of N markets, each with the same single-market appraisal ratio AR_1, has
   AR_N = AR_1 * N / sqrt(sum_ij rho_ij); with one pairwise correlation rho this is AR_1 * sqrt(N / (1 + (N-1) rho)).
   N_eff = N / (1 + (N-1) rho) is the number of independent bets; N_eff * T, not N * T, is the market-years count.
   AR_N tends to AR_1 / sqrt(rho) as N grows: breadth can never buy more than that.
3. A block version calibrated on Moskowitz, Ooi and Pedersen (2012), Table 4 (read): average pairwise correlation of
   12-month TSMOM returns within commodities 0.07, fixed income 0.38, currencies 0.10 (equities 0.37), and
   correlations of the asset-class TSMOM portfolios 0.05 to 0.21 (1985-2009). Instrument-level cross-class
   correlations are backed out of the portfolio correlations with MOP's counts (24, 13, 12, 9).
4. Time-varying breadth. N(t) by class comes from the vendors' published first-trade dates (procure_coverage.json)
   and, for the proxy, from SCOPE.md section 7 (FRED and H.10 start dates). The effective AR of a sample is the
   time-average of AR_N(t) over its years, because the sleeve is run at constant ex-ante volatility.

These are design inputs. Every AR here is assumed, not estimated. The iid SE ignores serial correlation and beta
estimation error, so the years are lower bounds and the powers upper bounds.

    python -I research/xasset/procure_power.py        # -> research/xasset/PROCURE_POWER.json
"""
import json
import math
import os
import re
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
N01 = NormalDist()
LEVELS = {"5%": 0.05, "0.10/40": 0.10 / 40, "0.10/60": 0.10 / 60}
AR1 = [0.1, 0.15, 0.2, 0.25, 0.3]
RHO = [0.1, 0.2, 0.3]
NS = [9, 40, 50, 60]

# MOP 2012 Table 4 (read): within-class pairwise TSMOM correlations and asset-class portfolio correlations
MOP_N = {"COM": 24, "EQ": 9, "FI": 13, "FX": 12}
MOP_WITHIN = {"COM": 0.07, "EQ": 0.37, "FI": 0.38, "FX": 0.10}
MOP_PORT = {("COM", "EQ"): 0.20, ("COM", "FI"): 0.07, ("COM", "FX"): 0.13,
            ("EQ", "FI"): 0.21, ("EQ", "FX"): 0.20, ("FI", "FX"): 0.05}


def se(s, t):
    return math.sqrt((1 + s * s / 2) / t)


def years_needed(s, alpha, power):
    z = N01.inv_cdf(1 - alpha) + N01.inv_cdf(power)
    return z * z * (1 + s * s / 2) / (s * s)


def power_at(s, t, alpha):
    return N01.cdf(s / se(s, t) - N01.inv_cdf(1 - alpha))


def uniform_mult(n, rho):
    return math.sqrt(n / (1 + (n - 1) * rho))


def eff(c, n=None, within=None):
    n = MOP_N[c] if n is None else n
    w = MOP_WITHIN[c] if within is None else within
    return (1 + (n - 1) * w) / n


def mop_cross():
    """Instrument-level cross-class correlation implied by MOP's portfolio-level correlation."""
    out = {}
    for (a, b), c in MOP_PORT.items():
        out[(a, b)] = out[(b, a)] = c * math.sqrt(eff(a) * eff(b))
    return out


CROSS = mop_cross()


def block_mult(counts, within):
    """AR_N / AR_1 = N / sqrt(sum_ij rho_ij) for class counts with within-class and MOP cross-class correlations."""
    n = sum(counts.values())
    if n == 0:
        return 0.0
    tot = 0.0
    for a, na in counts.items():
        tot += na + na * (na - 1) * within[a]
        for b, nb in counts.items():
            if a != b:
                if base(a) == base(b):  # US and non-US rates: MOP's fixed-income within-class value
                    tot += na * nb * MOP_WITHIN["FI"]
                else:
                    tot += na * nb * CROSS[(base(a), base(b))]
    return n / math.sqrt(tot)


def base(c):
    return {"FI_US": "FI", "FI_INTL": "FI"}.get(c, c)


US_RATES = r"Treasury|T-Note|T-Bond|T-Notes|T-Bonds|30 Year Bond|U\.S\.|Federal Funds|Fed Funds|Eurodollar|Muni|Swap"


def vendor_counts(markets, year, keep):
    """Class counts of non-duplicate markets live in `year` that pass `keep`."""
    c = {}
    for m in markets:
        if m["duplicate"] or m["start_year"] > year:
            continue
        end = m.get("end", "current")
        if isinstance(end, str) and re.match(r"^\d{4}", end) and int(end[:4]) < year:
            continue
        cls = m["class"]
        if cls == "FI":
            cls = "FI_US" if re.search(US_RATES, m["market"]) else "FI_INTL"
        if keep(cls, year):
            c[cls] = c.get(cls, 0) + 1
    return c


def proxy_counts(year):
    """SCOPE.md section 7 universe: 5y, 10y from 1962; 2y from 1976; 30y from 1977; 8 currencies 1972-1989."""
    r = 2 + (year >= 1976) + (year >= 1977)
    c = {"FI_US": r}
    if 1972 <= year <= 1989:
        c["FX"] = 8
    return c


def window_ar(counts_fn, y0, y1, within, ar1):
    """Time-average AR over [y0, y1) in calendar years (fractional ends allowed), and the average N."""
    t, acc, accn, y = 0.0, 0.0, 0.0, y0
    while y < y1 - 1e-9:
        step = min(1.0, math.floor(y) + 1 - y, y1 - y)
        c = counts_fn(int(math.floor(y)))
        n = sum(c.values())
        mult = (uniform_mult(n, within) if n else 0.0) if isinstance(within, float) else block_mult(c, within)
        acc += step * ar1 * mult
        accn += step * sum(c.values())
        t += step
        y += step
    return acc / t, accn / t, t


def main():
    cov = json.load(open(os.path.join(HERE, "procure_coverage.json")))
    out = {"method": __doc__.strip().splitlines()[:22], "levels": LEVELS}

    # replication check against SCOPE's POWER.json (5% one-sided, S=0.3: 71.8 / 31.4 years)
    out["check_power_py"] = {"S=0.3, 5%, power 80/50": [round(years_needed(0.3, 0.05, 0.8), 1),
                                                         round(years_needed(0.3, 0.05, 0.5), 1)]}

    # 1. uniform-correlation model
    uni = []
    for n in NS:
        for rho in RHO:
            m = uniform_mult(n, rho)
            row = {"N": n, "rho": rho, "N_eff": round(n / (1 + (n - 1) * rho), 2), "multiplier": round(m, 3),
                   "cap_multiplier_N_inf": round(1 / math.sqrt(rho), 3), "by_AR1": {}}
            for a in AR1:
                s = a * m
                row["by_AR1"][str(a)] = {
                    "AR_N": round(s, 3),
                    **{f"years_80_{k}": round(years_needed(s, v, 0.8), 1) for k, v in LEVELS.items()},
                    **{f"years_50_{k}": round(years_needed(s, v, 0.5), 1) for k, v in LEVELS.items()}}
            uni.append(row)
    out["uniform"] = uni

    # naive vs effective market-years
    out["market_years"] = [{"N": n, "T": t, "rho": r, "naive": n * t, "effective": round(n / (1 + (n - 1) * r) * t, 1)}
                           for n, t in ((50, 40), (9, 40.5)) for r in RHO]

    # 2. MOP-calibrated block model: check against MOP's own universe (58 markets) and implied average rho
    mop_all = dict(MOP_N)
    within_mop = dict(MOP_WITHIN)
    m58 = block_mult(mop_all, within_mop)
    implied_rho = (58 / m58 ** 2 - 1) / 57
    out["mop_calibration"] = {
        "cross_class_instrument_rho": {f"{a}-{b}": round(v, 4) for (a, b), v in CROSS.items() if a < b},
        "multiplier_58_markets": round(m58, 3), "implied_uniform_rho_58": round(implied_rho, 3),
        "non_equity_45_markets_multiplier": round(block_mult({"COM": 24, "FI": 13, "FX": 12 - 4}, within_mop), 3),
        "check": "MOP report a diversified 58-market Sharpe ratio 'greater than one' (gross, 1985-2009) and an average "
                 "per-market Sharpe that HOP put at about 0.4 (1880-2016). Multiplier x 0.4 should be near or above 1.",
        "predicted_portfolio_SR_at_AR1_0.4": round(0.4 * m58, 2)}

    # 3. time-varying samples (all end 2002-06, before the spent ETF era; FX stops 1989 to stay off the
    #    cross-sectional currency reads 1990-2003)
    pt = cov["portara"]["markets"]
    ng = cov["norgate"]["markets"]
    pn = cov["pinnacle_clc"]["markets"]
    noeq = lambda cls, y: cls in ("COM", "FI_US", "FI_INTL", "FX") and not (cls == "FX" and y >= 1990)
    supp = lambda cls, y: cls in ("COM", "FI_INTL")

    def comb(vendor):
        def f(y):
            c = proxy_counts(y)
            for k, v in vendor_counts(vendor, y, supp).items():
                c[k] = c.get(k, 0) + v
            return c
        return f

    samples = {
        "proxy_1962_2002 (rates + FX 1972-89)": (proxy_counts, 1962.0, 2002.5),
        "portara_replace_1975_2002 (all non-equity; FX to 1989)": (lambda y: vendor_counts(pt, y, noeq), 1975.0, 2002.5),
        "portara_replace_1980_2002": (lambda y: vendor_counts(pt, y, noeq), 1980.0, 2002.5),
        "norgate_replace_1980_2002": (lambda y: vendor_counts(ng, y, noeq), 1980.0, 2002.5),
        "portara_supplement_only_1970_2002 (commodities + non-US rates)": (lambda y: vendor_counts(pt, y, supp), 1970.0, 2002.5),
        "combined_proxy_plus_portara_supplement_1962_2002": (comb(pt), 1962.0, 2002.5),
        "combined_proxy_plus_norgate_supplement_1962_2002": (comb(ng), 1962.0, 2002.5),
        "combined_proxy_plus_pinnacle_supplement_1962_2002": (comb(pn), 1962.0, 2002.5),
    }
    within_sets = {"MOP (US curve rho 0.38)": {**MOP_WITHIN, "FI_US": 0.38, "FI_INTL": 0.38},
                   "US curve rho 0.7": {**MOP_WITHIN, "FI_US": 0.7, "FI_INTL": 0.38},
                   "uniform rho 0.1": 0.1, "uniform rho 0.2": 0.2, "uniform rho 0.3": 0.3}
    ts = {}
    for name, (fn, y0, y1) in samples.items():
        ts[name] = {"years": round(y1 - y0, 1),
                    "N_by_year": {str(y): fn(y) for y in (1962, 1970, 1975, 1980, 1985, 1990, 1995, 2002) if y >= int(y0)}}
        for wname, w in within_sets.items():
            res = {}
            for a in AR1:
                s, nbar, t = window_ar(fn, y0, y1, w, a)
                res[str(a)] = {"AR_eff": round(s, 3), "N_avg": round(nbar, 1),
                               **{f"power_{k}": round(power_at(s, t, v), 3) for k, v in LEVELS.items()},
                               "years_80_0.10/40": round(years_needed(s, LEVELS["0.10/40"], 0.8), 1),
                               "years_50_0.10/40": round(years_needed(s, LEVELS["0.10/40"], 0.5), 1)}
            ts[name][wname] = res
    out["time_varying"] = ts

    # uniform-rho comparison at the windows' lengths, for the owner's N = 9 versus 40-60
    out["uniform_windows"] = []
    for rho in RHO:
        for a in (0.1, 0.2, 0.3):
            for label, n, t in (("proxy N=9, 40.5 y", 9, 40.5), ("vendor N=50, 1980-2002 22.5 y", 50, 22.5),
                                ("vendor N=50, 1975-2002 27.5 y", 50, 27.5), ("vendor N=60, 1980-2025 45.9 y (spent)", 60, 45.9)):
                s = a * uniform_mult(n, rho)
                out["uniform_windows"].append({"rho": rho, "AR1": a, "sample": label, "AR_N": round(s, 3),
                                               **{f"power_{k}": round(power_at(s, t, v), 3) for k, v in LEVELS.items()}})
    p = os.path.join(HERE, "PROCURE_POWER.json")
    json.dump(out, open(p, "w"), indent=1)
    print(json.dumps(out["check_power_py"]), json.dumps(out["mop_calibration"], indent=0))
    for name, r in ts.items():
        for wname in within_sets:
            print(f"{name[:58]:58s} {wname[:14]:14s}", {a: (r[wname][a]["AR_eff"], r[wname][a]["N_avg"], r[wname][a]["power_0.10/40"], r[wname][a]["power_5%"]) for a in ("0.1", "0.2", "0.3")})


if __name__ == "__main__":
    main()
