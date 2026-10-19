"""Pre-registered test of the refit five-factor quant model on the S&P 500 (PREREG_quant_sp500.md).

    python sp500_test.py data     # download prices (no scoring; allowed before sign-off)
    python sp500_test.py run      # refuses unless the pre-registration is signed off, committed and pushed

Point-in-time membership; data ends 2025-12-31 (Jan-Sep 2026 is the sealed P8 holdout and is never loaded).
"""

import json
import os
import re
import subprocess
import sys

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge

import features as F
import panel as P

ROOT = P.ROOT
PREREG = os.path.join(ROOT, "reports", "research", "PREREG_quant_sp500.md")
OUT = os.path.join(P.REPORT, "SP500.md")
PX = os.path.join(P.CACHE, "sp500_close.parquet")
START, END, TRAIN0 = pd.Timestamp("2009-01-02"), pd.Timestamp("2025-12-31"), pd.Timestamp("2010-01-04")
H, ALPHAS = 20, (1e-2, 1e-1, 1, 10, 100, 1e3, 1e4, 1e5)


def membership():
    m = pd.read_csv(os.path.join(ROOT, "data", "raw", "stocks", "sp500_membership.csv"), parse_dates=["date"])
    return m[m.date <= END].set_index("date")["tickers"].map(lambda s: set(s.split(",")))


def download():
    import yfinance as yf
    mem = membership()
    names = sorted(set().union(*mem[mem.index >= START].values))
    ymap = {t: t.replace(".", "-") for t in names}
    frames = []
    for k in range(0, len(names), 100):
        chunk = [ymap[t] for t in names[k: k + 100]]
        d = yf.download(chunk + (["SPY"] if k == 0 else []), start=str(START.date()),
                        end=str((END + pd.Timedelta(days=1)).date()), auto_adjust=True, progress=False,
                        threads=True)["Close"]
        frames.append(d)
        print(f"  {k + len(chunk)}/{len(names)}", flush=True)
    px = pd.concat(frames, axis=1)
    px = px.loc[:, ~px.columns.duplicated()]
    px = px.rename(columns={v: k for k, v in ymap.items()})
    px = px[px.index <= END]
    px.to_parquet(PX)
    have = px.notna().any().sum()
    print(f"prices for {have} of {len(names)} names ever in the index since {START.date()}")


def build():
    px = pd.read_parquet(PX)
    px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
    assert px.index.max() <= END
    spy = px.pop("SPY")
    S = px.index
    mem = membership().reindex(S, method="ffill")
    names = list(px.columns)
    elig = np.array([[t in s for t in names] for s in mem.values])
    close = px.values
    lp = np.log(px)
    r = px.pct_change().values
    rm = spy.pct_change().values
    sig = {"mom12_1": (lp.shift(20) - lp.shift(252)).values, "rev1m": -(lp - lp.shift(20)).values,
           "rev1w": -(lp - lp.shift(5)).values,
           "lowvol": -np.log(px).diff().rolling(60, min_periods=50).std().values,
           "high52": (px / px.rolling(252, min_periods=200).max()).values}
    spec = json.load(open(os.path.join(ROOT, "artefacts", "llm", "ridge_stocks.json")))
    Z = np.stack([sig[c] for c in spec["features"]], -1)
    Z[~elig] = np.nan
    Z = (Z - np.nanmean(Z, 1, keepdims=True)) / np.nanstd(Z, 1, keepdims=True)
    frozen = Z @ np.asarray(spec["coef"])
    # shrunk Welch beta (fund/backtest_levels.py) over 252 sessions to d
    lo, hi = np.minimum(-2 * rm, 4 * rm)[:, None], np.maximum(-2 * rm, 4 * rm)[:, None]
    w = pd.DataFrame(np.clip(r, lo, hi), index=S)
    m = pd.Series(rm, index=S)
    beta = (2 / 3) * w.rolling(252, min_periods=200).cov(m).div(m.rolling(252, min_periods=200).var(), axis=0) \
        .fillna(1.0).values + 1 / 3
    cr = np.vstack([np.zeros((1, r.shape[1])), np.cumsum(np.nan_to_num(r), 0)])
    cm = np.concatenate([[0], np.cumsum(np.nan_to_num(rm))])

    def resid(h):
        y = np.full(r.shape, np.nan)
        for d in range(len(S) - 1 - h):
            a, b = d + 2, d + 2 + h
            y[d] = (cr[b] - cr[a]) - beta[d] * (cm[b] - cm[a])
        valid = np.isfinite(close)
        ok = np.zeros_like(valid)
        ok[: len(S) - 1 - h] = valid[1 + h:] & valid[: len(S) - 1 - h]
        y[~(ok & elig)] = np.nan
        return y - np.nanmean(y, 1, keepdims=True)
    # daily residual return e_t = r_t - beta_{t-1} r_SPY,t (beta known the session before); for the sequence models
    e = r - np.vstack([np.full((1, r.shape[1]), np.nan), beta[:-1]]) * rm[:, None]
    return {"S": S, "names": names, "Z": Z.astype(np.float32), "frozen": frozen, "y20": resid(H), "y5": resid(5),
            "y10": resid(10), "elig": elig, "e": e.astype(np.float32), "spy": spy.values, "rm": rm,
            "valid": np.isfinite(close)}


