"""Branch Q9_horizon (Layer 3, Amendment 10): longer horizons and the turnover / IC frontier.
Development data only (S&P 500, harness.load(), ends 2019-12-31; walk-forward 2013-2019, annual refits, seeds 0-2).

    OMP_NUM_THREADS=3 nohup python3 research/tree/Q9_horizon/run.py preds > research/tree/Q9_horizon/run.log 2>&1 &
    OMP_NUM_THREADS=3 python3 research/tree/Q9_horizon/run.py books

Stage "preds": one walk-forward score panel per configuration, saved to .cache/tree/preds/Q9_horizon/<cfg>.npy
(checkpoint per configuration; member fits cached per (horizon, year, seed)).
Stage "books": decile and hysteresis books, all measures, RESULTS.jsonl and RESULT.json.
"""
import importlib.util
import json
import math
import os
import sys
import time

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(v, "3")

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
sys.path.insert(0, TREE)
import harness  # noqa: E402

PREDS = os.path.join(ROOT, ".cache", "tree", "preds", "Q9_horizon")
MEMB = os.path.join(PREDS, "members")
X1CACHE = os.path.join(TREE, "X1_combine", "cache")          # read only
STATE = os.path.join(HERE, "STATE.json")
RESULTS = os.path.join(HERE, "RESULTS.jsonl")
RESULT = os.path.join(HERE, "RESULT.json")
FLAT14 = 14e-4


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


x1 = _mod("x1lib_q9", os.path.join(TREE, "X1_combine", "lib.py"))
q6 = _mod("q6lib_q9", os.path.join(TREE, "Q6_trade", "lib.py"))
m1 = q6.m1

CONFIGS = {
    "h21": [21],
    "h63": [63],
    "mix_5_21_63": [5, 21, 63],
    "ref_mh_3_5_10_20": [3, 5, 10, 20],
}
ORDER = ("ref_mh_3_5_10_20", "h21", "h63", "mix_5_21_63")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def state(**kw):
    s = json.load(open(STATE))
    for k, v in kw.items():
        if k == "done":
            s["done"].append(v)
        else:
            s[k] = v
    s["updated"] = now()
    json.dump(s, open(STATE, "w"), indent=1)


# ---------------------------------------------------------------- targets (as dev y5 is built)
_Y = {}


def resid(D, h):
    """research/quant_trials/sp500_test.py resid(h) on the development arrays: sum of r over rows t+2..t+1+h minus
    beta[t] x the same sum of SPY returns; NaN unless eligible at t and a valid close at t and t+1+h; demeaned across
    names. resid(D, 5) reproduces D['y5'] (max |diff| 1.3e-7)."""
    if h in _Y:
        return _Y[h]
    r, rm = D["r"].astype(np.float64), D["rm"].astype(np.float64)
    beta, valid, elig = D["beta"].astype(np.float64), D["valid"], D["elig"]
    T = len(r)
    cr = np.vstack([np.zeros((1, r.shape[1])), np.cumsum(np.nan_to_num(r), 0)])
    cm = np.concatenate([[0], np.cumsum(np.nan_to_num(rm))])
    y = np.full(r.shape, np.nan)
    d = np.arange(T - 1 - h)
    a, b = d + 2, d + 2 + h
    y[d] = (cr[b] - cr[a]) - beta[d] * (cm[b] - cm[a])[:, None]
    ok = np.zeros_like(valid)
    ok[:T - 1 - h] = valid[1 + h:] & valid[:T - 1 - h]
    y[~(ok & elig)] = np.nan
    with np.errstate(all="ignore"):
        y = y - np.nanmean(y, 1, keepdims=True)
    _Y[h] = y
    return y


_orig_target = x1.target


def target(D, h, te):
    if h not in (21, 63):
        return _orig_target(D, h, te)                 # the reference's members, unchanged
    y = resid(D, h).copy()
    y[max(0, te + 5 - h + 1):] = np.nan               # window t+2..t+1+h must end <= te+6 (before the year starts)
    return y


x1.target = target


