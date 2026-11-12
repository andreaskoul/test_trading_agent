"""Branch Q4 runner. Scores every configuration in STATE.json "pending" (specs below), resumable.

python run.py register NAME [NAME ...]   append names (must be in SPECS) to plan + pending
python run.py score                      score everything pending, in order

Hyperparameters: the band (0.1), the vol-managed cap (2), the drawdown rule (1.0 / 0.5 x vol, exposure 0.5) and the
covariance window (252) are fixed a priori. The partial-adjustment rate tau is chosen per signal and target on
2013-2016 only (grid 0.25 / 0.5 / 0.75, by net Sharpe; TUNING.jsonl); 2017-2019 is reported separately as the check.
"""
import json
import os
import sys
import time

import numpy as np

import lib
from lib import harness

HERE = lib.HERE
RES, STATE, TUNE = (os.path.join(HERE, f) for f in ("RESULTS.jsonl", "STATE.json", "TUNING.jsonl"))
TAUS = (0.25, 0.5, 0.75)
NTS = (0.5, 1.0, 2.0)          # no-trade half-width in units of the mean |target weight|, tuned on 2013-2016
NTS_WIDE = (2.0, 3.0, 4.0, 6.0)   # registered after mvnl_nt_trees chose the grid edge (2.0); still tuned on 2013-2016

SPECS = {}
for sig in ("master", "trees", "ipca", "blend"):
    SPECS[f"C_band_{sig}"] = (sig, {"target": "band"}, "declared control: M1 no-trade band 0.1, equal weights")
    SPECS[f"R_decile_{sig}"] = (sig, {"target": "decile"}, "reference: phase-1 decile book (not a candidate)")
    SPECS[f"rank_{sig}"] = (sig, {"target": "rank"}, "rank-proportional weights over all names, sides 0.5")
    SPECS[f"rank_pa_{sig}"] = (sig, {"target": "rank", "tau": "tune"}, "rank-proportional + partial adjustment (tau tuned 2013-16)")
    SPECS[f"mvnl_{sig}"] = (sig, {"target": "mvnl"}, "mean-variance, LW2020 nonlinear shrinkage, dollar+beta neutral, gross 1")
    SPECS[f"mvnl_pa_{sig}"] = (sig, {"target": "mvnl", "tau": "tune"}, "mvnl + partial adjustment (tau tuned 2013-16)")
    SPECS[f"band_legvol_{sig}"] = (sig, {"target": "band", "legvol": True}, "band + leg vol matching (LW-NL leg vols)")
    SPECS[f"band_vm_{sig}"] = (sig, {"target": "band", "vm": 2.0}, "band + Moreira-Muir inverse-variance scaling, cap 2")
    SPECS[f"mvnl_nt_{sig}"] = (sig, {"target": "mvnl", "nt": "tune"}, "mvnl + L1 no-trade region (k tuned 2013-16)")
    SPECS[f"mvnl_ntx_{sig}"] = (sig, {"target": "mvnl", "nt": "tune_wide"}, "mvnl + no-trade region, wider grid 2/3/4/6 (tuned 2013-16)")
    SPECS[f"mvlw_nt_{sig}"] = (sig, {"target": "mvlw", "nt": "tune"}, "ablation: linear LW (2004) instead of LW2020, + no-trade region")
    SPECS[f"band_dd_{sig}"] = (sig, {"target": "band", "dd": True}, "band + drawdown-conditioned exposure (0.5 when DD > 1 vol)")


