"""Cross-sectional US large-cap ladder, as pre-registered in
reports/research/PROTOCOL_stocks.md.

    python scripts/xs/stock_ladder.py   # -> reports/research/stocks/
"""

from __future__ import annotations

import os
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "data", "raw", "stocks")
OUT = os.path.join(ROOT, "reports", "research", "stocks")
os.makedirs(OUT, exist_ok=True)

DEV = ("2004-01-01", "2015-12-31")
HOLD = ("2016-01-01", "2026-03-31")
SIGNALS = ("mom12_1", "rev1m", "rev1w", "lowvol", "high52", "combo", "ridge")
BASE = ("mom12_1", "rev1m", "rev1w", "lowvol", "high52")
HOLDS = (1, 4)
N_TRIALS = len(SIGNALS) * len(HOLDS)
COST, N_COIN, EULER = 5e-4, 200, 0.5772156649

px = pd.read_parquet(os.path.join(RAW, "prices_adj.parquet")).astype("float64")
mem = pd.read_csv(os.path.join(RAW, "sp500_membership.csv"), parse_dates=["date"]).set_index("date").tickers.str.split(",")
ff = pd.read_parquet(os.path.join(RAW, "ff_daily.parquet"))
TK = list(px.columns)

days = pd.date_range("2003-01-01", "2026-09-25", freq="D")
dailyf = px.reindex(days).ffill(limit=3)
wed = dailyf[dailyf.index.dayofweek == 2]
wed = wed[wed.index >= "2003-01-08"]
thu = dailyf.reindex(wed.index + pd.Timedelta(days=1)); thu.index = wed.index
weeks = wed.index

# point-in-time membership, as of each Wednesday
member = pd.DataFrame(False, index=weeks, columns=TK)
mem_i = mem.reindex(mem.index.union(weeks)).ffill().reindex(weeks)
for w, lst in mem_i.items():
    if isinstance(lst, list):
        member.loc[w, [t for t in lst if t in member.columns]] = True
n_members = mem_i.map(lambda x: len(x) if isinstance(x, list) else np.nan)
elig = member & wed.notna() & thu.notna()
coverage = elig.sum(1) / n_members

lr_d = np.log(px).diff()
vol60 = lr_d.rolling(60, min_periods=50).std()
hi252 = px.rolling(252, min_periods=200).max()
lw = np.log(wed)
S = {
    "mom12_1": lw.shift(4) - lw.shift(52),
    "rev1m": -(lw - lw.shift(4)),
    "rev1w": -(lw - lw.shift(1)),
    "lowvol": -vol60.reindex(days).ffill(limit=3).reindex(weeks),
    "high52": wed / hi252.reindex(days).ffill(limit=3).reindex(weeks),
}
S = {k: v.where(elig) for k, v in S.items()}
fwd = (thu.shift(-1) / thu - 1)                      # Thu w -> Thu w+1


def xs_z(df):
    return df.sub(df.mean(1), axis=0).div(df.std(1), axis=0)


Z = {k: xs_z(S[k]) for k in BASE}
S["combo"] = pd.concat([Z[k] for k in ("mom12_1", "rev1m", "lowvol")]).groupby(level=0).mean()
S["combo"] = S["combo"].where(Z["mom12_1"].notna() & Z["rev1m"].notna() & Z["lowvol"].notna())
dev_w = (weeks >= DEV[0]) & (weeks <= DEV[1])
hold_w = (weeks >= HOLD[0]) & (weeks <= HOLD[1])

y_dm = fwd.where(elig).sub(fwd.where(elig).mean(1), axis=0)
X_all = pd.concat({k: Z[k].stack() for k in BASE}, axis=1).dropna()
panel = X_all.join(y_dm.stack().rename("y"), how="inner").dropna()
pw = panel.index.get_level_values(0)
xw = X_all.index.get_level_values(0)


def ridge_scores(train_weeks, test_weeks):
    tr = panel[pw.isin(train_weeks)]
    Xt = X_all[xw.isin(test_weeks)]
    if len(tr) == 0 or len(Xt) == 0:
        return pd.DataFrame(columns=TK, dtype=float)
    m = Ridge(alpha=10.0).fit(tr[list(BASE)], tr["y"])
    return pd.Series(m.predict(Xt[list(BASE)]), index=Xt.index).unstack()


