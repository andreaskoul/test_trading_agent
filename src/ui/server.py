"""FastAPI cockpit server.

Wires together the paper engine, bar feeds, and trade store, and exposes
a REST + WebSocket surface for the single-page frontend at ``/``.

The server is intentionally stateful: it keeps one :class:`PaperEngine`
per (asset, manifest_idx) session, started via ``POST /api/paper/start``
and torn down via ``POST /api/paper/stop``. WebSocket subscribers get a
multiplexed stream of ``bar``, ``signal``, ``trade``, ``equity`` and
``log`` events.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from stable_baselines3 import A2C, PPO

try:
    from sb3_contrib import RecurrentPPO
except ImportError:  # pragma: no cover
    RecurrentPPO = None  # type: ignore[assignment]

from ..data.config_utils import AssetConfig, parse_asset_configs
from ..data.features import feature_columns
from ..data.regimes import HMMRegimeModel
from ..env.trading_env import env_config_from_yaml
from ..live.feed import Bar, ReplayFeed, YFinanceFeed
from ..live.paper_engine import CostModel, PaperEngine, Signal, TradeStore
from ..models.meta_label import MetaLabelConfig, MetaLabelModel, build_trade_features
from ..models.precompute import precompute_embeddings
from ..training.pretrain_encoder import load_encoder

log = logging.getLogger("cockpit")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

from ..training.grpo import GRPO as _GRPO

_ALGO_MAP: dict[str, type] = {"ppo": PPO, "a2c": A2C, "grpo": _GRPO}
if RecurrentPPO is not None:
    _ALGO_MAP["recurrent_ppo"] = RecurrentPPO
    _ALGO_MAP["rppo"] = RecurrentPPO


# ---------------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------------


def _load_config(path: Optional[str] = None) -> dict:
    path = path or os.path.join(_REPO_ROOT, "configs", "default.yaml")
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)
    cfg["__repo_root__"] = _REPO_ROOT
    return cfg


def _path(cfg: dict, *parts: str) -> str:
    return os.path.join(cfg["__repo_root__"], *parts)


def _asset_features_path(cfg: dict, asset: AssetConfig) -> str:
    """Return the features parquet path for an asset, falling back to the
    legacy single-asset ``features.parquet`` if the per-asset file is
    missing (so a cockpit can open against older artefact sets)."""
    primary = _path(cfg, asset.features_path) if asset.features_path else ""
    if primary and os.path.exists(primary):
        return primary
    legacy = _path(cfg, "data/processed/features.parquet")
    if os.path.exists(legacy):
        log.warning("features file %s missing; falling back to %s", primary, legacy)
        return legacy
    return primary


def _load_manifest(cfg: dict) -> list[dict]:
    manifest_path = _path(cfg, cfg["artefact_dir"], "ppo_manifest.json")
    if not os.path.exists(manifest_path):
        return []
    with open(manifest_path) as f:
        manifest = json.load(f)
    assets = parse_asset_configs(cfg)
    default_asset = assets[0].symbol if assets else "unknown"
    for entry in manifest:
        if "asset" not in entry:
            entry["asset"] = default_asset
        if "encoder_group" not in entry:
            entry["encoder_group"] = int(entry.get("split", 0))
    return manifest


class Hub:
    """Broadcast pub/sub to all connected WebSocket clients.

    A simple fan-out: each client gets its own asyncio.Queue. Publishers
    are non-blocking; if a queue fills up we drop the oldest message
    rather than stall the paper engine.
    """

    def __init__(self) -> None:
        self._clients: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._clients.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            self._clients.discard(q)

    async def publish(self, channel: str, payload: dict) -> None:
        msg = json.dumps({"channel": channel, "payload": payload})
        async with self._lock:
            dead: list[asyncio.Queue] = []
            for q in self._clients:
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    try:
                        q.get_nowait()
                        q.put_nowait(msg)
                    except Exception:
                        dead.append(q)
            for q in dead:
                self._clients.discard(q)


@dataclass
class Session:
    asset: str
    manifest_idx: int
    mode: str  # "live" or "replay"
    engine: PaperEngine
    feed: object  # BarFeed subclass
    task: asyncio.Task
    run_id: str


class CockpitState:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.assets: list[AssetConfig] = parse_asset_configs(cfg)
        self.env_cfg = env_config_from_yaml(cfg)
        self.manifest: list[dict] = _load_manifest(cfg)
        self.hub = Hub()
        db_path = _path(cfg, cfg.get("ui", {}).get("db_path", "artefacts/paper_trades.db"))
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.store = TradeStore(db_path)
        self._precomputed_cache: dict[tuple[str, int], dict] = {}
        self._meta_cache: dict[str, Optional[MetaLabelModel]] = {}
        self.session: Optional[Session] = None

    # ------------------------------------------------------------------

    def _asset_by_symbol(self, symbol: str) -> Optional[AssetConfig]:
        for a in self.assets:
            if a.symbol == symbol:
                return a
        return None

    def _build_precomputed(self, asset: AssetConfig, encoder_group: int) -> dict:
        key = (asset.symbol, encoder_group)
        if key in self._precomputed_cache:
            return self._precomputed_cache[key]
        feats_path = _asset_features_path(self.cfg, asset)
        if not feats_path or not os.path.exists(feats_path):
            raise FileNotFoundError(f"features parquet missing for {asset.symbol}")
        features = pd.read_parquet(feats_path)
        feat_cols = feature_columns(features)
        enc_path = _path(
            self.cfg,
            self.cfg["artefact_dir"],
            "encoders",
            f"encoder_group{encoder_group}.pt",
        )
        if not os.path.exists(enc_path):
            raise FileNotFoundError(f"encoder missing: {enc_path}")
        encoder = load_encoder(enc_path)
        feat_arr = features[feat_cols].to_numpy(dtype=np.float32)
        emb = precompute_embeddings(encoder, feat_arr, seq_len=self.env_cfg.seq_len)
        close = features["close"].to_numpy(dtype=np.float64)
        atr = features["atr"].to_numpy(dtype=np.float64)
        rv = pd.Series(atr / close).rolling(20, min_periods=1).mean()
        vol_q = rv.rank(pct=True).to_numpy()
        pc = {
            "close": close,
            "atr": atr,
            "embeddings": emb,
            "vol_quantile": vol_q,
            "timestamps": features.index,
            "features": features,
        }
        self._precomputed_cache[key] = pc
        return pc

    def _load_regime(self, entry: dict) -> Optional[np.ndarray]:
        rp = entry.get("regime_path")
        if not rp:
            return None
        abs_rp = rp if os.path.isabs(rp) else _path(self.cfg, rp)
        if not os.path.exists(abs_rp):
            return None
        hmm = HMMRegimeModel.load(abs_rp)
        pc = self._build_precomputed(
            self._asset_by_symbol(entry["asset"]),  # type: ignore[arg-type]
            int(entry["encoder_group"]),
        )
        return hmm.posterior(pc["close"])

    def _load_model(self, entry: dict):
        algo = entry.get("algorithm", "ppo").lower()
        cls = _ALGO_MAP.get(algo, PPO)
        policy_path = entry["policy_path"]
        if not os.path.isabs(policy_path):
            policy_path = _path(self.cfg, policy_path)
        return cls.load(policy_path, device="cpu")

    def _fit_meta_model(self, asset_symbol: str) -> Optional[MetaLabelModel]:
        """Build a simple meta-labeler from the asset's own historical runs.

        We don't have per-asset cross-asset training data at cockpit
        startup, so this reconstructs one from the manifest entries for
        the selected asset by importing ``rollout_policy`` with tracing.
        Result is cached.
        """
        if asset_symbol in self._meta_cache:
            return self._meta_cache[asset_symbol]
        # Lazy import to keep startup fast.
        from ..training.evaluate import build_precomputed, rollout_policy

        entries = [e for e in self.manifest if e.get("asset") == asset_symbol]
        if not entries:
            self._meta_cache[asset_symbol] = None
            return None
        asset = self._asset_by_symbol(asset_symbol)
        if asset is None:
            self._meta_cache[asset_symbol] = None
            return None
        feats_path = _asset_features_path(self.cfg, asset)
        if not os.path.exists(feats_path):
            self._meta_cache[asset_symbol] = None
            return None
        features = pd.read_parquet(feats_path)
        feat_cols = feature_columns(features)
        X_parts: list[np.ndarray] = []
        y_parts: list[np.ndarray] = []
        for entry in entries[: min(4, len(entries))]:
            try:
                enc_path = _path(
                    self.cfg,
                    self.cfg["artefact_dir"],
                    "encoders",
                    f"encoder_group{entry['encoder_group']}.pt",
                )
                encoder = load_encoder(enc_path)
                pc = build_precomputed(features, feat_cols, encoder, seq_len=self.env_cfg.seq_len)
                model = self._load_model(entry)
                test_idx = np.concatenate(
                    [np.arange(int(g[1]), int(g[2]) + 1) for g in entry["test_blocks"]]
                )
                result = rollout_policy(model, pc, self.env_cfg, test_idx, trace_entries=True)
                if result.trade_features is not None and len(result.trade_features) > 0:
                    X_parts.append(result.trade_features)
                    y_parts.append((result.trade_returns > 0).astype(np.int64))
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("meta training rollout failed for %s: %s", entry, exc)
        if not X_parts:
            self._meta_cache[asset_symbol] = None
            return None
        X = np.concatenate(X_parts, axis=0)
        y = np.concatenate(y_parts, axis=0)
        mm = MetaLabelModel(MetaLabelConfig()).fit(X, y)
        self._meta_cache[asset_symbol] = mm
        return mm

    # ------------------------------------------------------------------
    # session control
    # ------------------------------------------------------------------

    async def start_session(
        self,
        *,
        asset_symbol: str,
        manifest_idx: int,
        mode: str,
        costs: CostModel,
        meta_threshold: float,
        replay_start: Optional[int] = None,
        replay_end: Optional[int] = None,
        replay_speed: float = 10.0,
    ) -> dict:
        if self.session is not None:
            await self.stop_session()
        if manifest_idx < 0 or manifest_idx >= len(self.manifest):
            raise HTTPException(400, f"manifest_idx {manifest_idx} out of range")
        entry = self.manifest[manifest_idx]
        if entry.get("asset") != asset_symbol:
            raise HTTPException(
                400, f"manifest entry {manifest_idx} is for {entry.get('asset')}, not {asset_symbol}"
            )
        asset = self._asset_by_symbol(asset_symbol)
        if asset is None:
            raise HTTPException(404, f"unknown asset {asset_symbol!r}")

        pc = self._build_precomputed(asset, int(entry["encoder_group"]))
        regime_post = self._load_regime(entry)
        pc_use = dict(pc)
        if regime_post is not None:
            pc_use["regime_posterior"] = regime_post

        model = self._load_model(entry)
        meta_model = self._fit_meta_model(asset_symbol)

        env_cfg = self.env_cfg
        # Replace spread_bps with the user-selected one so the backtest
        # cost model inside the env stays consistent with the UI knob.
        from dataclasses import replace

        env_cfg_for_session = replace(env_cfg, spread_bps=costs.spread_bps)

        run_id = f"{asset_symbol}-m{manifest_idx}-{mode}-{int(asyncio.get_event_loop().time())}"
        engine = PaperEngine(
            asset=asset_symbol,
            run_id=run_id,
            model=model,
            precomputed=pc_use,
            env_cfg=env_cfg_for_session,
            cost_model=costs,
            meta_model=meta_model,
            meta_threshold=meta_threshold,
            timestamps=pc["timestamps"] if isinstance(pc["timestamps"], pd.DatetimeIndex) else None,
            store=self.store,
        )

        if mode == "replay":
            if replay_start is None or replay_end is None:
                # Default to the first test block of the manifest entry.
                blocks = entry.get("test_blocks", [])
                if blocks:
                    replay_start = int(blocks[0][1])
                    replay_end = int(blocks[0][2]) + 1
                else:
                    replay_start = 0
                    replay_end = len(pc["close"])
            feat_df = pc["features"]
            feed = ReplayFeed(
                asset=asset_symbol,
                ohlcv=feat_df,
                start_idx=int(replay_start),
                end_idx=int(replay_end),
                speed=float(replay_speed),
                bar_interval_seconds=float(
                    self.cfg.get("ui", {}).get("paper", {}).get("bar_interval_seconds", 60.0)
                ),
            )
        elif mode == "live":
            feed = YFinanceFeed(
                asset=asset_symbol,
                interval="1m",
                bar_interval_seconds=float(
                    self.cfg.get("ui", {}).get("paper", {}).get("bar_interval_seconds", 60.0)
                ),
            )
            # Live mode still drives the engine over historical indices for
            # now; a proper live path would extend pc arrays in real time.
            # Emit a warning so the user knows the MVP limitation.
            log.warning(
                "live mode emits signals from latest precomputed bar; full "
                "live-encoder streaming is a future tier."
            )
        else:
            raise HTTPException(400, f"unknown mode {mode!r}")

        task = asyncio.create_task(self._run_session(engine, feed, mode))
        self.session = Session(
            asset=asset_symbol,
            manifest_idx=manifest_idx,
            mode=mode,
            engine=engine,
            feed=feed,
            task=task,
            run_id=run_id,
        )
        return {"run_id": run_id, "mode": mode, "asset": asset_symbol}

    async def stop_session(self) -> dict:
        sess = self.session
        if sess is None:
            return {"stopped": False}
        try:
            sess.feed.stop()  # type: ignore[attr-defined]
        except Exception:
            pass
        sess.task.cancel()
        try:
            await sess.task
        except (asyncio.CancelledError, Exception):
            pass
        self.session = None
        await self.hub.publish("log", {"level": "info", "msg": f"session {sess.run_id} stopped"})
        return {"stopped": True, "run_id": sess.run_id}

    async def _run_session(self, engine: PaperEngine, feed, mode: str) -> None:
        await self.hub.publish(
            "log", {"level": "info", "msg": f"session {engine.run_id} started ({mode})"}
        )
        try:
            async for bar in feed.subscribe():
                await self._process_bar(engine, bar)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("session failed: %s", exc)
            await self.hub.publish("log", {"level": "error", "msg": str(exc)})
        finally:
            await self.hub.publish(
                "log", {"level": "info", "msg": f"session {engine.run_id} finished"}
            )

    async def _process_bar(self, engine: PaperEngine, bar: Bar) -> None:
        # Replay bars carry idx; live bars don't — for now we don't
        # advance the engine on live bars because the encoder isn't
        # streaming yet. We still publish the bar so the UI shows it.
        await self.hub.publish("bar", bar.to_dict())
        if bar.idx is None:
            return
        sig: Signal = engine.step(bar.idx)
        payload = sig.to_dict()
        payload["asset"] = engine.asset
        await self.hub.publish("signal", payload)
        if sig.fired:
            records = engine.trade_records()
            if records:
                rec = records[-1]
                await self.hub.publish(
                    "trade",
                    {
                        "trade_id": rec.trade_id,
                        "asset": rec.asset,
                        "run_id": rec.run_id,
                        "direction": rec.direction,
                        "entry_idx": rec.entry_idx,
                        "exit_idx": rec.exit_idx,
                        "entry_ts": None if rec.entry_ts is None else str(rec.entry_ts),
                        "exit_ts": None if rec.exit_ts is None else str(rec.exit_ts),
                        "entry_price": rec.entry_price,
                        "exit_price": rec.exit_price,
                        "pnl": rec.pnl,
                        "meta_prob": rec.meta_prob,
                        "regime_idx": rec.regime_idx,
                        "vol_q": rec.vol_q,
                        "barrier": rec.barrier,
                    },
                )
        await self.hub.publish(
            "equity",
            {
                "asset": engine.asset,
                "idx": sig.idx,
                "equity": sig.equity,
                "n_trades": len(engine.trade_returns()),
            },
        )


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = _load_config()
    app.state.cockpit = CockpitState(cfg)
    log.info(
        "cockpit ready: %d assets, %d manifest entries, db=%s",
        len(app.state.cockpit.assets),
        len(app.state.cockpit.manifest),
        app.state.cockpit.store.db_path,
    )
    yield
    if app.state.cockpit.session is not None:
        await app.state.cockpit.stop_session()


app = FastAPI(title="Trading Cockpit", lifespan=lifespan)

if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


def _state(app: FastAPI) -> CockpitState:
    return app.state.cockpit


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------


@app.get("/")
async def index():
    path = os.path.join(_STATIC_DIR, "index.html")
    if not os.path.exists(path):
        return JSONResponse({"error": "index.html not found"}, status_code=404)
    return FileResponse(path)


# ---------------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------------


@app.get("/api/assets")
async def api_assets():
    s = _state(app)
    out = []
    for a in s.assets:
        entries = [e for e in s.manifest if e.get("asset") == a.symbol]
        out.append(
            {
                "symbol": a.symbol,
                "interval": a.interval,
                "features_path": a.features_path,
                "n_runs": len(entries),
            }
        )
    return out


@app.get("/api/manifest")
async def api_manifest():
    return _state(app).manifest


@app.get("/api/metrics")
async def api_metrics():
    s = _state(app)
    summary_path = _path(s.cfg, s.cfg["report_dir"], "evaluation_summary.json")
    summary = {}
    if os.path.exists(summary_path):
        with open(summary_path) as f:
            summary = json.load(f)
    per_run = []
    csv_path = _path(s.cfg, s.cfg["report_dir"], "per_run_metrics.csv")
    if os.path.exists(csv_path):
        per_run = pd.read_csv(csv_path).to_dict(orient="records")
    return {"summary": summary, "per_run": per_run}


@app.get("/api/trades")
async def api_trades(asset: Optional[str] = None, limit: int = 500):
    s = _state(app)
    return s.store.list_trades(asset=asset, limit=int(limit))


@app.get("/api/trades/{trade_id}")
async def api_trade(trade_id: int):
    s = _state(app)
    rec = s.store.get(int(trade_id))
    if rec is None:
        raise HTTPException(404, f"trade {trade_id} not found")
    return rec


@app.post("/api/paper/start")
async def api_paper_start(body: dict):
    s = _state(app)
    cost_block = body.get("costs") or {}
    cost = CostModel(
        spread_bps=float(cost_block.get("spread_bps", s.env_cfg.spread_bps)),
        slippage_bps=float(cost_block.get("slippage_bps", 0.0)),
        commission_usd=float(cost_block.get("commission_usd", 0.0)),
    )
    return await s.start_session(
        asset_symbol=body["asset"],
        manifest_idx=int(body["manifest_idx"]),
        mode=str(body.get("mode", "replay")),
        costs=cost,
        meta_threshold=float(
            body.get(
                "meta_threshold",
                s.cfg.get("ui", {}).get("paper", {}).get("meta_threshold", 0.55),
            )
        ),
        replay_start=body.get("replay_start"),
        replay_end=body.get("replay_end"),
        replay_speed=float(body.get("replay_speed", 10.0)),
    )


@app.post("/api/paper/stop")
async def api_paper_stop():
    return await _state(app).stop_session()


@app.get("/api/paper/state")
async def api_paper_state():
    s = _state(app)
    if s.session is None:
        return {"running": False}
    return {
        "running": True,
        "asset": s.session.asset,
        "manifest_idx": s.session.manifest_idx,
        "mode": s.session.mode,
        "run_id": s.session.run_id,
        "engine": s.session.engine.state(),
    }


@app.post("/api/explain")
async def api_explain(body: dict):
    from .explain import explain_trade

    s = _state(app)
    trade_id = int(body["trade_id"])
    rec = s.store.get(trade_id)
    if rec is None:
        raise HTTPException(404, f"trade {trade_id} not found")
    if rec.get("explanation"):
        return {"trade_id": trade_id, "explanation": rec["explanation"], "cached": True}
    text = await explain_trade(rec, s.cfg)
    s.store.set_explanation(trade_id, text)
    return {"trade_id": trade_id, "explanation": text, "cached": False}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    s = _state(app)
    await ws.accept()
    q = await s.hub.subscribe()
    try:
        while True:
            msg = await q.get()
            await ws.send_text(msg)
    except WebSocketDisconnect:
        pass
    finally:
        await s.hub.unsubscribe(q)
