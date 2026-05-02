"""Cron-driven one-bar paper-trading step (Phase Q).

Designed to run inside a GitHub Actions hourly cron. Each invocation:

  1. Loads the historical features parquet (training corpus).
  2. Loads accumulated live OHLCV from artefacts/live_bars.parquet.
  3. Fetches the latest bar via yfinance and appends it.
  4. Recomputes features on the combined corpus (training + live).
  5. Constructs PaperEngine + StreamingEncoder-equivalent precomputed
     arrays and replays the live segment through engine.step().
  6. Persists the latest closed trade (if any) to TradeStore.
  7. Saves the engine state JSON + live_bars parquet so the next run
     picks up exactly where this one left off.

Why deterministic full-replay instead of incremental state restore?
  The PPO/GRPO policy + meta-label + Kelly + regime-confirmation state
  combine into a vector that is annoying to serialise correctly.
  Replaying from the start of the live window is O(n_live_bars) which
  is small (a few hundred per month for 60m bars) and *always* correct.

Exit codes
  0 — success (with or without a new trade)
  2 — kill-switch halt or feed failure (cron will surface as workflow failure)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

import numpy as np
import pandas as pd

from _bootstrap import setup, path

from src.data.config_utils import parse_asset_configs
from src.data.features import build_features, feature_columns
from src.data.regimes import HMMRegimeModel
from src.env.trading_env import env_config_from_yaml
from src.live.kill_switch import KillSwitchConfig, evaluate as ks_evaluate, from_cfg as ks_from_cfg
from src.live.paper_engine import CostModel, PaperEngine, TradeStore
from src.models.precompute import build_rolling_windows, precompute_embeddings
from src.training.pretrain_encoder import load_encoder

try:
    from stable_baselines3 import PPO, A2C
except ImportError:    # pragma: no cover
    PPO = A2C = None    # type: ignore[assignment]

log = logging.getLogger("step_one_bar")


def _fetch_latest_bar(asset: str, interval: str) -> pd.DataFrame:
    """Fetch the latest yfinance bar; returns empty DataFrame on failure."""
    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance not installed; skipping fetch")
        return pd.DataFrame()
    try:
        raw = yf.download(asset, period="2d", interval=interval, progress=False,
                           auto_adjust=False, threads=False)
    except Exception as exc:
        log.warning("yfinance fetch failed for %s: %s", asset, exc)
        return pd.DataFrame()
    if raw is None or len(raw) == 0:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.rename(columns={"Open": "open", "High": "high", "Low": "low",
                                "Close": "close", "Volume": "volume"})
    keep = [c for c in ("open", "high", "low", "close", "volume") if c in raw.columns]
    raw = raw[keep].copy()
    if not isinstance(raw.index, pd.DatetimeIndex):
        raw.index = pd.to_datetime(raw.index, utc=True)
    elif raw.index.tz is None:
        raw.index = raw.index.tz_localize("UTC")
    else:
        raw.index = raw.index.tz_convert("UTC")
    return raw


def _load_or_init_live_bars(live_path: str) -> pd.DataFrame:
    if os.path.exists(live_path):
        df = pd.read_parquet(live_path)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        return df
    return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])


def _save_live_bars(live: pd.DataFrame, live_path: str) -> None:
    os.makedirs(os.path.dirname(live_path), exist_ok=True)
    live.to_parquet(live_path)


def _select_best_entry(manifest: list[dict], asset: str) -> dict:
    candidates = [e for e in manifest if e.get("asset") == asset]
    if not candidates:
        raise RuntimeError(f"no manifest entry for {asset}")
    # Highest validation Sharpe wins; falls back to the first entry.
    candidates.sort(key=lambda e: float(e.get("sharpe", 0.0)), reverse=True)
    return candidates[0]


def _load_policy(cfg: dict, entry: dict):
    algo = entry.get("algorithm", "ppo").lower()
    cls = PPO if algo in ("ppo", "grpo") else A2C
    if cls is None:
        raise RuntimeError("stable_baselines3 not installed")
    p = entry["policy_path"]
    if not os.path.isabs(p):
        p = path(cfg, p)
    return cls.load(p, device="cpu")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", default="GC=F")
    parser.add_argument("--offline", action="store_true",
                        help="skip yfinance fetch (test mode)")
    args = parser.parse_args()

    cfg = setup()    # respects TRADING_PROFILE
    asset_cfgs = parse_asset_configs(cfg)
    asset = next((a for a in asset_cfgs if a.symbol == args.asset), None)
    if asset is None:
        log.error("asset %s not in config", args.asset)
        return 2

    feats_path = path(cfg, asset.features_path)
    if not os.path.exists(feats_path):
        log.error("training features missing: %s", feats_path)
        return 2

    # Load training features (already the result of build_features); we
    # only need the OHLCV passthrough columns for the streaming
    # recomputation. Reading the original raw parquet is cheaper.
    raw_path = path(cfg, asset.raw_path)
    if not os.path.exists(raw_path):
        log.error("training OHLCV missing: %s", raw_path)
        return 2
    train_ohlcv = pd.read_parquet(raw_path)
    if train_ohlcv.index.tz is None:
        train_ohlcv.index = train_ohlcv.index.tz_localize("UTC")

    live_path = path(cfg, "artefacts", "live_bars.parquet")
    live = _load_or_init_live_bars(live_path)

    # Fetch + append latest bar.
    if not args.offline:
        new = _fetch_latest_bar(asset.symbol, asset.interval)
        if not new.empty:
            # Drop any bar we already have, plus any older than the last
            # training bar (keeps live segment monotonic and disjoint).
            cutoff = max(
                train_ohlcv.index.max() if len(train_ohlcv) else pd.Timestamp.min.tz_localize("UTC"),
                live.index.max() if len(live) else pd.Timestamp.min.tz_localize("UTC"),
            )
            new = new[new.index > cutoff]
            if len(new):
                live = pd.concat([live, new])
                log.info("appended %d new bar(s); live=%d total", len(new), len(live))
        else:
            log.info("no new bar from yfinance; live=%d", len(live))
    else:
        log.info("offline mode; skipping fetch")

    if len(live) == 0:
        log.warning("no live bars accumulated yet; nothing to step")
        _save_live_bars(live, live_path)
        return 0

    # Recompute features on (training + live) OHLCV.
    combined = pd.concat([train_ohlcv, live])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    feats = build_features(
        combined,
        warmup_bars=int(cfg.get("features", {}).get("warmup_bars", 252)),
        zscore_window=int(cfg.get("features", {}).get("zscore_window", 252)),
    )
    if len(feats) == 0:
        log.error("feature recomputation produced 0 rows; check warmup config")
        return 2

    # Identify the live segment within feats so we know which indices the
    # engine should step through.
    live_start_ts = live.index.min()
    live_mask = feats.index >= live_start_ts
    if not live_mask.any():
        log.info("live bars not yet through warmup; %d feature rows total", len(feats))
        _save_live_bars(live, live_path)
        return 0
    live_idx_start = int(np.argmax(live_mask))    # first True
    log.info("feature corpus: %d rows; live segment starts at idx=%d", len(feats), live_idx_start)

    # Build precomputed (encoder embeddings + atr/close/vol_q + regime).
    manifest_path = path(cfg, cfg["artefact_dir"], "ppo_manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    entry = _select_best_entry(manifest, asset.symbol)
    enc_path = path(cfg, cfg["artefact_dir"], "encoders",
                    f"encoder_group{entry['encoder_group']}.pt")
    encoder = load_encoder(enc_path)

    feat_cols = feature_columns(feats)
    feat_arr = feats[feat_cols].to_numpy(np.float32)
    env_cfg = env_config_from_yaml(cfg)
    emb = precompute_embeddings(encoder, feat_arr, seq_len=env_cfg.seq_len)
    close = feats["close"].to_numpy(np.float64)
    atr = feats["atr"].to_numpy(np.float64)

    # Volatility quantile = rolling rank of (atr/close).
    rv = atr / np.maximum(close, 1e-12)
    vol_q = pd.Series(rv).rank(pct=True).to_numpy(np.float64)

    pc: dict = {"close": close, "atr": atr, "embeddings": emb,
                "vol_quantile": vol_q}

    # Optional regime posterior.
    regime_post = None
    rp_rel = entry.get("regime_path") or "artefacts/regimes/hmm_gc_60m.pkl"
    rp_abs = path(cfg, rp_rel)
    if os.path.exists(rp_abs):
        try:
            hmm = HMMRegimeModel.load(rp_abs)
            regime_post = hmm.posterior(close)
            pc["regime_posterior"] = regime_post
        except Exception as exc:
            log.warning("regime model load failed: %s", exc)

    # Construct engine WITHOUT a TradeStore for the replay; we will
    # manually persist only the newest closed trade so deterministic
    # replay doesn't double-insert history.
    paper_cfg = cfg.get("ui", {}).get("paper", {})
    costs = paper_cfg.get("costs", {})
    cost_model = CostModel(
        spread_bps=float(costs.get("spread_bps", env_cfg.spread_bps)),
        slippage_bps=float(costs.get("slippage_bps", 0.0)),
        commission_usd=float(costs.get("commission_usd", 0.0)),
    )
    model = _load_policy(cfg, entry)
    run_id = f"live-{asset.symbol}-m{manifest.index(entry)}"

    engine = PaperEngine(
        asset=asset.symbol,
        run_id=run_id,
        model=model,
        precomputed=pc,
        env_cfg=env_cfg,
        cost_model=cost_model,
        meta_threshold=float(paper_cfg.get("meta_threshold", 0.55)) if float(paper_cfg.get("meta_threshold", 0.55)) >= 0 else 0.55,
        timestamps=feats.index,
        store=None,                            # replay: no persistence
        kelly_cap=float(paper_cfg.get("kelly_cap", 0.0)),
        kelly_floor=float(paper_cfg.get("kelly_floor", 1.0)),
        kelly_window=int(paper_cfg.get("kelly_window", 100)),
        kelly_cold_start_floor=float(paper_cfg.get("kelly_cold_start_floor",
                                                     paper_cfg.get("kelly_floor", 1.0))),
        daily_loss_limit=float(paper_cfg.get("daily_loss_limit", 0.0)),
        regime_size_multipliers={int(k): float(v)
                                   for k, v in paper_cfg.get("regime_size_multipliers", {}).items()},
        regime_confirm_bars=int(paper_cfg.get("regime_confirm_bars", 0)),
        trade_rate_max_per_day=int(paper_cfg.get("trade_rate_max_per_day", 0)),
    )

    # Step through the live segment. The policy is deterministic, so
    # replay is byte-stable across runs.
    n = len(close)
    last_idx = n - 1
    n_before_records = 0
    for i in range(max(env_cfg.seq_len, live_idx_start), n):
        engine.step(i)
    new_records = engine.trade_records()[n_before_records:]

    # Persist any newly-closed trade(s) on this run. Cheap idempotency:
    # we delete prior trades for this run_id and re-insert all engine
    # records — TradeStore is single-writer per cron job.
    db_path = path(cfg, cfg.get("trade_db_path", "artefacts/paper_trades.db"))
    store = TradeStore(db_path)
    with store._lock, store._connect() as conn:
        conn.execute("DELETE FROM trades WHERE run_id=?", (run_id,))
    for rec in engine.trade_records():
        rec.run_id = run_id
        store.insert(rec)
    log.info("persisted %d trades for run_id=%s", len(engine.trade_records()), run_id)

    # Kill-switch evaluation on accumulated returns.
    ks_cfg: KillSwitchConfig = ks_from_cfg(cfg.get("kill_switch", {}))
    ks = ks_evaluate(engine.trade_returns(), ks_cfg)
    if ks.halt:
        reasons = "; ".join(ks.reasons.values())
        log.error("KILL-SWITCH HALT (run_id=%s): %s", run_id, reasons)
        # Write a halt marker so the dashboard / next run can surface it.
        with open(path(cfg, "artefacts", "kill_switch_halt.json"), "w") as f:
            json.dump({"run_id": run_id, "reasons": ks.reasons,
                        "asset": asset.symbol}, f, indent=2)
        _save_live_bars(live, live_path)
        return 2

    # Snapshot engine state for the dashboard exporter.
    snap = engine.state()
    open_pos = engine.open_position_state()
    snap["open_position"] = open_pos
    snap["last_idx"] = last_idx
    snap["last_ts"] = str(feats.index[last_idx]) if hasattr(feats.index, "__getitem__") else None
    with open(path(cfg, "artefacts", "engine_state.json"), "w") as f:
        json.dump(snap, f, indent=2, default=str)

    _save_live_bars(live, live_path)
    log.info("done: run_id=%s, position=%d, equity=%.4f, n_trades=%d",
             run_id, snap["position"], snap["equity"], snap["n_trades"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