def _ic_rows(pred, y, idx):
    return F.weekly_ic(pred, y, idx)


def refit_predictions(d):
    S, Z, y = d["S"], d["Z"], d["y20"]
    pred = np.full(y.shape, np.nan)
    alphas = []
    qstarts = [i for i in range(1, len(S)) if S[i].quarter != S[i - 1].quarter and S[i].year >= 2013]
    qstarts.append(len(S))
    t0 = int(np.searchsorted(S, TRAIN0))
    for qa, qb in zip(qstarts[:-1], qstarts[1:]):
        train = np.arange(t0, qa)
        train = train[train + 1 + H < qa]
        cut = int(len(train) * 0.8)
        tr, va = train[: cut - H - 1], train[cut:]

        def rows(idx):
            X, yy = Z[idx].reshape(-1, Z.shape[-1]), y[idx].reshape(-1)
            k = np.isfinite(yy) & np.isfinite(X).all(1)
            return X[k], yy[k]
        Xt, yt = rows(tr)
        vth = va[S[va].weekday == 3]
        best, bs = None, -np.inf
        for a in ALPHAS:
            m = Ridge(alpha=a).fit(Xt, yt)
            pv = np.full(y.shape, np.nan)
            pv[vth] = np.where(np.isfinite(Z[vth]).all(-1), m.predict(np.nan_to_num(Z[vth]).reshape(-1, Z.shape[-1]))
                               .reshape(len(vth), -1), np.nan)
            s = np.nanmean(_ic_rows(pv, y, vth))
            if s > bs:
                best, bs = a, s
        m = Ridge(alpha=best).fit(*rows(train))
        test = np.arange(qa, qb)
        pt = m.predict(np.nan_to_num(Z[test]).reshape(-1, Z.shape[-1])).reshape(len(test), -1)
        pred[test] = np.where(np.isfinite(Z[test]).all(-1), pt, np.nan)
        alphas.append(best)
    return pred, alphas


def decile_net(pred, y5, idx, cost_bp=10.0):
    out, prev = [], None
    for dd in idx:
        k = np.isfinite(pred[dd]) & np.isfinite(y5[dd])
        w = np.zeros(pred.shape[1])
        if k.sum() >= 50:
            q = pd.Series(pred[dd][k]).rank(pct=True).values
            ix = np.where(k)[0]
            lo, hi = ix[q <= 0.1], ix[q > 0.9]
            if len(lo) and len(hi):
                w[hi], w[lo] = 1 / len(hi), -1 / len(lo)
        g = float(np.nansum(w * np.nan_to_num(y5[dd])))
        c = 0.0 if prev is None else cost_bp * 1e-4 * np.abs(w - prev).sum()
        out.append(g - c)
        prev = w
    return np.array(out)


