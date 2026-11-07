"""Contract tests for the panic-switch forward books (research/regime/forward.py).

    cd research/quant_trials && PYTHONPATH=. python ../regime/test_forward.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import forward as FWD  # noqa: E402


def _panel(ret_path, vol_path):
    """Synthetic panel: SPY with a chosen 252-session drift and recent volatility."""
    S = pd.bdate_range("2020-01-01", periods=1100)
    rng = np.random.default_rng(1)
    sd = np.r_[np.full(1079, 0.008), np.full(21, vol_path)]
    rm = rng.normal(0, 1, len(S)) * sd
    rm[-252:] += (ret_path - rm[-252:].sum()) / 252                       # set the 252-session log drift
    spy = 100 * np.exp(np.cumsum(rm))
    rm = np.r_[np.nan, np.diff(spy) / spy[:-1]]
    return {"S": S, "spy": spy, "rm": rm}


def _thursday(d):
    return max(k for k in range(len(d["S"])) if d["S"][k].weekday() == 3)


def test_panic_needs_both_a_bear_market_and_high_volatility():
    for ret, vol, want in ((-0.2, 0.03, 1), (-0.2, 0.002, 0), (0.2, 0.03, 0), (0.2, 0.002, 0)):
        d = _panel(ret, vol)
        t = _thursday(d)
        st = FWD.panic_at(d, t)
        assert st["panic"] == want, (ret, vol, st)
        assert abs(st["ret252"] - (d["spy"][t] / d["spy"][t - 252] - 1)) < 1e-12
        lr = np.log1p(d["rm"])
        assert abs(st["vol21_ann"] - np.std(lr[t - 20:t + 1]) * np.sqrt(252)) < 1e-12


def test_percentile_uses_only_earlier_thursdays():
    d = _panel(-0.2, 0.03)
    t = _thursday(d)
    st = FWD.panic_at(d, t)
    lr = np.log1p(np.nan_to_num(d["rm"]))
    thu = [k for k in range(252, t) if d["S"][k].weekday() == 3][-156:]
    hist = np.array([np.std(lr[k - 20:k + 1]) for k in thu])
    assert st["hist_weeks"] == 156 and abs(st["vol_pct"] - (hist < np.std(lr[t - 20:t + 1])).mean()) < 1e-12


def test_decile_book_is_dollar_and_beta_neutral():
    rng = np.random.default_rng(2)
    sc = rng.normal(size=500); sc[:20] = np.nan
    beta = rng.uniform(0.5, 1.5, 500)
    w, wspy = FWD.decile_book(sc, beta)
    assert abs(w[w > 0].sum() - 0.5) < 1e-12 and abs(w[w < 0].sum() + 0.5) < 1e-12
    assert abs((w * beta).sum() + wspy) < 1e-12 and np.all(w[:20] == 0)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
