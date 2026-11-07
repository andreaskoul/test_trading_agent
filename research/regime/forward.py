"""Forward paper books for the momentum panic switch (research/regime/PREREG.md Amendment 6; never traded).

    cd research/quant_trials && PYTHONPATH=. python ../regime/forward.py weekly [--asof YYYY-MM-DD] [--dry]
    cd research/quant_trials && PYTHONPATH=. python ../regime/forward.py ledger [--dry]

Runs after the forward S&P books (spx_forward.py) in the same job and reuses their price panel, calendar, holding
periods and book arithmetic. Records: one JSON per Thursday in $REGIME_REC, append-only; realised weeks frozen at
first computation in ledger.json; page.json for the website.
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

import spx_forward as FW
import spx_live as L
import strategies as ST

HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.environ.get("REGIME_REC", os.path.expanduser("~/.fund-runner/research/regime"))
DRY = os.path.join(FW.P.CACHE, "regime_forward_dry")
BOOKS = ("mom", "mom_panic", "ens", "ens_panic")
HIST = 156                                    # weekly decisions in the volatility percentile's history


def panic_at(d, t):
    """PANIC at session t (a Thursday): SPY's 252-session return < 0 and its 21-session realised volatility above
    the median of the same measure at the last 156 Thursday sessions before t (expanding from 26)."""
    lr = np.log1p(np.nan_to_num(d["rm"]))
    S = d["S"]
    vol = lambda k: float(np.std(lr[k - 20:k + 1]))
    thu = [k for k in range(252, t) if S[k].weekday() == 3][-HIST:]
    hist = np.array([vol(k) for k in thu])
    v = vol(t)
    pct = float((hist < v).mean()) if len(hist) >= 26 else None
    ret252 = float(d["spy"][t] / d["spy"][t - 252] - 1)
    panic = int(ret252 < 0 and pct is not None and pct > 0.5)
    return {"spy": float(d["spy"][t]), "ret252": ret252, "vol21_ann": v * np.sqrt(252), "vol_pct": pct,
            "hist_weeks": len(hist), "panic": panic}


def mom_scores(d, t):
    """12-1 month momentum (log return from session t-252 to t-20) of names eligible at t with 252 finite returns."""
    r = d["r"][t - 251:t + 1]
    ok = d["elig"][t] & np.isfinite(r).all(0) & np.isfinite(d["e"][max(0, t - 59):t + 1]).all(0)
    lr = np.log1p(np.where(np.isfinite(r), r, 0.0))
    m = lr[:-20].sum(0)
    return np.where(ok, m, np.nan)


def decile_book(score, beta):
    m = np.isfinite(score)
    w = np.zeros(score.shape)
    q = np.nanquantile(score[m], [0.1, 0.9])
    Lg, Sh = m & (score >= q[1]), m & (score <= q[0])
    w[Lg], w[Sh] = 0.5 / Lg.sum(), -0.5 / Sh.sum()
    return w, -float((w * np.nan_to_num(beta, nan=1.0)).sum())


def weekly(asof=None, dry=False):
    out = DRY if dry else REC
    if asof is None:
        exp = FW.expected_thursday()
        if exp is None or os.path.exists(os.path.join(out, f"regime_{exp.date()}.json")):
            print("nothing to record (already recorded, or a holiday week)")
            return None
        asof = str(exp.date())
    d = L.build()
    S, names = d["S"], list(d["names"])
    if pd.Timestamp(asof) not in S:
        sys.exit(f"prices for {asof} are missing (data to {S[-1].date()}): no record written")
    t = int(np.searchsorted(S, pd.Timestamp(asof)))
    if S[t].weekday() != 3:
        sys.exit(f"{asof}: not a Thursday session")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"regime_{asof}.json")
    if os.path.exists(path):
        sys.exit(f"{path} exists: records are append-only")
    st = panic_at(d, t)
    mom = mom_scores(d, t)
    w, wspy = decile_book(mom, d["beta"][t])
    on = 1 - st["panic"]
    vec = lambda x: {n: float(v) for n, v in zip(names, x) if v != 0}
    books = {"mom": {"weights": vec(w), "w_spy": wspy, "scale": 1.0},
             "mom_panic": {"weights": vec(w * on), "w_spy": wspy * on, "scale": float(on)}}
    problems = []
    spx = os.path.join(FW.DRY if dry else FW.REC, f"spx_{asof}.json")
    loadings = {}
    if os.path.exists(spx):
        R = json.load(open(spx))
        e = R["books"]["fw_ensemble"]
        books["ens"] = {"weights": e["weights"], "w_spy": e["w_spy"], "scale": 1.0}
        books["ens_panic"] = {"weights": {n: x * on for n, x in e["weights"].items() if on}, "w_spy": e["w_spy"] * on,
                              "scale": float(on)}
        ms = pd.Series(mom, index=names)
        for k, v in R["scores"].items():
            s = pd.Series(v)
            j = s.index.intersection(ms.dropna().index)
            loadings[k] = round(float(s[j].rank().corr(ms[j].rank())), 4) if len(j) > 30 else None
    else:
        problems.append(f"no forward S&P record for {asof}: ens books not formed")
    rec = {"asof": asof, "data_end": str(S[-1].date()), "dry": dry,
           "code": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip(),
           "state": st, "eligible": int(np.isfinite(mom).sum()), "mom_loadings": loadings, "books": books,
           "problems": problems}
    json.dump(rec, open(path, "w"), indent=1)
    print(f"written {path}")
    print(json.dumps({k: rec[k] for k in ("asof", "state", "eligible", "mom_loadings", "problems")}, indent=1))
    if problems:                                                        # fail loudly, after saving (CLAUDE.md 9)
        sys.exit("; ".join(problems))
    return path


def ledger(dry=False):
    path = DRY if dry else REC
    recs = [json.load(open(p)) for p in sorted(p for p in (os.path.join(path, f) for f in os.listdir(path))
                                                if os.path.basename(p).startswith("regime_20"))] if os.path.isdir(path) else []
    lp = os.path.join(path, "ledger.json")
    led = json.load(open(lp)) if os.path.exists(lp) else {"pl": []}
    have = {(r["bk"], r["asof"]) for r in led["pl"]}
    d = L.build()
    S = d["S"]
    stamp = str(S[-1].date())
    for a, b in zip(recs[:-1], recs[1:]):
        if FW.period(d, a, b) is None:
            break
        for bk in BOOKS:
            if bk not in a["books"] or bk not in b["books"] or (bk, a["asof"]) in have:
                continue
            book, Rm, days, net, dw = FW.book_return(d, a, b, bk)
            t, t2 = (int(np.searchsorted(S, pd.Timestamp(r["asof"]))) for r in (a, b))
            led["pl"].append({"bk": bk, "asof": a["asof"], "to": b["asof"], "start": str(S[t + 1].date()),
                              "end": str(S[t2 + 1].date()), "book": book, "spy": Rm, "turnover": dw,
                              "panic": a["state"]["panic"], "computed_with_data_to": stamp})
    json.dump(led, open(lp, "w"), indent=1)
    page = {"generated": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "records": len(recs),
            "latest": {k: recs[-1][k] for k in ("asof", "state", "mom_loadings", "eligible")} if recs else None,
            "states": [{"asof": r["asof"], **r["state"]} for r in recs], "books": {}, "evidence": evidence()}
    P = pd.DataFrame(led["pl"])
    for bk in BOOKS:
        rows = P[P.bk == bk].sort_values("asof") if len(P) else P
        r = rows["book"].to_numpy() if len(rows) else np.array([])
        page["books"][bk] = {"weeks": int(len(r)), "cum": float(np.prod(1 + r) - 1) if len(r) else None,
                             "ann": float(np.prod(1 + r) ** (52 / len(r)) - 1) if len(r) >= 26 else None,
                             "weekly": rows[["asof", "start", "end", "book", "panic"]].to_dict("records") if len(rows) else []}
    json.dump(page, open(os.path.join(path, "page.json"), "w"), indent=1, allow_nan=False)
    print(json.dumps({k: page["books"][k]["cum"] for k in BOOKS}, indent=1))
    return page


def evidence():
    """The registered evidence for the switch (OOS_RESULT.json, INT_RESULT.json), for the page."""
    out = {}
    try:
        o = json.load(open(os.path.join(HERE, "OOS_RESULT.json")))["results"]["H16"]
        out["us_2000_2025"] = {k: o[k] for k in ("t_dir", "p_one_sided", "p_holm")} | {"cond_sharpe": o["cond"]["sharpe"], "unc_sharpe": o["unc"]["sharpe"],
                                                                               "cond_net_pct_yr": o["cond"]["net_pct_yr"], "unc_net_pct_yr": o["unc"]["net_pct_yr"]}
        i = json.load(open(os.path.join(HERE, "INT_RESULT.json")))
        r = i["results"]["H16-INT"]
        out["intl_1992_2025"] = {"t_dir": r["t_dir"], "p_one_sided": r["p_one_sided"], "p_holm": r["p_holm"],
                                 "cond_sharpe": r["cond"]["sharpe"], "unc_sharpe": r["unc"]["sharpe"],
                                 "cond_net_pct_yr": r["cond"]["net_pct_yr"], "unc_net_pct_yr": r["unc"]["net_pct_yr"],
                                 "cond_max_dd_pct": r["cond"]["max_dd_pct"], "unc_max_dd_pct": r["unc"]["max_dd_pct"],
                                 "regions": {n: round(-p["H16"]["b_t"][1], 2) for n, p in i["regions"].items()}}
    except (OSError, KeyError) as e:
        out["error"] = repr(e)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["weekly", "ledger"])
    ap.add_argument("--asof")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    weekly(a.asof, a.dry) if a.cmd == "weekly" else ledger(a.dry)