def full_spec(name, spec, S, D, rows):
    spec = dict(spec)
    if spec["target"] == "decile":
        return spec
    for key, grid in (("tau", TAUS), ("nt", NTS), ("nt", NTS_WIDE)):
        if spec.get(key) != ("tune_wide" if grid is NTS_WIDE else "tune"):
            continue
        sig = SPECS[name][0]
        best = None
        for val in grid:
            tau = val
            sp = dict(spec, **{key: val})
            net, st, _ = lib.run(sp, S[sig], D, rows)
            row = {"config": name, key: val, "net_sharpe_2013_2016": st["net_sharpe_2013_2016"],
                   "net_pct_2013_2016": st["net_pct_2013_2016"], "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            with open(TUNE, "a") as f:
                f.write(json.dumps(row) + "\n")
            if best is None or st["net_sharpe_2013_2016"] > best[1]:
                best = (tau, st["net_sharpe_2013_2016"])
        spec[key] = best[0]
    return spec


def run_decile(S, sig, D, rows):
    W = lib.m1.build("decile", S[sig], D, rows)
    sim = lib.simulate(W, D, rows)
    net = sim["net"][1:]
    years = D["S"][rows[1:]].year.to_numpy()
    return net, lib.stats(net, sim["turn"][1:], np.abs(W[1:]).sum(1), years)


def update_state(fn):
    st = json.load(open(STATE))
    fn(st)
    st["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(st, open(STATE, "w"), indent=1)


def register(names):
    def f(st):
        for n in names:
            assert n in SPECS, n
            sig, spec, note = SPECS[n]
            if n not in [p["name"] for p in st["plan"]]:
                st["plan"].append({"name": n, "signal": sig, "spec": spec, "note": note})
            if n not in st["pending"] and n not in st["scored"]:
                st["pending"].append(n)
        st["status"] = "running"
    update_state(f)


def score():
    D = harness.load()
    S = lib.signals(D)
    rows = {k: lib.val_rows(D, v) for k, v in S.items()}
    ctl = {}
    while True:
        st = json.load(open(STATE))
        if not st["pending"]:
            break
        name = st["pending"][0]
        sig, spec, note = SPECS[name]
        r = rows[sig]
        if sig not in ctl:
            p = os.path.join(lib.PREDS, f"C_band_{sig}.npy")
            ctl[sig] = np.load(p) if os.path.exists(p) else lib.run({"target": "band"}, S[sig], D, r)[0]
        sp = full_spec(name, spec, S, D, r)
        if sp["target"] == "decile":
            net, stt = run_decile(S, sig, D, r)
        else:
            net, stt, _ = lib.run(sp, S[sig], D, r)
        d = net - ctl[sig]
        years = D["S"][r[1:]].year.to_numpy()
        row = {"name": name, "note": note, "signal": sig, "spec": sp, **stt,
               "vs_control_diff_pct_per_year": float(52 * d.mean() * 100),
               "vs_control_t_nw4": lib.nw_t(d) if np.abs(d).sum() > 0 else 0.0,
               "vs_control_diff_2013_2016": float(52 * d[years <= 2016].mean() * 100),
               "vs_control_diff_2017_2019": float(52 * d[years >= 2017].mean() * 100),
               "max_drawdown_at_control_vol": lib.max_dd(net * ctl[sig].std(ddof=1) / net.std(ddof=1)),
               "weeks": int(len(net)), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with open(RES, "a") as f:
            f.write(json.dumps(row) + "\n")
        np.save(os.path.join(lib.PREDS, f"{name}.npy"), net)
        print(json.dumps({k: row[k] for k in ("name", "net_pct_per_year", "net_sharpe", "max_drawdown", "turnover",
                                              "vs_control_diff_pct_per_year", "vs_control_t_nw4", "net_sharpe_2013_2016",
                                              "net_sharpe_2017_2019")}), flush=True)

        def f(st):
            st["pending"].remove(name)
            st["scored"].append(name)
            st["configurations_scored"] = len(st["scored"])
            cand = not name.startswith(("C_", "R_"))
            if cand and (st["best"] is None or row["net_sharpe"] > st["best"]["net_sharpe"]):
                st["best"] = {"name": name, "signal": sig, "net_sharpe": row["net_sharpe"],
                              "net_pct_per_year": row["net_pct_per_year"], "max_drawdown": row["max_drawdown"],
                              "vs_control_diff_pct_per_year": row["vs_control_diff_pct_per_year"],
                              "vs_control_t_nw4": row["vs_control_t_nw4"]}
            st["notes"].append(f"scored {name}; next: {st['pending'][0] if st['pending'] else 'deliverables'}")
        update_state(f)


if __name__ == "__main__":
    if sys.argv[1] == "register":
        register(sys.argv[2:])
    else:
        score()
