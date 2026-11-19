"""Layer 5 branch I, development (<= 2019): CIK verification, coverage contract, survivorship contract, the two
registered combinations with MASTER 5-day and the development gate. Writes RESULT.json ("development").

    OMP_NUM_THREADS=3 python3 research/tree/L5_insider/gate.py
"""
import json
import os
import sys
from datetime import datetime, timezone

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "3")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
sys.path.insert(0, TREE)
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
import lib as L  # noqa: E402

OVERLAY = 0.1


def state(**kw):
    p = os.path.join(HERE, "STATE.json")
    st = json.load(open(p))
    for k, v in kw.items():
        st[k] = st.get(k, []) + v if k == "done" else v
    st["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(st, open(p, "w"), indent=1)


def prank(a, ok):
    out = np.full(a.shape, np.nan)
    m = ok & np.isfinite(a)
    if m.sum():
        out[m] = pd.Series(a[m]).rank(pct=True).to_numpy()
    return out


def nw_t(x, lags=4):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n, d = len(x), x - x.mean()
    v = d @ d / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (d[l:] @ d[:-l]) / n
    return float(x.mean()), float(x.mean() / np.sqrt(v / n)), int(n)


def indicator_ic(ind, D, rows):
    out = []
    for t in rows:
        m = np.isfinite(D["y5"][t]) & D["elig"][t]
        x = ind[t][m].astype(float)
        if m.sum() < 50 or x.std() == 0:
            out.append(np.nan)
            continue
        out.append(float(pd.Series(x).corr(pd.Series(D["y5"][t][m]), method="spearman")))
    return np.array(out)


def build_scores(D, comps, rows, master):
    n = D["y5"].shape[1]
    ins = np.full(D["y5"].shape, np.nan)
    c1 = np.full(D["y5"].shape, np.nan)
    c2 = np.full(D["y5"].shape, np.nan)
    for i, t in enumerate(rows):
        ok = np.isfinite(master[t]) & D["elig"][t]
        R = np.vstack([prank(comps[k][i], ok) for k in ("cnt1", "cnt3", "val1", "val3")])
        cnt = np.isfinite(R).sum(0)
        s = np.where(cnt == 4, R.mean(0), np.nan)
        ins[t] = s
        pm = prank(master[t], ok)
        P = np.vstack([pm, prank(s, ok)])
        k = np.isfinite(P).sum(0)
        c1[t] = np.where(k > 0, np.nansum(P, 0) / np.maximum(k, 1), np.nan)
        c1[t][~ok] = np.nan
        sg = np.sign(comps["cnt3"][i])
        sg = np.where(sg == 0, np.sign(comps["val3"][i]), sg)
        c2[t] = pm + OVERLAY * np.nan_to_num(sg, nan=0.0)
        c2[t][~ok] = np.nan
    return ins, c1, c2


def main():
    D = H.load()
    S, names = D["S"], D["names"]
    F, T = L.load_raw()
    res = {"label": "development (data <= 2019)", "run_start": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "inputs": json.load(open(os.path.join(L.OUT, "MANIFEST.json")))["combined"]}
    F = F[F.filing_date <= S[-1]]
    T = T[T.filing_date <= S[-1]]

    # CIK verification
    cikmap, rows_map = L.verify_ciks(names, S, D["elig"], F)
    json.dump(rows_map, open(os.path.join(HERE, "cik_map_dev.json"), "w"), indent=1, default=str)
    dec = pd.Series([r["decision"] for r in rows_map]).value_counts().to_dict()
    th = np.where((S.weekday == 3) & (S.year >= 2013))[0]
    has = np.array([cikmap.get(n) is not None for n in names])
    el = D["elig"][th] & np.isfinite(D["y5"][th])
    res["cik_map"] = {"decisions": dec, "eligible_priced_name_weeks_with_cik_share_2013_2019": float((el & has).sum() / el.sum()),
                      "eligible_name_weeks_with_cik_share_2013_2019": float((D["elig"][th] & has).sum() / D["elig"][th].sum())}
    print("cik", res["cik_map"], flush=True)

    # coverage against expected
    man = json.load(open(os.path.join(L.OUT, "MANIFEST.json")))["quarters"]
    allq = [f"{y}q{q}" for y in range(2006, 2026) for q in (1, 2, 3, 4)]
    missing = [q for q in allq if q not in man]
    by = {}
    for q, v in man.items():
        by[int(q[:4])] = by.get(int(q[:4]), 0) + v["counts"]["all_4_5_filings"]
    med = float(np.median(list(by.values())))
    cik_of = {n: cikmap.get(n) for n in names}
    Ff = F.assign(y=F.filing_date.dt.year)
    Tt = T.assign(y=T.filing_date.dt.year)
    anyf = set(zip(Ff.cik.astype(int), Ff.y))
    anyt = set(zip(Tt.cik.astype(int), Tt.y))
    cov = {}
    for y in range(2009, 2020):
        ry = np.where(S.year == y)[0]
        nm = [n for j, n in enumerate(names) if D["elig"][ry, j].any() and cik_of[n] is not None]
        cov[y] = {"eligible_names_with_cik": len(nm),
                  "share_with_any_4_5": float(np.mean([(int(cik_of[n]), y) in anyf for n in nm])),
                  "share_with_any_P_or_S": float(np.mean([(int(cik_of[n]), y) in anyt for n in nm])),
                  "all_issuer_4_5_filings": by.get(y)}
    ok_cov = (not missing and all(0.5 * med <= v <= 2 * med for v in by.values())
              and all(v["share_with_any_4_5"] >= 0.9 and v["share_with_any_P_or_S"] >= 0.8 for v in cov.values()))
    res["coverage"] = {"quarters_missing": missing, "all_issuer_4_5_filings_by_year": by, "median_year": med,
                       "panel_by_year": cov, "pass": bool(ok_cov)}
    print("coverage pass", ok_cov, flush=True)
    if not ok_cov:
        json.dump(res, open(os.path.join(HERE, "RESULT.json"), "w"), indent=1, default=str)
        state(running=[], next=["STOPPED: coverage contract failed (typed defect)"])
        sys.exit("coverage contract failed")
    state(done=[f"CIK map {dec}; coverage contract passed"], running=["survivorship contract"])

    # survivorship contract
    rows = np.concatenate([H.thursdays(D, y) for y in H.VAL_YEARS])
    ind_a = np.broadcast_to(has, D["elig"].shape)
    first_pub = {}
    pidx = L.public_index(S, F.filing_date)
    for c, p in zip(F.cik.astype(int), pidx):
        first_pub[c] = min(first_pub.get(c, 10 ** 9), p)
    fp = np.array([first_pub.get(int(cik_of[n]), 10 ** 9) if cik_of[n] is not None else 10 ** 9 for n in names])
    ind_b = np.arange(len(S))[:, None] >= fp[None, :]
    sv = {}
    for k, ind in (("a_verified_cik", ind_a), ("b_any_4_5_public_before_t", ind_b)):
        ic = indicator_ic(ind, D, rows)
        m, t, n = nw_t(ic) if np.isfinite(ic).sum() > 10 else (float("nan"), float("nan"), int(np.isfinite(ic).sum()))
        sv[k] = {"ic": m, "nw_t": t, "weeks_defined": n, "share_name_weeks_indicator_1": float(ind[rows][D["elig"][rows]].mean()),
                 "pass": bool(not np.isfinite(t) or abs(t) < 2)}
    sv["pass"] = all(v["pass"] for v in sv.values() if isinstance(v, dict))
    res["survivorship_contract"] = sv
    print("survivorship", sv, flush=True)
    if not sv["pass"]:
        json.dump(res, open(os.path.join(HERE, "RESULT.json"), "w"), indent=1, default=str)
        state(running=[], next=["STOPPED: survivorship contract failed"])
        sys.exit("survivorship contract failed")
    state(done=["survivorship contract passed"], running=["signal + gate"])

    # signal
    To = L.opportunistic(T)
    G = L.accession_flows(To)
    comps = L.components(S, names, cikmap, G, rows)
    ty = To[To.trans_date.dt.year >= 2009]
    res["signal_stats"] = {"PS_transactions_2009_2019": int(len(ty)), "routine_share": float(ty.routine.mean()),
                           "P_share_of_opportunistic": float((ty[~ty.routine].code == "P").mean()),
                           "opportunistic_accessions": int(len(G)),
                           "share_ok_name_weeks_nonzero_cnt3": float(np.mean([np.mean(comps["cnt3"][i][np.isfinite(D["master_h5_ref"][t]) & D["elig"][t]] != 0)
                                                                            for i, t in enumerate(rows)])),
                           "share_ok_name_weeks_positive_cnt3": float(np.mean([np.mean(comps["cnt3"][i][np.isfinite(D["master_h5_ref"][t]) & D["elig"][t]] > 0)
                                                                             for i, t in enumerate(rows)]))}
    print("signal", res["signal_stats"], flush=True)
    master = D["master_h5_ref"].astype(np.float64)
    ins, c1, c2 = build_scores(D, comps, rows, master)
    np.savez_compressed(os.path.join(L.OUT, "dev_scores.npz"), insider=ins, C1=c1, C2=c2)
    log = os.path.join(HERE, "RESULTS.jsonl")
    res["insider_score_alone"] = H.score(ins, "insider score alone", log, "dev", D)
    res["insider_vs_master_increment"] = H.increment(ins, "insider score vs MASTER", None, "dev", D)
    gate = {}
    for k, p in (("C1_rank_average", c1), ("C2_sign_overlay", c2)):
        r = H.increment(p, k, log, "dev gate vs MASTER 5-day", D)
        r["gate_pass"] = bool(r["increment_t"] >= 2.0 and r["years_increment_positive"] >= 5)
        gate[k] = r
        print(k, {x: r[x] for x in ("ic", "base_ic", "increment", "increment_t", "years_increment_positive", "gate_pass")}, flush=True)
    res["gate"] = gate
    res["gate_passers"] = [k for k, v in gate.items() if v["gate_pass"]]
    res["run_end"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump({"development": res}, open(os.path.join(HERE, "RESULT.json"), "w"), indent=1, default=str)
    state(done=[f"gate: " + "; ".join(f"{k} inc {v['increment']:.4f} t {v['increment_t']:.2f} yrs+ {v['years_increment_positive']} pass {v['gate_pass']}" for k, v in gate.items())],
          running=[], next=["read 2020-2025 for " + ", ".join(res["gate_passers"])] if res["gate_passers"] else ["no gate passer: no read; report"])


if __name__ == "__main__":
    main()
