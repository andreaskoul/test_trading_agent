"""R3 report (P6-P8 of STATE.json): fidelity, paired IC, MASTER decile book and whole fund, repaired-name contribution,
delisting events. Every number: reused 2020-2025 window; survivorship bound. Imported by r3.py report."""
import json
import os
import sys

import numpy as np
import pandas as pd

import r3

TREE, ROOT, CACHE = r3.TREE, r3.ROOT, r3.CACHE
sys.path.insert(0, TREE)
from holdout2 import load_module  # noqa: E402

L4 = load_module(os.path.join(TREE, "L4_exploit", "run.py"), "l4run_r3")
K = L4.K
import features as F  # noqa: E402  (quant-tf, read-only)


def seed_avg(arm, d):
    S = d["S"]
    out = np.full((len(S), len(d["names"])), np.nan)
    per_seed = {s: np.full(out.shape, np.nan) for s in r3.SEEDS}
    info = {}
    for y in r3.YEARS:
        runs = []
        for s in r3.SEEDS:
            z = np.load(r3.pred_path(f"{arm}_y{y}_s{s}"))
            rows = z["rows"]
            sc = z["scores"].astype(np.float64)
            per_seed[s][rows] = sc
            runs.append(sc)
            info[f"{y}_s{s}"] = json.loads(str(z["info"]))
        with np.errstate(all="ignore"):
            out[rows] = np.nanmean(runs, 0)
    return out, per_seed, info


def ic_rows(d):
    S = d["S"]
    return {y: (lambda r: r[r < len(S) - 7])(np.where((S.weekday == 3) & (S.year == y))[0]) for y in r3.YEARS}


def ic_block(pred, d, mask=None):
    """harness.weekly_ic (Spearman vs y5 on eligible names, >= 50 names), Thursdays 2020-2025, NW t 4 lags."""
    import harness as H
    p = pred if mask is None else np.where(mask, pred, np.nan)
    rows = ic_rows(d)
    by = {y: H.weekly_ic(p, d, rows[y]) for y in r3.YEARS}
    allw = np.concatenate([by[y] for y in r3.YEARS])
    return allw, {"ic": float(np.nanmean(allw)), "nw_t": float(F.nw_t(allw, 4)), "weeks": int(np.isfinite(allw).sum()),
                  "by_year": {y: round(float(np.nanmean(v)), 4) for y, v in by.items()}}


# ------------------------------------------------------------------------------------------------ delisting
def delist_events(d, classes):
    S, v, el = d["S"], d["valid"], d["elig"]
    ev = {}
    for i, n in enumerate(d["names"]):
        if not el[:, i].any():
            continue
        le = int(np.where(el[:, i])[0].max())
        vv = np.where(v[: le + 11, i])[0]
        if not len(vv):
            continue
        L = int(vv.max())
        if L >= len(S) - 1 or L > le:
            continue
        cls = classes.get(n, "unexplained")
        ev[i] = {"name": n, "L": L, "last_bar": str(S[L].date()), "last_eligible": str(S[le].date()), "class": cls}
    return ev


def dl_return(cls, unexplained):
    return {"fdic": -1.0, "takeover": 0.0, "rename": 0.0}.get(cls, unexplained)


