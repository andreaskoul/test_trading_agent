"""X1, cross-asset trend sleeve (PREREG Layer 4; rules fixed in STATE.json plan.X1 before any number).

    python3 research/tree/L4_explore/x1.py dev     # development, first listing .. 2019-12-31 -> X1_DEV.json
    python3 research/tree/L4_explore/x1.py test    # 2020-2025 read, once; needs READ_X1.lock and X1_DEV.json

Inputs: .cache/tree/l4x/<T>.csv, frozen by fetch_x1.py (sha256 re-checked here).
"""
import hashlib
import json
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats as SS

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
CACHE = os.path.join(ROOT, ".cache", "tree", "l4x")
sys.path.insert(0, os.path.join(ROOT, "research", "sharpe"))
import construct as K  # noqa: E402
ST = K.ST

ETFS = ("IEF", "TLT", "GLD", "DBC", "UUP")
TARGET, LOOK, VOLWIN, GCAP, COST = 0.10, 252, 63, 2.0, 5e-4
FUND_GCAP = 1.9
DEV_END = pd.Timestamp("2019-12-31")
LOCK = os.path.join(HERE, "READ_X1.lock")
N_TRIALS = 44


def prices():
    man = json.load(open(os.path.join(CACHE, "MANIFEST.json")))
    out = {}
    for t in ETFS + ("SPY",):
        p = os.path.join(CACHE, f"{t}.csv")
        assert hashlib.sha256(open(p, "rb").read()).hexdigest() == man[t]["sha256"], f"{t} changed since frozen"
        out[t] = pd.read_csv(p, parse_dates=["Date"], index_col="Date")["Adj Close"]
    cal = out["SPY"].index
    return pd.DataFrame({t: out[t].reindex(cal) for t in ETFS}), out["SPY"]


def sleeve_weights(P, i):
    """Target weights at calendar row i (decision at that close), data through row i only."""
    x = np.zeros(len(ETFS))
    for k, t in enumerate(ETFS):
        col = P[t].values
        if i - LOOK < 0 or not np.isfinite(col[i - LOOK]) or not np.isfinite(col[i]):
            continue
        r = np.diff(col[i - VOLWIN:i + 1]) / col[i - VOLWIN:i]
        sig = r.std(ddof=1) * math.sqrt(252)
        x[k] = (1.0 if col[i] / col[i - LOOK] - 1 > 0 else -1.0) * TARGET / sig
    g = np.abs(x).sum()
    if g > GCAP:
        x *= GCAP / g
    return x


def rf_at(rf, d):
    return float(rf.asof(d - pd.Timedelta(days=1)))


def dev_periods(cal, start, end):
    th = np.where(cal.weekday == 3)[0]
    out = []
    for k in range(len(th) - 1):
        t, t2 = th[k], th[k + 1]
        if t2 + 1 >= len(cal) or cal[t2 + 1] > end or cal[t] < start:
            continue
        out.append((t, t + 1, t2 + 1))
    return out


def ann_stats(r, days):
    r, days = np.asarray(r, float), np.asarray(days, float)
    wk = r * 7 / days
    yrs = days.sum() / 365.25
    v = np.cumprod(1 + r)
    dd = float((v / np.maximum.accumulate(np.concatenate([[1], v]))[1:] - 1).min())
    return {"sharpe": float(wk.mean() / wk.std(ddof=1) * math.sqrt(52)), "pct_per_year": 100 * float(np.prod(1 + r) ** (1 / yrs) - 1),
            "vol_pct": 100 * float(wk.std(ddof=1) * math.sqrt(52)), "worst_fall_pct": 100 * dd, "weeks": int(len(r))}


