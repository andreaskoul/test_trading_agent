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


def run_all(panel, additional=True):
    """The primary sleeve and its statistics (§4-6), then any registered additional tests over the same panel
    (additional=False only for the primary-path synthetic dry run, whose generated panel has no flow inputs)."""
    out = {"primary": analyse(panel), "additional_tests": {}}
    for name, amendment, fn in (ADDITIONAL_TESTS if additional else []):
        out["additional_tests"][name] = {"amendment": amendment, "result": fn(panel)}
    return out


# ===================================================================================== Amendment 2: information flow
# LIT_FLOW.md §7 verbatim (PREREG_XASSET.md Amendment 2). Each hypothesis is its own function over the same guarded
# panel; the family function applies the data conditions fixed at the gate (CHECKS_XASSET.json "flow_conditions"),
# Holm at 0.10, the verdict rules and the posterior. Choices left open: IMPLEMENTATION_NOTES.md part E.
import xasset_flow as F                                             # noqa: E402

ENERGY = ("HEATOIL", "CRUDE_W", "GASOIL", "BRENT_W")
FLOW_WINDOWS = {"H1": ("1963-01-01", "2002-12-31"), "H2": ("1981-01-01", "2002-12-31"),
                "H3": ("1974-01-01", "2002-12-31"), "H4": ("1977-01-01", "2002-12-31"),
                "H5": ("1974-01-01", "2002-12-31"), "H6": ("1981-01-01", "2002-12-31"),
                "H6_fallback": ("1974-01-01", "2002-12-31")}
H4_FROM = pd.Timestamp("1976-01-01")


def _me(s):
    return pd.Series(s.values, index=s.index.to_timestamp(how="end").normalize())


def equity_base(panel):
    """French market: daily excess, monthly excess (compounded return - compounded T-bill), the core's state (index
    level above its 200-session average) daily and at each month end."""
    r, rf = panel["equity"]["r"], panel["equity"]["rf"]
    per = r.index.to_period("M")
    em = _me(np.expm1(np.log1p(r).groupby(per).sum()) - np.expm1(np.log1p(rf).groupby(per).sum()))
    lvl = (1 + r).cumprod()
    ma = lvl.rolling(200).mean()
    st = (lvl > ma).astype(float).where(ma.notna())
    return {"ex_d": r - rf, "em": em, "state_d": st, "state_m": _me(st.groupby(per).last())}


def _names(panel, cls):
    return [k for k, v in panel["markets"].items() if v["class"] == cls]


def _ew(panel, names, kind):
    xs = [panel["markets"][n][kind] for n in names if n in panel["markets"] and panel["markets"][n][kind] is not None]
    return pd.concat(xs, axis=1).mean(axis=1) if xs else None


def _contiguous_tail(ok):
    """Positions of the last contiguous run of True."""
    pos = np.flatnonzero(ok)
    if not len(pos):
        return pos
    gaps = np.flatnonzero(np.diff(pos) > 1)
    return pos[gaps[-1] + 1:] if len(gaps) else pos


def monthly_design(y_next, Z, innov, P, window):
    """Rows t (month ends) with the target y_next[t] (= month t+1) inside `window`, Z[t] and the innovations of rows
    t-P..t+1 present; the last contiguous block. Returns y, Z (with constant), innovations (P pre-sample rows, the T
    predictor months and the last target month: P + T + 1 rows), target dates."""
    cal = y_next.index
    Zd = Z.reindex(cal)
    inn = innov.reindex(cal)
    tgt = cal + pd.offsets.MonthEnd(1)
    have = inn.notna().all(axis=1).astype(int)
    ok_inn = have.rolling(P + 1).sum().eq(P + 1).values & have.shift(-1).eq(1).values   # + the target month's
    ok = (y_next.notna().values & Zd.notna().all(axis=1).values & ok_inn &
          (tgt >= pd.Timestamp(window[0])) & (tgt <= pd.Timestamp(window[1])))
    rows = _contiguous_tail(ok)
    if len(rows) < 60:
        raise ValueError(f"only {len(rows)} usable months")
    y = y_next.values[rows]
    Zm = np.column_stack([np.ones(len(rows)), Zd.values[rows]])
    I = inn.values[rows[0] - P:rows[-1] + 2]                         # P pre-sample, T rows, + the last target month
    G.derived(pd.Series(y, index=tgt[rows]), "flow_target")
    return y, Zm, I, tgt[rows]


def _rolling12(inn):
    c = np.convolve(inn[:, 0], np.ones(12), "valid")
    return np.expm1(c)


