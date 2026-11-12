"""Adaptive market-exposure core (research/sharpe/PREREG.md). Research only.

    python research/sharpe/core.py check     # US file: reproduce the incumbent's recorded Sharpe; US descriptive table
    python research/sharpe/core.py read      # ONCE: the three regions (READ.lock)
"""
import io
import json
import math
import os
import sys
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = os.path.join(ROOT, ".cache", "sharpe")
TARGET, SPREAD, SEED, BLOCK, DRAWS = 0.16, 0.01, 20261110, 20, 5000
BANDS = {"policy": (0.7, 1.3), "wide": (0.0, 1.5)}
REGIONS = {"Europe": "Europe_5_Factors_Daily_CSV.zip", "Japan": "Japan_5_Factors_Daily_CSV.zip",
           "AsiaPacExJapan": "Asia_Pacific_ex_Japan_5_Factors_Daily_CSV.zip"}
RULES = ("T200", "TSM", "VOL", "PANIC")
ALPHA, ETA, K = 1 / 252, math.sqrt(8 * math.log(5) / 252) / 0.10, 5


def us():
    raw = pd.read_csv(os.path.join(CACHE, "F-F_Research_Data_Factors_daily.csv"), skiprows=4, names=["d", "mkt_rf", "smb", "hml", "rf"], dtype=str)
    raw = raw[raw.d.str.strip().str.fullmatch(r"\d{8}", na=False)]
    df = pd.DataFrame({"mkt": raw.mkt_rf.astype(float) / 100 + raw.rf.astype(float) / 100, "rf": raw.rf.astype(float) / 100})
    df.index = pd.to_datetime(raw.d.str.strip(), format="%Y%m%d")
    return df


def region(fname):
    z = zipfile.ZipFile(os.path.join(CACHE, fname))
    lines = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    start = next(i for i, l in enumerate(lines) if "Mkt-RF" in l)
    hdr = [x.strip() for x in lines[start].split(",")]
    rows = []
    for l in lines[start + 1:]:
        p = [x.strip() for x in l.split(",")]
        if not (p[0].isdigit() and len(p[0]) == 8):
            break
        rows.append(p)
    d = pd.DataFrame(rows, columns=["d"] + hdr[1:])
    out = pd.DataFrame({"mkt": d["Mkt-RF"].astype(float) / 100 + d["RF"].astype(float) / 100, "rf": d["RF"].astype(float) / 100})
    out.index = pd.to_datetime(d["d"], format="%Y%m%d")
    out = out[(out.index <= "2025-12-31") & (out.mkt.abs() < 0.9)]                    # -99.99 marks a missing day
    return out


def base_weights(r, rf, band):
    """The four rules' weights for day t from information up to the close of t-1."""
    lo, hi = band
    idx, cash = (1 + r).cumprod(), (1 + rf).cumprod()
    s21 = r.rolling(21).std() * 252 ** .5
    up = (idx > idx.rolling(200).mean()).where(idx.rolling(200).mean().notna())
    tsm = sum(((idx / idx.shift(L)) > (cash / cash.shift(L))).where(idx.shift(L).notna()).astype(float) for L in (21, 63, 126, 252)) / 4
    tsm = tsm.where(idx.shift(252).notna())
    panic = ((idx / idx.shift(252) < 1) & (s21 > s21.rolling(756).median())).where(s21.rolling(756).median().notna() & idx.shift(252).notna())
    W = pd.DataFrame({"T200": lo + up.astype(float) * (hi - lo), "TSM": lo + tsm * (hi - lo),
                      "VOL": (TARGET / s21).clip(lo, hi), "PANIC": lo + (1 - panic.astype(float)) * (hi - lo)})
    W = W.where(pd.DataFrame({"T200": up.notna(), "TSM": tsm.notna(), "VOL": s21.notna(), "PANIC": panic.notna()}))
    return W.shift(1)


def pret(r, rf, w, cost):
    return w * r + (1 - w) * rf - np.maximum(w - 1, 0) * SPREAD / 252 - cost * w.diff().abs().fillna(0.0)


def strategies(df, band, cost=2e-4, eta=ETA, alpha=ALPHA):
    """Returns and weights of every rule, ENS, FS and BH from the first day on which all four rules exist."""
    r, rf = df.mkt, df.rf
    W = base_weights(r, rf, band).dropna()
    r, rf = r.loc[W.index], rf.loc[W.index]
    W["ENS"] = W[list(RULES)].mean(1)
    W["BH"] = 1.0
    R = pd.DataFrame({k: pret(r, rf, W[k], cost) for k in W})
    ex = ["T200", "TSM", "VOL", "PANIC", "BH"]
    X = (R[ex].sub(rf, axis=0)).to_numpy()
    U = X - X ** 2
    Wx = W[ex].to_numpy()
    v = np.full(K, 1 / K)
    wfs = np.empty(len(W))
    for t in range(len(W)):
        wfs[t] = v @ Wx[t]                                   # decided before day t's returns are known
        v = v * np.exp(eta * U[t])
        v = (1 - alpha) * v / v.sum() + alpha / K
    W["FS"] = wfs
    R["FS"] = pret(r, rf, W["FS"], cost)
    return R, W, rf


def stats(rp, rf, w):
    ex = rp - rf
    wealth = (1 + rp).cumprod()
    yrs = len(rp) / 252
    return dict(pct_per_year=100 * float(wealth.iloc[-1] ** (1 / yrs) - 1), vol_pct=100 * float(rp.std() * 252 ** .5),
                sharpe=float(ex.mean() / ex.std() * 252 ** .5), worst_fall_pct=100 * float((wealth / wealth.cummax() - 1).min()),
                avg_w=float(w.mean()), turnover_per_yr=float(w.diff().abs().sum() / yrs), years=round(yrs, 1))


