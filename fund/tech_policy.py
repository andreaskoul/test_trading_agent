"""Technicals desk · the rule policy of the Technical Timing book (draft Amendment 8). Pure, no I/O.

Everything here works in the long frame of `levels.Chart` (a short is a mirrored chart), at session
closes, in units of ATR (price structure) and W = sigma_e x sqrt(H) (the Position Lifecycle book's
residual-volatility unit, so stops and targets compare across names and with that book).

Three questions, one function each:
* `plan_entry(lm, ...)`   enter now (full / half), wait for a retest, or skip; with the stop and first target.
* `Lot.step(lm, ...)`     each later close: fill a waiting or half entry, stop, take profit, trail, time out.
* `regime(...)`           the pre-registered regime dial (trail width, size of the first partial).

The levels are context, never a reason to trade: the news view decides the side, and the policy only
decides where, when and how much (Osler 2000/2003; Kaminski & Lo 2014; see PROTOCOL_fund.md).
"""

import math

P = dict(
    STOP_BUF=0.25,        # stop sits this many ATR beyond the structural level
    ROUND_BUF=0.35,       # ... and beyond a round number within ROUND_NEAR ATR of it (stop clusters, Osler 2003)
    ROUND_NEAR=0.5,
    STOP_MIN_W=1.0,       # stop distance clamped to [1.0, 2.5] W
    STOP_MAX_W=2.5,
    STOP_CONFIRM_W=1.0,   # a structural stop needs a residual loss of at least 1 W too (the hedge covers market moves)
    BACKSTOP_W=2.0,       # the Position Lifecycle book's residual stop stays as a backstop
    TARGET_FRONT=0.1,     # first target this many ATR in front of the opposing zone or round number
    RR_SKIP=1.0,          # room / risk below this and no breakout: skip
    RR_FULL=2.0,          # at or above this (trend aligned, news accepted): full size
    PRICED_Z=2.0,         # residual move since the news above this many sigma*sqrt(days): wait for a retest
    EXT_ATR=2.0,          # or close more than this many ATR above the 20-day average
    RETEST_BAND=0.5,      # a retest is a close within this many ATR above the retest level, holding it
    WAIT_DAYS=3,          # sessions a waiting entry may wait
    BREAKOUT_RELVOL=1.5,  # a close through the opposing zone on this relative volume is a breakout
    ACCEPT_RELVOL=1.5,    # the news day's relative volume for "accepted"
    PART1=1 / 3,          # first partial at the first target (1/2 in a choppy regime)
    PART2=1 / 3,          # second partial at +3 W (the Position Lifecycle book's target)
    TARGET2_W=3.0,
    TRAIL_ATR=3.0,        # trail: highest close - 3 ATR (2.5 in a momentum regime)
    TRAIL_ON_W=1.0,       # in clear air (no target) the trail starts once the gain reaches 1 W
    PIVOT_BUF=0.25,       # ... or the last higher-low pivot minus 0.25 ATR, whichever is higher
    TIME_CHECK=0.5,       # at half the horizon, a gain below 0.5 W halves the position
    TIME_MIN_W=0.5,
    MAX_ROOM_ATR=10.0,    # room is capped here for the ratio (clear air)
)
ACTIONS = ("full", "half_add", "wait_retest", "skip_no_room", "skip_invalidated")


def regime(spy_above_200: bool | None, breadth50: float | None, bbw_pct: float | None) -> dict:
    """Momentum regime (SPY above its 200-day and > 60% of members above their 50-day): trail tighter, 2.5 ATR.
    Choppy (breadth 40-60% and the stock's band width in its bottom fifth): first partial is 1/2."""
    mom = bool(spy_above_200) and breadth50 is not None and breadth50 > 0.60
    chop = breadth50 is not None and 0.40 <= breadth50 <= 0.60 and bbw_pct is not None and bbw_pct <= 0.20
    return {"momentum": mom, "choppy": chop, "trail_atr": 2.5 if mom else P["TRAIL_ATR"],
            "part1": 0.5 if chop else P["PART1"]}


