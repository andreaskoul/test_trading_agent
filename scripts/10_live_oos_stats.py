"""Statistics on reports/live_oos/trades.parquet (from 09_live_oos_eval.py).

Unit of observation is the trade at unit notional, net of the cron's cost
model (1 bp spread round trip + vol-scaled slippage). Each engine trade is
priced under three execution models:

  engine  : what PaperEngine books. Barrier checked on the bar CLOSE, but
            the fill is the barrier PRICE. When the close has already gone
            through the stop, the loss is booked at the stop level: the
            stop is filled at a price the market left behind.
  next    : market orders at the next bar's open for entry and exit
            (what an hourly cron can actually do without resting orders).
  bracket : entry at next open, resting TP/SL orders checked on the bar
            high/low; stop first if both touch in one bar; gaps through a
            level fill at the open; timeout at the close of bar H.

Tests: HAC t (Newey-West, 5 lags); per-trade Sharpe; PSR(0); DSR with
N = zoo size and the cross-model Sharpe variance (Bailey & Lopez de Prado
2014); sign-randomisation null (same timing, random side); random-entry
null (same count, random bars and sides, same execution rules); zoo-level
equal-weight daily P&L with HAC t.
"""

import json
import sys

import numpy as np
import pandas as pd
from scipy import stats

D = sys.argv[1] if len(sys.argv) > 1 else "reports/live_oos"
T = pd.read_parquet(f"{D}/trades.parquet")
B = pd.read_parquet(f"{D}/bars.parquet")
meta = json.load(open(f"{D}/meta.json"))
rng = np.random.default_rng(0)
DEPLOYED, N_MODELS, EULER, NSIM = 0, meta["n_models"], 0.5772156649, 20000
H, UP, DN = meta["env"]["horizon"], meta["env"]["rr_upper"], meta["env"]["rr_lower"]
o, h, l, c, a = (B[k].to_numpy() for k in ("open", "high", "low", "close", "atr"))
cost = 2 * 0.5e-4 + 2 * 0.3e-4 * np.maximum(0.1, B["vol_q"].to_numpy())
n = len(c)


def nw_t(x, L=5):
    x = np.asarray(x, float); e = x - x.mean(); s = e @ e / len(x)
    for k in range(1, min(L, len(x) - 1) + 1):
        s += 2 * (1 - k / (L + 1)) * (e[k:] @ e[:-k]) / len(x)
    return x.mean() / np.sqrt(s / len(x))


def psr(x, sr0=0.0):
    x = np.asarray(x, float); sr = x.mean() / x.std(ddof=1)
    g3, g4 = stats.skew(x), stats.kurtosis(x, fisher=False)
    return float(stats.norm.cdf((sr - sr0) * np.sqrt(len(x) - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)))


def price(i, d, ex):
    """Net return of a trade signalled at bar i, side d, under execution ex."""
    if ex == "engine":
        e = c[i]; tp, sl = e + d * UP * a[i], e - d * DN * a[i]
        for j in range(i + 1, n):
            if d * (c[j] - tp) >= 0: return d * (tp / e - 1) - cost[i], j
            if d * (sl - c[j]) >= 0: return d * (sl / e - 1) - cost[i], j
            if j - i >= H: return d * (c[j] / e - 1) - cost[i], j
        return np.nan, n
    if ex == "next":
        _, j = price(i, d, "engine")
        if i + 1 >= n or j + 1 >= n: return np.nan, j
        return d * (o[j + 1] / o[i + 1] - 1) - cost[i], j
    # bracket
    if i + 1 >= n: return np.nan, n
    e = o[i + 1]; tp, sl = e + d * UP * a[i], e - d * DN * a[i]
    for j in range(i + 1, min(i + 1 + H, n)):
        lo_, hi_ = (l[j], h[j]) if d > 0 else (-h[j], -l[j])
        s_, t_ = d * sl, d * tp
        if lo_ <= s_:                                   # stop touched (checked first)
            fill = o[j] if (j > i + 1 and d * o[j] <= s_) else sl
            return d * (fill / e - 1) - cost[i], j
        if hi_ >= t_:
            fill = o[j] if (j > i + 1 and d * o[j] >= t_) else tp
            return d * (fill / e - 1) - cost[i], j
    j = min(i + H, n - 1)
    return d * (c[j] / e - 1) - cost[i], j


EXECS = ("engine", "next", "bracket")
pos = pd.Series(np.arange(n), index=B.index)
T["i"] = pos.reindex(T.entry_ts).to_numpy()
for ex in EXECS:
    T[f"r_{ex}"] = [price(i, d, ex)[0] for i, d in zip(T.i, T.direction)]

