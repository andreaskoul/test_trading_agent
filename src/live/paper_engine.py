"""Paper-trading engine that mirrors ``rollout_policy`` bar-by-bar.

The research pipeline runs a policy in one shot over a pre-computed
(N, hidden_size) embedding matrix (see ``src.training.evaluate``). The
cockpit needs the same logic driven from a streaming bar feed — live
yfinance ticks or a replayed historical window — so the user sees
trades opening and closing as the market moves.

This module keeps both paths semantically identical. ``PaperEngine`` is
a thin state machine that, given a cursor index ``i`` into the asset's
precomputed arrays, performs one step of the ``rollout_policy`` loop
and reports what happened. Running it from 0..N-1 over a test window
produces the *same* trade returns as ``rollout_policy`` — the parity
test in ``tests/test_cockpit.py`` enforces this byte-for-byte.

Extra knobs on top of the backtester:

* ``slippage_bps``: deducted once per round trip in addition to the
  ``spread_bps`` the env already charges. Scales linearly with the
  volatility quantile so illiquid bars are more expensive.
* ``commission_usd``: flat per-round-trip commission in notional USD,
  converted to a fractional-return deduction using the entry price.
  (Default 0 preserves backtest parity.)

Trades are persisted to SQLite so the cockpit can reopen and explain
them after a restart.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

import numpy as np
import pandas as pd

from ..env.trading_env import BUY, HOLD, SELL, EnvConfig
from ..models.meta_label import MetaLabelModel, build_trade_features

log = logging.getLogger(__name__)


@dataclass
class CostModel:
    """Realistic cost knobs surfaced to the cockpit UI."""

    spread_bps: float = 2.0
    slippage_bps: float = 0.0
    commission_usd: float = 0.0

    def roundtrip_deduction(self, entry_price: float, vol_q: float) -> float:
        """Fractional return deducted from a round trip.

        Spread is the backtester's ``2 * spread_bps / 1e4``; slippage
        scales with the vol quantile (illiquid bars hurt more);
        commission is converted from USD to fraction of notional.
        """
        spread = 2.0 * self.spread_bps / 1e4
        slip = 2.0 * self.slippage_bps / 1e4 * max(0.1, float(vol_q))
        comm_frac = 0.0
        if entry_price > 0 and self.commission_usd > 0:
            # Two commissions per round trip.
            comm_frac = 2.0 * self.commission_usd / entry_price
        return float(spread + slip + comm_frac)


@dataclass
class Signal:
    """One step's output, serialised to the WebSocket frontend."""

    ts: Optional[pd.Timestamp]
    idx: int
    price: float
    action: int  # HOLD/BUY/SELL emitted THIS bar
    position: int  # 0 / +1 / -1 AFTER this step
    meta_prob: Optional[float]
    regime_idx: Optional[int]
    regime_post: Optional[list]
    vol_q: float
    pnl: float  # realised PnL on the trade that just fired (0 otherwise)
    equity: float  # cumulative (1 + ret).prod()
    fired: bool  # True when a trade closed on this bar
    open_position: Optional[dict]  # {entry_i, entry_price, direction} or None

    def to_dict(self) -> dict:
        out = {
            "ts": None if self.ts is None else str(self.ts),
            "idx": int(self.idx),
            "price": float(self.price),
            "action": int(self.action),
            "position": int(self.position),
            "meta_prob": None if self.meta_prob is None else float(self.meta_prob),
            "regime_idx": None if self.regime_idx is None else int(self.regime_idx),
            "regime_post": None if self.regime_post is None else list(self.regime_post),
            "vol_q": float(self.vol_q),
            "pnl": float(self.pnl),
            "equity": float(self.equity),
            "fired": bool(self.fired),
            "open_position": self.open_position,
        }
        return out


@dataclass
class TradeRecord:
    trade_id: Optional[int]
    asset: str
    run_id: str
    direction: int
    entry_idx: int
    exit_idx: int
    entry_ts: Optional[pd.Timestamp]
    exit_ts: Optional[pd.Timestamp]
    entry_price: float
    exit_price: float
    pnl: float
    meta_prob: Optional[float]
    regime_idx: Optional[int]
    vol_q: float
    barrier: str  # "tp" / "sl" / "timeout"
    entry_features: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    embedding: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))