def _strong(z, lm_strong):
    return z["strength"] >= lm_strong


def structural_stop(lm: dict, W_px: float, strong: float) -> dict:
    """The stop below a long: the nearest of (strong zone wholly below the close, the news-day low) whose
    buffered distance is at least STOP_MIN_W; clamped to [STOP_MIN_W, STOP_MAX_W] W, then moved beyond a
    round number sitting just above it."""
    c, a = lm["close"], lm["atr"]
    cands = [(z["lo"], f"zone {z['id']}") for z in lm["zones"] if _strong(z, strong) and z["hi"] < c - 1e-12]
    if lm.get("event") and lm["event"]["low"] < c:
        cands.append((lm["event"]["low"], "news-day low"))
    cands.sort(key=lambda x: -x[0])                     # nearest first
    lo_d, hi_d = P["STOP_MIN_W"] * W_px, P["STOP_MAX_W"] * W_px
    level, why = None, None
    for px, nm in cands:
        s = px - P["STOP_BUF"] * a
        if c - s >= lo_d:
            level, why = s, f"below {nm}"
            break
    if level is None:
        level, why = c - lo_d, "1.0 W (structure closer than 1 W)"
    if c - level > hi_d:
        level, why = c - hi_d, "2.5 W cap (no structure within 2.5 W)"
    for r in lm["rounds"]:
        if level <= r["price"] <= level + P["ROUND_NEAR"] * a and r["price"] < c:
            nl = r["price"] - P["ROUND_BUF"] * a
            if c - nl <= hi_d:
                level, why = nl, why + f", beyond round {abs(r['price']):g}"
    return {"level": level, "dist": c - level, "dist_w": (c - level) / W_px if W_px else None, "why": why}


def room(lm: dict, strong: float) -> dict:
    """The nearest strong opposing zone above a long (a hard news level counts at any strength). A close
    inside a strong zone has zero room unless it is breaking out. None above: clear air.
    The 52-week (or all-time) high caps a long only once it has been tested (two swing highs, a double top);
    a single-touch high is the trend's own extreme, and being near it predicts continuation, not a stop
    (George & Hwang 2004), so above it is clear air."""
    c, a = lm["close"], lm["atr"]
    top_extreme = lambda z: ("52w_high" in z["anchors"] or "all_time_high" in z["anchors"]) and z["highs"] < 2
    above = [z for z in lm["zones"] if (_strong(z, strong) or z["hard"]) and z["hi"] >= c - 1e-12
             and (z["hard"] or not top_extreme(z))]
    above.sort(key=lambda z: z["lo"])
    if not above:
        return {"zone": None, "dist": math.inf, "target": None, "clear_air": True}
    z = above[0]
    dist = max(0.0, z["lo"] - c)
    tgt = z["lo"] - P["TARGET_FRONT"] * a
    for r in lm["rounds"]:
        if c < r["price"] <= tgt and tgt - r["price"] <= P["ROUND_NEAR"] * a:
            tgt = r["price"] - P["TARGET_FRONT"] * a
            break
    return {"zone": z, "dist": dist, "target": tgt if tgt > c else None, "clear_air": False}


def breakout(lm: dict, prev: dict | None, strong: float) -> bool:
    """Today's close went through a strong zone that capped yesterday's close, on relative volume."""
    if prev is None or (lm.get("relvol") or 0) < P["BREAKOUT_RELVOL"]:
        return False
    return any(_strong(z, strong) and prev["close"] <= z["hi"] < lm["close"] for z in prev["zones"])


def retest_level(lm: dict, strong: float) -> float | None:
    """Where a pullback should hold: the higher of the news-day AVWAP and the top of the nearest strong zone
    below the close."""
    c = lm["close"]
    xs = [z["hi"] for z in lm["zones"] if _strong(z, strong) and z["hi"] < c]
    if lm.get("avwap", {}).get("from_event") is not None and lm["avwap"]["from_event"] < c:
        xs.append(lm["avwap"]["from_event"])
    return max(xs) if xs else None


