"""Cockpit tier: paper-engine parity + FastAPI smoke tests.

The critical correctness gate is ``test_paper_engine_matches_backtest``:
running :class:`PaperEngine` step-by-step over a test window must
produce the same trade returns as ``rollout_policy`` on the same
precomputed arrays. This guarantees that replay and backtest stay
numerically reconciled as the cockpit ships.

The rest of the tests exercise the API surface with an in-memory
TestClient and verify the Claude-explanation fallback path works when
no API key is configured.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------


def _synthetic_ohlcv(n: int = 1500) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rets = 0.0002 + 0.01 * rng.standard_normal(n)
    close = 1500 * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, 0.003, size=n)))
    low = close * (1 - np.abs(rng.normal(0, 0.003, size=n)))
    open_ = close * (1 + rng.normal(0, 0.001, size=n))
    volume = np.abs(rng.normal(1e5, 1e4, size=n)).astype(np.int64)
    idx = pd.date_range("2015-01-02", periods=n, freq="B", tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


class _DeterministicBuyModel:
    """Fake SB3-compatible model that always returns BUY.

    Using a real PPO would make the test slow and non-deterministic across
    SB3 versions. All we need for parity is that both the engine and the
    backtester consume the SAME action at the same bar — a constant policy
    is the simplest guarantee.
    """

    def __init__(self, action: int = 1):
        self.action = action

    def predict(self, obs, deterministic=True):
        return np.int64(self.action), None


def _build_precomputed():
    from src.data.features import build_features, feature_columns
    from src.models.precompute import precompute_embeddings
    from src.models.xlstm_lite import XLSTMConfig, XLSTMLite

    df = _synthetic_ohlcv()
    feats = build_features(df)
    cols = feature_columns(feats)
    enc = XLSTMLite(
        XLSTMConfig(input_dim=len(cols), hidden_size=32, n_slstm=1, n_mlstm=1, dropout=0.0)
    )
    feat_arr = feats[cols].to_numpy(dtype=np.float32)
    emb = precompute_embeddings(enc, feat_arr, seq_len=16)
    close = feats["close"].to_numpy(dtype=np.float64)
    atr = feats["atr"].to_numpy(dtype=np.float64)
    rv = pd.Series(atr / close).rolling(20, min_periods=1).mean()
    vol_q = rv.rank(pct=True).to_numpy()
    return dict(
        close=close,
        atr=atr,
        embeddings=emb,
        vol_quantile=vol_q,
        features=feats,
        feat_cols=cols,
    )


# ---------------------------------------------------------------------------
# 1. Parity: paper engine vs rollout_policy
# ---------------------------------------------------------------------------


def test_paper_engine_matches_backtest():
    """PaperEngine.step(i) over a test window must produce the same trade
    returns as rollout_policy on the same precomputed inputs."""
    from src.env.trading_env import EnvConfig
    from src.live.paper_engine import CostModel, PaperEngine
    from src.training.evaluate import rollout_policy

    pc = _build_precomputed()
    env_cfg = EnvConfig(
        seq_len=16, horizon=10, spread_bps=2.0,
        reward_mode="return", reward_return_scale=100.0, reward_cost_lambda=0.0,
    )

    # Use the last ~400 bars as the test block. Enough for several
    # triple-barrier firings without dominating test runtime.
    n = len(pc["close"])
    test_idx = np.arange(n - 450, n - 5)

    model = _DeterministicBuyModel()
    expected = rollout_policy(
        model=model,
        precomputed={
            "close": pc["close"],
            "atr": pc["atr"],
            "embeddings": pc["embeddings"],
            "vol_quantile": pc["vol_quantile"],
        },
        env_cfg=env_cfg,
        test_idx=test_idx,
    )

    engine = PaperEngine(
        asset="SYN",
        run_id="parity",
        model=model,
        precomputed={
            "close": pc["close"],
            "atr": pc["atr"],
            "embeddings": pc["embeddings"],
            "vol_quantile": pc["vol_quantile"],
        },
        env_cfg=env_cfg,
        cost_model=CostModel(spread_bps=env_cfg.spread_bps),  # zero extras => parity
        meta_model=None,
    )

    # Walk exactly the same indices the backtester walks. rollout_policy's
    # inner loop is ``while env._step_i < end`` with ``end = test_idx[-1]``,
    # so it processes indices [test_idx[0], test_idx[-1] - 1] inclusive.
    for i in range(int(test_idx[0]), int(test_idx[-1])):
        engine.step(i)

    got = engine.trade_returns()
    assert got.shape == expected.trade_returns.shape, (
        f"trade count mismatch: got {got.shape}, expected {expected.trade_returns.shape}"
    )
    assert np.allclose(got, expected.trade_returns, atol=1e-9), (
        "paper engine trade returns must match rollout_policy exactly"
    )


def test_paper_engine_respects_extra_costs():
    """Raising slippage strictly lowers realised P&L on filled trades."""
    from src.env.trading_env import EnvConfig
    from src.live.paper_engine import CostModel, PaperEngine

    pc = _build_precomputed()
    env_cfg = EnvConfig(seq_len=16, horizon=10, spread_bps=2.0, reward_mode="return")

    def run(cost: CostModel):
        engine = PaperEngine(
            asset="SYN", run_id="cost-sweep",
            model=_DeterministicBuyModel(),
            precomputed={
                "close": pc["close"], "atr": pc["atr"],
                "embeddings": pc["embeddings"], "vol_quantile": pc["vol_quantile"],
            },
            env_cfg=env_cfg,
            cost_model=cost,
        )
        n = len(pc["close"])
        for i in range(n - 450, n - 6):
            engine.step(i)
        return engine.trade_returns()

    zero = run(CostModel(spread_bps=2.0, slippage_bps=0.0, commission_usd=0.0))
    high = run(CostModel(spread_bps=2.0, slippage_bps=50.0, commission_usd=0.0))
    assert len(zero) == len(high) and len(zero) > 0
    # Per-trade P&L must be strictly lower (or equal on zero-move trades) under
    # higher slippage.
    assert np.all(high <= zero + 1e-12)
    assert np.sum(zero - high) > 0, "slippage must reduce mean P&L"


# ---------------------------------------------------------------------------
# 2. ReplayFeed timing
# ---------------------------------------------------------------------------


def test_replay_feed_fast_mode():
    """speed<=0 means no sleep; a 200-bar window should complete promptly."""
    import time
    from src.live.feed import ReplayFeed

    df = _synthetic_ohlcv(400)

    async def run() -> int:
        feed = ReplayFeed("SYN", df, start_idx=100, end_idx=300, speed=0.0)
        count = 0
        t0 = time.monotonic()
        async for _ in feed.subscribe():
            count += 1
        dt = time.monotonic() - t0
        assert dt < 2.0, f"unrestricted replay took {dt:.2f}s (expected <2s)"
        return count

    count = asyncio.run(run())
    assert count == 200


def test_replay_feed_emits_idx():
    from src.live.feed import ReplayFeed

    df = _synthetic_ohlcv(50)

    async def run():
        feed = ReplayFeed("SYN", df, start_idx=0, end_idx=5, speed=0.0)
        seen = []
        async for bar in feed.subscribe():
            seen.append(bar.idx)
        return seen

    seen = asyncio.run(run())
    assert seen == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# 3. Trade store persistence
# ---------------------------------------------------------------------------


def test_trade_store_roundtrip():
    from src.live.paper_engine import TradeRecord, TradeStore

    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "trades.db")
        store = TradeStore(db)
        rec = TradeRecord(
            trade_id=None,
            asset="GC=F",
            run_id="unit",
            direction=1,
            entry_idx=10,
            exit_idx=18,
            entry_ts=pd.Timestamp("2024-01-02", tz="UTC"),
            exit_ts=pd.Timestamp("2024-01-03", tz="UTC"),
            entry_price=1800.0,
            exit_price=1810.0,
            pnl=0.0055,
            meta_prob=0.62,
            regime_idx=1,
            vol_q=0.4,
            barrier="tp",
            entry_features=np.arange(5, dtype=np.float32),
            embedding=np.arange(4, dtype=np.float32),
        )
        tid = store.insert(rec)
        assert tid > 0
        got = store.get(tid)
        assert got is not None
        assert got["pnl"] == 0.0055
        assert got["direction"] == 1

        store.set_explanation(tid, "test explanation")
        got2 = store.get(tid)
        assert got2["explanation"] == "test explanation"

        listed = store.list_trades(asset="GC=F", limit=10)
        assert len(listed) == 1


# ---------------------------------------------------------------------------
# 4. Explain fallback (no anthropic / no API key)
# ---------------------------------------------------------------------------


def test_explain_fallback_without_api_key():
    """When ANTHROPIC_API_KEY is missing, explain_trade returns a
    deterministic template that still cites the meta prob and barrier."""
    from src.ui.explain import explain_trade

    prior = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        trade = dict(
            asset="GC=F", direction=1,
            entry_price=1800.0, exit_price=1810.0, pnl=0.005,
            barrier="tp", meta_prob=0.62, regime_idx=1, vol_q=0.4,
            entry_ts="2024-01-02", exit_ts="2024-01-03",
            embedding_json=json.dumps([0.1, -0.9, 2.1, 0.2]),
            entry_features_json=json.dumps([0.1, 2.1, -1.2, 0.0, 0.1]),
        )
        text = asyncio.run(explain_trade(trade, {"ui": {"explain": {"max_words": 50}}}))
        assert len(text.split()) <= 50
        assert "GC=F" in text
        assert "0.62" in text  # meta prob rendered
    finally:
        if prior:
            os.environ["ANTHROPIC_API_KEY"] = prior


# ---------------------------------------------------------------------------
# 5. FastAPI endpoints (TestClient, no policies needed)
# ---------------------------------------------------------------------------


def test_api_smoke_endpoints():
    """Hit the read-only endpoints with an in-memory TestClient.

    The server reads ``configs/default.yaml`` and the existing artefacts —
    we assert endpoints return well-formed JSON even when some artefacts
    are absent (the cockpit must not crash on a fresh clone).
    """
    try:
        from fastapi.testclient import TestClient  # noqa: F401
    except ImportError:
        # FastAPI not installed in this environment -> skip rather than fail.
        import warnings
        warnings.warn("fastapi not installed; skipping api smoke", stacklevel=2)
        return

    from src.ui.server import app

    with TestClient(app) as client:
        r = client.get("/api/assets")
        assert r.status_code == 200
        assets = r.json()
        assert isinstance(assets, list)

        r = client.get("/api/manifest")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

        r = client.get("/api/metrics")
        assert r.status_code == 200
        body = r.json()
        assert "summary" in body and "per_run" in body

        r = client.get("/api/paper/state")
        assert r.status_code == 200
        assert r.json()["running"] in (True, False)

        r = client.get("/api/trades?limit=10")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


def test_api_monitoring_endpoints_json_shape():
    """Phase P1: monitoring endpoints (/active, /stats, /aggregate, /sessions)
    must return well-formed JSON even on a cold install with no trades.

    These are the contracts the UI's static JS depends on; a regression
    here breaks every monitoring panel silently."""
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        import warnings
        warnings.warn("fastapi not installed; skipping monitoring smoke", stacklevel=2)
        return
    from src.ui.server import app

    with TestClient(app) as client:
        r = client.get("/api/paper/active")
        assert r.status_code == 200
        body = r.json()
        assert "active" in body and isinstance(body["active"], list)

        r = client.get("/api/paper/stats")
        assert r.status_code == 200
        stats = r.json()
        for k in ("n_trades", "sharpe", "dsr", "psr_vs_zero",
                  "boot_p", "boot_lo", "boot_hi", "ann_factor"):
            assert k in stats, f"stats missing key {k}: {stats}"

        r = client.get("/api/paper/aggregate")
        assert r.status_code == 200
        agg = r.json()
        assert "total" in agg and "groups" in agg
        assert "n_trades" in agg["total"]

        r = client.get("/api/paper/aggregate?group_by=algorithm")
        assert r.status_code == 200
        assert "groups" in r.json()

        r = client.get("/api/paper/sessions")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

        r = client.get("/api/trades?algorithm=ppo&limit=5")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


def test_e2e_process_bar_publishes_all_channels():
    """Phase P1: drive PaperEngine + CockpitState.hub directly and verify
    every monitoring WebSocket channel emits at least once during a short
    synthetic session. Catches channel-name/shape regressions that would
    silently break the UI."""
    try:
        from fastapi.testclient import TestClient   # noqa: F401
    except ImportError:
        import warnings
        warnings.warn("fastapi not installed; skipping e2e channels", stacklevel=2)
        return

    from src.data.features import build_features, feature_columns
    from src.env.trading_env import EnvConfig, BUY
    from src.live.feed import Bar
    from src.live.paper_engine import PaperEngine, TradeStore
    from src.models.precompute import precompute_embeddings
    from src.models.xlstm_lite import XLSTMConfig, XLSTMLite
    from src.ui.server import CockpitState, Session

    # Build synthetic precomputed.
    rng = np.random.default_rng(0)
    n = 800
    rets = 0.0002 + 0.01 * rng.standard_normal(n)
    close = 1500 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({
        "open": close, "high": close * 1.001, "low": close * 0.999,
        "close": close, "volume": np.abs(rng.normal(1e5, 1e4, n)).astype(np.int64),
    }, index=pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC"))
    feats = build_features(df)
    feat_cols = feature_columns(feats)
    enc = XLSTMLite(XLSTMConfig(input_dim=len(feat_cols), hidden_size=16))
    emb = precompute_embeddings(enc, feats[feat_cols].to_numpy(np.float32), seq_len=8)
    pc = {
        "close": feats["close"].to_numpy(np.float64),
        "atr": feats["atr"].to_numpy(np.float64),
        "embeddings": emb,
        "vol_quantile": np.ones(len(feats), dtype=np.float64),
        "timestamps": feats.index,
    }

    cfg = {
        "ui": {"paper": {"ann_factor": 252.0, "stats_bootstrap_resamples": 50,
                          "meta_refit_every_n_trades": 0}},
        "kill_switch": {"enabled": False},
        "evaluation": {"permutation_block_size": 5},
        "data": {"assets": [{"symbol": "X", "interval": "1h"}]},
        "artefact_dir": tempfile.mkdtemp(),
        "report_dir": tempfile.mkdtemp(),
        "trade_db_path": tempfile.NamedTemporaryFile(suffix=".db", delete=False).name,
        "env": {"seq_len": 8, "horizon": 4, "rr_upper": 1.5, "rr_lower": 0.75,
                 "spread_bps": 0.5},
    }

    class AlwaysBuy:
        def predict(self, obs, deterministic=True): return BUY, None

    env_cfg = EnvConfig(seq_len=8, horizon=4, rr_upper=1.5, rr_lower=0.75, spread_bps=0.5)
    eng = PaperEngine(asset="X", run_id="e2e", model=AlwaysBuy(),
                      precomputed=pc, env_cfg=env_cfg,
                      timestamps=pc["timestamps"])

    # Build CockpitState (skip __init__ — it expects on-disk artefacts).
    state = CockpitState.__new__(CockpitState)
    state.cfg = cfg
    state.assets = []
    state.manifest = []
    state.env_cfg = env_cfg
    from src.ui.server import Hub
    state.hub = Hub()
    state.store = TradeStore(cfg["trade_db_path"])
    state._precomputed_cache = {}
    state._meta_cache = {}
    state._meta_train_data = {}
    state._meta_pending = {}
    state._meta_max_history = 2000
    state._meta_refit_every = 0
    from src.live.kill_switch import KillSwitchConfig
    state._ks_cfg = KillSwitchConfig(enabled=False)
    from src.validation.live_stats import LiveStats
    state._live_stats = LiveStats(annualisation_factor=252.0,
                                   bootstrap_resamples=50, bootstrap_block=5,
                                   n_trials_for_dsr=4)
    state.session = Session(asset="X", manifest_idx=0, mode="replay",
                             run_id="e2e", engine=eng, feed=None, task=None)

    seen_channels: set[str] = set()

    async def drive() -> set[str]:
        q = await state.hub.subscribe()

        async def consume() -> None:
            try:
                while True:
                    msg = await asyncio.wait_for(q.get(), timeout=2.0)
                    seen_channels.add(json.loads(msg)["channel"])
            except asyncio.TimeoutError:
                return

        consumer = asyncio.create_task(consume())
        # Drive enough bars to enter, exit, and emit a closed-trade stats burst.
        for i in range(8, 80):
            ts = pc["timestamps"][i]
            cls = float(pc["close"][i])
            bar = Bar(asset="X", ts=ts, idx=i, open=cls, high=cls, low=cls,
                      close=cls, volume=1.0)
            await state._process_bar(eng, bar)
        await consumer
        await state.hub.unsubscribe(q)
        return seen_channels

    channels = asyncio.run(drive())
    for required in ("bar", "signal", "active", "equity", "trade", "stats"):
        assert required in channels, \
            f"channel {required!r} never published; saw {channels}"


# ---------------------------------------------------------------------------
# Manual runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_paper_engine_matches_backtest,
        test_paper_engine_respects_extra_costs,
        test_replay_feed_fast_mode,
        test_replay_feed_emits_idx,
        test_trade_store_roundtrip,
        test_explain_fallback_without_api_key,
        test_api_smoke_endpoints,
        test_api_monitoring_endpoints_json_shape,
        test_e2e_process_bar_publishes_all_channels,
    ]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as exc:
            failures += 1
            import traceback
            print(f"FAIL {t.__name__}: {exc}")
            traceback.print_exc()
    if failures:
        sys.exit(1)
    print("all cockpit tests passed")
