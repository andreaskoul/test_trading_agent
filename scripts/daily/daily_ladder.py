"""Daily-horizon ladder, as pre-registered in reports/research/PROTOCOL_daily.md
(+ Amendment 1).

    python scripts/daily/daily_ladder.py   # -> reports/research/daily/
"""

from __future__ import annotations

import os
import warnings

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", message="Converting to PeriodArray")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "data", "raw", "daily")
OUT = os.path.join(ROOT, "reports", "research", "daily")
os.makedirs(OUT, exist_ok=True)

DEV = ("2006-06-13", "2018-12-31")
HOLD = ("2019-01-01", "2026-03-31")
HORIZONS = (1, 5)
RULES = ("tsmom12", "tsmom1", "realrate", "dollar", "cot", "ridge", "gbm")
N_TRIALS = len(RULES) * len(HORIZONS)
COSTS_BP = (1.0, 2.0, 4.0)
MAIN_COST = 2.0
N_COIN, K, EMBARGO = 500, 8, 5
EULER = 0.5772156649
FEATS = ["ret_5", "ret_20", "ret_60", "ret_250", "rv_20", "dry_5", "dry_20", "dbe_5", "dbe_20",
         "dxy_5", "dxy_20", "vix_5", "vix_20", "cot_z", "cot_d4"]
SHUTDOWNS = [("2013-09-24", "2013-11-26", "2013-12-30"),
             ("2018-12-18", "2019-02-26", "2019-03-11"),
             ("2025-09-30", "2025-12-16", "2025-12-29")]

# ---------------------------------------------------------------- data
gc = pd.read_parquet(os.path.join(RAW, "gc.parquet"))
cal = gc.index
close = gc["close"]


def on_calendar(s: pd.Series, available: pd.DatetimeIndex) -> pd.Series:
    """Re-stamp s at its availability dates and forward-fill onto the gold
    calendar. A value is visible on calendar day t only if available <= t."""
    s = pd.Series(s.to_numpy(), index=available).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(cal.union(s.index)).ffill().reindex(cal)


def fred(name):
    s = pd.read_parquet(os.path.join(RAW, f"{name}.parquet")).iloc[:, 0]
    return on_calendar(s, s.index + BDay(1))


dfii, t10ye, vix = fred("dfii10"), fred("t10yie"), fred("vixcls")
dxy_raw = pd.read_parquet(os.path.join(RAW, "dxy.parquet"))["close"]
dxy = on_calendar(dxy_raw, dxy_raw.index + BDay(1))

cot = pd.read_parquet(os.path.join(RAW, "cot_gold.parquet"))
net = (cot.mm_long - cot.mm_short) / cot.oi
cot_z_rep = (net - net.rolling(156, min_periods=156).mean()) / net.rolling(156, min_periods=156).std()
cot_d4_rep = net - net.shift(4)
avail = pd.Series(cot.index + pd.Timedelta(days=7), index=cot.index)   # Amendment 2
for a, b, rel in SHUTDOWNS:
    m = (cot.index >= a) & (cot.index <= b)
    avail[m] = np.maximum(avail[m], pd.Timestamp(rel))
cot_z = on_calendar(cot_z_rep, pd.DatetimeIndex(avail.values))
cot_d4 = on_calendar(cot_d4_rep, pd.DatetimeIndex(avail.values))

lc = np.log(close)
F = pd.DataFrame(index=cal)
for k in (5, 20, 60, 250):
    F[f"ret_{k}"] = lc - lc.shift(k)
F["rv_20"] = lc.diff().rolling(20).std()
for k in (5, 20):
    F[f"dry_{k}"] = dfii - dfii.shift(k)
    F[f"dbe_{k}"] = t10ye - t10ye.shift(k)
    F[f"dxy_{k}"] = np.log(dxy) - np.log(dxy.shift(k))
    F[f"vix_{k}"] = np.log(vix) - np.log(vix.shift(k))
F["cot_z"], F["cot_d4"] = cot_z, cot_d4

R = close.pct_change()                      # day-u return, close u-1 -> close u
n = len(cal)


def fwd(H):
    # return earned by a position set at close t+1 and held H days
    return close.shift(-(1 + H)) / close.shift(-1) - 1


