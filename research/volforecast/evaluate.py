"""Evaluation of PREREG_VOL.md §6–§8.

    PY=~/.fund-runner/venv-vol/bin/python
    $PY -I research/volforecast/evaluate.py dev [classes]    # development read (open) -> DEV_VOL.json
    $PY -I research/volforecast/evaluate.py read             # THE out-of-sample read, once -> RESULT_VOL.json/.md

The development run truncates the panel at the development end (rows after it dropped, targets closing after it
blanked), so no out-of-sample datum is present. The read refuses unless the pre-registration, code and DEV_VOL.json
are committed and unchanged, the contract tests pass and READ_VOL.lock does not exist.
"""
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import data as DATA  # noqa: E402
import features as FE  # noqa: E402
import models as M  # noqa: E402

OOS_END = "2026-11-27"
WINDOWS = {"stock": {"dev": ("2019-01-02", "2021-12-31"), "oos": ("2022-01-03", OOS_END)},
           "etf": {"dev": ("2019-01-02", "2021-12-31"), "oos": ("2022-01-03", OOS_END)},
           "index": {"dev": ("1995-01-02", "2021-12-31"), "oos": ("2022-01-03", OOS_END)},
           "crypto": {"dev": ("2019-07-01", "2021-12-31"), "oos": ("2022-01-01", OOS_END)}}
FRESH = ("2026-01-01", OOS_END)
N_PROGRAMME = 44
ALPHA_PRIMARY = 0.10 / N_PROGRAMME
C2_HALF, C2_BURN = 252, 252
C3_ETA, C3_ALPHA = 0.5, 1 / 252
SEED = 20261128
LOCK = os.path.join(HERE, "READ_VOL.lock")


# ===================================================================================== losses and tests
def qlike(y, f):
    with np.errstate(divide="ignore", invalid="ignore"):
        return y / f - np.log(y / f) - 1


def lstar(y, f):
    """y/f + log f: QLIKE minus a term in y only; identical differentials, defined at y = 0."""
    return y / f + np.log(f)


def nw_se(d, lag):
    d = np.asarray(d, float)
    d = d - d.mean()
    n = len(d)
    v = d @ d / n
    for k in range(1, lag + 1):
        v += 2 * (1 - k / (lag + 1)) * (d[k:] @ d[:-k]) / n
    return math.sqrt(max(v, 0) / n)


def dm(daily_ref, daily_m, H):
    d = (daily_ref - daily_m).dropna()
    n = len(d)
    lag = max(2 * H, math.ceil(n ** (1 / 3)))
    se = nw_se(d.values, lag)
    t = d.mean() / se if se > 0 else np.nan
    return {"mean_gain": float(d.mean()), "se": float(se), "t": float(t), "n_days": int(n), "nw_lag": lag,
            "p_one_sided": float(1 - stats.norm.cdf(t)), "p_two_sided": float(2 * (1 - stats.norm.cdf(abs(t))))}


def holm(ps):
    keys = sorted(ps, key=ps.get)
    m, out, run = len(keys), {}, 0.0
    for i, k in enumerate(keys):
        run = max(run, min(1.0, (m - i) * ps[k]))
        out[k] = run
    return out


