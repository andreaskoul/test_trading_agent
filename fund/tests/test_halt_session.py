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
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("session_equity", "halt_series")]
    ns = {}
    exec(compile(ast.Module(fns, []), SRC, "exec"), ns)
    return ns["session_equity"], ns["halt_series"]


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


def test_reconcile_uses_the_session_series():
    src = open(SRC).read()
    assert "H = halt_series(hist, session, eq_s)" in src and "session_equity(broker.account()[\"cash\"]" in src
    assert "tz_convert(\"America/New_York\").date" in src         # sessions by New York date, not UTC


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
