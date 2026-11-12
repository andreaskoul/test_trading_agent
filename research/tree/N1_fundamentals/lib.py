"""Branch N1: point-in-time SEC XBRL fundamentals on top of the frozen MASTER 5-day scores.

Causality: harness.load_extra("fundamentals") is already point-in-time (a value is present from the session after its
first filing). Every characteristic at row t uses only row t of that file; cross-sectional ranks use row t only.
Orientation: every characteristic is signed by its literature prior so that higher = expected to outperform.
Missing = neutral (0 after centring) inside composites; NaN in single-characteristic scores.

No price level exists in dev.npz (only returns), so market value, book-to-market and payout *yield* cannot be formed.
Substitutes, disclosed: payout and earnings are scaled by total assets; size is proxied by log assets.
"""
import os
import sys

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "3")

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import harness  # noqa: E402

LOG = os.path.join(HERE, "RESULTS.jsonl")
_C = {}

# name -> (description, literature sign already applied below)
CHARS = {
    "gpa": "gross profit / assets (Novy-Marx 2013), +",
    "opa": "operating income / assets (operating profitability, FF5 RMW), +",
    "roa": "net income / assets, +",
    "accruals": "-(net income - cfo) / mean assets (Sloan 1996)",
    "agrowth": "-(assets_0 / assets_1 - 1) (Cooper, Gulen and Schill 2008)",
    "invest": "-capex / assets (investment)",
    "payout": "(dividends + buybacks) / assets (net payout, assets-scaled: no price level), +",
    "issuance": "-(shares_0 / shares_1 - 1) (net share issuance)",
    "sue": "latest standardised earnings surprise (PEAD), +",
    "rnd": "R&D / assets, +",
    "leverage": "-(liabilities / assets)",
    "cfoa": "cfo / assets (cash profitability), +",
}
COMPOSITE = ("prof", "accruals", "agrowth", "payout", "sue")   # registered equal-weight literature composite


def _div(a, b):
    with np.errstate(all="ignore"):
        out = a / b
    out[~np.isfinite(out)] = np.nan
    return out


def raw():
    if "raw" in _C:
        return _C["raw"]
    F = {k: v.astype(np.float64) for k, v in harness.load_extra("fundamentals").items() if k != "note"}
    A0, A1 = F["assets_0"], F["assets_1"]
    A0 = np.where(A0 > 0, A0, np.nan)
    A1 = np.where(A1 > 0, A1, np.nan)
    Am = np.where(np.isfinite(A1), (A0 + A1) / 2, A0)
    R = {
        "gpa": _div(F["gross_profit_0"], A0),
        "opa": _div(F["operating_income_0"], A0),
        "roa": _div(F["net_income_0"], A0),
        "accruals": -_div(F["net_income_0"] - F["cfo_0"], Am),
        "agrowth": -(_div(A0, A1) - 1),
        "invest": -_div(np.abs(F["capex_0"]), A0),
        "payout": _div(np.nan_to_num(F["dividends_0"], nan=0.0) + np.nan_to_num(F["buybacks_0"], nan=0.0), A0)
        * np.where(np.isfinite(F["dividends_0"]) | np.isfinite(F["buybacks_0"]), 1.0, np.nan),
        "issuance": -(_div(F["shares_0"], np.where(F["shares_1"] > 0, F["shares_1"], np.nan)) - 1),
        "sue": F["sue"],
        "rnd": _div(F["rnd_0"], A0),
        "leverage": -_div(F["liabilities_0"], A0),
        "cfoa": _div(F["cfo_0"], A0),
        "logassets": np.log(A0),
    }
    _C["raw"] = R
    return R


def xrank(a, mask):
    """Cross-sectional percentile rank per row among `mask`, centred to [-0.5, 0.5]; NaN kept."""
    a = np.where(mask & np.isfinite(a), a, np.nan)
    return pd.DataFrame(a).rank(axis=1, pct=True).to_numpy() - 0.5


def ranks():
    """Centred cross-sectional ranks (NaN = missing) of every characteristic, plus 'prof' = gpa where present else opa."""
    if "ranks" in _C:
        return _C["ranks"]
    D = data()
    R = {k: xrank(v, D["elig"]) for k, v in raw().items()}
    R["prof"] = np.where(np.isfinite(R["gpa"]), R["gpa"], R["opa"])
    R["master"] = xrank(D["master_h5_ref"].astype(np.float64), D["elig"])
    _C["ranks"] = R
    return R


def data():
    if "D" not in _C:
        _C["D"] = harness.load()
    return _C["D"]


def composite(keys=COMPOSITE):
    """Equal-weight mean of signed ranks; missing = neutral (0); NaN only where every component is missing."""
    R = ranks()
    S = np.stack([R[k] for k in keys], 0)
    n = np.isfinite(S).sum(0)
    c = np.nansum(S, 0) / len(keys)
    return np.where(n > 0, c, np.nan)


def blend(score, w_master):
    """w * rank(MASTER) + (1-w) * rank(score); defined only where MASTER is (so increment compares the same names);
    a missing score counts as neutral."""
    D, R = data(), ranks()
    s = xrank(score, D["elig"])
    s = np.where(np.isfinite(R["master"]), np.nan_to_num(s, nan=0.0), np.nan)
    return w_master * R["master"] + (1 - w_master) * s


def target_rank(D, rows):
    """Use the D passed to fit_predict (its y5 is blanked after train_end)."""
    return xrank(D["y5"][rows].astype(np.float64), D["elig"][rows])


def train_thursdays(te, start=None):
    D = data()
    S = D["S"]
    m = (S.weekday == 3) & (np.arange(len(S)) <= te)
    if start is not None:
        m &= S.year >= start
    return np.where(m)[0]


def update_state(name, line, plan, best=None):
    import json, time
    p = os.path.join(HERE, "STATE.json")
    st = json.load(open(p))
    if name and name not in st["scored"]:
        st["scored"].append(name)
    st["configurations_scored"] = len([n for n in st["scored"] if not n.startswith("single_")])
    st["plan"] = plan
    st["pending"] = [n for n in plan if n not in st["scored"]]
    st["status"] = "in progress"
    if best is not None:
        st["best"] = best
    st["notes"].append(line)
    st["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(st, open(p, "w"), indent=1)
