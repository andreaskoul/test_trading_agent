"""Timing unit test for N4 features: planted headlines on the real session calendar.

    python research/tree/N4_news/test_timing.py
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import features as F  # noqa: E402
from features import harness  # noqa: E402


def frame(rows):
    return pd.DataFrame({"ts": pd.to_datetime([r[0] for r in rows], utc=True), "symbols": [r[1] for r in rows],
                         "headline": [r[2] for r in rows]})


def main():
    D = harness.load()
    S = D["S"]
    si = {d.date().isoformat(): i for i, d in enumerate(S)}
    # 1. session assignment (summer EDT = UTC-4, winter EST = UTC-5)
    cases = [("2019-06-06T19:59:00Z", "2019-06-06"),   # Thu 15:59 NY -> Thu
             ("2019-06-06T20:00:00Z", "2019-06-06"),   # Thu 16:00:00 NY exactly -> Thu (not after 16:00)
             ("2019-06-06T20:01:00Z", "2019-06-07"),   # Thu 16:01 NY -> Fri
             ("2019-06-08T14:00:00Z", "2019-06-10"),   # Sat -> Mon
             ("2019-06-07T03:00:00Z", "2019-06-06"),   # Thu 23:00 NY written as Fri UTC -> Fri session
             ("2019-01-10T21:00:30Z", "2019-01-11"),   # Thu 16:00:30 EST -> Fri
             ("2019-01-10T20:59:00Z", "2019-01-10"),   # Thu 15:59 EST -> Thu
             ("2019-07-04T15:00:00Z", "2019-07-05")]   # US holiday -> next session
    exp = {"2019-06-07T03:00:00Z": "2019-06-07"}         # (23:00 NY Thu is after the close: next session Fri)
    got = F.assign_sessions(pd.to_datetime(pd.Series([c[0] for c in cases]), utc=True), S)
    for (ts, want), k in zip(cases, got):
        want = exp.get(ts, want)
        assert k == si[want], (ts, S[k], want)
    # 2. planted headline after Thursday's close must not move any feature at rows <= Thursday
    names = ["AAA", "BBB"]
    base = frame([("2019-05-01T14:00:00Z", "AAA", "Acme upgraded to buy"),
                  ("2019-06-06T19:59:00Z", "AAA", "Acme beats estimates"),
                  ("2019-06-03T14:00:00Z", "BBB", "Bolt misses, shares fall"),
                  ("2019-06-03T14:00:00Z", "AAA,BBB", "Stocks With Most Active Options")])
    late = pd.concat([base, frame([("2019-06-06T20:01:00Z", "AAA", "Acme downgraded, lawsuit"),
                                   ("2019-06-07T15:00:00Z", "AAA", "Acme plunges")])], ignore_index=True)
    start = pd.Timestamp("2019-01-02")
    out = []
    for h in (base, late):
        heads = {"AAA": h[h.symbols.str.contains("AAA")].reset_index(drop=True),
                 "BBB": h[h.symbols.str.contains("BBB")].reset_index(drop=True)}
        out.append(F.raw_features(F.daily(heads, names, S), S, start=start))
    t = si["2019-06-06"]
    for k in out[0]:
        a, b = out[0][k][:t + 1], out[1][k][:t + 1]
        assert np.array_equal(np.isnan(a), np.isnan(b)) and np.allclose(np.nan_to_num(a), np.nan_to_num(b)), k
        assert not np.allclose(np.nan_to_num(out[0][k][t + 1:t + 3]), np.nan_to_num(out[1][k][t + 1:t + 3])) or k in (
            "multi21", "has5", "has21", "nov5", "nov21"), k   # Friday's features do see the late headlines
    f0 = out[0]
    assert f0["cnt1"][t, 0] == 1 and f0["cnt5"][t, 0] == 1 + 1, f0["cnt5"][t]        # Thu + Mon roundup
    assert f0["tone5"][t, 0] == 1.0                                                     # roundup excluded from tone
    assert f0["multi21"][t, 1] == 0.5 and f0["tone5"][t, 1] == -1.0
    assert f0["dsl"][t, 0] == 0 and f0["dsl"][t, 1] == 3
    print("timing test passed:", len(cases), "assignment cases; late headlines leave rows <= Thursday unchanged")


if __name__ == "__main__":
    main()
