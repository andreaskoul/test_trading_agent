"""Protocol 7B, Amendment 2 (PROTOCOL_fund.md): timing corrections. Pure functions, used by fund/lifecycle.py and
tested in fund/tests/test_amend7b2.py on real records.

B1 "already priced in" is measured from the release to the entry decision. Amendment 8's fraction p stopped at the
   as-of close, and dated the news by the first article of its first-report day, often a midnight preview. So an
   earnings release after the as-of close (GOOGL, 2026-10-28) counted as fully unpriced while the stock moved ~12%
   before entry. For earnings and guidance events, the news session is the session of the release:
   * the 8-K item 2.02 acceptance time within one calendar day of the first report;
   * else the earnings calendar's before-open / after-close flag;
   * else Amendment 8's rule.
   At the entry decision, CAR runs from that session to the decision price. The desk's horizon is rescaled by
   Amendment 8's own factor (1 - min(p, 1) / 2), with p recomputed. p >= 1 means hard news enters with H = 3 and
   soft news is not entered, as Amendment 8 already rules.
B2 news checks look back 24 hours before the previous check's cutoff, de-duplicated by headline, so an article the
   vendor serves late is checked at the next session at the latest. A check reads those late articles first, then the
   newest, up to 60 (it read the 25 newest). The 2026-10-31 audit of 16 live days found the checks had read 43% of
   their windows' articles: 967 were served after the check and 4,030 were cut by the cap.
B3 a new name is checked against its kill conditions on articles published after the desk's cutoff, at T-20 min on
   its entry day:
   * matched in >= 2 of 3 passes: not entered;
   * partial in >= 2: entered at half weight;
   * otherwise as decided.
"""

import numpy as np
import pandas as pd

LOOKBACK_S = 24 * 3600
CAP_BEFORE, CAP_A2 = 25, 60                         # articles one check reads: Amendment 7's 25, B2's 60
B1_TYPES = ("earnings", "guidance")


def session_of(ts_et, days):
    """The first session that can trade on news released at ts_et (US Eastern, naive): the same day if released
    before 16:00 on a trading day, else the next session (as fund/lifecycle.py session_of)."""
    d0, mins = pd.Timestamp(pd.Timestamp(ts_et).date()), ts_et.hour * 60 + ts_et.minute
    return next((d for d in days if d > d0 or (d == d0 and mins < 16 * 60)), None)


def release_session(event_type, first_reported, accepted, cal, days):
    """The session in which an earnings or guidance release reached the market, or None (Amendment 8's rule stands).
    accepted: 8-K item 2.02 acceptance times of the ticker (US Eastern, naive). cal: (date, hour) from the earnings
    calendar or None; hour 'bmo' (before the open) or 'amc' (after the close)."""
    if event_type not in B1_TYPES:
        return None
    fr = pd.Timestamp(first_reported)
    near = sorted(a for a in accepted if fr - pd.Timedelta(days=1) <= pd.Timestamp(pd.Timestamp(a).date()) <= fr + pd.Timedelta(days=1))
    if near:
        s0 = session_of(pd.Timestamp(near[0]), days)
        return {"session": str(s0.date()), "source": "8-K 2.02", "accepted": str(near[0])} if s0 is not None else None
    if cal and cal[1] in ("bmo", "amc"):
        d = pd.Timestamp(cal[0])
        if abs((d - fr).days) <= 1:
            s0 = d if cal[1] == "bmo" and d in days else next((x for x in days if x > d), None)
            return {"session": str(s0.date()), "source": f"calendar {cal[1]}"} if s0 is not None else None
    return None


def b1_horizon(t, info, side, R, beta, r_today, day, H_base, k):
    """The entry horizon under B1, or None when the name is not entered (priced in or stale). Returns (H, log).
    info: the desk's record of the name (inputs, release); R: frozen daily returns, dates x tickers with SPY, for the
    sessions before `day`; r_today: today's return to the decision price (a dict or Series with SPY); k: Amendment 8's
    constants (P_CAP, H_MIN, H8_MAX, STALE_AT)."""
    i, rel = info.get("inputs") or {}, info.get("release")
    if not rel or not i.get("M") or t not in r_today or "SPY" not in r_today:
        return H_base, {"b1": "not applicable"}
    s0 = pd.Timestamp(rel["session"])
    past = R[(R.index >= s0) & (R.index < pd.Timestamp(day))]
    car = float((past[t] - beta * past["SPY"]).sum()) if t in past and len(past) else 0.0
    car += (float(r_today[t]) - beta * float(r_today["SPY"])) if s0 <= pd.Timestamp(day) else 0.0
    if not np.isfinite(car):                           # a missing return: Amendment 8's horizon stands, logged
        return H_base, {"b1": "no return to measure", "release": rel}
    p_d, p_e = float(i.get("p") or 0.0), float(np.clip(side * car / float(i["M"]), 0.0, k["P_CAP"]))
    raw = H_base * (1 - 0.5 * min(p_e, 1.0)) / (1 - 0.5 * min(p_d, 1.0))
    log = {"release": rel, "car": car, "p_desk": p_d, "p_entry": p_e, "H_desk": H_base}
    if p_e >= 1:
        if i.get("hard"):
            return k["H_MIN"], {**log, "b1": "priced in, hard news -> 3"}
        return None, {**log, "b1": "priced in, not entered"}
    if raw <= k["STALE_AT"]:
        return None, {**log, "b1": "stale at entry, not entered"}
    H = int(min(max(round(raw), k["H_MIN"]), k["H8_MAX"]))
    return H, {**log, "b1": f"H {H_base} -> {H}"}


def news_lo(lot, day, a2_from):
    """B2: the start (epoch seconds) of a lot's news window. From a2_from on, 24 hours before the previous cutoff;
    before it, the previous cutoff itself. A lot never checked starts at its entry close."""
    until = lot.get("news_until")
    if not until:
        return lot["entry_close_ts"]
    return until - LOOKBACK_S if pd.Timestamp(day) >= pd.Timestamp(a2_from) else until


def b3_apply(cand, verdicts):
    """B3: cand {ticker: (w, side, info)} of new names; verdicts {ticker: check record}. Returns (cand, log)."""
    out, log = {}, {}
    for t, (w, side, info) in cand.items():
        v = (verdicts.get(t) or {}).get("verdict")
        if v == "exit":
            log[t] = "kill condition matched since the desk's cutoff: not entered"; continue
        if v == "reduce":
            out[t] = (w / 2, side, info); log[t] = "partial match since the desk's cutoff: half weight"; continue
        out[t] = (w, side, info)
        if v:
            log[t] = f"checked: {v} (no change at entry)"
    return out, log


def select_articles(arts, prev_until, day, a2_from):
    """The articles one kill check reads, from `arts` (unseen, sorted by publish time). Before a2_from: the 25 newest,
    as Amendment 7. From a2_from: those published at or before the previous check's cutoff (served late) first, then
    the newest, up to 60 in all. A lot never checked, or a pre-entry check, reads the 60 newest."""
    if pd.Timestamp(day) < pd.Timestamp(a2_from):
        return arts[-CAP_BEFORE:]
    if not prev_until:
        return arts[-CAP_A2:]
    late = [a for a in arts if a["datetime"] <= prev_until][-CAP_A2:]
    new = [a for a in arts if a["datetime"] > prev_until]
    new = new[-(CAP_A2 - len(late)):] if len(late) < CAP_A2 else []
    return sorted(late + new, key=lambda a: a["datetime"])
