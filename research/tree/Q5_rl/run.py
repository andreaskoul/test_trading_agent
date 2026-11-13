"""Branch Q5_rl runner (resumable).

python run.py register NAME [NAME ...]   append to STATE.json plan + pending (names must be in SPECS)
python run.py score                      score everything pending, in order

Protocol per candidate configuration (method x signal):
* Training length (the only tuned hyperparameter; grid in LENGTHS) chosen by the seed-mean walk-forward net Sharpe on
  2014-2016 only; every grid point is logged to TUNING.jsonl. Learning rates, network sizes, the DSR rate, PPO
  constants and the 26-week window are fixed a priori (lib.py).
* Walk-forward (the scored series): year y in 2014-2019 uses the policy trained on weeks whose y5 ended before y;
  the book carries over between years; 2013 holds the control band book (its switch cost is charged in 2014).
* Seeds 0, 1, 2. The scored weekly net = mean of the three seeds' nets (three sub-books at 1/3 each).
* Fixed split check: trained once on 2013-2016 with the chosen length, run 2017-2019 from the walk-forward book held
  at the end of 2016.
* Controls on the same 2014-2019 weeks: (a) M1 band 0.1, (b) Q4 mvnl_nt (k 2) on the same signal.
"""
import json
import os
import sys
import time

import numpy as np
import torch

import lib
from lib import harness

HERE = lib.HERE
RES, STATE, TUNE = (os.path.join(HERE, f) for f in ("RESULTS.jsonl", "STATE.json", "TUNING.jsonl"))
SEEDS = (0, 1, 2)
LENGTHS = {"rrl_bs": (25, 100, 300), "rrl_dsr": (1, 3, 10), "e2e": (25, 100, 300), "eiie_pvm": (200, 1000, 3000),
           "ppo": (30, 100, 300), "rrl_dsr_book": (1, 3, 10), "rrl_dsr_exp": (1, 3, 10), "band15": (0,)}
NOTES = {"rrl_bs": "Moody-Saffell RRL, 13-parameter smooth-band policy + exposure(state), batch net Sharpe, full BPTT",
         "rrl_dsr": "Moody-Saffell RRL, same policy, online differential Sharpe ratio updates",
         "ppo": "PPO, linear-Gaussian policy on (trade rate, exit width, exposure) from state, DSR reward",
         "eiie_pvm": "EIIE shared per-name network + exposure head, portfolio-vector memory, 26-week mini-batches, net Sharpe",
         "e2e": "same EIIE network, full-sequence BPTT on net Sharpe (Zhang-Zohren-Roberts style, non-RL baseline)",
         "rrl_dsr_book": "POST HOC ablation of rrl_dsr: exposure fixed at 1, only band shape and tilts learn",
         "rrl_dsr_exp": "POST HOC ablation of rrl_dsr: book fixed at the band, only the exposure head learns",
         "band15": "POST HOC reference: unlearned smooth band, exit width 0.15 (rrl_dsr's learned h), exposure 1"}
SPECS = {}
for sig in ("trees", "ipca", "master"):
    SPECS[f"C_band_{sig}"] = (sig, "control", "control (a): M1 band 0.1 on the same signal")
    SPECS[f"C_mvnlnt_{sig}"] = (sig, "control", "control (b): Q4 mvnl_nt (LW2020 mean-variance, L1 no-trade k 2)")
    for meth in LENGTHS:
        SPECS[f"{meth}_{sig}"] = (sig, meth, NOTES[meth])


# ---------------------------------------------------------------- generic train / run
def train(meth, Pd, jend, lengths, ctl_W):
    if meth == "rrl_bs":
        return lib.train_rrl_bs(Pd, jend, SEEDS, lengths)
    if meth == "rrl_dsr":
        return lib.train_rrl_dsr(Pd, jend, SEEDS, lengths)
    if meth in ("rrl_dsr_book", "rrl_dsr_exp"):
        return lib.train_rrl_dsr(Pd, jend, SEEDS, lengths, freeze="exposure" if meth == "rrl_dsr_book" else "book")
    if meth == "band15":
        return {0: lib.fixed_band(len(SEEDS), 0.15)}
    out = {}
    for s in SEEDS:
        if meth == "e2e":
            sn = lib.train_e2e(Pd, jend, s, lengths)
        elif meth == "eiie_pvm":
            sn = lib.train_eiie_pvm(Pd, jend, s, lengths)
        elif meth == "ppo":
            sn = lib.train_ppo(Pd, jend, s, lengths, ctl_book=ctl_W)
        for L, v in sn.items():
            out.setdefault(L, []).append(v)
    return out


