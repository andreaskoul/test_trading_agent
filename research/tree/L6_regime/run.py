"""Layer 6 T2 runner.  OMP_NUM_THREADS=3 python3 research/tree/L6_regime/run.py <stage> [args]

stages:
  build                 dev weekly series (dev.npz master_h5_ref, L4_exploit simulator) -> .cache/tree/l6r/dev_weekly.parquet
  check_ledger          2020-2025 book from the L4 simulator vs b0_audit_runner/weekly_b0_ledger.csv book_net_return
  model <hmm2|hmm3|msr2> development walk-forward -> .cache/tree/l6r/dev_<cfg>.parquet + fits json
  leak <cfg>            leakage test
  gate                  development gate for the three configurations -> RESULT.json
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "3")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
sys.path.insert(0, HERE)
sys.path.insert(0, TREE)
import lib as L  # noqa: E402
from holdout2 import load_module  # noqa: E402

X = load_module(os.path.join(TREE, "L4_exploit", "run.py"), "l4x_sim")
K = X.K
CACHE = os.path.join(ROOT, ".cache", "tree", "l6r")
DEV_YEARS = range(2009, 2020)
CFG = {"hmm2": ("hmm", 2), "hmm3": ("hmm", 3), "msr2": ("msr", 2)}


def log(*a):
    print(datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def state(**kw):
    p = os.path.join(HERE, "STATE.json")
    st = json.load(open(p))
    for k, v in kw.items():
        st[k] = st.get(k, []) + v if k == "done" else v
    st["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(st, open(p, "w"), indent=1)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_dev():
    z = np.load(os.path.join(ROOT, ".cache", "tree", "dev.npz"), allow_pickle=False)
    d = {k: z[k] for k in z.files}
    d["S"] = pd.DatetimeIndex(d["S"])
    d["names"] = [str(n) for n in d["names"]]
    for k in ("r", "rm", "beta", "y5", "master_h5_ref"):
        d[k] = d[k].astype(np.float64)
    d["spy"] = np.cumprod(1 + np.nan_to_num(d["rm"]))          # price level for the core's 200-day rule (book unaffected)
    return d


def dev_weekly(d, rf):
    K.GROSS_SIDE = X.SIDE0
    score = d["master_h5_ref"]
    G = []

    def builder(t, dd, sc, ok, st):                   # book_decile, recording the book gross sum|w| + |w_spy|
        w = X.book_decile(t, dd, sc, ok, st)
        G.append(float(np.abs(w).sum() + abs((w * np.nan_to_num(dd["beta"][t], nan=1.0)).sum())))
        return w
    bk = X.sim(d, score, builder, DEV_YEARS, rf=rf)
    ref = X.sim(d, score, X.book_decile, DEV_YEARS, rf=rf)
    assert np.array_equal(bk.book.to_numpy(), ref.book.to_numpy())
    W = L.weekly_states(d, score, bk, DEV_YEARS)
    W["G"] = G
    W["days"] = bk.days.to_numpy()
    return W


def build():
    os.makedirs(CACHE, exist_ok=True)
    d = load_dev()
    rf = K.ST.dtb3()
    W = dev_weekly(d, rf)
    p = os.path.join(CACHE, "dev_weekly.parquet")
    W.to_parquet(p)
    fb = W.b.first_valid_index()
    log("built", W.shape, "first b", fb, "sha", sha(p)[:12])
    log(W.describe().T)
    state(done=[f"dev weekly series built: {len(W)} weeks, first b {fb.date()}, sha256 {sha(p)}"])


def check_ledger():
    d = K.T.build()
    rf = K.ST.dtb3()
    K.GROSS_SIDE = X.SIDE0
    master = np.load(os.path.join(X.QTC, "sp500_tf_master_h5.npz"))["h5"].astype(np.float64)
    bk = X.sim(d, master, X.book_decile, range(2020, 2026), rf=rf)
    led = pd.read_csv(os.path.join(TREE, "L4_exploit", "b0_audit_runner", "weekly_b0_ledger.csv"), parse_dates=["date"]).set_index("date")
    j = bk.join(led[["book_net_return"]], how="inner")
    diff = (j.book - j.book_net_return).abs()
    res = {"weeks_sim": len(bk), "weeks_ledger": len(led), "weeks_matched": len(j), "max_abs_diff": float(diff.max()),
           "mean_book_sim": float(j.book.mean()), "mean_book_ledger": float(j.book_net_return.mean())}
    log("ledger", res)
    json.dump(res, open(os.path.join(CACHE, "ledger_check.json"), "w"), indent=1)
    # also save the 2020-2025 weekly states only if needed later (not read here: book series only, no model output)
    state(done=[f"ledger check 2020-2025 book vs book_net_return: {res}"])


def model(cfg, W=None, last_k=None, tag=""):
    kind, k = CFG[cfg]
    if W is None:
        W = pd.read_parquet(os.path.join(CACHE, "dev_weekly.parquet"))
    df, fits = L.walk(W, kind, K=k, last_k=last_k, log=None if tag else log)
    df["pi"], nfb = L.exposure(df.raw.to_numpy())
    df["b"] = W.b.to_numpy()[df.k.to_numpy()]
    df["G"] = W.G.to_numpy()[df.k.to_numpy()]
    df["days"] = W.days.to_numpy()[df.k.to_numpy()]
    if not tag:
        df.to_parquet(os.path.join(CACHE, f"dev_{cfg}.parquet"))
        json.dump({"fits": fits, "fallback_weeks_mean_raw_le_0": nfb}, open(os.path.join(CACHE, f"dev_{cfg}_fits.json"), "w"),
                  indent=1, default=float)
        state(done=[f"{cfg} development walk-forward: {len(df)} weeks, {len(fits)} refits"])
    return df


def leak(cfg):
    """Perturb all panel data after a cutoff; every pi_t with t <= cutoff must be unchanged (exact)."""
    d0 = load_dev()
    rf = K.ST.dtb3()
    S = d0["S"]
    out = {}
    for cut_date in ("2016-06-30", "2018-03-29"):
        tc = int(np.where(S == pd.Timestamp(cut_date))[0][0])
        res = {}
        for name, mode in (("future", "after"), ("power_check_past", "at")):
            d = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in d0.items()}
            rng = np.random.default_rng(7)
            if mode == "after":
                sl = slice(tc + 1, None)
                rows_y5 = np.arange(len(S)) + 6 > tc          # y5 rows realised after the cutoff
            else:
                sl = slice(tc - 9, tc + 1)                      # perturb the last 10 sessions up to the cutoff
                rows_y5 = (np.arange(len(S)) + 6 > tc - 10) & (np.arange(len(S)) + 6 <= tc)
            for k in ("r",):
                d[k][sl] = d[k][sl] + 0.05 * rng.standard_normal(d[k][sl].shape)
            d["rm"][sl] = d["rm"][sl] + 0.05 * rng.standard_normal(d["rm"][sl].shape)
            d["beta"][sl] = d["beta"][sl] * rng.uniform(0.5, 1.5, d["beta"][sl].shape)
            d["master_h5_ref"][sl] = rng.standard_normal(d["master_h5_ref"][sl].shape)
            d["y5"][rows_y5] = d["y5"][rows_y5] + 0.05 * rng.standard_normal(d["y5"][rows_y5].shape)
            d["spy"] = np.cumprod(1 + np.nan_to_num(d["rm"]))
            Wp = dev_weekly(d, rf)
            W0 = dev_weekly(d0, rf)
            last_k = int(np.where(W0.t.to_numpy() <= tc)[0].max())
            a = model(cfg, W0, last_k=last_k, tag="leak")
            b = model(cfg, Wp, last_k=last_k, tag="leak")
            res[name] = {"weeks_compared": len(a), "max_abs_pi_diff": float(np.abs(a.pi - b.pi).max()),
                         "identical": bool(np.array_equal(a.pi.to_numpy(), b.pi.to_numpy())),
                         "max_abs_raw_diff": float(np.abs(a.raw - b.raw).max())}
            log(cfg, cut_date, name, res[name])
        out[cut_date] = res
    json.dump(out, open(os.path.join(CACHE, f"leak_{cfg}.json"), "w"), indent=1)
    ok = all(v["future"]["identical"] for v in out.values())
    power = all(not v["power_check_past"]["identical"] for v in out.values())
    state(done=[f"leakage test {cfg}: future perturbation leaves pi unchanged: {ok}; past perturbation changes pi (test can fail): {power}"])


def gate_one(df):
    g = df[(df.index.year >= 2015) & (df.index.year <= 2019)]
    sel = (df.index.year >= 2015) & (df.index.year <= 2019)
    sc = 7 / g.days.to_numpy()                           # L4 wk convention: period return x 7/days
    pi, b = g.pi.to_numpy(), g.b.to_numpy() * sc
    x = L.timed(df.pi.to_numpy(), df.b.to_numpy(), df.G.to_numpy())[sel] * sc
    xm = x / pi.mean()                                   # matched average exposure (unit mean in the window)
    dif = xm - b
    hz = X.lw_hac_test(xm, b)
    nwd = X.nw(dif)
    yrs = {int(y): float(v) for y, v in pd.Series(dif, index=g.index).groupby(g.index.year).mean().items()}
    npos = sum(v > 0 for v in yrs.values())
    sh = lambda a: float(a.mean() / a.std(ddof=1) * 52 ** .5)
    return {"weeks": int(len(g)), "first_week": str(g.index[0].date()), "last_week": str(g.index[-1].date()),
            "mean_pi": float(pi.mean()), "sd_pi": float(pi.std(ddof=1)), "share_pi_0": float((pi == 0).mean()),
            "share_pi_2": float((pi == 2).mean()),
            "corr_pi_next_b": float(np.corrcoef(pi, b)[0, 1]),
            "timed_book_sharpe": sh(xm), "untimed_book_sharpe": sh(b),
            "timed_book_pct_per_year_arith": 100 * 52 * float(xm.mean()), "untimed_book_pct_per_year_arith": 100 * 52 * float(b.mean()),
            "diff_pct_per_year_arith": 100 * 52 * nwd[0], "diff_nw_t": nwd[1],
            "lw2008_hac": hz, "diff_by_year_pct_per_year": {y: 100 * 52 * v for y, v in yrs.items()},
            "years_positive": npos, "timing_cost_pct_per_year": 100 * 52 * float((pi * b - x).mean() / pi.mean()),
            "pass_t": bool(hz["z"] >= 2.0), "pass_years": bool(npos >= 3), "pass": bool(hz["z"] >= 2.0 and npos >= 3)}


def gate():
    res = {"label": "development, 2015-2019 after a 104-week burn-in (MASTER as-run scores, dev.npz master_h5_ref)",
           "configs": {}}
    for cfg in CFG:
        df = pd.read_parquet(os.path.join(CACHE, f"dev_{cfg}.parquet"))
        fits = json.load(open(os.path.join(CACHE, f"dev_{cfg}_fits.json")))
        r = gate_one(df)
        F = fits["fits"]
        r["refits"] = len(F)
        r["fallback_weeks_mean_raw_le_0"] = fits["fallback_weeks_mean_raw_le_0"]
        r["bic_first_last"] = [F[0]["bic"], F[-1]["bic"]]
        r["persistence_median_by_state"] = np.median([f["persistence"] for f in F], 0).tolist()
        r["share_filtered_argmax_median_by_state"] = np.median([f["share_filtered_argmax"] for f in F], 0).tolist()
        lk = os.path.join(CACHE, f"leak_{cfg}.json")
        r["leakage_test"] = json.load(open(lk)) if os.path.exists(lk) else "not run"
        res["configs"][cfg] = r
        log(cfg, {k: r[k] for k in ("timed_book_sharpe", "untimed_book_sharpe", "diff_pct_per_year_arith", "years_positive", "pass")},
            "z", round(r["lw2008_hac"]["z"], 3))
    res["any_pass"] = any(v["pass"] for v in res["configs"].values())
    res["refit_records"] = {cfg: json.load(open(os.path.join(CACHE, f"dev_{cfg}_fits.json")))["fits"] for cfg in CFG}
    res["inputs"] = {"dev_weekly_sha256": sha(os.path.join(CACHE, "dev_weekly.parquet")),
                     "ledger_check": json.load(open(os.path.join(CACHE, "ledger_check.json")))}
    json.dump(res, open(os.path.join(HERE, "RESULT.json"), "w"), indent=1, default=float)
    state(done=[f"development gate: any pass {res['any_pass']}; " +
                "; ".join(f"{c}: z {v['lw2008_hac']['z']:.2f}, years+ {v['years_positive']}" for c, v in res["configs"].items())])


if __name__ == "__main__":
    if sys.argv[1] == "gate":
        gate()
        sys.exit()
    st = sys.argv[1]
    if st == "build":
        build()
    elif st == "check_ledger":
        check_ledger()
    elif st == "model":
        model(sys.argv[2])
    elif st == "leak":
        leak(sys.argv[2])
