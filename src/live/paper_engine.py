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
import math
import sqlite3
import time
from collections import deque
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

    def list_trades(
        self,
        asset: Optional[str] = None,
        limit: int = 500,
        run_id: Optional[str] = None,
        run_ids: Optional[list[str]] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> list[dict]:
        """Filterable trade list. ``since`` / ``until`` are unix seconds
        (compared against ``created_at``). Pass ``run_ids`` (list) to
        filter by an algorithm-resolved subset."""
        clauses: list[str] = []
        args: list = []
        if asset:
            clauses.append("asset=?"); args.append(asset)
        if run_id:
            clauses.append("run_id=?"); args.append(run_id)
        if run_ids:
            placeholders = ",".join("?" * len(run_ids))
            clauses.append(f"run_id IN ({placeholders})")
            args.extend(run_ids)
        if since is not None:
            clauses.append("created_at >= ?"); args.append(float(since))
        if until is not None:
            clauses.append("created_at <= ?"); args.append(float(until))
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM trades {where} ORDER BY trade_id DESC LIMIT ?"
        args.append(int(limit))
        with self._lock, self._connect() as conn:
            cur = conn.execute(sql, args)
            return [dict(r) for r in cur.fetchall()]

    def get(self, trade_id: int) -> Optional[dict]:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM trades WHERE trade_id=?", (int(trade_id),)
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def sessions(self, limit: int = 200) -> list[dict]:
        """Phase N4: one summary row per distinct ``run_id``.

        Returns the most recent ``limit`` sessions ordered by ``ended_at``
        descending, with per-session PnL/Sharpe/DD already computed.
        """
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "SELECT run_id, asset, MIN(created_at) AS started_at, "
                "MAX(created_at) AS ended_at, COUNT(*) AS n_trades, "
                "GROUP_CONCAT(pnl) AS pnls "
                "FROM trades GROUP BY run_id "
                "ORDER BY ended_at DESC LIMIT ?",
                (int(limit),),
            )
            rows = cur.fetchall()
        out: list[dict] = []
        for r in rows:
            pnls = np.array([float(x) for x in r["pnls"].split(",")], dtype=float)
            equity = np.cumprod(1.0 + pnls)
            peak = np.maximum.accumulate(equity)
            dd = float(((equity - peak) / peak).min()) if pnls.size else 0.0
            std = float(pnls.std(ddof=1)) if pnls.size > 1 else 0.0
            out.append({
                "run_id": r["run_id"],
                "asset": r["asset"],
                "started_at": float(r["started_at"]),
                "ended_at": float(r["ended_at"]),
                "n_trades": int(r["n_trades"]),
                "total_return": float(equity[-1] - 1.0) if pnls.size else 0.0,
                "sharpe": float(pnls.mean() / std) if std > 1e-12 else 0.0,
                "max_dd": dd,
                "hit_rate": float((pnls > 0).mean()) if pnls.size else 0.0,
            })
        return out

    def aggregate(
        self,
        group_by: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> dict:
        """Phase N3: aggregate PnL/Sharpe/DD/hit-rate, optionally grouped.

        ``group_by`` may be ``"asset"`` or ``"run_id"`` (None = grand total
        only). Algorithm-grouped aggregation is layered on top by the
        cockpit (which has access to the manifest); the SQL layer doesn't
        know the manifest.

        Returns ``{"total": {...}, "groups": [{"key": ..., **stats}, ...]}``.
        """
        clauses, args = [], []
        if since is not None:
            clauses.append("created_at >= ?"); args.append(float(since))
        if until is not None:
            clauses.append("created_at <= ?"); args.append(float(until))
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        def _stats(pnls: list[float]) -> dict:
            arr = np.asarray(pnls, dtype=float)
            n = int(arr.size)
            if n == 0:
                return {"n_trades": 0, "total_return": 0.0, "sharpe": 0.0,
                        "max_dd": 0.0, "hit_rate": 0.0}
            equity = np.cumprod(1.0 + arr)
            peak = np.maximum.accumulate(equity)
            dd = float(((equity - peak) / peak).min())
            std = float(arr.std(ddof=1)) if n > 1 else 0.0
            sr = float(arr.mean() / std) if std > 1e-12 else 0.0
            return {
                "n_trades": n,
                "total_return": float(equity[-1] - 1.0),
                "sharpe": sr,
                "max_dd": dd,
                "hit_rate": float((arr > 0).mean()),
            }

        with self._lock, self._connect() as conn:
            cur = conn.execute(
                f"SELECT pnl, asset, run_id, created_at FROM trades "
                f"{where} ORDER BY trade_id ASC",
                args,
            )
            rows = cur.fetchall()
        all_pnls = [float(r["pnl"]) for r in rows]
        total = _stats(all_pnls)
        groups: list[dict] = []
        if group_by in ("asset", "run_id"):
            buckets: dict[str, list[float]] = {}
            for r in rows:
                buckets.setdefault(str(r[group_by]), []).append(float(r["pnl"]))
            for k, pnls in sorted(buckets.items()):
                g = _stats(pnls)
                g["key"] = k
                groups.append(g)
        return {"total": total, "groups": groups}


# ---------------------------------------------------------------------------
# Paper engine
# ---------------------------------------------------------------------------


class KellyCalculator:
    """Rolling fractional-Kelly sizer for the paper engine.

    f* = (hit * W/L_ratio - (1 - hit)) / W/L_ratio   — the classical
    Kelly criterion for fixed-odds bets. Capped at ``cap * f*`` to
    dampen realised variance (quarter-Kelly = cap=0.25 is the standard
    practitioner default).

    Set ``cap=0`` to disable sizing entirely (fraction always = ``floor``).
    With default cap=0 and floor=1.0, this is a no-op — preserving the
    backtest parity contract in ``test_cockpit.py``.

    ``cold_start_floor`` is returned instead of ``floor`` while the rolling
    window has fewer than ``min_window`` trades. Defaults to the same value
    as ``floor`` so existing tests are unaffected. Set to a smaller value
    (e.g. 0.05) to be conservative during the early-trade warm-up period.
    """

    def __init__(self, window: int = 100, cap: float = 0.0, floor: float = 1.0,
                 cold_start_floor: Optional[float] = None):
        self._rets: list[float] = []
        self.window = int(window)
        self.cap = float(cap)
        self.floor = float(floor)
        # During cold start (< min_window trades), return cold_start_floor
        # instead of floor. Defaults to floor for backward compat.
        self.cold_start_floor = float(cold_start_floor if cold_start_floor is not None else floor)
        self._min_window = 20

    def update(self, ret: float) -> None:
        self._rets.append(float(ret))
        if len(self._rets) > self.window:
            self._rets.pop(0)

    def fraction(self) -> float:
        # Cap=0 short-circuits: always return floor (sizing off).
        if self.cap <= 0.0:
            return self.floor
        # Cold start: use conservative floor until min_window trades filled.
        if len(self._rets) < self._min_window:
            return self.cold_start_floor
        arr = np.asarray(self._rets, dtype=float)
        wins = arr[arr > 0]
        losses = arr[arr <= 0]
        if len(wins) == 0 or len(losses) == 0:
            return self.cold_start_floor
        hit = len(wins) / len(arr)
        wl = float(wins.mean()) / max(abs(float(losses.mean())), 1e-12)
        f = (hit * wl - (1.0 - hit)) / wl
        return float(np.clip(f * self.cap, self.floor, 1.0))


class PaperEngine:
    """Stateful bar-by-bar wrapper around a frozen PPO/A2C/RecurrentPPO policy.

    ``step(i)`` advances the cursor to bar ``i`` and returns a :class:`Signal`.
    The caller is responsible for incrementing ``i`` exactly once per bar —
    ``ReplayFeed`` and the live loop both do this.

    For backtest parity, ``step`` reproduces ``rollout_policy``'s control
    flow: emit BUY/SELL only while flat, run meta-label gating if supplied,
    then check the triple-barrier. When a barrier fires, the trade is
    persisted to ``TradeStore`` and ``Signal.fired`` is True.

    Extra safety knobs (Phase J):
    * ``daily_loss_limit``: block new entries if session equity drops below
      ``1 - daily_loss_limit`` from ``_session_start_equity``. 0 = disabled.
    * ``regime_size_multipliers``: dict mapping HMM state index → Kelly
      fraction multiplier. E.g. ``{0: 0.5, 1: 1.0}`` sizes down in the
      low-Sharpe trend regime. Empty dict = no regime conditioning.

    Live-tier safety knobs (Phase L):
    * ``regime_confirm_bars``: require the regime to be stable for N
      consecutive bars before its multiplier is applied; before then,
      keep the previous regime's multiplier. Reduces whipsaw sizing on
      single-bar regime flickers. 0 = disabled (default).
    * ``trade_rate_max_per_day``: throttle new entries when the rolling
      24-hour trade count exceeds this. 0 = disabled (default).
    * ``adv_notional``: estimated average daily volume in $ notional for
      this asset. Combined with ``impact_coeff``, applies a square-root
      market-impact deduction so larger size pays more slippage.
      0 = disabled (default).
    * ``impact_coeff``: coefficient on the sqrt-impact model
      ``slippage = coeff * sqrt(notional / adv_notional)`` (in fraction).
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
        kelly_cap: float = 0.0,
        kelly_floor: float = 1.0,
        kelly_window: int = 100,
        kelly_cold_start_floor: Optional[float] = None,
        daily_loss_limit: float = 0.0,
        regime_size_multipliers: Optional[dict] = None,
        regime_confirm_bars: int = 0,
        trade_rate_max_per_day: int = 0,
        adv_notional: float = 0.0,
        impact_coeff: float = 0.0,
    ) -> None:
        self.asset = asset
        self.run_id = run_id
        self.model = model
        self.env_cfg = env_cfg
        self.cost = cost_model or CostModel(spread_bps=env_cfg.spread_bps)
        self.meta_model = meta_model
        self.meta_threshold = float(meta_threshold)
        self.store = store
        # Kelly sizer. Default cap=0 → always returns floor=1.0 (no scaling),
        # preserving byte-for-byte parity with the backtester. Enable by
        # passing kelly_cap>0 (e.g. 0.25 for quarter-Kelly).
        self._kelly = KellyCalculator(
            window=kelly_window, cap=kelly_cap, floor=kelly_floor,
            cold_start_floor=kelly_cold_start_floor,
        )
        # Daily loss limit: block entries if equity drops below threshold.
        # 0 = disabled (preserves parity with backtester).
        self.daily_loss_limit = float(daily_loss_limit)
        self._session_start_equity: float = 1.0
        # Regime-conditioned sizing: dict[regime_idx (int) → multiplier (float)].
        # Empty dict → no conditioning. Applied on top of Kelly fraction.
        self._regime_multipliers: dict[int, float] = (
            {int(k): float(v) for k, v in regime_size_multipliers.items()}
            if regime_size_multipliers else {}
        )
        # Phase L: run-length confirmation on regime switches. The
        # multiplier reflects the *confirmed* regime (the last regime
        # that was stable for >= ``regime_confirm_bars`` bars).
        self.regime_confirm_bars = int(regime_confirm_bars)
        self._confirmed_regime: Optional[int] = None
        self._candidate_regime: Optional[int] = None
        self._candidate_run: int = 0
        # Phase L: trade-rate governor. Counts entries (not bars) in the
        # last 24h; blocks new entries when the count exceeds the cap.
        self.trade_rate_max_per_day = int(trade_rate_max_per_day)
        self._entry_timestamps: deque[pd.Timestamp] = deque(maxlen=1024)
        # Phase L: capacity/impact model. Square-root impact on top of
        # the spread/slippage already deducted by CostModel.
        self.adv_notional = float(adv_notional)
        self.impact_coeff = float(impact_coeff)

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
        ret_unscaled = raw - base_spread - extra
        # Kelly scaling: with default cap=0, fraction()=floor=1.0 and
        # this is a no-op (byte-parity with backtester). When enabled
        # via kelly_cap>0, the recorded PnL is the Kelly-scaled return
        # while the Kelly state is updated with the UNSCALED return so
        # the hit-rate / W-L ratio estimates remain unbiased.
        kelly_f = self._kelly.fraction()
        # Regime-conditioned sizing: scale Kelly fraction by per-regime
        # multiplier (e.g. 0.5 in low-Sharpe trend regime). No-op when
        # _regime_multipliers is empty (default).
        regime_idx_entry = None
        if self._regime is not None:
            regime_idx_entry = int(np.argmax(self._regime[self._entry_i]))
        if self._regime_multipliers:
            # Phase L: prefer the *confirmed* regime over the raw bar regime
            # so single-bar flickers don't flap the multiplier.
            applied_regime = (
                self._confirmed_regime
                if self.regime_confirm_bars > 0 and self._confirmed_regime is not None
                else regime_idx_entry
            )
            if applied_regime is not None:
                kelly_f *= self._regime_multipliers.get(applied_regime, 1.0)
        # Phase L: square-root market-impact deduction. slippage as a fraction
        # of price = impact_coeff * sqrt(notional / adv). Notional is approx.
        # Kelly-scaled exposure × entry price; we use the unscaled return's
        # absolute Kelly fraction for the notional estimate.
        if self.adv_notional > 0.0 and self.impact_coeff > 0.0:
            notional = abs(kelly_f) * self._entry_price
            impact = self.impact_coeff * math.sqrt(notional / self.adv_notional)
            ret_unscaled -= impact
        ret = ret_unscaled * kelly_f
        self._kelly.update(ret_unscaled)
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

        # Phase L: update regime run-length tracker so _fire_trade can use
        # the confirmed regime (a multi-bar majority) instead of this bar's
        # raw regime.
        if self._regime is not None and self.regime_confirm_bars > 0:
            cur = int(np.argmax(self._regime[i]))
            if cur == self._candidate_regime:
                self._candidate_run += 1
            else:
                self._candidate_regime = cur
                self._candidate_run = 1
            if self._candidate_run >= self.regime_confirm_bars:
                self._confirmed_regime = cur

        if self._pos == 0:
            obs = self._obs(i)
            raw, _ = self.model.predict(obs, deterministic=True)
            a = int(raw)
            # Daily loss gate: block new entries when session equity has
            # dropped more than daily_loss_limit from the session start.
            # 0.0 disables the gate (default, preserving backtest parity).
            if a != HOLD and self.daily_loss_limit > 0.0:
                current_equity = float(np.prod(1.0 + np.asarray(self._trades))) if self._trades else 1.0
                if current_equity / self._session_start_equity - 1.0 < -self.daily_loss_limit:
                    a = HOLD
                    log.warning(
                        "daily loss gate triggered: equity %.4f / session_start %.4f "
                        "(limit %.2f%%); blocking new entry at bar %d",
                        current_equity, self._session_start_equity,
                        self.daily_loss_limit * 100, i,
                    )
            # Phase L: trade-rate governor. Block new entries when the
            # rolling 24-hour entry count exceeds the cap. 0 = disabled.
            if a != HOLD and self.trade_rate_max_per_day > 0:
                ts_now = self._ts(i) or pd.Timestamp.now(tz="UTC")
                cutoff = ts_now - pd.Timedelta(hours=24)
                # Drop expired entries from the deque (cheap when capped at 1024).
                while self._entry_timestamps and self._entry_timestamps[0] < cutoff:
                    self._entry_timestamps.popleft()
                if len(self._entry_timestamps) >= self.trade_rate_max_per_day:
                    a = HOLD
                    log.warning(
                        "trade-rate governor triggered: %d entries in last 24h "
                        "(limit %d); blocking new entry at bar %d",
                        len(self._entry_timestamps), self.trade_rate_max_per_day, i,
                    )
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
                    # Phase L: record entry timestamp for the trade-rate governor.
                    if self.trade_rate_max_per_day > 0:
                        ts_entry = self._ts(i) or pd.Timestamp.now(tz="UTC")
                        self._entry_timestamps.append(ts_entry)
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
    # live bar ingestion (Phase J — streaming encoder path)
    # ------------------------------------------------------------------

    def extend_precomputed(self, bar_data: dict) -> int:
        """Append one new bar's data and return the new bar index.

        ``bar_data`` must have keys: ``close``, ``atr``, ``embedding``,
        ``vol_quantile``, and optionally ``ts``.

        After calling this, ``step(new_idx)`` will observe the new bar
        through the same code path as replay mode — no other changes needed.
        """
        new_close = float(bar_data["close"])
        new_atr = float(bar_data["atr"])
        new_emb = np.asarray(bar_data["embedding"], dtype=np.float32)
        new_vq = float(bar_data["vol_quantile"])

        self._close = np.append(self._close, new_close)
        self._atr = np.append(self._atr, new_atr)
        self._emb = np.vstack([self._emb, new_emb[np.newaxis]])
        self._vol_q = np.append(self._vol_q, new_vq)

        if self._timestamps is not None:
            ts = bar_data.get("ts")
            if ts is None:
                ts = pd.Timestamp.now(tz="UTC")
            self._timestamps = self._timestamps.append(pd.DatetimeIndex([ts]))

        # If regime posterior exists, extend with the last known state
        # (HMM must be re-run externally to update; this is a placeholder).
        if self._regime is not None:
            self._regime = np.vstack([self._regime, self._regime[-1:]])

        return int(len(self._close) - 1)

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

    def open_position_state(self) -> Optional[dict]:
        """Phase N1: snapshot of the currently-open position, or None.

        Includes unrealised PnL (mark-to-market against the latest close),
        regime index, bars-in-trade and the active barrier prices so the
        UI active-trades panel can render without extra round-trips.
        """
        if self._pos == 0 or self._entry_i < 0:
            return None
        last_idx = len(self._close) - 1
        last_price = float(self._close[last_idx]) if last_idx >= 0 else self._entry_price
        unrealised = self._pos * (last_price / self._entry_price - 1.0)
        regime_idx = None
        if self._regime is not None and 0 <= self._entry_i < len(self._regime):
            regime_idx = int(np.argmax(self._regime[self._entry_i]))
        return {
            "asset": self.asset,
            "run_id": self.run_id,
            "direction": int(self._pos),
            "entry_idx": int(self._entry_i),
            "entry_ts": str(self._ts(self._entry_i)) if self._ts(self._entry_i) is not None else None,
            "entry_price": float(self._entry_price),
            "last_price": last_price,
            "unrealised_pnl": float(unrealised),
            "barrier_upper": float(self._barrier_upper),
            "barrier_lower": float(self._barrier_lower),
            "bars_in_trade": int(last_idx - self._entry_i),
            "regime_idx": regime_idx,
        }
