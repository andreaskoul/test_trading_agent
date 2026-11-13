"""Layer 3 registered read L3.1 (PREREG Layer 3, Amendments 1 and 2). Coordinating session only.

    python research/tree/read3.py panel    # build the broad panel once, save it, print coverage (no prediction is scored)
    python research/tree/read3.py L3a      # IPCA (M2) + its control (C ridge), one process
    python research/tree/read3.py L3b      # D trees on 4 horizons + its control (D trees, 5-session target)
    python research/tree/read3.py holm     # after both: Holm across L3a and L3b at alpha 0.05

Each candidate is read once: READ3.lock holds {candidate: start time}; a candidate already in it is refused.
Window 2017-2025; models fitted on S&P 500 panel + broad rows whose target ended before each year; weekly rank IC
scored on the broad names only. Results append to READ3_RESULT.json.
"""
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from holdout2 import band_book, load_module, nw, rows_for  # noqa: E402

PANEL = os.path.join(ROOT, ".cache", "tree", "broad", "panel.npz")
OUT = os.path.join(HERE, "READ3_RESULT.json")
LOCK = os.path.join(HERE, "READ3.lock")
YEARS = tuple(range(2017, 2026))
SEEDS = (0, 1, 2)
CAND = {"L3a": ("M2_ipca/model.py", "C_features/model.py"),
        "L3b": ("finalists/D_hgb_mh/model.py", "D_ensembles/model.py")}


