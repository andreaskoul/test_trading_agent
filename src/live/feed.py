"""Bar feeds for the cockpit.

Two implementations behind one async interface:

* :class:`ReplayFeed` yields bars from an on-disk features parquet at a
  configurable speed. Used by the Backtest Replay panel and by the
  parity test.
* :class:`YFinanceFeed` polls ``yfinance`` on a wall-clock interval so
  the cockpit can run against fresh market data. The implementation is
  deliberately conservative — one HTTP request per poll, no streaming
  dependencies — because the MVP only needs 1-minute granularity.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import AsyncIterator, Optional

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class Bar:
    ts: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float
    asset: str
    idx: Optional[int] = None  # index into the precomputed arrays (replay only)

    def to_dict(self) -> dict:
        return {
            "ts": str(self.ts),
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": float(self.volume),
            "asset": self.asset,
            "idx": None if self.idx is None else int(self.idx),
        }


class BarFeed:
    """Abstract async bar feed."""

    asset: str

    async def subscribe(self) -> AsyncIterator[Bar]:  # pragma: no cover - interface
        raise NotImplementedError
        yield  # keeps mypy happy about the return type


# ---------------------------------------------------------------------------
# Replay feed
# ---------------------------------------------------------------------------


class ReplayFeed(BarFeed):
    """Yield bars from a precomputed OHLCV DataFrame at a configurable speed.

    ``speed`` is a multiplier over real time. Speed=1 emits one bar per
    ``bar_interval_seconds`` of wall clock; speed=10 emits 10× faster;
    speed=0 or negative means as fast as possible (used by the parity test
    to compare outputs against ``rollout_policy`` without waiting).
    """

    def __init__(
        self,
        asset: str,
        ohlcv: pd.DataFrame,
        start_idx: int,
        end_idx: int,
        speed: float = 10.0,
        bar_interval_seconds: float = 60.0,
    ) -> None:
        self.asset = asset
        self._df = ohlcv
        self.start_idx = int(start_idx)
        self.end_idx = int(end_idx)
        self.speed = float(speed)
        self.bar_interval_seconds = float(bar_interval_seconds)
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    async def subscribe(self) -> AsyncIterator[Bar]:
        if self.start_idx < 0 or self.end_idx > len(self._df):
            raise IndexError(
                f"ReplayFeed window [{self.start_idx}, {self.end_idx}) out of range"
            )
        # Sleep between bars to simulate the passage of time. At speed<=0 we
        # don't sleep at all (deterministic parity testing).
        delay = 0.0
        if self.speed > 0:
            delay = self.bar_interval_seconds / self.speed

        ts_index = self._df.index
        for i in range(self.start_idx, self.end_idx):
            if self._stopped:
                break
            row = self._df.iloc[i]
            bar = Bar(
                ts=ts_index[i] if hasattr(ts_index, "__getitem__") else pd.Timestamp.now(tz="UTC"),
                open=float(row.get("open", row.get("close", np.nan))),
                high=float(row.get("high", row.get("close", np.nan))),
                low=float(row.get("low", row.get("close", np.nan))),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0)),
                asset=self.asset,
                idx=i,
            )
            yield bar
            if delay > 0:
                await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
# YFinance feed
# ---------------------------------------------------------------------------


class YFinanceFeed(BarFeed):
    """Polls yfinance for the latest bar on a wall-clock interval.

    Minimum viable implementation: every ``bar_interval_seconds`` we pull
    the last few bars and yield only bars whose timestamp is strictly
    greater than the most recently emitted one. This is good enough for
    1-minute / 5-minute cockpit sessions; high-frequency use cases would
    need a websocket broker feed instead.
    """

    def __init__(
        self,
        asset: str,
        interval: str = "1m",
        bar_interval_seconds: float = 60.0,
        lookback_bars: int = 5,
    ) -> None:
        self.asset = asset
        self.interval = interval
        self.bar_interval_seconds = float(bar_interval_seconds)
        self.lookback_bars = int(lookback_bars)
        self._stopped = False
        self._last_ts: Optional[pd.Timestamp] = None

    def stop(self) -> None:
        self._stopped = True

    async def subscribe(self) -> AsyncIterator[Bar]:
        try:
            import yfinance as yf
        except ImportError:  # pragma: no cover
            log.error("yfinance not installed; YFinanceFeed will not emit bars")
            return

        # yfinance 1m data is only available for the last 7 days, so start
        # with a short lookback.
        while not self._stopped:
            try:
                raw = await asyncio.to_thread(
                    yf.download,
                    self.asset,
                    period="1d",
                    interval=self.interval,
                    progress=False,
                    auto_adjust=False,
                    threads=False,
                )
            except Exception as exc:  # pragma: no cover - network
                log.warning("yfinance poll failed for %s: %s", self.asset, exc)
                await asyncio.sleep(self.bar_interval_seconds)
                continue

            if raw is None or len(raw) == 0:
                await asyncio.sleep(self.bar_interval_seconds)
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            raw = raw.rename(columns={c: c.lower() for c in raw.columns})

            tail = raw.iloc[-self.lookback_bars:]
            for ts, row in tail.iterrows():
                if self._last_ts is not None and ts <= self._last_ts:
                    continue
                self._last_ts = ts
                yield Bar(
                    ts=pd.Timestamp(ts),
                    open=float(row.get("open", row["close"])),
                    high=float(row.get("high", row["close"])),
                    low=float(row.get("low", row["close"])),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0.0)),
                    asset=self.asset,
                )
            await asyncio.sleep(self.bar_interval_seconds)
