"""Contract test (2026-11-24): the risk halts (10% drawdown from peak, 5% over 5 sessions) read the session just closed.

Incident. The reconcile runs at about 01:10 UTC and read only the broker's daily equity history, which at that hour
ends a session earlier. The account's equity fell to 87,702.83 at the 2026-11-20 close (drawdown 12.62% from the
10-09 peak of 100,372.87; 5-session change -8.37%): the halt should have been written at the 01:11 UTC reconcile on
11-21, and the account flat at the 11-23 close. The history then ended at 11-19 (drawdown 8.19%, week -4.29%: no
trip). The HALT file was written only on 11-24 01:11:51, and the account went flat at the 11-24 close, a session late
(-$356.85 that time). research/exec_recon/REPORT.md (branch research/exec-recon-20261124), defect 1.

Real fixture: the broker's daily equity, 2026-10-01..11-23, by New York session date (ledger_recon.csv
equity_broker_history; the rebuild from executions equals it to the cent on all 38 sessions), and the 11-20 close
equity rebuilt as cash 27,955.13 + holdings 59,747.70 at the SIP close.

execute.py runs at import, so the functions are taken from its source, as test_sip_close_query does.
"""
import ast
import os
from datetime import date

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "execute.py")
HIST = [("2026-10-01", 99999.89), ("2026-10-02", 99968.23), ("2026-10-05", 99986.53), ("2026-10-06", 100026.93),
        ("2026-10-07", 100100.07), ("2026-10-08", 100051.96), ("2026-10-09", 100372.87), ("2026-10-12", 99660.46),
        ("2026-10-13", 99625.25), ("2026-10-14", 98792.4), ("2026-10-15", 98144.96), ("2026-10-16", 97920.66),
        ("2026-10-19", 98431.86), ("2026-10-20", 98068.58), ("2026-10-21", 98528.21), ("2026-10-22", 97134.66),
        ("2026-10-23", 97550.24), ("2026-10-26", 97728.81), ("2026-10-27", 99040.77), ("2026-10-28", 99075.08),
        ("2026-10-29", 98257.85), ("2026-10-30", 98075.35), ("2026-11-02", 96232.54), ("2026-11-03", 96306.26),
        ("2026-11-04", 95717.96), ("2026-11-05", 95102.43), ("2026-11-06", 96426.81), ("2026-11-09", 96509.37),
        ("2026-11-10", 96382.53), ("2026-11-11", 95940.41), ("2026-11-12", 96277.02), ("2026-11-13", 95712.2),
        ("2026-11-16", 96161.7), ("2026-11-17", 94941.02), ("2026-11-18", 94585.4), ("2026-11-19", 92149.55),
        ("2026-11-20", 87702.83), ("2026-11-23", 90285.19)]
HIST = [(date.fromisoformat(d), e) for d, e in HIST]


def load():
    tree = ast.parse(open(SRC).read())
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("session_equity", "halt_series", "halt_fallback_equity")]
    consts = [n for n in tree.body if isinstance(n, ast.Assign) and any(getattr(x, "id", "") == "HALT_FALLBACK_HAIRCUT" for x in n.targets)]
    ns = {}
    exec(compile(ast.Module(consts, []), SRC, "exec"), ns)
    exec(compile(ast.Module(fns, []), SRC, "exec"), ns)
    return ns["session_equity"], ns["halt_series"]


def load_fallback():
    load()
    tree = ast.parse(open(SRC).read())
    nodes = [n for n in tree.body if (isinstance(n, ast.Assign) and any(getattr(x, "id", "") == "HALT_FALLBACK_HAIRCUT" for x in n.targets))
             or (isinstance(n, ast.FunctionDef) and n.name == "halt_fallback_equity")]
    ns = {}
    exec(compile(ast.Module(nodes, []), SRC, "exec"), ns)
    return ns["halt_fallback_equity"], ns["HALT_FALLBACK_HAIRCUT"]


def stats(series):
    e = [x for _, x in series]
    return 1 - e[-1] / max(e), e[-1] / e[max(0, len(e) - 6)] - 1


def trips(series):
    dd, wk = stats(series)
    return dd >= 0.10 or wk <= -0.05


def test_the_11_21_reconcile_trips_on_the_11_20_close():
    _, halt_series = load()
    before = [h for h in HIST if h[0] <= date(2026, 11, 19)]       # what the broker served at 01:11 UTC on 11-21
    old = halt_series(before, None, None)                         # the old behaviour: history only
    assert not trips(old)                                         # failure control: 8.19%, -4.29%
    new = halt_series(before, date(2026, 11, 20), 27955.13 + 59747.70)
    dd, wk = stats(new)
    assert new[-1][0] == date(2026, 11, 20) and trips(new)
    assert abs(dd - 0.1262) < 5e-4 and abs(wk - (-0.0837)) < 5e-4  # = the HALT file written a session late


def test_no_duplicate_when_the_broker_has_the_session():
    _, halt_series = load()
    s = halt_series(HIST, date(2026, 11, 23), 1.0)                # broker already serves 11-23: its value stands
    assert s == HIST