def member(h, D, te, rows, seed):
    k = ("hgb", "D", h, int(te), int(seed), int(rows[0]), int(rows[-1]), len(rows))
    fn = "_".join(str(x) for x in k) + ".npy"
    for d in (MEMB, X1CACHE):
        if os.path.exists(os.path.join(d, fn)):
            return np.load(os.path.join(d, fn))
    t0 = time.time()
    p = x1.hgb(D, te, rows, seed, fs="D", h=h)
    os.makedirs(MEMB, exist_ok=True)
    np.save(os.path.join(MEMB, fn), p)
    print(f"  fit h{h} te{te} s{seed} {time.time() - t0:.0f}s", flush=True)
    return p


def fit_predict_for(hs):
    def fp(D, train_end, pred_rows, seed):
        te, rows = int(train_end), np.asarray(pred_rows)
        with np.errstate(all="ignore"):
            return np.nanmean([x1.xrank(np.nanmean([x1.xrank(member(h, D, te, rows, seed)) for h in hs], 0))], 0)
    return fp


def stage_preds():
    D = harness.load()
    os.makedirs(PREDS, exist_ok=True)
    for c in ORDER:
        out = os.path.join(PREDS, f"{c}.npy")
        if os.path.exists(out):
            continue
        state(running=f"preds {c}", next=f"finish preds {c}")
        t0 = time.time()
        pred = harness.walk_forward(fit_predict_for(CONFIGS[c]), seeds=(0, 1, 2), D=D)
        np.save(out, pred)
        ic = float(np.nanmean(harness.weekly_ic(pred, D, np.concatenate([harness.thursdays(D, y) for y in harness.VAL_YEARS]))))
        print(c, "IC", ic, f"{time.time() - t0:.0f}s", flush=True)
        state(done=f"preds {c} saved (IC {ic:.5f}, {time.time() - t0:.0f}s)", running=None)
    state(next="books stage")


# ---------------------------------------------------------------- metrics
def nw_t(d, lags=4):
    d = d[np.isfinite(d)]
    n, dd = len(d), d - d.mean()
    v = dd @ dd / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (dd[l:] @ dd[:-l]) / n
    return float(d.mean() / math.sqrt(v / n))


def sharpe_lo(x):
    """Annualised Sharpe and Lo (2002) iid standard error sqrt((1 + SR_w^2 / 2) / T) x sqrt(52) (as h7_decomp.py)."""
    sw = x.mean() / x.std(ddof=1)
    return float(sw * math.sqrt(52)), float(math.sqrt((1 + sw * sw / 2) / len(x)) * math.sqrt(52))


def simulate_flat(W, D, rows, cost):
    prev = np.zeros(W.shape[1])
    net, turn = [], []
    for j, t in enumerate(rows):
        w = W[j]
        g = float(w @ np.nan_to_num(D["y5"][t]))
        dw = float(np.abs(w - prev).sum())
        net.append(g - cost * dw), turn.append(dw / 2)
        prev = w
    return np.array(net), np.array(turn)


