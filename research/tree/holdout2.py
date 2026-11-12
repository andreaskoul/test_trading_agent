"""Phase-2 holdout reads (PREREG phase 2, Amendment 2). Coordinating session only. One finalist per process, because
some finalists cache fits by training cut-off.

    python research/tree/holdout2.py N1      # S&P 500 2020-2025, increment over MASTER
    python research/tree/holdout2.py M2      # S&P 400 2019-2025, IC
    python research/tree/holdout2.py M4
    python research/tree/holdout2.py holm    # after all three: Holm across them
    python research/tree/holdout2.py X1ref   # reported only: the phase-1 best on the S&P 400 weeks

Each finalist is read once (`READ2_<name>.lock`). Results append to HOLDOUT2_RESULT.json.
"""
import importlib.util
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import harness as H   # noqa: E402

OUT = os.path.join(HERE, "HOLDOUT2_RESULT.json")
FINALISTS = ("N1", "M2", "M4")


def nw(x, lags=4):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n, d = len(x), x - x.mean()
    v = d @ d / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (d[l:] @ d[:-l]) / n
    return float(x.mean()), float(x.mean() / math.sqrt(v / n)), int(n)


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rows_for(D, years):
    rows = np.concatenate([H.thursdays(D, y) for y in years])
    return rows[rows < len(D["S"]) - 7]


def band_book(scores, D, rows):
    """Reported only: decile book net of 5 bp with M1's no-trade band (lib.build 'band', width 0.1) and without."""
    sys.path.insert(0, os.path.join(HERE, "M1_dyntrade"))
    import lib as M1
    rows = np.array([t for t in rows if M1.mask(scores, D, t).sum() >= 50])
    out = {}
    for kind, kw in (("deciles", {}), ("band", {"band": 0.1})):
        W = M1.build(kind, scores, D, rows, **kw)
        net = np.asarray(M1.simulate(W, D, rows)[0], float)
        out[kind] = {"net_pct_per_year": float(52 * net.mean() * 100), "net_sharpe": float(net.mean() / net.std(ddof=1) * math.sqrt(52))}
    return out


def save(key, res):
    allr = json.load(open(OUT)) if os.path.exists(OUT) else {}
    allr[key] = res
    json.dump(allr, open(OUT, "w"), indent=1)
    print(json.dumps(res, indent=1))


def read_N1():
    import holdout as HO
    D = HO.full_panel()
    full = dict(np.load(os.path.join(ROOT, ".cache", "tree", "extra_fundamentals_full.npz"), allow_pickle=False))
    orig = H.load_extra
    H.load_extra = lambda key: full if key == "fundamentals" else orig(key)        # the model's own loaders -> full period
    sys.path.insert(0, os.path.join(HERE, "N1_fundamentals"))
    import lib as N1
    N1._C.clear()
    N1._C["D"] = D
    model = load_module(os.path.join(HERE, "N1_fundamentals", "model.py"), "n1_model")
    years = (2020, 2021, 2022, 2023, 2024, 2025)
    rows = rows_for(D, years)
    pred = H.walk_forward(model.fit_predict, seeds=(0,), years=years, D=D)
    np.save(os.path.join(ROOT, ".cache", "tree", "holdout2_pred_N1.npy"), pred.astype(np.float32))
    base = D["master_h5_ref"].astype(np.float64)
    a, b = H.weekly_ic(pred, D, rows), H.weekly_ic(base, D, rows)
    m = np.isfinite(a) & np.isfinite(b)
    inc, t, n = nw(a[m] - b[m])
    by = {y: float(np.nanmean(H.weekly_ic(pred, D, rows_for(D, (y,))) - H.weekly_ic(base, D, rows_for(D, (y,))))) for y in years}
    res = {"panel": "S&P 500 2020-2025", "weeks": n, "ic": float(a[m].mean()), "master_ic": float(b[m].mean()), "increment": inc, "t": t,
           "p_one_sided": float(0.5 * math.erfc(t / math.sqrt(2))), "increment_by_year": by,
           "decile_net_pct_per_year": float(52 * 100 * H.decile_net(pred, D, rows).mean())}
    # reported only: the registered no-fit fallback
    rb = load_module(os.path.join(HERE, "N1_fundamentals", "run_blend.py"), "n1_blend")
    pf = H.walk_forward(rb.make(0.7), seeds=(0,), years=years, D=D)
    af = H.weekly_ic(pf, D, rows)
    mf = np.isfinite(af) & np.isfinite(b)
    res["fallback_comp_blend70"] = dict(zip(("increment", "t", "weeks"), nw(af[mf] - b[mf])))
    return res


def read_M(name, path):
    import panel400 as P4
    D, is400 = P4.build()
    model = load_module(path, f"{name}_model")
    years = (2019, 2020, 2021, 2022, 2023, 2024, 2025)
    pred = H.walk_forward(model.fit_predict, seeds=(0, 1, 2), years=years, D=D)
    np.save(os.path.join(ROOT, ".cache", "tree", f"holdout2_pred_{name}.npy"), pred.astype(np.float32))
    Ds = dict(D)
    Ds["elig"] = D["elig"] & is400[None, :]                                           # score the S&P 400 names only
    rows = rows_for(D, years)
    ic = H.weekly_ic(pred, Ds, rows)
    mean, t, n = nw(ic)
    by = {y: float(np.nanmean(H.weekly_ic(pred, Ds, rows_for(D, (y,))))) for y in years}
    res = {"panel": "S&P 400 2019-2025 (current members; model fitted on S&P 500 + S&P 400 rows before each year)", "weeks": n,
           "ic": mean, "t": t, "p_one_sided": float(0.5 * math.erfc(t / math.sqrt(2))), "ic_by_year": by,
           "names_per_week": float(np.mean([np.isfinite(pred[r][Ds["elig"][r]]).sum() for r in rows]))}
    try:
        res["books_reported"] = band_book(np.where(Ds["elig"], pred, np.nan), Ds, rows)
    except Exception as exc:                                                         # reported only; never blocks the read
        res["books_reported"] = {"error": repr(exc)[:200]}
    return res


def holm():
    allr = json.load(open(OUT))
    p = {k: allr[k]["p_one_sided"] for k in FINALISTS}
    ok, out = True, {}
    for i, k in enumerate(sorted(p, key=p.get)):
        ok = ok and p[k] <= 0.05 / (len(p) - i)
        out[k] = bool(ok)
    return {"p": p, "holm_pass": out}


def main():
    what = sys.argv[1]
    if what in FINALISTS:
        lock = os.path.join(HERE, f"READ2_{what}.lock")
        if os.path.exists(lock):
            sys.exit(f"{what} was already read: " + open(lock).read())
        open(lock, "w").write(datetime.now(timezone.utc).isoformat(timespec="seconds"))
        res = read_N1() if what == "N1" else read_M(what, os.path.join(HERE, {"M2": "M2_ipca", "M4": "M4_sdf"}[what], "model.py"))
        res["run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save(what, res)
    elif what == "holm":
        save("holm", holm())
    elif what == "X1ref":
        save("X1ref_reported", read_M("X1ref", os.path.join(HERE, "finalists", "X1_8p", "model.py")))


if __name__ == "__main__":
    main()