live = np.where(B.index >= pd.Timestamp(meta["live_start"]))[0]
live = live[live < n - H - 2]
bar = {ex: np.array([[price(i, d, ex)[0] for d in (1, -1)] for i in live]) for ex in EXECS}

res = {"meta": meta, "benchmarks": {ex: {
    "always_long_bps": float(np.nanmean(bar[ex][:, 0]) * 1e4),
    "always_short_bps": float(np.nanmean(bar[ex][:, 1]) * 1e4),
    "coinflip_bps": float(np.nanmean(bar[ex]) * 1e4)} for ex in EXECS}}
res["benchmarks"]["breakeven_hit_rate_gross"] = DN / (UP + DN)

rows = []
for (info, m), g in T.groupby(["info", "model"]):
    for ex in EXECS:
        x = g[f"r_{ex}"].dropna().to_numpy()
        rows.append(dict(info=info, model=m, exec=ex, algo=g.algo.iat[0], split=g.split.iat[0],
                         seed=g.seed.iat[0], n=len(x), mean_bps=x.mean() * 1e4,
                         sr=x.mean() / x.std(ddof=1), t_nw=nw_t(x), hit=(x > 0).mean(),
                         long_frac=(g.direction > 0).mean(), psr0=psr(x)))
M = pd.DataFrame(rows)
M.to_csv(f"{D}/per_model.csv", index=False)

for info in ("causal", "leaky"):
    g = T[T["info"] == info]
    for ex in EXECS:
        mm = M[(M["info"] == info) & (M["exec"] == ex)]
        s0 = float(np.sqrt(mm.sr.var(ddof=1)) * ((1 - EULER) * stats.norm.ppf(1 - 1 / N_MODELS)
                                                 + EULER * stats.norm.ppf(1 - 1 / (N_MODELS * np.e))))
        out = {}
        for tag, mid in (("deployed", DEPLOYED), ("best_ex_post", int(mm.loc[mm.sr.idxmax()].model))):
            dd = g[g.model == mid].dropna(subset=[f"r_{ex}"])
            x = dd[f"r_{ex}"].to_numpy(); ci = cost[dd.i.to_numpy()]
            gross = (x + ci) * dd.direction.to_numpy()            # side-free move
            flips = rng.choice([-1, 1], size=(NSIM, len(x)))
            p_flip = float(((flips * gross - ci).mean(1) >= x.mean()).mean())
            ri = rng.integers(0, len(live), size=(NSIM, len(x))); rs = rng.integers(0, 2, size=(NSIM, len(x)))
            p_rand = float((np.nanmean(bar[ex][ri, rs], 1) >= x.mean()).mean())
            r = mm[mm.model == mid].iloc[0]
            out[tag] = {"model": mid, "algo": r.algo, "n": int(r.n), "mean_bps": float(r.mean_bps),
                        "sr_trade": float(r.sr), "t_nw": float(r.t_nw), "hit": float(r.hit),
                        "long_frac": float(r.long_frac), "psr0": float(r.psr0), "dsr": psr(x, s0),
                        "p_sign_flip": p_flip, "p_random_entry": p_rand,
                        "cum_ret_unit": float(np.prod(1 + x) - 1)}
        daily = (g.assign(day=g.exit_ts.dt.floor("D")).groupby(["day", "model"])[f"r_{ex}"].sum()
                 .unstack(fill_value=0.0).reindex(columns=range(N_MODELS), fill_value=0.0))
        z = daily.mean(1).to_numpy()
        out["zoo"] = {"median_mean_bps": float(mm.mean_bps.median()),
                      "frac_positive": float((mm.mean_bps > 0).mean()),
                      "frac_t_gt_2": float((mm.t_nw > 2).mean()), "frac_t_lt_m2": float((mm.t_nw < -2).mean()),
                      "sr_star": s0, "ew_daily_bps": float(z.mean() * 1e4), "ew_daily_t_nw": float(nw_t(z)),
                      "ew_ann_sharpe": float(z.mean() / z.std(ddof=1) * np.sqrt(252)), "n_days": len(z),
                      "trades": int(mm.n.sum()), "long_frac": float((g.direction > 0).mean())}
        res[f"{info}/{ex}"] = out

# where the engine/bracket gap comes from (causal, all models)
g = T[T["info"] == "causal"]
res["exit_mix"] = g.barrier.value_counts(normalize=True).to_dict()
res["gap_by_barrier_bps"] = {b: float((gg.r_engine - gg.r_bracket).mean() * 1e4) for b, gg in g.groupby("barrier")}
json.dump(res, open(f"{D}/summary.json", "w"), indent=2, default=float)
print(json.dumps(res, indent=1, default=float))
