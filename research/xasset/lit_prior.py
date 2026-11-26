"""Literature prior for the appraisal ratio (AR) of non-equity time-series momentum against the trend core.

Reads no market data. Inputs:
* digitised.json (per-asset bar heights digitised by digitise.py from MOP 2012 Fig. 2, HOP 2017 Exhibits 3-4,
  Babu et al. 2020 Fig. 2);
* the table values typed below, each copied from the printed page named next to it;
* research/exposure/results.json on main (the core's full-sample Sharpe, P3).

Writes LIT_PRIOR.json. Every number this script creates is labelled `reasoning` in LIT_PRIOR.md: it is arithmetic on
copied figures under stated assumptions, not a reading of any source.

    python3 -I research/xasset/lit_prior.py > research/xasset/LIT_PRIOR.json
"""
import json
import math
import os
import statistics as st
import sys

import numpy as np
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "digitised.json")))
CORE = json.load(open(os.path.join(HERE, "..", "exposure", "results.json")))["full"]["P3"]

# ---------------------------------------------------------------- copied tables (printed values)
COPIED = {
    # HOP 2017 Exhibit 2 (printed p. 18): 12-month strategy, annualized gross Sharpe ratio, all 67 markets.
    "HOP_ex2_12m_gross_SR": {"full_1880_2016": 1.32, "1880s": 1.03, "1890s": 1.35, "1900s": 1.52, "1910s": 0.99,
                             "1920s": 1.77, "1930s": 1.09, "1940s": 1.54, "1950s": 1.55, "1960s": 1.01,
                             "1970s": 1.91, "1980s": 1.46, "1990s": 1.38, "2000s": 1.10, "2010_2016": 0.73},
    # HOP 2017 Exhibit 1 (printed p. 17): full sample, diversified 1/3/12 strategy at 10% target volatility.
    "HOP_ex1_full": {"gross_fee_gross_cost_excess": 0.180, "gross_fee_net_cost_excess": 0.110,
                     "net_2_20_net_cost_excess": 0.073, "realized_vol": 0.097, "SR_net_fees_costs": 0.76,
                     "corr_US_equity": -0.01, "corr_US_10y": -0.03},
    # HOP 2017 Exhibit B1 (printed p. 27): one-way cost, % of notional traded.
    "HOP_B1_oneway_cost": {"bonds": {"1880_1992": 0.0006, "1993_2002": 0.0002, "2003_2016": 0.0001},
                           "currencies": {"1880_1992": 0.0018, "1993_2002": 0.0006, "2003_2016": 0.0003}},
    # MOP 2012 Table 1 (p. 232): annualized volatility of the contract (Jan 1965 - Dec 2009 sample).
    "MOP_t1_vol": {"US2": 0.0186, "US5": 0.0425, "US10": 0.0930, "US30": 0.1856,
                   "AUD": 0.1086, "EUR": 0.1121, "CAD": 0.0629, "JPY": 0.1166, "NOK": 0.1056, "NZD": 0.1201,
                   "SEK": 0.1106, "CHF": 0.1233, "GBP": 0.1032},
    # MOP 2012 Table 4 (p. 240): average pairwise correlation of 12-month TSMOM returns, 1985-2009.
    "MOP_t4": {"within_FI": 0.38, "within_FX": 0.10, "FI_vs_FX": 0.05, "FI_vs_EQ": 0.21, "FX_vs_EQ": 0.20},
    # MOP 2012 Table 2 (p. 235): t-stat of alpha, k=12, h=1, on MSCI World, bond, GSCI, SMB, HML, UMD; 1985-2009.
    "MOP_t2_alpha_t_k12_h1": {"all": 6.61, "bonds": 3.53, "currencies": 3.41},
    # McLean-Pontiff 2016 abstract (p. 5), Table I (p. 11), Table II col. 1 (p. 13).
    "MP": {"decline_out_of_sample": 0.26, "decline_post_publication": 0.58, "publication_effect": 0.32,
           "mean_in_sample_monthly_pct": 0.582, "mean_oos_monthly_pct": 0.402, "mean_post_pub_monthly_pct": 0.264,
           "coef_post_sample": -0.150, "coef_post_publication": -0.337},
    # Huang-Li-Wang-Zhou 2020 Table 9 (p. 789): TSM Sharpe ratio per asset, monthly (not annualized), 1986-2015,
    # unscaled sign strategy; and TSH (historical-mean sign) Sharpe ratio.
    "HLWZ_t9_TSM_SR_monthly": {"AU3": 0.24, "AU10": 0.15, "EU2": 0.13, "EU5": 0.06, "EU10": 0.02, "EU30": 0.05,
                               "CA10": 0.11, "JP10": 0.06, "UK10": 0.14, "US2": 0.28, "US5": 0.15, "US10": 0.09,
                               "US30": 0.12, "AUD": 0.02, "EUR": 0.03, "CAD": 0.11, "JPY": 0.14, "NOK": 0.02,
                               "NZD": 0.07, "SEK": 0.01, "CHF": 0.05, "GBP": 0.00},
    "HLWZ_t9_TSH_SR_monthly": {"AU3": 0.28, "AU10": 0.21, "EU2": 0.10, "EU5": 0.11, "EU10": 0.09, "EU30": 0.19,
                               "CA10": 0.17, "JP10": 0.02, "UK10": 0.12, "US2": 0.26, "US5": 0.19, "US10": 0.13,
                               "US30": 0.20, "AUD": -0.05, "EUR": 0.03, "CAD": -0.04, "JPY": 0.03, "NOK": -0.02,
                               "NZD": 0.01, "SEK": -0.02, "CHF": 0.06, "GBP": -0.01},
}
BONDS = ["AU3", "AU10", "EU2", "EU5", "EU10", "EU30", "CA10", "JP10", "UK10", "US2", "US5", "US10", "US30"]
FXS = ["AUD", "EUR", "CAD", "JPY", "NOK", "NZD", "SEK", "CHF", "GBP"]