# ------------------------------------------------------------------------------------------------ simulator
def sim(d, pred, rf, events=None, unexplained=-0.30, track=None):
    """L4_exploit sim (B0: book_decile, mult 1) copied, plus delisting returns and per-week weights on `track`."""
    S, spy = d["S"], pd.Series(d["spy"])
    ma = spy.rolling(K.ST.TREND, min_periods=K.ST.TREND).mean().values
    rows, prev, prev_spy, prev_s = [], None, 0.0, None
    held = []
    th = np.where(S.weekday == 3)[0]
    for t, R, Rm, days in K.ST.periods(d, range(2020, 2026)):
        ok = np.isfinite(pred[t]) & d["elig"][t]
        w = K.deciles(pred[t], ok)
        R = np.nan_to_num(R).copy()
        if events:
            t2 = int(th[np.searchsorted(th, t) + 1])
            for i, e in events.items():
                if t + 1 <= e["L"] <= t2:
                    dl = dl_return(e["class"], unexplained)
                    if w[i] != 0:
                        held.append({"date": str(S[t].date()), "name": e["name"], "class": e["class"], "w": float(w[i]),
                                     "R_before": float(R[i]), "dl": dl})
                    R[i] = (1 + R[i]) * (1 + dl) - 1
        s = K.ST.UP if np.isfinite(ma[t]) and d["spy"][t] > ma[t] else K.ST.DOWN
        beta = np.nan_to_num(d["beta"][t], nan=1.0)
        w_spy = -float((w * beta).sum())
        dw = np.abs(w - (prev if prev is not None else 0)).sum() + abs(w_spy - prev_spy)
        book = float((w * R).sum() + w_spy * Rm) - L4.COST * dw
        mrate = (float(rf.asof(S[t] - pd.Timedelta(days=1))) + K.ST.MARGIN_SPREAD) * days / 360
        sw = abs(s - (prev_s if prev_s is not None else s))
        sleeve = s * Rm - L4.COST * sw
        total = sleeve + book - max(s + float(w.sum()) + w_spy - 1, 0) * mrate
        row = {"date": S[t], "year": S[t].year, "days": days, "book": book, "total": total, "spy": Rm, "turnover": dw,
               "book_cost": L4.COST * dw, "core_cost": L4.COST * sw, "k": 1.0, "gross": L4.gross_of(s, w, w_spy), "s": s}
        if track is not None:
            m = np.zeros(len(w), bool)
            m[track] = True
            hw = m & (w != 0)
            row.update({"rep_names_held": int(hw.sum()), "rep_long": int((hw & (w > 0)).sum()),
                        "rep_short": int((hw & (w < 0)).sum()), "rep_gross": float(np.abs(w[m]).sum()),
                        "book_gross": float(np.abs(w).sum()), "rep_contrib": float((w[m] * R[m]).sum()),
                        "rep_held_idx": ",".join(str(i) for i in np.where(hw)[0])})
        rows.append(row)
        prev, prev_spy, prev_s = w, w_spy, s
    return pd.DataFrame(rows).set_index("date"), held


def ann(x_wk):
    return 100 * 52 * float(np.mean(x_wk))


def paired(a, b):
    x = L4.wk(a) - L4.wk(b)
    m, t, n = L4.nw(x)
    return {"diff_pct_per_year_arith": 100 * 52 * m, "nw_t": t, "weeks": n}


def paired_book(a, b):
    x = (a.book * 7 / a.days).to_numpy() - (b.book * 7 / b.days).to_numpy()
    m, t, n = L4.nw(x)
    return {"diff_pct_per_year_arith": 100 * 52 * m, "nw_t": t, "weeks": n}


def book_by_year(df):
    return {int(y): round(100 * 52 * float((g.book * 7 / g.days).mean()), 2) for y, g in df.groupby("year")}


