"""Configurations 6-9: refinements of the two best (comp_blend70: highest increment t; fm_ridge: largest increment).
Chosen after seeing configurations 1-5 on the development years (disclosed: post-hoc)."""
import sys
import numpy as np
import lib
from run_blend import run, make
import run_fit

PLAN = ["comp_blend70", "comp_blend50", "fm_ridge", "hgb_blend", "dml_composite",
        "fm_fixed70", "comp_lit7_blend70", "fm_lit_fixed70", "comp_blend80"]
LIT7 = lib.COMPOSITE + ("issuance", "invest")


def fm_fixed(feats, w=0.7):
    def fit_predict(Dm, te, rows, seed):
        tr = lib.train_thursdays(te)
        b = run_fit.fm(run_fit.X_at(tr, feats), lib.target_rank(Dm, tr)).mean(0)
        s = np.full(Dm["y5"].shape, np.nan); s[rows] = run_fit.X_at(rows, feats) @ b
        return lib.blend(s, w)[rows]
    return fit_predict


if __name__ == "__main__":
    w = sys.argv[1:]
    if "fm_fixed70" in w:
        run("fm_fixed70", fm_fixed(run_fit.FEATS), "Fama-MacBeth fundamentals score (13 chars, training Thursdays) blended at fixed 0.7 MASTER", PLAN)
    if "comp_lit7_blend70" in w:
        run("comp_lit7_blend70", make(0.7, LIT7), "equal-weight composite + issuance + investment (7 literature signs), fixed 0.7 MASTER", PLAN)
    if "fm_lit_fixed70" in w:
        run("fm_lit_fixed70", fm_fixed(list(lib.COMPOSITE)), "Fama-MacBeth weights on the 5 composite components only, fixed 0.7 MASTER", PLAN)
    if "comp_blend80" in w:
        run("comp_blend80", make(0.8), "0.8 MASTER / 0.2 composite; post-hoc interpolation after 0.7 and 0.5", PLAN)
