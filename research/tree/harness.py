"""Tree search over stock-selection models: the shared development harness (research/tree/PREREG.md).

The development file ends on 2019-12-31. Nothing after that date exists in it: the 2020-2025 holdout cannot be read
from here. Every candidate is a function

    fit_predict(D, train_end, pred_rows, seed) -> array of shape (len(pred_rows), n_names)

* D is the dict from load(). Rows are sessions, columns are names.
* Train only on rows <= train_end. The harness blanks D["y5"] after train_end before calling you, so a target from the
  validation year cannot leak. Features for a prediction row may use anything in D up to and including that row
  (D["r"], D["e"], D["Z"], D["beta"], D["rm"], D["elig"]); never a later row.
* A prediction is a score per name: higher = expected to outperform over the next 5 sessions (entered at the next
  close). NaN = no view.

    from harness import load, walk_forward, score
    pred = walk_forward(fit_predict, seeds=(0, 1, 2))     # validation years 2013-2019, mean over seeds
    print(score(pred, "my model", "research/tree/<branch>/RESULTS.jsonl", note="what changed"))
"""
import json
import os
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DEV = os.path.join(ROOT, ".cache", "tree", "dev.npz")
VAL_YEARS = (2013, 2014, 2015, 2016, 2017, 2018, 2019)
COST = 5e-4


def load(path=DEV):
    z = np.load(path, allow_pickle=False)
    D = {k: z[k] for k in z.files}
    D["S"] = pd.DatetimeIndex(D["S"])
    D["names"] = [str(n) for n in D["names"]]
    return D


def thursdays(D, year):
    S = D["S"]
    return np.where((S.weekday == 3) & (S.year == year))[0]


def train_end(D, year):
    """The last row whose 5-session target ends before the first session of `year`."""
    first = int(np.where(D["S"].year == year)[0][0])
    return first - 8


def walk_forward(fit_predict, seeds=(0, 1, 2), years=VAL_YEARS, D=None):
    D = D or load()
    pred = np.full(D["y5"].shape, np.nan, dtype=np.float64)
    for y in years:
        te, rows = train_end(D, y), thursdays(D, y)
        Dm = dict(D)
        y5 = D["y5"].copy()
        y5[te + 1:] = np.nan
        Dm["y5"] = y5
        ps = []
        for s in seeds:
            p = np.asarray(fit_predict(Dm, te, rows, s), dtype=np.float64)
            assert p.shape == (len(rows), y5.shape[1]), p.shape
            # average ranks across seeds, so scale differences between seeds do not matter
            ps.append(pd.DataFrame(p).rank(axis=1, pct=True).to_numpy())
        with np.errstate(all="ignore"):
            pred[rows] = np.nanmean(ps, 0)
    return pred


def weekly_ic(pred, D, rows):
    out = []
    for t in rows:
        m = np.isfinite(pred[t]) & np.isfinite(D["y5"][t]) & D["elig"][t]
        if m.sum() < 50:
            out.append(np.nan)
            continue
        out.append(float(pd.Series(pred[t][m]).corr(pd.Series(D["y5"][t][m]), method="spearman")))
    return np.array(out)


def decile_net(pred, D, rows):
    """Weekly top-minus-bottom decile spread of the 5-session hedged return, net of 5 bp a side on the names replaced."""
    out, prev_top, prev_bot = [], set(), set()
    for t in rows:
        m = np.isfinite(pred[t]) & np.isfinite(D["y5"][t]) & D["elig"][t]
        if m.sum() < 50:
            continue
        idx = np.where(m)[0]
        pct = pd.Series(pred[t][m]).rank(pct=True).to_numpy()
        top, bot = set(idx[pct > 0.9]), set(idx[pct <= 0.1])
        gross = float(D["y5"][t][list(top)].mean() - D["y5"][t][list(bot)].mean()) / 2          # 0.5 a side
        turn = (len(top - prev_top) / max(len(top), 1) + len(bot - prev_bot) / max(len(bot), 1)) / 2   # share replaced, per unit gross
        out.append(gross - COST * 2 * turn)
        prev_top, prev_bot = top, bot
    return np.array(out)