def stage_books():
    D = harness.load()
    P = {c: np.load(os.path.join(PREDS, f"{c}.npy")) for c in ORDER}
    allrows = np.concatenate([harness.thursdays(D, y) for y in harness.VAL_YEARS])
    rows = np.array([t for t in allrows if all(m1.mask(P[c], D, t).sum() >= 50 for c in ORDER)])
    SIG, ADV, info = q6.cost_inputs(D, rows)
    yrs = D["S"][rows].year.to_numpy()
    sl = slice(1, None)
    out, nets = [], {}
    for c in ORDER:
        sc = P[c]
        ic = harness.weekly_ic(sc, D, rows)
        rho = m1.autocorr(sc, D, rows)
        icf = ic[np.isfinite(ic)]
        base = {"config": c, "horizons": CONFIGS[c], "ic_y5": float(icf.mean()), "ic_y5_nw_t": nw_t(ic), "weeks_ic": int(len(icf)),
                "rho": float(np.nanmean(rho[sl])),
                "ic_by_year": {int(y): float(np.nanmean(ic[yrs == y])) for y in harness.VAL_YEARS},
                "rho_by_year": {int(y): float(np.nanmean(rho[sl][yrs[sl] == y])) for y in harness.VAL_YEARS}}
        for kind, label in (("C0", "deciles"), ("T1", "hysteresis_10_30")):
            W = q6.build(kind, sc, D, rows)
            sq = q6.simulate_sqrt(W, D, rows, q6.AUM, SIG, ADV)
            f14, turn = simulate_flat(W, D, rows, FLAT14)
            nsq, n14, gr, tu = sq["net"][sl], f14[sl], sq["gross"][sl], turn[sl]
            ys = yrs[sl]
            s_sq, se_sq = sharpe_lo(nsq)
            s_14, se_14 = sharpe_lo(n14)
            s_g, se_g = sharpe_lo(gr)
            gk = math.sqrt(2 * (1 - base["rho"]))
            row = {"name": f"{c}__{label}", **base, "construction": label,
                   "turnover_wk": float(tu.mean()), "gk_sqrt_2_1_minus_rho": gk, "implied_k": float(tu.mean() / gk),
                   "net_sharpe_sqrt_sp": s_sq, "net_sharpe_sqrt_sp_lo_se": se_sq, "net_pct_per_year_sqrt_sp": float(52 * 100 * nsq.mean()),
                   "net_sharpe_flat14": s_14, "net_sharpe_flat14_lo_se": se_14, "net_pct_per_year_flat14": float(52 * 100 * n14.mean()),
                   "gross_sharpe": s_g, "gross_sharpe_lo_se": se_g, "gross_pct_per_year": float(52 * 100 * gr.mean()),
                   "cost_pct_per_year_sqrt_sp": float(52 * 100 * sq["cost"][sl].mean()),
                   "cost_pct_per_year_flat14": float(52 * 100 * (gr - n14).mean()),
                   "vol_pct_per_year": float(gr.std(ddof=1) * math.sqrt(52) * 100), "weeks": int(len(nsq)),
                   "by_year": {int(y): {"ic_y5": base["ic_by_year"][int(y)], "rho": base["rho_by_year"][int(y)],
                                        "turnover_wk": float(tu[ys == y].mean()),
                                        "net_sharpe_flat14": sharpe_lo(n14[ys == y])[0],
                                        "net_pct_flat14": float(52 * 100 * n14[ys == y].mean()),
                                        "net_sharpe_sqrt_sp": sharpe_lo(nsq[ys == y])[0],
                                        "net_pct_sqrt_sp": float(52 * 100 * nsq[ys == y].mean()),
                                        "gross_pct": float(52 * 100 * gr[ys == y].mean())} for y in harness.VAL_YEARS},
                   "label": "development data 2013-2019, not out of sample", "at": now()}
            # per-week Grinold-Kahn: weekly turnover against sqrt(2(1 - rho_t))
            rr = rho[sl]
            okw = np.isfinite(rr)
            row["weekly_corr_turnover_vs_gk"] = float(np.corrcoef(tu[okw], np.sqrt(2 * (1 - rr[okw])))[0, 1])
            nets[row["name"]] = {"flat14": n14, "sqrt": nsq}
            out.append(row)
            np.savez(os.path.join(PREDS, f"book_{row['name']}.npz"), net_flat14=n14, net_sqrt=nsq, gross=gr, turn=tu)
            print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items() if k not in ("by_year", "ic_by_year", "rho_by_year")}), flush=True)
    with open(RESULTS, "w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    # Grinold-Kahn pooled fit per construction: turnover = k sqrt(2(1 - rho)), least squares through the origin
    gk = {}
    for label in ("deciles", "hysteresis_10_30"):
        rs = [r for r in out if r["construction"] == label]
        x, y = np.array([r["gk_sqrt_2_1_minus_rho"] for r in rs]), np.array([r["turnover_wk"] for r in rs])
        k = float(x @ y / (x @ x))
        res = y - k * x
        gk[label] = {"k_pooled": k, "r2_uncentred": float(1 - res @ res / (y @ y)), "r2_centred": float(1 - res @ res / ((y - y.mean()) @ (y - y.mean()))),
                     "max_abs_rel_error": float(np.max(np.abs(res / y))),
                     "implied_k": {r["config"]: r["implied_k"] for r in rs}}
    # frontier and selection
    ref = "ref_mh_3_5_10_20"
    byn = {r["name"]: r for r in out}
    front = []
    for label in ("deciles", "hysteresis_10_30"):
        rref = byn[f"{ref}__{label}"]
        for r in out:
            if r["construction"] != label:
                continue
            d = {"name": r["name"], "ic_lost_vs_ref": rref["ic_y5"] - r["ic_y5"],
                 "turnover_saved_vs_ref_same_construction": rref["turnover_wk"] - r["turnover_wk"],
                 "turnover_saved_vs_ref_deciles": byn[f"{ref}__deciles"]["turnover_wk"] - r["turnover_wk"],
                 "net_sharpe_flat14": r["net_sharpe_flat14"], "net_sharpe_sqrt_sp": r["net_sharpe_sqrt_sp"]}
            if r["name"] != rref["name"]:
                a, b = nets[r["name"]], nets[rref["name"]]
                d["paired_vs_ref_flat14_pct_per_year"] = float(52 * 100 * (a["flat14"] - b["flat14"]).mean())
                d["paired_vs_ref_flat14_nw_t"] = nw_t(a["flat14"] - b["flat14"])
                d["paired_vs_ref_sqrt_pct_per_year"] = float(52 * 100 * (a["sqrt"] - b["sqrt"]).mean())
                d["paired_vs_ref_sqrt_nw_t"] = nw_t(a["sqrt"] - b["sqrt"])
                dic = harness.weekly_ic(P[r["config"]], D, rows) - harness.weekly_ic(P[ref], D, rows)
                d["ic_diff_nw_t"] = nw_t(dic)
            front.append(d)
    for d in front:                         # Pareto: no other point has both less IC lost and more turnover saved
        d["pareto"] = not any(e is not d and e["ic_lost_vs_ref"] <= d["ic_lost_vs_ref"] and
                              e["turnover_saved_vs_ref_deciles"] >= d["turnover_saved_vs_ref_deciles"] and
                              (e["ic_lost_vs_ref"] < d["ic_lost_vs_ref"] or e["turnover_saved_vs_ref_deciles"] > d["turnover_saved_vs_ref_deciles"])
                              for e in front)
    ric = byn[f"{ref}__hysteresis_10_30"]["ic_y5"]
    elig = [r for r in out if r["construction"] == "hysteresis_10_30" and r["ic_y5"] >= ric - 0.005]
    best = max(elig, key=lambda r: r["net_sharpe_flat14"])
    res = {"branch": "Q9_horizon", "label": "development data 2013-2019 (S&P 500, harness.load()), not out of sample",
           "weeks_book": int(len(rows) - 1), "cost_inputs": info,
           "selection_rule": "highest net Sharpe at 14 bp flat with hysteresis 10/30, among configurations with IC_y5 >= reference IC - 0.005",
           "reference_ic_y5": ric, "eligible": [r["config"] for r in elig],
           "selected": best["name"], "selected_net_sharpe_flat14": best["net_sharpe_flat14"],
           "selected_net_sharpe_flat14_lo_se": best["net_sharpe_flat14_lo_se"],
           "selected_is_reference": best["config"] == ref,
           "grinold_kahn_fit": gk, "frontier": front,
           "survivorship_contract": "does not apply: no new inputs (same D features, same panel; only the target horizon changes)",
           "at": now()}
    json.dump(res, open(RESULT, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "frontier"}, indent=1))
    state(done="books stage: RESULTS.jsonl, RESULT.json written", running=None, next="report")


if __name__ == "__main__":
    {"preds": stage_preds, "books": stage_books}[sys.argv[1]]()
