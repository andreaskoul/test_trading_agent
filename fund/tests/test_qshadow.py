"""Contract tests for the research shadow books (fund/qshadow.py). Offline except the price download.

    python fund/tests/test_qshadow.py
"""

import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import qshadow as Q  # noqa: E402


def test_session_rule():
    S = pd.DatetimeIndex(pd.to_datetime(["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15"]))
    assert Q.session_of("2026-10-13T19:59:00Z", S) == pd.Timestamp("2026-10-13")      # 15:59 EDT
    assert Q.session_of("2026-10-13T20:00:00Z", S) == pd.Timestamp("2026-10-14")      # 16:00 EDT: next session
    assert Q.session_of("2026-10-11T15:00:00Z", S) == pd.Timestamp("2026-10-12")      # Sunday: Monday
    assert pd.isna(Q.session_of("2026-10-15T21:00:00Z", S))                           # past the calendar: wait


def test_risk_caps():
    sector = {t: "Energy" if t in ("XOM", "CVX", "COP", "OXY", "HAL") else "Tech" for t in Q.NAMES}
    w = pd.Series({"XOM": .1, "CVX": .1, "COP": .1, "OXY": .1, "HAL": .1, "AAPL": -.1, "MSFT": -.1, "NVDA": -.1,
                   "AMD": -.1, "MU": -.1})
    out, _ = Q.risk(w, sector, {t: 1.0 for t in Q.NAMES})
    s = pd.Series({k: v for k, v in out.items() if k != "SPY"})
    by = s.groupby(pd.Series(sector)).sum()
    assert (by.abs() <= Q.SECTOR_CAP + 1e-6).all()
    assert abs(s.sum()) <= Q.DOLLAR_CAP * s.abs().sum() + 1e-6
    assert abs(sum(v for v in s.values) + out.get("SPY", 0.0)) < 1e-4        # beta 1 names: SPY offsets the net


def test_prompt_is_m0_verbatim():
    src = "/Users/apollogodofthesun/caf_ml_v0/data/prep/m0.ipynb"
    if not os.path.exists(src):
        return
    nb = json.load(open(src))
    code = "".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    body = re.search(r'def build_prompt\(title: str, snippet: str, entity: str\) -> str:\n    return f"""(.*?)"""',
                     code, re.S).group(1)
    ours = Q.m0_prompt("{title}", "{snippet}", "{entity}")
    assert ours == body.replace("{{", "{").replace("}}", "}"), "prompt drifted from m0"


def test_sealed_window_never_in_targets():
    p = Q.Panel(pd.Timestamp("2026-10-16"))
    for h in (5, 10, 20):
        y = p.target(h)
        for d in np.where(np.isfinite(y).any(1))[0]:
            win = p.S[d: d + 2 + h]
            assert not ((win >= Q.SEALED[0]) & (win <= Q.SEALED[1])).any(), (h, p.S[d])
    assert p.n[(p.S >= Q.SEALED[0]) & (p.S <= Q.SEALED[1])].sum() == 0            # no text from the window


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