def h1_bonds_equity(panel, draws=None):
    """H1: OLS of r^e_{t+1} on [1, Z_t, x1_t]; x1 = 12-month excess return of the US 10-year proxy; one-sided (+)."""
    eb = equity_base(panel)
    Z = pd.concat([eb["em"], eb["state_m"]], axis=1)
    inn = np.log1p(panel["us10"]).to_frame()
    y, Zm, I, dates = monthly_design(eb["em"].shift(-1), Z, inn, 11, FLOW_WINDOWS["H1"])
    return F.mean_granger(y, Zm, I, _rolling12, +1, draws or F.DRAWS, F.SEED, dates)


def h2_energy_equity(panel, draws=None):
    """H2: as H1 with x2 = last month's excess return of the equal-weight energy futures composite; one-sided (-)."""
    eb = equity_base(panel)
    en = _ew(panel, [n for n in ENERGY if n in panel["markets"]], "monthly")
    Z = pd.concat([eb["em"], eb["state_m"]], axis=1)
    y, Zm, I, dates = monthly_design(eb["em"].shift(-1), Z, en.to_frame(), 0, FLOW_WINDOWS["H2"])
    return F.mean_granger(y, Zm, I, lambda a: a[:, 0], -1, draws or F.DRAWS, F.SEED, dates)


def h3_ccy_commodities(panel, draws=None):
    """H3: OLS of the next-month equal-weight commodity futures excess return on [1, its month-t return, x3_t];
    x3 = equal-weight month-t excess return of AUD and CAD; one-sided (+)."""
    com = _ew(panel, _names(panel, "commodities"), "monthly")
    x3 = _ew(panel, ["AUD", "CAD"], "monthly")
    y, Zm, I, dates = monthly_design(com.shift(-1), com.to_frame(), x3.to_frame(), 0, FLOW_WINDOWS["H3"])
    return F.mean_granger(y, Zm, I, lambda a: a[:, 0], +1, draws or F.DRAWS, F.SEED, dates, nonneg_forecast=False)


def h4_daily_composites(panel):
    eb = equity_base(panel)
    cols = {"equity": eb["ex_d"], "us10": panel["markets"]["US10"]["daily"],
            "currencies": _ew(panel, _names(panel, "currencies"), "daily"),
            "commodities": _ew(panel, _names(panel, "commodities"), "daily"),
            "gold": panel["markets"]["GOLD"]["daily"]}
    D = pd.concat(cols, axis=1).dropna()
    return D[(D.index >= H4_FROM) & (D.index <= END)]


def h4_absorption_spike(panel, draws=None):
    """H4: Spike_t = 1 if (mean AR over 15 days - mean AR over 252 days) / sd of AR over 252 days >= 1 at the end of
    month t; AR = largest-eigenvalue share of the correlation matrix of the 5 composites' trailing 252 daily returns.
    Coefficient of Spike_t in the H1-form regression; one-sided (-). Daily data resampled in month blocks."""
    eb = equity_base(panel)
    D = h4_daily_composites(panel)
    per = D.index.to_period("M")
    months = per.unique()
    blocks = [D.values[per == m] for m in months]
    me = months.to_timestamp(how="end").normalize()

    def build(month_idx_rows):
        ix = month_idx_rows[:, 0].astype(int)
        parts = [blocks[i] for i in ix]
        lens = np.cumsum([len(b) for b in parts]) - 1
        sp = F.spike_series(F.absorption_ratio(np.vstack(parts)))
        return sp[lens][P:]
    build.indices = True                                               # innovations are month indices
    P = 25                                                             # warm-up months (252 + 252 + 15 sessions)
    inn = pd.DataFrame({"m": np.arange(len(months), dtype=float)}, index=me)
    Z = pd.concat([eb["em"], eb["state_m"]], axis=1)
    y, Zm, I, dates = monthly_design(eb["em"].shift(-1), Z, inn, P, FLOW_WINDOWS["H4"])
    res = F.mean_granger(y, Zm, I, build, -1, draws or F.DRAWS, F.SEED, dates)
    res["spike_months"] = int(np.nansum(build(I[:-1])))
    return res