def panel():
    import pandas as pd
    import panel_broad as PB
    D, isb = PB.build()
    arrs = {k: v for k, v in D.items() if isinstance(v, np.ndarray)}
    np.savez(PANEL, S=np.asarray(D["S"].values), names=np.array(D["names"]), isb=isb, **arrs)
    S = D["S"]
    th = np.where((S.weekday == 3) & (S.year >= 2017))[0]
    nb = D["elig"][th][:, isb].sum(1)
    ny = np.isfinite(D["y5"][th][:, isb]).sum(1)
    meta = json.load(open(os.path.join(PB.BROAD, "symbols.json")))
    status = {s["symbol"]: s["status"] for s in meta["symbols"]}
    namesb = [n for n, f in zip(D["names"], isb) if f]
    ever = D["elig"][th][:, isb].any(0)
    last = pd.DataFrame(D["valid"][:, isb], index=S).apply(lambda c: S[c.values].max() if c.any() else pd.NaT)
    res = {"broad_names_ever_eligible_2017_2025": int(ever.sum()),
           "eligible_per_Thursday": {"mean": float(nb.mean()), "min": int(nb.min()), "max": int(nb.max())},
           "with_y5_per_Thursday_mean": float(ny.mean()),
           "share_inactive_at_alpaca": float(np.mean([status.get(n) == "inactive" for n, e in zip(namesb, ever) if e])),
           "share_last_bar_before_2025_12": float((last[ever] < pd.Timestamp("2025-12-01")).mean()),
           "sp500_names": int((~isb).sum()), "sessions": [str(S[0].date()), str(S[-1].date())],
           "symbols_meta": meta["meta"], "built": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    json.dump(res, open(os.path.join(HERE, "READ3_PANEL.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


def load_panel():
    import pandas as pd
    z = np.load(PANEL, allow_pickle=False)
    D = {k: z[k] for k in z.files if k not in ("S", "names", "isb")}
    D["S"] = pd.DatetimeIndex(z["S"])
    D["names"] = list(z["names"])
    return D, z["isb"]


def ic_series(pred, Ds, rows):
    return H.weekly_ic(pred, Ds, rows)


def read(cand):
    D, isb = load_panel()
    Ds = dict(D)
    Ds["elig"] = D["elig"] & isb[None, :]
    rows = rows_for(D, YEARS)
    res = {"panel": "S&P 500 panel + broad survivorship-free universe; scored on broad names, 2017-2025", "seeds": list(SEEDS)}
    preds = {}
    for role, rel in zip(("candidate", "control"), CAND[cand]):
        model = load_module(os.path.join(HERE, rel), f"{cand}_{role}")
        p = H.walk_forward(model.fit_predict, seeds=SEEDS, years=YEARS, D=D)
        np.save(os.path.join(ROOT, ".cache", "tree", f"read3_pred_{cand}_{role}.npy"), p.astype(np.float32))
        preds[role] = p
        ic = ic_series(p, Ds, rows)
        mean, t, n = nw(ic)
        r = {"model": rel, "weeks": n, "ic": mean, "t": t, "p_one_sided": float(0.5 * math.erfc(t / math.sqrt(2))),
             "ic_by_year": {y: float(np.nanmean(ic_series(p, Ds, rows_for(D, (y,))))) for y in YEARS},
             "names_per_week": float(np.mean([np.isfinite(p[t_][Ds["elig"][t_]]).sum() for t_ in rows]))}
        try:
            Db = dict(Ds)
            Db["y5"] = np.clip(Ds["y5"], -1.0, 1.0)          # Amendment 5: books only; the IC test uses y5 unchanged
            r["books_reported"] = band_book(np.where(Ds["elig"], p, np.nan), Db, rows)
        except Exception as exc:                                                       # reported only
            r["books_reported"] = {"error": repr(exc)[:200]}
        res[role] = r
        print(role, json.dumps({k: r[k] for k in ("ic", "t", "weeks")}), flush=True)
    res["reported_amendment4"] = extras(preds, Ds, rows)
    a, b = ic_series(preds["candidate"], Ds, rows), ic_series(preds["control"], Ds, rows)
    m = np.isfinite(a) & np.isfinite(b)
    res["paired_vs_control_reported"] = dict(zip(("diff", "t", "weeks"), nw(a[m] - b[m])))
    res["p_one_sided"] = res["candidate"]["p_one_sided"]
    return res


def extras(preds, Ds, rows):
    """Reported only (PREREG Layer 3, Amendment 4): IC with delisting returns kept; IC by dollar-volume tercile."""
    out = {}
    Dd = dict(Ds)
    Dd["y5"] = Ds["y5_delist"]
    for role, p in preds.items():
        o = {"ic_delist_kept": nw(ic_series(p, Dd, rows))[:2]}
        for k, (lo, hi) in enumerate(((0, 1 / 3), (1 / 3, 2 / 3), (2 / 3, 1.0001))):
            Dt = dict(Ds)
            q = np.full(Ds["elig"].shape, False)
            for t in rows:
                e = Ds["elig"][t] & np.isfinite(Ds["dv"][t])
                if e.sum():
                    pr = pd_rank(Ds["dv"][t][e])
                    q[t, np.where(e)[0][(pr >= lo) & (pr < hi)]] = True
            Dt["elig"] = q
            o[f"ic_dv_tercile_{k + 1}"] = nw(ic_series(p, Dt, rows))[:2]
        out[role] = o
    return out


def pd_rank(x):
    import pandas as pd
    return pd.Series(x).rank(pct=True).to_numpy()


def save(key, res):
    allr = json.load(open(OUT)) if os.path.exists(OUT) else {}
    allr[key] = res
    json.dump(allr, open(OUT, "w"), indent=1)
    print(json.dumps(res, indent=1))


def holm():
    allr = json.load(open(OUT))
    p = {k: allr[k]["p_one_sided"] for k in CAND}
    ok, out = True, {}
    for i, k in enumerate(sorted(p, key=p.get)):
        ok = ok and p[k] <= 0.05 / (len(p) - i)
        out[k] = bool(ok)
    return {"p": p, "holm_pass": out}


def main():
    what = sys.argv[1]
    if what == "panel":
        panel()
    elif what in CAND:
        lock = json.load(open(LOCK)) if os.path.exists(LOCK) else {}
        if what in lock:
            sys.exit(f"{what} was already read: {lock[what]}")
        lock[what] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        json.dump(lock, open(LOCK, "w"))
        res = read(what)
        res["run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save(what, res)
    elif what == "holm":
        save("holm", holm())


if __name__ == "__main__":
    main()