# ---------------------------------------------------------------- helpers
def nw_t(x, L):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    e = x - x.mean(); s = e @ e / len(x)
    for k in range(1, min(L, len(x) - 1) + 1):
        s += 2 * (1 - k / (L + 1)) * (e[k:] @ e[:-k]) / len(x)
    return x.mean() / np.sqrt(s / len(x))


def alpha_t(y, x, L):
    ok = ~(np.isnan(y) | np.isnan(x)); y, x = y[ok], x[ok]
    X = np.column_stack([np.ones(len(x)), x])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    XtX = np.linalg.inv(X.T @ X)
    S = (X * e[:, None]).T @ (X * e[:, None]) / len(y)
    for k in range(1, L + 1):
        G = (X[k:] * e[k:, None]).T @ (X[:-k] * e[:-k, None]) / len(y)
        S += (1 - k / (L + 1)) * (G + G.T)
    V = len(y) * XtX @ S @ XtX
    return b[0], b[0] / np.sqrt(V[0, 0]), b[1]


def psr(x, sr0=0.0):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    sr = x.mean() / x.std(ddof=1)
    g3, g4 = stats.skew(x), stats.kurtosis(x, fisher=False)
    return float(stats.norm.cdf((sr - sr0) * np.sqrt(len(x) - 1) / np.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2, 1e-12))))


def pnl(signal: pd.Series, H: int, cost_bp: float, mask: np.ndarray):
    """Daily net returns inside mask. Position set at close t+1 from signal t;
    H overlapping tranches; cost on turnover."""
    s = signal.where(mask).fillna(0.0)
    pos = s.rolling(H, min_periods=1).mean().shift(1)          # set at close t+1
    ret = pos.shift(1) * R                                       # earned on the next day
    cost = cost_bp / 1e4 * pos.diff().abs()
    out = (ret - cost.shift(1).fillna(0.0))
    return out[mask], pos


def monthly_ic(score, y, mask):
    df = pd.DataFrame({"s": score, "y": y})[mask].dropna()
    df = df[df.s != 0]
    ic = df.groupby(df.index.to_period("M")).apply(
        lambda g: stats.spearmanr(g.s, g.y)[0] if g.s.nunique() > 1 and len(g) > 8 else np.nan).dropna()
    return ic.mean(), nw_t(ic.to_numpy(), 3), len(ic)


def fit_predict(rule, tr, te, H):
    y = fwd(H)
    if rule == "tsmom12":
        return np.sign(F["ret_250"])[te]
    if rule == "tsmom1":
        return np.sign(F["ret_20"])[te]
    if rule == "realrate":
        return np.sign(-F["dry_20"])[te]
    if rule == "dollar":
        return np.sign(-F["dxy_20"])[te]
    if rule == "cot":
        z = F["cot_z"]
        return (-np.sign(z) * (z.abs() > 1)).where(z.notna())[te]
    Xtr, ytr = F.loc[tr, FEATS], y[tr]
    ok = ytr.notna() & (Xtr.notna().all(1) if rule == "ridge" else True)
    Xtr, ytr = Xtr[ok], ytr[ok]
    Xte = F.loc[te, FEATS]
    if rule == "ridge":
        sc = StandardScaler().fit(Xtr)
        m = Ridge(alpha=10.0).fit(sc.transform(Xtr), ytr)
        okte = Xte.notna().all(1)
        p = pd.Series(np.nan, index=Xte.index)
        p[okte] = m.predict(sc.transform(Xte[okte]))
        return p
    m = HistGradientBoostingRegressor(max_depth=3, max_iter=200, learning_rate=0.05, random_state=0).fit(Xtr, ytr)
    return pd.Series(m.predict(Xte), index=Xte.index)


