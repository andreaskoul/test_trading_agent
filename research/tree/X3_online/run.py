"""Run named configurations, each online and yearly. usage: python3 run.py name [name ...]"""
import os, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "3"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "3"); os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "3")
import warnings; warnings.filterwarnings('ignore')
import json
import numpy as np
import lib
import harness

W = 5  # sessions per week
CFG = {
    "ridge_exp":   dict(kind="Z5", mode="pool"),
    "ridge_ew26":  dict(kind="Z5", mode="pool", window="ew", hl=26 * W),
    "ridge_ew104": dict(kind="Z5", mode="pool", window="ew", hl=104 * W),
    "fm26":        dict(kind="Z5", mode="fm", window="roll", roll=26 * W),
    "fm52":        dict(kind="Z5", mode="fm", window="roll", roll=52 * W),
    "fm104":       dict(kind="Z5", mode="fm", window="roll", roll=104 * W),
    "hedge":       dict(kind="Z5", mode="hedge", eta=0.5),
    "ict52":       dict(kind="Z5", mode="ict", window="roll", roll=52 * W),
    "c32_fm_exp":  dict(kind="C32", mode="fm"),
    "c32_fm104":   dict(kind="C32", mode="fm", window="roll", roll=104 * W),
    "c32_fm_ew104": dict(kind="C32", mode="fm", window="ew", hl=104 * W),
    "c32_fm_ew260": dict(kind="C32", mode="fm", window="ew", hl=260 * W),
    "c32_pool_exp": dict(kind="C32", mode="pool"),
    "c32_pool_ew104": dict(kind="C32", mode="pool", window="ew", hl=104 * W),
    "fm_exp":      dict(kind="Z5", mode="fm"),
}
LOG = os.path.join(lib.HERE, "RESULTS.jsonl")

if __name__ == "__main__":
    D = harness.load()
    te0 = harness.train_end(D, 2013)
    print("rebuilt target vs y5 on rows <= %d: corr %.4f (n=%d of %d y5 cells)" % ((te0,) + lib.check_target(D, te0)))
    for name in sys.argv[1:]:
        ics = {}
        for online in (False, True):
            t0 = time.time()
            fp = lib.make(online=online, **CFG[name])
            pred = harness.walk_forward(fp, seeds=(0, 1, 2), D=D)
            tag = "%s | %s" % (name, "online" if online else "yearly")
            r = harness.score(pred, tag, LOG, note=str(CFG[name]) + (" cut=t-6" if online else " cut=train_end") + "; rebuilt rank target, all sessions", D=D)
            print("%-28s ic %.4f t %.2f min_yr %.4f dec %.1f%%/yr  by_year %s  (%.0fs)" % (tag, r["ic"], r["ic_t"], r["min_year_ic"], r["decile_net_pct_per_year"],
                  " ".join("%.3f" % v for v in r["ic_by_year"].values()), time.time() - t0), flush=True)
            ics[online] = np.concatenate([harness.weekly_ic(pred, D, harness.thursdays(D, y)) for y in harness.VAL_YEARS])
        d = ics[True] - ics[False]; d = d[np.isfinite(d)]
        pd_ = dict(name=name, diff=float(d.mean()), se=float(d.std(ddof=1) / np.sqrt(len(d))), weeks=int(len(d)))
        print("   paired online - yearly: %+.4f (se %.4f, t %.2f)" % (pd_["diff"], pd_["se"], pd_["diff"] / pd_["se"]), flush=True)
        open(os.path.join(lib.HERE, "PAIRED.jsonl"), "a").write(json.dumps(pd_) + "\n")
