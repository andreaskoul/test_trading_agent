"""N4 data audit (CLAUDE.md rules 1-4): coverage vs expected, and the availability check (does having news predict y5?).

    python research/tree/N4_news/audit.py   -> research/tree/N4_news/AUDIT.json
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib  # noqa: E402
from lib import harness  # noqa: E402

YEARS = (2015, 2016, 2017, 2018, 2019)


def ic_t(pred, D, rows, mask=None):
    p = pred.astype(np.float64).copy()
    if mask is not None:
        p[~mask] = np.nan
    ic = harness.weekly_ic(p, D, rows)
    ic = ic[np.isfinite(ic)]
    return {"ic": float(ic.mean()), "t_nw4": float(lib.nw_t(ic)), "weeks": int(len(ic))}


def main():
    D = harness.load()
    X = lib.news()
    S, elig = D["S"], D["elig"]
    cnt = X["daily_cnt"]
    out = {"note": "development data only (headlines <= 2019-12-31)"}
    # headlines per name-year, over names eligible at any session of the year
    py = {}
    for y in YEARS:
        r = np.where(S.year == y)[0]
        el = elig[r].any(0)
        c = cnt[r].sum(0)[el]
        priced = np.isfinite(D["y5"][r]).any(0)[el]
        py[y] = {"eligible_names": int(el.sum()), "headlines_mean": float(c.mean()), "headlines_median": float(np.median(c)),
                 "names_zero": int((c == 0).sum()), "names_zero_priced": int(((c == 0) & priced).sum()),
                 "names_zero_unpriced": int(((c == 0) & ~priced).sum()),
                 "median_priced": float(np.median(c[priced])) if priced.any() else None,
                 "median_unpriced": float(np.median(c[~priced])) if (~priced).any() else None,
                 "unpriced_names": int((~priced).sum())}
    out["per_name_year"] = py
    # share of eligible name-weeks (Thursdays) with any headline in the prior 5 / 21 sessions
    h5, h21 = X["raw_has5"], X["raw_has21"]
    sh = {}
    for y in YEARS:
        r = harness.thursdays(D, y)
        e = elig[r]
        yv = e & np.isfinite(D["y5"][r])
        mv = e & np.isfinite(D["master_h5_ref"][r])
        sh[y] = {"has5_all_eligible": float(np.nanmean(np.where(e, h5[r], np.nan))),
                 "has21_all_eligible": float(np.nanmean(np.where(e, h21[r], np.nan))),
                 "has21_with_target": float(np.nanmean(np.where(yv, h21[r], np.nan))),
                 "has21_without_target": float(np.nanmean(np.where(e & ~np.isfinite(D["y5"][r]), h21[r], np.nan))),
                 "has21_master_names": float(np.nanmean(np.where(mv, h21[r], np.nan)))}
    out["share_name_weeks_with_news"] = sh
    # names that left the index during 2015-2019 vs names still eligible at the end
    r = np.where(S.year >= 2015)[0]
    ever = elig[r].any(0)
    end = elig[-1]
    eyrs = elig[r].sum(0) / 252
    rate = cnt[r].sum(0) / np.maximum(eyrs, 1e-9)
    out["left_vs_stayed"] = {
        "stayed_names": int((ever & end).sum()), "left_names": int((ever & ~end).sum()),
        "headlines_per_eligible_year_median_stayed": float(np.median(rate[ever & end])),
        "headlines_per_eligible_year_median_left": float(np.median(rate[ever & ~end])),
        "zero_archive_stayed": int((ever & end & (cnt[r].sum(0) == 0)).sum()),
        "zero_archive_left": int((ever & ~end & (cnt[r].sum(0) == 0)).sum())}
    # availability check (as Q7 for GICS): IC of pure coverage indicators with y5, 2016-2019 Thursdays
    rows = np.concatenate([harness.thursdays(D, y) for y in lib.YEARS])
    arch = np.broadcast_to((cnt[np.where(S.year >= 2015)[0]].sum(0) > 0)[None, :], cnt.shape).astype(float)
    mN = np.isfinite(D["master_h5_ref"])
    av = {"has21_all": ic_t(h21, D, rows), "has5_all": ic_t(h5, D, rows), "has21_master_names": ic_t(h21, D, rows, mN),
          "has_any_2015_2019_all (uses within-dev future)": ic_t(arch, D, rows),
          "has21_by_year": {int(y): ic_t(h21, D, harness.thursdays(D, y))["ic"] for y in lib.YEARS}}
    # coverage by liquidity tercile
    terc = lib.size_tercile(D)
    av["has21_share_by_dollar_volume_tercile"] = {int(k): float(np.nanmean(np.where(elig[rows] & (terc[rows] == k), h21[rows], np.nan)))
                                                   for k in (0, 1, 2)}
    out["availability"] = av
    # content check (rule 11): sample headlines and their features
    json.dump(out, open(os.path.join(HERE, "AUDIT.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
