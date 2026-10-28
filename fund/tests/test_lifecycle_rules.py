"""Contracts for the Protocol 7B rules (fund/lifecycle_rules.py; PROTOCOL_fund.md, Protocol 7B).

    python fund/tests/test_lifecycle_rules.py          (or pytest, if installed)

Fixtures are real lots from the live record (fund-data, lifecycle/state.json, 2026-10-21/22), the cases that led
to the rules: news increases on losing lots (HPE, NKE, MRVL on 10-21) and capacity exits of carried lots (10-22).
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lifecycle_rules as LR                                     # noqa: E402

BEFORE, AFTER = pd.Timestamp("2026-10-21"), LR.P7B

# 10-21 news increases (R, W, days held) as recorded
INCREASES = {"HPE": -0.187273, "NKE": -0.079749, "MRVL": -0.105767, "CRM": -0.021008}
# 10-23 news increases on lots that were working
WORKING = {"TSLA": 0.002381, "CRM-short": 0.003798}


def test_r1_no_averaging_down():
    for t, R in INCREASES.items():
        assert LR.may_increase(BEFORE, {"R": R}), f"{t}: before P7B Amendment 7 stands"
        assert not LR.may_increase(AFTER, {"R": R}), f"{t}: from P7B no increase at R {R}"
    for t, R in WORKING.items():
        assert LR.may_increase(AFTER, {"R": R}), f"{t}: a working lot may still be increased"
    assert LR.may_increase(AFTER, {"R": 0.0})


def test_r2_checkpoint():
    lot = {"structural": True, "sigma_e": 0.02, "H": 63, "days": 20}
    # z = R / (0.02 * sqrt(20)) = R / 0.0894
    assert LR.checkpoint_exit(AFTER, {**lot, "R": -0.10})              # z -1.12: exit
    assert not LR.checkpoint_exit(AFTER, {**lot, "R": -0.05})          # z -0.56: hold
    assert not LR.checkpoint_exit(AFTER, {**lot, "R": -0.10, "days": 19})   # not a checkpoint day
    assert LR.checkpoint_exit(AFTER, {**lot, "R": -0.15, "days": 40})       # second checkpoint: z -1.19
    assert not LR.checkpoint_exit(AFTER, {**lot, "R": -0.10, "structural": False})
    assert not LR.checkpoint_exit(BEFORE, {**lot, "R": -0.10})
    assert not LR.checkpoint_exit(AFTER, {**lot, "R": -0.30, "days": 63})   # at the horizon the A8 review decides


def test_r2_structural_horizon():
    days = list(pd.bdate_range("2026-10-26", periods=120))
    t0 = days[3]                                                       # 2026-10-29
    h, why = LR.structural_h(15, ("2026-12-10", "bmo"), days, t0, days[3 + 30])
    assert h == 31, (h, why)                                           # 30 sessions to the report + 1
    h, _ = LR.structural_h(25, ("2026-11-05", "amc"), days, t0, days[3 + 6])
    assert h == 25                                                     # never below the Amendment 8 horizon
    h, _ = LR.structural_h(20, ("2027-03-01", ""), days, t0, days[3 + 85])
    assert h == LR.STRUCT_MAX                                          # capped at 63
    h, why = LR.structural_h(14, None, days, t0, None)
    assert h == LR.STRUCT_DEFAULT and "no dated report" in why


def test_r2_mean_over_samples():
    # dry run on as-of 2026-10-21 (real votes): HAS T T F F T with A8 horizons 3 and no dated report (40);
    # NFLX T T T F F, next report in 59 sessions (60); SMCI T F T F F, report in 3 sessions (A8 4 dominates)
    h, hs = LR.structural_mean([True, True, False, False, True], [3, 3, 3, 3, 3], 40)
    assert abs(h - 25.2) < 1e-9 and hs == [40, 40, 3, 3, 40]
    h, _ = LR.structural_mean([True, True, True, False, False], [3, 3, 3, 3, 3], 60)
    assert abs(h - 37.2) < 1e-9
    h, _ = LR.structural_mean([True] * 5, [10] * 5, 80)
    assert h == LR.STRUCT_MAX
    h, _ = LR.structural_mean([False] * 5, [14, 14, 13, 14, 15], 60)
    assert h == 14.0                                                   # no structural vote: the A8 mean stands


def test_r3_slots():
    # 10-22: carried 10-14 shorts (R, days, H) as recorded, and new 10-21 candidates with larger weights
    cur = {"BAC": {"R": 0.003524, "days": 5, "H": 6}, "DAL": {"R": -0.030457, "days": 5, "H": 11},
           "KHC": {"R": -0.081305, "days": 5, "H": 9}, "JPM": {"R": -0.011827, "days": 5, "H": 13}}
    target = {"BAC": -0.029, "DAL": -0.06, "KHC": -0.03, "JPM": -0.03}
    target.update({f"N{i}": -0.05 for i in range(10)})                # ten new shorts, all ranked above the carried
    key = {t: abs(w) * 0.2 if t in cur else abs(w) - 0.001 for t, w in target.items()}
    before = LR.slots(target, cur, key, BEFORE)
    after = LR.slots(target, cur, key, AFTER)
    assert "BAC" not in before and all(t not in before for t in cur)  # Amendment 7: every carried short loses its slot
    assert "BAC" in after                                             # 7B: the working lot inside its horizon stays
    assert all(t not in after for t in ("DAL", "KHC", "JPM"))         # losing lots still compete and lose
    assert len([t for t in after if target[t] < 0]) == LR.N_SIDE
    cur["BAC"]["days"] = 6                                            # at its horizon it is no longer protected
    assert "BAC" not in LR.slots(target, cur, key, AFTER)


def test_control_switch():
    # the shadow control (active=False) never applies 7B, whatever the date: HPE could still be increased on 10-21-like
    # terms, a failing structural lot is not checkpointed, and no carried lot is protected
    assert LR.may_increase(AFTER, {"R": INCREASES["HPE"]}, active=False)
    lot = {"structural": True, "sigma_e": 0.02, "H": 63, "days": 20, "R": -0.10}
    assert not LR.checkpoint_exit(AFTER, lot, active=False)
    cur = {"BAC": {"R": 0.003524, "days": 5, "H": 6}}
    target = {"BAC": -0.029, **{f"N{i}": -0.05 for i in range(10)}}
    key = {t: abs(w) * 0.2 if t in cur else abs(w) - 0.001 for t, w in target.items()}
    assert "BAC" not in LR.slots(target, cur, key, AFTER, active=False)


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"ok   {name}")
            except AssertionError as e:
                fails += 1; print(f"FAIL {name}: {e}")
    sys.exit(1 if fails else 0)