# ===================================================================================== combinations C2, C3
def adaptive(F, Y, end, cls, H):
    """C2 (discounted inverse-QLIKE, half-life 252 days of the class calendar, 252 scored days of burn-in) and C3
    (fixed share, eta 1/2, alpha 1/252). A loss is scored on the date its target closes; weights at origin t use
    scores dated <= t only (target windows closed by t's close)."""
    comps = M.COMBO[cls]
    ok = F[comps].notna().all(1) & np.isfinite(Y) & (Y > 0) & end.notna()
    L = pd.DataFrame({m: qlike(Y[ok], F.loc[ok, m]) for m in comps})
    L["sd"] = end[ok].values
    daily = L.groupby("sd")[comps].mean().sort_index()
    origins = np.sort(F.index.get_level_values("date").unique().values)
    cal = np.union1d(origins, daily.index.values)
    pos = {d: i for i, d in enumerate(cal)}
    dl = daily.reindex(cal)
    delta = 0.5 ** (1 / C2_HALF)
    num = np.zeros(len(comps))
    den, scored = 0.0, 0
    w3 = np.full(len(comps), 1 / len(comps))
    W2, W3 = {}, {}
    for d in cal:
        num *= delta
        den *= delta
        row = dl.loc[d].values
        if np.isfinite(row).all():
            num += row
            den += 1
            scored += 1
            v = w3 * np.exp(-C3_ETA * row)
            v /= v.sum()
            w3 = (1 - C3_ALPHA) * v + C3_ALPHA / len(comps)
        if scored >= C2_BURN:
            inv = 1 / (num / den)
            W2[d] = inv / inv.sum()
        else:
            W2[d] = np.full(len(comps), 1 / len(comps))
        W3[d] = w3.copy()
    dates = F.index.get_level_values("date").values
    w2 = np.array([W2[d] for d in dates])
    w3a = np.array([W3[d] for d in dates])
    X = F[comps].values
    return pd.Series((w2 * X).sum(1), index=F.index), pd.Series((w3a * X).sum(1), index=F.index), \
        {"C2_last": dict(zip(comps, np.round(W2[cal[-1]], 4))), "C3_last": dict(zip(comps, np.round(W3[cal[-1]], 4)))}


# ===================================================================================== economic measures
def forward_sum(ret, H):
    """Sum of returns over t+1..t+H, complete windows only (NaN on any missing or masked day)."""
    v = ret.shift(-1)
    s = v[::-1].rolling(H, min_periods=H).sum()[::-1]
    return s


def stop_hits(P, F, H, models, rows):
    """Random-direction positions, barrier -2W at closes, W = sqrt(forecast): share of windows that hit, both sides."""
    out = {m: [0, 0] for m in models}
    for a, g in P.loc[rows].groupby(level="asset", sort=False):
        r = P.loc[a, "ret"].astype(float)
        c = np.r_[0.0, np.nancumsum(r.values)]
        isn = np.r_[0, np.cumsum(np.isnan(r.values))]
        idx = {d: i for i, d in enumerate(r.index)}
        for d in g.index.get_level_values("date"):
            p = idx[d]
            if p + H >= len(r) or isn[p + H + 1] - isn[p + 1] > 0:
                continue
            path = c[p + 2:p + H + 2] - c[p + 1]
            lo, hi = path.min(), path.max()
            for m in models:
                W = math.sqrt(F.loc[(a, d), m])
                out[m][0] += (lo <= -2 * W) + (hi >= 2 * W)
                out[m][1] += 2
    theory = 2 * stats.norm.cdf(-(2 + 0.5826 / math.sqrt(H)))
    return {m: (v[0] / v[1] if v[1] else None) for m, v in out.items()}, theory


# ===================================================================================== one class, one window
def truncate(P, until, horizons):
    P = P[P.index.get_level_values("date") <= pd.Timestamp(until)].copy()
    for H in horizons:
        late = pd.to_datetime(P[f"end{H}"]) > pd.Timestamp(until)
        P.loc[late, [f"y{H}", f"y{H}_r2"]] = np.nan
    return P


