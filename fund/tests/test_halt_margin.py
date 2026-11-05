"""Contracts for the risk halt and the pre-trade margin check in the trading path (fund/lifecycle.py trade).

    python fund/tests/test_halt_margin.py          (or pytest, if installed)

The failure class (found 2026-11-05): under Protocol 7, execute.py reconcile writes fund_state/live/HALT after a 10%
drawdown or a 5% week, but lifecycle.trade() never read it, so a halt would not have stopped trading. Nothing
checked the account's margin either.

Fixtures (fund/tests/fixtures/halt/): the 2026-11-04 live record on fund-data, trimmed to the decision fields, and
five fields of the paper account read on 2026-11-05.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(HERE, "fixtures", "halt")
sys.path.insert(0, os.path.dirname(HERE))
import ops_stats as O                                             # noqa: E402

REC = json.load(open(os.path.join(FX, "live_2026-11-04.json")))
ACCT = json.load(open(os.path.join(FX, "account_2026-11-05.json")))


def lots():
    """The model's lots as trade() sees them (n = notional), rebuilt from the record's weights."""
    return [{"ticker": L["ticker"], "n": L["w"] * REC["nav_model"]} for L in REC["lots_after"]]


def test_target_reproduces_the_record():
    t = O.account_target(lots(), REC["nav_model"], REC["hedge_w"] * REC["nav_model"], halted=False)
    assert set(t) == set(REC["target_weights"])
    assert all(abs(t[k] - REC["target_weights"][k]) < 1e-12 for k in t)


def test_halt_is_flat():
    assert O.account_target(lots(), REC["nav_model"], REC["hedge_w"] * REC["nav_model"], halted=True) == {}


def test_margin_on_the_real_account():
    m = O.margin_check(ACCT, REC["target_weights"])
    assert m["problems"] == [] and 0.9 < m["gross"] < 1.0 and m["multiplier"] == 4 and m["shorting_enabled"]


def test_margin_flags():
    big = {k: 2 * v for k, v in REC["target_weights"].items()}               # the same book at twice the size: 1.94x
    big["AAPL"] = big.get("AAPL", 0) + 0.05
    assert any("above 1.95x" in p for p in O.margin_check(ACCT, big)["problems"])
    no_short = {**ACCT, "shorting_enabled": False}
    assert any("shorting is disabled" in p for p in O.margin_check(no_short, REC["target_weights"])["problems"])
    cash = {**ACCT, "multiplier": "1"}
    lev = {k: 1.5 * v for k, v in REC["target_weights"].items()}
    assert any("multiplier is 1" in p for p in O.margin_check(cash, lev)["problems"])
    assert O.margin_check(ACCT, {})["problems"] == []                        # a halted, flat target is always fine


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
