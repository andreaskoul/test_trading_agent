"""Risk-field research, Amendment 15: verifying F2 (S&P 400 replication, controls, stability).

    python research/riskfield/verify10.py     # ONCE for the replication (REP10_READ.lock) -> VERIFY10.md/json
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "regime"))
import panel as PN                                                                    # noqa: E402
import regime as RG                                                                   # noqa: E402
import round10 as R10                                                                 # noqa: E402
from intl import dk_t                                                                 # noqa: E402
from round6 import dk_multi                                                           # noqa: E402


def panel400():
    a = pd.read_parquet(os.path.join(PN.P8, "alpaca_bars.parquet"))
    a = a[a.date <= PN.END]
    s4 = pd.read_csv(os.path.join(PN.ROOT, "data", "raw", "stocks", "sp400_current.csv")).Symbol.astype(str)
    px = a[a.ticker.isin(set(s4) | {"SPY"})].pivot(index="date", columns="ticker", values="close").sort_index()
    px.index = pd.to_datetime(px.index)
    spy = px.pop("SPY")
    names = list(px.columns)
    r = px.pct_change().values
    rm = spy.pct_change().values
    lo, hi = np.minimum(-2 * rm, 4 * rm)[:, None], np.maximum(-2 * rm, 4 * rm)[:, None]
    w = pd.DataFrame(np.clip(r, lo, hi), index=px.index)
    m = pd.Series(rm, index=px.index)
    beta = ((2 / 3) * w.rolling(252, min_periods=200).cov(m).div(m.rolling(252, min_periods=200).var(), axis=0).fillna(1.0) + 1 / 3).values
    e = r - np.vstack([np.full((1, r.shape[1]), np.nan), beta[:-1]]) * rm[:, None]
    return dict(S=px.index, names=names, close=px.values, spy=spy.values, r=r, rm=rm, beta=beta, e=e, elig=np.isfinite(px.values))


def controls(P, rows):
    """Next week's residual on [z(F2), z(5d residual), z(log 20d vol), z(log 20d FINRA dollar volume)]."""
    F = pd.read_parquet(os.path.join(PN.CACHE, "finra_short.parquet"))
    F = F[F.ticker.isin(P["names"])]
    tot = F.pivot(index="date", columns="ticker", values="total").reindex(P["S"]).reindex(columns=P["names"]).to_numpy()
    cr = np.vstack([np.zeros((1, len(P["names"]))), np.nancumsum(np.nan_to_num(P["e"]), 0)])
    blocks = []
    for w, t, z, y, R, Rm in rows:
        rev = cr[t + 1] - cr[t - 4]
        vol = np.log(np.nanstd(P["r"][t - 19:t + 1], 0))
        dv = np.log(np.nanmean(tot[t - 19:t + 1], 0) * P["close"][t])
        X = np.column_stack([z, RG.zs(rev), RG.zs(vol), RG.zs(dv)])
        blocks.append((w, y, X))
    b, tt, n = dk_multi(blocks)
    return {"b_bp": [float(x * 1e4) for x in b], "t": [float(x) for x in tt], "n": n,
            "names": ["F2", "reversal_5d", "log_vol_20d", "log_dollar_volume_20d"]}


def main():
    lock = os.path.join(HERE, "REP10_READ.lock")
    if os.path.exists(lock):
        raise SystemExit("already read: " + open(lock).read())
    out = {}
    # 1. replication, S&P 400
    P4 = panel400()
    rows4, _ = R10.build("F", (pd.Timestamp("2016-02-01"), pd.Timestamp("2025-12-24")), P4)
    rep = R10.evaluate(rows4["F2"], P4, "F2", -1)
    rep["p_one_sided"] = float(norm.cdf(rep["t"]))
    rep["pass"] = bool(rep["p_one_sided"] < 0.05 and rep["2bp"]["net_bp_wk"] > 0)
    out["replication_sp400"] = rep
    # 2. controls, S&P 500 OOS
    P = RG.panel()
    rows, _ = R10.build("F", R10.PER["F"]["oos"], P)
    out["controls_oos"] = controls(P, rows["F2"])
    out["controls_oos"]["robust"] = bool(out["controls_oos"]["t"][0] <= -1.65)
    # 3. stability, S&P 500 by year (descriptive)
    allrows, _ = R10.build("F", (pd.Timestamp("2012-04-01"), pd.Timestamp("2025-12-24")), P)
    S = P["S"]
    yrs = {}
    for y in range(2012, 2026):
        sel = [x for x in allrows["F2"] if S[x[1]].year == y]
        b, t, n = dk_t([(np.full(len(z), w), yy, z) for w, tt_, z, yy, R, Rm in sel])
        yrs[y] = {"bp_per_sd": b * 1e4, "t": t}
    for nm, f in (("before_2018_08", lambda d: d < pd.Timestamp("2018-08-01")), ("after_2018_08", lambda d: d >= pd.Timestamp("2018-08-01"))):
        sel = [x for x in allrows["F2"] if f(S[x[1]])]
        b, t, n = dk_t([(np.full(len(z), w), yy, z) for w, tt_, z, yy, R, Rm in sel])
        yrs[nm] = {"bp_per_sd": b * 1e4, "t": t}
    out["stability"] = yrs
    at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    out["read_at"] = at
    json.dump(out, open(os.path.join(HERE, "VERIFY10.json"), "w"), indent=1, default=float)
    open(lock, "w").write(f"read {at}\n")
    c = out["controls_oos"]
    L = ["# Verifying F2, the off-exchange short-volume ratio (Amendment 15)", "", f"Read {at}.", "",
         f"**1. Replication, S&P 400 current list 2016-2025 (one read):** {rep['bp_per_sd']:.1f} bp per sd, DK t {rep['t']:.2f}, "
         f"one-sided p {rep['p_one_sided']:.4f}; book net {rep['2bp']['net_pct_yr']:.2f}% a year at 2 bp (Sharpe {rep['2bp']['sharpe']:.2f}), "
         f"{rep['5bp']['net_pct_yr']:.2f}% at 5 bp; {rep['names']:.0f} names. **{'pass' if rep['pass'] else 'fail'}**", "",
         "**2. Controls, S&P 500 OOS 2020-2025:**", "", "| Regressor | bp per sd | DK t |", "|---|---:|---:|"]
    L += [f"| {n} | {b:.1f} | {t:.2f} |" for n, b, t in zip(c["names"], c["b_bp"], c["t"])]
    L += ["", f"F2 robust to the controls (t <= -1.65): **{'yes' if c['robust'] else 'no'}**", "",
          "**3. Stability (descriptive), S&P 500:**", "", "| Period | bp per sd | t |", "|---|---:|---:|"]
    L += [f"| {k} | {v['bp_per_sd']:.1f} | {v['t']:.2f} |" for k, v in yrs.items()]
    open(os.path.join(HERE, "VERIFY10.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
