"""Leakage test for Layer 6 T1 (STATE.json plan 7): perturb every value dated after a cut t* and rerun the whole
pipeline (book, states, random-feature ridge, positions, annual selection, benchmarks). Nothing at decisions <= t*
may move; something after t* must.

    OMP_NUM_THREADS=4 python3 research/tree/L6_complexity/test_timing.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib as L  # noqa: E402

CUTS = ("2016-06-02", "2018-11-15", "2019-09-12")
CG, ZG, SEEDS = (0.5, 10), (0.1, 10.0), (0, 1)


def perturb(d, pred, macro, t, rng):
    d2 = dict(d)
    for k in ("r", "beta"):
        a = d[k].copy()
        a[t + 1:] = a[t + 1:] * rng.uniform(-3, 3, a[t + 1:].shape) + rng.normal(0, 0.02, a[t + 1:].shape)
        d2[k] = a
    for k in ("rm", "spy"):
        a = d[k].copy()
        a[t + 1:] = a[t + 1:] * rng.uniform(0.5, 1.5, a[t + 1:].shape)
        d2[k] = a
    p2 = pred.copy()
    p2[t + 1:] = rng.normal(size=p2[t + 1:].shape) * np.isfinite(p2[t + 1:]) + np.where(np.isfinite(p2[t + 1:]), 0, np.nan)
    cut = d["S"][t]
    m2 = {}
    for k, s in macro.items():
        s = s.copy()
        fut = s.index > cut
        s[fut] = s[fut] * rng.uniform(0.2, 3, fut.sum()) + 1.0
        m2[k] = s
    return d2, p2, m2


def same(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return bool(np.array_equal(np.isnan(a), np.isnan(b)) and np.allclose(np.nan_to_num(a), np.nan_to_num(b), rtol=0, atol=1e-12))


def main():
    d, rf = L.panel()
    pred = L.dev_scores(d)
    macro, _ = L.load_macro()
    S = d["S"]
    upto = int(np.where(S <= pd.Timestamp("2019-12-31"))[0][-1])
    kw = dict(book_years=range(2013, 2020), sel_years=range(2015, 2020), cgrid=CG, zgrid=ZG, seeds=SEEDS, upto=upto)
    base = L.pipeline(d, pred, macro, rf, **kw)
    # y5 recomputed equals the panel target
    y = L.resid5(d)
    assert same(y[:upto - 10], d["y5"][:upto - 10]) or np.nanmax(np.abs(y[:upto - 10] - d["y5"][:upto - 10])) < 1e-6
    rng = np.random.default_rng(7)
    rep = {}
    for c in CUTS:
        t = int(S.get_loc(pd.Timestamp(c)))
        d2, p2, m2 = perturb(d, pred, macro, t, rng)
        alt = L.pipeline(d2, p2, m2, rf, **kw)
        dec = base["rows"] <= t
        thm = base["th"] <= t
        chk = {"states": same(base["Z"][thm], alt["Z"][thm]), "raw_states": same(base["raw"].to_numpy()[thm], alt["raw"].to_numpy()[thm]),
               "book_completed": same(base["b"][base["end"] <= t], alt["b"][base["end"] <= t]),
               "forecasts": all(same(base["fs"][k][dec], alt["fs"][k][dec]) for k in base["fs"]),
               "pi_configs": all(same(base["pis"][k][dec], alt["pis"][k][dec]) for k in base["pis"]),
               "pi_candidate": same(base["pi"][dec], alt["pi"][dec]),
               "bench_signals": all(same(base["bench"][k]["signal"][dec], alt["bench"][k]["signal"][dec]) for k in base["bench"]),
               "pi_benchmarks": all(same(base["bench"][k]["pi"][dec], alt["bench"][k]["pi"][dec]) for k in base["bench"]),
               "x_completed": same(base["x"][base["end"] <= t], alt["x"][base["end"] <= t])}
        later = ~dec
        chk["something_after_cut_changes"] = (not same(base["Z"][~thm], alt["Z"][~thm])) and any(
            not same(base["fs"][k][later], alt["fs"][k][later]) for k in base["fs"])
        rep[c] = chk
        L.log(c, chk)
        assert all(chk.values()), (c, chk)
    json.dump({"cuts": rep, "grid": {"c": CG, "z": ZG, "seeds": SEEDS}, "pass": True},
              open(os.path.join(L.HERE, "TEST_TIMING.json"), "w"), indent=1)
    L.log("PASS")


if __name__ == "__main__":
    main()