def signed_off():
    rel = os.path.relpath(PREREG, ROOT)
    txt = open(PREREG).read()
    if "Owner sign-off:** _pending_" in txt:
        sys.exit("pre-registration not signed off")
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=ROOT).returncode:
        sys.exit("pre-registration has uncommitted changes")
    sha = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", rel], cwd=ROOT, text=True).strip()
    if not subprocess.check_output(["git", "branch", "-r", "--contains", sha], cwd=ROOT, text=True).strip():
        sys.exit("pre-registration commit is not pushed")
    if os.path.exists(OUT):
        sys.exit("SP500.md exists: the read has been made")
    return sha


def run():
    sha = signed_off()
    d = build()
    S = d["S"]
    pred, alphas = refit_predictions(d)
    rows, ics, fics, nets, neu = [], {}, {}, {}, {}
    meta = pd.read_csv(os.path.join(ROOT, "data", "raw", "stocks", "sp500_current.csv")).set_index("Symbol")
    sector = np.array([meta["GICS Sector"].get(t, "unknown") for t in d["names"]])
    for fy in range(2013, 2026):
        yrs = np.where(S.year == fy)[0]
        yrs = yrs[yrs + 1 + H <= yrs[-1]]
        wk = yrs[S[yrs].weekday == 3]
        y = d["y20"].copy()
        y[yrs[-1] + 1:] = np.nan
        ics[fy] = _ic_rows(pred, y, wk)
        fics[fy] = _ic_rows(d["frozen"], y, wk)
        nets[fy] = decile_net(pred, d["y5"], wk)
        neu[fy] = _ic_rows(F.neutralise(pred, sector), F.neutralise(y, sector), wk)
        rows.append({"year": fy, "names_with_data": int(np.isfinite(d["Z"][wk]).all(-1).sum(1).mean()),
                     "ic": np.nanmean(ics[fy]), "frozen_ic_in_sample": np.nanmean(fics[fy]),
                     "sector_neutral_ic": np.nanmean(neu[fy]), "net_decile_bp_wk": np.nanmean(nets[fy]) * 1e4})
    cat = lambda dct, ys: np.concatenate([dct[y_] for y_ in ys])
    allY = range(2013, 2026)
    ic = cat(ics, allY)
    t = F.nw_t(ic, 4)
    p = float(stats.norm.sf(t))
    res = {"ic": np.nanmean(ic), "t": t, "p": p,
           "ic_2013_19": np.nanmean(cat(ics, range(2013, 2020))), "ic_2020_25": np.nanmean(cat(ics, range(2020, 2026))),
           "ic_2022": np.nanmean(ics[2022]), "net_decile_bp_wk": np.nanmean(cat(nets, allY)) * 1e4,
           "ic_2022_25": np.nanmean(cat(ics, range(2022, 2026))), "t_2022_25": F.nw_t(cat(ics, range(2022, 2026)), 4),
           "frozen_ic_in_sample": np.nanmean(cat(fics, allY)), "sector_neutral_ic": np.nanmean(cat(neu, allY))}
    res["pass"] = bool(p < 0.05 and res["ic_2013_19"] > 0 and res["ic_2020_25"] > 0 and res["ic_2022"] >= 0
                       and res["net_decile_bp_wk"] > 0)
    yr = pd.DataFrame(rows)
    yr.to_csv(os.path.join(P.REPORT, "sp500_years.csv"), index=False)
    with open(OUT, "w") as f:
        f.write(f"# S&P 500 test of the refit five-factor model (pre-registration `{sha}`)\n\n")
        f.write("| statistic | value |\n|---|---|\n" + "".join(f"| {k} | {v:.4f} |\n" if isinstance(v, float)
                                                           else f"| {k} | {v} |\n" for k, v in res.items()))
        f.write(f"\nRidge alphas chosen per quarter: {pd.Series(alphas).value_counts().to_dict()}\n\n")
        f.write(yr.round(4).to_markdown(index=False) + "\n")
    print(json.dumps(res, default=float, indent=1))
    print(yr.round(4).to_string(index=False))


if __name__ == "__main__":
    {"data": download, "run": run}[sys.argv[1]]()