def dev():
    P, spy = prices()
    cal = P.index
    rf = ST.dtb3()
    ma = spy.rolling(ST.TREND, min_periods=ST.TREND).mean().values
    sp = spy.values
    rows, prev_x, prev_s = [], np.zeros(len(ETFS)), None
    first = cal[LOOK + 1]
    for t, a, b in dev_periods(cal, cal[0], DEV_END):
        x = sleeve_weights(P, t)
        days = (cal[b] - cal[a]).days
        rfp = rf_at(rf, cal[t]) * days / 360
        R = (P.values[b] / P.values[a] - 1)
        R = np.where(np.isfinite(R), R, 0.0)
        if np.abs(x).sum() == 0:
            continue
        sx = float((x * (R - rfp)).sum()) - COST * float(np.abs(x - prev_x).sum())
        s = ST.UP if sp[t] > ma[t] else ST.DOWN
        Rm = sp[b] / sp[a] - 1
        mrate = (rf_at(rf, cal[t]) + ST.MARGIN_SPREAD) * days / 360
        core_raw = s * Rm - COST * abs(s - (prev_s if prev_s is not None else s)) - max(s - 1, 0) * mrate
        rows.append({"date": cal[t], "year": cal[t].year, "days": days, "sleeve_x": sx, "core_raw": core_raw, "core_x": core_raw - rfp,
                     "spy_x": Rm - rfp, "gross": float(np.abs(x).sum()), "n_inst": int((x != 0).sum()),
                     **{f"c_{e}": float(x[k] * (R[k] - rfp)) for k, e in enumerate(ETFS)}})
        prev_x, prev_s = x, s
    df = pd.DataFrame(rows)
    # code check: core raw vs construct.py's core-only path, 2013-2019 weeks
    d = K.T.build()
    K.RF, K.YEARS, K.GROSS_SIDE = rf, range(2013, 2020), 0.3
    zero = np.full(d["r"].shape, np.nan)
    sec = np.array(["U"] * len(d["names"]))
    ref = K.run(d, zero, "S0", COST, sec, np.zeros(len(sec), int), K.panic_flags(d))
    ref["date"] = d["S"][[t for t, *_ in ST.periods(d, K.YEARS)]]
    j = ref.set_index("date")[["total"]].join(df.set_index("date")[["core_raw"]], how="inner")
    check = {"weeks": int(len(j)), "corr": float(j.corr().iloc[0, 1]), "max_abs_diff": float((j.total - j.core_raw).abs().max())}
    assert check["corr"] > 0.99, f"core code check failed {check}"
    w = lambda c: df[c] * 7 / df.days  # noqa: E731
    Sc = float(w("core_x").mean() / w("core_x").std() * math.sqrt(52))
    Sx = float(w("sleeve_x").mean() / w("sleeve_x").std() * math.sqrt(52))
    sc, sx = float(w("core_x").std() * math.sqrt(52)), float(w("sleeve_x").std() * math.sqrt(52))
    rho = float(np.corrcoef(w("core_x"), w("sleeve_x"))[0, 1])
    Sxh = 0.5 * Sx
    wt = (sc / sx) * (Sxh - rho * Sc) / (Sc - rho * Sxh)
    pred = math.sqrt(Sc ** 2 + (Sxh - rho * Sc) ** 2 / (1 - rho ** 2))
    res = {"label": "development, first sleeve week .. 2019-12-31",
           "first_week": str(df.date.iloc[0].date()), "last_week": str(df.date.iloc[-1].date()),
           "sleeve_excess": ann_stats(df.sleeve_x, df.days), "core_excess": ann_stats(df.core_x, df.days),
           "spy_excess": ann_stats(df.spy_x, df.days),
           "sleeve_by_year": {int(y): {"pct": round(100 * float(np.prod(1 + g.sleeve_x) - 1), 2), "sharpe": round(float((g.sleeve_x * 7 / g.days).mean() / (g.sleeve_x * 7 / g.days).std() * math.sqrt(52)), 2)} for y, g in df.groupby("year")},
           "corr_sleeve_spy": float(np.corrcoef(w("sleeve_x"), w("spy_x"))[0, 1]), "corr_sleeve_core": rho,
           "avg_gross": float(df.gross.mean()), "max_gross": float(df.gross.max()),
           "contribution_pct_per_year": {e: 100 * float(df[f"c_{e}"].sum() / (df.days.sum() / 365.25)) for e in ETFS},
           "standalone_sharpe_per_etf": {e: float((df[f"c_{e}"] * 7 / df.days).mean() / (df[f"c_{e}"] * 7 / df.days).std() * math.sqrt(52)) for e in ETFS},
           "core_code_check_2013_2019": check,
           "weight": {"S_c": Sc, "S_x": Sx, "S_x_haircut": Sxh, "rho": rho, "sigma_c": sc, "sigma_x": sx, "w_sleeve_per_core_unit": wt,
                      "predicted_combined_sharpe_core_plus_sleeve": pred,
                      "formula": "w = (sigma_c/sigma_x)(S_x' - rho S_c)/(S_c - rho S_x'), S_x' = 0.5 S_x"}}
    json.dump(res, open(os.path.join(HERE, "X1_DEV.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


# ---------------------------------------------------------------- 2020-2025 test
def fund_components(d, pred, cost=5e-4):
    """The S0 path of construct.run (deciles, gross side 0.3), keeping the parts needed to add a sleeve."""
    S, spy = d["S"], pd.Series(d["spy"])
    ma = spy.rolling(ST.TREND, min_periods=ST.TREND).mean().values
    rows, prev, prev_spy, prev_s = [], None, 0.0, None
    for t, R, Rm, days in ST.periods(d, K.YEARS):
        ok = np.isfinite(pred[t]) & d["elig"][t]
        w = K.deciles(pred[t], ok)
        s = ST.UP if np.isfinite(ma[t]) and d["spy"][t] > ma[t] else ST.DOWN
        beta = np.nan_to_num(d["beta"][t], nan=1.0)
        w_spy = -float((w * beta).sum())
        dw = np.abs(w - (prev if prev is not None else 0)).sum() + abs(w_spy - prev_spy)
        book = float((w * np.nan_to_num(R)).sum() + w_spy * Rm) - cost * dw
        mrate = (float(K.RF.asof(S[t] - pd.Timedelta(days=1))) + ST.MARGIN_SPREAD) * days / 360
        core = s * Rm - cost * abs(s - (prev_s if prev_s is not None else s))
        net = s + float(w.sum()) + w_spy
        rows.append({"t": t, "date": S[t], "year": S[t].year, "days": days, "book": book, "core": core, "net": net, "mrate": mrate,
                     "gross_f": abs(s + w_spy) + float(np.abs(w).sum()), "spy": Rm,
                     "total": core + book - max(net - 1, 0) * mrate})
        prev, prev_spy, prev_s = w, w_spy, s
    return pd.DataFrame(rows)


def hac(Y, lags):
    T = len(Y)
    Y = Y - Y.mean(0)
    V = Y.T @ Y / T
    for l in range(1, lags + 1):
        G = Y[l:].T @ Y[:-l] / T
        V += (1 - l / (lags + 1)) * (G + G.T)
    return V


def lw_test(a, b):
    """Ledoit-Wolf (2008) delta-method HAC test of SR(a) - SR(b), weekly; Bartlett kernel."""
    T = len(a)
    lags = int(math.floor(4 * (T / 100) ** (2 / 9)))
    m1, m2, g1, g2 = a.mean(), b.mean(), (a * a).mean(), (b * b).mean()
    d = m1 / math.sqrt(g1 - m1 ** 2) - m2 / math.sqrt(g2 - m2 ** 2)
    grad = np.array([g1 / (g1 - m1 ** 2) ** 1.5, -g2 / (g2 - m2 ** 2) ** 1.5, -m1 / (2 * (g1 - m1 ** 2) ** 1.5), m2 / (2 * (g2 - m2 ** 2) ** 1.5)])
    Y = np.column_stack([a - m1, b - m2, a * a - g1, b * b - g2])
    se = math.sqrt(grad @ hac(Y, lags) @ grad / T)
    z = d / se
    return {"sharpe_diff_annual": d * math.sqrt(52), "se_annual": se * math.sqrt(52), "z": z, "p_one_sided": float(1 - SS.norm.cdf(z)), "lags": lags, "weeks": T}


def dsr(x, N):
    x = np.asarray(x, float)
    T = len(x)
    sr = x.mean() / x.std(ddof=1)
    g3, g4 = float(SS.skew(x)), float(SS.kurtosis(x, fisher=False))
    e = 0.5772156649
    sr0 = math.sqrt(1 / (T - 1)) * ((1 - e) * SS.norm.ppf(1 - 1 / N) + e * SS.norm.ppf(1 - 1 / (N * math.e)))
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)
    return {"N": N, "sharpe_annual": sr * math.sqrt(52), "sr0_annual": sr0 * math.sqrt(52), "skew": g3, "kurtosis": g4, "dsr": float(SS.norm.cdf(z))}


def test():
    assert os.path.exists(LOCK), "create READ_X1.lock first"
    devres = json.load(open(os.path.join(HERE, "X1_DEV.json")))
    wt = devres["weight"]["w_sleeve_per_core_unit"]
    assert wt > 0
    P, _ = prices()
    rf = ST.dtb3()
    d = K.T.build()
    K.RF, K.YEARS, K.GROSS_SIDE = rf, range(2020, 2026), 0.3
    pred = np.load(os.path.join(K.QT, ".cache", "quant_trials", "sp500_tf_master_h5.npz"))["h5"].astype(np.float64)
    F = fund_components(d, pred)
    ref = K.run(d, pred, "S0", 5e-4, K.sectors(d["names"]), np.zeros(len(d["names"]), int), K.panic_flags(d))
    assert np.allclose(ref.total.values, F.total.values, atol=1e-12), "re-implementation differs from construct.run"
    b0 = ann_stats(F.total, F.days)
    assert abs(b0["pct_per_year"] - 21.69) < 0.1 and abs(b0["sharpe"] - 0.937) < 0.01, f"B0 not reproduced {b0}"
    S, cal = d["S"], P.index
    pos = {dt: i for i, dt in enumerate(cal)}
    xs, Rs, prev_x = [], [], np.zeros(len(ETFS))
    for _, r in F.iterrows():
        t = int(r.t)
        i, a = pos[S[t]], pos[S[t + 1]]
        t2 = None
        b = a + int(np.searchsorted(cal[a:], S[t + 1] + pd.Timedelta(days=r.days)))
        assert cal[b] == S[t + 1] + pd.Timedelta(days=r.days)
        x = sleeve_weights(P, i)
        R = P.values[b] / P.values[a] - 1
        xs.append(x), Rs.append(R)
    xs, Rs = np.array(xs), np.array(Rs)
    dx = np.abs(np.diff(np.vstack([np.zeros(len(ETFS)), xs]), axis=0)).sum(1)
    dx[0] = np.abs(xs[0]).sum()
    raw_sleeve = (xs * Rs).sum(1) - COST * dx
    G = F.gross_f.values + wt * np.abs(xs).sum(1)
    c = np.minimum(1.0, FUND_GCAP / G)
    comb = c * (F.core.values + F.book.values + wt * raw_sleeve) - np.maximum(c * (F.net.values + wt * xs.sum(1)) - 1, 0) * F.mrate.values
    comb_uncapped = F.core.values + F.book.values + wt * raw_sleeve - np.maximum(F.net.values + wt * xs.sum(1) - 1, 0) * F.mrate.values
    rfp = np.array([rf_at(rf, S[int(t)]) * dd / 360 for t, dd in zip(F.t, F.days)])
    sleeve_x = raw_sleeve - xs.sum(1) * rfp
    wk = lambda v: np.asarray(v) * 7 / F.days.values  # noqa: E731
    a, bb = wk(comb), wk(F.total)
    a_m = a * bb.std(ddof=1) / a.std(ddof=1)
    test = lw_test(a_m, bb)
    D = {n: dsr(a, n) for n in (N_TRIALS, 100, 200)}
    passed = test["p_one_sided"] <= 0.05 and D[N_TRIALS]["dsr"] > 0.95
    by = lambda v: {int(y): round(100 * float(np.prod(1 + v[F.year.values == y]) - 1), 1) for y in range(2020, 2026)}  # noqa: E731
    res = {"label": "2020-2025 test, read once (READ_X1.lock)", "w_sleeve": wt,
           "B0": {**b0, "by_year": by(F.total.values)},
           "with_sleeve": {**ann_stats(comb, F.days), "by_year": by(comb)},
           "with_sleeve_uncapped_descriptive": {**ann_stats(comb_uncapped, F.days), "by_year": by(comb_uncapped)},
           "sleeve_alone_excess": {**ann_stats(sleeve_x, F.days), "by_year": by(sleeve_x)},
           "sleeve_contribution_pct_per_year_by_etf": {e: 100 * float((xs[:, k] * (Rs[:, k] - rfp)).sum() / (F.days.sum() / 365.25)) for k, e in enumerate(ETFS)},
           "corr_sleeve_vs_B0": float(np.corrcoef(wk(sleeve_x), bb)[0, 1]),
           "corr_sleeve_vs_spy": float(np.corrcoef(wk(sleeve_x), wk(F.spy.values - rfp))[0, 1]),
           "avg_gross_cap_scale_c": float(c.mean()), "share_weeks_scaled": float((c < 1).mean()),
           "avg_sleeve_gross_in_fund": float((wt * np.abs(xs).sum(1)).mean()),
           "lw2008_test": test, "dsr": D, "pass_X1": bool(passed),
           "consequence": "pass -> forward shadow from the first full week of December 2026 (proposal, instruments are owner policy); fail -> no sleeve"}
    json.dump(res, open(os.path.join(HERE, "X1_TEST.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    {"dev": dev, "test": test}[sys.argv[1]]()
