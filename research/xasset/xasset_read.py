"""§4-6 of PREREG_XASSET.md: the non-equity trend sleeve against the trend core, 1962-2002 (ONE read).

    python research/xasset/xasset_read.py --synthetic   # dry run on generated data: same code path, no real data,
                                                        # no lock -> research/xasset/SYNTHETIC_XASSET.json
    python research/xasset/xasset_read.py               # THE read -> RESULT_XASSET.json (once; READ_XASSET.lock)

The real read refuses to start unless CHECKS_XASSET.json exists, its gate is "pass", and it and the read's code are
committed and unchanged (git). It then writes READ_XASSET.lock (O_EXCL; the commit hashes of the code and of CHECKS and
the sha256 of CHECKS) BEFORE any pre-2003 sleeve data is loaded; xasset_lib.PRE2003_GUARD admits pre-2003 non-equity
data only inside that block. Choices the registration leaves open: IMPLEMENTATION_NOTES.md part B.
Every result line is "against the core only; proxy and futures instruments".
"""
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xasset_lib as L                                              # noqa: E402
from xasset_lib import G, P                                         # noqa: E402

START, END = pd.Timestamp("1962-01-01"), pd.Timestamp("2002-12-31")
POS_VOL, TARGET_VOL, EWMA_COM, ANN_DAYS = 0.40, 0.10, 60, 261
MIN_MONTHS, SIG_MONTHS, SD_MONTHS = 13, 12, 36
COSTS = {"bonds": (0.0006, 0.0002), "currencies": (0.0018, 0.0006), "commodities": (0.0018, 0.0006)}
COST_SWITCH_YEAR = 1992                     # first rate to 1992, second 1993-2002 (HOP Exhibit B1)
NW_LAGS, DRAWS, MEAN_BLOCK, SEED = 6, 10000, 12, 20261125
PRIOR_MEAN, PRIOR_SD, DECAY = 0.48, 0.20, 0.555
CAP_NOTIONAL, VOL_EQ_CAP, STRESS_LIMIT, ABS_NOTIONAL = 1.9, 1.9, 0.25, 6.0
LABEL = "against the core only; proxy and futures instruments"
CLASS_FROM = {"currencies": pd.Timestamp("1972-01-01")}   # §2 table "From 1972" (no floating-rate data before)
OUT = os.path.join(HERE, "RESULT_XASSET.json")
SYN_OUT = os.path.join(HERE, "SYNTHETIC_XASSET.json")
CODE_FILES = [os.path.join(HERE, f) for f in ("xasset_read.py", "xasset_lib.py", "proxy.py", "xasset_checks.py")] + \
             [os.path.join(L.ROOT, "research", "sharpe", "capital.py")]


# ===================================================================================== sleeve (§4)
def month_calendar(idx_list):
    lo = min(i.min() for i in idx_list if len(i))
    return pd.date_range(lo + pd.offsets.MonthEnd(0), END, freq="ME")


def market_signal_sigma(monthly, daily, cal):
    """Position inputs at each month end t: sign of the past-12-month compounded return (12 consecutive months), the
    ex-ante annualised volatility, and the entry rule (13 monthly returns behind the market)."""
    m = monthly.reindex(cal)
    have = m.notna().astype(int)
    run = have.groupby((have == 0).cumsum()).cumsum()
    s12 = np.log1p(m).rolling(SIG_MONTHS).sum()
    sig = np.sign(s12.where(run >= SIG_MONTHS))
    nobs = have.cumsum()
    if daily is not None:
        v = np.sqrt(daily.ewm(com=EWMA_COM).var() * ANN_DAYS)
        sd = v.groupby(daily.index.to_period("M")).last()
        sd = pd.Series(sd.values, index=sd.index.to_timestamp(how="end").normalize()).reindex(cal)
    else:
        sd = m.rolling(SD_MONTHS, min_periods=MIN_MONTHS).std() * math.sqrt(12)
    ok = (nobs >= MIN_MONTHS) & sig.notna() & (sd > 0)
    pos = (sig * POS_VOL / sd).where(ok)
    return pos, sd.where(ok), m


def cost_rates(cal, classes):
    yr = (cal - pd.offsets.MonthEnd(1)).year                          # trade at the previous month end
    return pd.DataFrame({k: np.where(yr <= COST_SWITCH_YEAR, COSTS[c][0], COSTS[c][1]) for k, c in classes.items()},
                        index=cal)