def run(meth, snap, Pd, j0, j1, pu, pw):
    """pu, pw: (nb, n) numpy per seed. Returns R (L, nb), W (L, nb, n), pu, pw."""
    if meth.startswith("rrl") or meth == "band15":
        with torch.no_grad():
            R, W, u, w = lib.run_seq(lib.rrl_stepper(snap, Pd), Pd, j0, j1, torch.as_tensor(pu), torch.as_tensor(pw))
        return R.numpy(), W.numpy(), u.numpy(), w.numpy()
    Rs, Ws, us, ws = [], [], [], []
    for i, st in enumerate(snap):
        if meth == "ppo":
            R, W, u, w = lib.ppo_run(st, Pd, j0, j1, pu[i], pw[i])
            Rs.append(R), Ws.append(W), us.append(u), ws.append(w)
        else:
            net = lib.EIIE(0)
            net.load_state_dict(st)
            with torch.no_grad():
                R, W, u, w = lib.run_seq(lib.eiie_stepper(net, Pd), Pd, j0, j1, torch.as_tensor(pu[i:i + 1]),
                                         torch.as_tensor(pw[i:i + 1]))
            Rs.append(R.numpy()[:, 0]), Ws.append(W.numpy()[:, 0]), us.append(u.numpy()[0]), ws.append(w.numpy()[0])
    return np.stack(Rs, 1), np.stack(Ws, 1), np.stack(us), np.stack(ws)


