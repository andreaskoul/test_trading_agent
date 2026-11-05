"""Protocol 9 (PROTOCOL_fund.md): the SPY trend core under the 7B book. Pure functions, plus the frozen daily state.

* trend_state: SPY's close at a session against the mean of its last 200 closes, that session included.
* core_state: the session's core weight, decided on the previous session's close. Written once to
  fund_state/live/core/state.json and never recomputed (CLAUDE.md 4).
* account_target: the core plus lambda x the model's target, with one net SPY position.
* gross_guard: scales the overlay only, so the account's gross stays within GROSS_CAP.
* account_limits: what the pre-trade account check allows (shorting, margin multiplier).

The rule was tested once, pre-registered, on CRSP daily data 1927-2026 (research/exposure/, read 2026-11-04).
"""
import json
import os

import numpy as np
import pandas as pd

SLEEVE_UP, SLEEVE_DOWN, TREND_WIN = 1.3, 0.7, 200
LAMBDA, GROSS_CAP = 1 / 3, 1.9
P9_SHADOW = pd.Timestamp("2026-11-09")
# FUND_P9_START moves the first traded session (a failed shadow week defers it without a code change)
P9_START = pd.Timestamp(os.environ.get("FUND_P9_START") or "2026-11-16")


def trend_state(spy, S, d):
    """SPY's trend at the close of session index d: the close against the mean of the last TREND_WIN closes, d
    included. Uses closes <= d only."""
    win = spy[max(0, d - TREND_WIN + 1): d + 1]
    if len(win) < TREND_WIN or not np.isfinite(win).all():
        return None
    ma = float(win.mean())
    up = bool(spy[d] > ma)
    return {"spy": round(float(spy[d]), 4), "ma": round(ma, 4), "up": up, "sleeve": SLEEVE_UP if up else SLEEVE_DOWN}


def core_state(path, day, sessions, spy):
    """The core weight for `day`, from the last session before it. sessions: trading days; spy: SPY's adjusted
    closes on them. The first value computed for a day is written to `path` and returned ever after."""
    E = json.load(open(path)) if os.path.exists(path) else {}
    k = str(pd.Timestamp(day).date())
    if k in E:
        return E[k]
    S = pd.DatetimeIndex(sessions)
    prev = S[S < pd.Timestamp(day)]
    if not len(prev):
        return None
    st = trend_state(np.asarray(spy, float)[: len(prev)], prev, len(prev) - 1)
    if st is None:
        return None
    E[k] = {**st, "session": str(prev[-1].date())}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(E, open(path, "w"), indent=0, sort_keys=True)
    return E[k]


def account_target(model_target, s, lam=LAMBDA):
    """Core s in SPY plus lam x the model's weights; the model's SPY hedge nets into the one SPY position."""
    out = {t: lam * w for t, w in model_target.items() if t != "SPY"}
    out["SPY"] = s + lam * model_target.get("SPY", 0.0)
    return out


def gross(target):
    return float(sum(abs(v) for v in target.values()))


def gross_guard(model_target, s, lam=LAMBDA, cap=GROSS_CAP):
    """(target, k): the account target with the largest overlay scale k <= lam whose gross is within cap. The core is
    never scaled. Gross is convex in k and the core alone (k = 0) is within cap, so bisection finds the bound."""
    if gross(account_target(model_target, s, lam)) <= cap:
        return account_target(model_target, s, lam), lam
    lo, hi = 0.0, lam
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if gross(account_target(model_target, s, mid)) <= cap else (lo, mid)
    return account_target(model_target, s, lo), lo


def account_limits(acct, s):
    """(core weight, overlay allowed, problems) under the pre-trade account check: shorting disabled drops the
    overlay; a margin multiplier below 2 caps the core at 1.0 and drops the overlay."""
    problems, overlay = [], True
    if float(acct.get("multiplier") or 1) < 2:
        s, overlay = min(s, 1.0), False
        problems.append(f"protocol 9: account multiplier {acct.get('multiplier')} < 2: core capped at 1.0, no overlay")
    if not acct.get("shorting_enabled"):
        overlay = False
        problems.append("protocol 9: shorting disabled: no overlay this session")
    return s, overlay, problems
