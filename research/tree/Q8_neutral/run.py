"""Score the registered Q8 configurations (STATE.json plan) on development data 2013-2019. Usage: python run.py"""
import importlib.util
import json
import os
import sys
import time

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[v] = "3"
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
sys.path.insert(0, TREE)
sys.path.insert(0, HERE)
import harness  # noqa: E402
import model  # noqa: E402

OUT = os.path.join(ROOT, ".cache", "tree", "preds", "Q8_neutral")
LOG = os.path.join(HERE, "RESULTS.jsonl")
STATE = os.path.join(HERE, "STATE.json")


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


m1 = _mod("m1lib_q8", os.path.join(TREE, "M1_dyntrade", "lib.py"))
q4 = _mod("q4lib_q8", os.path.join(TREE, "Q4_portfolio", "lib.py"))
nw_t, max_dd = q4.nw_t, q4.max_dd


def sh(x):
    x = x[np.isfinite(x)]
    return float(x.mean() / x.std(ddof=1) * np.sqrt(52)) if len(x) > 2 else float("nan")


def weekly(pred, D, rows):
    """Per validation Thursday: IC, decile net (harness), band net (M1). NaN where a book is not formed."""
    ic = harness.weekly_ic(pred, D, rows)
    dn = np.full(len(rows), np.nan)
    ok = np.array([(np.isfinite(pred[t]) & np.isfinite(D["y5"][t]) & D["elig"][t]).sum() >= 50 for t in rows])
    dn[ok] = harness.decile_net(pred, D, rows)
    vr = m1.val_rows(D, pred)
    sim = m1.simulate(m1.build("band", pred, D, vr), D, vr)
    bn = np.full(len(rows), np.nan)
    pos = {t: j for j, t in enumerate(rows)}
    for j, t in enumerate(vr[1:], 1):                    # M1 summary convention: the first week is dropped
        bn[pos[t]] = sim["net"][j]
    bt = np.full(len(rows), np.nan)
    for j, t in enumerate(vr[1:], 1):
        bt[pos[t]] = sim["turn"][j]
    return np.column_stack([rows, ic, dn, bn, bt])


def block(W, yrs, sel):
    ic, dn, bn = W[sel, 1], W[sel, 2], W[sel, 3]
    ic = ic[np.isfinite(ic)]
    d, b = dn[np.isfinite(dn)], bn[np.isfinite(bn)]
    return {"ic": float(ic.mean()), "ic_sd": float(ic.std(ddof=1)), "ic_t": float(ic.mean() / ic.std(ddof=1) * np.sqrt(len(ic))),
            "ic_t_nw": nw_t(ic), "weeks": int(len(ic)), "decile_net_pct_per_year": float(52 * d.mean() * 100),
            "decile_net_sharpe": sh(d), "decile_max_drawdown": max_dd(d), "band_net_pct_per_year": float(52 * b.mean() * 100),
            "band_net_sharpe": sh(b), "band_max_drawdown": max_dd(b), "band_turnover": float(np.nanmean(W[sel, 4]))}


def stats(W, D, base=None):
    yrs = D["S"][W[:, 0].astype(int)].year.to_numpy()
    full, a, b = np.ones(len(W), bool), yrs <= 2016, yrs >= 2017
    res = block(W, yrs, full)
    res["net_sharpe"] = res["decile_net_sharpe"]
    res["ic_by_year"] = {int(y): float(np.nanmean(W[yrs == y, 1])) for y in np.unique(yrs)}
    res["decile_net_by_year_pct"] = {int(y): float(52 * np.nanmean(W[yrs == y, 2]) * 100) for y in np.unique(yrs)}
    res["split_2013_2016"], res["split_2017_2019"] = block(W, yrs, a), block(W, yrs, b)
    if base is not None:
        for nm, sel in (("vs_N0", full), ("vs_N0_2013_2016", a), ("vs_N0_2017_2019", b)):
            o = {}
            for k, c in (("ic", 1), ("decile_net", 2), ("band_net", 3)):
                dd = W[sel, c] - base[sel, c]
                dd = dd[np.isfinite(dd)]
                scale = 1.0 if k == "ic" else 52 * 100
                o[f"{k}_diff"] = float(dd.mean() * scale)
                o[f"{k}_diff_nw_t"] = nw_t(dd)
            res[nm] = o
    return res


def ehl(scores, D, rows, sec):
    """Ehsani-Harvey-Li decomposition on the given rows: across-sector vs within-sector components of the rank-weighted
    book (primary) and of the decile book (descriptive); gross weekly returns w . y5."""
    out = {}
    for kind in ("rank", "decile"):
        ra, rw = [], []
        for t in rows:
            m = m1.mask(scores, D, t)
            if m.sum() < 50:
                continue
            if kind == "rank":
                w = m1.sides(np.where(m, np.nan_to_num(pd.Series(scores[t]).where(m).rank(pct=True).to_numpy() - 0.5), 0.0))
            else:
                w = m1.aim_decile(scores[t], m)
            wa = np.zeros_like(w)
            for g in np.unique(sec[m]):
                k = m & (sec == g)
                wa[k] = w[k].mean()
            y = np.nan_to_num(D["y5"][t])
            ra.append(wa @ y), rw.append((w - wa) @ y)
        ra, rw = np.array(ra), np.array(rw)
        sa, sw, rho = sh(ra), sh(rw), float(np.corrcoef(ra, rw)[0, 1])
        out[kind] = {"sr_across": sa, "sr_within": sw, "corr": rho, "ratio": sa / sw if sw != 0 else float("nan"),
                     "neutralise": bool(sa / sw < rho) if sw > 0 else None, "weeks": int(len(ra))}
    return out