def build_sleeve(markets, subset=None, cost_mult=1.0):
    """Monthly sleeve (rows = holding month t+1): unscaled weights, gross and net excess returns, the 10 %-vol scaled
    version (36-month past sd), per-market trend returns, and sigma at the trade date."""
    names = [k for k, v in markets.items() if subset is None or v["class"] in subset]
    if not names:
        return None
    cal = month_calendar([markets[k]["monthly"].index for k in names])
    pos, sd, ret = {}, {}, {}
    for k in names:
        pos[k], sd[k], ret[k] = market_signal_sigma(markets[k]["monthly"], markets[k]["daily"], cal)
    POS, SD, R = pd.DataFrame(pos), pd.DataFrame(sd), pd.DataFrame(ret)
    held, sd_held = POS.shift(1), SD.shift(1)                       # position set at t, held over t+1
    active = held.notna() & R.notna()
    cls = {k: markets[k]["class"] for k in names}
    n_c = pd.DataFrame({c: active[[k for k in names if cls[k] == c]].sum(axis=1) for c in set(cls.values())})
    K = (n_c > 0).sum(axis=1)
    W = pd.DataFrame({k: np.where(active[k], held[k] / (K * n_c[cls[k]]).replace(0, np.nan), 0.0) for k in names},
                     index=cal).fillna(0.0)
    rates = cost_rates(cal, cls)
    gross = (W * R.fillna(0.0)).sum(axis=1)
    cost = (rates * W.diff().abs().fillna(W.abs())).sum(axis=1)
    live = K > 0
    first = live[live].index.min()
    keep = cal >= first
    gross, cost, W, R, active, sd_held, held = (x[keep] for x in (gross, cost, W, R, active, sd_held, held))
    net = gross - cost_mult * cost
    scale = TARGET_VOL / (gross.rolling(SD_MONTHS).std().shift(1) * math.sqrt(12))
    WS = W.mul(scale, axis=0)
    cost_s = (rates[keep] * WS.diff().abs().fillna(WS.abs())).sum(axis=1)
    net_s = ((WS * R.fillna(0.0)).sum(axis=1) - cost_mult * cost_s).where(scale.notna())
    trend = (held * R).where(active)
    out = {"gross": gross, "net": net, "net_scaled": net_s.dropna(), "W": W, "W_scaled": WS[scale.notna()],
           "trend": trend, "sigma_held": sd_held, "n_active": active.sum(axis=1), "classes": cls}
    for k in ("gross", "net", "net_scaled", "n_active"):
        G.derived(out[k], f"sleeve_{k}")
    return out


# ===================================================================================== statistics (§5)
def ols(y, X):
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    return b, e, math.sqrt(e @ e / (len(y) - X.shape[1]))


def nw_cov(X, e, lags):
    n = len(e)
    u = X * e[:, None]
    S = u.T @ u
    for lag in range(1, lags + 1):
        g = u[lag:].T @ u[:-lag]
        S += (1 - lag / (lags + 1)) * (g + g.T)
    XtXi = np.linalg.inv(X.T @ X)
    return XtXi @ S @ XtXi


def ar_stats(y, X):
    b, e, s = ols(y, X)
    se_a = math.sqrt(nw_cov(X, e, NW_LAGS)[0, 0])
    return {"alpha_pct_per_year": 1200 * b[0], "alpha_nw_se_pct_per_year": 1200 * se_a,
            "betas": [float(x) for x in b[1:]], "resid_sd_pct_per_year": 100 * s * math.sqrt(12),
            "AR": b[0] / s * math.sqrt(12), "AR_se_nw": se_a / s * math.sqrt(12), "months": int(len(y))}


def stationary_indices(T, draws, mean_block, rng):
    p = 1.0 / mean_block
    new = rng.random((draws, T)) < p
    starts = rng.integers(0, T, size=(draws, T))
    idx = np.empty((draws, T), dtype=np.int64)
    idx[:, 0] = starts[:, 0]
    for t in range(1, T):
        idx[:, t] = np.where(new[:, t], starts[:, t], (idx[:, t - 1] + 1) % T)
    return idx


def boot_ar(y, X, idx):
    out = np.empty(len(idx))
    for i, ix in enumerate(idx):
        yy, XX = y[ix], X[ix]
        b, *_ = np.linalg.lstsq(XX, yy, rcond=None)
        e = yy - XX @ b
        out[i] = b[0] / math.sqrt(e @ e / (len(yy) - XX.shape[1])) * math.sqrt(12)
    return out


