"""Common backtest performance metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass
class PerformanceMetrics:
    n_trades: int
    total_return: float
    cagr: float
    sharpe: float
    sortino: float
    max_drawdown: float
    hit_rate: float
    expectancy: float
    avg_win: float
    avg_loss: float
    equity_final: float

    def asdict(self) -> dict:
        return asdict(self)


def _sharpe(rets: np.ndarray, periods: float) -> float:
    rets = rets[np.isfinite(rets)]
    if len(rets) < 2 or rets.std(ddof=1) == 0:
        return 0.0
    return float(rets.mean() / rets.std(ddof=1) * np.sqrt(periods))


def _sortino(rets: np.ndarray, periods: float) -> float:
    rets = rets[np.isfinite(rets)]
    if len(rets) < 2:
        return 0.0
    downside = rets[rets < 0]
    if len(downside) == 0 or downside.std(ddof=1) == 0:
        return 0.0
    return float(rets.mean() / downside.std(ddof=1) * np.sqrt(periods))


def _max_drawdown(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / np.where(peak == 0, 1, peak)
    return float(dd.min())


def compute_metrics(
    trade_returns: np.ndarray,
    periods_per_year: float = 252.0,
    bars_per_trade: float = 5.0,
) -> PerformanceMetrics:
    trade_returns = np.asarray(trade_returns, dtype=float)
    trade_returns = trade_returns[np.isfinite(trade_returns)]
    n = len(trade_returns)
    if n == 0:
        return PerformanceMetrics(
            n_trades=0,
            total_return=0.0,
            cagr=0.0,
            sharpe=0.0,
            sortino=0.0,
            max_drawdown=0.0,
            hit_rate=0.0,
            expectancy=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            equity_final=1.0,
        )
    equity = np.cumprod(1 + trade_returns)
    total_return = float(equity[-1] - 1)
    trades_per_year = periods_per_year / max(bars_per_trade, 1.0)
    sr = _sharpe(trade_returns, trades_per_year)
    so = _sortino(trade_returns, trades_per_year)
    dd = _max_drawdown(equity)
    wins = trade_returns[trade_returns > 0]
    losses = trade_returns[trade_returns <= 0]
    hit_rate = float(len(wins) / n)
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    expectancy = float(trade_returns.mean())
    years = max(n / trades_per_year, 1e-6)
    cagr = float((equity[-1]) ** (1 / years) - 1)
    return PerformanceMetrics(
        n_trades=n,
        total_return=total_return,
        cagr=cagr,
        sharpe=sr,
        sortino=so,
        max_drawdown=dd,
        hit_rate=hit_rate,
        expectancy=expectancy,
        avg_win=avg_win,
        avg_loss=avg_loss,
        equity_final=float(equity[-1]),
    )