def test_session_equity_is_cash_plus_shares_at_the_close():
    session_equity, _ = load()
    assert session_equity(1000.0, {"SPY": 2, "AAPL": -1, "XOM": 0}, {"SPY": 689.81, "AAPL": 354.07}) == \
        1000.0 + 2 * 689.81 - 354.07
    assert session_equity(1000.0, {"SPY": 2, "AAPL": -1}, {"SPY": 689.81}) is None      # a missing close: no guess
    assert session_equity("27955.13", {}, {}) == 27955.13                                # flat account: the cash


def test_missing_close_falls_back_conservatively_not_to_stale_history():
    """Real fixture: the live equity read at the 11-21 01:11 UTC reconcile was 87,752.49 (close equity 87,702.83).
    Live marks overstated the close by up to +91.8 bp (11-18: 95,453.69 against 94,585.40), so the haircut must exceed
    that: the fallback is then below the close equity on every reconcile observed, and the 11-20 halt still trips."""
    fallback, haircut = load_fallback()
    _, halt_series = load()
    assert haircut > 0.0092
    observed = [(87752.49, 87702.83), (95453.69, 94585.40), (92078.56, 92149.55), (90540.79, 90285.19)]  # live, close
    assert all(fallback(live) <= close for live, close in observed)
    before = [h for h in HIST if h[0] <= date(2026, 11, 19)]
    assert trips(halt_series(before, date(2026, 11, 20), fallback(87752.49)))


def test_reconcile_uses_the_session_series():
    src = open(SRC).read()
    assert "H = halt_series(hist, session, eq_s)" in src and "session_equity(acct[\"cash\"]" in src
    assert "tz_convert(\"America/New_York\").date" in src         # sessions by New York date, not UTC
    assert "eq_s = halt_fallback_equity(acct[\"equity\"])" in src    # a missing close never leaves the stale history


def test_valuation_hold_never_adds_exposure():
    """No new exposure while a session is unvalued: shrink or close only (owner, 2026-11-25)."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from lifecycle_rules import hold_qty
    cases = {(0, 10): 0, (0, -10): 0,            # no opening
             (10, 15): 10, (-10, -15): -10,      # no enlarging
             (10, 4): 4, (-10, -4): -4,          # shrinking passes
             (10, 0): 0, (-10, 0): 0,            # closing passes
             (10, -5): 0, (-10, 5): 0}           # a flip only closes
    for (cq, tq), want in cases.items():
        assert hold_qty(cq, tq) == want, (cq, tq, hold_qty(cq, tq))
        assert abs(hold_qty(cq, tq)) <= abs(cq)


def test_hold_is_set_by_the_fallback_and_applied_by_the_trade_path():
    src = open(SRC).read()
    lc = open(os.path.join(os.path.dirname(SRC), "lifecycle.py")).read()
    assert 'if src.startswith("broker history + account equity"):' in src and '"VALUATION_HOLD"' in src
    assert "if vhold:\n            tq = LR.hold_qty(cq, tq)" in lc and '"VALUATION_HOLD"' in lc
    assert "never late" not in src                                   # the fallback is conservative, not guaranteed


def test_every_order_path_is_held_in_broker_send():
    """Owner acceptance check (2026-11-25): the hold applies to every order-producing path. All orders (weekly
    execution and reviews, the lifecycle book, the SPY core and hedge, the fill test) go through broker.send."""
    import glob
    import re
    fund = os.path.dirname(SRC)
    callers = sorted(os.path.basename(f) for f in glob.glob(os.path.join(fund, "*.py"))
                     if re.search(r"broker\.send\(|\bsend\(orders", open(f).read()) and not f.endswith("broker.py"))
    assert callers == ["execute.py", "lifecycle.py"], callers
    posts = [f for f in glob.glob(os.path.join(fund, "*.py")) if '"POST", "/v2/orders"' in open(f).read()]
    assert [os.path.basename(f) for f in posts] == ["broker.py"], posts       # no order bypasses send
    b = open(os.path.join(fund, "broker.py")).read()
    i = b.index("def send(")
    assert b.index("hold = valuation_hold()", i) < b.index("def submit(", i)   # before any submission


def test_hold_filter_on_a_day_of_orders():
    import sys
    sys.path.insert(0, os.path.dirname(SRC))
    from lifecycle_rules import hold_filter
    cur = {"SPY": 120, "AAPL": 10, "XOM": -20}
    orders = [{"symbol": "SPY", "leg": "rebalance", "side": "buy", "qty": 30},     # core up: blocked
              {"symbol": "AAPL", "leg": "open", "side": "sell", "qty": 5},        # flip, open leg: blocked
              {"symbol": "AAPL", "leg": "flatten", "side": "sell", "qty": 10},    # flip, flatten leg: passes
              {"symbol": "XOM", "leg": "rebalance", "side": "buy", "qty": 8},     # short shrinks: passes
              {"symbol": "MSFT", "leg": "rebalance", "side": "buy", "qty": 4},    # new name: blocked
              {"symbol": "SPY", "leg": "close", "side": "sell", "qty": 50}]       # core down: passes
    hold_filter(orders, cur)
    assert [o["qty"] for o in orders] == [0, 0, 10, 8, 0, 50], [o["qty"] for o in orders]
    assert [bool(o.get("hold")) for o in orders] == [True, True, False, False, True, False]


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
