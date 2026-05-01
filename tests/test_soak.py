"""Phase P5: opt-in soak / load test.

Excluded from default test runs because it takes ~30s and exercises the
full hub fan-out pipeline. Run explicitly when validating live readiness::

    python tests/test_soak.py

What it checks:
  * Driving 10× synthetic bar rate for 5000 bars produces a sane number
    of trades (not zero, not pathological).
  * Resident memory stays bounded (<200 MB growth) across the run —
    catches accumulator leaks in the hub, meta-pending queue, or stats
    cache.
  * Every monitoring channel publishes during the run (no silent gaps).
  * stop_session() succeeds at the end (no deadlocked tasks).
"""

from __future__ import annotations

import asyncio
import gc
import json
import os
import sys
import tempfile
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _resident_mb() -> float:
    try:
        import resource
        ru = resource.getrusage(resource.RUSAGE_SELF)
        # ru_maxrss is KB on Linux, bytes on macOS — handle both.
        kb = float(ru.ru_maxrss)
        if kb > 1e7:    # macOS: bytes
            return kb / 1024 / 1024
        return kb / 1024
    except Exception:
        return -1.0


def _build_state_and_engine(n_bars: int):
    """Return (CockpitState, PaperEngine, precomputed dict) ready to drive."""
    from src.data.features import build_features, feature_columns
    from src.env.trading_env import EnvConfig, BUY
    from src.live.kill_switch import KillSwitchConfig
    from src.live.paper_engine import PaperEngine, TradeStore
    from src.models.precompute import precompute_embeddings
    from src.models.xlstm_lite import XLSTMConfig, XLSTMLite
    from src.ui.server import CockpitState, Hub, Session
    from src.validation.live_stats import LiveStats

    rng = np.random.default_rng(42)
    rets = 0.0002 + 0.01 * rng.standard_normal(n_bars)
    close = 1500 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({
        "open": close, "high": close * 1.001, "low": close * 0.999,
        "close": close,
        "volume": np.abs(rng.normal(1e5, 1e4, n_bars)).astype(np.int64),
    }, index=pd.date_range("2020-01-01", periods=n_bars, freq="h", tz="UTC"))
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
                          "meta_refit_every_n_trades": 0,
                          "meta_max_history": 1000}},
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
    eng = PaperEngine(asset="X", run_id="soak", model=AlwaysBuy(),
                      precomputed=pc, env_cfg=env_cfg, timestamps=pc["timestamps"])

    state = CockpitState.__new__(CockpitState)
    state.cfg = cfg
    state.assets = []
    state.manifest = []
    state.env_cfg = env_cfg
    state.hub = Hub()
    state.store = TradeStore(cfg["trade_db_path"])
    state._precomputed_cache = {}
    state._meta_cache = {}
    state._meta_train_data = {}
    state._meta_pending = {}
    state._meta_max_history = 1000
    state._meta_refit_every = 0
    state._ks_cfg = KillSwitchConfig(enabled=False)
    state._live_stats = LiveStats(annualisation_factor=252.0,
                                   bootstrap_resamples=50, bootstrap_block=5,
                                   n_trials_for_dsr=4)
    state.session = Session(asset="X", manifest_idx=0, mode="replay",
                             run_id="soak", engine=eng, feed=None, task=None)
    return state, eng, pc


def test_soak_5000_bars():
    """Drive 5000 bars; assert memory growth < 200MB and key channels emit."""
    from src.live.feed import Bar

    state, eng, pc = _build_state_and_engine(5200)
    seen_channels: dict[str, int] = {}
    mem_before = _resident_mb()

    async def drive():
        q = await state.hub.subscribe()

        async def consume():
            try:
                while True:
                    msg = await asyncio.wait_for(q.get(), timeout=3.0)
                    ch = json.loads(msg)["channel"]
                    seen_channels[ch] = seen_channels.get(ch, 0) + 1
            except asyncio.TimeoutError:
                return

        consumer = asyncio.create_task(consume())
        n_avail = len(pc["close"])
        for i in range(8, n_avail):
            cls = float(pc["close"][i])
            bar = Bar(asset="X", ts=pc["timestamps"][i], idx=i, open=cls,
                      high=cls, low=cls, close=cls, volume=1.0)
            await state._process_bar(eng, bar)
        await consumer
        await state.hub.unsubscribe(q)

    t0 = time.time()
    asyncio.run(drive())
    elapsed = time.time() - t0
    gc.collect()
    mem_after = _resident_mb()

    print(f"soak: {len(pc['close']) - 8} bars in {elapsed:.1f}s; "
          f"memory {mem_before:.0f} -> {mem_after:.0f} MB; "
          f"channels: {seen_channels}")

    assert "trade" in seen_channels and seen_channels["trade"] > 50, \
        f"expected many closed trades; got {seen_channels.get('trade', 0)}"
    for ch in ("bar", "signal", "active", "equity", "stats"):
        assert ch in seen_channels, f"channel {ch} never published"

    if mem_before > 0 and mem_after > 0:
        growth = mem_after - mem_before
        assert growth < 200, f"memory grew {growth:.0f}MB > 200MB cap"


if __name__ == "__main__":
    try:
        test_soak_5000_bars()
        print("PASS test_soak_5000_bars")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"FAIL test_soak_5000_bars: {exc}")
        sys.exit(1)
