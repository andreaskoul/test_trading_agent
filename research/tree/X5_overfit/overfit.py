"""X5: overfitting diagnostics on development data only (PHASE3_PLAN.md L3.3).

Step 1  weekly IC matrices from saved development predictions (checked against RESULTS.jsonl) -> ICMAT.npz
Step 2  PBO by CSCV (Bailey, Borwein, Lopez de Prado, Zhu 2017), S = 16 contiguous blocks; coarse yearly CSCV  -> PBO.json
Step 3  deflated Sharpe ratio (Bailey, Lopez de Prado 2014) of the weekly IC series                          -> DSR.json
Step 4  James-Stein-type shrunk IC of each branch's best                                                      -> SHRINK.json
Step 5  calibration against the six holdout reads                                                             -> CALIBRATION.json
Run: python3 overfit.py [step ...]   (no args = all). Reads only harness.load() and saved files; writes only here.
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "3"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "3"); os.environ.setdefault("MKL_NUM_THREADS", "3")
import itertools
import json
import sys

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
sys.path.insert(0, TREE)
import harness  # noqa: E402

PRED_BRANCHES = ["D_ensembles", "M2_ipca", "M3_cae", "M4_sdf", "M5_graph", "M6_ssl"]
PHASE1 = ["A_loss", "B_arch", "C_features", "D_ensembles", "E_regime", "X1_combine", "X2_costs", "X3_online"]
PHASE2 = ["M1_dyntrade", "M2_ipca", "M3_cae", "M4_sdf", "M5_graph", "M6_ssl", "N1_fundamentals", "N2_short", "N3_intraday"]
YEARS = [str(y) for y in harness.VAL_YEARS]

# finalist -> (branch, config name, selection metric used, holdout IC/increment, holdout panel)
FINALISTS = {
    "X1_8p":      ("X1_combine", "8p_hgbD_mh+fmC_mh+mlpC_mh_panic", 114, 0.0224, "S&P 500 2020-25"),
    "D_hgb_mh":   ("D_ensembles", "hgb_multihorizon", 114, 0.0185, "S&P 500 2020-25"),
    "A_mse_rank": ("A_loss", "mse_rank", 114, 0.0078, "S&P 500 2020-25"),
    "M2_M05_U":   ("M2_ipca", "M05_C24_wk_xn_U", 251, 0.0183, "S&P 400 2019-25"),
    "M4_S04":     ("M4_sdf", "S04_X324_wk_mv", 251, 0.0033, "S&P 400 2019-25"),
    "N1_fm_fixed70": ("N1_fundamentals", "fm_fixed70", 251, -0.0001, "S&P 500 2020-25 (increment over MASTER)"),
}


def dump(obj, name):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(obj, f, indent=1, default=float)


def rows_of(branch):
    out = []
    for l in open(os.path.join(TREE, branch, "RESULTS.jsonl")):
        out.append(json.loads(l))
    return out


def metric_rows(branch):
    """The branch's trials on one metric. N1: the 9 increment-over-MASTER rows (its 14 single-characteristic rows are
    standalone ICs, a different metric). Others: rows with ic, ic_t and ic_by_year."""
    rs = rows_of(branch)
    if branch == "N1_fundamentals":
        return [dict(name=r["name"], m=r["increment"], t=r["increment_t"], weeks=r["weeks"], by=[r["increment_by_year"][y] for y in YEARS])
                for r in rs if "increment" in r and all(y in r["increment_by_year"] for y in YEARS)]
    return [dict(name=r["name"], m=r["ic"], t=r["ic_t"], weeks=r["weeks"], by=[r["ic_by_year"][y] for y in YEARS])
            for r in rs if "ic_t" in r and "ic_by_year" in r and r.get("weeks") and all(y in r["ic_by_year"] for y in YEARS)]


# ------------------------------------------------------------------ step 1
def step1():
    D = harness.load()
    rows = np.concatenate([harness.thursdays(D, int(y)) for y in YEARS])
    out, checks = {}, []
    for b in PRED_BRANCHES:
        res = {r["name"]: r for r in rows_of(b)}
        names, cols = [], []
        for n in res:
            f = os.path.join(TREE, b, f"pred_{n}.npy")
            if not os.path.exists(f):
                checks.append(dict(branch=b, name=n, status="no saved prediction"))
                continue
            p = np.load(f).astype(np.float64)
            assert p.shape == D["y5"].shape, (f, p.shape)
            ic = harness.weekly_ic(p, D, rows)
            got, want = float(np.nanmean(ic)), res[n]["ic"]
            ok = abs(got - want) < 5e-5
            checks.append(dict(branch=b, name=n, ic_recomputed=got, ic_logged=want, match=ok))
            if not ok:
                print("MISMATCH (excluded)", b, n, got, want)
                continue
            names.append(n); cols.append(ic)
        out[b] = (names, np.column_stack(cols))
        print(b, len(names), "configs")
    m = harness.weekly_ic(D["master_h5_ref"].astype(np.float64), D, rows)
    h = harness.weekly_ic(np.load(os.path.join(TREE, "M1_dyntrade", "base_hgb_multihorizon.npy")).astype(np.float64), D, rows)
    d_hgb = out["D_ensembles"][1][:, out["D_ensembles"][0].index("hgb_multihorizon")]
    checks.append(dict(branch="ref", name="MASTER", ic=float(np.nanmean(m))))
    checks.append(dict(branch="ref", name="M1 base_hgb_multihorizon equals D pred", max_abs_diff=float(np.nanmax(np.abs(h - d_hgb)))))
    np.savez(os.path.join(HERE, "ICMAT.npz"), master=m, rows=rows,
             **{f"{b}__ic": v[1] for b, v in out.items()}, **{f"{b}__names": np.array(v[0]) for b, v in out.items()})
    dump(checks, "ICMAT_CHECKS.json")


def icmat():
    z = np.load(os.path.join(HERE, "ICMAT.npz"))
    return {b: (list(z[f"{b}__names"]), z[f"{b}__ic"]) for b in PRED_BRANCHES}, z["master"]


# ------------------------------------------------------------------ step 2
def cscv(M, S=16, crit="mean", weights=None):
    """M: (T x N) per-period performance; S contiguous blocks; all C(S, S/2) IS sets. crit 'mean' or 't'."""
    T, N = M.shape
    blocks = np.array_split(np.arange(T), S) if weights is None else [np.array([i]) for i in range(T)]
    s1 = np.array([np.nansum(M[b], 0) for b in blocks])
    s2 = np.array([np.nansum(M[b] ** 2, 0) for b in blocks])
    c = np.array([np.isfinite(M[b]).sum(0) for b in blocks]).astype(float)
    def perf(J):
        n, a, q = c[J].sum(0), s1[J].sum(0), s2[J].sum(0)
        mu = a / n
        if crit == "mean":
            return mu
        sd = np.sqrt(np.maximum(q / n - mu ** 2, 1e-18) * n / (n - 1))
        return mu / sd
    lam, is_best, oos_best, oos_med = [], [], [], []
    sizes = [S // 2] if S % 2 == 0 else [S // 2, S // 2 + 1]
    for k in sizes:
        for J in itertools.combinations(range(S), k):
            J = list(J); Jc = [i for i in range(S) if i not in J]
            pi, po = perf(J), perf(Jc)
            n_star = int(np.argmax(pi))
            r = stats.rankdata(po)[n_star]          # 1 = worst
            w = r / (N + 1)
            lam.append(np.log(w / (1 - w)))
            is_best.append(pi[n_star]); oos_best.append(po[n_star]); oos_med.append(np.median(po))
    lam, is_best, oos_best = np.array(lam), np.array(is_best), np.array(oos_best)
    slope = float(np.polyfit(is_best, oos_best, 1)[0]) if len(lam) > 2 else None
    return dict(S=S, n_configs=N, n_splits=len(lam), crit=crit,
                pbo=float((lam <= 0).mean()), pbo_strict=float((lam < 0).mean()),
                logit=dict(mean=float(lam.mean()), median=float(np.median(lam)), sd=float(lam.std()),
                           q10=float(np.quantile(lam, .1)), q25=float(np.quantile(lam, .25)), q75=float(np.quantile(lam, .75)), q90=float(np.quantile(lam, .9))),
                is_best_mean=float(is_best.mean()), oos_best_mean=float(oos_best.mean()), oos_median_mean=float(np.mean(oos_med)),
                degradation_slope=slope, prob_oos_loss=float((oos_best < 0).mean()))


def step2():
    mats, _ = icmat()
    out = {"fine": {}, "coarse_yearly": {}}
    for b, (names, M) in mats.items():
        out["fine"][b] = {c: cscv(M, 16, c) for c in ("mean", "t")}
        out["fine"][b]["mean"]["is_best_overall"] = names[int(np.nanargmax(np.nanmean(M, 0)))]
    for b in PHASE1 + PHASE2:
        try:
            rs = metric_rows(b)
        except FileNotFoundError:
            continue
        if len(rs) < 3:
            continue
        Y = np.array([r["by"] for r in rs]).T        # 7 x N yearly ICs
        # S = 7 is odd: every split into 3 and 4 years, both ways (70 splits); yearly means weighted equally
        out["coarse_yearly"][b] = cscv(Y, S=7, crit="mean", weights="yearly")
        out["coarse_yearly"][b]["names_best_full"] = rs[int(np.argmax([r["m"] for r in rs]))]["name"]
    out["note"] = ("fine: weekly IC matrices rebuilt from saved predictions, 353 Thursdays 2013-2019, 16 contiguous blocks, "
                   "C(16,8)=12870 splits; PBO = share of splits where the IS-best has OOS logit <= 0 (pbo_strict: < 0). "
                   "coarse_yearly: the 7 yearly ICs in RESULTS.jsonl as blocks, all 3/4 splits both ways (70); "
                   "a coarse approximation, not the registered CSCV. N1 coarse uses the 9 increment-over-MASTER rows.")
    dump(out, "PBO.json")
    return out


# ------------------------------------------------------------------ step 3
EM = 0.5772156649


def sr0(var_sr, N):
    if N <= 1:
        return 0.0
    return float(np.sqrt(var_sr) * ((1 - EM) * stats.norm.ppf(1 - 1 / N) + EM * stats.norm.ppf(1 - 1 / (N * np.e))))


def dsr(sr, T, skew, kurt, var_sr, N):
    s0 = sr0(var_sr, N)
    z = (sr - s0) * np.sqrt(T - 1) / np.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2)
    return float(stats.norm.cdf(z)), s0


def all_sr(branches):
    srs = []
    for b in branches:
        for r in metric_rows(b):
            if r["weeks"] and np.isfinite(r["t"]) and r["t"] != 0:
                srs.append(r["t"] / np.sqrt(r["weeks"]))
    return np.array(srs)


def step3():
    mats, master = icmat()
    moments = {}
    for b, (names, M) in mats.items():
        for j, n in enumerate(names):
            x = M[:, j][np.isfinite(M[:, j])]
            moments[(b, n)] = (float(stats.skew(x)), float(stats.kurtosis(x, fisher=False)), float(x.mean() / x.std(ddof=1)), len(x))
    sk_med = float(np.median([v[0] for v in moments.values()])); ku_med = float(np.median([v[1] for v in moments.values()]))
    cum = {114: all_sr(PHASE1), 251: all_sr(PHASE1 + PHASE2)}
    out = {"pooled_moments_of_saved_series": dict(skew_median=sk_med, kurt_median=ku_med, n_series=len(moments)),
           "cumulative_trials": {str(k): dict(n_with_t=len(v), var_sr=float(v.var(ddof=1)), sd_sr=float(v.std(ddof=1))) for k, v in cum.items()},
           "finalists": {}}
    for f, (b, n, ncum, _, _) in FINALISTS.items():
        rs = metric_rows(b)
        srb = np.array([r["t"] / np.sqrt(r["weeks"]) for r in rs])
        me = [r for r in rs if r["name"] == n][0]
        if (b, n) in moments:
            sk, ku, sr, T = moments[(b, n)]; src = "weekly series rebuilt from saved predictions"
        else:
            sr, T = me["t"] / np.sqrt(me["weeks"]), me["weeks"]
            sk, ku = sk_med, ku_med; src = "no saved predictions: SR = t/sqrt(weeks) from RESULTS.jsonl; skew/kurt = median of the saved weekly IC series"
            if b == "N1_fundamentals":
                src += "; N1's t is Newey-West, so SR is approximate"
        rb, s0b = dsr(sr, T, sk, ku, srb.var(ddof=1), len(srb))
        rc, s0c = dsr(sr, T, sk, ku, cum[ncum].var(ddof=1), ncum)
        rn, _ = dsr(sr, T, 0.0, 3.0, srb.var(ddof=1), len(srb))
        out["finalists"][f] = dict(branch=b, config=n, sr_weekly=sr, sr_annual=sr * np.sqrt(52), T=T, skew=sk, kurt=ku, moments_source=src,
                                   psr_vs_0=dsr(sr, T, sk, ku, 0, 1)[0],
                                   n_branch=len(srb), var_sr_branch=float(srb.var(ddof=1)), sr0_branch=s0b, dsr_branch=rb, dsr_branch_normal=rn,
                                   n_cum=ncum, var_sr_cum=float(cum[ncum].var(ddof=1)), sr0_cum=s0c, dsr_cum=rc)
    x = master[np.isfinite(master)]
    sr = x.mean() / x.std(ddof=1)
    out["MASTER_reference"] = dict(sr_weekly=float(sr), psr_vs_0=dsr(sr, len(x), float(stats.skew(x)), float(stats.kurtosis(x, fisher=False)), 0, 1)[0],
                                   note="single pre-existing model, N = 1: the deflated Sharpe is the probabilistic Sharpe against 0")
    out["note"] = ("Return series = weekly rank IC (N1: weekly increment over MASTER). SR per week. V[SR] over the branch's logged "
                   "configurations (SR = t/sqrt(weeks)) or over all logged rows with a t up to that phase (114 / 251 rows counted as N; "
                   "M1 book rows and DML rows have no t and add to N but not to V). Kurtosis non-excess.")
    dump(out, "DSR.json")
    return out


# ------------------------------------------------------------------ step 4
def step4():
    mats, _ = icmat()
    out = {}
    for f, (b, n, _, _, _) in FINALISTS.items():
        rs = metric_rows(b)
        m = np.array([r["m"] for r in rs]); t = np.array([r["t"] for r in rs])
        ok = np.abs(t) > 0.2
        se2 = (m[ok] / t[ok]) ** 2
        noise, between = float(np.mean(se2)), float(np.var(m, ddof=1))
        best = [r["m"] for r in rs if r["name"] == n][0]
        gm = float(m.mean())
        B = max(0.0, 1 - noise / between)
        row = dict(branch=b, config=n, n=len(m), dev=best, grand_mean=gm, var_between=between, var_noise=noise, B=B,
                   shrunk=gm + B * (best - gm), shrunk_over_dev=(gm + B * (best - gm)) / best)
        if b in mats:   # variant: noise of each configuration's deviation from the branch's weekly mean
            names, M = mats[b]
            dev = M - np.nanmean(M, 1, keepdims=True)
            nz = float(np.mean(np.nanvar(dev, 0, ddof=1) / np.isfinite(dev).sum(0)))
            Bp = max(0.0, 1 - nz / between)
            row.update(var_noise_paired=nz, B_paired=Bp, shrunk_paired=gm + Bp * (best - gm))
        out[f] = row
    out["note"] = ("shrunk = grand mean + max(0, 1 - s2_noise/s2_between) x (finalist - grand mean). s2_noise = mean squared SE "
                   "(m/t) over the branch's configurations (|t| > 0.2; iid t; N1 Newey-West). s2_between = variance of the configurations' "
                   "mean metric (total, so it already contains noise). _paired variant (saved predictions only): noise of each "
                   "configuration's weekly deviation from the branch mean, i.e. ignoring the noise common to all configurations.")
    dump(out, "SHRINK.json")
    return out


# ------------------------------------------------------------------ step 5
def step5():
    P, Dd, Sh = (json.load(open(os.path.join(HERE, x))) for x in ("PBO.json", "DSR.json", "SHRINK.json"))
    tab = []
    for f, (b, n, ncum, hold, panel) in FINALISTS.items():
        sh, ds = Sh[f], Dd["finalists"][f]
        fine = P["fine"].get(b)
        row = dict(finalist=f, branch=b, n_branch=sh["n"], dev=sh["dev"], holdout=hold, panel=panel, retention=hold / sh["dev"],
                   pbo_cscv16_mean=fine["mean"]["pbo"] if fine else None, pbo_cscv16_t=fine["t"]["pbo"] if fine else None,
                   pbo_yearly_coarse=P["coarse_yearly"][b]["pbo"], degradation_slope_yearly=P["coarse_yearly"][b]["degradation_slope"],
                   psr=ds["psr_vs_0"], dsr_branch=ds["dsr_branch"], dsr_cum=ds["dsr_cum"], n_cum=ncum,
                   shrunk=sh["shrunk"], shrunk_over_dev=sh["shrunk_over_dev"], shrunk_paired=sh.get("shrunk_paired"))
        tab.append(row)
    ret = np.array([r["retention"] for r in tab])
    corr = {}
    for k in ("pbo_yearly_coarse", "dsr_branch", "dsr_cum", "shrunk_over_dev", "shrunk", "psr", "dev"):
        v = np.array([r[k] for r in tab], float)
        corr[k] = float(stats.spearmanr(v, ret)[0])
    held = np.array([r["holdout"] for r in tab])
    corr["shrunk_vs_holdout_level"] = float(stats.spearmanr([r["shrunk"] for r in tab], held)[0])
    corr["dev_vs_holdout_level"] = float(stats.spearmanr([r["dev"] for r in tab], held)[0])
    out = dict(table=tab, spearman_with_retention_n6=corr,
               MASTER_reference=dict(dev=0.0125, holdout=0.0326, retention=0.0326 / 0.0125, psr=Dd["MASTER_reference"]["psr_vs_0"]),
               note="six points; Spearman values are descriptive only (with n = 6, |rho| must reach 0.886 for p < 0.05 two-sided).")
    dump(out, "CALIBRATION.json")
    return out


if __name__ == "__main__":
    steps = sys.argv[1:] or ["1", "2", "3", "4", "5"]
    for s in steps:
        r = globals()[f"step{s}"]()
        print(f"step {s} done")
