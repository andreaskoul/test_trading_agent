"""Configuration set 2: registered equal-weight literature composite blended with MASTER at fixed 0.7/0.3 and 0.5/0.5."""
import json, sys
import numpy as np
import lib
from lib import harness

D = lib.data()
PLAN = ["comp_blend70", "comp_blend50", "fm_ridge", "hgb_blend", "dml_composite"]


def make(w, keys=lib.COMPOSITE):
    B = lib.blend(lib.composite(keys), w)
    def fit_predict(Dm, te, rows, seed):
        return B[rows]
    return fit_predict


def run(name, fp, note, plan=PLAN):
    st = json.load(open(lib.os.path.join(lib.HERE, "STATE.json")))
    if name in st["scored"]:
        print("skip", name); return None
    pred = harness.walk_forward(fp, seeds=(0, 1, 2), D=D)
    r = harness.increment(pred, name, lib.LOG, note=note, D=D)
    print(json.dumps({k: r[k] for k in ("name", "ic", "base_ic", "increment", "increment_t", "years_increment_positive",
                                        "corr_with_base", "decile_net_pct_per_year", "decile_net_sharpe", "increment_by_year")}), flush=True)
    lib.update_state(name, f"{name}: increment {r['increment']:.4f} t {r['increment_t']:.2f}, net {r['decile_net_pct_per_year']:.1f}%/yr", plan)
    return r


if __name__ == "__main__":
    run("comp_blend70", make(0.7), "0.7 rank(MASTER) + 0.3 rank(equal-weight prof, accruals, agrowth, payout, sue); fixed, no fitting")
    run("comp_blend50", make(0.5), "0.5 rank(MASTER) + 0.5 rank(equal-weight composite); fixed, no fitting")
