"""Descriptive verification of E2 (core excess over 1x held in a 2x daily-reset S&P fund) before any deployment.

    python research/sharpe/verify_e2.py     # writes research/sharpe/VERIFY_E2.json

Not a hypothesis test: every sample here was already seen by research/sharpe/capital.py (READ_CAPITAL.lock).
Nothing is tuned; spreads and margin spreads are scenario grids, reported side by side.

Inputs:
* frozen by capital.py (sha256 checked against .cache/capital/MANIFEST.json and the ledger's git blob):
  SPY.csv, SSO.csv, weekly_b0_ledger.csv; the French daily file and FRED DTB3 (sha256 recorded here);
* new, frozen at first fetch here (.cache/e2verify/MANIFEST.json): SPY, SSO, UPRO daily OHLCV from yfinance,
  used for UPRO returns and for SSO/SPY dollar volume only.
"""
import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import capital as CP                                            # noqa: E402

CAP = os.path.join(ROOT, ".cache", "capital")
NEW = os.path.join(ROOT, ".cache", "e2verify")
DTB3 = os.path.join(os.path.dirname(ROOT), "quant-tf", ".cache", "quant_trials", "dtb3.csv")
OUT = os.path.join(HERE, "VERIFY_E2.json")
LEDGER_BLOB = "2313f28e85f973152094f423df16d5f492531b56"
END = "2026-11-20"                         # last close in the frozen SPY/SSO files
UP = 1.3

WINDOWS = {
    "2008-09..2009-03 financial crisis": ("2008-09-01", "2009-03-31"),
    "2010-05 flash crash month": ("2010-05-01", "2010-05-31"),
    "2011-08 US downgrade": ("2011-08-01", "2011-08-31"),
    "2015-08 China devaluation": ("2015-08-01", "2015-08-31"),
    "2018-02 Volmageddon": ("2018-02-01", "2018-02-28"),
    "2018-Q4": ("2018-10-01", "2018-12-31"),
    "2020-02-19..2020-04-30 COVID": ("2020-02-19", "2020-04-30"),
    "2022 rate shock": ("2022-01-01", "2022-12-31"),
}
SPREAD_GRID = [0.010, 0.015, 0.0243, 0.030]                 # margin spread over the T-bill
SSO_SPREAD_BP = [1, 2, 5, 10, 20]                           # full quoted spread scenarios
SPY_SPREAD_BP = 0.2                                         # about one tick on a ~$500-660 SPY
EXTERNAL = {
    "SSO_proshares": {"url": "https://www.proshares.com/our-etfs/leveraged-and-inverse/sso", "access": "read-directly "
                      "(fetched 2026-11-24; page text summarised by the fetch tool)", "30-Day Median Bid Ask Spread":
                      "0.01% (as of 11/23/2026)", "Trading Volume": "8,811,534 shares (11/23/2026)",
                      "Net Assets": "$6,355,203,208", "Gross Expense Ratio": "0.88%",
                      "Net Expense Ratio": "0.84% (contractual waiver through 2027-09-30)",
                      "NAV": "$61.11", "Market Price": "$61.15 (11/23/2026)"},
    "UPRO_proshares": {"url": "https://www.proshares.com/our-etfs/leveraged-and-inverse/upro", "access": "read-directly "
                       "(fetched 2026-11-24; page text summarised by the fetch tool)", "30-Day Median Bid Ask Spread":
                       "0.03% (as of 11/23/2026)", "Trading Volume": "4,670,531 shares (11/23/2026)",
                       "Net Assets": "$4,591,703,318", "Gross/Net Expense Ratio": "0.88% / 0.88% (as shown)",
                       "NAV": "$119.58", "Market Price": "$119.74 (11/23/2026)"},
    "alpaca_margin_rate": {"url": "https://docs.alpaca.markets/docs/margin-and-short-selling", "access":
                           "search-summary (not opened)", "value": "5.00%/yr elite, 6.50%/yr non-elite, flat (not "
                           "T-bill-linked); another Alpaca page shows 6.25% as of 2025-11-04; interest on end-of-day "
                           "debit / 360"},
    "finra_leveraged_etf_maintenance": {"url": "https://www.finra.org/rules-guidance/notices/09-53", "access":
                                        "search-summary (not opened)", "value": "maintenance margin on leveraged "
                                        "ETFs = standard requirement x leverage factor (2x long: 50%; 3x long: 75%)"},
    "ibkr_margin_rates": {"url": "https://www.interactivebrokers.com/en/trading/margin-rates.php",
                          "access": "did not load (HTTP 403)"},
}
LOW_RATE = 0.005                                            # T-bill below 0.5 %/yr = "near zero"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


