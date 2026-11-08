"""Contract tests for Protocol 10 (fund/lifecycle_rules.py: hedge_beta; fund/screen.py: beta_b1).

    python fund/tests/test_p10.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "fund"))
import lifecycle_rules as LR  # noqa: E402

LOTS = [{"ticker": "AAA", "n": 10_000.0, "beta": 1.2}, {"ticker": "BBB", "n": -6_000.0, "beta": 0.8},
        {"ticker": "CCC", "n": 4_000.0, "beta": 1.0}]
HB = {"AAA": 1.5, "BBB": 0.4}                                   # CCC has no B1


def test_before_p10_the_hedge_is_the_lot_beta_exactly():
    d = LR.P10 - pd.Timedelta(days=1)
    old = sum(L["n"] * L["beta"] for L in LOTS)                  # the pre-Protocol-10 expression
    assert LR.hedge_beta(LOTS, HB, d) == old                     # bit-identical: recorded days and rebuilds unchanged


def test_from_p10_the_hedge_uses_b1_and_falls_back_to_the_lot_beta():
    got = LR.hedge_beta(LOTS, HB, LR.P10)
    assert abs(got - (10_000 * 1.5 - 6_000 * 0.4 + 4_000 * 1.0)) < 1e-9
    assert LR.hedge_beta(LOTS, {}, LR.P10) == sum(L["n"] * L["beta"] for L in LOTS)


def test_p10_starts_with_protocol_9():
    import core
    assert LR.P10 == core.P9_START == pd.Timestamp("2026-11-16")


def test_b1_formula_is_the_frozen_research_blend():
    """screen.py computes B1 with research/riskfield/forward.py and its frozen coefficients (OOS read 2020-2025)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("rf_forward", os.path.join(ROOT, "research", "riskfield", "forward.py"))
    RF = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(RF)
    c = json.load(open(RF.FROZEN))
    assert abs(c["hf21"] - 0.332) < 0.001 and abs(c["hf63"] - 0.269) < 0.001 and abs(c["ols"] - 0.389) < 0.001
    v = RF.b1(c, np.array([1.0, np.nan]), np.array([1.0, 1.0]), np.array([1.0, 1.0]))
    assert abs(v[0] - (c["intercept"] + c["hf21"] + c["hf63"] + c["ols"])) < 1e-12 and np.isnan(v[1])   # missing -> NaN -> fallback


def test_screen_never_lets_b1_block_the_desk():
    src = open(os.path.join(ROOT, "fund", "screen.py")).read()
    i = src.index("b1_status = \"ok\"")
    block = src[i:src.index("print(f\"screen: Protocol 10 B1", i)]
    assert "try:" in block and "except Exception" in block and 'Z["beta_b1"] = np.nan' in block
    assert '"beta_b1_status": b1_status' in src


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
            print("ok", k)
