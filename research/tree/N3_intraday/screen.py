"""Config 1: single-feature screen. Rules fixed BEFORE any 2017-2019 number was seen (2026-11-12):
* Selection for configs 2-3: the two features with largest |t| of partial IC (feature vs y5 rank after regressing y5
  rank on MASTER rank, per Thursday) on 2016 Thursdays only (training data for every fold); sign from 2016.
* Rank-average weights fixed: 0.8 MASTER + 0.2 feature (one), 0.8/0.1/0.1 (two).
* Combined scores keep MASTER's universe: missing intraday data -> neutral feature rank 0.
"""
import json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import harness as h
import features as fe

YRS = (2017, 2018, 2019)
LOG = os.path.join(HERE, "RESULTS.jsonl")
D = h.load(); F = fe.build(D)
M = D["master_h5_ref"].astype(np.float64)
Mr = fe.rank_rows(M)


def partial_ic(x, rows):
    out = []
    for t in rows:
        m = np.isfinite(x[t]) & np.isfinite(D["y5"][t]) & D["elig"][t] & np.isfinite(M[t])
        if m.sum() < 50: continue
        yr = pd.Series(D["y5"][t][m]).rank(pct=True).to_numpy() - .5
        mr = pd.Series(M[t][m]).rank(pct=True).to_numpy() - .5
        res = yr - mr * (mr @ yr) / (mr @ mr)
        out.append(pd.Series(x[t][m]).corr(pd.Series(res), method="spearman"))
    out = np.array(out); return out.mean(), out.mean() / out.std(ddof=1) * np.sqrt(len(out))

if __name__ == "__main__":
    th16 = h.thursdays(D, 2016)
    sel = {}
    for k, x in F.items():
        pic, pt = partial_ic(x, th16)
        cm = np.nanmean([pd.Series(x[t]).corr(pd.Series(M[t]), method="spearman") for t in np.concatenate([h.thursdays(D, y) for y in YRS])])
        r = h.score(x, f"N3_screen_{k}", LOG, note=f"config1 single feature, raw sign; 2016 partial IC {pic:.4f} t {pt:.2f}; spearman with MASTER {cm:.3f}", D=D, years=YRS)
        sel[k] = (pic, pt)
        print(f"{k:22s} 2016pIC {pic:+.4f} t {pt:+.2f} | 17-19 IC {r['ic']:+.4f} t {r['ic_t']:+.2f} byyr {[round(v,3) for v in r['ic_by_year'].values()]} corrM {cm:+.3f} dec {r['decile_net_pct_per_year']:+.1f}")
    best = sorted(sel, key=lambda k: -abs(sel[k][1]))[:2]
    json.dump({k: {"partial_ic_2016": sel[k][0], "t_2016": sel[k][1], "sign": int(np.sign(sel[k][0]))} for k in best},
              open(os.path.join(HERE, "selected.json"), "w"), indent=1)
    print("selected", best)