def score_candidate(name, sig, meth, Pd, ctl_W, D):
    T, n, ns = len(Pd["rows"]), Pd["Y"].shape[1], len(SEEDS)
    lengths = LENGTHS[meth]
    f, years = Pd["first"], Pd["years"]
    j14 = f[2014]
    W0 = ctl_W[j14 - 1]
    # the control band's unscaled book at the end of 2013 = its weights (gross 1)
    book = {L: {"R": np.zeros((T, ns)), "W": np.zeros((T, ns, n)), "pu": np.tile(W0, (ns, 1)), "pw": np.tile(W0, (ns, 1))}
            for L in lengths}
    t0 = time.time()
    wf_snaps = {}
    for y in range(2014, 2020):
        j0, j1 = f[y], (f[y + 1] if y < 2019 else T)
        snaps = train(meth, Pd, Pd["te"][y], lengths, ctl_W)
        wf_snaps[y] = snaps
        for L in lengths:
            b = book[L]
            R, W, b["pu"], b["pw"] = run(meth, snaps[L], Pd, j0, j1, b["pu"], b["pw"])
            b["R"][j0:j1], b["W"][j0:j1] = R, W
        print(f"  {name} {y} trained+run ({time.time() - t0:.0f}s)", flush=True)
    sel = slice(j14, T)
    yrs = years[sel]
    tune = []
    for L in lengths:
        R = book[L]["R"][sel]
        a = yrs <= 2016
        sh_seeds = [lib.shp(R[a, i]) for i in range(ns)]
        row = {"config": name, "length": L, "wf_net_sharpe_2014_2016_seed_mean": float(np.mean(sh_seeds)),
               "seeds": sh_seeds, "wf_net_sharpe_2017_2019_seed_mean_not_used": float(np.mean([lib.shp(R[~a, i]) for i in range(ns)])),
               "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        tune.append(row)
        with open(TUNE, "a") as fh:
            fh.write(json.dumps(row) + "\n")
    Lb = max(tune, key=lambda r: r["wf_net_sharpe_2014_2016_seed_mean"])["length"]
    b = book[Lb]
    Rs, Ws = b["R"][sel], b["W"][sel]
    net = Rs.mean(1)
    prevW = np.concatenate([np.tile(W0, (1, ns, 1)), b["W"][j14:T - 1]], 0)
    turn = (np.abs(Ws - prevW).sum(-1) / 2).mean(1)
    gross = np.einsum("tsn,tn->ts", Ws, Pd["Y"][sel]).mean(1)
    st = lib.stats(net, turn, yrs, gross)
    seed_sh = [lib.shp(Rs[:, i]) for i in range(ns)]
    seed_dd = [lib.max_dd(Rs[:, i]) for i in range(ns)]
    seed_p = {p: [lib.shp(Rs[(yrs <= 2016) if p == "2014-2016" else (yrs >= 2017), i]) for i in range(ns)]
              for p in ("2014-2016", "2017-2019")}
    # fixed split: trained once on 2013-2016 = the walk-forward 2017 fit; run 2017-2019 from the WF book at end-2016
    j17 = f[2017]
    pu, pw = b["W"][j17 - 1] / np.maximum(np.abs(b["W"][j17 - 1]).sum(-1, keepdims=True), 1e-12), b["W"][j17 - 1]
    Rf, _, _, _ = run(meth, wf_snaps[2017][Lb], Pd, j17, T, pu, pw)
    zero = np.zeros((ns, n))
    Rin, _, _, _ = run(meth, wf_snaps[2017][Lb], Pd, 0, j17, zero, zero)
    fs = {"oos_2017_2019_net_sharpe_seed_mean": float(np.mean([lib.shp(Rf[:, i]) for i in range(ns)])),
          "oos_2017_2019_net_sharpe_seeds": [lib.shp(Rf[:, i]) for i in range(ns)],
          "oos_2017_2019_net_pct_per_year": float(52 * Rf.mean() * 100),
          "insample_2013_2016_net_sharpe_seed_mean": float(np.mean([lib.shp(Rin[1:, i]) for i in range(ns)]))}
    # stock-leg net beta carried by the implicit SPY hedge
    hb = float(np.mean(np.abs(np.einsum("tsn,tn->ts", Ws, Pd["B"][sel] + Pd["M"][sel]))))
    dol = float(np.max(np.abs(Ws.sum(-1))))
    exposure = float(np.abs(Ws).sum(-1).mean())
    return net, {**st, "spec": {"method": meth, "length": Lb, "grid": list(lengths), "seeds": list(SEEDS)},
                 "seeds_net_sharpe": seed_sh, "seeds_spread": float(np.max(seed_sh) - np.min(seed_sh)),
                 "seeds_max_drawdown": seed_dd, "seeds_by_period_net_sharpe": seed_p, "fixed_split": fs,
                 "mean_gross": exposure, "max_abs_dollar_net": dol, "mean_abs_stock_beta_hedged_by_spy": hb,
                 "tuning": tune, "seconds": time.time() - t0}


def update_state(fn):
    import fcntl
    with open(STATE + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        st = json.load(open(STATE))
        fn(st)
        st["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        json.dump(st, open(STATE + ".tmp", "w"), indent=1)
        os.replace(STATE + ".tmp", STATE)


def register(names):
    def f(st):
        for nme in names:
            assert nme in SPECS, nme
            sig, meth, note = SPECS[nme]
            if nme not in [p["name"] for p in st["plan"]]:
                st["plan"].append({"name": nme, "signal": sig, "method": meth,
                                   "length_grid": list(LENGTHS.get(meth, ())), "seeds": list(SEEDS), "note": note})
            if nme not in st["pending"] and nme not in st["scored"]:
                st["pending"].append(nme)
        st["status"] = "running"
    update_state(f)


def score(only=None):
    D = harness.load()
    S = lib.signals(D)
    cache = {}
    while True:
        st = json.load(open(STATE))
        todo = [p for p in st["pending"] if only is None or SPECS[p][0] == only]
        if not todo:
            break
        name = todo[0]
        sig, meth, note = SPECS[name]
        if sig not in cache:
            Pd = lib.prep(D, S[sig])
            Wb = lib.control_band(D, S[sig], Pd)
            Wm = lib.control_mvnl_nt(D, S[sig], Pd, sig)
            cache[sig] = (Pd, Wb, lib.net_of(Wb, Pd), lib.net_of(Wm, Pd), Wm)
        Pd, Wb, (nb_, tb_), (nm_, tm_), Wm = cache[sig]
        j14 = Pd["first"][2014]
        sel = slice(j14, None)
        yrs = Pd["years"][sel]
        if meth == "control":
            W = Wb if name.startswith("C_band") else Wm
            net, turn = lib.net_of(W, Pd)
            net, turn = net[sel], turn[sel]
            gross = (W * Pd["Y"]).sum(1)[sel]
            row = {**lib.stats(net, turn, yrs, gross), "spec": {"method": "control"},
                   "full_2013_2019_net_sharpe_skip_first": lib.shp(lib.net_of(W, Pd)[0][1:]),
                   "mean_gross": float(np.abs(W[sel]).sum(1).mean())}
        else:
            net, row = score_candidate(name, sig, meth, Pd, Wb, D)
        row["vs_control_band"] = lib.versus(net, nb_[sel], yrs)
        row["vs_control_mvnlnt"] = lib.versus(net, nm_[sel], yrs)
        row = {"name": name, "note": note, "signal": sig, "weeks": int(len(net)), "period": "2014-2019 (walk-forward)",
               **row, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        import fcntl
        with open(RES, "a") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.write(json.dumps(row) + "\n")
        np.save(os.path.join(lib.PREDS, f"{name}.npy"), net)
        print(json.dumps({k: row.get(k) for k in ("name", "net_pct_per_year", "net_sharpe", "gross_sharpe", "max_drawdown",
                                                 "turnover", "seeds_net_sharpe")}), flush=True)
        print("   by_period", json.dumps(row["by_period"]), "| vs band", json.dumps({k: round(v, 3) for k, v in row["vs_control_band"].items()}),
              "| fs", json.dumps(row.get("fixed_split")), flush=True)

        def f(st):
            st["pending"].remove(name)
            st["scored"].append(name)
            st["configurations_scored"] = len(st["scored"])
            if meth != "control":
                ctl_dd = row["vs_control_band"]["max_drawdown_at_control_vol"] <= row["vs_control_band"]["control_max_drawdown"]
                if ctl_dd and (st["best"] is None or row["net_sharpe"] > st["best"]["net_sharpe"]):
                    st["best"] = {"name": name, "signal": sig, "net_sharpe": row["net_sharpe"],
                                  "net_pct_per_year": row["net_pct_per_year"], "max_drawdown": row["max_drawdown"],
                                  "vs_band": row["vs_control_band"], "vs_mvnlnt": row["vs_control_mvnlnt"]}
            st["notes"].append(f"scored {name}; next: {st['pending'][0] if st['pending'] else 'deliverables'}")
        update_state(f)


if __name__ == "__main__":
    if sys.argv[1] == "register":
        register(sys.argv[2:])
    else:
        score(sys.argv[2] if len(sys.argv) > 2 else None)