def accepted(lm: dict) -> bool | None:
    """The market accepted the news: close above the news-day AVWAP and the news-day midpoint, and the news
    day traded on volume. None when there is no news day in the price."""
    ev = lm.get("event")
    if not ev:
        return None
    return bool(lm["close"] >= (ev["avwap"] or -math.inf) and lm["close"] >= ev["mid"]
                and (ev["relvol"] or 0) >= P["ACCEPT_RELVOL"])


def invalidated(lm: dict) -> bool:
    """The close is already below the news-day low (long frame): the market rejected the news."""
    ev = lm.get("event")
    return bool(ev and ev["sessions_since"] >= 1 and lm["close"] < ev["low"])


def plan_entry(lm: dict, W_px: float, priced_z: float | None, prev: dict | None = None, strong: float = 2.0) -> dict:
    """The entry decision at a close, with its reasons, the stop and the first target (long frame)."""
    st = structural_stop(lm, W_px, strong)
    rm = room(lm, strong)
    risk = st["dist"]
    rr = min(rm["dist"], P["MAX_ROOM_ATR"] * lm["atr"]) / risk if risk > 0 else 0.0
    bo = breakout(lm, prev, strong)
    acc = accepted(lm)
    trend = (lm.get("slope50_atr") or 0) > 0 and (lm.get("mad_atr") or 0) > 0
    ext = lm.get("ext_atr")
    stretched = (priced_z is not None and priced_z > P["PRICED_Z"]) or (ext is not None and ext > P["EXT_ATR"])
    why = []
    if invalidated(lm):
        act = "skip_invalidated"; why.append("closed below the news-day low")
    elif rr < P["RR_SKIP"] and not bo:
        act = "skip_no_room"; why.append(f"room/risk {rr:.2f} < {P['RR_SKIP']}")
    elif stretched:
        act = "wait_retest"; why.append(f"stretched (priced-in z {priced_z if priced_z is None else round(priced_z, 2)}, "
                                         f"extension {ext} ATR)")
    elif rr < P["RR_FULL"] or not trend or acc is False:
        act = "half_add"
        why += ([f"room/risk {rr:.2f} < {P['RR_FULL']}"] if rr < P["RR_FULL"] else []) + \
               (["against the trend"] if not trend else []) + (["news not accepted"] if acc is False else [])
    else:
        act = "full"; why.append(f"room/risk {rr:.2f}, trend aligned" + (", news accepted" if acc else ""))
    return {"action": act, "why": "; ".join(why), "rr": round(rr, 3), "risk_w": st["dist_w"], "stop": st,
            "room": {"dist_atr": None if rm["dist"] == math.inf else rm["dist"] / lm["atr"], "clear_air": rm["clear_air"],
                     "zone": rm["zone"]["id"] if rm["zone"] else None, "target": rm["target"]},
            "breakout": bo, "accepted": acc, "trend": trend, "stretched": stretched,
            "retest": retest_level(lm, strong)}


