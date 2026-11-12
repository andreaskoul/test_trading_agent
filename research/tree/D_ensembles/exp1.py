import os
os.environ["OMP_NUM_THREADS"] = "2"
import functools, numpy as np, lib, harness
D = harness.load(); lib.RUN_D = D
# sanity: target(5) == y5 construction check via h=3 shape & no-leak
te = harness.train_end(D, 2015); y3 = lib.target(D, 3, te); y20 = lib.target(D, 20, te)
print("last finite row h3", np.where(np.isfinite(y3).any(1))[0].max() - te, "h20", np.where(np.isfinite(y20).any(1))[0].max() - te)
e = D["e"].astype(float); t = 1500; chk = e[t+2:t+7].sum(0); m = np.isfinite(D["y5"][t]) & np.isfinite(chk)
print("y5 rebuild max err", np.abs(chk[m] - D["y5"][t][m]).max())
info = []
lib.BASE["hgb"] = functools.partial(lib.hgb, info=info)
lib.BASE["et"] = functools.partial(lib.forest, kind="et")
lib.BASE["rf"] = functools.partial(lib.forest, kind="rf")
lib.BASE["ridge"] = lib.ridge
for n, note in [("hgb", "HGB rank target, 22 ranked return features + 5 chars, Thursdays, lr .03 leaves 8 msl 400, trees picked by inner rank IC from 50/100/200/400"),
                ("et", "ExtraTrees 200 trees, min leaf 1000, max_features .33, rank target, Thursdays"),
                ("rf", "RandomForest 200 trees, min leaf 1000, max_features .33, max_samples .5, rank target, Thursdays"),
                ("ridge", "ridge on the 27 features, rank target, Thursdays (linear member for the ensemble)")]:
    lib.run(n, functools.partial(lib.cached, n), note)
    if n == "hgb": print(info)
