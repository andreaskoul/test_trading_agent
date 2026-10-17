"""Contract tests for fund/guards.py, on real SEC filings saved as fixtures (no network, no keys).

    python fund/tests/test_guards.py        # or: python -m pytest fund/tests/test_guards.py

Each test pins a failure that happened (R5, 2026-10-15/16) or the guard that prevents it.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("OPENROUTER_API_KEY", "test")          # common.py only reads it at call time

import guards  # noqa: E402

FIX = os.path.join(HERE, "fixtures")
read = lambda f: open(os.path.join(FIX, f), encoding="utf-8", errors="replace").read()
# the press release each filing really holds (EX-99.1 in its index), and the file the v1 name rule fell back to
EXPECTED = {"cfg": "a2q26earningsrelease.htm", "pnc": "q32026financialhighlightsa.htm",
            "trv": "a991pressrelease63026.htm", "aa": "aa-ex99_1.htm"}


def test_exhibit_is_chosen_by_declared_type_never_the_8k():
    for firm, name in EXPECTED.items():
        docs = guards.filing_documents(read(f"{firm}_index.html"))
        assert any(d["type"] == "8-K" for d in docs), f"{firm}: the index should list the 8-K itself"
        doc, how = guards.typed_exhibit(docs)
        assert doc is not None and doc["name"] == name, f"{firm}: chose {doc and doc['name']} ({how}), want {name}"
        assert doc["type"].startswith("EX-99"), how


def test_no_exhibit_is_a_defect_not_a_fallback():
    docs = [{"seq": "1", "description": "8-K", "name": "x-8k.htm", "type": "8-K", "size": "1"}]
    doc, how = guards.typed_exhibit(docs)
    assert doc is None and "no EX-99" in how


def test_cover_pages_fail_the_release_contract():
    for firm in EXPECTED:                                   # CFG, PNC and TRV fed v1 cards exactly this text
        assert guards.release_check(read(f"{firm}_8k_primary.txt")) is not None, firm


def test_real_releases_pass_the_release_contract():
    for firm in EXPECTED:
        assert guards.release_check(read(f"{firm}_release_head.txt")) is None, firm


def test_grounding_rejects_invented_numbers_and_accepts_real_ones():
    src = read("cfg_release_head.txt")
    real = " ".join(sorted(guards.numbers(src))[:8])
    ok, st = guards.grounding(real, src)
    assert ok and st["share"] == 1.0
    ok, st = guards.grounding("net interest margin 9.87%, revenue $123.45 billion, EPS $77.31, loans up 41.2%", src)
    assert not ok and st["found"] < st["numbers"]
    ok, st = guards.grounding("margins improved", src)            # too few numbers to check: accepted, and said so
    assert ok and st["numbers"] == 0


def test_years_and_single_digits_are_not_evidence():
    assert guards.numbers("in 2026 the 3 segments grew 12.5% to $1,234 million") == {"12.5", "1234"}


def test_quality_gate():
    assert guards.quality_gate(["ok"] * 9 + ["ledger_failed"])[0]
    ok, q = guards.quality_gate(["ok"] * 13 + ["input_defect"] * 6 + ["card_failed"])     # the 10-15/16 v1 reality
    assert not ok and q["bad"] == 7 and q["bad_share"] == 0.35
    assert guards.quality_gate(["card_failed", "ok", "already_reported"])[0]         # too small to gate
    assert guards.quality_gate(["already_reported"] * 10)[1]["attempted"] == 0


def test_guarded_llm_logs_rejections_and_repairs_once():
    calls = []

    def fake(system, user, check=None, tries=3, temperature=0.0):
        calls.append(user)
        out = {"drivers": []} if len(calls) == 1 else {"drivers": [{"id": "D1", "name": "x"}]}
        e = check(out)
        return ("ok", out, {"provider": "fake"}, None) if e is None else ("failed", None, {}, e)

    real, guards.llm = guards.llm, fake
    try:
        chk = lambda o: None if o.get("drivers") else "drivers: empty"
        st, out, meta, err, log = guards.guarded_llm("sys", "user", chk)
        assert st == "ok" and log["repaired"] and log["attempts"][0]["kind"] == "schema"
        assert "REJECTED BY THE VALIDATOR: drivers: empty" in calls[1]
    finally:
        guards.llm = real


def test_guarded_llm_records_transport_errors():
    real = guards.llm
    guards.llm = lambda *a, **k: ("failed", None, {}, "IncompleteRead(0 bytes read)")
    try:
        st, out, meta, err, log = guards.guarded_llm("sys", "user", lambda o: None)
        assert st == "failed" and log["attempts"] == [{"kind": "transport", "error": "IncompleteRead(0 bytes read)"}]
        assert not log["repaired"]                       # transport failures are re-run by the caller, not "repaired"
    finally:
        guards.llm = real


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in tests:
        f()
        print(f"ok  {f.__name__}")
    print(f"{len(tests)} guard contracts hold")
