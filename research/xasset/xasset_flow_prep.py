"""Before the read (PREREG_XASSET.md Amendment 2): synthetic validation of H1-H6 and the registered power simulation
for H5 and H6. Generated data only, except the 2003+ autocorrelations used to match the power simulation (spent data,
through the guard). No pre-2003 non-equity value is loaded.

    python research/xasset/xasset_flow_prep.py validate   # (a) -> FLOW_SYNTHETIC.json
    python research/xasset/xasset_flow_prep.py power      # (b) -> FLOW_POWER.json

(a) Every hypothesis function of xasset_read.py runs unchanged on a generated panel (same layout as the read's):
    null worlds (no effect) give the rejection rate at 5 % and 10 % (size); planted worlds (one effect each) give the
    rejection rate and the mean estimate against the planted value. Fewer bootstrap draws than the read (199).
(b) H5 and H6 at the registered T (weekly 1974-2002: 1,513 weeks; monthly fallback 1974-2002: 348 months, full
    1981-2002: 264), with lag-1 autocorrelations and cross-correlations of target and predictors matched to the 2003+
    data; 999 draws; power at 5 %, at the Holm first step over the current evaluable set (0.10/3) and at the
    programme level 0.10/(40 + 3).
"""
import json
import math
import os
import sys
from datetime import datetime, timezone
from multiprocessing import Pool

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xasset_lib as L                                              # noqa: E402
import xasset_flow as F                                             # noqa: E402
import xasset_read as R                                             # noqa: E402

G = L.PRE2003_GUARD
OUT_A = os.path.join(HERE, "FLOW_SYNTHETIC.json")
OUT_B = os.path.join(HERE, "FLOW_POWER.json")
VAL_DRAWS, NULL_REPS, PLANT_REPS = 199, 200, 100
POW_DRAWS, POW_REPS = 999, 200
SPEC = ([("US10", "bonds", 1962, 0.08)] +
        [(c, "currencies", 1972, 0.10) for c in ("GBP", "AUD", "CAD", "JPY", "DEM", "NOK", "SEK", "DKK")] +
        [("GOLD", "commodities", 1975, 0.18), ("HEATOIL", "commodities", 1980, 0.30),
         ("BRENT_W", "commodities", 1988, 0.30)] +
        [(f"K{i}", "commodities", 1970, 0.20) for i in range(1, 10)])
# planted effects (one at a time); sized so that recovery is visible at 199 draws
PLANTED = {"H1": {"b1": 0.10}, "H2": {"b2": -0.17}, "H3": {"b3": 0.17}, "H4": {"d4": -0.03},
           "H5": {"g5": 0.25}, "H6": {"l6": 0.35}}