def save_state(done, pending, note, best=None, extra=None):
    s = json.load(open(STATE))
    s["scored"] = done
    s["configurations_scored"] = len(done)
    s["pending"] = pending
    if best is not None:
        s["best"] = best
    if extra:
        s.update(extra)
    s["notes"].append(note)
    s["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(s, open(STATE, "w"), indent=1)


def main():
    os.makedirs(OUT, exist_ok=True)
    D = harness.load()
    rows = np.concatenate([harness.thursdays(D, y) for y in harness.VAL_YEARS])
    sec = model.sectors(D["names"])
    S = {"trees": np.load(os.path.join(ROOT, ".cache", "tree", "preds", "Q4_portfolio", "sig_trees.npy")),
         "ipca": np.load(os.path.join(ROOT, ".cache", "tree", "preds", "Q4_portfolio", "sig_ipca.npy")),
         "master": D["master_h5_ref"].astype(np.float64)}
    st = json.load(open(STATE))
    done, pending = list(st["scored"]), list(st["pending"])
    yrs = D["S"][rows].year.to_numpy()
    for sig, raw in S.items():
        m = np.isfinite(raw[rows]) & D["elig"][rows]
        audit = {"scored_name_weeks": int(m.sum()), "with_sector": float((m & (sec != "NA")[None]).sum() / m.sum())}
        W, P = {}, {}
        for mode in ("N0", "N1", "N2w"):
            P[mode] = model.neutralise(raw, D, rows, mode=mode, sec=sec)
            print(sig, mode, model.check(D, rows, raw, P[mode]), flush=True)
            W[mode] = weekly(P[mode], D, rows)
            np.save(os.path.join(OUT, f"{sig}_{mode}.npy"), W[mode])
            np.save(os.path.join(OUT, f"{sig}_{mode}_scores.npy"), P[mode].astype(np.float32))
        for mode in ("N0", "N1", "N2w"):
            name = f"{sig}_{mode}"
            res = {"name": name, "signal": sig, "config": mode, "sector_audit": audit,
                   **stats(W[mode], D, None if mode == "N0" else W["N0"]),
                   "note": "weekly array columns: row, ic, decile_net, band_net, band_turnover", "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            with open(LOG, "a") as f:
                f.write(json.dumps(res) + "\n")
            print(json.dumps({k: res[k] for k in ("name", "ic", "ic_sd", "ic_t", "decile_net_pct_per_year", "net_sharpe", "decile_max_drawdown", "band_net_sharpe")}), flush=True)
            done.append(name)
            pending.remove(name)
            save_state(done, pending, f"scored {name}; next: {pending[0] if pending else 'report'}")
        # Ehsani-Harvey-Li rule, 2013-2016 only
        r16 = rows[yrs <= 2016]
        rule = ehl(raw, D, r16, sec)
        dec = rule["rank"]["neutralise"]
        applied = "N2w" if dec else "N0"
        Wd = W[applied]
        y = D["S"][Wd[:, 0].astype(int)].year.to_numpy()
        b = y >= 2017
        res = {"name": f"{sig}_N2rule", "signal": sig, "config": "N2rule", "rule_2013_2016": rule,
               "rule_full_period_descriptive": ehl(raw, D, rows, sec), "rule_2017_2019_descriptive": ehl(raw, D, rows[yrs >= 2017], sec),
               "decision": "neutralise (within-sector ranks)" if dec else "keep across-sector (raw)", "applied": applied,
               "applied_2017_2019": block(Wd, y, b), "N0_2017_2019": block(W["N0"], y, b),
               "applied_vs_N0_2017_2019": stats(Wd, D, W["N0"])["vs_N0_2017_2019"] if applied != "N0" else None,
               "full_period_N0": {"net_sharpe": stats(W["N0"], D)["net_sharpe"]}, "full_period_N2w": {"net_sharpe": stats(W["N2w"], D)["net_sharpe"]},
               "net_sharpe": block(Wd, y, b)["decile_net_sharpe"], "net_sharpe_note": "2017-2019 decile net Sharpe of the applied choice",
               "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with open(LOG, "a") as f:
            f.write(json.dumps(res) + "\n")
        print(json.dumps({k: res[k] for k in ("name", "rule_2013_2016", "decision", "net_sharpe")}), flush=True)
        done.append(f"{sig}_N2rule")
        pending.remove(f"{sig}_N2rule")
        save_state(done, pending, f"scored {sig}_N2rule (EHL decision: {res['decision']}); next: {pending[0] if pending else 'report'}")


if __name__ == "__main__":
    main()
