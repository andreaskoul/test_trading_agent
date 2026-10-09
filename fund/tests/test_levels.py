"""Checks for the technicals desk's level map and rule policy, on synthetic series.

    python fund/tests/test_levels.py          (or pytest, if installed)
"""

import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import levels as LV                       # noqa: E402
import tech_policy as TP                  # noqa: E402


def bars_from_close(c, spread=0.01, vol=1e6, seed=0):
    rng = np.random.default_rng(seed)
    c = np.asarray(c, float)
    o = np.r_[c[0], c[:-1]]
    hi = np.maximum(o, c) * (1 + spread * rng.uniform(0.2, 1, len(c)))
    lo = np.minimum(o, c) * (1 - spread * rng.uniform(0.2, 1, len(c)))
    v = vol * rng.uniform(0.7, 1.3, len(c))
    idx = pd.bdate_range("2024-01-02", periods=len(c))
    return pd.DataFrame({"open": o, "high": hi, "low": lo, "close": c, "volume": v}, index=idx)


def range_series(n=300, lo=90.0, hi=110.0, period=40):
    """A price oscillating between lo and hi: pivots should cluster into zones near both."""
    x = np.arange(n)
    return lo + (hi - lo) * (0.5 + 0.5 * np.sin(2 * np.pi * x / period))


def test_zones_in_a_range():
    b = bars_from_close(range_series())
    ch = LV.Chart(b)
    lm = ch.levels(b.index[-1])
    strong = [z for z in lm["zones"] if z["strength"] >= LV.P["STRONG"]]
    assert any(abs(z["mid"] - 110) < 2.5 for z in strong), [(z["mid"], z["strength"]) for z in strong]
    assert any(abs(z["mid"] - 90) < 2.5 for z in strong), [(z["mid"], z["strength"]) for z in strong]


def test_no_lookahead_truncation():
    """The map at day t must not change when later bars exist."""
    rng = np.random.default_rng(3)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.015, 400)))
    b = bars_from_close(c, seed=3)
    for t in (b.index[260], b.index[320], b.index[-30]):
        full = LV.Chart(b).levels(t)
        cut = LV.Chart(b.loc[:t]).levels(t)
        strip = lambda m: {k: v for k, v in m.items() if k != "_profile"}
        assert strip(full) == strip(cut), f"look-ahead at {t.date()}"


def test_avwap_by_hand():
    b = bars_from_close(np.linspace(100, 120, 60))
    ch = LV.Chart(b)
    s, t = b.index[40], b.index[50]
    seg = b.loc[s:t]
    tp = (seg.high + seg.low + seg.close) / 3
    assert abs(ch.avwap(s, t) - float((tp * seg.volume).sum() / seg.volume.sum())) < 1e-9


def test_mirror_is_exact():
    """A short's map is the long map of the mirrored chart: distances in ATR are the same."""
    rng = np.random.default_rng(5)
    c = 50 * np.exp(np.cumsum(rng.normal(0, 0.02, 300)))
    b = bars_from_close(c, seed=5)
    m = LV.mirror(b)
    a = LV.Chart(b, side=-1).levels(b.index[-1])
    z = LV.Chart(m, side=1).levels(b.index[-1])
    assert [q["dist_atr"] for q in a["zones"]] == [q["dist_atr"] for q in z["zones"]]
    assert abs(a["atr"] - z["atr"]) < 1e-12


def test_round_levels():
    r = LV.round_levels(101.3, 6)
    assert {x["price"] for x in r} >= {100, 105} and any(x["price"] == 100 and x["major"] for x in r)
    rn = LV.round_levels(-101.3, 6)
    assert {x["price"] for x in rn} >= {-100, -105}


def test_event_candle_and_invalidation():
    c = np.r_[np.full(250, 100.0) + np.random.default_rng(1).normal(0, 0.3, 250), 108, 109, 110]
    b = bars_from_close(c, seed=1)
    b.loc[b.index[250], ["open", "low", "high", "volume"]] = [106, 105.5, 108.5, 5e6]      # gap-up news day
    ch = LV.Chart(b)
    lm = ch.levels(b.index[-1], event_day=b.index[250])
    ev = lm["event"]
    assert ev and ev["gap_atr"] > 3 and ev["relvol"] > 3 and not ev["gap_filled"]
    assert not TP.invalidated(lm)
    b2 = b.copy()
    b2.loc[b2.index[-1], ["close", "low", "open"]] = [104, 103.5, 105]               # back below the news-day low
    lm2 = LV.Chart(b2).levels(b2.index[-1], event_day=b2.index[250])
    assert TP.invalidated(lm2)
    assert TP.plan_entry(lm2, W_px=3.0, priced_z=0.5)["action"] == "skip_invalidated"


def test_stop_is_beyond_structure_and_clamped():
    b = bars_from_close(range_series(), seed=2)
    ch = LV.Chart(b)
    t = b.index[-1]
    lm = ch.levels(t)
    W_px = 0.04 * lm["close"]
    st = TP.structural_stop(lm, W_px, 2.0)
    assert 1.0 - 1e-9 <= st["dist_w"] <= 2.5 + 1e-9
    assert st["level"] < lm["close"]


def test_policy_clear_air_and_trail():
    """A steady uptrend at new highs: clear air, no fixed target, the trail follows."""
    c = 100 * np.exp(np.linspace(0, 0.5, 320))
    b = bars_from_close(c, seed=4)
    ch = LV.Chart(b)
    lm = ch.levels(b.index[300])
    plan = TP.plan_entry(lm, W_px=0.03 * lm["close"], priced_z=0.5)
    assert plan["room"]["clear_air"] and plan["room"]["target"] is None
    lot = TP.Lot(plan, lm, W=0.03, H=15, reg=TP.regime(True, 0.7, 0.5))
    R, prev, acts = 0.0, lm, []
    for d in b.index[301:316]:
        l2 = ch.levels(d)
        R += math.log(l2["close"] / prev["close"])
        acts += lot.step(l2, R, prev, 0.5)
        prev = l2
    assert lot.trail is not None or plan["action"] != "full"
    assert acts[-1][1] in ("horizon", "trail") or lot.frac > 0


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"ok   {name}")
            except AssertionError as e:
                fails += 1; print(f"FAIL {name}: {e}")
    sys.exit(1 if fails else 0)
