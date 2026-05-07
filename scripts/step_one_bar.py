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


def _fetch_bars_since(
    asset: str, interval: str, since: pd.Timestamp,
    max_lookback_days: int = 700,
) -> pd.DataFrame:
    """Fetch all yfinance bars from ``since`` (exclusive) up to now.

    On first cron run with empty live_bars, ``since`` will be the last
    training bar (potentially weeks/months ago) and this fetches the whole
    gap in one call — the system can start trading immediately instead of
    waiting ~10 days for live_bars to accumulate organically.

    On steady-state runs, ``since`` is the previous tick's last bar so
    this returns at most one new bar.

    yfinance enforces a 730-day lookback cap for 60m intervals; we cap at
    700 to stay well within bounds.
    """
    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance not installed; skipping fetch")
        return pd.DataFrame()

    end = pd.Timestamp.now(tz="UTC")
    cap = end - pd.Timedelta(days=max_lookback_days)
    start = max(since + pd.Timedelta(hours=1), cap).floor("h")
    if start >= end:
        return pd.DataFrame()
    log.info("yfinance fetch: %s [%s -> %s] interval=%s",
             asset, start.isoformat(), end.isoformat(), interval)

    try:
        raw = yf.download(
            asset, start=start, end=end, interval=interval,
            progress=False, auto_adjust=False, threads=False,
        )
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
        if isinstance(df.index, pd.DatetimeIndex):
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC")
        elif len(df) > 0:
            log.warning("live_bars has non-DatetimeIndex; re-creating")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
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


def _normalize_artefact_path(cfg: dict, p: str) -> str:
    """Return a usable absolute path for an artefact stored in the manifest.

    Manifests written on one machine store absolute paths that won't resolve
    on a different machine (e.g. GitHub Actions runner).  If the stored path
    doesn't exist, re-root it at the repo root by extracting the relative
    portion starting at 'artefacts/'.
    """
    if not os.path.isabs(p):
        return path(cfg, p)
    if os.path.exists(p):
        return p
    try:
        rel = p[p.index("artefacts/"):]
        candidate = path(cfg, rel)
        if os.path.exists(candidate):
            return candidate
    except ValueError:
        pass
    return p  # return original; caller will surface a clear FileNotFoundError


def _load_policy(cfg: dict, entry: dict):
    algo = entry.get("algorithm", "ppo").lower()
    cls = PPO if algo in ("ppo", "grpo") else A2C
    if cls is None:
        raise RuntimeError("stable_baselines3 not installed")
    p = _normalize_artefact_path(cfg, entry["policy_path"])
    return cls.load(p, device="cpu")


_MACRO_SLUG_TO_SYMBOL: dict[str, str] = {
    "vix": "^VIX",
    "gspc": "^GSPC",
    "tnx": "^TNX",
    "dxy": "DX-Y.NYB",
}


