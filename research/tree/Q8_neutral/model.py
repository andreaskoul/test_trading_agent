"""Branch Q8_neutral (layer 3, Amendment 8): neutralisation of a weekly score panel. Development data only.

    from model import neutralise, check
    out = neutralise(scores, D, rows, mode="N1")      # rows = the scored Thursdays; NaN elsewhere

Modes (registered in STATE.json before scoring):
* "N0"  control: the centred cross-sectional rank of the score (no neutralisation).
* "N1"  Numerai partial neutralisation, p = 0.5: s = centred rank; E = [1, z(beta), z(log ADV), z(vol60), sector
        dummies]; s -= p * E @ pinv(E) @ s; then re-ranked (centred).
* "N2w" within-sector ranks: the score's percentile rank inside its sector group, centred.

Every exposure at row t uses data <= t only:
* beta   D["beta"][t].
* ADV    log of the mean FINRA Reg SHO total share volume over sessions t-19..t (>= 10 sessions with data). This is a
         proxy: FINRA-reported (off-exchange) share volume, not consolidated dollar volume (dev.npz has no price level).
* vol60  sd of D["r"] over t-59..t (>= 40 sessions).
* sector GICS sector = the typed 2-digit prefix of `industry_code` in .cache/p8/gics.json (current classification
         applied to the past: disclosed look-ahead). A name not in the file is its own group, "NA".
A missing exposure is set to the week's cross-sectional mean (z = 0). Only names with a finite score and eligibility
at t are used and returned; everything else is NaN.
"""
import json
import os
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
GICS = os.path.join(ROOT, ".cache", "p8", "gics.json")
FINRA = os.path.join(ROOT, ".cache", "tree", "extra_finra.npz")
P = 0.5
# Set after scoring by the registered rule (highest decile net Sharpe with max drawdown no worse than N0), per signal.
# None of these differences is significant (REPORT.md); N0 is the honest default for anything not listed.
BEST_BY_SIGNAL = {"trees": "N1", "ipca": "N0", "master": "N1"}
BEST = "N1"           # trees, the primary signal


def sectors(names):
    """Typed GICS sector code per panel name ('NA' when the name is absent from gics.json)."""
    firms = json.load(open(GICS))["firms"]
    out = []
    for n in names:
        f = firms.get(n)
        code = (f or {}).get("industry_code")
        out.append(code[:2] if isinstance(code, str) and len(code) == 6 and code.isdigit() else "NA")
    return np.array(out)


def _finra_total(D):
    if "_q8_finra" not in D:
        z = np.load(FINRA, allow_pickle=False)
        assert z["total"].shape == D["y5"].shape, "FINRA file not aligned to the panel"
        D["_q8_finra"] = z["total"].astype(np.float64)
    return D["_q8_finra"]


def _z(x, m):
    v = np.where(np.isfinite(x) & m, x, np.nan)
    mu, sd = np.nanmean(v[m]), np.nanstd(v[m])
    v = np.where(np.isfinite(v), (v - mu) / (sd if sd > 0 else 1.0), 0.0)
    return v[m]


def exposures(D, t, m, sec):
    """E (names in m x columns): intercept, z(beta), z(log ADV), z(vol60), sector dummies."""
    vol = _finra_total(D)[max(0, t - 19):t + 1]
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        adv = np.where((np.isfinite(vol) & (vol > 0)).sum(0) >= 10, np.log(np.nanmean(np.where(vol > 0, vol, np.nan), 0)), np.nan)
        r = D["r"][max(0, t - 59):t + 1].astype(np.float64)
        v60 = np.where(np.isfinite(r).sum(0) >= 40, np.nanstd(r, 0), np.nan)
    cols = [np.ones(m.sum()), _z(D["beta"][t].astype(np.float64), m), _z(adv, m), _z(v60, m)]
    s = sec[m]
    for g in np.unique(s):
        cols.append((s == g).astype(np.float64))
    return np.column_stack(cols)


def _crank(x):
    return pd.Series(x).rank(pct=True).to_numpy() - 0.5


def neutralise(scores, D, rows, mode=BEST, p=P, sec=None):
    sec = sectors(D["names"]) if sec is None else sec
    out = np.full(scores.shape, np.nan)
    for t in rows:
        m = np.isfinite(scores[t]) & D["elig"][t]
        if m.sum() < 2:
            continue
        s = _crank(scores[t][m])
        if mode == "N0":
            pass
        elif mode == "N1":
            E = exposures(D, t, m, sec)
            s = _crank(s - p * E @ (np.linalg.pinv(E) @ s))
        elif mode == "N2w":
            s = pd.Series(s).groupby(sec[m]).rank(pct=True).to_numpy() - 0.5
        else:
            raise ValueError(mode)
        out[t, np.where(m)[0]] = s
    return out


def check(D, rows, scores, out=None, mode="N1"):
    """Content contract (CLAUDE.md rules 2-3), raising on failure:
    * sectors: the typed code exists for at least the audited 434 of 666 eligible validation names;
    * exposures: beta finite for all, FINRA ADV for >= 95% and vol60 for >= 70% of scored name-weeks (audited
      97.1% / 76.8% of eligible name-weeks);
    * output: same finite pattern as the masked input, and for N1 at p = 1 the residual is orthogonal to E."""
    sec = sectors(D["names"])
    el_any = D["elig"][rows].any(0)
    covered = int(((sec != "NA") & el_any).sum())
    assert covered >= 434, f"sector coverage fell: {covered} eligible names with a sector, expected >= 434"
    assert set(np.unique(sec)) - {"NA"} <= {"10", "15", "20", "25", "30", "35", "40", "45", "50", "55", "60"}
    m = np.isfinite(scores[rows]) & D["elig"][rows]
    fin = _finra_total(D)
    assert np.isfinite(D["beta"][rows][m]).all(), "beta missing on scored names"
    assert (np.isfinite(fin[rows]) & m).sum() / m.sum() >= 0.95, "FINRA volume coverage below 95% of scored name-weeks"
    r_ok = np.isfinite(D["r"][rows]) & m
    assert r_ok.sum() / m.sum() >= 0.70, "price coverage below 70% of scored name-weeks"
    if out is not None:
        assert (np.isfinite(out[rows]) == m).all(), "neutralised panel does not keep the input's mask"
    t = rows[len(rows) // 2]
    mt = np.isfinite(scores[t]) & D["elig"][t]
    E = exposures(D, t, mt, sec)
    s = _crank(scores[t][mt])
    res = s - E @ (np.linalg.pinv(E) @ s)
    assert np.abs(E.T @ res).max() < 1e-6 * len(s), "full neutralisation does not remove the exposures"
    return {"sector_names_eligible": covered, "eligible_names": int(el_any.sum()),
            "finra_cov": float((np.isfinite(fin[rows]) & m).sum() / m.sum()), "price_cov": float(r_ok.sum() / m.sum())}