# ---------------------------------------------------------------------------
# SQLite persistence
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    run_id TEXT NOT NULL,
    direction INTEGER NOT NULL,
    entry_idx INTEGER NOT NULL,
    exit_idx INTEGER NOT NULL,
    entry_ts TEXT,
    exit_ts TEXT,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    pnl REAL NOT NULL,
    meta_prob REAL,
    regime_idx INTEGER,
    vol_q REAL NOT NULL,
    barrier TEXT NOT NULL,
    entry_features_json TEXT,
    embedding_json TEXT,
    explanation TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS trades_asset_idx ON trades(asset);
CREATE INDEX IF NOT EXISTS trades_run_idx ON trades(run_id);
"""


class TradeStore:
    """Thread-safe SQLite trade log. One DB per cockpit install."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = Lock()
        with self._connect() as conn:
            conn.executescript(_DDL)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def insert(self, rec: TradeRecord) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO trades
                  (asset, run_id, direction, entry_idx, exit_idx,
                   entry_ts, exit_ts, entry_price, exit_price, pnl,
                   meta_prob, regime_idx, vol_q, barrier,
                   entry_features_json, embedding_json, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    rec.asset,
                    rec.run_id,
                    int(rec.direction),
                    int(rec.entry_idx),
                    int(rec.exit_idx),
                    None if rec.entry_ts is None else str(rec.entry_ts),
                    None if rec.exit_ts is None else str(rec.exit_ts),
                    float(rec.entry_price),
                    float(rec.exit_price),
                    float(rec.pnl),
                    None if rec.meta_prob is None else float(rec.meta_prob),
                    None if rec.regime_idx is None else int(rec.regime_idx),
                    float(rec.vol_q),
                    rec.barrier,
                    json.dumps(rec.entry_features.tolist()) if rec.entry_features.size else None,
                    json.dumps(rec.embedding.tolist()) if rec.embedding.size else None,
                    time.time(),
                ),
            )
            return int(cur.lastrowid)

    def set_explanation(self, trade_id: int, text: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE trades SET explanation=? WHERE trade_id=?",
                (text, int(trade_id)),
            )

    def list_trades(self, asset: Optional[str] = None, limit: int = 500) -> list[dict]:
        with self._lock, self._connect() as conn:
            if asset:
                cur = conn.execute(
                    "SELECT * FROM trades WHERE asset=? ORDER BY trade_id DESC LIMIT ?",
                    (asset, int(limit)),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM trades ORDER BY trade_id DESC LIMIT ?",
                    (int(limit),),
                )
            return [dict(r) for r in cur.fetchall()]

    def get(self, trade_id: int) -> Optional[dict]:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM trades WHERE trade_id=?", (int(trade_id),)
            )
            row = cur.fetchone()
            return dict(row) if row else None


# ---------------------------------------------------------------------------
# Paper engine
# ---------------------------------------------------------------------------