def design(sleeve, core, us10=None):
    j = pd.concat([sleeve.rename("s"), core.rename("c")] + ([us10.rename("b")] if us10 is not None else []),
                  axis=1).dropna()
    X = np.column_stack([np.ones(len(j)), j.c.values] + ([j.b.values] if us10 is not None else []))
    return j.s.values, X, j


def cross_corr(trend, classes, min_overlap=24):
    names = list(trend.columns)
    C = trend.corr(min_periods=min_overlap)
    pairs = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            v = C.loc[a, b]
            if np.isfinite(v):
                key = "-".join(sorted((classes[a], classes[b])))
                pairs.setdefault(key, []).append(float(v))
    allv = [v for vs in pairs.values() for v in vs]
    return {"mean_pairwise_all": float(np.mean(allv)) if allv else None, "pairs": len(allv),
            "by_class_pair": {k: {"mean": float(np.mean(v)), "pairs": len(v)} for k, v in sorted(pairs.items())},
            "planning_value_rho": 0.1, "MOP_table4": {"within bonds": 0.38, "within FX": 0.10, "bonds-FX": 0.05}}


def contribution(sl, core_ex, exposure, sig_mkt):
    """§6 constrained contribution to fund Sharpe (in-sample, descriptive): core at weight 1 + w_t x 10 %-vol sleeve."""
    S = sl["net_scaled"]
    j = pd.concat([core_ex.rename("C"), S.rename("S"), exposure.rename("e")], axis=1).dropna()
    WS = sl["W_scaled"].reindex(j.index)
    sigma = sl["sigma_held"].reindex(j.index)
    sm = sig_mkt.shift(1).reindex(j.index)                          # market sigma at the trade date
    N = WS.abs().sum(axis=1)
    VS = (WS.abs() * sigma.fillna(0.0)).sum(axis=1)                 # sum |n_i| sigma_i
    mu = np.array([j.C.mean(), j.S.mean()])
    Sig = np.cov(np.vstack([j.C.values, j.S.values]))
    z = np.linalg.solve(Sig, mu)
    w_star = float(max(z[1] / z[0], 0.0)) if z[0] > 0 else (float("inf") if z[1] > 0 else 0.0)
    e = j.e
    cap_i = ((CAP_NOTIONAL - e) / N).clip(lower=0)
    cap_ii = pd.concat([((VOL_EQ_CAP - e) / (VS / sm)).clip(lower=0),
                        ((STRESS_LIMIT * math.sqrt(12) / 3 - e * sm) / VS).clip(lower=0),
                        ((ABS_NOTIONAL - e) / N).clip(lower=0)], axis=1).min(axis=1)

    def sr(x):
        return float(x.mean() / x.std(ddof=1) * math.sqrt(12))
    res = {"months": int(len(j)), "window": [str(j.index.min().date()), str(j.index.max().date())],
           "core_sharpe": sr(j.C), "w_star_unconstrained": w_star,
           "ideal_unconstrained_fund_sharpe": sr(j.C + (w_star if np.isfinite(w_star) else 0) * j.S)}
    for name, cap in (("i_notional_1.9", cap_i), ("ii_vol_equivalent", cap_ii)):
        w = np.minimum(w_star, cap) if np.isfinite(w_star) else cap
        F = j.C + w * j.S
        res[name] = {"fund_sharpe": sr(F), "delta_sharpe_vs_core": sr(F) - sr(j.C), "mean_w": float(w.mean()),
                     "share_months_capped": float((cap < w_star).mean()) if np.isfinite(w_star) else 1.0,
                     "max_notional": float((e + w * N).max())}
    res["largest_notional_under_ii"] = res["ii_vol_equivalent"]["max_notional"]
    return res