# MOP 2012 Table 1 data start, used for years inside 1985-2009 (sampling error of each Fig. 2 bar).
MOP_FI_YEARS = {"3 Yr Australian Bond": 18.0, "10 Yr Australian Bond": 24.1, "2 Yr Euro-Schatz": 12.8,
                "5 Yr Euro-Bobl": 17.0, "10 Yr Euro-Bund": 25.0, "30 Yr Euro-Buxl": 11.1, "10 Yr CGB": 25.0,
                "10 Yr JGB": 25.0, "10 Yr Long Gilt": 25.0, "2 Yr US Treasury Note": 13.75,
                "5 Yr US Treasury Note": 20.0, "10 Yr US Treasury Note": 25.0, "30 Yr US Treasury Bond": 20.0}

PROXY = {"rates": (1962.0, 2002.5), "fx": (1972.0, 1990.0)}  # SCOPE.md §7: rates 1962-01..2002-06, FX 1972-01..1989-12


def overlap(a, b):
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def cls(key, c):
    return D[key]["summary"][c]["mean"]


def heterogeneity(rows, years):
    """True cross-asset sd of per-asset SR: observed variance minus mean Lo-iid sampling variance."""
    v = [r["gross_sharpe"] for r in rows]
    samp = st.mean((1 + s * s / 2) / years[r["instrument"]] for r, s in zip(rows, v))
    obs = st.pvariance(v)
    return math.sqrt(max(obs - samp, 0.0)), math.sqrt(obs), math.sqrt(samp)


def sleeve_sr(s_r, s_fx, n_r, n_fx, rho_r, rho_fx, rho_x, c_r=None, c_fx=None):
    """Equal-risk sleeve over n_r rates and n_fx FX markets: (sum of per-market SR) / sd of the sum."""
    n = n_r + n_fx
    C = np.full((n, n), rho_x)
    C[:n_r, :n_r] = rho_r
    C[n_r:, n_r:] = rho_fx
    np.fill_diagonal(C, 1.0)
    sd = math.sqrt(C.sum())
    mu = n_r * s_r + n_fx * s_fx
    cost = 0.0 if c_r is None else (n_r * c_r + n_fx * c_fx)
    return (mu - cost) / sd


def ar_vs_core(sr, rho, sr_core):
    return (sr - rho * sr_core) / math.sqrt(1 - rho * rho)


def power(delta, years, z):
    se = math.sqrt((1 + delta * delta / 2) / years)
    return norm.cdf(delta / se - z)