def score(pred, name, log=None, note="", D=None, years=VAL_YEARS):
    D = D or load()
    ics, by = [], {}
    for y in years:
        ic = weekly_ic(pred, D, thursdays(D, y))
        by[y] = float(np.nanmean(ic))
        ics.append(ic)
    ic = np.concatenate(ics)
    ic = ic[np.isfinite(ic)]
    rows = np.concatenate([thursdays(D, y) for y in years])
    net = decile_net(pred, D, rows)
    res = {"name": name, "note": note, "ic": float(ic.mean()), "ic_t": float(ic.mean() / ic.std(ddof=1) * np.sqrt(len(ic))), "weeks": int(len(ic)),
           "ic_by_year": by, "min_year_ic": float(min(by.values())), "share_weeks_positive": float((ic > 0).mean()),
           "decile_net_pct_per_year": float(52 * net.mean() * 100), "decile_net_sharpe": float(net.mean() / net.std(ddof=1) * np.sqrt(52)),
           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if log:
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "a") as f:
            f.write(json.dumps(res) + "\n")
    return res


def ridge_fit_predict(D, te, rows, seed, lam=1.0):
    """The reference: ridge of y5 on the five characteristics, all Thursdays up to train_end."""
    S = D["S"]
    tr = np.where((S.weekday == 3) & (np.arange(len(S)) <= te))[0]
    X, y = D["Z"][tr].reshape(-1, D["Z"].shape[2]), D["y5"][tr].reshape(-1)
    m = np.isfinite(X).all(1) & np.isfinite(y)
    X, y = X[m].astype(np.float64), y[m].astype(np.float64)
    b = np.linalg.solve(X.T @ X + lam * len(y) / 1000 * np.eye(X.shape[1]), X.T @ y)
    return D["Z"][rows].astype(np.float64) @ b


if __name__ == "__main__":
    D = load()
    print(json.dumps(score(walk_forward(ridge_fit_predict, seeds=(0,), D=D), "ridge reference", D=D), indent=1))
    print(json.dumps(score(D["master_h5_ref"].astype(np.float64), "MASTER 5-day (October read), reference", D=D), indent=1))


# ---------------------------------------------------------------- phase 2 additions (research/tree/PHASE2_PLAN.md)
def load_extra(key):
    """A phase-2 input file, aligned to load()'s rows and columns and ending 2019-12-31: "finra" (daily short and total
    volume), "intraday" (overnight + 13 half-hour log returns, 2016-2019), "fundamentals" (point-in-time annual SEC
    XBRL values and the latest earnings surprise) or "peers" (yearly 10-K text-neighbour graph). Read its "note" field
    before use."""
    z = np.load(os.path.join(ROOT, ".cache", "tree", f"extra_{key}.npz"), allow_pickle=False)
    return {k: z[k] for k in z.files}


def increment(pred, name, log=None, note="", D=None, years=VAL_YEARS, base=None):
    """Phase-2 track N: is `pred` better than the frozen MASTER 5-day scores on the same weeks?
    Reports both ICs and the paired weekly difference with its t (Newey-West, 4 lags)."""
    D = D or load()
    base = D["master_h5_ref"].astype(np.float64) if base is None else base
    rows = np.concatenate([thursdays(D, y) for y in years])
    a, b = weekly_ic(pred, D, rows), weekly_ic(base, D, rows)
    m = np.isfinite(a) & np.isfinite(b)
    d = a[m] - b[m]
    n, dd = len(d), d - d.mean()
    v = dd @ dd / n
    for l in range(1, 5):
        v += 2 * (1 - l / 5) * (dd[l:] @ dd[:-l]) / n
    by = {int(y): float(np.nanmean(weekly_ic(pred, D, thursdays(D, y)) - weekly_ic(base, D, thursdays(D, y)))) for y in years}
    res = {"name": name, "note": note, "ic": float(a[m].mean()), "base_ic": float(b[m].mean()), "increment": float(d.mean()),
           "increment_t": float(d.mean() / np.sqrt(v / n)), "weeks": int(n), "increment_by_year": by,
           "years_increment_positive": int(sum(x > 0 for x in by.values())), "corr_with_base": float(np.nanmean(
               [pd.Series(pred[t]).corr(pd.Series(base[t]), method="spearman") for t in rows[m]])),
           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    full = score(pred, name, None, note, D, years)
    res.update({k: full[k] for k in ("decile_net_pct_per_year", "decile_net_sharpe")})
    if log:
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "a") as f:
            f.write(json.dumps(res) + "\n")
    return res