# ===================================================================================== the generated panel
def flow_world(seed, b1=0.0, b2=0.0, b3=0.0, d4=0.0, g5=0.0, l6=0.0):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("1962-01-01", "2002-12-31")
    n = len(days)
    per = days.to_period("M")
    mstart = np.r_[0, np.flatnonzero(per[1:] != per[:-1]) + 1, n]
    M = len(mstart) - 1
    burst = np.zeros(n)                                               # correlation bursts (absorption-ratio spikes)
    for m in range(M):
        if rng.random() < 0.10:
            a = mstart[m]
            b = min(a + 15, mstart[m + 1])
            burst[a:b] = rng.normal(0, 0.012, b - a)
    ret = {}
    for name, cls, y0, vol in SPEC:
        r = rng.normal(0, vol / math.sqrt(261), n) + 0.8 * burst
        r[days < pd.Timestamp(f"{y0}-01-01")] = np.nan
        ret[name] = r
    me = pd.PeriodIndex(per[mstart[:-1]]).to_timestamp(how="end").normalize()

    def monthly(r):
        out = np.full(M, np.nan)
        for m in range(M):
            seg = r[mstart[m]:mstart[m + 1]]
            if np.isfinite(seg).all():
                out[m] = np.expm1(np.log1p(seg).sum())
        return out
    mon = {k: monthly(v) for k, v in ret.items()}
    if b3:                                                            # H3: AUD/CAD month t -> commodities month t+1
        x3 = np.nanmean([mon["AUD"], mon["CAD"]], axis=0)
        for name, cls, _, _ in SPEC:
            if cls == "commodities":
                for m in range(M - 1):
                    if np.isfinite(x3[m]):
                        a, b = mstart[m + 1], mstart[m + 2]
                        ret[name][a:b] += b3 * x3[m] / (b - a)
                mon[name] = monthly(ret[name])
    us = pd.Series(mon["US10"], index=me)
    x1 = np.expm1(np.log1p(us).rolling(12).sum()).values
    x2 = np.nanmean([mon["HEATOIL"], mon["BRENT_W"]], axis=0) if b2 else np.zeros(M)
    z6 = (us - us.mean()) / us.std()
    drift = np.zeros(M)
    scale = np.ones(M)
    for m in range(M - 1):
        drift[m + 1] = b1 * np.nan_to_num(x1[m]) + b2 * np.nan_to_num(x2[m])
        scale[m + 1] = math.exp(-l6 * z6.iloc[m]) / math.exp(l6 ** 2 / 2) if l6 else 1.0
    eq = np.empty(n)
    for m in range(M):
        a, b = mstart[m], mstart[m + 1]
        eq[a:b] = 0.0003 + drift[m] / (b - a) + scale[m] * rng.normal(0, 0.01, b - a) + 0.8 * burst[a:b]
    if g5:                                                            # H5: nonlinear weekly effect
        thu = pd.date_range("1961-12-01", "2003-01-10", freq="W-THU")
        wed = thu - pd.Timedelta(days=1)
        us_d = pd.Series(ret["US10"], index=days)
        k = wed.searchsorted(days, side="left")
        wk = pd.Series(np.log1p(us_d.values)).groupby(k).sum()
        z = (wk - wk.mean()) / wk.std()
        kt = thu.searchsorted(days, side="left")                      # day in (Thu_{k-1}, Thu_k] -> k
        cnt = pd.Series(1, index=range(n)).groupby(kt).transform("size").values
        for i in range(n):
            src = kt[i] - 1                                           # target week k+1 uses predictor week k
            if src in z.index:
                eq[i] += g5 * 0.022 * (z[src] ** 2 - 1) / math.sqrt(2) / cnt[i]
    if d4:                                                            # H4: sequential spikes from the composites
        eq = _h4_sequential(eq, ret, days, mstart, d4)
    rf = pd.Series(0.0002, index=days)
    r_eq = pd.Series(eq, index=days) + rf
    mk = {}
    for name, cls, _, _ in SPEC:
        d = pd.Series(ret[name], index=days).dropna()
        mk[name] = {"class": cls, "daily": d, "monthly": pd.Series(monthly(ret[name]), index=me).dropna()}
    sys.path.insert(0, os.path.join(L.ROOT, "research", "sharpe"))
    import capital as CAP                                             # noqa: E402
    e = CAP.core_path(r_eq)
    arms, _ = CAP.arms_daily(r_eq.loc[e.index], rf.loc[e.index], e)
    ex, e_first, sig = L.core_monthly(r_eq.loc[e.index], rf.loc[e.index], e, arms[("M", "R")])
    return {"markets": mk, "us10": mk["US10"]["monthly"], "equity": {"r": r_eq, "rf": rf},
            "core": {"excess": ex, "exposure": e_first, "sigma_mkt": sig}}


def _h4_sequential(eq, ret, days, mstart, d4):
    """Plant H4: equity drift d4 in month t+1 when the month-t spike fires, the spike computed (as in the read) from
    the five composites up to the end of month t; generated month by month."""
    fx = np.nanmean([ret[c] for c, cl, _, _ in SPEC if cl == "currencies"], axis=0)
    com = np.nanmean([ret[c] for c, cl, _, _ in SPEC if cl == "commodities"], axis=0)
    t0 = np.searchsorted(days.values, np.datetime64("1976-01-01"))
    ar = np.full(len(days), np.nan)
    for m in range(len(mstart) - 2):
        a, b = mstart[m], mstart[m + 1]
        for i in range(max(a, t0 + 251), b):
            W = np.column_stack([eq[i - 251:i + 1], ret["US10"][i - 251:i + 1], fx[i - 251:i + 1],
                                 com[i - 251:i + 1], ret["GOLD"][i - 251:i + 1]])
            ar[i] = np.linalg.eigvalsh(np.corrcoef(W.T))[-1] / 5
        s = pd.Series(ar[t0:b])
        if len(s.dropna()) >= 252 + 15:
            d = (s.rolling(15).mean() - s.rolling(252).mean()) / s.rolling(252).std()
            if d.iloc[-1] >= 1.0:
                a2, b2 = mstart[m + 1], mstart[m + 2]
                eq[a2:b2] += d4 / (b2 - a2)
    return eq


