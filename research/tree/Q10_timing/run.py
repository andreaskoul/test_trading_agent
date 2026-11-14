"""Q10_timing (PREREG Layer 3, Amendment 10): Nagel (2012) liquidity-provision timing of the D_hgb_mh decile book.

Development data only (harness.load(), ends 2019-12-31). Every rule is in STATE.json "plan", fixed before scoring.
    OMP_NUM_THREADS=3 python3 research/tree/Q10_timing/run.py
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
sys.path.insert(0, TREE)
sys.path.insert(0, os.path.join(TREE, "M1_dyntrade"))
import harness  # noqa: E402
import lib  # noqa: E402  (M1_dyntrade)

COST = harness.COST
BURN, LAGS = 104, 4
PRED = os.path.join(TREE, "M1_dyntrade", "base_hgb_multihorizon.npy")
OUT = os.path.join(ROOT, ".cache", "tree", "preds", "Q10_timing")


# ---------------------------------------------------------------- statistics
def nw_var(u, lags=LAGS):
    """Newey-West long-run covariance of the rows of u (T x k), Bartlett weights."""
    u = np.atleast_2d(u.T).T
    u = u - u.mean(0)
    T = len(u)
    S = u.T @ u / T
    for l in range(1, lags + 1):
        G = u[l:].T @ u[:-l] / T
        S += (1 - l / (lags + 1)) * (G + G.T)
    return S


def ols_nw(y, x):
    X = np.column_stack([np.ones(len(x)), x])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    XtXi = np.linalg.inv(X.T @ X / len(y))
    V = XtXi @ nw_var(X * e[:, None]) @ XtXi / len(y)
    return b, b / np.sqrt(np.diag(V))


def ols(y, x):
    X = np.column_stack([np.ones(len(x)), x])
    return np.linalg.lstsq(X, y, rcond=None)[0]


def nw_t_mean(d):
    return float(d.mean() / np.sqrt(nw_var(d[:, None])[0, 0] / len(d)))


def sharpe(r):
    return float(r.mean() / r.std(ddof=1) * np.sqrt(52))


def sharpe_diff(r1, r2):
    """Lo (2002) delta method for SR1 - SR2: HAC (NW, 4 lags) on moments (r1, r2, r1^2, r2^2); iid (Memmel) too."""
    T = len(r1)
    g = np.column_stack([r1, r2, r1 ** 2, r2 ** 2])
    m = g.mean(0)
    sr, grad = [], np.zeros(4)
    for i in (0, 1):
        mu, s = m[i], m[i + 2]
        sig = np.sqrt(s - mu * mu)
        sr.append(mu / sig)
        sgn = 1 if i == 0 else -1
        grad[i] = sgn * s / sig ** 3
        grad[i + 2] = sgn * (-mu / (2 * sig ** 3))
    d = (sr[0] - sr[1]) * np.sqrt(52)
    se_hac = float(np.sqrt(grad @ nw_var(g) @ grad / T) * np.sqrt(52))
    rho = np.corrcoef(r1, r2)[0, 1]
    v_iid = (2 - 2 * rho + 0.5 * (sr[0] ** 2 + sr[1] ** 2 - 2 * sr[0] * sr[1] * rho ** 2)) / T
    se_iid = float(np.sqrt(v_iid) * np.sqrt(52))
    return {"diff": float(d), "se_lo_hac": se_hac, "z_lo_hac": float(d / se_hac), "se_lo_iid": se_iid,
            "z_lo_iid": float(d / se_iid), "corr_weekly": float(rho)}


def worst_fall(r):
    w = np.cumprod(1 + r)
    w = np.concatenate([[1.0], w])
    return float(np.max(1 - w / np.maximum.accumulate(w)))


def stats(r):
    return {"pct_per_year": float(52 * r.mean() * 100), "vol_pct_per_year": float(r.std(ddof=1) * np.sqrt(52) * 100),
            "net_sharpe": sharpe(r), "worst_fall_pct": worst_fall(r) * 100, "weeks": int(len(r))}


# ---------------------------------------------------------------- data
def variables(D, rows):
    r, rm, el = D["r"].astype(np.float64), D["rm"].astype(np.float64), D["elig"]
    disp, vol = [], []
    for s in rows:
        g = np.prod(1 + r[s - 4:s + 1], 0) - 1
        m = el[s] & np.isfinite(g)
        disp.append(np.std(g[m], ddof=1))
        vol.append(np.std(rm[s - 20:s + 1], ddof=1) * np.sqrt(252))
    return np.array(disp), np.array(vol)


def exposure_paths(b, x, rows):
    """Candidate and Moreira-Muir raw signals and exposures from expanding fits on weeks whose return is known."""
    n = len(b)
    raw_c, raw_m = np.full(n, np.nan), np.full(n, np.nan)
    floor_hits = 0
    for j in range(BURN, n):
        k = np.array([i for i in range(j) if rows[i] + 6 <= rows[j] and np.isfinite(x[i])])
        a, c = ols(b[k], x[k])
        a2, c2 = ols(b[k] ** 2, x[k])
        mu, m2 = a + c * x[j], a2 + c2 * x[j]
        s2 = m2 - mu * mu
        fl = 0.1 * np.var(b[k], ddof=1)
        if s2 < fl:
            s2, floor_hits = fl, floor_hits + 1
        raw_c[j], raw_m[j] = mu / s2, 1.0 / s2
    out = {}
    for name, raw in (("cand", raw_c), ("mm", raw_m)):
        e = np.full(n, np.nan)
        neg = 0
        for j in range(BURN, n):
            mbar = raw[BURN:j + 1].mean()
            if mbar <= 0:
                e[j], neg = 0.5, neg + 1
            else:
                e[j] = np.clip(raw[j] / mbar, 0.5, 2.0)
        out[name] = {"e": e, "raw": raw, "mean_le0_weeks": neg}
    out["sigma2_floor_weeks"] = floor_hits
    return out


def net_of(b, e):
    de = np.abs(np.diff(e, prepend=e[0]))
    return e * b - COST * de


def main():
    t0 = time.time()
    D = harness.load()
    assert D["S"][-1] <= np.datetime64("2019-12-31")
    pred = np.load(PRED).astype(np.float64)
    sc = harness.score(pred, "D_hgb_mh check", D=D)
    assert abs(sc["ic"] - 0.023568388085769547) < 5e-5, sc["ic"]   # saved as float32 (D_ensembles/lib.py:264): ~10% ties
    rows = lib.val_rows(D, pred)
    b = harness.decile_net(pred, D, rows)
    assert len(b) == len(rows)
    W = np.array([lib.aim_decile(pred[t], lib.mask(pred, D, t)) for t in rows])
    sim = lib.simulate(W, D, rows)
    S = D["S"]
    dates = [str(S[t].date()) for t in rows]
    xd, xv = variables(D, rows)
    # lag one week: x for week j is the value at the previous scored Thursday
    lag = {"DISP": np.concatenate([[np.nan], xd[:-1]]), "SPYVOL": np.concatenate([[np.nan], xv[:-1]])}
    res = {"label": "DEVELOPMENT DATA 2013-2019, NOT OUT OF SAMPLE", "check": {
        "ic": sc["ic"], "decile_net_pct_per_year": sc["decile_net_pct_per_year"],
        "decile_net_sharpe": sc["decile_net_sharpe"], "book_weeks": len(b), "first_week": dates[0],
        "last_week": dates[-1],
        "max_abs_diff_harness_vs_exact_weights_net": float(np.max(np.abs(b - sim["net"])))},
        "burn_in_weeks": BURN, "test_start": dates[BURN], "test_end": dates[-1], "test_weeks": len(b) - BURN,
        "step1": {}, "step2": {}}
    weekly = {"rows": rows, "book": b, "DISP": lag["DISP"], "SPYVOL": lag["SPYVOL"]}
    tw = np.arange(BURN, len(b))
    years = np.array([S[rows[j]].year for j in tw])
    for vname, x in lag.items():
        ok = np.isfinite(x)
        s1 = {}
        for tgt, y in (("return", b), ("square", b ** 2)):
            co, t = ols_nw(y[ok], x[ok])
            path = {}
            for yr in range(2014, 2020):
                kk = ok & (np.array([S[t_].year for t_ in rows]) <= yr)
                path[str(yr)] = float(ols(y[kk], x[kk])[1])
            s1[tgt] = {"intercept": float(co[0]), "slope": float(co[1]), "slope_nw_t": float(t[1]),
                       "x_mean": float(x[ok].mean()), "x_sd": float(x[ok].std(ddof=1)),
                       "slope_x_1sd_pct_per_week": float(co[1] * x[ok].std(ddof=1) * 100),
                       "expanding_slope_at_year_end": path, "weeks": int(ok.sum())}
        res["step1"][vname] = s1
        P = exposure_paths(b, x, rows)
        ec, em = P["cand"]["e"][tw], P["mm"]["e"][tw]
        g = ec.mean()
        econst = np.full(len(tw), g)
        emm = em * g / em.mean()
        bt = b[tw]
        nc, nk, nm = net_of(bt, ec), net_of(bt, econst), net_of(bt, emm)
        weekly[vname + "_e_cand"], weekly[vname + "_e_mm"] = P["cand"]["e"], P["mm"]["e"]
        # exact-weights sensitivity: weights e_j * decile weights through the M1 simulator
        exact = {}
        for nme, e in (("cand", ec), ("const", econst), ("mm", emm)):
            Wj = W[tw] * e[:, None]
            exact[nme] = lib.simulate(Wj, D, rows[tw])["net"]
        s2 = {"mean_gross": float(g), "mm_scale": float(g / em.mean()),
              "share_weeks_at_floor_0.5": float((ec <= 0.5 + 1e-12).mean()),
              "share_weeks_at_cap_2": float((ec >= 2 - 1e-12).mean()),
              "mm_share_floor": float((em <= 0.5 + 1e-12).mean()), "mm_share_cap": float((em >= 2 - 1e-12).mean()),
              "weeks_expanding_mean_le0": P["cand"]["mean_le0_weeks"], "weeks_sigma2_floor": P["sigma2_floor_weeks"],
              "corr_exposure_cand_vs_mm": float(np.corrcoef(ec, em)[0, 1]),
              "exposure_change_cost_pct_per_year": {"cand": float(52 * COST * np.abs(np.diff(ec)).mean() * 100),
                                                    "mm": float(52 * COST * np.abs(np.diff(emm)).mean() * 100)},
              "candidate": stats(nc), "constant": stats(nk), "moreira_muir": stats(nm),
              "vs_constant": {**sharpe_diff(nc, nk), "pct_per_year_diff": float(52 * (nc - nk).mean() * 100),
                              "paired_nw_t": nw_t_mean(nc - nk)},
              "vs_moreira_muir": {**sharpe_diff(nc, nm), "pct_per_year_diff": float(52 * (nc - nm).mean() * 100),
                                  "paired_nw_t": nw_t_mean(nc - nm)},
              "exact_weights_sensitivity": {k: stats(v) for k, v in exact.items()},
              "by_year": {}}
        for yr in sorted(set(years)):
            m = years == yr
            s2["by_year"][str(int(yr))] = {
                "weeks": int(m.sum()), "mean_exposure_cand": float(ec[m].mean()),
                **{f"{k}_pct_per_year": float(52 * v[m].mean() * 100) for k, v in
                   (("cand", nc), ("const", nk), ("mm", nm))},
                **{f"{k}_sharpe": sharpe(v[m]) for k, v in (("cand", nc), ("const", nk), ("mm", nm))}}
        zs = [s2["vs_constant"]["z_lo_hac"], s2["vs_moreira_muir"]["z_lo_hac"]]
        s2["pass"] = bool(all(z >= 1.96 for z in zs))
        res["step2"][vname] = s2
    from scipy.stats import norm
    p = {v: max(2 * norm.sf(abs(res["step2"][v][c]["z_lo_hac"])) for c in ("vs_constant", "vs_moreira_muir"))
         for v in lag}
    order = sorted(p, key=p.get)
    holm = {}
    for i, v in enumerate(order):
        holm[v] = min(1.0, max(p[v] * (len(order) - i), holm.get(order[i - 1], 0) if i else 0))
    res["holm_descriptive"] = {"p_max_over_controls": p, "holm_adjusted": holm}
    res["passes"] = [v for v in lag if res["step2"][v]["pass"]]
    res["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    res["seconds"] = round(time.time() - t0, 1)
    os.makedirs(OUT, exist_ok=True)
    np.savez(os.path.join(OUT, "weekly.npz"), **{k: np.asarray(v) for k, v in weekly.items()})
    with open(os.path.join(HERE, "RESULT.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
