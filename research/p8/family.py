"""The single validation read of P8 family H (PREREG_thesis_tree.md §2, §6; Amendments 4-6).

    python research/p8/family.py --read-validation     # ONCE. Refuses if the lock exists.
    python research/p8/family.py --dry-fit             # the same code on the fit sample (2012-2021), no lock, B = 199

Committed before any validation statistic existed. Rules:
* Validation sample: events / signal months with t0 (or month) in 2022-01-01 .. 2025-12-31 whose target window is
  fully observed by 2025-12-31 (the data stop there; the sealed window is never loaded).
* Per universe (S&P 500 point in time; S&P 400 current list), one family of m = 7: H1, H2, H2b, H3a, H3b, H4, H5.
  - H4 is sector-level, not universe-specific: its p enters both families.
  - H2's registered arm is S&P 400 suppliers with a named S&P 500 customer: it enters the S&P 400 family; in the
    S&P 500 family it enters with p = 1. If its gates fail, p = 1 in both.
  - H2b: p = 1 (Amendment 5 A1). A test that could not be built: p = 1.
* p of a test: event tests max(p_WCR, p_RI) (B = 9,999); FM tests the calibrated NW(3) p.
* Pass on validation: Holm-adjusted p <= 0.05, AND the registered sign of the primary statistic in 2022-23 and in
  2024-25 separately, AND net long-short spread > 0 (Amendment 4/5 definitions).
* Survivors go to the sealed read (Amendment 4: registered sign and net spread > 0 on Jan-Sep 2026), run separately.
* Output: reports/research/p8/VALIDATION_READ.md and .json, and the lock reports/research/p8/VALIDATION_READ.lock
  (written first, with the commit hash and time, so a second read cannot pass unnoticed).
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h1 as H1                                                  # noqa: E402
import h3a as H3A                                                # noqa: E402
import h3b as H3B                                                # noqa: E402
import h4 as H4                                                  # noqa: E402
import inference as I                                            # noqa: E402
import prices as PX                                              # noqa: E402

LOCK = os.path.join(PX.OUT, "VALIDATION_READ.lock")
V0, V1 = pd.Timestamp("2022-01-01"), pd.Timestamp("2025-12-31")
HALVES = ((pd.Timestamp("2022-01-01"), pd.Timestamp("2023-12-31")), (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31")))


MONTHS = ("2022-01", "2025-12")
MHALVES = (("2022-01", "2023-12"), ("2024-01", "2025-12"))


def ev_block(D, date_col, run, spread, direction):
    v = D[(D[date_col] >= V0) & (D[date_col] <= V1)]
    o = run(v)
    halves = [run(v[(v[date_col] >= a) & (v[date_col] <= b)], ) for a, b in HALVES]
    return {"n": o["n"], "beta": o["beta"], "t": o["t"], "p_wild": o["p_wild"], "p_ri": o["p_ri"], "p": o["p"],
            "half_signs_ok": all(np.sign(h["beta"]) == direction for h in halves),
            "half_betas": [h["beta"] for h in halves], "net_spread": spread(v)}


def fm_block(D, run, direction):
    v = D[(D["month"] >= MONTHS[0]) & (D["month"] <= MONTHS[1])]
    o = run(v)
    s = o["series"]
    halves = [s[(s["month"] >= a) & (s["month"] <= b)]["slope"].mean() for a, b in MHALVES]
    return {"months": o["months"], "slope": o["slope"], "t": o["t"], "p": o["p"],
            "half_signs_ok": all(np.sign(h) == direction for h in halves), "half_slopes": halves,
            "net_spread": o["ls_net"]}


def main():
    global V0, V1, HALVES, MONTHS, MHALVES, LOCK
    dry = "--dry-fit" in sys.argv
    if dry:                                              # code check on the fit sample: no lock, small B
        V0, V1 = pd.Timestamp("2012-01-01"), pd.Timestamp("2021-12-31")
        HALVES = ((V0, pd.Timestamp("2016-12-31")), (pd.Timestamp("2017-01-01"), V1))
        MONTHS, MHALVES = ("2012-01", "2021-11"), (("2012-01", "2016-12"), ("2017-01", "2021-11"))
        I_event = I.event_test
        I.event_test = lambda *a, **k: I_event(*a, **{**k, "B": 199})
        LOCK = os.path.join(PX.OUT, "DRY_FIT.lock")
        if os.path.exists(LOCK):
            os.remove(LOCK)
    else:
        assert "--read-validation" in sys.argv, "the validation read needs --read-validation"
        assert not os.path.exists(LOCK), f"the validation read has already been made ({open(LOCK).read().strip()})"
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=PX.ROOT).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "research/p8"], capture_output=True, text=True, cwd=PX.ROOT).stdout.strip()
    assert dry or not dirty, "commit research/p8 before the read"
    open(LOCK, "w").write(f"{datetime.now(timezone.utc).isoformat()} commit {commit}{' DRY-FIT' if dry else ''}\n")

    res = {u: {} for u in ("sp500", "sp400")}
    d1 = pd.read_parquet(H1.ROWS)
    d3a = pd.read_parquet(H3A.ROWS)
    d3b = pd.read_parquet(H3B.ROWS)
    d4 = pd.read_parquet(H4.ROWS)
    h4 = ev_block(d4, "day", H4.stat, H4.spread, +1)
    for u in res:
        res[u]["H1"] = ev_block(d1[d1["universe"] == u], "t0", H1.stat, H1.spread, -1)
        res[u]["H3a"] = fm_block(d3a[d3a["universe"] == u].drop_duplicates(["month", "ticker", "chain", "link"]), H3A.stat, +1)
        res[u]["H3b"] = ev_block(d3b[d3b["universe"] == u], "t0", H3B.stat, H3B.spread, +1)
        res[u]["H4"] = h4
    for name, mod in (("H5", "h5"), ("H2", "h2")):
        p = os.path.join(PX.CACHE, f"{mod}_rows.parquet")
        if not os.path.exists(p):
            for u in res:
                res[u][name] = {"p": 1.0, "not_run": "rows not built (gates or data)"}
            continue
        m = __import__(mod)
        D = pd.read_parquet(p)
        for u in res:
            if name == "H2" and u == "sp500":
                res[u][name] = {"p": 1.0, "not_run": "registered arm is S&P 400 suppliers"}
            else:
                res[u][name] = fm_block(D[D["universe"] == u], m.stat, +1)
    for u in res:
        res[u]["H2b"] = {"p": 1.0, "not_run": "TNIC not joinable (Amendment 5 A1)"}
        names = ["H1", "H2", "H2b", "H3a", "H3b", "H4", "H5"]
        adj, ok = I.holm([res[u][k]["p"] for k in names])
        for k, a, o in zip(names, adj, ok):
            r = res[u][k]
            r["p_holm"] = float(a)
            r["pass"] = bool(o and r.get("half_signs_ok", False) and r.get("net_spread", -1) > 0)
    stem = "DRY_FIT" if dry else "VALIDATION_READ"
    json.dump(res, open(os.path.join(PX.OUT, f"{stem}.json"), "w"), indent=1, default=float)
    title = "dry run on the FIT sample (code check, B = 199)" if dry else "the validation read (2022-2025), made once"
    L = [f"# P8 family H: {title}", "", f"Lock: {open(LOCK).read().strip()}", ""]
    for u in res:
        L += [f"## {u}", "", "| test | statistic | t | p | Holm p | halves | net spread | pass |", "|---|---|---|---|---|---|---|---|"]
        for k in ["H1", "H2", "H2b", "H3a", "H3b", "H4", "H5"]:
            r = res[u][k]
            if "not_run" in r:
                L.append(f"| {k} | not run: {r['not_run']} | | 1 | {r['p_holm']:.3f} | | | no |")
                continue
            st = f"beta {r['beta']:+.4f}" if "beta" in r else f"slope {r['slope'] * 1e4:+.1f} bp/sd"
            L.append(f"| {k} | {st} | {r['t']:+.2f} | {r['p']:.4f} | {r['p_holm']:.3f} | "
                     f"{'ok' if r['half_signs_ok'] else 'no'} | {r['net_spread'] * 1e4:+.1f} bp | {'PASS' if r['pass'] else 'no'} |")
        L.append("")
    open(os.path.join(PX.OUT, f"{stem}.md"), "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