def evaluate_class(cls, which, P=None):
    a, b = WINDOWS[cls][which]
    horizons = FE.HORIZONS_BY_CLASS[cls]
    P = pd.read_parquet(os.path.join(DATA.CACHE, f"panel_{cls}.parquet")) if P is None else P
    until = b
    if which == "dev":
        P = truncate(P, b, horizons)
    garch = M.garch_states(P) if "S2" in M.CLASS_MODELS[cls] else None
    res = {}
    for H in horizons:
        F = M.forecasts(P, cls, H, until, garch)
        Y = P[f"y{H}"].astype(float).reindex(F.index)
        end = pd.to_datetime(P[f"end{H}"]).reindex(F.index)
        F["C2"], F["C3"], wts = adaptive(F, Y, end, cls, H)
        dates = F.index.get_level_values("date")
        win = (dates >= pd.Timestamp(a)) & (dates <= pd.Timestamp(b)) & (end <= pd.Timestamp(b)).values
        if cls == "stock":
            win &= P["member"].reindex(F.index).fillna(False).astype(bool).values
            win &= ~P["masked"].reindex(F.index).fillna(False).astype(bool).values
        cols = list(F.columns)
        good = win & np.isfinite(Y.values) & (Y.values >= 0) & np.isfinite(F[cols].values).all(1) & \
            (F[cols].values > 0).all(1)
        Fg, Yg = F[good], Y[good]
        Ls = pd.DataFrame({m: lstar(Yg.values, Fg[m].values) for m in cols}, index=Fg.index)
        daily = Ls.groupby(level="date").mean()
        pos = Yg.values > 0
        lev = {m: float(np.mean(qlike(Yg.values[pos], Fg[m].values[pos]))) for m in cols}
        rH = {}
        for ref in ("S0", "S1"):
            tests = {m: dm(daily[ref], daily[m], H) for m in cols if m != ref}
            adj = holm({m: t["p_two_sided"] for m, t in tests.items()})
            for m in tests:
                tests[m]["p_holm"] = float(adj[m])
            rH[f"vs_{ref}"] = tests
        from arch.bootstrap import MCS
        mcs = MCS(daily, size=0.10, reps=1000, block_size=max(5, H), method="R", bootstrap="stationary",
                  seed=SEED)
        mcs.compute()
        R2 = P[f"y{H}_r2"].astype(float).reindex(Fg.index).values
        okr = np.isfinite(R2) & (R2 >= 0)
        dr = pd.DataFrame({m: lstar(R2[okr], Fg[m].values[okr]) for m in cols},
                          index=Fg.index[okr]).groupby(level="date").mean()
        z = (P["ret"].astype(float).groupby(level="asset", group_keys=False).apply(lambda s: forward_sum(s, H))
             .reindex(Fg.index).values)
        okz = np.isfinite(z)
        rH.update({
            "n_rows": int(good.sum()), "n_assets": int(Fg.index.get_level_values("asset").nunique()),
            "n_days": int(len(daily)), "mean_qlike": lev,
            "ratio_to_S0": {m: lev[m] / lev["S0"] for m in cols}, "ratio_to_S1": {m: lev[m] / lev["S1"] for m in cols},
            "mcs_90_included": sorted(mcs.included), "mcs_pvalues": {k: float(v) for k, v in mcs.pvalues["Pvalue"].items()},
            "realised_over_forecast": {m: float(Yg.sum() / Fg[m].sum()) for m in cols},
            "mz_slope_intercept": {m: [float(x) for x in np.polyfit(Fg[m].values, Yg.values, 1)] for m in cols},
            "tracking_std_z": {m: float(np.std(z[okz] / np.sqrt(Fg[m].values[okz]))) for m in cols},
            "r2_proxy_vs_S0": {m: dm(dr["S0"], dr[m], H) for m in cols if m != "S0"},
            "adaptive_weights_last": wts,
        })
        if which == "oos":
            fresh = (daily.index >= pd.Timestamp(FRESH[0])) & (daily.index <= pd.Timestamp(FRESH[1]))
            df = daily[fresh]
            rH["fresh_2026"] = {"n_days": int(len(df)),
                                "vs_S0": {m: dm(df["S0"], df[m], H) for m in cols if m != "S0"}}
        if cls == "stock" and H == 22:
            hits, theory = stop_hits(P, Fg, H, ["S0", "S1", "C1", "C2", "C3"], Fg.index)
            rH["stop_hit"] = {"rates": hits, "theory": theory}
            rH["daily_gain_C1_vs_S0"] = (daily["S0"] - daily["C1"]).to_dict() if which == "dev" else None
        res[f"H{H}"] = rH
        print(f"{cls} {which} H={H}: rows {rH['n_rows']:,}, days {rH['n_days']}, "
              f"C1/S0 {rH['ratio_to_S0']['C1']:.3f}, MCS {rH['mcs_90_included']}", flush=True)
    return res


