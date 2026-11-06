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


# Reg T: positions held overnight may total at most 2x equity (Alpaca enforces it; its "multiplier" of 4 is intraday)
GROSS_ALERT = 1.95


def account_target(lots, nav, hedge, halted):
    """The account's target weights for a session: each lot's notional over the model NAV, plus the SPY hedge.
    A risk halt (fund_state/live/HALT, written by execute.py reconcile) makes the target flat until it is removed
    by hand; before 2026-11-06 lifecycle.trade() did not read the file."""
    if halted:
        return {}
    target = {L["ticker"]: L["n"] / nav for L in lots}
    if abs(hedge) > 1e-9:
        target["SPY"] = hedge / nav
    return target


def margin_check(acct, target):
    """Pre-trade account check, logged with the decision. Returns the projected gross (sum of |weights|), the
    account's margin fields and the problems: gross above GROSS_ALERT, a margin account below 2x when the book is
    levered, or shorts in the target with shorting disabled. It changes no order."""
    gross = float(sum(abs(w) for w in target.values()))
    mult = float(acct.get("multiplier") or 1)
    shorting = bool(acct.get("shorting_enabled"))
    out = {"gross": round(gross, 4), "multiplier": mult, "shorting_enabled": shorting,
           "regt_buying_power": float(acct.get("regt_buying_power") or 0), "problems": []}
    if gross > GROSS_ALERT:
        out["problems"].append(f"margin: projected gross {gross:.2f}x equity is above {GROSS_ALERT}x (Reg T overnight 2x)")
    if gross > 1 and mult < 2:
        out["problems"].append(f"margin: the book is levered ({gross:.2f}x) but the account multiplier is {mult:g}")
    if any(w < 0 for w in target.values()) and not shorting:
        out["problems"].append("margin: the target has shorts but shorting is disabled on the account")
    return out


def rebuild_diff(first, second):
    """Where two rebuilds of a book disagree (the determinism check in lifecycle.daily/control). first, second: run()
    outputs ({"rows": [{"date", "nav"}], "events": [...]}). Returns the first date whose NAV differs (with both values),
    the dates only one run has, and up to 10 events in one run but not the other. Diagnosis only: it changes nothing."""
    a, b = {r["date"]: r["nav"] for r in first["rows"]}, {r["date"]: r["nav"] for r in second["rows"]}
    both = sorted(set(a) & set(b))
    d0 = next((d for d in both if a[d] != b[d]), None)
    key = lambda e: json.dumps(e, sort_keys=True, default=str)
    ea, eb = {key(e) for e in first.get("events", [])}, {key(e) for e in second.get("events", [])}
    return {"first_nav_diff": None if d0 is None else {"date": d0, "first": a[d0], "second": b[d0], "diff": b[d0] - a[d0]},
            "dates_only_first": sorted(set(a) - set(b)), "dates_only_second": sorted(set(b) - set(a)),
            "events_only_first": sorted(ea - eb)[:10], "events_only_second": sorted(eb - ea)[:10]}