ridge = pd.DataFrame(np.nan, index=weeks, columns=TK)
dev_weeks = weeks[dev_w]
for f in np.array_split(np.arange(len(dev_weeks)), 8):
    keep = [i for i in range(len(dev_weeks)) if i < f[0] - 5 or i > f[-1] + 5]
    sc = ridge_scores(dev_weeks[keep], dev_weeks[f]); ridge.loc[sc.index, sc.columns] = sc
sc = ridge_scores(dev_weeks, weeks[hold_w]); ridge.loc[sc.index, sc.columns] = sc
S["ridge"] = ridge.where(elig)


def rank_weights(score):
    r = score.where(elig).rank(axis=1)
    r = r.sub(r.mean(1), axis=0)
    return r.div(r.abs().sum(1), axis=0).mul(2.0).fillna(0.0)


fwd0 = fwd.fillna(0.0)                                 # a position with no next price exits flat


def run(W, H, mask, cost=COST):
    pos = W.where(pd.Series(mask, index=weeks), 0.0).rolling(H, min_periods=1).mean()
    gross = (pos * fwd0).sum(1)
    tc = pos.diff().abs().fillna(pos.abs()).sum(1) * cost
    return (gross - tc)[mask], pos, tc[mask]


def nw_t(x, L):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 5 or x.std() == 0:
        return np.nan
    e = x - x.mean(); s = e @ e / len(x)
    for k in range(1, min(L, len(x) - 1) + 1):
        s += 2 * (1 - k / (L + 1)) * (e[k:] @ e[:-k]) / len(x)
    return x.mean() / np.sqrt(s / len(x))


def ols_hac(y, X, L):
    ok = ~(np.isnan(y) | np.isnan(X).any(1)); y, X = y[ok], X[ok]
    X = np.column_stack([np.ones(len(y)), X]); b = np.linalg.lstsq(X, y, rcond=None)[0]; e = y - X @ b
    XtX = np.linalg.inv(X.T @ X); Sg = (X * e[:, None]).T @ (X * e[:, None]) / len(y)
    for k in range(1, L + 1):
        G = (X[k:] * e[k:, None]).T @ (X[:-k] * e[:-k, None]) / len(y); Sg += (1 - k / (L + 1)) * (G + G.T)
    V = len(y) * XtX @ Sg @ XtX
    return b, b / np.sqrt(np.diag(V))


def psr(x, sr0=0.0):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    sr = x.mean() / x.std(ddof=1); g3, g4 = stats.skew(x), stats.kurtosis(x, fisher=False)
    return float(stats.norm.cdf((sr - sr0) * np.sqrt(len(x) - 1) / np.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2, 1e-12))))


def fama_macbeth(score, mask):
    s = score.where(elig & fwd.notna())[mask]
    r = s.rank(axis=1); n = r.count(1)
    r = r.sub(1).div(n - 1, axis=0) - 0.5
    y = fwd.where(s.notna())[mask]
    rc = r.sub(r.mean(1), axis=0); yc = y.sub(y.mean(1), axis=0)
    sl = ((rc * yc).sum(1) / (rc ** 2).sum(1))[n >= 50]
    return sl.mean() * 52, nw_t(sl.to_numpy(), 4)


# weekly FF factors on the Thu -> Thu window
ffw = (1 + ff).groupby(np.searchsorted(weeks + pd.Timedelta(days=1), ff.index, side="left")).prod() - 1
ffw = ffw[(ffw.index > 0) & (ffw.index < len(weeks))]
ffw.index = weeks[ffw.index - 1]                         # window (Thu w-1, Thu w] -> label w-1 (the week it is earned)
FAC = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
mkt_ew = fwd.where(elig).mean(1)

