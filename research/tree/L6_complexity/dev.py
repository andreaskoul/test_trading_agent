"""Layer 6 T1 development run (decisions 2013-2019 only): full c x z grid, 10 seeds, virtue-of-complexity surface,
nested selection, benchmarks B_m / B_mv, the gate (amendment), and the stationary-bootstrap null.

    OMP_NUM_THREADS=4 python3 research/tree/L6_complexity/dev.py        # -> RESULT.json (development part)
"""
import json
import math
import os
import sys
from multiprocessing import get_context

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib as L  # noqa: E402

GATE_YEARS = range(2015, 2020)
NBOOT, BOOT_SEED, MEAN_BLOCK = 1000, 20261121, 4
G = {}


def wkly(x, days):
    return x * 7 / days


def compare(a, b, pa, pb, years, mask):
    """a vs b (weekly, 7/days-normalised) on mask: LW HAC Sharpe difference and yearly matched-exposure sign."""
    A, B = a[mask], b[mask]
    hz = L.L4.lw_hac_test(A, B)
    pa_bar, pb_bar = float(np.nanmean(pa[mask])), float(np.nanmean(pb[mask]))
    diff = A / pa_bar - B / pb_bar
    yy = years[mask]
    by = {int(y): 100 * 52 * float(diff[yy == y].mean()) for y in np.unique(yy)}
    dm = L.L4.nw(diff)
    return {"sharpe_a": L.sharpe(A), "sharpe_b": L.sharpe(B), "lw_hac": hz,
            "matched_exposure_diff_pct_per_year": 100 * 52 * dm[0], "matched_diff_nw_t": dm[1],
            "mean_pi_a": pa_bar, "mean_pi_b": pb_bar, "yearly_matched_diff_pct_per_year": by,
            "years_positive": int(sum(v > 0 for v in by.values())),
            "pass": bool(hz["z"] >= 2.0 and sum(v > 0 for v in by.values()) >= 3)}


def stationary_idx(n, rng):
    idx = np.empty(n, int)
    i = rng.integers(n)
    for k in range(n):
        if k > 0 and rng.random() < 1 / MEAN_BLOCK:
            i = rng.integers(n)
        idx[k] = i
        i = (i + 1) % n
    return idx


def boot_one(seed):
    g = G
    rng = np.random.default_rng(seed)
    bb = g["b"][stationary_idx(len(g["b"]), rng)]
    Zd = g["Zd"].copy()
    bs = L.book_states(bb, g["end"], g["th"])
    for n, _ in L.BOOK_COLS:
        Zd[:, g["names"].index(n)] = L.expanding_z(bs[n])[g["pos"]]
    F, _ = L.forecasts(Zd, bb, g["end"], g["rows"], np.arange(len(g["rows"])), g["cs"], g["zs"], list(range(L.NSEEDS)))
    fs, pis, xs = L.strategies(F, bb, g["end"], g["rows"], g["gross"], g["cs"], g["zs"])
    pi = np.full(len(bb), np.nan)
    for Y, ch in g["choice"].items():
        iy = g["yr"] == Y
        pi[iy] = pis[tuple(ch)][iy]
    ok = np.isfinite(pi)
    x = np.full(len(bb), np.nan)
    x[ok] = L.timed(pi[ok], bb[ok], g["gross"][ok])
    bx = L.bench_x(bb, g["end"], g["rows"], g["gross"])
    m, days = g["mask"], g["days"]
    xt, xb = wkly(x, days)[m], wkly(bb, days)[m]
    sb = {k: L.sharpe(wkly(v["x"], days)[m]) for k, v in bx.items()}
    st = L.sharpe(xt)
    return [st, st - L.sharpe(xb), st - max(sb.values())]


