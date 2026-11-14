"""N4_news shared code: loaders, the scoring wrapper (increment + covered subset + size terciles), STATE.json updates."""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
sys.path.insert(0, TREE)
import harness  # noqa: E402

YEARS = (2016, 2017, 2018, 2019)
NEWS_FILE = os.path.join(harness.ROOT, ".cache", "tree", "extra_news_dev.npz")
PREDS = os.path.join(harness.ROOT, ".cache", "tree", "preds", "N4_news")
LOG = os.path.join(HERE, "RESULTS.jsonl")
STATE = os.path.join(HERE, "STATE.json")
_C = {}


def news():
    if "news" not in _C:
        z = np.load(NEWS_FILE, allow_pickle=False)
        _C["news"] = {k: z[k] for k in z.files}
    return _C["news"]


def xrank(a, elig=None):
    a = np.asarray(a, dtype=np.float64).copy()
    if elig is not None:
        a[~elig] = np.nan
    return pd.DataFrame(a).rank(axis=1, pct=True).to_numpy() - 0.5


def nw_t(x, lags=4):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n, d = len(x), x - x.mean()
    v = d @ d / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (d[l:] @ d[:-l]) / n
    return x.mean() / np.sqrt(v / n)


def size_tercile(D):
    """Liquidity proxy for size: trailing 63-session mean dollar volume (q6_dv), tercile 0/1/2 across eligible names
    per session (NaN where unknown). No market cap exists in the development file."""
    if "terc" not in _C:
        dv = np.load(os.path.join(harness.ROOT, ".cache", "tree", "q6_dv.npz"), allow_pickle=False)["dv"].astype(np.float64)
        m = pd.DataFrame(dv).rolling(63, min_periods=40).mean().to_numpy().copy()
        m[~D["elig"]] = np.nan
        p = pd.DataFrame(m).rank(axis=1, pct=True).to_numpy().copy()
        _C["terc"] = np.where(np.isfinite(p), np.clip(np.ceil(p * 3) - 1, 0, 2), np.nan)
    return _C["terc"]


def covered(D):
    """Name-weeks with >= 1 headline in the prior 21 sessions (causal coverage)."""
    return news()["raw_has21"] == 1


def _mask(p, m):
    q = np.array(p, dtype=np.float64)
    q[~m] = np.nan
    return q


def evaluate(pred, name, note, D, control=None, control_name=None, save=True):
    """Log the increment over MASTER (full, covered subset, by size tercile) and, if given, over a control."""
    base = D["master_h5_ref"].astype(np.float64)
    res = harness.increment(pred, name, None, note, D, YEARS)
    cov = covered(D)
    rc = harness.increment(_mask(pred, cov), name, None, note, D, YEARS, base=_mask(base, cov))
    res["covered_subset"] = {k: rc[k] for k in ("ic", "base_ic", "increment", "increment_t", "years_increment_positive",
                                                 "increment_by_year", "weeks")}
    terc = size_tercile(D)
    res["by_size_tercile"] = {}
    for k in (0, 1, 2):
        mk = terc == k
        rk = harness.increment(_mask(pred, mk), name, None, note, D, YEARS, base=_mask(base, mk))
        res["by_size_tercile"][["low", "mid", "high"][k]] = {x: rk[x] for x in ("ic", "base_ic", "increment", "increment_t",
                                                                               "years_increment_positive", "weeks")}
    if control is not None:
        r2 = harness.increment(pred, name, None, note, D, YEARS, base=control)
        r3 = harness.increment(_mask(pred, cov), name, None, note, D, YEARS, base=_mask(control, cov))
        res["vs_control"] = {"control": control_name, **{k: r2[k] for k in ("base_ic", "increment", "increment_t",
                             "years_increment_positive", "increment_by_year", "corr_with_base")},
                             "covered_subset": {k: r3[k] for k in ("base_ic", "increment", "increment_t", "years_increment_positive")}}
    res["years"] = list(YEARS)
    with open(LOG, "a") as f:
        f.write(json.dumps(res) + "\n")
    if save:
        os.makedirs(PREDS, exist_ok=True)
        np.save(os.path.join(PREDS, f"{name}.npy"), np.asarray(pred, dtype=np.float32))
    by = " ".join("%+.4f" % v for v in res["increment_by_year"].values())
    print("%-10s IC %.4f base %.4f incr %+.4f t %+.2f [%s] pos %d/4 | covered incr %+.4f t %+.2f | net %+.1f%%/y%s" % (
        name, res["ic"], res["base_ic"], res["increment"], res["increment_t"], by, res["years_increment_positive"],
        rc["increment"], rc["increment_t"], res["decile_net_pct_per_year"],
        "" if control is None else " | vs %s %+.4f t %+.2f pos %d/4" % (control_name, res["vs_control"]["increment"],
                                                                       res["vs_control"]["increment_t"],
                                                                       res["vs_control"]["years_increment_positive"])),
          flush=True)
    return res


def state(scored=None, note=None, **kw):
    s = json.load(open(STATE))
    if scored:
        if scored not in s["scored"]:
            s["scored"].append(scored)
        s["pending"] = [p for p in s["pending"] if p != scored]
        s["configurations_scored"] = len(s["scored"])
    if note:
        s["notes"].append(note)
    s.update(kw)
    s["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(s, open(STATE, "w"), indent=1)
