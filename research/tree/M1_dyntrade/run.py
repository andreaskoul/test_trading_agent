"""Branch M1: run every configuration and log it. python3 research/tree/M1_dyntrade/run.py [config ...]"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib  # noqa: E402

harness = lib.harness
LOG = os.path.join(HERE, "RESULTS.jsonl")
CONFIGS = {   # name: (kind, kwargs, note)
    "decile": ("decile", {}, "phase-1 book: equal-weight top/bottom decile, rebuilt weekly"),
    "ema_hl1": ("ema", {"hl": 1.0}, "X2: rank smoothed with half-life 1 week, then deciles"),
    "band10": ("band", {"band": 0.1}, "no-trade band: enter at 10% tails, exit past 20% tails"),
    "mv_diag": ("mv_diag", {}, "mean-variance aim, diagonal residual covariance, traded fully each week"),
    "gp_decile": ("gp_decile", {"cal": "ref"}, "GP partial trade toward the decile aim, derived tau (ref calibration)"),
    "gp_mv_diag": ("gp_mv_diag", {"cal": "ref"}, "GP toward diagonal mean-variance aim, derived tau (ref)"),
    "gp_mv_lw": ("gp_mv_lw", {"cal": "ref"}, "GP toward Ledoit-Wolf mean-variance aim, derived tau (ref)"),
    "gp_mv_diag_fp": ("gp_mv_diag", {"cal": "fp"}, "GP toward diagonal MV aim, tau from fixed-point calibration"),
    "gp_decile_fp": ("gp_decile", {"cal": "fp"}, "GP toward decile aim, tau from fixed-point calibration"),
}


def bases(D):
    return {"MASTER": D["master_h5_ref"].astype(np.float64),
            "HGB4h": np.load(os.path.join(HERE, "base_hgb_multihorizon.npy")).astype(np.float64)}


def run(names):
    D = harness.load()
    for bname, sc in bases(D).items():
        rows = lib.val_rows(D, sc)
        for name in names:
            kind, kw, note = CONFIGS[name]
            W = lib.build(kind, sc, D, rows, **kw)
            sm = lib.summary(lib.simulate(W, D, rows), skip_first=False)
            res = {"base": bname, "config": name, "note": note, "weeks": int(len(rows)),
                   "ic_scores": lib.ic_of(sc, D, rows), "ic_book": lib.ic_of(np.where(np.isfinite(sc), 0, np.nan) + _rowfill(W, rows, sc.shape), D, rows),
                   **{k: float(v) for k, v in sm.items()}, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            if kind.startswith("gp"):
                P = lib.gp_params(sc, D, rows, kw.get("cal", "ref"))
                res["tau_by_year"] = {int(y): float(np.nanmean(P[np.isin(rows, harness.thursdays(D, y)), 0])) for y in harness.VAL_YEARS}
                res["g_by_year"] = {int(y): float(np.nanmean(P[np.isin(rows, harness.thursdays(D, y)), 1])) for y in harness.VAL_YEARS}
                res["phi_mean"] = float(np.nanmean(P[:, 4]))
            # yearly net for the noise statement
            sim = lib.simulate(W, D, rows)
            res["net_by_year"] = {int(y): float(52 * 100 * sim["net"][np.isin(rows, harness.thursdays(D, y))].mean()) for y in harness.VAL_YEARS}
            with open(LOG, "a") as f:
                f.write(json.dumps(res) + "\n")
            print(bname, name, {k: round(res[k], 4) for k in ("ic_book", "gross_pct_yr", "cost_pct_yr", "turnover_wk", "net_pct_yr", "net_sharpe")}, flush=True)


def _rowfill(W, rows, shape):
    """Weights as a panel, so the IC of the held book (weights vs y5, names with nonzero weight... all scored names)."""
    P = np.full(shape, np.nan)
    P[rows] = W
    return P


if __name__ == "__main__":
    run(sys.argv[1:] or list(CONFIGS))
