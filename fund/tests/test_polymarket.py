"""Contract tests for the Polymarket source of the context archive (fund/polymarket.py), on a real saved response.

    python fund/tests/test_polymarket.py
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "fund"))
import polymarket as PM  # noqa: E402

EVENTS = json.load(open(os.path.join(ROOT, "fund", "tests", "fixtures", "polymarket", "events.json")))["events"]
OPEN, SPORT, RESOLVED, SMALL = EVENTS            # as saved: an open politics event, a sports event, a resolved Fed event, a tiny event


def test_selection_is_by_typed_fields():
    assert PM.wanted(OPEN) is True and PM.wanted(RESOLVED) is True
    assert PM.wanted(SPORT) is False              # tag slug, not the title
    assert PM.wanted(SMALL) is False              # volume below the floor
    e = copy.deepcopy(OPEN)
    del e["tags"]
    assert PM.wanted(e) is None                   # a missing typed field is a defect, not a guess


def test_rows_from_the_real_fixture():
    rows, defects, unlisted = PM.market_rows(EVENTS)
    assert not defects and unlisted == 1          # the placeholder slot is skipped, not stored and not a defect
    assert len(rows) == len(OPEN["markets"]) - 1 + len(RESOLVED["markets"])
    ids = {k.split("|")[0] for k, _, _ in rows}
    assert ids == {str(OPEN["id"]), str(RESOLVED["id"])}
    for key, published, p in rows:
        assert published and len(p["outcomes"]) == len(p["prices"]) >= 2
        assert all(0.0 <= x <= 1.0 for x in p["prices"]) and abs(sum(p["prices"]) - 1) <= 0.10
        assert p["event_volume"] >= PM.MIN_VOLUME and p["question"] and p["tags"]
    # the resolved event carries its outcome: a price of exactly 1 on one side
    res = [p for k, _, p in rows if k.startswith(str(RESOLVED["id"]) + "|")]
    assert all(max(p["prices"]) == 1.0 and p["closed"] is True for p in res)


def test_an_active_market_without_prices_is_a_defect_not_a_placeholder():
    e = copy.deepcopy(OPEN)
    e["markets"][0]["outcomePrices"] = None       # still active: the venue lists it, so missing prices are a fault
    rows, defects, unlisted = PM.market_rows([e])
    assert unlisted == 1 and len(defects) == 1 and "JSON" in defects[0]["why"]


def test_a_broken_market_is_a_defect_and_is_not_stored():
    for fault, why in (({"outcomePrices": '["1.4", "-0.4"]'}, "outside"), ({"outcomePrices": '["0.2", "0.2"]'}, "sum"),
                       ({"outcomePrices": "not json"}, "JSON"), ({"outcomes": '["Yes"]'}, "match"), ({"question": ""}, "id or question")):
        e = copy.deepcopy(OPEN)
        e["markets"][0].update(fault)
        rows, defects, _ = PM.market_rows([e])
        assert len(rows) == len(OPEN["markets"]) - 2 and len(defects) == 1 and why in defects[0]["why"], (fault, defects)


def test_a_response_that_is_mostly_broken_fails_loudly():
    e = copy.deepcopy(OPEN)
    for m in e["markets"]:
        m["outcomePrices"] = "not json"
    rows, defects, _ = PM.market_rows([e])
    try:
        PM.check(rows, defects)
    except RuntimeError as exc:
        assert "content contract" in str(exc)
    else:
        raise AssertionError("check() accepted a response in which every market is broken")
    PM.check(*PM.market_rows(EVENTS)[:2])         # the clean fixture passes


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
    print(f"{n} Polymarket source contracts hold")
