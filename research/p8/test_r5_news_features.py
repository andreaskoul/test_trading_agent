"""Contracts for R5's news controls (research/p8/r5_news_features.py; PREREG_thesis_tree.md Amendment 9). No network.

    python3 research/p8/test_r5_news_features.py

Fixture: a real R5 own-ledger prompt (DOC, report date 2026-10-21; research-data), whose record lists 60 news items.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r5_news_features as F                                     # noqa: E402


def test_parses_every_item_of_a_real_prompt():
    x = json.load(open(os.path.join(HERE, "data", "r5_prompt_DOC_2026-10-21.json")))
    its = F.items(x["user"])
    assert len(its) == 60 and its[0][0] == "2026-08-04" and its[0][1] == "Yahoo"
    assert its[0][2].startswith("Healthpeak (DOC) Surpasses Q2 FFO")


def test_lm_tone_by_hand():
    P, N = F.lexicon()
    assert {"gain", "strong"} <= P and {"loss", "decline"} <= N
    its = [("2026-01-01", "X", "Strong gain in sales", "record"), ("2026-01-02", "X", "Loss widens on decline", "")]
    f = F.features(its, P, N)
    p = sum(w in P for w in "strong gain in sales record".split())
    n = sum(w in N for w in "loss widens on decline".split())
    assert (f["lm_pos"], f["lm_neg"]) == (p, n) and abs(f["tone"] - (p - n) / (p + n)) < 1e-12
    assert f["quantified"] == 0.0 and F.features([("d", "s", "Up 5%", "")], P, N)["quantified"] == 1.0
    assert F.features([], P, N)["tone"] == 0.0


def test_auc():
    assert F.auc(np.array([2.0, 3.0]), np.array([0.0, 1.0])) == 1.0
    assert F.auc(np.array([0.0]), np.array([1.0])) == 0.0
    assert F.auc(np.array([1.0]), np.array([1.0])) == 0.5


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