def weekly_design(panel, window, bandwidths=None):
    """H5 data: target = equity excess Thursday close -> next Thursday close; predictors = the week to the preceding
    Wednesday (a full day skipped); Z = equity excess of the week to Thursday and the core state at Thursday."""
    eb = equity_base(panel)
    X = {"us10": panel["markets"]["US10"]["daily"], "currencies": _ew(panel, _names(panel, "currencies"), "daily"),
         "commodities": _ew(panel, _names(panel, "commodities"), "daily")}
    X = {k: v for k, v in X.items() if v is not None}
    lo, hi = pd.Timestamp(window[0]) - pd.Timedelta(days=21), pd.Timestamp(window[1]) + pd.Timedelta(days=8)
    thu = pd.date_range(lo, hi, freq="W-THU")
    wed = thu - pd.Timedelta(days=1)

    def bucket(s, edges):
        s = s.dropna()
        s = s[(s.index > edges[0]) & (s.index <= edges[-1])]
        k = edges.searchsorted(s.index, side="left")
        g = np.log1p(s).groupby(k).sum()
        cnt = s.groupby(k).size()
        out = pd.Series(np.nan, index=range(len(edges)))
        out.loc[g.index] = np.expm1(g.values)
        out.loc[cnt.index[cnt == 0]] = np.nan
        return out.values
    eq = bucket(eb["ex_d"], thu)                                      # eq[k]: week (Thu_{k-1}, Thu_k]
    st = eb["state_d"].dropna().reindex(thu, method="ffill").values
    xs = np.column_stack([bucket(v, wed) for v in X.values()])         # x[k]: week (Wed_{k-1}, Wed_k]
    y = np.r_[eq[1:], np.nan]
    Z = np.column_stack([np.ones(len(thu)), eq, st])
    ok = (np.isfinite(y) & np.isfinite(Z).all(1) & np.isfinite(xs).all(1) & (thu + pd.Timedelta(days=7) >= window[0])
          & (thu + pd.Timedelta(days=7) <= pd.Timestamp(window[1])))
    ok[0] = False
    G.derived(pd.Series(y[ok], index=thu[ok] + pd.Timedelta(days=7)), "flow_weekly_target")
    yv, Zv, Xv = y[ok], Z[ok], xs[ok]
    b, *_ = np.linalg.lstsq(np.column_stack([Zv, Xv]), yv, rcond=None)
    e = yv - np.column_stack([Zv, Xv]) @ b
    return {"y": yv, "Z": Zv, "X": Xv, "resid": e, "weeks": thu[ok] + pd.Timedelta(days=7), "predictors": list(X)}


def h5_hsic(panel, draws=None):
    """H5: HSIC between the linear-model residual and X_t (Gaussian kernels, the frozen median-heuristic bandwidths),
    wild bootstrap."""
    bw = panel["flow_conditions"]["H5_bandwidth"]
    w = weekly_design(panel, FLOW_WINDOWS["H5"])
    if w["predictors"] != bw["predictors"]:
        raise ValueError(f"predictors {w['predictors']} differ from the frozen bandwidth's {bw['predictors']}")
    r = F.hsic_wild(w["resid"], w["X"], bw["sigma_resid"], bw["sigma_X"], draws or F.DRAWS, F.SEED)
    r["predictors"] = w["predictors"]
    return r


def h6_tail(panel, draws=None):
    """H6: quantile regression (tau 0.10) of r^e_{t+1} on [1, Z_t, x1_t, x2_t, x_FX,t] (one-month returns); rank-score
    test that the cross-asset slopes are jointly 0; fallback without energy (1974-2002)."""
    variant = panel["flow_conditions"]["H6"]["variant"]
    eb = equity_base(panel)
    xs = {"us10": panel["us10"], "currencies": _ew(panel, _names(panel, "currencies"), "monthly")}
    if variant == "full":
        xs["energy"] = _ew(panel, [n for n in ENERGY if n in panel["markets"]], "monthly")
    win = FLOW_WINDOWS["H6" if variant == "full" else "H6_fallback"]
    Z = pd.concat([eb["em"], eb["state_m"]], axis=1)
    inn = pd.concat(xs, axis=1)
    y, Zm, I, dates = monthly_design(eb["em"].shift(-1), Z, inn, 0, win)
    r = F.quantile_granger(y, Zm, I, draws or F.DRAWS, F.SEED, F.TAU, dates)
    r.update({"variant": variant, "predictors": list(xs)})
    return r


FLOW_TESTS = {"H1": h1_bonds_equity, "H2": h2_energy_equity, "H3": h3_ccy_commodities, "H4": h4_absorption_spike,
              "H5": h5_hsic, "H6": h6_tail}