def analyse(data):
    """Everything in §5-6, identical for real and synthetic data."""
    mk, core = data["markets"], data["core"]
    out = {"label": LABEL, "markets": {k: v["class"] for k, v in mk.items()}}
    sl = build_sleeve(mk)
    sl2 = build_sleeve(mk, cost_mult=2.0)
    core_ex = core["excess"]
    spec = {}
    y0, X0, j0 = design(sl["net"], core_ex, data["us10"])           # months where both benchmarks exist
    months = j0.index
    rng = np.random.default_rng(SEED)
    idx = stationary_indices(len(months), DRAWS, MEAN_BLOCK, rng)
    for cname, s in (("registered", sl["net"]), ("2x", sl2["net"])):
        for bname, us10 in (("core", None), ("core+US10", data["us10"])):
            y, X, _ = design(s.reindex(months), core_ex.reindex(months), None if us10 is None else us10.reindex(months))
            st = ar_stats(y, X)
            b = boot_ar(y, X, idx)
            st["AR_90pct_bootstrap"] = [float(np.percentile(b, 5)), float(np.percentile(b, 95))]
            spec[f"{cname}_costs__{bname}"] = st
    out["window"] = [str(months.min().date()), str(months.max().date())]
    out["AR"] = spec
    jj = pd.concat([sl["net"].rename("s"), core_ex.rename("c")], axis=1).dropna()
    worst = jj.c <= jj.c.quantile(0.10)
    out["corr_with_core_all_months"] = float(jj.s.corr(jj.c))
    out["corr_with_core_worst_10pct_core_months"] = {"months": int(worst.sum()), "corr": float(jj.s[worst].corr(jj.c[worst]))}
    out["sleeve_gross_net"] = {"gross_pct_per_year": float(1200 * sl["gross"].mean()),
                               "net_pct_per_year": float(1200 * sl["net"].mean()),
                               "cost_pct_per_year": float(1200 * (sl["gross"] - sl["net"]).mean()),
                               "mean_active_markets": float(sl["n_active"].mean())}
    # diagnostics (attribution, not selection)
    diag = {}
    for name, subset, lo in (("rates_only", {"bonds"}, None), ("rates_and_fx_1972_2002", {"bonds", "currencies"},
                                                                  "1972-01-01"), ("commodities_only", {"commodities"}, None)):
        s = build_sleeve(mk, subset=subset)
        if s is None:
            diag[name] = {"markets": 0, "note": "no market of this class entered"}
            continue
        ser = s["net"] if lo is None else s["net"][s["net"].index >= lo]
        y, X, _ = design(ser, core_ex)
        diag[name] = ar_stats(y, X)
    for d0 in (1960, 1970, 1980, 1990, 2000):
        ser = sl["net"][(sl["net"].index.year >= d0) & (sl["net"].index.year < d0 + 10)]
        if len(ser) > 24:
            y, X, _ = design(ser, core_ex)
            diag[f"decade_{d0}s"] = ar_stats(y, X)
    out["diagnostics"] = diag
    out["realised_cross_market_correlation"] = cross_corr(sl["trend"], sl["classes"])
    out["constrained_contribution"] = contribution(sl, core_ex, core["exposure"], core["sigma_mkt"])
    # verdict (§6)
    reg_c, reg_b = spec["registered_costs__core"], spec["registered_costs__core+US10"]
    if reg_c["AR_90pct_bootstrap"][0] > 0 and reg_b["AR_90pct_bootstrap"][0] > 0:
        verdict = "supported"
    elif reg_c["AR_90pct_bootstrap"][1] < 0.15:
        verdict = "rejected"
    else:
        verdict = "inconclusive"
    out["verdict"] = verdict
    a, se = reg_c["AR"], reg_c["AR_se_nw"]
    prec = 1 / PRIOR_SD ** 2 + 1 / se ** 2
    pm = (PRIOR_MEAN / PRIOR_SD ** 2 + a / se ** 2) / prec
    out["posterior"] = {"prior": [PRIOR_MEAN, PRIOR_SD], "estimate": [a, se], "posterior_mean": pm,
                        "posterior_sd": math.sqrt(1 / prec), "decay": DECAY,
                        "forward_planning_AR": DECAY * pm, "forward_planning_AR_sd": DECAY * math.sqrt(1 / prec)}
    return out


# ===================================================================================== further registered tests
# Tests added by a later dated amendment to PREREG_XASSET.md (e.g. a multi-horizon blend as a secondary sleeve, or
# predictive tests from non-equity trends) go here as separate functions f(panel) -> dict, appended to
# ADDITIONAL_TESTS with their amendment id. They read the same frozen, guarded panel that the primary path reads
# (`panel["markets"][name]["monthly"|"daily"]`, `panel["core"]`, `panel["us10"]`), run inside the same lock, and never
# modify it or the primary path. An unregistered function must not be added here.
ADDITIONAL_TESTS = []          # [(name, amendment_id, function)]


def run_all(panel):
    """The primary sleeve and its statistics (§4-6), then any registered additional tests over the same panel."""
    out = {"primary": analyse(panel), "additional_tests": {}}
    for name, amendment, fn in ADDITIONAL_TESTS:
        out["additional_tests"][name] = {"amendment": amendment, "result": fn(panel)}
    return out


