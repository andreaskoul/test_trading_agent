"""L5 breadth, development (<= 2019): coverage checks, survivorship contract, then (only if it passes) the gate for
C1 (rank average with MASTER 5-day) and C2 (sign-only overlay). Rules: STATE.json plan. -> RESULT.json

    OMP_NUM_THREADS=3 python3 research/tree/L5_breadth/dev.py
"""
import glob
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
C5 = os.path.join(ROOT, ".cache", "tree", "l5breadth")
sys.path.insert(0, TREE)
import harness as H  # noqa: E402

YEARS = tuple(range(2014, 2020))


def nw(x, lags=4):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n, d = len(x), x - x.mean()
    v = d @ d / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (d[l:] @ d[:-l]) / n
    return float(x.mean()), float(x.mean() / np.sqrt(v / n)), int(n)


def prank(a, ok):
    out = np.full(a.shape, np.nan)
    m = ok & np.isfinite(a)
    if m.sum():
        out[m] = pd.Series(a[m]).rank(pct=True).to_numpy()
    return out


def state(**kw):
    p = os.path.join(HERE, "STATE.json")
    st = json.load(open(p))
    for k, v in kw.items():
        st[k] = st.get(k, []) + v if k == "done" else v
    st["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(st, open(p, "w"), indent=1)


def main():
    D = H.load()
    S, names = D["S"], D["names"]
    sc = np.load(os.path.join(C5, "score_dev.npy")).astype(np.float64)
    info = json.load(open(os.path.join(C5, "score_dev_info.json")))
    PN = json.load(open(os.path.join(C5, "panel_names.json")))
    man = json.load(open(os.path.join(C5, "MANIFEST.json")))
    res = {"label": "development, Thursdays 2014-2019", "run_start": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "inputs": {"holdings.parquet_sha256": man["holdings.parquet"]["sha256"], "holdings_rows": man["holdings.parquet"]["rows"],
                      "zips": {k: v["sha256"] for k, v in man.items() if k.endswith(("q1", "q2", "q3", "q4"))}}}

    # ------------------------------------------------ coverage against what was expected
    h = pd.read_parquet(os.path.join(C5, "holdings.parquet"))
    rep = h[h.issuer == -1]
    fp = rep.groupby("period").filer.nunique()
    fp = fp[(fp.index >= "2013-06-30") & (fp.index <= "2019-09-30")]
    qoq = fp.pct_change()
    filers = {str(p.date()): int(n) for p, n in fp.items()}
    defects = [p for p, n in filers.items() if n < 3000] + [str(p.date()) for p, x in qoq.items() if x < -0.2]
    stats = {}
    for f in sorted(glob.glob(os.path.join(C5, "parsed", "*.json"))):
        j = json.load(open(f))["stats"]
        stats[j["file"]] = {k: j[k] for k in ("reports_kept", "summarypage_rows_agree_share", "cusips_mapped", "panel_ciks_mapped",
                                              "panel_ciks_valid_name", "cusip_bad_length_rows", "non_equity_issue_rows")}
    rows_all = np.concatenate([H.thursdays(D, y) for y in YEARS])
    by = {}
    for y in YEARS:
        r = H.thursdays(D, y)
        el = D["elig"][r]
        by[y] = {"eligible_name_weeks_scored": float((np.isfinite(sc[r]) & el).sum() / el.sum()),
                 "eligible_with_cik": float(el[:, [n in PN["ticker_cik"] for n in names]].sum() / el.sum()),
                 "eligible_scored_and_master": float((np.isfinite(sc[r]) & np.isfinite(D["master_h5_ref"][r]) & el).sum() /
                                                     (np.isfinite(D["master_h5_ref"][r]) & el).sum())}
    per = pd.Series([x["period"] for x in info if pd.Timestamp(x["t"]).year in YEARS])
    res["coverage"] = {"filers_per_period": filers, "filer_count_defects": defects, "per_file": stats,
                       "panel": {"tickers": PN["n_tickers"], "with_cik": PN["n_with_cik"], "ciks": PN["n_ciks"]},
                       "by_year": by, "thursdays_without_score": int(per.isna().sum()),
                       "period_used_counts": per.value_counts().sort_index().to_dict(),
                       "share_weeks_on_latest_quarter_note": "see period_used_counts"}
    # spot check
    sp = {}
    g = h[h.period == pd.Timestamp("2016-06-30")]
    for t in ("AAPL", "JPM", "XOM", "MSFT", "WMT"):
        c = PN["ticker_cik"].get(t)
        sp[t] = {"cik": c, "filers_holding_2016-06-30": int((g.issuer == c).sum()) if c else None,
                 "filers_2016-06-30": int((g.issuer == -1).sum())}
    tq = [i for i, x in enumerate(info) if x["t"] == "2016-09-01"]
    res["spot_check"] = sp
    json.dump(res, open(os.path.join(HERE, "RESULT.json"), "w"), indent=1, default=str)
    if defects:
        state(done=[f"coverage defect: {defects}"], running=[], next=["STOPPED: filer coverage defect"])
        sys.exit(f"filer coverage defect {defects}")

    # ------------------------------------------------ survivorship contract
    ind = np.where(np.isfinite(sc), 1.0, 0.0)
    ic = H.weekly_ic(ind, D, rows_all)
    m, t, n = nw(ic)
    byy = {int(y): float(np.nanmean(H.weekly_ic(ind, D, H.thursdays(D, y)))) for y in YEARS}
    passed = abs(t) < 2
    res["survivorship_contract"] = {"indicator": "breadth score finite (1) vs not (0), eligible names", "ic": m, "nw_t": t, "weeks": n,
                                    "ic_by_year": byy, "pass": bool(passed)}
    # descriptive companion: CIK availability alone
    cik = np.zeros(sc.shape)
    cik[:, [j for j, nm in enumerate(names) if nm in PN["ticker_cik"]]] = 1.0
    ic2 = nw(H.weekly_ic(cik, D, rows_all))
    res["survivorship_contract"]["descriptive_cik_available_indicator"] = {"ic": ic2[0], "nw_t": ic2[1]}
    json.dump(res, open(os.path.join(HERE, "RESULT.json"), "w"), indent=1, default=str)
    state(done=[f"survivorship contract: availability IC {m:+.4f}, NW t {t:.2f} ({n} weeks) -> {'pass' if passed else 'REJECTED'}"])
    if not passed:
        state(running=[], next=["STOPPED: rejected at the survivorship contract; no gate, no read"], status="rejected at survivorship contract")
        print("REJECTED at survivorship contract", m, t)
        return

    # ------------------------------------------------ development gate
    base = D["master_h5_ref"].astype(np.float64)
    ok = np.isfinite(base) & D["elig"]
    c1 = np.full(base.shape, np.nan)
    c2 = np.full(base.shape, np.nan)
    for r in rows_all:
        R = np.vstack([prank(base[r], ok[r]), prank(sc[r], ok[r])])
        cnt = np.isfinite(R).sum(0)
        v = np.where(cnt > 0, np.nansum(R, 0) / np.maximum(cnt, 1), np.nan)
        v[~ok[r]] = np.nan
        c1[r] = v
        sg = np.where(np.isfinite(sc[r]), np.sign(sc[r]), 0.0)
        c2[r] = np.where(ok[r], prank(base[r], ok[r]) + 0.1 * sg, np.nan)
    gate = {}
    for k, p in (("C1_rank_average", c1), ("C2_sign_overlay", c2)):
        g = H.increment(p, k, os.path.join(HERE, "RESULTS.jsonl"), "L5 breadth dev gate", D=D, years=YEARS, base=base)
        g["pass"] = bool(g["increment_t"] >= 2.0 and g["years_increment_positive"] >= 4)
        gate[k] = g
    alone = H.score(sc, "breadth change alone (descriptive)", None, "", D=D, years=YEARS)
    res["gate"] = gate
    res["breadth_alone_descriptive"] = alone
    res["gate_passers"] = [k for k, v in gate.items() if v["pass"]]
    res["run_end"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(res, open(os.path.join(HERE, "RESULT.json"), "w"), indent=1, default=str)
    state(done=["gate: " + "; ".join(f"{k} increment {v['increment']:+.4f} t {v['increment_t']:.2f}, {v['years_increment_positive']}/6 years -> "
                                      f"{'PASS' if v['pass'] else 'fail'}" for k, v in gate.items())])
    print(json.dumps({k: {x: gate[k][x] for x in ("increment", "increment_t", "years_increment_positive", "pass")} for k in gate}, indent=1))


if __name__ == "__main__":
    main()
