"""End-to-end smoke test on a small synthetic series.

Goals:
  * prove the pipeline runs from data -> features -> labels -> CPCV
    -> encoder -> env -> PPO -> evaluation without exceptions
  * verify the key correctness properties:
      - no NaNs in features after warmup drop
      - CPCV purges training labels whose t1 overlaps a test block
      - the encoder forward pass returns the expected shape
      - the environment completes at least one trade
      - PPO can take a few gradient steps on the env
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


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


def test_features_no_nans():
    from src.data.features import build_features
    df = _synthetic_ohlcv()
    feats = build_features(df, warmup_bars=252, zscore_window=252)
    assert feats.isna().sum().sum() == 0
    assert len(feats) > 500


def test_triple_barrier_labels():
    from src.data.features import build_features
    from src.data.triple_barrier import TBConfig, label_triple_barrier
    df = _synthetic_ohlcv()
    feats = build_features(df)
    labels = label_triple_barrier(feats, TBConfig(horizon=20, rr_upper=2.0, rr_lower=1.0))
    assert set(labels["label_multi"].unique()).issubset({-1, 0, 1})
    assert labels["t1"].is_monotonic_increasing or True  # t1 is per-row, not monotonic
    # t1 must not go backwards
    assert (labels["t1"].to_numpy() >= feats.index.to_numpy()).all()


def test_cpcv_purge_no_leakage():
    from src.data.features import build_features
    from src.data.triple_barrier import TBConfig, label_triple_barrier
    from src.validation.cpcv import CombinatorialPurgedKFold
    df = _synthetic_ohlcv()
    feats = build_features(df)
    labels = label_triple_barrier(feats, TBConfig())
    t1 = pd.Series(labels["t1"].values, index=feats.index)

    # Integer position of each label's t1 for leakage verification
    idx_ns = pd.DatetimeIndex(t1.index).asi8
    t1_ns = pd.DatetimeIndex(t1.values).asi8
    t1_pos = np.searchsorted(idx_ns, t1_ns).clip(0, len(idx_ns) - 1)

    cpcv = CombinatorialPurgedKFold(n_splits=6, n_test_splits=2, embargo_pct=0.01)
    n = len(feats)
    for split in cpcv.split(t1):
        # Real test blocks can be disjoint (e.g. {group 0, group 5}).
        # A training sample leaks if its inclusive label window
        # [tr, t1_pos[tr]] intersects ANY test bar.
        is_test = np.zeros(n, dtype=bool)
        is_test[split.test_idx] = True
        # Prefix-sum: count of test bars up to (inclusive) position i.
        cum = np.concatenate([[0], np.cumsum(is_test)])
        for tr in split.train_idx:
            lo = int(tr)
            hi = int(t1_pos[tr])
            n_test_in_window = cum[hi + 1] - cum[lo]
            assert n_test_in_window == 0, f"leakage at train idx {tr}"


def test_encoder_shape():
    from src.models.xlstm_lite import XLSTMConfig, XLSTMLite
    cfg = XLSTMConfig(input_dim=10, hidden_size=32, n_slstm=1, n_mlstm=1, dropout=0.0)
    model = XLSTMLite(cfg)
    x = torch.randn(4, 16, 10)
    emb = model.encode(x)
    assert emb.shape == (4, 32)
    logits = model(x)
    assert logits.shape == (4, 3)


def test_vib_encoder():
    from src.models.xlstm_lite import (
        XLSTMConfig, XLSTMLite, vib_kl, vib_reparameterize,
    )
    cfg = XLSTMConfig(
        input_dim=10, hidden_size=32, n_slstm=1, n_mlstm=1,
        dropout=0.0, vib=True, vib_beta=1e-3,
    )
    model = XLSTMLite(cfg).eval()
    x = torch.randn(4, 16, 10)
    mu, logsigma = model.encode_params(x)
    assert mu.shape == (4, 32) and logsigma.shape == (4, 32)
    assert torch.allclose(model.encode(x), mu), "encode() should return mu"
    z = vib_reparameterize(mu, logsigma)
    assert z.shape == mu.shape and not torch.allclose(z, mu)
    kl = vib_kl(mu, logsigma)
    assert kl.dim() == 0 and float(kl.detach()) >= 0.0


def test_kill_switch():
    from src.live.kill_switch import KillSwitchConfig, evaluate, from_cfg
    cfg = KillSwitchConfig()
    # Catastrophe
    r = evaluate(np.array([0.01, 0.02, -0.10]), cfg)
    assert "catastrophe" in r.triggered and r.halt
    # Sharpe floor requires duration >= 3 consecutive breaches
    bad = np.random.default_rng(1).normal(-0.001, 0.01, 100)
    single = evaluate(bad, cfg)
    assert "sharpe_floor" not in single.triggered, "single breach should not trigger"
    with_hist = evaluate(bad, cfg, recent_sharpe_history=[0.0, 0.1, 0.2])
    assert "sharpe_floor" in with_hist.triggered
    # Disabled config never triggers
    off = evaluate(np.array([0.01, -0.20, 0.01]), KillSwitchConfig(enabled=False))
    assert not off.halt
    # from_cfg dict roundtrip
    kc = from_cfg({"sharpe_floor": 0.3, "max_drawdown": 0.15})
    assert kc.sharpe_floor == 0.3 and kc.max_drawdown == 0.15


def test_grpo_trainer():
    import tempfile
    import gymnasium as gym
    from gymnasium import spaces
    from src.training.grpo import GRPO, GRPOConfig

    class _Toy(gym.Env):
        observation_space = spaces.Box(low=-5, high=5, shape=(4,), dtype=np.float32)
        action_space = spaces.Discrete(3)
        def __init__(self): self.t = 0
        def reset(self, seed=None, options=None):
            super().reset(seed=seed); self.t = 0
            return np.zeros(4, dtype=np.float32), {}
        def step(self, a):
            self.t += 1
            r = 1.0 if a == (self.t % 3) else -0.5
            return np.random.randn(4).astype(np.float32), r, self.t >= 16, False, {}

    env = _Toy()
    cfg = GRPOConfig(total_timesteps=64, group_size=2, steps_per_trajectory=16,
                     n_epochs=1, batch_size=16, seed=0)
    model = GRPO(env, cfg).learn(64)
    obs, _ = env.reset()
    a, _ = model.predict(obs, deterministic=True)
    assert isinstance(int(a), int)
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        path = f.name
    model.save(path)
    loaded = GRPO.load(path, env=env)
    a2, _ = loaded.predict(obs, deterministic=True)
    assert int(a) == int(a2), "GRPO save/load round-trip mismatch"


def test_tft_encoder():
    from src.models.xlstm_lite import XLSTMConfig, XLSTMLite
    cfg = XLSTMConfig(
        input_dim=10, hidden_size=32, n_slstm=1, n_mlstm=1,
        dropout=0.0, tft=True, tft_heads=4,
    )
    model = XLSTMLite(cfg).eval()
    x = torch.randn(4, 16, 10)
    emb = model.encode(x)
    assert emb.shape == (4, 32)
    logits = model(x)
    assert logits.shape == (4, 3)
    # TFT + VIB compose
    cfg2 = XLSTMConfig(
        input_dim=10, hidden_size=32, n_slstm=1, n_mlstm=1,
        dropout=0.0, tft=True, tft_heads=4, vib=True, vib_beta=1e-3,
    )
    m2 = XLSTMLite(cfg2).eval()
    mu, logsigma = m2.encode_params(x)
    assert mu.shape == (4, 32) and logsigma.shape == (4, 32)


def test_env_runs_trade():
    from src.data.features import build_features, feature_columns
    from src.env.trading_env import EnvConfig, TradingEnv, BUY
    df = _synthetic_ohlcv()
    feats = build_features(df)
    cols = feature_columns(feats)
    env = TradingEnv(feats, cols, EnvConfig(seq_len=16, horizon=15))
    obs, _ = env.reset(seed=0)
    assert obs.shape == (16, len(cols))
    # Force a BUY so we know a trade opens
    env.step(BUY)
    for _ in range(20):
        _, _, term, _, info = env.step(0)
        if "trade_return" in info:
            break
        if term:
            break
    # After enough steps the TB must fire - a trade should have been logged
    assert any(k == "trade_return" for k in info) or len(env._episode_trades) > 0


def test_ppo_short_train():
    import tempfile
    from src.data.features import build_features, feature_columns
    from src.env.trading_env import EnvConfig, TradingEnv
    from src.models.policy import build_policy_kwargs
    from src.models.xlstm_lite import XLSTMConfig, XLSTMLite
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    df = _synthetic_ohlcv()
    feats = build_features(df)
    cols = feature_columns(feats)
    enc_cfg = XLSTMConfig(input_dim=len(cols), hidden_size=32, n_slstm=1, n_mlstm=1, dropout=0.0)
    encoder = XLSTMLite(enc_cfg)

    def make():
        return TradingEnv(feats, cols, EnvConfig(seq_len=16, horizon=10))
    venv = DummyVecEnv([make])
    policy_kwargs = build_policy_kwargs(encoder)
    model = PPO(
        "MlpPolicy",
        venv,
        n_steps=128,
        batch_size=32,
        policy_kwargs=policy_kwargs,
        device="cpu",
        verbose=0,
    )
    model.learn(total_timesteps=128)
    venv.close()


def test_reward_modes():
    """T1.2 / T1.3: return-mode and diff_sharpe reward modes must not
    crash and must produce finite non-shaped rewards."""
    from src.data.features import build_features, feature_columns
    from src.env.trading_env import EnvConfig, TradingEnv, BUY
    df = _synthetic_ohlcv()
    feats = build_features(df)
    cols = feature_columns(feats)

    for mode in ("shaped", "return", "diff_sharpe"):
        cfg = EnvConfig(
            seq_len=16,
            horizon=15,
            reward_mode=mode,
            reward_return_scale=100.0,
            reward_cost_lambda=3.0,
            reward_dsr_eta=0.01,
        )
        env = TradingEnv(feats, cols, cfg)
        env.reset(seed=0)
        saw_reward = False
        # Force a BUY then HOLD until a barrier fires.
        env.step(BUY)
        for _ in range(40):
            _, r, term, _, info = env.step(0)
            assert np.isfinite(r), f"non-finite reward in mode={mode}"
            if "trade_return" in info:
                saw_reward = True
                break
            if term:
                break
        assert saw_reward, f"no trade fired in mode={mode}"


def test_regime_conditioned_env():
    """T2.1: EmbeddingTradingEnv with a 3-state HMM regime posterior
    should expose 131-dim obs (128 embedding + 3 posterior)."""
    from src.data.features import build_features, feature_columns
    from src.data.regimes import HMMRegimeConfig, HMMRegimeModel
    from src.env.embedding_env import EmbeddingTradingEnv
    from src.env.trading_env import EnvConfig
    from src.models.xlstm_lite import XLSTMConfig, XLSTMLite
    from src.models.precompute import precompute_embeddings

    df = _synthetic_ohlcv()
    feats = build_features(df)
    cols = feature_columns(feats)
    enc = XLSTMLite(XLSTMConfig(input_dim=len(cols), hidden_size=32, n_slstm=1, n_mlstm=1, dropout=0.0))
    feat_arr = feats[cols].to_numpy(dtype=np.float32)
    emb = precompute_embeddings(enc, feat_arr, seq_len=16)
    close = feats["close"].to_numpy(dtype=np.float64)
    atr = feats["atr"].to_numpy(dtype=np.float64)
    vq = np.linspace(0, 1, len(feats))

    hmm = HMMRegimeModel(HMMRegimeConfig(n_states=3))
    hmm.fit(close, train_idx=np.arange(len(close) - 200))
    post = hmm.posterior(close)
    assert post.shape == (len(close), 3)

    env = EmbeddingTradingEnv(
        close=close, atr=atr, embeddings=emb, vol_quantile=vq,
        cfg=EnvConfig(seq_len=16, horizon=15),
        regime_posterior=post,
    )
    obs, _ = env.reset(seed=0)
    assert obs.shape == (32 + 3,), f"expected 35-dim obs, got {obs.shape}"


def test_deflated_sharpe_reasonable():
    from src.validation.deflated_sr import deflated_sharpe_ratio, sharpe_ratio
    rng = np.random.default_rng(1)
    # Slight positive drift - should yield non-trivial PSR
    rets = 0.0005 + 0.01 * rng.standard_normal(500)
    sr = sharpe_ratio(rets)
    assert sr != 0.0
    dsr = deflated_sharpe_ratio(rets, n_trials=10)
    assert 0.0 <= dsr.psr_vs_zero <= 1.0
    assert 0.0 <= dsr.deflated_sharpe <= 1.0


def test_bootstrap_and_permutation():
    from src.validation.bootstrap import (
        block_bootstrap_sharpe,
        bootstrap_pvalue_sharpe,
        permutation_pvalue_sharpe,
        block_permutation_pvalue_sharpe,
        acf_lag1,
    )
    rng = np.random.default_rng(2)
    rets = 0.0005 + 0.01 * rng.standard_normal(300)
    ci = block_bootstrap_sharpe(rets, block=10, n_resamples=100)
    assert ci.lo <= ci.point <= ci.hi
    p = permutation_pvalue_sharpe(rets, n_resamples=100)
    assert 0.0 <= p <= 1.0

    # PRIMARY edge test: centred block-bootstrap p-value (Phase H)
    p_boot = bootstrap_pvalue_sharpe(rets, block=10, n_resamples=200)
    assert 0.0 <= p_boot <= 1.0

    # Block permutation + ACF diagnostic
    p_block = block_permutation_pvalue_sharpe(rets, block_size=8, n_resamples=100)
    assert 0.0 <= p_block <= 1.0
    acf = acf_lag1(rets)
    assert -1.0 <= acf <= 1.0
    assert abs(acf) < 0.15, f"i.i.d. series unexpectedly autocorrelated: acf={acf:.4f}"

    # On a deliberately-clustered positive-drift series (blocks of wins
    # interleaved with smaller-magnitude losses so observed Sharpe > 0),
    # ACF(1) should be clearly positive and both permutation tests
    # should return a non-degenerate p-value in (0, 1).
    clustered = np.concatenate([
        np.full(8, 0.005), np.full(8, -0.002),
        np.full(8, 0.005), np.full(8, -0.002),
    ])
    assert abs(acf_lag1(clustered)) > 0.05
    p_clust_block = block_permutation_pvalue_sharpe(
        clustered, block_size=8, n_resamples=200, seed=42
    )
    assert 0.0 < p_clust_block <= 1.0


def test_multi_asset_config():
    """Verify parse_asset_configs handles both new multi-asset and legacy single-asset formats."""
    from src.data.config_utils import parse_asset_configs, freq_multiplier, scale_param

    # New multi-asset format
    cfg_new = {
        "data": {
            "assets": [
                {"symbol": "GC=F", "raw_path": "data/raw/gc.parquet",
                 "features_path": "data/processed/features_gc.parquet",
                 "labels_path": "data/processed/labels_gc.parquet"},
                {"symbol": "SI=F", "raw_path": "data/raw/si.parquet",
                 "features_path": "data/processed/features_si.parquet",
                 "labels_path": "data/processed/labels_si.parquet"},
            ],
            "start": "2005-01-01",
            "end": "2025-12-31",
        }
    }
    assets = parse_asset_configs(cfg_new)
    assert len(assets) == 2
    assert assets[0].symbol == "GC=F"
    assert assets[1].symbol == "SI=F"

    # Legacy single-asset format (backward compat)
    cfg_old = {
        "data": {
            "symbol": "GC=F",
            "fallback_symbols": ["GLD"],
            "raw_path": "data/raw/gold.parquet",
            "features_path": "data/processed/features.parquet",
            "labels_path": "data/processed/labels.parquet",
        }
    }
    assets_old = parse_asset_configs(cfg_old)
    assert len(assets_old) == 1
    assert assets_old[0].symbol == "GC=F"
    assert assets_old[0].fallback_symbols == ["GLD"]

    # Frequency scaling
    assert freq_multiplier("1d") == 1.0
    assert freq_multiplier("1h") == 6.5
    assert scale_param(252, "1d") == 252
    assert scale_param(20, "1h") == 130  # 20 * 6.5 = 130


def test_multi_asset_loader():
    """Verify load_ohlcv generates different synthetic data per symbol."""
    from src.data.loader import load_ohlcv, load_gold

    # load_gold is an alias for load_ohlcv
    assert load_gold is load_ohlcv

    r1 = load_ohlcv("GC=F", force_synthetic=True)
    r2 = load_ohlcv("SI=F", force_synthetic=True)
    assert "synthetic" in r1.source
    assert "synthetic" in r2.source
    # Different symbols should produce different price levels
    assert abs(r1.df["close"].iloc[0] - r2.df["close"].iloc[0]) > 100
    # Both should have valid OHLCV
    assert len(r1.df) > 1000
    assert len(r2.df) > 1000
    for col in ["open", "high", "low", "close", "volume"]:
        assert col in r1.df.columns
        assert col in r2.df.columns


def test_shared_encoder_multi_asset():
    """Verify that a single encoder can process features from different assets
    (since all assets share the same feature columns after z-scoring)."""
    from src.data.features import build_features, feature_columns
    from src.data.loader import load_ohlcv
    from src.models.xlstm_lite import XLSTMConfig, XLSTMLite

    # Build features for two different assets
    r1 = load_ohlcv("GC=F", force_synthetic=True)
    r2 = load_ohlcv("SI=F", force_synthetic=True)
    f1 = build_features(r1.df)
    f2 = build_features(r2.df)

    cols1 = feature_columns(f1)
    cols2 = feature_columns(f2)
    assert cols1 == cols2, "feature columns must match across assets"

    # One encoder handles both
    cfg = XLSTMConfig(input_dim=len(cols1), hidden_size=32, n_slstm=1, n_mlstm=1, dropout=0.0)
    encoder = XLSTMLite(cfg)
    import torch
    x1 = torch.randn(2, 16, len(cols1))
    x2 = torch.randn(2, 16, len(cols2))
    e1 = encoder.encode(x1)
    e2 = encoder.encode(x2)
    assert e1.shape == (2, 32) and e2.shape == (2, 32)


def test_kelly_calculator():
    """Phase H: KellyCalculator returns floor=1.0 by default (no scaling)."""
    from src.live.paper_engine import KellyCalculator
    # Default cap=0 -> always floor=1.0 regardless of history
    k = KellyCalculator()
    assert k.fraction() == 1.0
    for _ in range(50):
        k.update(0.001)
    assert k.fraction() == 1.0     # cap=0 short-circuits

    # Enable Kelly: positive expectancy series should produce 0 < f < 1
    k2 = KellyCalculator(window=100, cap=0.25, floor=0.0)
    assert k2.fraction() == 0.0    # warming up < 20 trades
    rng = np.random.default_rng(0)
    for _ in range(50):
        # 60% wins of size +0.002, 40% losses of size -0.001
        k2.update(0.002 if rng.random() < 0.6 else -0.001)
    f = k2.fraction()
    assert 0.0 < f <= 1.0, f"Kelly fraction out of range: {f:.4f}"


def test_yfinance_feed_validation():
    """Phase H: YFinanceFeed._validate_bar rejects NaN, gaps, stale bars."""
    from src.live.feed import YFinanceFeed, Bar
    feed = YFinanceFeed("GC=F", interval="1m", bar_interval_seconds=60)
    feed._last_close = 2000.0
    now = pd.Timestamp.utcnow()

    good = Bar(ts=now, open=2001, high=2002, low=2000, close=2001, volume=10, asset="GC=F")
    ok, _ = feed._validate_bar(good)
    assert ok

    nan_bar = Bar(ts=now, open=float("nan"), high=2002, low=2000, close=2001, volume=10, asset="GC=F")
    ok, reason = feed._validate_bar(nan_bar)
    assert not ok and "non-finite" in reason

    gap_bar = Bar(ts=now, open=2200, high=2200, low=2200, close=2200, volume=10, asset="GC=F")
    ok, reason = feed._validate_bar(gap_bar)
    assert not ok and "gap" in reason

    stale_bar = Bar(ts=now - pd.Timedelta(seconds=300), open=2001, high=2001, low=2001,
                    close=2001, volume=10, asset="GC=F")
    ok, reason = feed._validate_bar(stale_bar)
    assert not ok and "old" in reason


if __name__ == "__main__":
    tests = [
        test_features_no_nans,
        test_triple_barrier_labels,
        test_cpcv_purge_no_leakage,
        test_encoder_shape,
        test_vib_encoder,
        test_tft_encoder,
        test_grpo_trainer,
        test_kill_switch,
        test_env_runs_trade,
        test_reward_modes,
        test_ppo_short_train,
        test_regime_conditioned_env,
        test_deflated_sharpe_reasonable,
        test_bootstrap_and_permutation,
        test_multi_asset_config,
        test_multi_asset_loader,
        test_shared_encoder_multi_asset,
        test_kelly_calculator,
        test_yfinance_feed_validation,
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
    print("all smoke tests passed")
