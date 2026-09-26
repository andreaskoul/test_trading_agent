"""Execution-rule tests, and the coin-flip test every backtest must pass.

A strategy that picks sides at random has no information, so after costs
it must lose roughly the cost. If a backtester shows it making money, the
backtester is manufacturing the profit and every policy trained or ranked
in it is suspect. The legacy "close" rule fails this; "bracket" must pass.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.features import build_features
from src.env.fills import check_exit, open_trade, require_ohlc
from src.env.trading_env import EnvConfig
from src.live.paper_engine import CostModel, PaperEngine

# bars:        0      1      2      3      4
O = np.array([100.0, 100.0, 100.2, 99.0, 100.0])
H = np.array([100.5, 100.4, 100.3, 99.2, 100.5])
L = np.array([99.5, 99.6, 99.4, 98.5, 99.5])
C = np.array([100.0, 100.2, 100.1, 99.1, 100.0])
A = np.full(5, 1.0)


def test_bracket_enters_on_next_open():
    entry, tp, sl = open_trade(0, +1, C, A, O, 1.5, 0.75, "bracket")
    assert entry == O[1] and tp == pytest.approx(101.5) and sl == pytest.approx(99.25)
    assert open_trade(4, +1, C, A, O, 1.5, 0.75, "bracket") is None   # no next bar


def test_intrabar_stop_fires_even_if_close_recovers():
    # long from 100, stop 99.25: bar 2 low 99.4 no; widen: stop at 99.5
    hit = check_exit(2, 0, +1, 101.5, 99.5, 4, O, H, L, C, "bracket")
    assert hit == ("sl", 99.5)
    # the legacy rule never sees it: close 100.1 is above the stop
    assert check_exit(2, 0, +1, 101.5, 99.5, 4, O, H, L, C, "close") is None


def test_gap_through_stop_fills_at_open():
    # bar 3 opens at 99.0, below a 99.5 stop
    assert check_exit(3, 0, +1, 101.5, 99.5, 10, O, H, L, C, "bracket") == ("sl", 99.0)
    # legacy books the stop level although the market never traded there
    assert check_exit(3, 0, +1, 101.5, 99.5, 10, O, H, L, C, "close") == ("sl", 99.5)


def test_stop_assumed_first_when_both_touched():
    assert check_exit(4, 0, +1, 100.4, 99.6, 10, O, H, L, C, "bracket")[0] == "sl"


def test_short_side_mirror():
    assert check_exit(2, 0, -1, 99.0, 100.25, 4, O, H, L, C, "bracket") == ("sl", 100.25)
    assert check_exit(3, 0, -1, 99.0, 101.0, 10, O, H, L, C, "bracket") == ("tp", 99.0)


def test_timeout_at_horizon_close():
    assert check_exit(4, 0, +1, 110.0, 90.0, 4, O, H, L, C, "bracket") == ("timeout", C[4])


def test_bracket_requires_ohlc():
    with pytest.raises(ValueError):
        require_ohlc("bracket", None, H, L)


class _Coin:
    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)

    def predict(self, obs, deterministic=True):
        return int(self.rng.integers(1, 3)), None      # BUY or SELL


def _coin_flip_gross_bps(fill_model):
    raw = pd.read_parquet(os.path.join(os.path.dirname(__file__), "..", "data", "raw", "gc_60m.parquet"))
    f = build_features(raw, warmup_bars=252, zscore_window=252)
    n = len(f)
    pc = {k: f[k].to_numpy(np.float64) for k in ("open", "high", "low", "close", "atr")}
    pc["embeddings"] = np.zeros((n, 4), np.float32)
    pc["vol_quantile"] = np.full(n, 0.5)
    cfg = EnvConfig(seq_len=8, horizon=4, rr_upper=1.5, rr_lower=0.75, spread_bps=0.5,
                    fill_model=fill_model)
    cost = CostModel(spread_bps=0.5, slippage_bps=0.3)
    per_trade_cost = cost.roundtrip_deduction(1.0, 0.5)
    r = []
    for seed in range(3):
        eng = PaperEngine(asset="X", run_id="coin", model=_Coin(seed), precomputed=pc,
                          env_cfg=cfg, cost_model=cost)
        for i in range(cfg.seq_len, n):
            eng.step(i)
        r.append(eng.trade_returns())
    r = np.concatenate(r) + per_trade_cost
    return r.mean() * 1e4, r.std(ddof=1) / np.sqrt(len(r)) * 1e4


def test_coin_flip_has_no_gross_edge_under_bracket_fills():
    m, se = _coin_flip_gross_bps("bracket")
    assert abs(m) < 3 * se, f"random entries earn {m:.2f} bp gross (se {se:.2f}): fills leak"


def test_legacy_close_rule_manufactures_edge():
    # Documents why "close" is not the default: random entries earn several
    # standard errors of gross profit on 2023-2026 GC 60m.
    m, se = _coin_flip_gross_bps("close")
    assert m > 5 * se


def test_streaming_signal_on_newest_bar_enters_at_next_open():
    """Live: a signal on the last known bar can only fill once the next bar
    exists. The engine must defer, not drop or fill at the stale close."""
    n = 40
    rng = np.random.default_rng(1)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 1e-3, n)))
    pc = {"open": c.copy(), "high": c * 1.001, "low": c * 0.999, "close": c,
          "atr": np.full(n, 0.5), "embeddings": np.zeros((n, 4), np.float32),
          "vol_quantile": np.full(n, 0.5)}

    class Buy:
        def predict(self, obs, deterministic=True):
            return 1, None

    cfg = EnvConfig(seq_len=8, horizon=4, rr_upper=1.5, rr_lower=0.75, spread_bps=0.5)
    eng = PaperEngine(asset="X", run_id="d", model=Buy(), precomputed=pc, env_cfg=cfg)
    eng.step(n - 1)
    assert eng._pos == 0                       # nothing to fill against yet
    new = eng.extend_precomputed({"open": 101.0, "high": 101.2, "low": 100.9, "close": 101.1,
                                  "atr": 0.5, "embedding": np.zeros(4, np.float32),
                                  "vol_quantile": 0.5})
    eng.step(new)
    assert eng._pos == 1 and eng._entry_price == 101.0 and eng._entry_i == n - 1