class Lot:
    """One position's technical state in the long frame. `frac` is the share of the planned size held
    (0 waiting, 0.5 half, 1 full; partials take it lower). R is the side-signed residual return since entry,
    supplied by the caller each close, in return units; W in return units too."""

    def __init__(self, plan: dict, lm: dict, W: float, H: int, reg: dict):
        self.W, self.H, self.reg = W, H, reg
        self.action = plan["action"]
        self.frac = {"full": 1.0, "half_add": 0.5}.get(self.action, 0.0)
        self.waiting = self.action == "wait_retest"
        self.add_open = self.action == "half_add"
        self.retest = plan["retest"]
        self.days, self.wait_days = 0, 0
        self.entered = self.frac > 0
        self._arm(plan, lm)
        self.part1 = self.part2 = self.halved = False
        self.peak = lm["close"]
        self.trail = None
        self.R_entry = 0.0                     # residual R at the first fill (waiting entries start later)

    def _arm(self, plan, lm):
        self.entry_px = lm["close"]
        self.stop = plan["stop"]["level"]
        self.target1 = plan["room"]["target"]
        self.clear_air = plan["room"]["clear_air"]

    def step(self, lm: dict, R: float, prev: dict | None, priced_z: float | None, strong: float = 2.0) -> list:
        """One close. Returns [(new_frac, reason)] in order; the caller trades to the last new_frac.
        R: side-signed residual return since the lot was first opened (0 while waiting)."""
        out = []
        c, a = lm["close"], lm["atr"]
        W_px = self.W * abs(c)
        if self.waiting:                                 # wait for a retest, at most WAIT_DAYS sessions
            self.wait_days += 1
            if invalidated(lm):
                self.waiting = False
                return [(0.0, "skip_invalidated")]
            lvl = self.retest
            if lvl is not None and lvl <= c <= lvl + P["RETEST_BAND"] * a:
                plan = plan_entry(lm, W_px, priced_z, prev, strong)
                self.waiting, self.entered, self.frac = False, True, 1.0
                self._arm(plan, lm); self.peak = c
                return [(1.0, "entry_retest")]
            if self.wait_days >= P["WAIT_DAYS"]:
                self.waiting = False
                if accepted(lm) is not False:
                    plan = plan_entry(lm, W_px, priced_z, prev, strong)
                    self.entered, self.frac, self.add_open = True, 0.5, True
                    self.retest = plan["retest"]
                    self._arm(plan, lm); self.peak = c
                    return [(0.5, "entry_late_half")]
                return [(0.0, "skip_no_retest")]
            return []
        if not self.entered or self.frac <= 0:
            return []
        self.days += 1
        self.peak = max(self.peak, c)
        # 1. stops: structural (confirmed by the residual), trail, backstop
        if R <= -P["BACKSTOP_W"] * self.W:
            return [(0.0, "stop_backstop")]
        if c <= self.stop and R <= -P["STOP_CONFIRM_W"] * self.W:
            return [(0.0, "stop_structural")]
        if self.trail is not None and c <= self.trail:
            return [(0.0, "trail")]
        # 2. profits
        if not self.part1 and self.target1 is not None and c >= self.target1:
            self.part1 = True
            self.frac *= 1 - self.reg["part1"]
            self.stop = max(self.stop, self.entry_px, lm["avwap"].get("from_event") or -math.inf)
            out.append((self.frac, "take_profit_1"))
        if not self.part2 and R >= P["TARGET2_W"] * self.W:
            self.part2 = True
            self.frac *= 1 - P["PART2"]
            out.append((self.frac, "take_profit_2"))
        # 3. the trail: after the first partial, or in clear air once the gain reaches TRAIL_ON_W
        if self.part1 or self.part2 or (self.clear_air and R >= P["TRAIL_ON_W"] * self.W):
            hl = [z["lo"] - P["PIVOT_BUF"] * a for z in lm["zones"] if "L" in z["kinds"] and z["hi"] < c
                  and z["lo"] > self.entry_px]
            tr = max([self.peak - self.reg["trail_atr"] * a] + hl)
            self.trail = tr if self.trail is None else max(self.trail, tr)
        # 4. add the second half: a held retest or a breakout, until half the horizon
        if self.add_open and not self.part1 and self.days <= self.H * P["TIME_CHECK"]:
            lvl = self.retest
            held = lvl is not None and lvl <= c <= lvl + P["RETEST_BAND"] * a and R > -P["STOP_CONFIRM_W"] * self.W
            if held or breakout(lm, prev, strong):
                self.add_open = False
                self.frac = min(1.0, self.frac + 0.5)
                out.append((self.frac, "add_retest" if held else "add_breakout"))
        # 5. time: no progress by half the horizon halves it; the horizon ends it
        if self.days >= self.H:
            return out + [(0.0, "horizon")]
        if not self.halved and self.days >= self.H * P["TIME_CHECK"] and R < P["TIME_MIN_W"] * self.W:
            self.halved = True
            self.add_open = False
            self.frac *= 0.5
            out.append((self.frac, "time_halve"))
        return out