rows, series, coin = [], {}, {}
rng = np.random.default_rng(0)
for H in HOLDS:
    for sig in SIGNALS:
        W = rank_weights(S[sig])
        for split, m in (("dev", dev_w), ("holdout", hold_w)):
            valid = m & (W.abs().sum(1) > 0).to_numpy()
            net, pos, tc = run(W, H, valid)
            series[(H, sig, split)] = net
            b, t = ols_hac(net.to_numpy(), mkt_ew[net.index].to_numpy()[:, None], 4 + H)
            F_ = ffw.reindex(net.index)[FAC].to_numpy()
            bf, tf = ols_hac(net.to_numpy(), F_, 4 + H)
            fm, fm_t = fama_macbeth(S[sig], m)
            row = dict(H=H, signal=sig, split=split, start=str(net.index.min().date()), weeks=len(net),
                       ann_ret=net.mean() * 52, ann_vol=net.std() * np.sqrt(52),
                       sharpe=net.mean() / net.std() * np.sqrt(52), t_nw=nw_t(net, 4 + H),
                       alpha_mkt_ann=b[0] * 52, alpha_mkt_t=t[0], beta_mkt=b[1],
                       alpha_ff6_ann=bf[0] * 52, alpha_ff6_t=tf[0],
                       **{f"b_{f}": v for f, v in zip(FAC, bf[1:])},
                       cost_ann=tc.mean() * 52, fm_spread_ann=fm, fm_t=fm_t, psr0=psr(net),
                       coverage_median=float(coverage[net.index].median()))
            for c in (2.5e-4, 1e-3):
                nn, _, _ = run(W, H, valid, c)
                row[f"sharpe_{c * 1e4:g}bp"] = nn.mean() / nn.std() * np.sqrt(52)
            v90 = valid & (coverage >= 0.9).to_numpy()
            if v90.sum() > 52:
                nn, _, _ = run(W, H, v90)
                row["sharpe_cov90"], row["t_cov90"], row["weeks_cov90"] = nn.mean() / nn.std() * np.sqrt(52), nw_t(nn, 4 + H), int(v90.sum())
            rows.append(row)
    for split, m in (("dev", dev_w), ("holdout", hold_w)):
        srs = []
        for _ in range(N_COIN):
            rnd = pd.DataFrame(rng.standard_normal(wed.shape), index=weeks, columns=TK)
            nn, _, _ = run(rank_weights(rnd), H, m)
            srs.append(nn.mean() / nn.std() * np.sqrt(52))
        coin[(H, split)] = np.asarray(srs)
        rows.append(dict(H=H, signal="coin", split=split, sharpe=float(np.mean(srs)), coin_sd=float(np.std(srs))))

T = pd.DataFrame(rows)
for split in ("dev", "holdout"):
    m = T[(T.split == split) & T.signal.isin(SIGNALS)]
    v = (m.sharpe / np.sqrt(52)).var(ddof=1)
    sr0 = np.sqrt(v) * ((1 - EULER) * stats.norm.ppf(1 - 1 / N_TRIALS) + EULER * stats.norm.ppf(1 - 1 / (N_TRIALS * np.e)))
    for i in m.index:
        T.at[i, "dsr"] = psr(series[(T.at[i, "H"], T.at[i, "signal"], split)].to_numpy(), sr0)
        T.at[i, "p_vs_coin"] = float((coin[(T.at[i, "H"], split)] >= T.at[i, "sharpe"]).mean())
    T.loc[m.index, "sr_star_ann"] = sr0 * np.sqrt(52)
h = T[(T.split == "holdout") & T.signal.isin(SIGNALS)]
T.loc[h.index, "PASS"] = (h.t_nw > 2) & (h.dsr > 0.95) & (h.fm_t > 2) & (h.alpha_mkt_t > 2)
T.to_csv(os.path.join(OUT, "stock_ladder_results.csv"), index=False)
coverage.to_frame("coverage").to_parquet(os.path.join(OUT, "coverage.parquet"))
pd.concat({f"{k[0]}_{k[1]}_{k[2]}": v for k, v in series.items()}, axis=1).to_parquet(os.path.join(OUT, "stock_weekly_returns.parquet"))
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40)
cols = ["H", "signal", "split", "sharpe", "t_nw", "alpha_mkt_t", "beta_mkt", "alpha_ff6_t", "b_Mom", "fm_t",
        "cost_ann", "sharpe_10bp", "sharpe_cov90", "t_cov90", "coverage_median", "dsr", "p_vs_coin", "PASS"]
print(T[[c for c in cols if c in T]].round(3).to_string())
