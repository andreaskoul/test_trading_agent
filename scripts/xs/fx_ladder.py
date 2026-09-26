"""Cross-sectional FX ladder, as pre-registered in reports/research/PROTOCOL_fx.md
(+ Amendment 1).

    python scripts/xs/fx_ladder.py   # -> reports/research/fx/
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
RAW = os.path.join(ROOT, "data", "raw", "fx")
OUT = os.path.join(ROOT, "reports", "research", "fx")
os.makedirs(OUT, exist_ok=True)

DEV = ("2004-01-01", "2015-12-31")
HOLD = ("2016-01-01", "2026-03-31")
SIGNALS = ("carry", "mom12", "mom3", "mom1", "rev1w", "value", "combo", "ridge")
BASE = ("carry", "mom12", "mom3", "mom1", "rev1w", "value")
HOLDS = (1, 4)
N_TRIALS = len(SIGNALS) * len(HOLDS)
N_COIN, EULER = 500, 0.5772156649
COST_BP = {**{c: 1.0 for c in "EUR JPY GBP CHF AUD NZD CAD SEK NOK".split()},
           **{c: 3.0 for c in "MXN PLN HUF CZK ILS KRW".split()},
           **{c: 6.0 for c in "ZAR CLP".split()}}

spot = pd.read_parquet(os.path.join(RAW, "spot_usd_per_ccy.parquet"))
rates = pd.read_parquet(os.path.join(RAW, "rates_monthly.parquet"))
CCY = list(spot.columns)

# ------------------------------------------------------------------ weekly panel
days = pd.date_range("2003-06-04", "2026-09-24", freq="D")
daily = spot.reindex(days).ffill(limit=3)                 # last print, at most 3 days stale
wed = daily[daily.index.dayofweek == 2]
thu = daily.reindex(wed.index + pd.Timedelta(days=1))
thu.index = wed.index                                     # row w = Thursday after Wednesday w

# accrual: rate of the current month (forward-filled)
m_rates = rates.reindex(pd.date_range(rates.index.min(), "2026-10-01", freq="MS")).ffill()
diff_now = (m_rates[CCY].sub(m_rates["USD"], axis=0))
acc = diff_now.reindex(wed.index, method="ffill") / 52.0
# signal: month m usable from the first day of m+2
diff_sig = diff_now.copy()
diff_sig.index = diff_sig.index + pd.DateOffset(months=2)
carry_sig = diff_sig.reindex(wed.index, method="ffill")

x_wed = np.log(wed).diff() + acc                          # excess return, Wed w-1 -> Wed w
x_thu_fwd = (np.log(thu).shift(-1) - np.log(thu)) + acc.shift(-1)   # Thu w -> Thu w+1, earned by position set at Thu w

S = {
    "carry": carry_sig,
    "mom12": x_wed.shift(4).rolling(48, min_periods=40).sum(),
    "mom3": x_wed.rolling(13, min_periods=11).sum(),
    "mom1": x_wed.rolling(4, min_periods=4).sum(),
    "rev1w": -x_wed,
    "value": -(np.log(wed) - np.log(wed.shift(260))),
}


def xs_z(df):
    return df.sub(df.mean(1), axis=0).div(df.std(1), axis=0)


S["combo"] = pd.concat([xs_z(S[k]) for k in ("carry", "mom12", "value")]).groupby(level=0).mean()
S["combo"] = S["combo"].where(xs_z(S["carry"]).notna() & xs_z(S["mom12"]).notna() & xs_z(S["value"]).notna())

weeks = wed.index
dev_w = (weeks >= DEV[0]) & (weeks <= DEV[1])
hold_w = (weeks >= HOLD[0]) & (weeks <= HOLD[1])

# ridge: pooled on cross-sectional z-scores of the six base signals
Z = {k: xs_z(S[k]) for k in BASE}
y_dm = x_thu_fwd.sub(x_thu_fwd.mean(1), axis=0)
panel = pd.concat({k: Z[k].stack() for k in BASE}, axis=1)
panel["y"] = y_dm.stack()
panel = panel.dropna()
wk = panel.index.get_level_values(0)


def ridge_scores(train_mask_weeks, test_weeks):
    tr = panel[np.isin(wk, train_mask_weeks)]
    m = Ridge(alpha=10.0).fit(tr[list(BASE)], tr["y"])
    X = pd.concat({k: Z[k].stack() for k in BASE}, axis=1).dropna()
    X = X[np.isin(X.index.get_level_values(0), test_weeks)]
    if len(X) == 0 or len(tr) == 0:
        return pd.DataFrame(columns=CCY, dtype=float)
    return pd.Series(m.predict(X[list(BASE)]), index=X.index).unstack()


ridge = pd.DataFrame(np.nan, index=weeks, columns=CCY)
dev_weeks = weeks[dev_w]
for f in np.array_split(np.arange(len(dev_weeks)), 8):
    lo, hi = f[0] - 5, f[-1] + 5
    keep = [i for i in range(len(dev_weeks)) if i < lo or i > hi]
    sc = ridge_scores(dev_weeks[keep], dev_weeks[f])
    ridge.loc[sc.index, sc.columns] = sc
sc = ridge_scores(dev_weeks, weeks[hold_w])
ridge.loc[sc.index, sc.columns] = sc
S["ridge"] = ridge


# ------------------------------------------------------------------ portfolio machinery
def rank_weights(score: pd.DataFrame) -> pd.DataFrame:
    ok = score.notna() & wed.notna() & thu.notna()      # tradable now; never peeks at next week
    r = score.where(ok).rank(axis=1)
    r = r.sub(r.mean(1), axis=0)
    return r.div(r.abs().sum(1), axis=0).mul(2.0).fillna(0.0)


cost_vec = pd.Series(COST_BP)[CCY] / 1e4


def run(weights: pd.DataFrame, H: int, mask, cost_mult=1.0):
    pos = weights.where(pd.Series(mask, index=weeks), 0.0).rolling(H, min_periods=1).mean()
    gross = (pos * x_thu_fwd.fillna(0.0)).sum(1)
    tc = (pos.diff().abs().fillna(pos.abs()) * cost_vec * cost_mult).sum(1)
    net = (gross - tc)[mask]
    return net, pos, tc[mask]


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
    X = np.column_stack([np.ones(len(y)), X])
    b = np.linalg.lstsq(X, y, rcond=None)[0]; e = y - X @ b
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
    sl = []
    for w in weeks[mask]:
        s, y = score.loc[w], x_thu_fwd.loc[w]
        ok = s.notna() & y.notna()
        if ok.sum() < 6:
            continue
        r = s[ok].rank(); r = (r - 1) / (len(r) - 1) - 0.5
        sl.append(np.polyfit(r.to_numpy(), y[ok].to_numpy(), 1)[0])
    sl = np.asarray(sl)
    return sl.mean() * 52, nw_t(sl, 4), len(sl)


# ------------------------------------------------------------------ run
dol = x_thu_fwd.mean(1)
rows, series = [], {}
rng = np.random.default_rng(0)
coin = {}
for H in HOLDS:
    carry_net = {}
    for split, m in (("dev", dev_w), ("holdout", hold_w)):
        carry_net[split] = run(rank_weights(S["carry"]), H, m)[0]
    for sig in SIGNALS:
        W = rank_weights(S[sig])
        for split, m in (("dev", dev_w), ("holdout", hold_w)):
            valid = m & (W.abs().sum(1) > 0).to_numpy()
            net, pos, tc = run(W, H, valid)
            series[(H, sig, split)] = net
            b, t = ols_hac(net.to_numpy(), dol[net.index].to_numpy()[:, None], 4 + H)
            if sig != "carry":
                cn = carry_net[split].reindex(net.index)
                bc, tcarry = ols_hac(net.to_numpy(), np.column_stack([dol[net.index], cn]), 4 + H)
            else:
                bc, tcarry = [np.nan] * 3, [np.nan] * 3
            fm, fm_t, n_fm = fama_macbeth(S[sig], m)
            row = dict(H=H, signal=sig, split=split, start=str(net.index.min().date()), weeks=len(net),
                       ann_ret=net.mean() * 52, ann_vol=net.std() * np.sqrt(52),
                       sharpe=net.mean() / net.std() * np.sqrt(52), t_nw=nw_t(net, 4 + H),
                       alpha_dol_ann=b[0] * 52, alpha_dol_t=t[0], beta_dol=b[1],
                       alpha_dol_carry_t=tcarry[0], beta_carry=bc[2],
                       cost_ann=tc.mean() * 52, turnover_ann=pos.diff().abs().sum(1)[net.index].mean() * 52,
                       fm_spread_ann=fm, fm_t=fm_t, psr0=psr(net))
            for mult in (0.5, 2.0):
                nn, _, _ = run(W, H, valid, mult)
                row[f"sharpe_cost{mult}x"] = nn.mean() / nn.std() * np.sqrt(52)
            rows.append(row)
    for split, m in (("dev", dev_w), ("holdout", hold_w)):
        srs = []
        for _ in range(N_COIN):
            rnd = pd.DataFrame(rng.standard_normal((len(weeks), len(CCY))), index=weeks, columns=CCY)
            nn, _, _ = run(rank_weights(rnd), H, m)
            srs.append(nn.mean() / nn.std() * np.sqrt(52))
        coin[(H, split)] = np.asarray(srs)
        rows.append(dict(H=H, signal="coin", split=split, sharpe=float(np.mean(srs)), coin_sd=float(np.std(srs))))
        d_ = dol[m].dropna()
        rows.append(dict(H=H, signal="DOL (long all vs USD)", split=split, ann_ret=d_.mean() * 52,
                         sharpe=d_.mean() / d_.std() * np.sqrt(52), t_nw=nw_t(d_, 4)))

T = pd.DataFrame(rows)
for split in ("dev", "holdout"):
    m = T[(T.split == split) & T.signal.isin(SIGNALS)]
    v = (m.sharpe / np.sqrt(52)).var(ddof=1)
    sr0 = np.sqrt(v) * ((1 - EULER) * stats.norm.ppf(1 - 1 / N_TRIALS) + EULER * stats.norm.ppf(1 - 1 / (N_TRIALS * np.e)))
    for i in m.index:
        k = (T.at[i, "H"], T.at[i, "signal"], split)
        T.at[i, "dsr"] = psr(series[k].to_numpy(), sr0)
        T.at[i, "p_vs_coin"] = float((coin[(T.at[i, "H"], split)] >= T.at[i, "sharpe"]).mean())
    T.loc[m.index, "sr_star_ann"] = sr0 * np.sqrt(52)
h = T[(T.split == "holdout") & T.signal.isin(SIGNALS)]
T.loc[h.index, "PASS"] = (h.t_nw > 2) & (h.dsr > 0.95) & (h.fm_t > 2) & (h.alpha_dol_t > 2)
T.to_csv(os.path.join(OUT, "fx_ladder_results.csv"), index=False)
pd.concat({f"{k[0]}_{k[1]}_{k[2]}": v for k, v in series.items()}, axis=1).to_parquet(os.path.join(OUT, "fx_weekly_returns.parquet"))
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
cols = ["H", "signal", "split", "start", "weeks", "ann_ret", "sharpe", "t_nw", "alpha_dol_t", "alpha_dol_carry_t",
        "beta_carry", "fm_spread_ann", "fm_t", "cost_ann", "sharpe_cost2.0x", "dsr", "p_vs_coin", "PASS"]
print(T[[c for c in cols if c in T]].round(3).to_string())