class PaperEngine:
    """Stateful bar-by-bar wrapper around a frozen PPO/A2C/RecurrentPPO policy.

    ``step(i)`` advances the cursor to bar ``i`` and returns a :class:`Signal`.
    The caller is responsible for incrementing ``i`` exactly once per bar —
    ``ReplayFeed`` and the live loop both do this.

    For backtest parity, ``step`` reproduces ``rollout_policy``'s control
    flow: emit BUY/SELL only while flat, run meta-label gating if supplied,
    then check the triple-barrier. When a barrier fires, the trade is
    persisted to ``TradeStore`` and ``Signal.fired`` is True.
    """

    def __init__(
        self,
        *,
        asset: str,
        run_id: str,
        model,
        precomputed: dict,
        env_cfg: EnvConfig,
        cost_model: Optional[CostModel] = None,
        meta_model: Optional[MetaLabelModel] = None,
        meta_threshold: float = 0.5,
        timestamps: Optional[pd.DatetimeIndex] = None,
        store: Optional[TradeStore] = None,
    ) -> None:
        self.asset = asset
        self.run_id = run_id
        self.model = model
        self.env_cfg = env_cfg
        self.cost = cost_model or CostModel(spread_bps=env_cfg.spread_bps)
        self.meta_model = meta_model
        self.meta_threshold = float(meta_threshold)
        self.store = store

        self._close = np.asarray(precomputed["close"], dtype=np.float64)
        self._atr = np.asarray(precomputed["atr"], dtype=np.float64)
        self._emb = np.asarray(precomputed["embeddings"], dtype=np.float32)
        self._vol_q = np.asarray(precomputed["vol_quantile"], dtype=np.float64)
        rp = precomputed.get("regime_posterior")
        self._regime = None if rp is None else np.asarray(rp, dtype=np.float32)
        self._timestamps = timestamps

        self._pos = 0
        self._entry_i = -1
        self._entry_price = 0.0
        self._barrier_upper = 0.0
        self._barrier_lower = 0.0
        self._pending_entry: Optional[tuple[np.ndarray, int, float, Optional[float]]] = None
        self._trades: list[float] = []
        self._trade_records: list[TradeRecord] = []

    # ------------------------------------------------------------------
    # observation helpers
    # ------------------------------------------------------------------

    def _obs(self, i: int) -> np.ndarray:
        """Identical to ``EmbeddingTradingEnv._obs``."""
        i = min(i, len(self._close) - 1)
        emb = self._emb[i].astype(np.float32)
        if self._regime is None:
            return emb
        return np.concatenate([emb, self._regime[i]]).astype(np.float32)

    # ------------------------------------------------------------------
    # trade bookkeeping
    # ------------------------------------------------------------------

    def _open_position(self, direction: int, i: int) -> None:
        self._pos = direction
        self._entry_i = i
        self._entry_price = float(self._close[i])
        atr_now = max(float(self._atr[i]), 1e-8)
        if direction == +1:
            self._barrier_upper = self._entry_price + self.env_cfg.rr_upper * atr_now
            self._barrier_lower = self._entry_price - self.env_cfg.rr_lower * atr_now
        else:
            self._barrier_upper = self._entry_price - self.env_cfg.rr_upper * atr_now
            self._barrier_lower = self._entry_price + self.env_cfg.rr_lower * atr_now

    def _fire_trade(self, i: int, exit_price: float, barrier: str) -> float:
        """Compute realised return using the CURRENT cost model and persist."""
        pos = self._pos
        # Base return as in rollout_policy / env: price-ratio times direction
        # with a spread-only deduction. The UI cost knobs add on top.
        raw = pos * (exit_price / self._entry_price - 1.0)
        base_spread = 2.0 * self.env_cfg.spread_bps / 1e4
        ui_deduction = self.cost.roundtrip_deduction(
            self._entry_price, float(self._vol_q[self._entry_i])
        )
        # The backtester's reference deducts only ``base_spread``. The UI may
        # charge more (slippage + commission) on top. The delta vs reference
        # is ``ui_deduction - base_spread`` which is always >= 0 so trades
        # become strictly more expensive.
        extra = max(0.0, ui_deduction - base_spread)
        ret = raw - base_spread - extra
        self._trades.append(float(ret))

        entry_feats = (
            np.zeros(self._emb.shape[1] + 2, dtype=np.float32)
            if self._pending_entry is None
            else self._pending_entry[0]
        )
        meta_prob = None if self._pending_entry is None else self._pending_entry[3]
        regime_idx = None
        if self._regime is not None:
            regime_idx = int(np.argmax(self._regime[self._entry_i]))

        rec = TradeRecord(
            trade_id=None,
            asset=self.asset,
            run_id=self.run_id,
            direction=pos,
            entry_idx=self._entry_i,
            exit_idx=i,
            entry_ts=self._ts(self._entry_i),
            exit_ts=self._ts(i),
            entry_price=self._entry_price,
            exit_price=float(exit_price),
            pnl=float(ret),
            meta_prob=meta_prob,
            regime_idx=regime_idx,
            vol_q=float(self._vol_q[self._entry_i]),
            barrier=barrier,
            entry_features=entry_feats,
            embedding=self._emb[self._entry_i].astype(np.float32),
        )
        if self.store is not None:
            rec.trade_id = self.store.insert(rec)
        self._trade_records.append(rec)

        self._pos = 0
        self._entry_i = -1
        self._pending_entry = None
        return float(ret)

    def _ts(self, i: int) -> Optional[pd.Timestamp]:
        if self._timestamps is None:
            return None
        if 0 <= i < len(self._timestamps):
            return self._timestamps[i]
        return None

    # ------------------------------------------------------------------
    # step
    # ------------------------------------------------------------------

    def step(self, i: int) -> Signal:
        """Run one bar. Mirrors ``rollout_policy``'s inner loop.

        ``i`` is the bar index into the precomputed arrays. It must be the
        *current* bar the policy observes, i.e. the bar we might open on or
        close on.
        """
        n = len(self._close)
        if i < 0 or i >= n:
            raise IndexError(f"bar index {i} out of range [0, {n})")

        price = float(self._close[i])
        vol_q = float(self._vol_q[i])
        action = HOLD
        fired = False
        pnl = 0.0
        meta_prob_for_signal: Optional[float] = None

        if self._pos == 0:
            obs = self._obs(i)
            raw, _ = self.model.predict(obs, deterministic=True)
            a = int(raw)
            if a != HOLD:
                direction = +1 if a == BUY else -1
                feats = build_trade_features(obs, direction, vol_q)
                gated = False
                p_profit: Optional[float] = None
                if self.meta_model is not None:
                    p_profit = float(self.meta_model.predict_proba(feats)[0])
                    if p_profit < self.meta_threshold:
                        a = HOLD
                        gated = True
                if not gated:
                    self._pending_entry = (feats, direction, price, p_profit)
                    self._open_position(direction, i)
                    action = a
                    meta_prob_for_signal = p_profit
                else:
                    self._pending_entry = None
                    meta_prob_for_signal = p_profit
        else:
            # We hold until a barrier fires; meta-prob is only meaningful
            # at entry, not mid-trade.
            horizon_exceeded = (i - self._entry_i) >= self.env_cfg.horizon
            hit_tp = False
            hit_sl = False
            if self._pos == +1:
                hit_tp = price >= self._barrier_upper
                hit_sl = price <= self._barrier_lower
            else:
                hit_tp = price <= self._barrier_upper
                hit_sl = price >= self._barrier_lower

            if hit_tp:
                pnl = self._fire_trade(i, self._barrier_upper, "tp")
                fired = True
            elif hit_sl:
                pnl = self._fire_trade(i, self._barrier_lower, "sl")
                fired = True
            elif horizon_exceeded:
                pnl = self._fire_trade(i, price, "timeout")
                fired = True

        equity = float(np.prod(1.0 + np.asarray(self._trades))) if self._trades else 1.0
        regime_idx = None
        regime_post = None
        if self._regime is not None:
            regime_idx = int(np.argmax(self._regime[i]))
            regime_post = self._regime[i].astype(float).tolist()

        open_pos = None
        if self._pos != 0:
            open_pos = {
                "entry_i": int(self._entry_i),
                "entry_ts": str(self._ts(self._entry_i)) if self._ts(self._entry_i) else None,
                "entry_price": float(self._entry_price),
                "direction": int(self._pos),
                "barrier_upper": float(self._barrier_upper),
                "barrier_lower": float(self._barrier_lower),
            }

        return Signal(
            ts=self._ts(i),
            idx=i,
            price=price,
            action=action,
            position=self._pos,
            meta_prob=meta_prob_for_signal,
            regime_idx=regime_idx,
            regime_post=regime_post,
            vol_q=vol_q,
            pnl=pnl,
            equity=equity,
            fired=fired,
            open_position=open_pos,
        )

    # ------------------------------------------------------------------
    # snapshots for the UI
    # ------------------------------------------------------------------

    def trade_returns(self) -> np.ndarray:
        return np.asarray(self._trades, dtype=float)

    def trade_records(self) -> list[TradeRecord]:
        return list(self._trade_records)

    def state(self) -> dict:
        return {
            "asset": self.asset,
            "run_id": self.run_id,
            "position": int(self._pos),
            "entry_idx": int(self._entry_i) if self._entry_i >= 0 else None,
            "entry_price": float(self._entry_price) if self._pos != 0 else None,
            "n_trades": len(self._trades),
            "equity": float(np.prod(1.0 + np.asarray(self._trades))) if self._trades else 1.0,
            "cost_model": {
                "spread_bps": self.cost.spread_bps,
                "slippage_bps": self.cost.slippage_bps,
                "commission_usd": self.cost.commission_usd,
            },
            "meta_threshold": self.meta_threshold,
        }