def main():
    out = {"inputs_copied": COPIED, "core_P3_full_sample": {"sharpe": CORE["sharpe"], "years": CORE["years"],
                                                             "label": "repository: research/exposure/results.json"}}
    sr_core = CORE["sharpe"]

    # ---- per-asset class means from the digitised figures
    src = {
        "MOP_fig2_1985_2009": {"years": (1985.0, 2010.0), "FI": cls("MOP_fig2_1985_2009", "Fixed Income"),
                               "FX": cls("MOP_fig2_1985_2009", "Currencies")},
        "HOP_ex3_1880_2016": {"years": (1880.0, 2017.0), "FI": cls("HOP_ex3_1880_2016", "Fixed Income"),
                              "FX": cls("HOP_ex3_1880_2016", "Currencies")},
        "HOP_ex4_1880_1984": {"years": (1880.0, 1985.0), "FI": cls("HOP_ex4_1880_1984", "Fixed Income"),
                              "FX": cls("HOP_ex4_1880_1984", "Currencies")},
        "TE_fig2A_1985_2017": {"years": (1985.0, 2018.0), "FI": cls("TE_fig2A_1985_2017", "Fixed Income"),
                               "FX": cls("TE_fig2A_1985_2017", "Currencies")},
        "TE_fig2B_new_markets": {"FI_swaps": cls("TE_fig2B_alt_assets_to_2017", "FI swaps"),
                                 "EM_FX": cls("TE_fig2B_alt_assets_to_2017", "Emerging FX")},
        "HLWZ_t9_1986_2015_annualized": {
            "FI": round(st.mean(COPIED["HLWZ_t9_TSM_SR_monthly"][k] for k in BONDS) * math.sqrt(12), 3),
            "FX": round(st.mean(COPIED["HLWZ_t9_TSM_SR_monthly"][k] for k in FXS) * math.sqrt(12), 3),
            "FI_TSH": round(st.mean(COPIED["HLWZ_t9_TSH_SR_monthly"][k] for k in BONDS) * math.sqrt(12), 3),
            "FX_TSH": round(st.mean(COPIED["HLWZ_t9_TSH_SR_monthly"][k] for k in FXS) * math.sqrt(12), 3)},
    }
    # implied 2010-2017 per-asset class mean (TE 1985-2017 minus MOP 1985-2009, year-weighted; same 58 contracts)
    for c in ("FI", "FX"):
        src.setdefault("implied_2010_2017", {})[c] = round(
            (33 * src["TE_fig2A_1985_2017"][c] - 25 * src["MOP_fig2_1985_2009"][c]) / 8, 3)
    out["class_means_gross_SR"] = src

    # ---- US Treasury contracts in each source (the proxy's own market)
    def pick(key, names):
        rows = {r["instrument"]: r["gross_sharpe"] for r in D[key]["rows"]}
        return {n: rows[n] for n in names}
    out["US_treasuries_gross_SR"] = {
        "MOP_fig2_1985_2009": pick("MOP_fig2_1985_2009", ["2 Yr US Treasury Note", "5 Yr US Treasury Note",
                                                          "10 Yr US Treasury Note", "30 Yr US Treasury Bond"]),
        "HOP_ex3_1880_2016": pick("HOP_ex3_1880_2016", ["U.S. 2-Yr Treasury Note", "U.S. 5-Yr Treasury Note",
                                                        "U.S. 10-Yr Treasury Note", "U.S. 20-Yr Treasury Bond"]),
        "HOP_ex4_1880_1984": pick("HOP_ex4_1880_1984", ["U.S. 2-Yr Treasury Note", "U.S. 5-Yr Treasury Note",
                                                        "U.S. 10-Yr Treasury Note", "U.S. 20-Yr Treasury Bond"]),
        "TE_fig2A_1985_2017": pick("TE_fig2A_1985_2017", ["U.S. 2 Yr Treasury Note", "U.S. 5 Yr Treasury Note",
                                                          "U.S. 10 Yr Treasury Note", "U.S. 30 Yr Treasury Bond"]),
    }

    # ---- overlap of each source's years with the proxy window (dates only: 'broad'); spent samples listed in md
    ov = {}
    for k in ("MOP_fig2_1985_2009", "HOP_ex3_1880_2016", "HOP_ex4_1880_1984", "TE_fig2A_1985_2017"):
        y = src[k]["years"]
        fx_y = (max(y[0], 1971.0), y[1])  # HOP Exhibit A1: currency series start in the early 1970s
        ov[k] = {"FI_share": round(overlap(y, PROXY["rates"]) / (y[1] - y[0]), 3),
                 "FX_share": round(overlap(fx_y, PROXY["fx"]) / (fx_y[1] - fx_y[0]), 3)}
    out["overlap_share_with_proxy_dates"] = ov

    # ---- window-years premium: HOP Ex. 2 decades inside vs outside the proxy window (12-month strategy)
    e2 = COPIED["HOP_ex2_12m_gross_SR"]
    inside = [e2["1960s"], e2["1970s"], e2["1980s"], e2["1990s"]]
    outside_w = {"1880s": 1, "1890s": 1, "1900s": 1, "1910s": 1, "1920s": 1, "1930s": 1, "1940s": 1, "1950s": 1,
                 "2000s": 0.75, "2010_2016": 0.7}
    outside = sum(e2[d] * w for d, w in outside_w.items()) / sum(outside_w.values())
    k_prem = st.mean(inside) / outside
    out["window_premium"] = {"inside_mean": round(st.mean(inside), 3), "outside_mean": round(outside, 3),
                             "k": round(k_prem, 3)}

    # ---- disjoint-years centre: remove each source's in-window share, then pool the two eras
    def strip(sr, f):
        return sr / (1 + f * (k_prem - 1))
    fi_A = strip(src["HOP_ex4_1880_1984"]["FI"], 0.30)  # bonds pre-1985: ~30% of market-years in 1962-84 (A1, approx.)
    fi_B = strip(src["MOP_fig2_1985_2009"]["FI"], ov["MOP_fig2_1985_2009"]["FI_share"])
    fx_A = strip(src["HOP_ex4_1880_1984"]["FX"], ov["HOP_ex4_1880_1984"]["FX_share"])
    fx_B = strip(src["MOP_fig2_1985_2009"]["FX"], ov["MOP_fig2_1985_2009"]["FX_share"])
    w_fxA = (1 - ov["HOP_ex4_1880_1984"]["FX_share"]) * 14 * 6
    w_fxB = (1 - ov["MOP_fig2_1985_2009"]["FX_share"]) * 25 * 12
    # sampling SE of a class mean of N per-asset SRs over T years with mean pairwise TSMOM correlation rho
    # (MOP Table 4), inflated by 1/sqrt(1 - f) so that only the out-of-window years carry precision
    def se_class(T, N, rho, f):
        return math.sqrt((1 / T) * (1 + (N - 1) * rho) / N) / math.sqrt(1 - f)
    t4 = COPIED["MOP_t4"]
    se_fi_B = se_class(25, 13, t4["within_FI"], ov["MOP_fig2_1985_2009"]["FI_share"])
    se_fi_A = se_class(60, 10, t4["within_FI"], 0.30)  # ~60 market-years each before 1985 (A1, approximate)
    se_fx_B = se_class(25, 12, t4["within_FX"], ov["MOP_fig2_1985_2009"]["FX_share"])
    fi_c = (fi_A + fi_B) / 2
    fi_between = max(abs(fi_A - fi_B) / 2, 0.5 * math.sqrt(se_fi_A ** 2 + se_fi_B ** 2))
    fx_c = (w_fxA * fx_A + w_fxB * fx_B) / (w_fxA + w_fxB)
    fx_between = se_fx_B
    # pre-publication (data-mining) haircut: 26% (MP) on the share of the centre that comes from MOP's own sample
    h_fi, h_fx = 1 - 0.26 * 0.5, 1 - 0.26 * (w_fxB / (w_fxA + w_fxB))
    het_fi = heterogeneity(D["MOP_fig2_1985_2009"]["rows"][45:58], MOP_FI_YEARS)
    out["centre_construction"] = {
        "FI": {"HOP_pre1985_stripped": round(fi_A, 3), "MOP_stripped": round(fi_B, 3), "centre": round(fi_c, 3),
               "half_era_difference": round(abs(fi_A - fi_B) / 2, 3),
               "sampling_se_inflated": {"HOP_pre1985": round(se_fi_A, 3), "MOP": round(se_fi_B, 3)},
               "centre_sd_used": round(fi_between, 3), "oos_haircut": h_fi, "per_asset_hist": round(fi_c * h_fi, 3)},
        "FX": {"HOP_pre1985_stripped": round(fx_A, 3), "MOP_stripped": round(fx_B, 3),
               "weights": [round(w_fxA, 1), round(w_fxB, 1)], "centre": round(fx_c, 3),
               "centre_sd_used_sampling_se_inflated": round(fx_between, 3), "oos_haircut": round(h_fx, 3),
               "per_asset_hist": round(fx_c * h_fx, 3)},
        "FI_heterogeneity_MOP": {"true_sd": round(het_fi[0], 3), "observed_sd": round(het_fi[1], 3),
                                 "sampling_sd": round(het_fi[2], 3)},
    }

    # ---- decay evidence (post-publication) and forward factor
    imp = src["implied_2010_2017"]
    dec = {"MP_post_pub_ratio": round(1 - 0.58, 2), "MP_oos_ratio": round(1 - 0.26, 2),
           "trend_FI_2010_17_over_1985_09": round(imp["FI"] / src["MOP_fig2_1985_2009"]["FI"], 3),
           "trend_FX_2010_17_over_1985_09": round(imp["FX"] / src["MOP_fig2_1985_2009"]["FX"], 3),
           "HOP_ex2_2010_16_over_1980s_2000s": round(e2["2010_2016"] / st.mean([e2["1980s"], e2["1990s"],
                                                                                 e2["2000s"]]), 3)}
    fwd_f = st.mean([dec["MP_post_pub_ratio"], dec["trend_FI_2010_17_over_1985_09"],
                     dec["trend_FX_2010_17_over_1985_09"], dec["HOP_ex2_2010_16_over_1980s_2000s"]])
    dec["forward_factor_centre"] = round(fwd_f, 3)
    dec["forward_factor_sd"] = 0.10
    out["decay"] = dec

    # ---- cost in SR units per market: (2 x flips + 0.5) x one-way cost / vol; flips = 1.5 a year (assumption)
    turn = 2 * 1.5 + 0.5
    vol = COPIED["MOP_t1_vol"]
    c_pre = COPIED["HOP_B1_oneway_cost"]
    cost_r = {k: turn * c_pre["bonds"]["1880_1992"] / vol[k] for k in ("US2", "US5", "US10", "US30")}
    fx8 = ["JPY", "GBP", "CHF", "CAD", "AUD", "SEK", "NOK"]  # DKK not in MOP Table 1: use the mean of these 7
    cost_fx = {k: turn * c_pre["currencies"]["1880_1992"] / vol[k] for k in fx8}
    cost_fx["DKK"] = st.mean(cost_fx.values())
    cost_r_mod = {k: turn * c_pre["bonds"]["2003_2016"] / vol[k] for k in cost_r}
    cost_fx_mod = {k: turn * c_pre["currencies"]["2003_2016"] / vol[k] for k in fx8}
    out["cost_SR_units"] = {"turnover_multiple_assumed": turn,
                            "rates_pre1993": {k: round(v, 4) for k, v in cost_r.items()},
                            "fx_pre1993": {k: round(v, 4) for k, v in cost_fx.items()},
                            "rates_2003_on": {k: round(v, 4) for k, v in cost_r_mod.items()},
                            "fx_2003_on": {k: round(v, 4) for k, v in cost_fx_mod.items()}}

    # ---- Monte Carlo over the structural assumptions
    rng = np.random.default_rng(20261125)
    M = 20000
    res = {"single_US10_hist": [], "single_generic_hist": [], "sleeve_hist": [], "sleeve_fwd": [],
           "single_US10_fwd": []}
    mean_cr = st.mean(cost_r.values())
    mean_cfx = st.mean(cost_fx.values())
    for _ in range(M):
        fi = rng.normal(fi_c, fi_between)
        fx = rng.normal(fx_c, fx_between)
        hfi = rng.normal(h_fi, 0.07)
        hfx = rng.normal(h_fx, 0.07)
        rho_c = rng.normal(0.0, 0.15)
        rho_r = float(np.clip(rng.normal(0.7, 0.1), 0.3, 0.95))
        rho_fx = float(np.clip(rng.normal(0.35, 0.15), 0.0, 0.8))
        cm = rng.uniform(0.5, 2.0)  # cost multiplier on the assumed turnover
        het = rng.normal(0.0, het_fi[0])
        s_r, s_fx = fi * hfi, fx * hfx
        # single market, historical, net of pre-1993 costs
        res["single_US10_hist"].append(ar_vs_core(s_r + het - cm * cost_r["US10"], rho_c, sr_core))
        res["single_generic_hist"].append(ar_vs_core(s_r + het - cm * mean_cr, rho_c, sr_core))
        # sleeve over the proxy window, three regimes, time-weighted
        a = sleeve_sr(s_r, s_fx, 2, 0, rho_r, rho_fx, 0.05, cm * mean_cr, cm * mean_cfx)        # 1962-71
        b = sleeve_sr(s_r, s_fx, 4, 8, rho_r, rho_fx, 0.05, cm * mean_cr, cm * mean_cfx)        # 1972-89
        c = sleeve_sr(s_r, s_fx, 4, 0, rho_r, rho_fx, 0.05, cm * mean_cr / 3, cm * mean_cfx / 3)  # 1990-2002 (x2)
        res["sleeve_hist"].append(ar_vs_core((10 * a + 18 * b + 12.5 * c) / 40.5, rho_c, sr_core))
        # forward: MOP-era level x decay factor, 4 rates + 6 G10 FX futures, modern costs
        f = rng.normal(fwd_f, 0.10)
        sf_r = src["MOP_fig2_1985_2009"]["FI"] * f
        sf_fx = src["MOP_fig2_1985_2009"]["FX"] * f
        res["sleeve_fwd"].append(ar_vs_core(sleeve_sr(sf_r, sf_fx, 4, 6, rho_r, rho_fx, 0.05,
                                                      cm * st.mean(cost_r_mod.values()),
                                                      cm * st.mean(cost_fx_mod.values())), rho_c, sr_core))
        res["single_US10_fwd"].append(ar_vs_core(sf_r + het - cm * cost_r_mod["US10"], rho_c, sr_core))
    prior = {}
    for k, v in res.items():
        v = np.array(v)
        prior[k] = {"mean": round(float(v.mean()), 3), "sd": round(float(v.std()), 3),
                    "p05": round(float(np.quantile(v, 0.05)), 3), "p50": round(float(np.quantile(v, 0.5)), 3),
                    "p95": round(float(np.quantile(v, 0.95)), 3), "P_gt_0": round(float((v > 0).mean()), 3)}
    out["prior_AR_vs_core"] = prior

    # ---- literature value (no haircut, gross, rho = 0) for the rule-3 reading 'delta = 1/2 x literature value'
    lit_single = src["MOP_fig2_1985_2009"]["FI"]
    lit_sleeve = sleeve_sr(src["MOP_fig2_1985_2009"]["FI"], src["MOP_fig2_1985_2009"]["FX"], 4, 8, 0.7, 0.35, 0.05)
    deltas = {"half_literature_single": lit_single / 2, "half_literature_sleeve": lit_sleeve / 2,
              "prior_centre_single_US10": prior["single_US10_hist"]["mean"],
              "prior_centre_sleeve": prior["sleeve_hist"]["mean"]}
    pw = {}
    for name, d in deltas.items():
        pw[name] = {"delta": round(d, 3)}
        for T in (30.5, 40.5):
            for zname, z in (("z_0.05", norm.ppf(0.95)), ("z_0.10/40", norm.ppf(1 - 0.10 / 40)),
                             ("z_0.10/60", norm.ppf(1 - 0.10 / 60))):
                pw[name][f"P_T{T}_{zname}"] = round(power(d, T, z), 3)
    out["literature_value_gross_rho0"] = {"single_FI_mean_MOP": lit_single, "sleeve_MOP_level": round(lit_sleeve, 3)}
    out["power_rule3_Lo_iid"] = pw

    # ---- proxy precision and the combination rule (illustration of the formula, no proxy result exists)
    T = 40.5
    se_proxy = math.sqrt((1 + prior["sleeve_hist"]["mean"] ** 2 / 2) / T)
    out["combination"] = {
        "proxy_SE_Lo_iid_T40.5_at_prior_centre": round(se_proxy, 3),
        "prior_sd_sleeve_hist": prior["sleeve_hist"]["sd"],
        "weight_on_proxy_if_combined": round((1 / se_proxy ** 2) / (1 / se_proxy ** 2 + 1 / prior["sleeve_hist"]["sd"] ** 2), 3),
    }
    json.dump(out, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
