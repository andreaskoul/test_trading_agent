"""Contract test (2026-11-19, issues #169/#170): the lifecycle determinism check compares the two rebuilds' NAVs to
within half a cent, not by exact float equality. Fixture: the real values recorded in fund-data
fund_state/live/lifecycle/checks.json by the reconcile of 2026-11-19 (rebuild_diff.first_nav_diff)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lifecycle_rules import navs_match  # noqa: E402

FIRST, SECOND = 96664.81610178133, 96664.81610178131      # 2026-11-18, the two runs of the 2026-11-19 reconcile


def rows(*navs, dates=None):
    dates = dates or [f"2026-11-{16 + i:02d}" for i in range(len(navs))]
    return {"rows": [{"date": d, "nav": v} for d, v in zip(dates, navs)]}


def test_float_noise_passes():
    assert navs_match(rows(96000.0, FIRST), rows(96000.0, SECOND))


def test_a_cent_fails():
    assert not navs_match(rows(96000.0, FIRST), rows(96000.0, FIRST + 0.01))


def test_missing_or_moved_day_fails():
    assert not navs_match(rows(96000.0, FIRST), rows(96000.0))
    assert not navs_match(rows(96000.0, FIRST), rows(96000.0, FIRST, dates=["2026-11-16", "2026-11-19"]))


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
