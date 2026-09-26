"""Stats for scripts/12_rl_zoo_holdout.py output, on the ladder's terms.

    python scripts/14_rl_zoo_stats.py
"""

import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, "scripts/11_baseline_ladder.py")).read().split("results, trades_out = [], {}")[0]
L = {"__file__": os.path.join(ROOT, "scripts/11_baseline_ladder.py")}
exec(compile(src, "ladder_helpers", "exec"), L)

Z = pd.read_parquet(os.path.join(ROOT, "reports/research/rl_zoo_holdout.parquet"))
hold = L["hold"]
net, gross, ex, cost = L["outcomes"](hold, 4)
pos = pd.Series(np.arange(len(hold)), index=hold.index)
Z["cost"] = cost[pos.reindex(Z.entry_ts).to_numpy()]
Z["gross"] = Z.ret + Z.cost

rows = []
for m, g in Z.groupby("model"):
    r = g.ret.to_numpy()
    rows.append(dict(model=m, algo=g.algo.iat[0], split=g.split.iat[0], seed=g.seed.iat[0], n=len(r),
                     mean_bps=r.mean() * 1e4, gross_bps=g.gross.mean() * 1e4, t_nw=L["nw_t"](r),
                     sr=r.mean() / r.std(ddof=1), long_frac=(g.direction > 0).mean()))
M = pd.DataFrame(rows)
N = len(M)
sr0 = np.sqrt(M.sr.var(ddof=1)) * ((1 - L["EULER"]) * stats.norm.ppf(1 - 1 / N)
                                   + L["EULER"] * stats.norm.ppf(1 - 1 / (N * np.e)))
M["dsr"] = [L["psr"](Z[Z.model == m].ret.to_numpy(), sr0) for m in M.model]

# coin-flip distribution under identical sequencing (H = 4)
rng = np.random.default_rng(0)
coins = np.array([L["trade"](rng.choice([-1, 1], size=len(net)), net, ex)[0].mean() for _ in range(200)]) * 1e4
M["p_vs_coin"] = [(coins >= x).mean() for x in M.mean_bps]

# equal-weight zoo, daily
daily = (Z.assign(day=Z.exit_ts.dt.floor("D")).groupby(["day", "model"]).ret.sum()
         .unstack(fill_value=0.0).reindex(columns=range(N), fill_value=0.0))
z = daily.mean(1).to_numpy()
M.to_csv(os.path.join(ROOT, "reports/research/rl_zoo_holdout_per_model.csv"), index=False)
summary = {
    "n_models": N, "coin_mean_bps": float(coins.mean()), "coin_sd_bps": float(coins.std()),
    "median_net_bps": float(M.mean_bps.median()), "median_gross_bps": float(M.gross_bps.median()),
    "frac_net_positive": float((M.mean_bps > 0).mean()),
    "frac_beat_coin_p05": float((M.p_vs_coin < 0.05).mean()),
    "frac_t_gt_2": float((M.t_nw > 2).mean()), "frac_t_lt_m2": float((M.t_nw < -2).mean()),
    "best": M.loc[M.sr.idxmax()].to_dict(), "sr_star": float(sr0),
    "max_dsr": float(M.dsr.max()),
    "ew_daily_bps": float(z.mean() * 1e4), "ew_daily_t": float(L["nw_t"](z)),
    "median_trades": float(M.n.median()),
}
pd.Series(summary).to_json(os.path.join(ROOT, "reports/research/rl_zoo_holdout_summary.json"), indent=2,
                           default_handler=str)
print(pd.Series(summary).to_string())
print(M.groupby("algo")[["mean_bps", "gross_bps", "n", "long_frac"]].median().round(2))
