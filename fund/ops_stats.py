"""Operations statistics for the go-live gate (fund/score.py). Pure functions, so they can be tested on real records.

* executed_share: under Protocol 7 the account trades every session (fund/lifecycle.py trade). A scored week counts
  as fully executed when every session in it has a submitted live record with no unfilled order. Before 2026-10-31
  the gate read the retired weekly execution.json files and showed 0%.
* cost_stats: the signed, notional-weighted mean slippage per side against the official close, with a day-block
  bootstrap (fills on one day share the last-minute market move). Median |slippage| measures dispersion, not cost;
  it is kept for the registered rule and reported beside these.
"""

import json
import os

import numpy as np
import pandas as pd


def executed_share(weeks, live_dir, sessions):
    """weeks: as-of dates (YYYY-MM-DD, Wednesdays); live_dir: lifecycle/live; sessions: the trading days the book was
    marked on (lifecycle/state.json rows). A week covers the sessions after its as-of up to and including the next
    as-of (Thursday to Wednesday). Returns (share of weeks fully executed, {week: [failed sessions]})."""
    days = sorted(pd.Timestamp(d) for d in sessions)
    bad = {}
    for a in weeks:
        a0 = pd.Timestamp(a)
        span = [d for d in days if a0 < d <= a0 + pd.Timedelta(days=7)]
        fails = []
        for d in span:
            p = os.path.join(live_dir, f"{d.date()}.json")
            rec = json.load(open(p)) if os.path.exists(p) else None
            if not rec or rec.get("status") != "submitted" or rec.get("problems"):
                fails.append(str(d.date()))
        bad[a] = fails if span else ["no session"]
    return (float(np.mean([not v for v in bad.values()])) if bad else float("nan")), bad


def cost_stats(fills, source="lifecycle", B=9999, seed=0):
    """fills: execution/fills.csv rows. Cost per fill = slip_bp (+ = worse than the official close), weighted by
    traded value. Returns n, days, mean, the day-block bootstrap standard error and one-sided 95% upper bound,
    median |slip| (dispersion) and the fill rate on ordered shares."""
    F = fills[fills["source"] == source] if "source" in fills else fills
    out = {"n": 0, "days": 0, "mean_bp": float("nan"), "se_bp": float("nan"), "upper95_bp": float("nan"),
           "median_abs_bp": float("nan"), "fill_rate": float("nan")}
    if not len(F):
        return out
    out["fill_rate"] = float(F["filled_qty"].fillna(0).sum() / F["qty"].sum()) if F["qty"].sum() else float("nan")
    G = F[F["slip_bp"].notna() & (F["filled_qty"] > 0)].copy()
    if not len(G):
        return out
    G["v"] = G["filled_qty"] * G["fill"]
    per_day = G.groupby("exec_day").apply(lambda g: pd.Series({"sv": (g["slip_bp"] * g["v"]).sum(), "v": g["v"].sum()}))
    mean = per_day["sv"].sum() / per_day["v"].sum()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(per_day), size=(B, len(per_day)))
    sv, v = per_day["sv"].to_numpy()[idx].sum(1), per_day["v"].to_numpy()[idx].sum(1)
    draws = sv / v
    out.update(n=int(len(G)), days=int(len(per_day)), mean_bp=float(mean), se_bp=float(draws.std(ddof=1)),
               upper95_bp=float(np.quantile(draws, 0.95)), median_abs_bp=float(G["slip_bp"].abs().median()))
    return out