def _conditions(bw):
    c = {h: {"evaluable": True, "reason": None} for h in ("H1", "H2", "H3", "H4", "H5")}
    c["H6"] = {"evaluable": True, "variant": "fallback_without_energy", "reason": None}
    c["H5_bandwidth"] = bw
    return c


def _bandwidth():
    w = flow_world(987654)
    with G.synthetic():
        d = R.weekly_design(w, R.FLOW_WINDOWS["H5"])
    e = (d["resid"] - d["resid"].mean()) / d["resid"].std()
    X = (d["X"] - d["X"].mean(0)) / d["X"].std(0)
    return {"sigma_resid": F.median_heuristic(e[:, None]), "sigma_X": F.median_heuristic(X),
            "predictors": d["predictors"], "note": "from an auxiliary generated world (seed 987654)"}


# ===================================================================================== (a) validation
def _one(args):
    seed, world, tests, bw, scheme = args
    F.NULL_SCHEME = scheme
    eff = PLANTED.get(world, {}) if world != "null" else {}
    p = flow_world(seed, **eff)
    p["flow_conditions"] = _conditions(bw)
    out = {}
    with G.synthetic():
        for h in tests:
            r = R.FLOW_TESTS[h](p, VAL_DRAWS)
            out[h] = {"p": r.get("p_one_sided", r.get("p")), "beta": r.get("beta"), "T": r["T"],
                      "stat": r.get("t", r.get("nHSIC", r.get("rank_score")))}
    return out


