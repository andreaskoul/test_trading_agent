"""Q2_xsattn summary: every logged configuration, module-vs-ablation pairs (paired weekly IC difference, Newey-West t
at 4 lags), James-Stein shrunk IC toward the branch mean, and reference rows (D trees, MASTER).   python analyze.py"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import harness as H  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
PRED = os.path.join(ROOT, ".cache", "tree", "preds", "Q2_xsattn")


def nw_t(d, lags=4):
    d = d[np.isfinite(d)]
    n, dd = len(d), d - d.mean()
    v = dd @ dd / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (dd[l:] @ dd[:-l]) / n
    return float(d.mean()), float(d.mean() / np.sqrt(v / n))


def main():
    D = H.load()
    rows = np.concatenate([H.thursdays(D, y) for y in H.VAL_YEARS])
    years = np.concatenate([[y] * len(H.thursdays(D, y)) for y in H.VAL_YEARS])
    res = [json.loads(l) for l in open(os.path.join(HERE, "RESULTS.jsonl"))]
    st = json.load(open(os.path.join(HERE, "STATE.json")))
    ctrl = {x["name"]: x.get("control") for x in st["scored"]}
    ics = {}
    for r in res:
        p = np.load(os.path.join(PRED, r["name"] + ".npy")).astype(np.float64)
        ics[r["name"]] = H.weekly_ic(p, D, rows)
    dd = os.path.join(os.path.dirname(HERE), "D_ensembles")
    ref = {"D trees hgb_multihorizon (the 0.0236 bar)": np.load(os.path.join(dd, "pred_hgb_multihorizon.npy")),
           "D trees hgb, 5-session target": np.load(os.path.join(dd, "pred_hgb.npy")),
           "MASTER h5 reference": D["master_h5_ref"]}
    refic = {k: H.weekly_ic(v.astype(np.float64), D, rows) for k, v in ref.items()}
    # James-Stein toward the branch mean
    m = np.array([np.nanmean(ics[r["name"]]) for r in res])
    se2 = np.mean([np.nanvar(ics[r["name"]], ddof=1) / np.isfinite(ics[r["name"]]).sum() for r in res])
    k = len(m)
    ss = ((m - m.mean()) ** 2).sum()
    B = max(0.0, 1 - (k - 3) * se2 / ss) if k > 3 and ss > 0 else 0.0
    shr = m.mean() + B * (m - m.mean())
    out = dict(rows=[], pairs=[], refs={}, js=dict(branch_mean=float(m.mean()), factor=float(B), se=float(np.sqrt(se2))))
    for r, s in zip(res, shr):
        out["rows"].append(dict(name=r["name"], ic=r["ic"], t=r["ic_t"], years_pos=sum(v > 0 for v in r["ic_by_year"].values()),
                                net=r["decile_net_pct_per_year"], sharpe=r["decile_net_sharpe"], shrunk=float(s), by=r["ic_by_year"],
                                control=ctrl.get(r["name"])))
    for a, c in ctrl.items():
        if c and a in ics and c in ics:
            d = ics[a] - ics[c]
            mu, t = nw_t(d)
            by = {int(y): float(np.nanmean(d[years == y])) for y in H.VAL_YEARS}
            out["pairs"].append(dict(module=a, control=c, diff=mu, nw_t=t, years_pos=sum(v > 0 for v in by.values()), by=by))
    best = max([x for x in out["rows"] if x["years_pos"] >= 5], key=lambda x: x["ic"], default=None)
    if best:
        for kname, v in refic.items():
            mu, t = nw_t(ics[best["name"]] - v)
            out["refs"][kname] = dict(ic=float(np.nanmean(v)), best_minus_ref=mu, nw_t=t)
    out["best"] = best and best["name"]
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
