import os
os.environ["OMP_NUM_THREADS"] = "2"
import functools, sys, warnings, numpy as np, lib, harness
warnings.filterwarnings("ignore")
D = harness.load(); lib.RUN_D = D
lib.BASE["hgb"] = lib.hgb
lib.BASE["et"] = functools.partial(lib.forest, kind="et")
lib.BASE["ridge"] = lib.ridge
for h in (3, 10, 20):
    lib.BASE["hgb_h%d" % h] = functools.partial(lib.hgb, h=h)
    lib.BASE["ridge_h%d" % h] = functools.partial(lib.ridge, h=h)
lib.BASE["hgb_bag"] = functools.partial(lib.hgb, block_bag=8)
which = sys.argv[1:]
if "mh" in which:
    lib.run("hgb_multihorizon", lib.ew(["hgb_h3", "hgb", "hgb_h10", "hgb_h20"]), "equal-weight rank average of HGB trained on 3-, 5-, 10-, 20-session hedged-return rank targets")
if "ew3" in which:
    lib.run("ew_hgb_et_ridge", lib.ew(["hgb", "et", "ridge"]), "equal-weight rank average of HGB, ExtraTrees, ridge (5-session target)")
if "ew6" in which:
    lib.run("ew_all6", lib.ew(["hgb_h3", "hgb", "hgb_h10", "hgb_h20", "et", "ridge"]), "equal-weight rank average: HGB at 3/5/10/20-session targets + ExtraTrees + ridge")
if "stack" in which:
    names = ["hgb_h3", "hgb", "hgb_h10", "hgb_h20", "et", "ridge"]
    for nm, sh, note in [("stack_nnls", 0.0, "non-negative least-squares stacking of the 6 members on walk-forward out-of-sample ranks of earlier years (2011..Y-1); equal weights when none"),
                         ("stack_nnls_shrink50", 0.5, "same stacking, weights shrunk 50% toward equal weights")]:
        info = []
        lib.run(nm, functools.partial(lib.stack(names, shrink=sh), info=info), note)
        print([i for i in info if i[1] == 0])
if "bag" in which:
    lib.run("hgb_blockbag", functools.partial(lib.cached, "hgb_bag"), "HGB bagged 8x over random 60% of half-year time blocks, rank-averaged")