def sh(x):
    return x.mean(0) / x.std(0) * 252 ** .5


def boot_idx(n, rng):
    out, tot = [], 0
    while tot < n:
        L = rng.geometric(1 / BLOCK); s = rng.integers(n)
        out.append((s + np.arange(L)) % n); tot += L
    return np.concatenate(out)[:n]


def holm(p, alpha=0.05):
    order = sorted(p, key=p.get); m = len(p); res, ok = {}, True
    for i, k in enumerate(order):
        ok = ok and p[k] <= alpha / (m - i)
        res[k] = bool(ok)
    return res


def table(df, band, cost=2e-4, **kw):
    R, W, rf = strategies(df, band, cost, **kw)
    return {k: stats(R[k], rf, W[k]) for k in R}, R, W, rf


def check():
    df = us()
    # the incumbent on the exposure study's window (from 1927-06-01), 2 bp
    lo, hi = BANDS["policy"]
    idx = (1 + df.mkt).cumprod()
    ma = idx.rolling(200).mean()
    w = (lo + (idx > ma).where(ma.notna()).astype(float) * (hi - lo)).where(ma.notna()).shift(1)
    rp = pret(df.mkt, df.rf, w, 2e-4).loc["1927-06-01":]
    got = float(((rp - df.rf.loc[rp.index]).mean() / (rp - df.rf.loc[rp.index]).std()) * 252 ** .5)
    want = json.load(open(os.path.join(ROOT, "research", "exposure", "results.json")))["full"]["P3"]["sharpe"]
    ok = round(got, 2) == round(want, 2)
    out = {"incumbent_sharpe_reproduced": got, "recorded": want, "ok": ok, "US": {}}
    if ok:
        for b, band in BANDS.items():
            T, R, W, rf = table(df, band)
            out["US"][b] = T
            out["US"][b + "_by_period"] = {f"{a}-{z}": {k: float(sh((R[k] - rf).loc[str(a):str(z)].to_numpy())) for k in R}
                                           for a, z in ((1929, 1962), (1963, 1999), (2000, 2026))}
    json.dump(out, open(os.path.join(HERE, "US_CHECK.json"), "w"), indent=1)
    return out


def read():
    lock = os.path.join(HERE, "READ.lock")
    if os.path.exists(lock):
        sys.exit("the read was already made: " + open(lock).read())
    c = check()
    if not c["ok"]:
        sys.exit(f"code check failed: {c['incumbent_sharpe_reproduced']:.3f} vs {c['recorded']:.3f}; regions not read")
    open(lock, "w").write(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    data = {n: region(f) for n, f in REGIONS.items()}
    res = {"run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "eta": ETA, "alpha": ALPHA, "bands": {}}
    for b, band in BANDS.items():
        out, EX = {"regions": {}}, {}
        for n, df in data.items():
            T, R, W, rf = table(df, band)
            out["regions"][n] = T
            out["regions"][n + "_first_day"] = str(R.index[0].date())
            out["regions"][n + "_by_decade"] = {f"{a}s": {k: float(sh((R[k] - rf).loc[str(a):str(a + 9)].to_numpy())) for k in R} for a in (1990, 2000, 2010, 2020)}
            out["regions"][n + "_cost10bp_sharpe"] = {k: v["sharpe"] for k, v in table(df, band, 1e-3)[0].items()}
            EX[n] = R.sub(rf, axis=0)
        common = sorted(set.intersection(*[set(e.index) for e in EX.values()]))
        A = {n: e.loc[common] for n, e in EX.items()}
        pairs = {"H1": ("ENS", "BH"), "H2": ("ENS", "T200"), "H3": ("FS", "ENS")}
        obs = {h: float(np.mean([sh(A[n][a].to_numpy()) - sh(A[n][b_].to_numpy()) for n in A])) for h, (a, b_) in pairs.items()}
        rng = np.random.default_rng(SEED)
        draws = {h: np.empty(DRAWS) for h in pairs}
        arr = {n: {k: A[n][k].to_numpy() for k in ("ENS", "BH", "T200", "FS")} for n in A}
        for i in range(DRAWS):
            ix = boot_idx(len(common), rng)
            for h, (a, b_) in pairs.items():
                draws[h][i] = np.mean([sh(arr[n][a][ix]) - sh(arr[n][b_][ix]) for n in arr])
        p = {h: float((draws[h] <= 0).mean()) for h in pairs}
        out["tests"] = {h: {"sharpe_diff": obs[h], "p_one_sided": p[h], "ci90": [float(np.quantile(draws[h], .05)), float(np.quantile(draws[h], .95))]} for h in pairs}
        hm = holm(p)
        for h in pairs:
            out["tests"][h]["holm_pass"] = hm[h]
        out["pooled_days"] = len(common)
        # exploratory sensitivities of FS (labelled as such)
        out["exploratory_FS"] = {f"eta_x{m}_alpha_1/{int(1 / a)}": float(np.mean([sh((lambda R, rf: (R["FS"] - rf).to_numpy())(*(lambda t: (t[1], t[3]))(table(df, band, eta=ETA * m, alpha=a)))) for df in data.values()]))
                                 for m, a in ((1, 1 / 252), (10, 1 / 252), (100, 1 / 252), (1, 1 / 63), (1, 1 / 756), (100, 1 / 63))}
        res["bands"][b] = out
    json.dump(res, open(os.path.join(HERE, "RESULT.json"), "w"), indent=1)
    return res


if __name__ == "__main__":
    out = {"check": check, "read": read}[sys.argv[1]]()
    print(json.dumps(out, indent=1)[:200])