# ---------------------------------------------------------------- run
dev_m = (cal >= DEV[0]) & (cal <= DEV[1])
hold_m = (cal >= HOLD[0]) & (cal <= HOLD[1])
rows, daily = [], {}
rng = np.random.default_rng(0)
coin_sr = {}
for H in HORIZONS:
    y = fwd(H)
    dev_idx = np.where(dev_m)[0]
    folds = np.array_split(dev_idx, K)
    for rule in RULES:
        score = pd.Series(np.nan, index=cal)
        for f in folds:
            lo, hi = f[0] - (H + 1) - EMBARGO, f[-1] + (H + 1) + EMBARGO
            tr_i = dev_idx[(dev_idx < lo) | (dev_idx > hi)]
            score.iloc[f] = fit_predict(rule, cal[tr_i], cal[f], H).to_numpy()
        score[hold_m] = fit_predict(rule, cal[dev_m], cal[hold_m], H).to_numpy()
        sig = np.sign(score)
        for split, m in (("dev_oof", dev_m), ("holdout", hold_m)):
            valid = m & score.notna().to_numpy()
            for c in COSTS_BP:
                r, pos = pnl(sig, H, c, valid)
                r = r.dropna()
                if c == MAIN_COST:
                    daily[(H, rule, split)] = r
                a, at, beta = alpha_t(r.to_numpy(), R[r.index].to_numpy(), H + 5)
                ic, ic_t, n_m = monthly_ic(score, y, valid)
                rows.append(dict(H=H, rule=rule, split=split, cost_bp=c, start=str(r.index.min().date()),
                                 days=len(r), ann_ret=r.mean() * 252, ann_vol=r.std() * np.sqrt(252),
                                 sharpe=r.mean() / r.std() * np.sqrt(252), t_nw=nw_t(r.to_numpy(), H + 5),
                                 alpha_ann=a * 252, alpha_t=at, beta=beta, psr0=psr(r.to_numpy()),
                                 long_frac=float((pos[r.index] > 0).mean()),
                                 turnover_ann=float(pos.diff().abs()[r.index].sum() / len(r) * 252),
                                 ic=ic, ic_t=ic_t, ic_months=n_m))
    for split, m in (("dev_oof", dev_m), ("holdout", hold_m)):
        srs = []
        for _ in range(N_COIN):
            cs = pd.Series(rng.choice([-1.0, 1.0], size=n), index=cal)
            r, _ = pnl(cs, H, MAIN_COST, m)
            srs.append(r.mean() / r.std() * np.sqrt(252))
        coin_sr[(H, split)] = np.asarray(srs)
        r, _ = pnl(pd.Series(1.0, index=cal), H, MAIN_COST, m)
        rows.append(dict(H=H, rule="always_long", split=split, cost_bp=MAIN_COST, days=len(r),
                         ann_ret=r.mean() * 252, sharpe=r.mean() / r.std() * np.sqrt(252),
                         t_nw=nw_t(r.to_numpy(), H + 5)))
        rows.append(dict(H=H, rule="coin_flip", split=split, cost_bp=MAIN_COST,
                         sharpe=float(np.mean(srs)), coin_sr_sd=float(np.std(srs))))

T = pd.DataFrame(rows)
for split in ("dev_oof", "holdout"):
    m = T[(T.split == split) & T.rule.isin(RULES) & (T.cost_bp == MAIN_COST)]
    sr_d = m.sharpe / np.sqrt(252)
    sr0 = np.sqrt(sr_d.var(ddof=1)) * ((1 - EULER) * stats.norm.ppf(1 - 1 / N_TRIALS)
                                       + EULER * stats.norm.ppf(1 - 1 / (N_TRIALS * np.e)))
    for i in m.index:
        k = (T.at[i, "H"], T.at[i, "rule"], split)
        T.at[i, "dsr"] = psr(daily[k].to_numpy(), sr0)
        T.at[i, "p_vs_coin"] = float((coin_sr[(T.at[i, "H"], split)] >= T.at[i, "sharpe"]).mean())
    T.loc[m.index, "sr_star_ann"] = sr0 * np.sqrt(252)
h = T[(T.split == "holdout") & T.rule.isin(RULES) & (T.cost_bp == MAIN_COST)]
T.loc[h.index, "PASS"] = (h.t_nw > 2) & (h.alpha_t > 2) & (h.dsr > 0.95) & (h.ic_t > 2)
T.to_csv(os.path.join(OUT, "daily_ladder_results.csv"), index=False)
pd.concat({f"{k[0]}_{k[1]}_{k[2]}": v for k, v in daily.items()}, axis=1).to_parquet(
    os.path.join(OUT, "daily_returns.parquet"))
F.to_parquet(os.path.join(OUT, "features.parquet"))
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
cols = ["H", "rule", "split", "start", "days", "ann_ret", "sharpe", "t_nw", "alpha_ann", "alpha_t", "beta",
        "long_frac", "turnover_ann", "ic", "ic_t", "dsr", "p_vs_coin", "PASS"]
print(T[(T.cost_bp == MAIN_COST)][[c for c in cols if c in T]].round(3).to_string())