# ===================================================================================== dev and power
def power(dev_stock):
    d = pd.Series(dev_stock["H22"]["daily_gain_C1_vs_S0"])
    H = 22
    lag = max(2 * H, math.ceil(len(d) ** (1 / 3)))
    sd_lr = nw_se(d.values, lag) * math.sqrt(len(d))
    base = dev_stock["H22"]["mean_qlike"]["S0"]
    delta = min(0.5 * d.mean(), 0.05 * base) if d.mean() > 0 else 0.05 * base
    n_oos = int(np.busday_count(WINDOWS["stock"]["oos"][0], OOS_END)) - H
    z = stats.norm.ppf(1 - ALPHA_PRIMARY)
    P_ = float(stats.norm.cdf(delta * math.sqrt(n_oos) / sd_lr - z))
    return {"dev_mean_gain": float(d.mean()), "dev_long_run_sd": float(sd_lr), "delta": float(delta),
            "delta_rule": "min(0.5 x development gain, 0.05 x development mean QLIKE of S0)", "n_oos_days": n_oos,
            "alpha": ALPHA_PRIMARY, "power": P_, "rule_3_met": P_ >= 0.5}


def dev(classes):
    out = json.load(open(os.path.join(HERE, "DEV_VOL.json"))) if os.path.exists(os.path.join(HERE, "DEV_VOL.json")) \
        else {}
    for cls in classes:
        out[cls] = evaluate_class(cls, "dev")
    if "stock" in out:
        out["power_primary"] = power(out["stock"])
        out["stock"]["H22"].pop("daily_gain_C1_vs_S0", None)
    out["written_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out["note"] = "development read (open): windows of PREREG_VOL.md §5, panel truncated at each class's dev end"
    json.dump(out, open(os.path.join(HERE, "DEV_VOL.json"), "w"), indent=1, default=float)


# ===================================================================================== the read
def _committed_and_clean(paths):
    for p in paths:
        r = subprocess.run(["git", "status", "--porcelain", p], capture_output=True, text=True, cwd=ROOT)
        if r.stdout.strip():
            raise SystemExit(f"refusing: {p} is not committed and unchanged")


def read():
    if os.path.exists(LOCK):
        raise SystemExit("refusing: READ_VOL.lock exists (the read is spent)")
    need = [os.path.join(HERE, f) for f in ("PREREG_VOL.md", "data.py", "features.py", "models.py", "evaluate.py",
                                            "test_vol.py", "DEV_VOL.json", "DATA_MANIFEST.json")]
    _committed_and_clean(need)
    dv = json.load(open(os.path.join(HERE, "DEV_VOL.json")))
    if "power_primary" not in dv or not all(c in dv for c in WINDOWS):
        raise SystemExit("refusing: DEV_VOL.json lacks a class or the power table")
    if subprocess.run([sys.executable, "-I", os.path.join(HERE, "test_vol.py")], capture_output=True).returncode:
        raise SystemExit("refusing: test_vol.py fails")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip()
    fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, json.dumps({"locked_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "commit": head}).encode())
    os.close(fd)
    res = {"commit": head, "lock": "READ_VOL.lock"}
    for cls in WINDOWS:
        res[cls] = evaluate_class(cls, "oos")
    p = res["stock"]["H22"]["vs_S0"]["C1"]
    cal = res["stock"]["H22"]["realised_over_forecast"]["C1"]
    hit = res["stock"]["H22"]["stop_hit"]
    hit_ok = abs(hit["rates"]["C1"] - hit["theory"]) <= 0.01
    gain_hi = p["mean_gain"] + stats.norm.ppf(0.95) * p["se"]
    base = res["stock"]["H22"]["mean_qlike"]["S0"]
    if p["p_one_sided"] <= ALPHA_PRIMARY and 0.9 <= cal <= 1.1 and hit_ok:
        verdict = "supported"
    elif gain_hi < 0.01 * base:
        verdict = "rejected"
    else:
        verdict = "inconclusive"
    res["primary"] = {"test": "stocks H=22, C1 vs S0, one-sided DM", "p": p["p_one_sided"], "alpha": ALPHA_PRIMARY,
                      "realised_over_forecast_C1": cal, "stop_hit_C1": hit["rates"]["C1"], "theory": hit["theory"],
                      "upper_90_gain": gain_hi, "one_percent_of_S0": 0.01 * base, "verdict": verdict,
                      "precision_estimate": not dv["power_primary"]["rule_3_met"]}
    res["written_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(res, open(os.path.join(HERE, "RESULT_VOL.json"), "w"), indent=1, default=float)
    print(json.dumps(res["primary"], indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "dev":
        dev(sys.argv[2].split(",") if len(sys.argv) > 2 else list(WINDOWS))
    elif sys.argv[1] == "read":
        read()
