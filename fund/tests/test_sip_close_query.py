"""Contract test (2026-11-20): the reconcile's second close source (Alpaca SIP daily bar) asks for the session's own
date only. With end = day + 1, Alpaca read the date-only end as the whole of the next day, still in the future at the
01:10 UTC reconcile, and refused every request with 403 "subscription does not permit querying recent SIP data"; all
258 priced fills since 2026-10-01 have an empty close_alpaca. Real fixture: the request and answers observed on
2026-11-20 (end 2026-11-20 -> 403; end 2026-11-19 -> 200 with the 2026-11-19 bar, AAPL c 349.21, SPY c 715.87).
execute.py runs at import, so the function is taken from its source, as test_p11 does for catalyst_session."""
import ast
import os
from urllib.parse import parse_qs, urlparse

import pandas as pd

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "execute.py")


def load():
    tree = ast.parse(open(SRC).read())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "sip_close_query")
    ns = {"pd": pd}
    exec(compile(ast.Module([fn], []), SRC, "exec"), ns)
    return ns["sip_close_query"]


def params(q):
    return {k: v[0] for k, v in parse_qs(urlparse(q).query).items()}


def test_window_is_the_session_itself():
    p = params(load()(["AAPL", "SPY"], pd.Timestamp("2026-11-19")))
    assert p["start"] == "2026-11-19" and p["end"] == "2026-11-19"          # end 2026-11-20 was refused (403)
    assert p["symbols"] == "AAPL,SPY" and p["feed"] == "sip" and p["adjustment"] == "raw" and p["timeframe"] == "1Day"


def test_status_is_logged_not_swallowed():
    src = open(SRC).read()
    assert "if s_ != 200:" in src and "Alpaca closes unavailable (HTTP" in src


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
