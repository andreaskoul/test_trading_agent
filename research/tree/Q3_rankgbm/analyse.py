"""Summary table for REPORT.md: every scored configuration, James-Stein shrunk IC, and paired weekly IC differences
vs ref_control (Newey-West t, 4 lags, via harness.increment with base = ref_control predictions)."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import harness as H  # noqa: E402

PRED = os.path.join(H.ROOT, ".cache", "tree", "preds", "Q3_rankgbm")


def main():
    D = H.load()
    rs = {}
    for l in open(os.path.join(HERE, "RESULTS.jsonl")):
        r = json.loads(l)
        rs[r["name"]] = r                      # last entry per name
    names = list(rs)
    ic = np.array([rs[n]["ic"] for n in names])
    se2 = np.array([(rs[n]["ic"] / rs[n]["ic_t"]) ** 2 for n in names])
    k, mu = len(ic), ic.mean()
    ss = ((ic - mu) ** 2).sum()
    c = max(0.0, 1 - (k - 3) * se2.mean() / ss) if k > 3 and ss > 0 else 0.0
    shr = mu + c * (ic - mu)
    base = np.load(os.path.join(PRED, "ref_control.npy")).astype(np.float64)
    rows = []
    for n, s in zip(names, shr):
        r = rs[n]
        pos = sum(v > 0 for v in r["ic_by_year"].values())
        if n == "ref_control":
            inc = {"increment": 0.0, "increment_t": float("nan"), "years_increment_positive": 0, "corr_with_base": 1.0}
        else:
            p = np.load(os.path.join(PRED, n + ".npy")).astype(np.float64)
            inc = H.increment(p, n, None, D=D, base=base)
        rows.append(dict(name=n, ic=r["ic"], t=r["ic_t"], pos=pos, min_year=r["min_year_ic"], shrunk=float(s),
                         dec=r["decile_net_pct_per_year"], sh=r["decile_net_sharpe"], d=inc["increment"],
                         dt=inc["increment_t"], dpos=inc["years_increment_positive"], corr=inc["corr_with_base"],
                         by=r["ic_by_year"], note=r["note"]))
    print("shrinkage factor c = %.3f (branch mean %.4f, k=%d)" % (c, mu, k))
    print("| config | IC | t | years + | min year | shrunk IC | decile net %/yr | net Sharpe | ΔIC vs control | NW t | years Δ>0 | rank corr w/ control |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print("| %s | %.4f | %.2f | %d/7 | %+.4f | %.4f | %+.1f | %+.2f | %+.4f | %s | %s | %.2f |" % (
            r["name"], r["ic"], r["t"], r["pos"], r["min_year"], r["shrunk"], r["dec"], r["sh"], r["d"],
            "—" if r["name"] == "ref_control" else "%+.2f" % r["dt"], "—" if r["name"] == "ref_control" else "%d/7" % r["dpos"], r["corr"]))
    print()
    print("| config | " + " | ".join(str(y) for y in H.VAL_YEARS) + " |")
    print("|---|" + "---|" * len(H.VAL_YEARS))
    for r in rows:
        print("| %s | " % r["name"] + " | ".join("%+.3f" % v for v in r["by"].values()) + " |")
    json.dump(rows, open(os.path.join(HERE, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