def _fetch_macro_data(ref_cols: list[str], start: pd.Timestamp) -> dict:
    """Fetch daily macro closes for every slug referenced in *ref_cols*.

    Detects required symbols from column names ending in ``_chg5`` /
    ``_chg20`` (e.g. ``vix_chg5`` → ``^VIX``), fetches 1 year of history
    before *start* so the rolling z-score is pre-warmed, and returns a dict
    suitable for passing directly to ``build_features(macro_data=...)``.
    """
    slugs = {c.rsplit("_chg", 1)[0] for c in ref_cols
             if c.endswith("_chg5") or c.endswith("_chg20")}
    if not slugs:
        return {}

    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance not installed; macro data unavailable")
        return {}

    # Give a 1-year pre-start buffer so the 252-bar z-score is populated.
    fetch_start = (start - pd.Timedelta(days=365)).normalize()
    fetch_end = pd.Timestamp.now(tz="UTC")

    result: dict = {}
    for slug in sorted(slugs):
        sym = _MACRO_SLUG_TO_SYMBOL.get(slug)
        if sym is None:
            log.warning("unknown macro slug '%s'; skipping", slug)
            continue
        try:
            raw = yf.download(
                sym, start=fetch_start, end=fetch_end, interval="1d",
                progress=False, auto_adjust=False, threads=False,
            )
        except Exception as exc:
            log.warning("macro fetch failed for %s: %s", sym, exc)
            continue
        if raw is None or len(raw) == 0:
            log.warning("no macro data for %s", sym)
            continue
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw = raw.rename(columns={"Close": "close"})
        if "close" not in raw.columns:
            log.warning("no Close column for %s", sym)
            continue
        if not isinstance(raw.index, pd.DatetimeIndex):
            raw.index = pd.to_datetime(raw.index, utc=True)
        elif raw.index.tz is None:
            raw.index = raw.index.tz_localize("UTC")
        else:
            raw.index = raw.index.tz_convert("UTC")
        result[sym] = raw[["close"]]
        log.info("macro %s: %d daily bars", sym, len(raw))

    return result


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

    # Fetch + append every bar since the last known one. On the very
    # first cron run this backfills the entire gap between training-end
    # and now (so the system can start trading immediately, not after a
    # 10-day organic warmup); subsequent runs return at most one new bar.
    if not args.offline:
        cutoff = max(
            train_ohlcv.index.max() if len(train_ohlcv) else pd.Timestamp.min.tz_localize("UTC"),
            live.index.max() if len(live) else pd.Timestamp.min.tz_localize("UTC"),
        )
        new = _fetch_bars_since(asset.symbol, asset.interval, cutoff)
        if not new.empty:
            new = new[new.index > cutoff]   # belt-and-braces dedupe
            if len(new):
                live = pd.concat([live, new])
                log.info("appended %d new bar(s); live=%d total", len(new), len(live))
            else:
                log.info("no new bar after dedupe; live=%d", len(live))
        else:
            log.info("no new bar from yfinance; live=%d", len(live))
    else:
        log.info("offline mode; skipping fetch")

    if len(live) == 0:
        log.warning("no live bars accumulated yet; nothing to step")
        _save_live_bars(live, live_path)
        return 0

    # Load reference feature columns from the training parquet so the live
    # recomputation produces the same schema (MI-pruned, with macros) that
    # the encoder was trained on.
    ref_feats = pd.read_parquet(feats_path)
    ref_cols = feature_columns(ref_feats)
    log.info("reference feature set: %d columns (%s…)", len(ref_cols), ref_cols[:3])

    # Fetch macro data required by the reference feature set (e.g. VIX, GSPC,
    # TNX) so build_features can reproduce the macro columns.
    macro_data: dict | None = None
    if not args.offline:
        macro_data = _fetch_macro_data(ref_cols, train_ohlcv.index.min())
        if not macro_data:
            log.warning("no macro data fetched; macro columns will be absent")

    # Recompute features on (training + live) OHLCV.
    combined = pd.concat([train_ohlcv, live])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    feats = build_features(
        combined,
        warmup_bars=int(cfg.get("features", {}).get("warmup_bars", 252)),
        zscore_window=int(cfg.get("features", {}).get("zscore_window", 252)),
        macro_data=macro_data,
    )
    if len(feats) == 0:
        log.error("feature recomputation produced 0 rows; check warmup config")
        return 2

    # Select only the columns the encoder was trained on, in the same order.
    # This handles MI-pruning (encoder input_dim matches ref_cols, not the
    # full build_features output) and ensures macro columns are present.
    missing_cols = [c for c in ref_cols if c not in feats.columns]
    if missing_cols:
        log.error("live features missing reference columns: %s", missing_cols)
        return 2
    passthrough = [c for c in ("close", "atr") if c in feats.columns]
    feats = feats[ref_cols + passthrough]
    log.info("live feature shape after column selection: %s", feats.shape)

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

    # Optional regime posterior. Lazy-import HMMRegimeModel so a missing
    # hmmlearn install degrades gracefully (no regime conditioning) instead
    # of crashing the whole trading loop.
    regime_post = None
    rp_rel = entry.get("regime_path") or "artefacts/regimes/hmm_gc_60m.pkl"
    rp_abs = _normalize_artefact_path(cfg, rp_rel)
    if os.path.exists(rp_abs):
        try:
            from src.data.regimes import HMMRegimeModel
            hmm = HMMRegimeModel.load(rp_abs)
            regime_post = hmm.posterior(close)
            pc["regime_posterior"] = regime_post
        except ImportError as exc:
            log.warning("hmmlearn not installed; regime conditioning disabled (%s)", exc)
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