def validate():
    bw = _bandwidth()
    hs = list(R.FLOW_TESTS)
    res = {"kind": "SYNTHETIC validation of H1-H6 (generated data only)", "draws": VAL_DRAWS,
           "written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bandwidth_synthetic": bw,
           "planted": PLANTED}
    with Pool(min(10, os.cpu_count() or 1)) as pool:
        for scheme in ("registered", "decoupled"):
            hs_s = hs if scheme == "registered" else [h for h in hs if h != "H5"]   # H5 uses the wild bootstrap
            null = pool.map(_one, [(10_000 + s, "null", hs_s, bw, scheme) for s in range(NULL_REPS)])
            blk = {"null": {}, "planted_runs": {}}
            for h in hs_s:
                ps = np.array([r[h]["p"] for r in null])
                blk["null"][h] = {"reps": NULL_REPS, "reject_5pct": float(np.mean(ps <= 0.05)),
                                  "reject_10pct": float(np.mean(ps <= 0.10)),
                                  "mean_T": float(np.mean([r[h]["T"] for r in null])),
                                  "mc_se_at_5pct": math.sqrt(0.05 * 0.95 / NULL_REPS)}
                if null[0][h]["beta"] is not None:
                    blk["null"][h]["mean_beta"] = float(np.mean([r[h]["beta"] for r in null]))
            for h in hs_s:
                pl = pool.map(_one, [(20_000 + 1000 * hs.index(h) + s, h, [h], bw, scheme) for s in range(PLANT_REPS)])
                ps = np.array([r[h]["p"] for r in pl])
                row = {"reps": PLANT_REPS, "planted": PLANTED[h], "reject_5pct": float(np.mean(ps <= 0.05)),
                       "reject_10pct": float(np.mean(ps <= 0.10)),
                       "mean_t_or_stat": float(np.mean([r[h]["stat"] for r in pl]))}
                if pl[0][h]["beta"] is not None:
                    bs = np.array([r[h]["beta"] for r in pl])
                    row.update({"mean_beta": float(bs.mean()), "sd_beta": float(bs.std(ddof=1)),
                                "planted_beta": list(PLANTED[h].values())[0]})
                blk["planted_runs"][h] = row
            res[scheme] = blk
        res["decoupled_note"] = ("SYNTHETIC-ONLY comparison, not registered: u = c v + w with v and w drawn in "
                                 "independent stationary blocks; keeps the contemporaneous correlation and both "
                                 "persistences, breaks the lagged predictive link that joint blocks preserve")
    json.dump(res, open(OUT_A, "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("registered", "decoupled")}, indent=1))


# ===================================================================================== (b) power for H5 and H6
def matched_moments():
    """Lag-1 autocorrelations and cross-correlations of the H5 weekly and H6 monthly series on 2003+ data (spent),
    through the guard."""
    import xasset_checks as C
    chk = json.load(open(L.CHECKS_OUT))
    p03 = C.panel_2003(chk["entering_read"])
    w = R.weekly_design(p03, ("2003-01-01", "2026-12-31"))
    eb = R.equity_base(p03)
    mon = pd.concat({"y": eb["em"], "us10": p03["us10"],
                     "currencies": R._ew(p03, R._names(p03, "currencies"), "monthly")}, axis=1).dropna()
    mon = mon[mon.index >= L.VALID_START]
    G.derived(mon, "power_moments_monthly")

    def ac1(x):
        x = np.asarray(x, float)
        return float(np.corrcoef(x[:-1], x[1:])[0, 1])
    return {"weekly": {"ac1_y": ac1(w["y"]), "ac1_X": [ac1(w["X"][:, i]) for i in range(w["X"].shape[1])],
                       "corr_X": np.corrcoef(w["X"].T).tolist(), "weeks": int(len(w["y"]))},
            "monthly": {"ac1_y": ac1(mon.y), "ac1_X": [ac1(mon.us10), ac1(mon.currencies)],
                        "corr_X": np.corrcoef(mon[["us10", "currencies"]].values.T).tolist(),
                        "months": int(len(mon)), "window": [str(mon.index.min().date()), str(mon.index.max().date())]}}


def _ar_panel(rng, T, ac1_y, ac1_X, corr_X, burn=100):
    k = len(ac1_X)
    Lc = np.linalg.cholesky(np.asarray(corr_X))
    e = rng.standard_normal((T + burn, k)) @ Lc.T
    X = np.zeros((T + burn, k))
    for t in range(1, T + burn):
        X[t] = np.asarray(ac1_X) * X[t - 1] + np.sqrt(1 - np.asarray(ac1_X) ** 2) * e[t]
    s = np.zeros(T + burn)
    for t in range(1, T + burn):
        s[t] = s[t - 1] if rng.random() < 0.98 else 1 - s[t - 1]
    return X[burn:], s[burn:]


def _h5_rep(args):
    seed, r2, mom, bw = args
    rng = np.random.default_rng(seed)
    T = 1513
    X, s = _ar_panel(rng, T + 1, 0, mom["ac1_X"], mom["corr_X"])
    g = (X[:, 0] ** 2 - 1) / math.sqrt(2)
    u = np.zeros(T + 1)
    eps = rng.standard_normal(T + 1)
    for t in range(1, T + 1):
        u[t] = mom["ac1_y"] * u[t - 1] + math.sqrt(1 - mom["ac1_y"] ** 2) * eps[t]
    y_next = math.sqrt(r2) * g[:-1] + math.sqrt(1 - r2) * u[1:]
    Z = np.column_stack([np.ones(T), np.r_[0, y_next[:-1]], s[:-1]])
    A = np.column_stack([Z, X[:-1]])
    b, *_ = np.linalg.lstsq(A, y_next, rcond=None)
    r = F.hsic_wild(y_next - A @ b, X[:-1], bw["sigma_resid"], bw["sigma_X"], POW_DRAWS, seed)
    return r["p"]


def _h6_rep(args):
    seed, design, size, T, mom = args
    rng = np.random.default_rng(seed)
    k = 3 if T == 264 else 2
    ac1, corr = list(mom["ac1_X"]), np.asarray(mom["corr_X"])
    if k == 3:                                                         # energy: uncorrelated, ac1 0 (no 2003+ energy passes)
        ac1 = ac1 + [0.0]
        corr = np.pad(corr, ((0, 1), (0, 1)))
        corr[-1, -1] = 1.0
    X, s = _ar_panel(rng, T + 1, 0, ac1, corr)
    eps = rng.standard_normal(T + 1)
    u = np.zeros(T + 1)
    for t in range(1, T + 1):
        u[t] = mom["ac1_y"] * u[t - 1] + math.sqrt(1 - mom["ac1_y"] ** 2) * eps[t]
    xs = X[:-1].sum(1) / math.sqrt(X[:-1].sum(1).var())               # unit-variance index of the predictors
    if design == "location":
        y = math.sqrt(size) * xs + math.sqrt(1 - size) * u[1:]
    elif design == "tail_scale":
        lam = math.sqrt(size) / 1.2816                                 # tau-0.10 shift equals the location design's
        y = (1 - lam * xs) * u[1:]
    else:
        y = u[1:]
    Zr = np.column_stack([np.ones(T), np.r_[0, y[:-1]], s[:-1]])
    r = F.quantile_granger(y, Zr, X, POW_DRAWS, seed)                 # Xc_ext needs T+1 rows (row r=month t, r+1=target);
    return r["p"]                                                    # X has T+1 rows, so pass X, not X[:-1] (matches h6_tail)


def _h6_rep_dec(args):
    F.NULL_SCHEME = "decoupled"
    try:
        return _h6_rep(args)
    finally:
        F.NULL_SCHEME = "registered"


def power():
    chk = json.load(open(L.CHECKS_OUT))
    bw = chk["flow_conditions"]["H5_bandwidth"]
    mom = matched_moments()
    m = len(chk["flow_conditions"]["evaluable_set"])
    levels = {"5pct": 0.05, f"holm_first_step_0.10/{m}": 0.10 / m, f"programme_0.10/{40 + m}": 0.10 / (40 + m)}
    res = {"kind": "registered power simulation for H5 and H6 (generated data matched in T and autocorrelation)",
           "written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "draws": POW_DRAWS,
           "reps": POW_REPS, "matched_moments_2003_on": mom, "levels": levels, "H5_bandwidth_frozen": bw}
    with Pool(min(10, os.cpu_count() or 1)) as pool:
        res["H5"] = {"T": 1513, "effect": "nonlinear (x1^2 - 1)/sqrt(2) term; size = its share of target variance"}
        for r2 in (0.0, 0.005, 0.01, 0.02):
            ps = np.array(pool.map(_h5_rep, [(30_000 + i, r2, mom["weekly"], bw) for i in range(POW_REPS)]))
            res["H5"][f"nonlinear_R2_{r2}"] = {k: float(np.mean(ps <= v)) for k, v in levels.items()}
        res["H6"] = {}
        for T in (348, 264):
            row = {"variant": "fallback_without_energy (registered now)" if T == 348 else "full (if energy qualifies)"}
            for design, size in (("null", 0.0), ("location", 0.005), ("location", 0.01), ("tail_scale", 0.005),
                                 ("tail_scale", 0.01)):
                ps = np.array(pool.map(_h6_rep, [(40_000 + i, design, size, T, mom["monthly"]) for i in range(POW_REPS)]))
                row[f"{design}_{size}"] = {k: float(np.mean(ps <= v)) for k, v in levels.items()}
            res["H6"][f"T{T}"] = row
        F.NULL_SCHEME = "decoupled"
        row = {"note": "SYNTHETIC-ONLY comparison under the decoupled null (not registered)"}
        for design, size in (("null", 0.0), ("location", 0.01), ("tail_scale", 0.01)):
            ps = np.array(pool.map(_h6_rep_dec, [(40_000 + i, design, size, 348, mom["monthly"]) for i in range(POW_REPS)]))
            row[f"{design}_{size}"] = {k: float(np.mean(ps <= v)) for k, v in levels.items()}
        res["H6"]["T348_decoupled_comparison"] = row
        F.NULL_SCHEME = "registered"
    json.dump(res, open(OUT_B, "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("H5", "H6")}, indent=1))


if __name__ == "__main__":
    {"validate": validate, "power": power}[sys.argv[1]]()