# ===================================================================================== real data (inside the lock)
def load_real(checks):
    mk = {}
    for cls, v in checks["entering_read"].items():
        for name in v["markets"]:
            if name in L.US_TSY:
                m, d = L.us_tsy(name, True), L.us_tsy(name, False)
            elif cls == "currencies":
                m, _ = L.fx_excess(name, True)
                d, _ = L.fx_excess(name, False)
            elif cls == "bonds":
                m, d = L.intl_bond_monthly(name.split("_")[1]), None
            else:
                d = L.pst_excess_daily(name)
                m = L.compound_monthly(d, f"pst_m_{name}")
            lo = CLASS_FROM.get(cls, START)                          # §2 table: the leg's registered start
            m, d = m[(m.index >= lo) & (m.index <= END)], None if d is None else d[(d.index >= lo) & (d.index <= END)]
            mk[name] = {"class": cls, "monthly": m, "daily": d}
    chk, r, rf, e, md = L.core_reproduce()
    if not chk["match_1e-6"]:
        raise RuntimeError(f"core does not reproduce RESULT_CAPITAL.json: {chk}")
    ex, e_first, sig = L.core_monthly(r, rf, e, md)
    us10 = L.us_tsy("US10", True)
    return {"markets": mk, "core": {"excess": ex, "exposure": e_first, "sigma_mkt": sig, "reproduction": chk},
            "us10": us10[(us10.index >= START) & (us10.index <= END)]}