def main():
    os.makedirs(L.CACHE, exist_ok=True)
    L.state(running=["dev.py: full grid"], next=["surface, gate, bootstrap"])
    d, rf = L.panel()
    pred = L.dev_scores(d)
    macro, prov = L.load_macro()
    S = d["S"]
    upto = int(np.where(S <= pd.Timestamp("2019-12-31"))[0][-1])
    P = L.pipeline(d, pred, macro, rf, range(2013, 2020), GATE_YEARS, upto=upto, keep_F=True)
    np.savez_compressed(os.path.join(L.CACHE, "dev_F.npz"), F=P["F"], rows=P["rows"], Zd=P["Zd"])
    rows, b, days, gross = P["rows"], P["b"], P["book"].days.to_numpy(float), P["gross"]
    yr = S[rows].year.to_numpy()
    mask = (yr >= 2015) & (yr <= 2019)
    L.log("grid done; Tn in gate window", P["Tn"][mask].min(), P["Tn"][mask].max())
    res = {"label": "Layer 6 T1, development only (decisions 2013-2019; gate window 2015-2019)",
           "book": json.load(open(os.path.join(L.HERE, "BUILD_CHECK.json")))["book"],
           "inputs": {"states": P["names"], "K": len(P["names"]), "macro_provenance": prov,
                      "survivorship": "not applicable: every state is market-level (SPY, VIX, FRED) or computed on the point-in-time membership (dispersion, the book, MASTER's IC); the contract tests stock-level inputs",
                      "ic_rule": "MASTER weekly Spearman IC of decision s uses the 5-session residual completing at row s+6; used at t only if s+6 <= t",
                      "timing_test": json.load(open(os.path.join(L.HERE, "TEST_TIMING.json")))},
           "training_sizes_gate_window": {"min": int(P["Tn"][mask].min()), "max": int(P["Tn"][mask].max())}}
    # ---------------- surface
    F = P["F"]
    Fm = np.nanmean(F, 0)
    surf = []
    for ci, c in enumerate(L.CGRID):
        for zi, z in enumerate(L.ZGRID):
            k = (c, z)
            f, pi, x = P["fs"][k], P["pis"][k], P["xs"][k]
            fm, bm = f[mask], b[mask]
            seed_sh = []
            for s in range(F.shape[0]):
                ps = L.positions(F[s, ci, zi])
                xs_ = np.full(len(b), np.nan)
                ok = np.isfinite(ps)
                xs_[ok] = L.timed(ps[ok], b[ok], gross[ok])
                seed_sh.append(L.sharpe(wkly(xs_, days)[mask]))
            dpi = np.abs(np.diff(np.concatenate([[1.0], pi[mask]])))
            surf.append({"c": c, "z": z, "P": L.P_of(c),
                         "sharpe_timed_net": L.sharpe(wkly(x, days)[mask]),
                         "sharpe_kmz_timing_f_times_b_gross": L.sharpe(wkly(fm * bm, days[mask])),
                         "oos_r2": float(1 - np.sum((bm - fm) ** 2) / np.sum(bm ** 2)),
                         "sd_pi": float(np.std(pi[mask], ddof=1)), "mean_pi": float(np.mean(pi[mask])),
                         "share_pi_zero": float(np.mean(pi[mask] == 0)),
                         "sd_forecast_pct_per_week": 100 * float(np.std(fm, ddof=1)),
                         "mean_forecast_pct_per_week": 100 * float(np.mean(fm)),
                         "pi_turnover_per_year": float(dpi.sum() / 5),
                         "single_seed_sharpe_mean": float(np.mean(seed_sh)), "single_seed_sharpe_sd": float(np.std(seed_sh, ddof=1))})
    res["surface_2015_2019_development"] = surf
    sd = pd.DataFrame(surf)
    rl = {}
    for z in L.ZGRID:
        g = sd[sd.z == z].sort_values("c")
        rl[str(z)] = {"spearman_sharpe_on_c": float(spearmanr(g.c, g.sharpe_timed_net)[0]),
                      "spearman_kmz_timing_sharpe_on_c": float(spearmanr(g.c, g.sharpe_kmz_timing_f_times_b_gross)[0]),
                      "spearman_r2_on_c": float(spearmanr(g.c, g.oos_r2)[0]),
                      "sharpe_by_c": dict(zip(map(str, g.c), g.sharpe_timed_net.round(4))),
                      "kmz_timing_sharpe_by_c": dict(zip(map(str, g.c), g.sharpe_kmz_timing_f_times_b_gross.round(4))),
                      "r2_by_c": dict(zip(map(str, g.c), g.oos_r2.round(4)))}
    res["ridgeless_check"] = {"z_1e-3": rl[str(1e-3)], "by_z": rl,
                              "rises_with_c_at_z_1e-3": bool(rl[str(1e-3)]["spearman_sharpe_on_c"] > 0)}
    # ---------------- candidate and benchmarks
    choice = {Y: v for Y, v in P["choice"].items()}
    res["selection"] = {str(Y): {"c": v["cfg"][0], "z": v["cfg"][1], "inner_sharpe": v["inner_sharpe"],
                                 "inner_weeks": v["inner_weeks"], "inner_first": v["inner_first"], "inner_last": v["inner_last"]}
                        for Y, v in choice.items()}
    xT, piT = wkly(P["x"], days), P["pi"]
    bx = P["bench"]
    one = np.ones(len(b))
    cmp_ = {"T1_vs_constant": compare(xT, wkly(b, days), piT, one, yr, mask)}
    for k, v in bx.items():
        cmp_[f"T1_vs_{k}"] = compare(xT, wkly(v["x"], days), piT, v["pi"], yr, mask)
        cmp_[f"{k}_vs_constant"] = compare(wkly(v["x"], days), wkly(b, days), v["pi"], one, yr, mask)
    bsh = {k: L.sharpe(wkly(v["x"], days)[mask]) for k, v in bx.items()}
    bstar = max(bsh, key=bsh.get)
    gate = {"benchmark_sharpes": bsh, "B_star_max": bstar,
            "vs_B_star": cmp_[f"T1_vs_{bstar}"]["pass"], "vs_other": cmp_[f"T1_vs_{[k for k in bsh if k != bstar][0]}"]["pass"]}
    gate["pass"] = bool(gate["vs_B_star"] and gate["vs_other"])
    res["comparisons_2015_2019_development"] = cmp_
    res["candidate_2015_2019_development"] = {"sharpe_net": L.sharpe(xT[mask]), "pct_per_year_arith": 100 * 52 * float(np.nanmean(xT[mask])),
                                              "mean_pi": float(np.mean(piT[mask])), "sd_pi": float(np.std(piT[mask], ddof=1)),
                                              "book_sharpe_same_weeks": L.sharpe(wkly(b, days)[mask]),
                                              "book_pct_per_year_arith": 100 * 52 * float(np.mean(wkly(b, days)[mask]))}
    res["gate"] = gate
    res["N_layer6_T1_configurations"] = len(L.CGRID) * len(L.ZGRID)
    json.dump(res, open(os.path.join(L.HERE, "RESULT.json"), "w"), indent=1, default=float)
    L.state(done=[f"dev grid + surface + gate written: gate pass {gate['pass']}"], running=["bootstrap null"])
    L.log("gate", gate, cmp_["T1_vs_constant"]["lw_hac"]["z"])
    # ---------------- bootstrap null (choices fixed at the selected (c, z))
    cfgs = sorted({tuple(v["cfg"]) for v in choice.values()})
    G.update(b=b, Zd=P["Zd"], end=P["end"], th=P["th"], names=P["names"], pos=np.searchsorted(P["th"], rows), rows=rows,
             gross=gross, cs=tuple(sorted({c for c, _ in cfgs})), zs=tuple(sorted({z for _, z in cfgs})),
             choice={Y: tuple(v["cfg"]) for Y, v in choice.items()}, yr=yr, mask=mask, days=days)
    obs = [res["candidate_2015_2019_development"]["sharpe_net"],
           res["candidate_2015_2019_development"]["sharpe_net"] - cmp_["T1_vs_constant"]["sharpe_b"],
           res["candidate_2015_2019_development"]["sharpe_net"] - bsh[bstar]]
    os.environ["OMP_NUM_THREADS"] = "1"
    seeds = [BOOT_SEED * 10 + i for i in range(NBOOT)]
    with get_context("fork").Pool(4) as pool:
        out = np.array(pool.map(boot_one, seeds, chunksize=10))
    np.save(os.path.join(L.CACHE, "boot_null.npy"), out)
    names = ["T1_sharpe", "T1_minus_constant_sharpe", "T1_minus_Bstar_sharpe"]
    res["bootstrap_null"] = {"draws": NBOOT, "mean_block": MEAN_BLOCK, "seed": BOOT_SEED, "cfgs_fixed": [list(c) for c in cfgs],
                             "stats": {n: {"observed": float(o), "null_mean": float(np.nanmean(out[:, i])),
                                           "null_q95": float(np.nanquantile(out[:, i], 0.95)),
                                           "p_one_sided": float(np.mean(out[:, i] >= o))} for i, (n, o) in enumerate(zip(names, obs))}}
    json.dump(res, open(os.path.join(L.HERE, "RESULT.json"), "w"), indent=1, default=float)
    L.state(done=["bootstrap null written"], running=[], next=["read only if gate passes" if gate["pass"] else "gate failed: no 2020-2025 read"])
    L.log("boot", res["bootstrap_null"])


if __name__ == "__main__":
    main()
