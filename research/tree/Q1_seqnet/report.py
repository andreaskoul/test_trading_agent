"""Summaries for REPORT.md: table of all logged configurations, paired weekly IC difference vs the control (Newey-West,
4 lags), and James-Stein shrunk ICs toward the branch mean. Reads RESULTS.jsonl and the saved predictions only."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
sys.path.insert(0, TREE)
import harness as H  # noqa: E402

PRED = os.path.join(os.path.dirname(os.path.dirname(TREE)), ".cache", "tree", "preds", "Q1_seqnet")


def nw(d, lags=4):
    d = d[np.isfinite(d)]
    n, dd = len(d), d - d.mean()
    v = dd @ dd / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (dd[l:] @ dd[:-l]) / n
    return d.mean(), d.mean() / np.sqrt(v / n)


def main(base="ref_control", extra=()):
    D = H.load()
    rows = np.concatenate([H.thursdays(D, y) for y in H.VAL_YEARS])
    R = [json.loads(l) for l in open(os.path.join(HERE, "RESULTS.jsonl"))]
    wk = {r["name"]: H.weekly_ic(np.load(os.path.join(PRED, r["name"] + ".npy")).astype(np.float64), D, rows) for r in R}
    for e in extra:                                       # other branches' saved predictions, for comparison only
        wk[os.path.basename(e)] = H.weekly_ic(np.load(e).astype(np.float64), D, rows)
    ic = np.array([r["ic"] for r in R])
    se2 = np.array([(r["ic"] / r["ic_t"]) ** 2 for r in R if abs(r["ic_t"]) > 0.2])
    gm, between = ic.mean(), ic.var(ddof=1)
    Bf = max(0.0, 1 - se2.mean() / between)                       # X5 step 4 formula
    M = np.stack([wk[r["name"]] for r in R], 1)
    dev = M - np.nanmean(M, 1, keepdims=True)
    nz = float(np.mean(np.nanvar(dev, 0, ddof=1) / np.isfinite(dev).sum(0)))
    Bp = max(0.0, 1 - nz / between)                                 # paired variant
    shrunk = gm + Bf * (ic - gm)
    shp = gm + Bp * (ic - gm)
    print(f"n {len(ic)}; branch mean IC {gm:.4f}; var between {between:.2e}; noise iid {se2.mean():.2e} -> B {Bf:.2f}; noise paired {nz:.2e} -> B {Bp:.2f}")
    print("| name | IC | t | yrs+/7 | decile net %/yr | shrunk IC | shrunk (paired) | diff vs control | NW t |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r, s, sp in zip(R, shrunk, shp):
        yp = sum(v > 0 for v in r["ic_by_year"].values())
        dm, dt = nw(wk[r["name"]] - wk[base]) if r["name"] != base else (np.nan, np.nan)
        print(f"| {r['name']} | {r['ic']:.4f} | {r['ic_t']:.2f} | {yp} | {r['decile_net_pct_per_year']:.1f} | {s:.4f} | {sp:.4f} | {dm:+.4f} | {dt:.2f} |")
    for e in extra:
        n = os.path.basename(e)
        print(n, "IC %.4f" % np.nanmean(wk[n]))
    return wk


if __name__ == "__main__":
    main(extra=sys.argv[1:])