# ---------------------------------------------------------------- inputs
def check_frozen():
    man = json.load(open(os.path.join(CAP, "MANIFEST.json")))
    for t in ("SPY", "SSO"):
        got = sha(os.path.join(CAP, f"{t}.csv"))
        if got != man[t]["sha256"]:
            raise RuntimeError(f"STOP: {t}.csv sha256 {got} != manifest {man[t]['sha256']}")
    blob = subprocess.run(["git", "hash-object", os.path.join(CAP, "weekly_b0_ledger.csv")],
                          capture_output=True, text=True, check=True).stdout.strip()
    if blob != LEDGER_BLOB:
        raise RuntimeError(f"STOP: ledger blob {blob} != {LEDGER_BLOB}")
    return {"SPY.csv": man["SPY"]["sha256"], "SSO.csv": man["SSO"]["sha256"], "ledger_git_blob": blob,
            "french_daily_sha256": sha(CP.FF), "dtb3_sha256": sha(DTB3)}


def fetch_new():
    """SPY, SSO, UPRO OHLCV from yfinance, frozen with sha256 at first fetch, verified thereafter."""
    os.makedirs(NEW, exist_ok=True)
    mp = os.path.join(NEW, "MANIFEST.json")
    man = json.load(open(mp)) if os.path.exists(mp) else {}
    for t in ("SPY", "SSO", "UPRO"):
        p = os.path.join(NEW, f"{t}.csv")
        if t not in man:
            import yfinance as yf
            d = yf.download(t, start="2006-01-01", end="2026-11-24", auto_adjust=False, progress=False,
                            actions=False)
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            d = d[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].dropna()
            d.index.name = "Date"
            d.to_csv(p)
            man[t] = {"rows": len(d), "first": str(d.index[0].date()), "last": str(d.index[-1].date()),
                      "sha256": sha(p), "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "source": "yfinance 1.3.0, auto_adjust=False"}
            json.dump(man, open(mp, "w"), indent=1)
        elif sha(p) != man[t]["sha256"]:
            raise RuntimeError(f"STOP: {p} changed since first fetch")
    return man, {t: pd.read_csv(os.path.join(NEW, f"{t}.csv"), index_col=0, parse_dates=True)
                 for t in ("SPY", "SSO", "UPRO")}


def rf_daily(idx):
    s = pd.read_csv(DTB3, parse_dates=["date"]).set_index("date")["v"] / 100
    return s.reindex(s.index.union(idx)).ffill().shift(1).reindex(idx) / 252, \
        s.reindex(s.index.union(idx)).ffill().shift(1).reindex(idx)


def load_real(new):
    spy, sso = CP.adj("SPY"), CP.adj("SSO")
    upro = new["UPRO"]["Adj Close"].astype(float)
    upro = upro[upro.index <= END]
    # the new SPY/SSO download must give the same daily returns as the frozen files (adjustments may rescale)
    chk = {}
    for t, old in (("SPY", spy), ("SSO", sso)):
        a = new[t]["Adj Close"].astype(float).pct_change()
        b = old.pct_change()
        j = a.index.intersection(b.index)
        d = (a.loc[j] - b.loc[j]).abs().dropna()
        chk[t] = {"days": int(len(d)), "share_within_1bp": float((d <= 1e-4).mean()), "max_gap_bp": float(1e4 * d.max())}
    return spy, sso, upro, chk


# ---------------------------------------------------------------- Q1 tracking
def tracking_block(te, windows=True):
    def one(x):
        if len(x) < 2:
            return None
        return {"days": int(len(x)), "drag_pct_per_year": float(-252 * 100 * x.mean()),
                "drag_pct_over_period": float(-100 * x.sum()),
                "tracking_sd_pct_per_year": float(100 * x.std(ddof=1) * math.sqrt(252)),
                "worst_day_bp": float(1e4 * x.min()), "worst_day": str(x.idxmin().date()),
                "best_day_bp": float(1e4 * x.max())}
    res = {"all": one(te), "by_year": {int(y): one(g) for y, g in te.groupby(te.index.year)}}
    if windows:
        res["windows"] = {k: one(te.loc[a:b]) for k, (a, b) in WINDOWS.items()}
    return res


# ---------------------------------------------------------------- daily-constant-weight arms on sample (b)
def daily_arms(rs, r2, r3, rfd, e, spread):
    """As capital.arms_daily (cash earns the T-bill), plus E3 = 0.85 SPY + 0.15 UPRO in up-trends."""
    sw = CP.SWITCH * e.diff().abs().fillna(0)
    debit, cash = (e - 1).clip(lower=0), (1 - e).clip(lower=0)
    M = e * rs - debit * (rfd + spread / 252) + cash * rfd - sw
    b = (e - 1).clip(lower=0)
    a = e - 2 * b
    E2 = a * rs + b * r2 + (1 - a - b) * rfd - sw
    out = {"M": M, "E2": E2}
    if r3 is not None:
        b3 = (e - 1).clip(lower=0) / 2
        a3 = e - 3 * b3
        out["E3"] = a3 * rs + b3 * r3 + (1 - a3 - b3) * rfd - sw
    return out


def diff_stats(d, per_year):
    mu, se = CP.hac_mean(d.values if hasattr(d, "values") else d)
    return {"mean_pct_per_year": per_year * 100 * mu, "hac_se_pct_per_year": per_year * 100 * se, "n": int(len(d))}


def window_compare(arms, e):
    res = {}
    for k, (a, b) in WINDOWS.items():
        sl = {n: x.loc[a:b] for n, x in arms.items()}
        if len(sl["M"]) == 0:
            continue
        cm = float(np.prod(1 + sl["M"].values) - 1)
        row = {"days": int(len(sl["M"])), "share_days_at_1.3": float((e.loc[a:b] > 1).mean()),
               "M_pct_over_window": 100 * cm}
        for n in ("E2", "E3"):
            if n in sl and sl[n].notna().all() and len(sl[n]):
                cn = float(np.prod(1 + sl[n].values) - 1)
                row[f"{n}_pct_over_window"] = 100 * cn
                row[f"{n}_minus_M_pct_over_window"] = 100 * (cn - cm)
        res[k] = row
    return res


# ---------------------------------------------------------------- weekly-rebalanced simulation on sample (b)
def weekly_sim(spy, rs, r2, r3, rfd, spread, start):
    """Thursday decision on SPY's own 200-session trend; trade at the next session's close; buy and hold to the next
    trade. Every leg drifts within the week (the SSO/UPRO daily reset is in their returns). Margin debt accrues at
    T-bill + spread; cash earns the T-bill. Returns per-period returns and per-instrument turnover (no costs)."""
    lvl = (1 + spy.pct_change()).cumprod()
    ma = lvl.rolling(CP.TREND, min_periods=CP.TREND).mean()
    S = rs.index[rs.index >= start]
    if r3 is not None:
        S = S[r3.reindex(S).notna().values]
    pos = {s: i for i, s in enumerate(S)}
    th = [i for i, s in enumerate(S) if s.weekday() == 3 and i + 1 < len(S) and ma.get(s) == ma.get(s)]
    rsv, r2v, rfv = rs.reindex(S).values, r2.reindex(S).values, rfd.reindex(S).values
    r3v = r3.reindex(S).values if r3 is not None else None
    arms = ["M", "E2"] + (["E3"] if r3 is not None else [])
    prev = {a: None for a in arms}
    rows = []
    for k in range(len(th) - 1):
        t, t2 = th[k], th[k + 1]
        if t2 + 1 >= len(S):
            break
        e = UP if lvl[S[t]] > ma[S[t]] else 0.7
        days = range(t + 2, t2 + 2)
        row = {"decision": S[t], "trade": S[t + 1], "e": e,
               "spy_ret": float(np.prod(1 + rsv[t + 2:t2 + 2]) - 1)}
        for arm in arms:
            # target weights: spy, lev, cash (cash < 0 = margin debt)
            if arm == "M":
                w = {"spy": e, "lev": 0.0, "cash": 1 - e}
            elif arm == "E2":
                b = max(e - 1, 0)
                w = {"spy": e - 2 * b, "lev": b, "cash": 1 - (e - 2 * b) - b}
            else:
                b = max(e - 1, 0) / 2
                w = {"spy": e - 3 * b, "lev": b, "cash": 1 - (e - 3 * b) - b}
            # turnover against the drifted weights from the previous period
            if prev[arm] is None:
                to_spy, to_lev = abs(w["spy"]), abs(w["lev"])
            else:
                to_spy, to_lev = abs(w["spy"] - prev[arm]["spy"]), abs(w["lev"] - prev[arm]["lev"])
            v = dict(w)
            for i in days:
                rl = r2v[i] if arm == "E2" else (r3v[i] if arm == "E3" else 0.0)
                v["spy"] *= 1 + rsv[i]
                v["lev"] *= 1 + rl
                v["cash"] *= 1 + rfv[i] + (spread / 252 if v["cash"] < 0 else 0)
            nav = v["spy"] + v["lev"] + v["cash"]
            prev[arm] = {x: v[x] / nav for x in v}
            row[f"{arm}_ret"] = nav - 1
            row[f"{arm}_to_spy"], row[f"{arm}_to_lev"] = to_spy, to_lev
        row["switch_cost_units"] = 0.0 if k == 0 else abs(e - rows[-1]["e"])
        rows.append(row)
    W = pd.DataFrame(rows).set_index("trade")
    for arm in arms:      # the 2 bp per unit of exposure switched, as capital.py, applied identically
        W[f"{arm}_ret"] -= CP.SWITCH * W["switch_cost_units"]
    return W


def weekly_summary(W, arms, years):
    res = {"weeks": int(len(W)), "years": years, "share_weeks_at_1.3": float((W.e > 1).mean())}
    for arm in arms:
        x = W[f"{arm}_ret"]
        res[arm] = {"pct_per_year_arith": float(100 * x.sum() / years),
                    "cagr_pct": float(100 * ((1 + x).prod() ** (1 / years) - 1)),
                    "worst_week_pct": float(100 * x.min()), "worst_week": str(x.idxmin().date()),
                    "turnover_spy_per_year": float(W[f"{arm}_to_spy"].sum() / years),
                    "turnover_lev_per_year": float(W[f"{arm}_to_lev"].sum() / years)}
        if arm != "M":
            d = x - W["M_ret"]
            mu, se = CP.hac_mean(d.values)
            res[arm]["minus_M_pct_per_year"] = float(100 * d.sum() / years)
            res[arm]["minus_M_hac_se_pct_per_year"] = float(100 * se * len(d) / years)
            worst = d.nsmallest(5)
            res[arm]["worst_weeks_vs_M"] = [{"trade": str(i.date()), "e": float(W.e[i]),
                                             "diff_bp": float(1e4 * v),
                                             "spy_week_pct": float(100 * W.spy_ret[i])} for i, v in worst.items()]
            res[arm]["best_weeks_vs_M"] = [{"trade": str(i.date()), "diff_bp": float(1e4 * v)}
                                            for i, v in d.nlargest(3).items()]
    return res


def cost_table(res, arms):
    """Extra trading cost vs margin at half the quoted spread, and the break-even full spread of the lev fund."""
    out = {}
    tm = res["M"]["turnover_spy_per_year"]
    for arm in arms:
        if arm == "M":
            continue
        ts, tl = res[arm]["turnover_spy_per_year"], res[arm]["turnover_lev_per_year"]
        extra_spy = (ts - tm) * SPY_SPREAD_BP / 2 / 1e4
        row = {"lev_turnover_per_year": tl, "spy_turnover_per_year": ts, "M_spy_turnover_per_year": tm,
               "extra_spy_cost_pct_per_year": 100 * extra_spy,
               "cost_pct_per_year_at_full_spread_bp": {str(s): 100 * (extra_spy + tl * s / 2 / 1e4) for s in SSO_SPREAD_BP}}
        adv = res[arm]["minus_M_pct_per_year"] / 100
        row["break_even_full_spread_bp"] = float(2 * 1e4 * (adv - extra_spy) / tl) if tl > 0 else None
        out[arm] = row
    return out


# ---------------------------------------------------------------- ledger (c), with E3 and a margin-spread knob
def ledger_period(L, px):
    cal = px.index
    out = []
    for d, days in zip(pd.to_datetime(L.date), L.days):
        start = cal[cal > d][0]
        end = start + pd.Timedelta(days=int(days))
        out.append(px[end] / px[start] - 1)
    return np.array(out)


def ledger_arms(L, rm, r2, r3, spread):
    s, w_spy, ss = L.core_spy.values, L.book_spy_hedge.values, L.sum_stock.values
    rf, days = L.risk_free_rate.values, L.days.values.astype(float)
    rate = rf + spread
    book, ccost = L.book_net_return.values, L.core_turnover_cost.values
    spy_short = np.maximum(-s - w_spy, 0)
    st_short = L.short_sale_nav.values - spy_short
    st_long = ss + st_short
    f = days / 360

    def fin(lmv, smv, ret, conv):
        debit = np.maximum(lmv - smv - 1, 0) if conv == "net" else np.maximum(lmv - 1, 0)
        credit = np.maximum(1 - (lmv - smv), 0) if conv == "net" else np.maximum(1 - lmv, 0)
        return ret - debit * rate * f + credit * rf * f
    out, pos = {}, {}
    for conv in ("net", "seg"):
        sp = s + w_spy
        out[("M", conv)] = fin(np.maximum(sp, 0) + st_long, np.maximum(-sp, 0) + st_short, s * rm - ccost + book, conv)
        for arm, k, rl in (("E2", 2, r2), ("E3", 3, r3)):
            b = np.maximum(s - 1, 0) / (k - 1)
            a = s - k * b
            sp = a + w_spy
            out[(arm, conv)] = fin(b + np.maximum(sp, 0) + st_long, np.maximum(-sp, 0) + st_short,
                                   a * rm + b * rl - ccost + book, conv)
            pos[arm] = (a, b)
    pos["M"] = (s, np.zeros_like(s))
    return out, pos


def ledger_turnover(L, out, pos, rm, rl_by_arm):
    """Weekly turnover of the core's SPY and lev-fund legs against weights drifted by the period's returns
    (the hedge and stock book are unchanged across arms and not counted)."""
    years = L.days.sum() / 365.25
    res = {}
    for arm in ("M", "E2", "E3"):
        a, b = pos[arm]
        nav = 1 + out[(arm, "net")]
        rl = rl_by_arm.get(arm, np.zeros_like(rm))
        pa = np.r_[a[0], a[:-1] * (1 + rm[:-1]) / nav[:-1]]
        pb = np.r_[b[0], b[:-1] * (1 + rl[:-1]) / nav[:-1]]
        ta, tb = np.abs(a - pa), np.abs(b - pb)
        ta[0] = tb[0] = 0
        res[arm] = {"turnover_spy_per_year": float(ta.sum() / years), "turnover_lev_per_year": float(tb.sum() / years)}
    return res, years


def main():
    frozen = check_frozen()
    man, new = fetch_new()
    spy, sso, upro, newchk = load_real(new)
    res = {"what_this_is": "descriptive verification on samples already seen by capital.py; not a hypothesis "
                           "test; nothing tuned", "inputs": {"frozen_by_capital": frozen, "new_downloads": man,
                                                              "new_vs_frozen_daily_returns": newchk},
           "assumptions": {"capital_ER2x": CP.ER2, "capital_s": CP.S2, "capital_ER1x": CP.ER1,
                           "capital_margin_spread": CP.SPREAD, "switch_cost_per_unit": CP.SWITCH,
                           "spy_full_spread_bp": SPY_SPREAD_BP, "sso_full_spread_bp_grid": SSO_SPREAD_BP,
                           "margin_spread_grid": SPREAD_GRID, "low_rate_threshold": LOW_RATE}}

    # ---------------- Q1 tracking (from SSO's first full month)
    idx = sso.index[(sso.index >= "2006-07-01") & (sso.index <= END)]
    rs_all, r2_all = spy.pct_change().reindex(idx), sso.pct_change().reindex(idx)
    rfd_all, rfa_all = rf_daily(idx)
    te2 = (r2_all - (2 * rs_all - rfd_all)).dropna()
    res["q1_sso_tracking"] = tracking_block(te2)
    res["q1_sso_tracking"]["definition"] = "r_SSO - (2 r_SPY - rf_d); drag = -mean; SPY is net of its 0.0945% fee"
    res["q1_sso_tracking"]["capital_assumed_drag_pct"] = 100 * (CP.ER2 + CP.S2 - 2 * CP.ER1)

    # ---------------- sample (b): daily constant weights, as capital.py
    e_all = CP.core_path(spy.pct_change().dropna())
    r3_all = upro.pct_change()
    e = e_all.reindex(idx).dropna()
    ok = e.index[rs_all.loc[e.index].notna() & r2_all.loc[e.index].notna() & rfd_all.loc[e.index].notna()]
    e, rs, r2, rfd, rfa = e.loc[ok], rs_all.loc[ok], r2_all.loc[ok], rfd_all.loc[ok], rfa_all.loc[ok]
    r3 = r3_all.reindex(ok)
    arms = daily_arms(rs, r2, r3, rfd, e, CP.SPREAD)
    # reproduce capital.py (b): E2 - M (R) = +0.2352 %/yr
    rep = diff_stats(arms["E2"] - arms["M"], 252)
    res["b_reproduction"] = {"E2_minus_M": rep, "capital_reported": 0.23519396612533744,
                             "period": [str(ok[0].date()), str(ok[-1].date())]}
    if abs(rep["mean_pct_per_year"] - 0.23519396612533744) > 1e-6:
        raise RuntimeError("STOP: sample (b) does not reproduce capital.py")
    res["q1_window_E2_vs_M_daily_weights"] = window_compare(arms, e)

    # ---------------- Q2 path and gap risk
    up = e > 1
    p_e2 = 0.7 * rs + 0.3 * r2
    p_m = 1.3 * rs - 0.3 * (rfd + CP.SPREAD / 252)
    p_e3 = 0.85 * rs + 0.15 * r3
    d = (p_e2 - p_m)
    q2 = {"note": "one day held at 1.3 (start-of-day weights), every day of sample (b) and only the days the core "
                  "was at 1.3; close-to-close only, intraday risk not modelled"}
    for lab, mask in (("all_days_if_at_1.3", pd.Series(True, index=rs.index)), ("days_core_at_1.3", up)):
        q2[lab] = {"worst_day_E2_pct": float(100 * p_e2[mask].min()), "worst_day_E2": str(p_e2[mask].idxmin().date()),
                   "worst_day_M_pct": float(100 * p_m[mask].min()), "worst_day_M": str(p_m[mask].idxmin().date()),
                   "worst_day_E3_pct": float(100 * p_e3[mask].dropna().min()),
                   "worst_day_E3": str(p_e3[mask].dropna().idxmin().date()),
                   "E2_minus_M_worst5_bp": [{"date": str(i.date()), "bp": float(1e4 * v),
                                             "spy_pct": float(100 * rs[i])} for i, v in d[mask].nsmallest(5).items()],
                   "E2_minus_M_days_below_-10bp": int((d[mask] < -0.001).sum()),
                   "E2_minus_M_days_below_-25bp": int((d[mask] < -0.0025).sum()),
                   "days": int(mask.sum())}
    # French 1927-2026: the worst index day, and the one-day index loss that would wipe out the 2x / 3x fund
    rfr, _ = CP.french()
    q2["french_worst_day"] = {"date": str(rfr.idxmin().date()), "index_pct": float(100 * rfr.min()),
                              "2x_fund_pct_model": float(100 * 2 * rfr.min()), "3x_fund_pct_model": float(100 * 3 * rfr.min())}
    q2["wipeout_index_move_pct"] = {"SSO": -50.0, "UPRO": -33.3}
    res["q2_path_gap"] = q2

    # ---------------- weekly-rebalanced simulation, (b) and the UPRO common sample
    years_b = (ok[-1] - ok[0]).days / 365.25
    Wb = weekly_sim(spy, rs, r2, None, rfd, CP.SPREAD, ok[0])
    yb = (Wb.index[-1] - Wb.index[0]).days / 365.25
    wb = weekly_summary(Wb, ["M", "E2"], yb)
    wb["costs"] = cost_table(wb, ["M", "E2"])
    wb["period"] = [str(Wb.index[0].date()), str(Wb.index[-1].date())]
    res["weekly_rebalanced_b"] = wb
    u0 = r3.dropna().index[0]
    Wu = weekly_sim(spy, rs, r2, r3, rfd, CP.SPREAD, u0)
    yu = (Wu.index[-1] - Wu.index[0]).days / 365.25
    wu = weekly_summary(Wu, ["M", "E2", "E3"], yu)
    wu["costs"] = cost_table(wu, ["M", "E2", "E3"])
    wu["period"] = [str(Wu.index[0].date()), str(Wu.index[-1].date())]
    res["weekly_rebalanced_upro_sample"] = wu

    # weekly windows (E2 - M, % over the window, compounded)
    res["q1_window_E2_vs_M_weekly_rebalanced"] = {}
    for k, (a, b) in WINDOWS.items():
        sl = Wb.loc[a:b]
        if len(sl) == 0:
            continue
        cm, c2 = (1 + sl.M_ret).prod() - 1, (1 + sl.E2_ret).prod() - 1
        res["q1_window_E2_vs_M_weekly_rebalanced"][k] = {"weeks": int(len(sl)), "share_weeks_at_1.3": float((sl.e > 1).mean()),
                                                         "M_pct": float(100 * cm), "E2_pct": float(100 * c2),
                                                         "E2_minus_M_pct": float(100 * (c2 - cm))}

    # ---------------- Q4 financing: margin spread grid x rate regime, daily weights (b) and weekly (b)
    q4 = {"daily_weights_b": {}, "weekly_rebalanced_b": {}}
    low = rfa < LOW_RATE
    named = {"2006-10..2008-12": ("2006-10-01", "2008-12-31"), "2009-2015 zero rates": ("2009-01-01", "2015-12-31"),
             "2016-2019": ("2016-01-01", "2019-12-31"), "2020-03..2022-03 zero rates": ("2020-03-16", "2022-03-16"),
             "2022-03..2026-11": ("2022-03-17", END)}
    for sp in SPREAD_GRID:
        A = daily_arms(rs, r2, None, rfd, e, sp)
        dd = A["E2"] - A["M"]
        row = {"all": diff_stats(dd, 252), "T-bill < 0.5%": diff_stats(dd[low], 252),
               "T-bill >= 0.5%": diff_stats(dd[~low], 252)}
        for k, (a, b) in named.items():
            row[k] = diff_stats(dd.loc[a:b], 252)
            row[k]["share_days_at_1.3"] = float((e.loc[a:b] > 1).mean())
            row[k]["mean_tbill_pct"] = float(100 * rfa.loc[a:b].mean())
        q4["daily_weights_b"][str(sp)] = row
        W = weekly_sim(spy, rs, r2, None, rfd, sp, ok[0])
        dw = W.E2_ret - W.M_ret
        lw = rfa.reindex(W.index) < LOW_RATE
        yrs = lambda s: (len(s) * 7.0) / 365.25 if len(s) else float("nan")      # noqa: E731
        q4["weekly_rebalanced_b"][str(sp)] = {
            "all_pct_per_year": float(100 * dw.sum() / yb),
            "T-bill < 0.5%_pct_per_year": float(100 * dw[lw].sum() / yrs(dw[lw])),
            "T-bill >= 0.5%_pct_per_year": float(100 * dw[~lw].sum() / yrs(dw[~lw])),
            "weeks_low": int(lw.sum()), "weeks_high": int((~lw).sum())}
    # break-even margin spread (daily weights; the difference is linear in the spread)
    d0 = q4["daily_weights_b"][str(SPREAD_GRID[0])]
    d1 = q4["daily_weights_b"][str(SPREAD_GRID[-1])]
    be = {}
    for k in ["all", "T-bill < 0.5%", "T-bill >= 0.5%"] + list(named):
        y0, y1 = d0[k]["mean_pct_per_year"], d1[k]["mean_pct_per_year"]
        slope = (y1 - y0) / (SPREAD_GRID[-1] - SPREAD_GRID[0])
        be[k] = float(100 * (SPREAD_GRID[0] - y0 / slope)) if slope else None
    q4["break_even_margin_spread_pct_daily_weights_b"] = be
    # implied SSO drag by regime (vs 2 x SPY - T-bill)
    q4["sso_drag_by_regime_pct_per_year"] = {
        "T-bill < 0.5%": float(-252 * 100 * te2[rfa_all.reindex(te2.index) < LOW_RATE].mean()),
        "T-bill >= 0.5%": float(-252 * 100 * te2[rfa_all.reindex(te2.index) >= LOW_RATE].mean())}
    res["q4_financing"] = q4

    # ---------------- ledger (c): reproduce capital, margin-spread grid, regimes, E3, turnover
    L = CP.ledger()
    rm_l = ledger_period(L, spy)
    r2_l, r3_l = ledger_period(L, sso), ledger_period(L, upro)
    days = L.days.values.astype(float)
    c = {}
    for sp in SPREAD_GRID:
        out, pos = ledger_arms(L, rm_l, r2_l, r3_l, sp)
        row = {}
        for arm in ("E2", "E3"):
            for conv in ("net", "seg"):
                dd = 7 * (out[(arm, conv)] - out[("M", conv)]) / days
                lowc = L.risk_free_rate.values < LOW_RATE
                row[f"{arm}_{conv}_R"] = {"all": diff_stats(dd, 52), "T-bill < 0.5%": diff_stats(dd[lowc], 52),
                                          "T-bill >= 0.5%": diff_stats(dd[~lowc], 52)}
        c[str(sp)] = row
        if sp == 0.0243:
            rep_c = row["E2_net_R"]["all"]["mean_pct_per_year"]
            if abs(rep_c - 0.25304467804716824) > 1e-3:
                raise RuntimeError(f"STOP: ledger E2 net R {rep_c} does not reproduce capital.py +0.2530")
            to, yl = ledger_turnover(L, out, pos, rm_l, {"E2": r2_l, "E3": r3_l})
            gross = {}
            for arm in ("M", "E2", "E3"):
                x = out[(arm, "net")]
                nav = np.cumprod(1 + x)
                gross[arm] = {"cagr_pct": float(100 * (nav[-1] ** (365.25 / days.sum()) - 1)),
                              "worst_week_pct": float(100 * x.min()),
                              "worst_52w_pct": float(100 * pd.Series(nav).pct_change(52).min())}
            costs = {}
            for arm in ("E2", "E3"):
                tl = to[arm]["turnover_lev_per_year"]
                extra_spy = (to[arm]["turnover_spy_per_year"] - to["M"]["turnover_spy_per_year"]) * SPY_SPREAD_BP / 2 / 1e4
                adv = row[f"{arm}_net_R"]["all"]["mean_pct_per_year"] / 100
                costs[arm] = {"cost_pct_per_year_at_full_spread_bp": {str(s): 100 * (extra_spy + tl * s / 2 / 1e4)
                                                                      for s in SSO_SPREAD_BP},
                              "extra_spy_cost_pct_per_year": 100 * extra_spy,
                              "break_even_full_spread_bp": float(2 * 1e4 * (adv - extra_spy) / tl)}
            c["turnover_2.43"] = to
            c["costs_2.43"] = costs
            c["levels_net_R_2.43"] = gross
            # window differences on the ledger
            dates = pd.to_datetime(L.date)
            wl = {}
            for k, (a, b) in WINDOWS.items():
                m = ((dates >= a) & (dates <= b)).values
                if m.sum() == 0:
                    continue
                cm = np.prod(1 + out[("M", "net")][m]) - 1
                wl[k] = {"weeks": int(m.sum()), "share_weeks_at_1.3": float((L.core_spy.values[m] > 1).mean())}
                for arm in ("E2", "E3"):
                    wl[k][f"{arm}_minus_M_pct"] = float(100 * (np.prod(1 + out[(arm, "net")][m]) - 1 - cm))
            c["windows_net_R_2.43"] = wl
    c["weeks_T-bill_below_0.5"] = int((L.risk_free_rate.values < LOW_RATE).sum())
    lo, hi = str(SPREAD_GRID[0]), str(SPREAD_GRID[-1])
    c["break_even_margin_spread_pct"] = {}
    for arm in ("E2_net_R", "E2_seg_R", "E3_net_R"):
        for k in ("all", "T-bill < 0.5%", "T-bill >= 0.5%"):
            y0, y1 = c[lo][arm][k]["mean_pct_per_year"], c[hi][arm][k]["mean_pct_per_year"]
            slope = (y1 - y0) / (SPREAD_GRID[-1] - SPREAD_GRID[0])
            c["break_even_margin_spread_pct"][f"{arm} {k}"] = float(100 * (SPREAD_GRID[0] - y0 / slope))
    res["c_fund_2020_2025"] = c

    # ---------------- Q5 UPRO tracking
    j = r3_all.dropna().index.intersection(idx)
    te3 = (r3_all.loc[j] - (3 * rs_all.loc[j] - 2 * rfd_all.loc[j])).dropna()
    res["q5_upro_tracking"] = tracking_block(te3)
    res["q5_upro_tracking"]["definition"] = "r_UPRO - (3 r_SPY - 2 rf_d)"
    te2u = te2.loc[te2.index >= te3.index[0]]
    res["q5_upro_tracking"]["sso_on_same_days"] = tracking_block(te2u, windows=False)["all"]
    # daily weights on the UPRO common sample
    k3 = r3.notna()
    A = {n: x[k3] for n, x in arms.items()}
    res["q5_daily_weights_upro_sample"] = {"period": [str(r3[k3].index[0].date()), str(r3[k3].index[-1].date())],
                                           "E2_minus_M": diff_stats(A["E2"] - A["M"], 252),
                                           "E3_minus_M": diff_stats(A["E3"] - A["M"], 252),
                                           "E3_minus_E2": diff_stats(A["E3"] - A["E2"], 252)}
    res["q5_window_daily_weights"] = window_compare(A, e[k3])

    # ---------------- liquidity: dollar volume (yfinance volume x unadjusted close)
    liq = {}
    for t in ("SPY", "SSO", "UPRO"):
        d = new[t]
        dv = (d["Volume"] * d["Close"]).iloc[-63:]
        liq[t] = {"median_dollar_volume_63d_musd": float(dv.median() / 1e6), "mean_dollar_volume_63d_musd": float(dv.mean() / 1e6),
                  "median_shares_63d": float(d["Volume"].iloc[-63:].median()), "last_close": float(d["Close"].iloc[-1]),
                  "window": [str(d.index[-63].date()), str(d.index[-1].date())],
                  "one_cent_spread_bp_at_last_close": float(1e4 * 0.01 / d["Close"].iloc[-1])}
    res["liquidity_yfinance"] = liq
    res["external_sources"] = EXTERNAL
    res["run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