def preflight():
    if os.path.exists(L.LOCK):
        raise SystemExit(f"already read: {open(L.LOCK).read()}")
    if not os.path.exists(L.CHECKS_OUT):
        raise SystemExit("refusing: CHECKS_XASSET.json does not exist (run xasset_checks.py run)")
    checks = json.load(open(L.CHECKS_OUT))
    if checks.get("gate") != "pass":
        raise SystemExit(f"refusing: the §3 gate is {checks.get('gate')!r}: {checks.get('gate_fail_reasons')}")
    ok_c, h_c = L.committed_clean([L.CHECKS_OUT])
    ok_k, h_k = L.committed_clean(CODE_FILES)
    if not (ok_c and ok_k):
        raise SystemExit("refusing: CHECKS_XASSET.json and the read code must be committed and unchanged")
    return checks, {"checks_commit": h_c, "checks_sha256": L.sha256(L.CHECKS_OUT), "code_commit": h_k,
                    "head": L.git("rev-parse", "HEAD").stdout.strip(),
                    "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def run_read():
    checks, payload = preflight()
    with G.read(L.LOCK, payload):                                    # lock written before any pre-2003 data
        data = load_real(checks)                                     # the panel: monthly + daily per market
        res = run_all(data)
    res.update({"prereg": "research/xasset/PREREG_XASSET.md", "lock": payload,
                "core_reproduction": data["core"]["reproduction"],
                "written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    print(json.dumps({k: res["primary"][k] for k in ("verdict", "AR", "posterior")}, indent=1, default=float))


# ===================================================================================== synthetic dry run
def synthetic_world(kappa, seed, start="1962-01-01", end="2002-12-31"):
    """Business-day random walks with a planted trend: in month t+1 every market's drift is
    kappa x sign(its past 12-month return) x its monthly sd (kappa = 0: no trend). 12 markets, 4 per class; two bond
    markets are month-end-only. The core is capital.py's 200-day rule on an independent random-walk index."""
    sys.path.insert(0, os.path.join(L.ROOT, "research", "sharpe"))
    import capital as CAP                                             # noqa: E402
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, end)
    per = days.to_period("M")
    mstarts = np.r_[0, np.flatnonzero(per[1:] != per[:-1]) + 1, len(days)]
    names = [("B1", "bonds", True), ("B2", "bonds", True), ("B3", "bonds", False), ("B4", "bonds", False),
             ("C1", "currencies", True), ("C2", "currencies", True), ("C3", "currencies", True),
             ("C4", "currencies", True), ("K1", "commodities", True), ("K2", "commodities", True),
             ("K3", "commodities", True), ("K4", "commodities", True)]
    vols = rng.uniform(0.05, 0.25, len(names))
    daily = np.zeros((len(days), len(names)))
    monthly = np.zeros((len(mstarts) - 1, len(names)))
    for t in range(len(mstarts) - 1):
        a, b = mstarts[t], mstarts[t + 1]
        sgn = np.sign(np.log1p(monthly[t - 12:t]).sum(0)) if t >= 12 else np.zeros(len(names))
        drift = kappa * sgn * vols / math.sqrt(12) / (b - a)
        daily[a:b] = drift + rng.normal(0, 1, (b - a, len(names))) * vols / math.sqrt(ANN_DAYS)
        monthly[t] = np.expm1(np.log1p(daily[a:b]).sum(0))
    me = pd.PeriodIndex(per[mstarts[:-1]]).to_timestamp(how="end").normalize()
    mk = {}
    for i, (n, c, has_daily) in enumerate(names):
        mk[n] = {"class": c, "monthly": pd.Series(monthly[:, i], index=me),
                 "daily": pd.Series(daily[:, i], index=days) if has_daily else None}
    idx_r = pd.Series(rng.normal(0.0003, 0.01, len(days)), index=days)
    rf = pd.Series(0.0002, index=days)
    e = CAP.core_path(idx_r)
    r2, rf2 = idx_r.loc[e.index], rf.loc[e.index]
    arms, _ = CAP.arms_daily(r2, rf2, e)
    ex, e_first, sig = L.core_monthly(r2, rf2, e, arms[("M", "R")], start=start, end=end)
    us10 = mk["B1"]["monthly"]
    return {"markets": mk, "core": {"excess": ex, "exposure": e_first, "sigma_mkt": sig}, "us10": us10}


def run_synthetic(reps=100):
    """The registered code path on generated data: recovery of a planted AR and of a null. No real file, no lock."""
    global DRAWS
    out = {"kind": "SYNTHETIC dry run: generated data only; no real data loaded; no READ_XASSET.lock",
           "written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    kappa_planted = 0.3 / 12.0                                       # sleeve SR ~ kappa * sqrt(12) * sqrt(12 markets)
    with G.synthetic():
        for world, kappa in (("planted_AR_0.3", kappa_planted), ("null", 0.0)):
            res = run_all(synthetic_world(kappa, SEED))["primary"]
            keep, DRAWS = DRAWS, 0
            truth = []
            try:
                for s in range(1, reps + 1):                        # same-design replications (no bootstrap)
                    truth.append(_quick_ar(synthetic_world(kappa, 1000 + s)))
            finally:
                DRAWS = keep
            reg = res["AR"]["registered_costs__core"]
            tr = np.array(truth)
            gross_truth = float(tr[:, 2].mean())
            mean_se, truth = float(tr[:, 1].mean()), tr[:, 0]
            t_mean, t_se = float(np.mean(truth)), float(np.std(truth, ddof=1) / math.sqrt(reps))
            out[world] = {"kappa": kappa, "true_AR_mean_of_replications": t_mean, "true_AR_mc_se": t_se,
                          "replications": reps, "replication_sd": float(np.std(truth, ddof=1)),
                          "mean_nw_se_over_replications": mean_se,
                          "true_gross_AR_before_costs": gross_truth,
                          "share_replications_within_1se": float(np.mean(np.abs(truth - t_mean) <= tr[:, 1])),
                          "dry_run_seed": SEED, "estimate": reg["AR"], "estimate_nw_se": reg["AR_se_nw"],
                          "estimate_90pct_bootstrap": reg["AR_90pct_bootstrap"],
                          "within_one_se_of_truth": bool(abs(reg["AR"] - t_mean) <= reg["AR_se_nw"]),
                          "truth_inside_90pct_interval": bool(reg["AR_90pct_bootstrap"][0] <= t_mean <=
                                                              reg["AR_90pct_bootstrap"][1]),
                          "verdict_on_synthetic": res["verdict"], "window": res["window"],
                          "full_output": res}
    json.dump(out, open(SYN_OUT, "w"), indent=1, default=float)
    print(json.dumps({w: {k: v for k, v in out[w].items() if k != "full_output"} for w in ("planted_AR_0.3", "null")},
                     indent=1, default=float))
    if os.path.exists(L.LOCK):
        raise RuntimeError("a lock exists after a synthetic run")


def _quick_ar(data):
    sl = build_sleeve(data["markets"])
    y, X, _ = design(sl["net"], data["core"]["excess"])
    yg, Xg, _ = design(sl["gross"], data["core"]["excess"])
    st = ar_stats(y, X)
    return st["AR"], st["AR_se_nw"], ar_stats(yg, Xg)["AR"]


if __name__ == "__main__":
    if "--synthetic" in sys.argv:
        run_synthetic()
    else:
        run_read()