def flow_family(panel, draws=None):
    """Amendment 2 family: the evaluable set fixed at the gate; Holm at 0.10; programme p; verdicts; posterior."""
    if F.NULL_SCHEME != "registered":
        raise RuntimeError("the family runs only under the registered null scheme")
    cond = panel["flow_conditions"]
    res = {}
    for h, fn in FLOW_TESTS.items():
        if not cond[h]["evaluable"]:
            res[h] = {"evaluable": False, "reason": cond[h]["reason"]}
            continue
        res[h] = {"evaluable": True, **fn(panel, draws)}
    pv = {h: (r.get("p_one_sided", r.get("p")) if r["evaluable"] else None) for h, r in res.items()}
    adj = F.holm(pv)
    m = sum(v is not None for v in pv.values())
    N = F.N_PROGRAMME_BASE + m
    for h, r in res.items():
        if not r["evaluable"]:
            continue
        r["holm_p"] = adj[h]
        r["programme_p_bonferroni"] = min(1.0, pv[h] * N)
        if h in ("H1", "H2", "H3", "H4"):
            r["verdict"] = F.verdict(adj[h], r["oos"].get("R2_oos"), r["implied_R2_90pct_upper"])
            r["posterior"] = F.posterior_r2(r["std_beta"], r["std_beta_se"], r["expected_sign"])
        elif h == "H6":
            r["verdict"] = F.verdict(adj[h], r["oos_check_loss_skill"].get("skill"), None)
        else:
            r["verdict"] = F.verdict(adj[h], None, None)
    return {"family": "Amendment 2 (H1-H6), Holm at 0.10 over the evaluable set", "evaluable": m,
            "programme_N": N, "results": res}


def flow_diagnostics(panel):
    """Outside the family: Forbes-Rigobon-adjusted correlations (core's worst 10 % months vs the rest), Diebold-Yilmaz
    and Barunik-Krehlik connectedness on daily composites by decade, the reverse directions of H1 and H3."""
    eb = equity_base(panel)
    core = panel["core"]["excess"]
    crisis = (core <= core.quantile(0.10)).astype(float)
    comps = {"us10": panel["us10"], "currencies": _ew(panel, _names(panel, "currencies"), "monthly"),
             "commodities": _ew(panel, _names(panel, "commodities"), "monthly"),
             "energy": _ew(panel, [n for n in ENERGY if n in panel["markets"]], "monthly")}
    if "GOLD" in panel["markets"]:
        comps["gold"] = panel["markets"]["GOLD"]["monthly"]
    out = {"forbes_rigobon": {k: F.forbes_rigobon(eb["em"], v, crisis) for k, v in comps.items() if v is not None}}
    daily = {"equity": eb["ex_d"], "us10": panel["markets"]["US10"]["daily"],
             "currencies": _ew(panel, _names(panel, "currencies"), "daily"),
             "commodities": _ew(panel, _names(panel, "commodities"), "daily")}
    D = pd.concat({k: v for k, v in daily.items() if v is not None}, axis=1).dropna()
    D = D[D.index <= END]
    out["connectedness"] = {}
    for d0 in (1970, 1980, 1990, 2000):
        sub = D[(D.index.year >= d0) & (D.index.year < d0 + 10)]
        if len(sub) > 500:
            Y = (sub / sub.std()).values
            out["connectedness"][f"{d0}s"] = {"days": int(len(sub)), "diebold_yilmaz": F.diebold_yilmaz(Y, list(D)),
                                              "barunik_krehlik": F.barunik_krehlik(Y, list(D))}
    # reverse directions (OLS, Newey-West 6 lags; descriptive)
    us = panel["us10"]
    eq12 = np.expm1(np.log1p(eb["em"]).rolling(12).sum())
    j = pd.concat([us.shift(-1).rename("y"), us.rename("own"), eq12.rename("x")], axis=1).dropna()
    j = j[j.index <= END]
    out["reverse_H1_equity_to_bonds"] = _nw_slope(j)
    com = comps["commodities"]
    if com is not None and len(_names(panel, "commodities")) >= 10:
        fx = _ew(panel, ["AUD", "CAD"], "monthly")
        j = pd.concat([fx.shift(-1).rename("y"), fx.rename("own"), com.rename("x")], axis=1).dropna()
        out["reverse_H3_commodities_to_ccy"] = _nw_slope(j[j.index <= END])
    else:
        out["reverse_H3_commodities_to_ccy"] = {"note": "commodity composite below 10 markets: not run"}
    return out


def _nw_slope(j):
    X = np.column_stack([np.ones(len(j)), j.own.values, j.x.values])
    b, e, s = ols(j.y.values, X)
    se = math.sqrt(nw_cov(X, e, NW_LAGS)[2, 2])
    return {"months": int(len(j)), "slope": float(b[2]), "nw_se": float(se), "t": float(b[2] / se)}


ADDITIONAL_TESTS.append(("flow_family", "PREREG_XASSET.md Amendment 2 (1284c08)", flow_family))
ADDITIONAL_TESTS.append(("flow_diagnostics", "PREREG_XASSET.md Amendment 2 (1284c08), outside the family",
                         flow_diagnostics))


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
            "us10": us10[(us10.index >= START) & (us10.index <= END)],
            "equity": {"r": r[r.index <= END], "rf": rf[rf.index <= END]},            # Amendment 2 targets
            "flow_conditions": checks["flow_conditions"]}


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
            res = run_all(synthetic_world(kappa, SEED), additional=False)["primary"]
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