def main():
    st = json.load(open(r3.STATE))
    dO, dR = r3.load("ORIG"), r3.load("REPAIRED")
    assert (dO["S"] == dR["S"]).all() and dO["names"] == dR["names"]
    S, names = dO["S"], dO["names"]
    filled = json.load(open(os.path.join(CACHE, "filled_names.json")))["filled"]
    rep = np.array([names.index(n) for n in filled], int)
    repmask = np.zeros(len(names), bool)
    repmask[rep] = True
    pO, psO, infO = seed_avg("ORIG", dO)
    pR, psR, infR = seed_avg("REPAIRED", dR)
    res = {"label": r3.LABEL}
    # P6 fidelity vs the saved as-run read
    z = np.load(os.path.join(L4.QTC, "sp500_tf_master_h5.npz"))
    saved = z["h5"].astype(np.float64)
    assert saved.shape == pO.shape
    th = np.where((S.weekday == 3) & (S.year >= 2020))[0]
    rc = np.array([pd.Series(pO[t]).corr(pd.Series(saved[t]), method="spearman") for t in th])
    icS, sS = ic_block(saved, dO)
    icO, sO = ic_block(pO, dO)
    ok = np.isfinite(icS) & np.isfinite(icO)
    res["P6_fidelity_orig_retrain_vs_saved_h5"] = {
        "label": r3.LABEL, "weekly_score_spearman": {"mean": float(np.nanmean(rc)), "min": float(np.nanmin(rc)), "max": float(np.nanmax(rc))},
        "ic_saved": sS, "ic_orig_retrain": sO, "ic_diff_retrain_minus_saved": sO["ic"] - sS["ic"],
        "corr_of_weekly_ics": float(np.corrcoef(icS[ok], icO[ok])[0, 1]), "paired_ic_diff_nw_t": float(F.nw_t(icO - icS, 4))}
    # P7 IC
    icR, sR = ic_block(pR, dR)
    icRu, sRu = ic_block(pR, dR, mask=~repmask[None, :])
    seeds = {}
    for s in r3.SEEDS:
        seeds[s] = {"ORIG": ic_block(psO[s], dO)[1]["ic"], "REPAIRED": ic_block(psR[s], dR)[1]["ic"]}
        seeds[s]["diff"] = seeds[s]["REPAIRED"] - seeds[s]["ORIG"]
    dif = icR - icO
    res["P7_ic"] = {"label": r3.LABEL, "ORIG": sO, "REPAIRED": sR, "REPAIRED_on_unrepaired_names_only": sRu,
                    "paired_weekly_diff_REPAIRED_minus_ORIG": {"mean": float(np.nanmean(dif)), "nw_t": float(F.nw_t(dif, 4))},
                    "paired_weekly_diff_REPAIRED_unrepaired_minus_ORIG": {"mean": float(np.nanmean(icRu - icO)), "nw_t": float(F.nw_t(icRu - icO, 4))},
                    "per_seed_ic": seeds,
                    "seed_spread_ORIG_ic_sd": float(np.std([v["ORIG"] for v in seeds.values()], ddof=1)),
                    "seed_spread_REPAIRED_ic_sd": float(np.std([v["REPAIRED"] for v in seeds.values()], ddof=1)),
                    "names_scored_per_thursday_mean": {"ORIG": float(np.isfinite(pO[th]).sum(1).mean()), "REPAIRED": float(np.isfinite(pR[th]).sum(1).mean())}}
    # P8 delisting events
    cl = st["plan"]["P8_delisting_v2"]
    classes = {**{n: "fdic" for n in cl["FDIC_minus_100"]}, **{n: "takeover" for n in cl["takeover_or_merger_0"]},
               **{n: "rename" for n in cl["rename_or_successor_listing_0"]}}
    evO, evR = delist_events(dO, classes), delist_events(dR, classes)
    res["P8_delisting_events_in_panel"] = {
        "ORIG": len(evO), "REPAIRED": len(evR),
        "REPAIRED_by_class": pd.Series([e["class"] for e in evR.values()]).value_counts().to_dict(),
        "REPAIRED_events": {e["name"]: [e["last_bar"], e["last_eligible"], e["class"]] for e in evR.values()},
        "declared_names_without_event": sorted(set(classes) - {e["name"] for e in evR.values()})}
    # books
    rf = K.ST.dtb3()
    K.GROSS_SIDE = L4.SIDE0
    ref = L4.sim(dO, saved, L4.book_decile, range(2020, 2026), rf=rf)
    b_saved, _ = sim(dO, saved, rf)
    assert np.allclose(ref.total.values, b_saved.total.values, rtol=0, atol=1e-12)
    s_saved = L4.summary(b_saved)
    rec = json.load(open(os.path.join(TREE, "OOS_RETURNS.json")))["MASTER|gross 0.6|5bp"]
    bO, hO = sim(dO, pO, rf, evO, track=rep)
    bR, hR = sim(dR, pR, rf, evR, -0.30, track=rep)
    bR0, hR0 = sim(dR, pR, rf, evR, 0.0, track=rep)
    bRx, _ = sim(dR, np.where(repmask[None, :], np.nan, pR), rf, evR, -0.30, track=rep)
    out = {"label": r3.LABEL,
           "sim_check_saved_h5_on_ORIG": {"pct_per_year": s_saved["pct_per_year"], "sharpe": s_saved["sharpe"],
                                         "recorded": [rec["pct_per_year"], rec["sharpe"]], "identical_to_L4_sim": True}}
    for k, df in (("ORIG", bO), ("REPAIRED", bR), ("REPAIRED_unexplained_0pct", bR0), ("REPAIRED_book_without_repaired_names", bRx)):
        s = L4.summary(df)
        out[k] = {"whole_fund": {kk: s[kk] for kk in ("pct_per_year", "sharpe", "vol_pct", "worst_fall_pct", "by_year_pct", "by_year_sharpe", "mean_gross")},
                  "book": {"pct_per_year_arith": s["book_pct_per_year_arith"], "sharpe": s["book_sharpe"],
                           "by_year_pct_arith": book_by_year(df), "turnover_x_per_year": s["book_turnover_x_per_year"],
                           "cost_pct_per_year": s["book_cost_pct_per_year"]}}
    out["paired_REPAIRED_minus_ORIG"] = {"whole_fund": paired(bR, bO), "book": paired_book(bR, bO),
                                         "sharpe_diff_whole_fund": out["REPAIRED"]["whole_fund"]["sharpe"] - out["ORIG"]["whole_fund"]["sharpe"],
                                         "sharpe_diff_book": out["REPAIRED"]["book"]["sharpe"] - out["ORIG"]["book"]["sharpe"],
                                         "lw2008_hac_whole_fund": L4.lw_hac_test(L4.wk(bR), L4.wk(bO))}
    out["paired_ORIG_retrain_minus_saved"] = {"whole_fund": paired(bO, b_saved), "book": paired_book(bO, b_saved),
                                              "saved_whole_fund": {"pct_per_year": s_saved["pct_per_year"], "sharpe": s_saved["sharpe"]},
                                              "saved_book": {"pct_per_year_arith": s_saved["book_pct_per_year_arith"], "sharpe": s_saved["book_sharpe"]}}
    # repaired names in the REPAIRED book
    yrs = bR.days.sum() / 365.25
    idx = sorted({int(i) for x in bR.rep_held_idx if x for i in x.split(",")})
    contrib_wk = (bR.rep_contrib * 7 / bR.days).to_numpy()
    out["repaired_names_in_REPAIRED_book"] = {
        "label": r3.LABEL, "distinct_names_held": len(idx), "names": [names[i] for i in idx],
        "name_weeks_held": int(bR.rep_names_held.sum()), "long_name_weeks": int(bR.rep_long.sum()), "short_name_weeks": int(bR.rep_short.sum()),
        "weeks_with_any": int((bR.rep_names_held > 0).sum()), "weeks": int(len(bR)),
        "share_of_book_gross_mean": float((bR.rep_gross / bR.book_gross.replace(0, np.nan)).mean()),
        "contribution_pct_per_year_arith": ann(contrib_wk), "contribution_nw_t": L4.nw(contrib_wk)[1],
        "contribution_by_year_pct": {int(y): round(100 * 52 * float((g.rep_contrib * 7 / g.days).mean()), 3) for y, g in bR.groupby("year")},
        "years": float(yrs)}
    out["delisting_events_held_by_book"] = {
        "REPAIRED_default": {"n": len(hR), "by_class": pd.Series([h["class"] for h in hR]).value_counts().to_dict() if hR else {},
                             "events": hR, "return_effect_pct_of_book_total": 100 * float(sum(h["w"] * ((1 + h["R_before"]) * (1 + h["dl"]) - 1 - h["R_before"]) for h in hR))},
        "REPAIRED_unexplained_0pct": {"n": len(hR0)}, "ORIG": {"n": len(hO)}}
    res["P7_book_and_fund"] = out
    # MPS hours
    fits = st.get("fits", {})
    res["compute"] = {"fits": len(fits), "mps_wall_hours_sum_over_fits": sum(v.get("session_sec", 0) for v in fits.values()) / 3600,
                      "train_hours_sum": sum(v.get("train_sec", 0) for v in fits.values()) / 3600,
                      "epochs": {"ORIG_mean": float(np.mean([v["epochs"] for k, v in fits.items() if k.startswith("ORIG")])),
                                 "REPAIRED_mean": float(np.mean([v["epochs"] for k, v in fits.items() if k.startswith("REPAIRED")]))}}
    pd.DataFrame({"ORIG": L4.wk(bO), "REPAIRED": L4.wk(bR), "saved": L4.wk(b_saved),
                  "ORIG_book": (bO.book * 7 / bO.days).to_numpy(), "REPAIRED_book": (bR.book * 7 / bR.days).to_numpy()},
                 index=bO.index).to_parquet(os.path.join(CACHE, "weekly_2020_2025.parquet"))
    json.dump(res, open(os.path.join(r3.HERE, "RESULT.json"), "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float)[:6000])
