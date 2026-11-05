"""Contracts for Protocol 9's SPY core (fund/core.py) and its account target.

    python fund/tests/test_core.py          (or pytest, if installed)

Fixtures:
* fund/tests/fixtures/core/spy_closes.csv: SPY's adjusted daily closes (Alpaca SIP), 2025-06-02 -> 2026-11-03.
* fund/tests/fixtures/halt/: the 2026-11-04 live record (the model's target) and the real account fields.
"""
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import core as C                                                  # noqa: E402

SPY = pd.read_csv(os.path.join(HERE, "fixtures", "core", "spy_closes.csv"), index_col=0, parse_dates=True)["SPY"]
REC = json.load(open(os.path.join(HERE, "fixtures", "halt", "live_2026-11-04.json")))
ACCT = json.load(open(os.path.join(HERE, "fixtures", "halt", "account_2026-11-05.json")))
DAY = pd.Timestamp("2026-11-04")                                  # decided on the 2026-11-03 close


def state(day=DAY, spy=SPY, path=None):
    path = path or os.path.join(tempfile.mkdtemp(), "state.json")
    return C.core_state(path, day, spy.index, spy.to_numpy()), path


def test_state_matches_a_hand_computation():
    st, _ = state()
    prev = SPY.loc[: DAY - pd.Timedelta(days=1)]
    ma = prev.iloc[-200:].mean()
    assert st["session"] == "2026-11-03" and abs(st["ma"] - round(ma, 4)) < 1e-9
    assert st["up"] == (prev.iloc[-1] > ma) and st["sleeve"] == (1.3 if prev.iloc[-1] > ma else 0.7)


def test_state_uses_no_close_from_the_day_itself():
    # the failure class: a decision at T-3 min must not see that session's close
    later = pd.concat([SPY, pd.Series([1.0], index=[DAY])])     # a crash on the decision day itself
    assert state(spy=later)[0] == state()[0]


def test_state_is_frozen_at_first_use():
    st, path = state()
    moved = SPY * 0.5                                             # revised history after the first use changes nothing
    assert C.core_state(path, DAY, moved.index, moved.to_numpy()) == st
    assert C.core_state(os.path.join(tempfile.mkdtemp(), "s.json"), SPY.index[150], SPY.index, SPY.to_numpy()) is None


def test_account_target_nets_spy():
    m = REC["target_weights"]
    a = C.account_target(m, 1.3)
    assert abs(a["SPY"] - (1.3 + m["SPY"] / 3)) < 1e-12
    assert all(abs(a[t] - m[t] / 3) < 1e-12 for t in m if t != "SPY")
    assert C.gross(a) <= C.GROSS_CAP                              # the real book at 1/3 fits under the core


def test_gross_guard_scales_only_the_overlay():
    big = {t: 6 * w for t, w in REC["target_weights"].items()}   # a model book six times today's size
    a, k = C.gross_guard(big, 1.3)
    assert k < C.LAMBDA and abs(C.gross(a) - C.GROSS_CAP) < 1e-6
    assert abs(a["SPY"] - (1.3 + k * big["SPY"])) < 1e-9          # the core's 1.3 is intact
    a0, k0 = C.gross_guard(REC["target_weights"], 1.3)
    assert k0 == C.LAMBDA and a0 == C.account_target(REC["target_weights"], 1.3)
    assert C.gross_guard({}, 0.7) == ({"SPY": 0.7}, C.LAMBDA)


def test_account_limits():
    assert C.account_limits(ACCT, 1.3) == (1.3, True, [])
    s, ov, p = C.account_limits({**ACCT, "shorting_enabled": False}, 1.3)
    assert s == 1.3 and not ov and p
    s, ov, p = C.account_limits({**ACCT, "multiplier": "1"}, 1.3)
    assert s == 1.0 and not ov and p


def test_qshadow_uses_the_same_rule():
    src = open(os.path.join(os.path.dirname(HERE), "qshadow.py")).read()
    assert "from core import SLEEVE_UP, SLEEVE_DOWN, TREND_WIN, trend_state" in src and "def trend_state" not in src


NAV = pd.read_csv(os.path.join(HERE, "fixtures", "core", "nav.csv"), parse_dates=["date"]).set_index("date")["equity"]
RSPY = pd.read_csv(os.path.join(HERE, "fixtures", "core", "spy_returns.csv"), parse_dates=["date"]).set_index("date")["ret"]


def test_yardsticks_by_hand():
    # the broker NAV and SPY's frozen returns since 1 Oct (fund-data, 2026-11-04)
    y = C.yardsticks(NAV, RSPY, start="2026-10-01")
    ra = NAV.pct_change().dropna().loc["2026-10-01":]
    assert y["sessions"] == len(ra) and abs(y["account"]["total"] - (NAV.iloc[-1] / NAV.loc[:"2026-09-30"].iloc[-1] - 1)) < 1e-12
    rs = RSPY.reindex(ra.index).fillna(0)
    assert abs(y["spy"]["total"] - ((1 + rs).prod() - 1)) < 1e-12
    assert abs(y["spy"]["per_year"] - ((1 + rs).prod() ** (252 / len(rs)) - 1)) < 1e-12
    s = pd.Series(1.3, index=ra.index)                            # a risk-matched line at 1.3x pays margin on 0.3x
    rm = C.yardsticks(NAV, RSPY, s, "2026-10-01")["risk_matched"]
    assert abs(rm["total"] - ((1 + 1.3 * rs - 0.3 * C.MARGIN_RATE / 252).prod() - 1)) < 1e-12 and rm["weight"] == 1.3


def test_composite_and_fidelity():
    idx = RSPY.index[-10:]
    s, rs, rmod = pd.Series(1.3, index=idx), RSPY.loc[idx], pd.Series(0.001, index=idx)
    net = pd.Series(0.15, index=idx)                              # overlay net weight 0.15 at lambda 1/3 -> debit 0.35
    c = C.composite(s, rs, rmod, net)
    assert np.allclose(c, 1.3 * rs + rmod / 3 - 0.35 * C.MARGIN_RATE / 252)
    f = C.fidelity(c, c)
    assert f and all(abs(v) < 1e-9 for v in f.values())
    f2 = C.fidelity(c + 0.0001, c)                                # one bp a session shows as roughly that many bp a month
    assert all(v > 0 for v in f2.values())


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
