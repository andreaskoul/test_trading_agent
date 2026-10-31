"""Contracts for Protocol 7B Amendment 2 (fund/amend7b2.py; PROTOCOL_fund.md).

    python fund/tests/test_amend7b2.py          (or pytest, if installed)

Fixtures: the 2026-10-28 cohort's real desk inputs and the frozen daily returns (fund/tests/fixtures/timing/). The
failure class is GOOGL: its earnings came after the 10-28 close, the desk's "already priced in" fraction was 0 and
its horizon 24 sessions, while the stock had moved about 12% against SPY by the entry decision on 10-29. The
release times below are the constructed after-close / before-open cases of that week; the 8-K times themselves are
read from EDGAR live.
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(HERE, "fixtures", "timing")
sys.path.insert(0, os.path.dirname(HERE))
import amend7b2 as A2                                             # noqa: E402

K = {"P_CAP": 1.5, "H_MIN": 3, "H8_MAX": 25, "STALE_AT": 2}      # Amendment 8's constants (fund/lifecycle.py)
R = pd.read_csv(os.path.join(FX, "base", "lifecycle", "returns.csv"), parse_dates=["date"]).pivot_table(
    index="date", columns="ticker", values="ret")
DAYS = list(R.index) + [pd.Timestamp("2026-10-30"), pd.Timestamp("2026-11-02")]
C = json.load(open(os.path.join(FX, "cohort_2026-10-28_entry.json")))
D, D0 = pd.Timestamp("2026-10-29"), pd.Timestamp("2026-10-28")


def test_release_session_from_8k_calendar_and_type():
    amc = [pd.Timestamp("2026-10-28 16:05")]                       # accepted after the close: the next session
    assert A2.release_session("earnings", "2026-10-28", amc, None, DAYS)["session"] == "2026-10-29"
    bmo = [pd.Timestamp("2026-10-28 07:01")]                       # before the open: that session
    assert A2.release_session("earnings", "2026-10-28", bmo, None, DAYS)["session"] == "2026-10-28"
    assert A2.release_session("guidance", "2026-10-28", [], ("2026-10-28", "amc"), DAYS)["source"] == "calendar amc"
    assert A2.release_session("guidance", "2026-10-28", [], ("2026-10-28", "amc"), DAYS)["session"] == "2026-10-29"
    assert A2.release_session("partnership", "2026-10-28", amc, None, DAYS) is None        # B1 is for earnings/guidance
    assert A2.release_session("earnings", "2026-10-28", [pd.Timestamp("2026-09-01 16:05")], None, DAYS) is None


def _info(t, session):
    return {"inputs": C["names"][t]["inputs"], "release": {"session": session, "source": "8-K 2.02"}}


def test_b1_googl_priced_in_at_entry():
    past, today = R[R.index < D], R.loc[D].to_dict()
    H, log = A2.b1_horizon("GOOGL", _info("GOOGL", "2026-10-29"), -1, past, C["beta"]["GOOGL"], today, D,
                           C["names"]["GOOGL"]["H"], K)
    assert log["p_desk"] == 0.0 and log["p_entry"] >= 1 and C["names"]["GOOGL"]["inputs"]["hard"]
    assert H == 3                                                  # hard news, priced in: Amendment 8's H = 3


def test_b1_msft_small_move_keeps_most_of_its_horizon():
    past, today = R[R.index < D], R.loc[D].to_dict()
    H, log = A2.b1_horizon("MSFT", _info("MSFT", "2026-10-29"), 1, past, C["beta"]["MSFT"], today, D,
                           C["names"]["MSFT"]["H"], K)
    assert 0 <= log["p_entry"] < 1 and K["H_MIN"] <= H <= C["names"]["MSFT"]["H"]
    assert H == min(max(round(C["names"]["MSFT"]["H"] * (1 - 0.5 * log["p_entry"])), 3), 25)


def test_b1_soft_priced_in_is_not_entered_and_no_release_changes_nothing():
    past, today = R[R.index < D], R.loc[D].to_dict()
    soft = {"inputs": {**C["names"]["GOOGL"]["inputs"], "hard": False}, "release": {"session": "2026-10-29"}}
    H, log = A2.b1_horizon("GOOGL", soft, -1, past, C["beta"]["GOOGL"], today, D, 24, K)
    assert H is None and "not entered" in log["b1"]
    H, log = A2.b1_horizon("GOOGL", {"inputs": C["names"]["GOOGL"]["inputs"], "release": None}, -1, past, 1.0, today, D, 24, K)
    assert H == 24 and log["b1"] == "not applicable"


def test_b2_lookback_only_from_the_amendment_date():
    lot = {"news_until": 1_800_000_000, "entry_close_ts": 1_790_000_000}
    assert A2.news_lo(lot, "2026-11-04", "2026-11-05") == 1_800_000_000          # recorded days unchanged
    assert A2.news_lo(lot, "2026-11-05", "2026-11-05") == 1_800_000_000 - 86400
    assert A2.news_lo({"entry_close_ts": 1_790_000_000}, "2026-11-05", "2026-11-05") == 1_790_000_000


def test_b2_selection_reads_late_articles_first_and_up_to_60():
    prev = 1_800_000_000
    late = [{"datetime": prev - 60 * k, "headline": f"late {k}"} for k in range(5, 0, -1)]
    new = [{"datetime": prev + 60 * k, "headline": f"new {k}"} for k in range(1, 81)]
    arts = late + new
    before = A2.select_articles(arts, prev, "2026-11-04", "2026-11-05")
    assert before == arts[-25:]                                   # Amendment 7 as recorded: the 25 newest
    after = A2.select_articles(arts, prev, "2026-11-05", "2026-11-05")
    assert len(after) == 60 and all(a in after for a in late)     # every late article, then the 55 newest
    assert [a for a in after if a in new] == new[-55:]
    assert A2.select_articles(arts, None, "2026-11-05", "2026-11-05") == arts[-60:]


def test_b3_verdicts():
    cand = {"A": (0.05, 1, {}), "B": (-0.04, -1, {}), "C": (0.03, 1, {}), "D": (0.02, 1, {})}
    out, log = A2.b3_apply(cand, {"A": {"verdict": "exit"}, "B": {"verdict": "reduce"}, "C": {"verdict": "increase"},
                                  "D": {"status": "news_unavailable"}})
    assert "A" not in out and out["B"][0] == -0.02 and out["C"][0] == 0.03 and out["D"][0] == 0.02
    assert "not entered" in log["A"] and "half" in log["B"] and "no change" in log["C"] and "D" not in log


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
