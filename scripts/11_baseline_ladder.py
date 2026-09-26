"""Baseline ladder, as pre-registered in reports/research/PROTOCOL.md.

    python scripts/11_baseline_ladder.py            # -> reports/research/ladder_*.{json,csv}

Everything here is fixed by the protocol: two horizons, six rules, no
hyperparameter search. Run order: out-of-fold on dev (purged 8-fold), then
one refit on all of dev and a single pass over the holdout.
"""

from __future__ import annotations

import json
import os
import warnings
import sys

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data.features import feature_columns
from src.env.fills import check_exit, open_trade

warnings.filterwarnings("ignore", message="Converting to PeriodArray")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "reports", "research")
os.makedirs(OUT, exist_ok=True)
UP, DN, SEQ, K = 1.5, 0.75, 32, 8
HORIZONS = (4, 26)
RULES = ("tod", "mom", "rev", "trend", "ridge", "gbm")
N_TRIALS = len(RULES) * len(HORIZONS)
N_COIN = 200
EULER = 0.5772156649

dev = pd.read_parquet(os.path.join(ROOT, "data/processed/features_gc_extended.parquet"))
hold = pd.read_parquet(os.path.join(ROOT, "data/processed/features_gc_extended_holdout.parquet"))
FEATS = feature_columns(dev)


def outcomes(df: pd.DataFrame, H: int):
    """Net and gross bracket outcome, and exit bar, for long (col 0) and short
    (col 1) signalled at every bar. Vectorised version of fills.check_exit."""
    o, h, l, c, a = (df[k].to_numpy(np.float64) for k in ("open", "high", "low", "close", "atr"))
    n = len(c)
    rv = pd.Series(a / c)
    vq = rv.expanding().rank(pct=True).to_numpy()
    cost = 2 * 0.5e-4 + 2 * 0.3e-4 * np.maximum(0.1, vq)
    gross = np.full((n, 2), np.nan)
    exit_j = np.full((n, 2), -1, dtype=np.int64)
    idx = np.arange(n - H - 1)
    entry = o[idx + 1]
    for s, d in enumerate((1, -1)):
        tp, sl = entry + d * UP * a[idx], entry - d * DN * a[idx]
        done = np.zeros(len(idx), bool)
        px = np.full(len(idx), np.nan)
        ej = np.full(len(idx), -1)
        for k in range(1, H + 1):
            j = idx + k
            first = k == 1
            s_hit = ~done & ((l[j] <= sl) if d > 0 else (h[j] >= sl))
            s_gap = s_hit & (~first) & (d * (o[j] - sl) <= 0)
            px[s_hit] = np.where(s_gap[s_hit], o[j][s_hit], sl[s_hit])
            ej[s_hit] = j[s_hit]
            done |= s_hit
            t_hit = ~done & ((h[j] >= tp) if d > 0 else (l[j] <= tp))
            t_gap = t_hit & (~first) & (d * (o[j] - tp) >= 0)
            px[t_hit] = np.where(t_gap[t_hit], o[j][t_hit], tp[t_hit])
            ej[t_hit] = j[t_hit]
            done |= t_hit
        px[~done] = c[idx + H][~done]
        ej[~done] = (idx + H)[~done]
        gross[idx, s] = d * (px / entry - 1)
        exit_j[idx, s] = ej
    return gross - cost[:, None], gross, exit_j, cost


def check_against_reference(df, H, gross, ex, n_check=300, seed=0):
    """Spot-check the vectorised outcomes against src/env/fills.py."""
    o, h, l, c, a = (df[k].to_numpy(np.float64) for k in ("open", "high", "low", "close", "atr"))
    rng = np.random.default_rng(seed)
    for i in rng.integers(0, len(c) - H - 2, n_check):
        for s_, d in enumerate((1, -1)):
            entry, tp, sl = open_trade(i, d, c, a, o, UP, DN, "bracket")
            for j in range(i + 1, len(c)):
                hit = check_exit(j, i, d, tp, sl, H, o, h, l, c, "bracket")
                if hit:
                    break
            assert j == ex[i, s_], (i, s_, j, ex[i, s_])
            assert abs(d * (hit[1] / entry - 1) - gross[i, s_]) < 1e-12, (i, s_)


