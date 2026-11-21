"""Capital-efficient core, overlay sizing inputs and fund volatility scale (research/sharpe/PREREG_CAPITAL.md).

    python research/sharpe/capital.py      # writes research/sharpe/RESULT_CAPITAL.json once (READ_CAPITAL.lock)

Inputs (frozen; sha256 in .cache/capital/MANIFEST.json): the French daily factors file, SSO and SPY adjusted closes
(yfinance), DTB3 (quant-tf strategies.dtb3), and the audited weekly B0 ledger (git blob 2313f28e...).
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
C = os.path.join(ROOT, ".cache", "capital")
FF = os.path.join(ROOT, ".cache", "exposure", "F-F_Research_Data_Factors_daily.csv")
QT = os.path.join(os.path.dirname(ROOT), "quant-tf", "research", "quant_trials")
LOCK, OUT = os.path.join(HERE, "READ_CAPITAL.lock"), os.path.join(HERE, "RESULT_CAPITAL.json")

UP, DOWN, TREND = 1.3, 0.7, 200
SPREAD = 0.0243            # margin spread over the T-bill
ER2, S2, ER1 = 0.0089, 0.0050, 0.000945
SWITCH = 0.0002            # 2 bp per unit of exposure traded


# ---------------------------------------------------------------- statistics
def stats_daily(r, rf):
    r, rf = np.asarray(r, float), np.asarray(rf, float)
    ex = r - rf
    nav = np.cumprod(1 + r)
    roll = pd.Series(nav).pct_change(252).min()        # worst rolling 252-session return
    return {"pct_per_year_arith": 252 * 100 * r.mean(), "cagr_pct": 100 * (nav[-1] ** (252 / len(r)) - 1),
            "excess_sharpe": float(ex.mean() / ex.std(ddof=1) * math.sqrt(252)),
            "vol_pct": float(100 * r.std(ddof=1) * math.sqrt(252)), "worst_12m_pct": float(100 * roll),
            "days": int(len(r))}


def hac_mean(x, lags=4):
    x = np.asarray(x, float)
    n, e = len(x), x - x.mean()
    v = e @ e / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (e[l:] @ e[:-l]) / n
    return float(x.mean()), float(math.sqrt(v / n))


def tracking(a, m, per_year):
    d = np.asarray(a, float) - np.asarray(m, float)
    mu, se = hac_mean(d)
    return {"mean_pct_per_year": per_year * 100 * mu, "hac_se_pct_per_year": per_year * 100 * se,
            "sd_pct_per_year": float(100 * d.std(ddof=1) * math.sqrt(per_year))}


# ---------------------------------------------------------------- core path and arms (daily)
def core_path(r):
    lvl = (1 + r).cumprod()
    ma = lvl.rolling(TREND, min_periods=TREND).mean()
    up = (lvl.shift(1) > ma.shift(1))
    e = pd.Series(np.where(up, UP, DOWN), index=r.index)
    return e[ma.shift(1).notna()]


def arms_daily(r, rf, e, r2x=None, r1x=None):
    """Daily returns of M, E1, E2 under cash conventions R (cash earns rf) and S (cash earns 0, debit charged).
    r: index return; rf: daily T-bill; r2x / r1x: real fund returns if given, else modelled."""
    if r2x is None:
        r2x = 2 * r - (rf + S2 / 252) - ER2 / 252
    if r1x is None:
        r1x = r - ER1 / 252
    sw = SWITCH * e.diff().abs().fillna(0)
    out, gross = {}, {}
    # M: hold e of the index (as a 1x fund when r1x is the real SPY)
    hold = r1x
    debit, cash = (e - 1).clip(lower=0), (1 - e).clip(lower=0)
    for cv in ("R", "S"):
        out[("M", cv)] = e * hold - debit * (rf + SPREAD / 252) + (cash * rf if cv == "R" else 0) - sw
    gross["M"] = e
    # E1: e/2 in the 2x fund, rest cash
    h = e / 2
    for cv in ("R", "S"):
        out[("E1", cv)] = h * r2x + ((1 - h) * rf if cv == "R" else 0) - sw
    gross["E1"] = h
    # E2: a 1x + b 2x, a + 2b = e, a + b <= 1, minimal b
    b = (e - 1).clip(lower=0)
    a = e - 2 * b
    for cv in ("R", "S"):
        out[("E2", cv)] = a * r1x + b * r2x + ((1 - a - b) * rf if cv == "R" else 0) - sw
    gross["E2"] = a + b
    return out, gross


def summarise_daily(out, gross, rf, e):
    res = {}
    for cv in ("R", "S"):
        m = out[("M", cv)]
        for arm in ("M", "E1", "E2"):
            x = out[(arm, cv)]
            s = stats_daily(x, rf)
            s["avg_gross"] = float(gross[arm].mean())
            s["avg_gross_in_1.3_weeks"] = float(gross[arm][e > 1].mean())
            s["gross_freed_vs_M_in_1.3"] = float((gross["M"] - gross[arm])[e > 1].mean())
            if arm != "M":
                s["tracking_vs_M"] = tracking(x, m, 252)
            res[f"{arm}_{cv}"] = s
    res["share_days_at_1.3"] = float((e > 1).mean())
    return res


def french():
    raw = pd.read_csv(FF, skiprows=4, names=["d", "mkt_rf", "smb", "hml", "rf"], dtype=str)
    raw = raw[raw.d.str.strip().str.fullmatch(r"\d{8}")]
    d = pd.to_datetime(raw.d.str.strip(), format="%Y%m%d")
    rf = raw.rf.astype(float).values / 100
    return pd.Series(raw.mkt_rf.astype(float).values / 100 + rf, index=d), pd.Series(rf, index=d)


def adj(t):
    p = pd.read_csv(os.path.join(C, f"{t}.csv"), index_col=0, parse_dates=True)["Adj Close"].astype(float)
    return p


def dtb3():
    sys.path.insert(0, QT)
    import strategies as ST                                     # noqa: E402
    return ST.dtb3()


# ---------------------------------------------------------------- item 1 (a), (b)
def item1_long():
    r, rf = french()
    e = core_path(r)
    r, rf = r.loc[e.index], rf.loc[e.index]
    out, gross = arms_daily(r, rf, e)
    res = summarise_daily(out, gross, rf, e)
    res["period"] = [str(e.index[0].date()), str(e.index[-1].date())]
    res["note"] = "French daily market (CRSP value-weighted), synthetic 2x fund; not the S&P 500"
    return res, (r, rf, e, out)


def item1_real():
    spy, sso = adj("SPY"), adj("SSO")
    tb = dtb3()
    idx = sso.index[sso.index >= "2006-07-01"]
    rs = spy.pct_change().reindex(idx)
    r2 = sso.pct_change().reindex(idx)
    rfd = tb.reindex(tb.index.union(idx)).ffill().shift(1).reindex(idx) / 252      # known the day before
    # trend on SPY's own history (from 2006-01)
    e_all = core_path(spy.pct_change().dropna())
    e = e_all.reindex(idx).dropna()
    ok = e.index[rs.loc[e.index].notna() & r2.loc[e.index].notna() & rfd.loc[e.index].notna()]
    e, rs, r2, rfd = e.loc[ok], rs.loc[ok], r2.loc[ok], rfd.loc[ok]
    # model check: tracking of the real 2x fund against 2 x SPY - rf
    te = r2 - (2 * rs - rfd)
    implied = float(-252 * te.mean())
    by_year = {int(y): float(-252 * g.mean()) for y, g in te.groupby(te.index.year)}
    check = {"implied_annual_drag_pct": 100 * implied, "assumed_drag_pct": 100 * (ER2 + S2),
             "assumed_less_2x_spy_er_pct": 100 * (ER2 + S2 - 2 * ER1),
             "tracking_sd_pct_per_year": float(100 * te.std(ddof=1) * math.sqrt(252)),
             "implied_by_year_pct": {k: 100 * v for k, v in by_year.items()},
             "note": "SPY returns are already net of SPY's 0.0945% fee; SSO tracks the index, so the comparable "
                     "assumption is ER2 + s - 2 x ER1"}
    out, gross = arms_daily(rs, rfd, e, r2x=r2, r1x=rs)              # real funds; M holds SPY
    res = summarise_daily(out, gross, rfd, e)
    res["period"] = [str(e.index[0].date()), str(e.index[-1].date())]
    res["model_check"] = check
    # modelled 2x on the same days, for the assumption check at fund level
    outm, _ = arms_daily(rs, rfd, e, r2x=2 * rs - (rfd + S2 / 252) - ER2 / 252 + 2 * ER1 / 252, r1x=rs)
    res["E1_R_modelled_on_same_days"] = stats_daily(outm[("E1", "R")], rfd)
    return res, implied


def item1_long_sensitivity(implied):
    """Rerun (a) with the implied drag in place of ER2 + s (pre-registered if |diff| > 0.25 %/yr)."""
    global S2
    keep = S2
    S2 = implied - ER2 + 2 * ER1
    try:
        res, _ = item1_long()
    finally:
        S2 = keep
    return {k: res[k] for k in ("M_R", "E1_R", "E2_R", "M_S", "E1_S", "E2_S")}


# ---------------------------------------------------------------- item 1 (c): whole fund 2020-2025
def ledger():
    L = pd.read_csv(os.path.join(C, "weekly_b0_ledger.csv"))
    assert len(L) == 302 and L.missing_held_returns.eq(0).all()
    return L


def period_returns(L):
    spy, sso = adj("SPY"), adj("SSO")
    cal = spy.index
    out = []
    for d, days in zip(pd.to_datetime(L.date), L.days):
        start = cal[cal > d][0]
        end = start + pd.Timedelta(days=int(days))
        if end not in cal:
            raise RuntimeError(f"period end {end.date()} is not a session")
        out.append((spy[end] / spy[start] - 1, sso[end] / sso[start] - 1))
    return np.array(out)


def item1_fund():
    L = ledger()
    pr = period_returns(L)
    s, w_spy, ss = L.core_spy.values, L.book_spy_hedge.values, L.sum_stock.values
    rate, rf, days = L.modeled_margin_rate.values, L.risk_free_rate.values, L.days.values.astype(float)
    book, ccost, total = L.book_net_return.values, L.core_turnover_cost.values, L.fund_total_return.values
    # check the ledger's implied SPY return against yfinance
    rm_impl = (total - book + ccost + L.legacy_margin_cost_nav.values) / s
    gap_bp = 1e4 * np.abs(rm_impl - pr[:, 0])
    share_ok = float((gap_bp <= 5).mean())
    if share_ok < 0.95:
        raise RuntimeError(f"STOP: ledger SPY vs yfinance agree within 5 bp on only {share_ok:.1%} of weeks")
    rm = rm_impl                                                     # the ledger's own SPY return
    r2 = pr[:, 1]
    spy_short = np.maximum(-s - w_spy, 0)
    st_short = L.short_sale_nav.values - spy_short
    st_long = ss + st_short
    f = days / 360
    arms, gross = {}, {}

    def finance(lmv, smv, ret):
        res = {}
        for conv in ("net", "seg"):
            debit = np.maximum(lmv - smv - 1, 0) if conv == "net" else np.maximum(lmv - 1, 0)
            credit = np.maximum(1 - (lmv - smv), 0) if conv == "net" else np.maximum(1 - lmv, 0)
            for cv in ("R", "S"):
                res[(conv, cv)] = ret - debit * rate * f + (credit * rf * f if cv == "R" else 0)
        return res

    # M: core SPY netted with the hedge
    spy_pos = s + w_spy
    lmv = np.maximum(spy_pos, 0) + st_long
    smv = np.maximum(-spy_pos, 0) + st_short
    arms["M"], gross["M"] = finance(lmv, smv, s * rm - ccost + book), lmv + smv
    # E1: e/2 in SSO; SPY = hedge only
    h = s / 2
    lmv = h + np.maximum(w_spy, 0) + st_long
    smv = np.maximum(-w_spy, 0) + st_short
    arms["E1"], gross["E1"] = finance(lmv, smv, h * r2 - ccost + book), lmv + smv
    # E2: a SPY + b SSO
    b = np.maximum(s - 1, 0)
    a = s - 2 * b
    spy_pos = a + w_spy
    lmv = b + np.maximum(spy_pos, 0) + st_long
    smv = np.maximum(-spy_pos, 0) + st_short
    arms["E2"], gross["E2"] = finance(lmv, smv, a * rm + b * r2 - ccost + book), lmv + smv
    # B0 identity: M net under S equals the audited ledger
    b0_err = float(np.max(np.abs(arms["M"][("net", "S")] - total)))
    res = {"weeks": 302, "spy_check_share_within_5bp": share_ok, "spy_check_max_gap_bp": float(gap_bp.max()),
           "B0_identity_max_abs_error": b0_err}

    def wstats(x):
        wk = 7 * x / days
        ex = wk - 7 * rf / 360
        nav = np.cumprod(1 + x)
        r52 = pd.Series(nav).pct_change(52).min()
        return {"pct_per_year_arith": float(52 * 100 * wk.mean()),
                "cagr_pct": float(100 * (nav[-1] ** (365.25 / days.sum()) - 1)),
                "excess_sharpe": float(ex.mean() / ex.std(ddof=1) * math.sqrt(52)),
                "legacy_ratio": float(wk.mean() / wk.std(ddof=1) * math.sqrt(52)),
                "vol_pct": float(100 * wk.std(ddof=1) * math.sqrt(52)), "worst_52w_pct": float(100 * r52)}
    for conv in ("net", "seg"):
        for cv in ("R", "S"):
            for arm in ("M", "E1", "E2"):
                x = arms[arm][(conv, cv)]
                st = wstats(x)
                st["avg_gross"] = float(gross[arm].mean())
                st["avg_gross_in_1.3_weeks"] = float(gross[arm][s > 1].mean())
                st["weeks_gross_above_1.9"] = int((gross[arm] > 1.9 + 1e-9).sum())
                if arm != "M":
                    st["vs_M_same_conventions"] = tracking(7 * x / days, 7 * arms["M"][(conv, cv)] / days, 52)
                res[f"{arm}_{conv}_{cv}"] = st
    res["share_weeks_at_1.3"] = float((s > 1).mean())
    return res, L, arms


# ---------------------------------------------------------------- item 4
def vol_scale_long(r, rf, e):
    base, _ = arms_daily(r, rf, e)
    m = base[("M", "R")]
    sq = m ** 2
    ew = sq.ewm(alpha=2 / 64, adjust=False).mean().shift(1)
    sig = np.sqrt(ew * 252)
    tgt = sig.expanding(min_periods=1).mean().shift(1)
    w = (tgt / sig).clip(0.5, 1.5)
    keep = w.index[252:][w.iloc[252:].notna().values]
    ew_e = (e * w).loc[keep]
    out, _ = arms_daily(r.loc[keep], rf.loc[keep], ew_e)
    return {"with_scale": stats_daily(out[("M", "R")], rf.loc[keep]),
            "without_scale": stats_daily(m.loc[keep], rf.loc[keep]),
            "avg_w": float(w.loc[keep].mean()), "share_w_at_bounds": float(((w.loc[keep] <= 0.5) | (w.loc[keep] >= 1.5)).mean()),
            "period": [str(keep[0].date()), str(keep[-1].date())]}


def vol_scale_fund(L):
    days, rf, rate = L.days.values.astype(float), L.risk_free_rate.values, L.modeled_margin_rate.values
    r = L.fund_total_return.values
    rfw = rf * days / 360
    ex = r - rfw
    sq = pd.Series((ex * np.sqrt(7 / days)) ** 2)
    sig = np.sqrt(sq.ewm(alpha=2 / 14, adjust=False).mean().shift(1) * 52)
    tgt = sig.expanding(min_periods=1).mean().shift(1)
    w = (tgt / sig).clip(0.5, 1.5).values
    net = L.core_spy.values + L.sum_stock.values + L.book_spy_hedge.values
    rp = rfw + w * ex - np.maximum(w - 1, 0) * rate * days / 360 * np.maximum(net, 0)
    k = np.arange(len(r)) >= 52
    k &= np.isfinite(w)

    def st(x):
        wk = 7 * x[k] / days[k]
        e2 = wk - 7 * rf[k] / 360
        nav = np.cumprod(1 + x[k])
        return {"pct_per_year_arith": float(52 * 100 * wk.mean()), "excess_sharpe": float(e2.mean() / e2.std(ddof=1) * math.sqrt(52)),
                "vol_pct": float(100 * wk.std(ddof=1) * math.sqrt(52)),
                "worst_52w_pct": float(100 * pd.Series(nav).pct_change(52).min()),
                "cagr_pct": float(100 * (nav[-1] ** (365.25 / days[k].sum()) - 1))}
    return {"with_scale": st(rp), "without_scale": st(r), "avg_w": float(np.nanmean(w[k])),
            "weeks": int(k.sum()), "first_week": str(L.date.values[k][0])}


def main():
    if os.path.exists(LOCK):
        sys.exit("already read: " + open(LOCK).read())
    open(LOCK, "w").write(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    res = {"prereg": "research/sharpe/PREREG_CAPITAL.md", "assumptions": {"ER2x": ER2, "s_financing": S2, "ER1x": ER1,
           "margin_spread": SPREAD, "switch_cost": SWITCH}}
    a, (r, rf, e, _) = item1_long()
    res["item1_a_1927_2026"] = a
    b, implied = item1_real()
    res["item1_b_real_2006_2026"] = b
    if abs(implied - (ER2 + S2 - 2 * ER1)) > 0.0025:
        res["item1_a_sensitivity_implied_drag"] = item1_long_sensitivity(implied)
    c, L, _ = item1_fund()
    res["item1_c_fund_2020_2025"] = c
    res["item4_descriptive_not_a_test"] = {"a_core_1927_2026": vol_scale_long(r, rf, e), "c_fund_2020_2025": vol_scale_fund(L)}
    res["run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(res, open(OUT, "w"), indent=1)
    print(json.dumps(res, indent=1)[:6000])


if __name__ == "__main__":
    main()
