"""Contracts for the horizon-end review's decision (PROTOCOL_fund.md, Amendments 8 B and 9).

    python fund/tests/test_review_rules.py          (or pytest, if installed)

The fixtures are the five real reviews of the 2026-10-26 plan run (live prices and news; labels by three samples,
every quote found verbatim in its article). That run found the Amendment 9 defect: XOM, z 1.60 with CONFIRMING news
and earnings 4 sessions away, exited by rule 5 although rule 3 exempts exactly that case.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from review_rules import review_rule      # noqa: E402

P = dict(z_hi=1.5, id_hi=0.1, to_lo=1.0)  # pre-registered (Amendment 8 B)

# ticker: (kill_hit, label, z, ID, TO, catalyst within reach) -> (decision, rule), from the 2026-10-26 plan run
REAL = {
    "WMT":  ((False, "STALE", -0.480, -1.0, 0.922, False), ("exit", 2)),
    "MMM":  ((False, "STALE", -0.978, -1.0, 1.978, False), ("exit", 2)),
    "XOM":  ((False, "CONFIRMING", 1.596, -1.0, 0.900, True), ("extend", 5)),   # exited before Amendment 9
    "CRM":  ((False, "STALE", 0.501, -1.0, 0.647, False), ("exit", 5)),
    "AVGO": ((False, "CONTRADICTING", -0.716, -1.0, 0.891, False), ("exit", 1)),
}


def test_real_reviews():
    for t, (x, want) in REAL.items():
        got = review_rule(*x, **P)
        assert got == want, f"{t}: {got} != {want}"


def test_strong_move_with_support_extends():
    assert review_rule(False, "CONFIRMING", 2.4, 0.0, 1.2, False, **P) == ("extend", 5)
    assert review_rule(False, "STALE", 2.4, 0.0, 1.2, True, **P) == ("extend", 5)


def test_strong_move_without_support_exits():
    # rule 3: neither CONFIRMING nor a catalyst; a smooth path on rising turnover does not save it
    assert review_rule(False, "STALE", 2.4, -1.0, 1.5, False, **P) == ("exit", 3)
    assert review_rule(False, "NONE", 1.5, -1.0, 1.5, False, **P) == ("exit", 3)


def test_contradiction_and_kill_always_exit():
    assert review_rule(False, "CONTRADICTING", 2.4, -1.0, 1.5, True, **P) == ("exit", 1)
    assert review_rule(True, "CONFIRMING", 2.4, -1.0, 1.5, True, **P) == ("exit", 1)


def test_unchanged_below_z_hi():
    # Amendment 9 changes only z >= z_hi; between 0 and z_hi the Amendment 8 rule stands
    assert review_rule(False, "STALE", 0.8, -0.2, 1.1, False, **P) == ("extend", 5)
    assert review_rule(False, "STALE", 0.8, 0.0, 0.9, False, **P) == ("exit", 5)
    assert review_rule(False, "STALE", 0.8, 0.3, 0.9, False, **P) == ("exit", 4)
    assert review_rule(False, "CONFIRMING", 0.8, 0.3, 0.9, False, **P) == ("extend", 5)


def test_earnings_hold():
    # Protocol 7B Amendment 1 (owner 2026-10-28): a losing lot with earnings expected stays open; after the report it
    # closes only if the thesis is structurally changed (rule 1). Real fixture: WMT (10-26 plan run, z -0.48, STALE,
    # earnings 2026-11-19 within the cap) exited by rule 2 under Amendment 9; with the hold it is extended past the report.
    assert review_rule(False, "STALE", -0.480, -1.0, 0.922, False, **P) == ("exit", 2)
    assert review_rule(False, "STALE", -0.480, -1.0, 0.922, False, **P, earnings_hold=True, report_within_cap=True) == ("extend", "E1")
    # after the report: not contradicted -> kept; contradicted or a kill condition -> closed
    assert review_rule(False, "NONE", -0.9, 0.3, 0.8, False, **P, earnings_hold=True, after_report=True) == ("extend", "E2")
    assert review_rule(False, "CONTRADICTING", -0.9, 0.3, 0.8, False, **P, earnings_hold=True, after_report=True) == ("exit", 1)
    assert review_rule(True, "NONE", -0.9, 0.3, 0.8, False, **P, earnings_hold=True, report_within_cap=True) == ("exit", 1)
    # no report in reach and not held for one: Amendment 9 as before
    assert review_rule(False, "STALE", -0.480, -1.0, 0.922, False, **P, earnings_hold=True) == ("exit", 2)
    # the hold is for losing lots only; a winner keeps the Amendment 9 rules
    assert review_rule(False, "STALE", 0.501, -1.0, 0.647, False, **P, earnings_hold=True, report_within_cap=True) == ("exit", 5)
    # the shadow control never holds
    assert review_rule(False, "STALE", -0.480, -1.0, 0.922, False, **P, earnings_hold=False, report_within_cap=True) == ("exit", 2)


def test_losers_are_not_extended_without_a_catalyst():
    assert review_rule(False, "CONFIRMING", -0.1, -1.0, 1.5, False, **P) == ("exit", 2)
    assert review_rule(False, "CONFIRMING", 0.0, -1.0, 1.5, False, **P) == ("exit", 2)


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"ok   {name}")
            except AssertionError as e:
                fails += 1; print(f"FAIL {name}: {e}")
    sys.exit(1 if fails else 0)