def trade(side: np.ndarray, net: np.ndarray, ex: np.ndarray, start: int = SEQ):
    """Sequential, one position at a time; next decision on the bar after exit."""
    rets, ent = [], []
    i, n = start, len(side)
    while i < n:
        s = side[i]
        if s == 0 or np.isnan(net[i, 0]):
            i += 1
            continue
        k = 0 if s > 0 else 1
        rets.append(net[i, k]); ent.append(i)
        i = ex[i, k] + 1
    return np.asarray(rets), np.asarray(ent, dtype=np.int64)


def nw_t(x, L=5):
    x = np.asarray(x, float)
    if len(x) < 3 or x.std() == 0:
        return np.nan
    e = x - x.mean(); s = e @ e / len(x)
    for k in range(1, min(L, len(x) - 1) + 1):
        s += 2 * (1 - k / (L + 1)) * (e[k:] @ e[:-k]) / len(x)
    return x.mean() / np.sqrt(s / len(x))


def psr(x, sr0=0.0):
    x = np.asarray(x, float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return np.nan
    sr = x.mean() / x.std(ddof=1)
    g3, g4 = stats.skew(x), stats.kurtosis(x, fisher=False)
    den = 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2
    return float(stats.norm.cdf((sr - sr0) * np.sqrt(len(x) - 1) / np.sqrt(max(den, 1e-12))))


def monthly_ic(score, realised, index):
    df = pd.DataFrame({"s": score, "r": realised}, index=index).dropna()
    df = df[df.s.ne(0)] if set(np.unique(df.s)) <= {-1.0, 0.0, 1.0} else df
    ic = df.groupby(df.index.to_period("M")).apply(
        lambda g: stats.spearmanr(g.s, g.r)[0] if g.s.nunique() > 1 and len(g) > 20 else np.nan).dropna()
    return float(ic.mean()), float(nw_t(ic.to_numpy(), L=3)), int(len(ic))


def fit_predict(rule, Xtr, Ytr, hours_tr, Xte, hours_te, fte):
    """Return (score, side) for the test rows. score = predicted long - short."""
    if rule == "mom":
        sc = np.sign(fte["ret_50"].to_numpy()); return sc, sc
    if rule == "rev":
        sc = -np.sign(fte["ret_5"].to_numpy()); return sc, sc
    if rule == "trend":
        sc = np.sign(fte["ema_200_dist"].to_numpy()); return sc, sc
    if rule == "tod":
        m = pd.DataFrame(Ytr, columns=["L", "S"]).groupby(hours_tr).mean()
        L = m["L"].reindex(hours_te).to_numpy(); S = m["S"].reindex(hours_te).to_numpy()
        side = np.where(np.maximum(L, S) <= 0, 0, np.where(L >= S, 1, -1))
        return L - S, side
    sc_ = StandardScaler().fit(Xtr)
    A, B = sc_.transform(Xtr), sc_.transform(Xte)
    if rule == "ridge":
        P = np.column_stack([Ridge(alpha=10.0).fit(A, Ytr[:, k]).predict(B) for k in (0, 1)])
    else:
        P = np.column_stack([HistGradientBoostingRegressor(max_depth=3, max_iter=200, learning_rate=0.05,
                                                           random_state=0).fit(A, Ytr[:, k]).predict(B)
                             for k in (0, 1)])
    side = np.where(np.maximum(P[:, 0], P[:, 1]) <= 0, 0, np.where(P[:, 0] >= P[:, 1], 1, -1))
    return P[:, 0] - P[:, 1], side


results, trades_out = [], {}
for H in HORIZONS:
    nd, gd, exd, cd = outcomes(dev, H)
    nh, gh, exh, ch = outcomes(hold, H)
    check_against_reference(hold, H, gh, exh)
    Xd, Xh = dev[FEATS].to_numpy(), hold[FEATS].to_numpy()
    okd = ~np.isnan(nd).any(1)
    hrs_d, hrs_h = dev.index.hour.to_numpy(), hold.index.hour.to_numpy()
    folds = np.array_split(np.arange(len(dev)), K)
    purge = H + SEQ

    for rule in RULES:
        # out-of-fold on dev
        score_d, side_d = np.zeros(len(dev)), np.zeros(len(dev))
        for f in folds:
            lo, hi = f[0] - purge, f[-1] + purge
            tr = np.where(((np.arange(len(dev)) < lo) | (np.arange(len(dev)) > hi)) & okd)[0]
            score_d[f], side_d[f] = fit_predict(rule, Xd[tr], nd[tr], hrs_d[tr], Xd[f], hrs_d[f], dev.iloc[f])
        # single holdout pass, refit on all dev
        tr = np.where(okd)[0]
        score_h, side_h = fit_predict(rule, Xd[tr], nd[tr], hrs_d[tr], Xh, hrs_h, hold)

        for split, sc, sd, net, gro, ex, idx in (
                ("dev_oof", score_d, side_d, nd, gd, exd, dev.index),
                ("holdout", score_h, side_h, nh, gh, exh, hold.index)):
            r, ent = trade(sd, net, ex)
            ic, ic_t, n_m = monthly_ic(sc, gro[:, 0] - gro[:, 1], idx)
            cst = (cd if split == "dev_oof" else ch)[ent]
            results.append(dict(H=H, rule=rule, split=split, n=len(r),
                                mean_bps=r.mean() * 1e4 if len(r) else np.nan,
                                gross_bps=(r + cst).mean() * 1e4 if len(r) else np.nan,
                                gross_t=nw_t(r + cst), cost_bps=cst.mean() * 1e4 if len(r) else np.nan,
                                t_nw=nw_t(r), sr=r.mean() / r.std(ddof=1) if len(r) > 2 else np.nan,
                                psr0=psr(r), hit=(r > 0).mean() if len(r) else np.nan,
                                long_frac=float((sd[ent] > 0).mean()) if len(r) else np.nan,
                                ic=ic, ic_t=ic_t, ic_months=n_m))
            trades_out[(H, rule, split)] = r

    # benchmarks under identical sequencing
    rng = np.random.default_rng(0)
    for split, net, ex in (("dev_oof", nd, exd), ("holdout", nh, exh)):
        coins = [trade(rng.choice([-1, 1], size=len(net)), net, ex)[0].mean() for _ in range(N_COIN)]
        for b, side in (("always_long", np.ones(len(net))), ("always_short", -np.ones(len(net)))):
            r, _ = trade(side, net, ex)
            results.append(dict(H=H, rule=b, split=split, n=len(r), mean_bps=r.mean() * 1e4,
                                t_nw=nw_t(r), sr=r.mean() / r.std(ddof=1), psr0=psr(r)))
        results.append(dict(H=H, rule="coin_flip", split=split, mean_bps=float(np.mean(coins) * 1e4),
                            coin_sd_bps=float(np.std(coins) * 1e4)))
        trades_out[(H, "coin_dist", split)] = np.asarray(coins)

R = pd.DataFrame(results)
# DSR across the 12 trials, per split
for split in ("dev_oof", "holdout"):
    m = R[(R.split == split) & R.rule.isin(RULES)]
    v = m.sr.var(ddof=1)
    sr0 = np.sqrt(v) * ((1 - EULER) * stats.norm.ppf(1 - 1 / N_TRIALS) + EULER * stats.norm.ppf(1 - 1 / (N_TRIALS * np.e)))
    for i in m.index:
        r = trades_out[(R.at[i, "H"], R.at[i, "rule"], split)]
        R.at[i, "dsr"] = psr(r, sr0)
        coins = trades_out[(R.at[i, "H"], "coin_dist", split)]
        R.at[i, "p_vs_coin"] = float((coins >= r.mean()).mean()) if len(r) else np.nan
    R.loc[m.index, "sr_star"] = sr0
h = R[(R.split == "holdout") & R.rule.isin(RULES)]
R.loc[h.index, "PASS"] = (h.mean_bps > 0) & (h.t_nw > 2) & (h.dsr > 0.95) & (h.ic_t > 2)
R.to_csv(os.path.join(OUT, "ladder_results.csv"), index=False)
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
print(R.round(3).to_string())
