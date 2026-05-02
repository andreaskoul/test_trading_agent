"""Kill-switch rules for the autonomous live loop.

Pure functions of the trade log, so they can be unit-tested independently
of any paper engine or websocket. The cockpit + auto loop poll
``evaluate(trades)`` after each fill; if the returned ``triggered`` list
is non-empty, the caller stops opening new positions (existing ones are
still allowed to exit through the triple barrier).

Four rules, matching the original research-synthesis kill-switches:

* ``sharpe_floor``: rolling Sharpe over the last N trades below threshold
  for at least ``sharpe_duration_bars`` consecutive bars.
* ``max_drawdown``: cumulative-return drawdown below ``max_drawdown``.
* ``win_rate_floor``: win rate over the last ``win_rate_window`` trades
  below break-even (default 0.5).
* ``catastrophe``: any single trade loss beyond ``catastrophe_pct``.

Thresholds live in configs/default.yaml under ``kill_switch:`` so the
cockpit can surface them on the performance panel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np


@dataclass
class KillSwitchConfig:
    enabled: bool = True
    sharpe_floor: float = 1.0
    sharpe_window: int = 60           # trades
    sharpe_duration_bars: int = 3     # #consecutive windows below floor
    max_drawdown: float = 0.05        # 5%
    win_rate_floor: float = 0.5
    win_rate_window: int = 100
    catastrophe_pct: float = 0.05     # any single trade worse than -5%
    # Phase M: deflated-Sharpe gate. Fires when DSR < dsr_floor with at
    # least dsr_min_trades samples — i.e. rolling Sharpe is "fine" but
    # the result is unlikely to be statistically real. 0.0 = disabled.
    dsr_floor: float = 0.0
    dsr_min_trades: int = 50
    dsr_n_trials: int = 36            # matches the 36-run training corpus


@dataclass
class KillSwitchResult:
    triggered: list[str] = field(default_factory=list)
    reasons: dict[str, str] = field(default_factory=dict)

    @property
    def halt(self) -> bool:
        return len(self.triggered) > 0


def _rolling_sharpe(returns: np.ndarray, window: int) -> float:
    """Annualization-free Sharpe on a window slice. Zero std returns 0."""
    if returns.size < window:
        sl = returns
    else:
        sl = returns[-window:]
    if sl.size == 0:
        return 0.0
    std = float(sl.std(ddof=0))
    if std <= 1e-12:
        return 0.0
    return float(sl.mean() / std)


def _max_drawdown(returns: np.ndarray) -> float:
    """Max peak-to-trough drawdown on cumulative compounded equity."""
    if returns.size == 0:
        return 0.0
    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return float(dd.min())


def evaluate(
    returns: Sequence[float],
    cfg: KillSwitchConfig,
    *,
    recent_sharpe_history: Sequence[float] | None = None,
) -> KillSwitchResult:
    """Apply each rule and return the set that fired.

    ``recent_sharpe_history`` optionally lets the caller supply previously
    computed rolling-Sharpes so the duration rule can track consecutive
    breaches across calls. Pass ``None`` for single-shot evaluation.
    """
    result = KillSwitchResult()
    if not cfg.enabled:
        return result
    arr = np.asarray(list(returns), dtype=np.float64)
    if arr.size == 0:
        return result

    # Rule 1: rolling Sharpe floor
    rs = _rolling_sharpe(arr, cfg.sharpe_window)
    if rs < cfg.sharpe_floor:
        history = list(recent_sharpe_history or [])
        consec = 1
        for v in reversed(history):
            if v < cfg.sharpe_floor:
                consec += 1
            else:
                break
        if consec >= cfg.sharpe_duration_bars:
            result.triggered.append("sharpe_floor")
            result.reasons["sharpe_floor"] = (
                f"rolling Sharpe={rs:.2f} < {cfg.sharpe_floor:.2f} "
                f"for {consec} consecutive windows"
            )

    # Rule 2: max drawdown
    mdd = _max_drawdown(arr)
    if mdd < -abs(cfg.max_drawdown):
        result.triggered.append("max_drawdown")
        result.reasons["max_drawdown"] = (
            f"equity drawdown {mdd*100:.1f}% exceeds {cfg.max_drawdown*100:.1f}%"
        )

    # Rule 3: win-rate floor
    wr_window = arr[-cfg.win_rate_window:] if arr.size >= cfg.win_rate_window else arr
    if wr_window.size >= min(20, cfg.win_rate_window):
        win_rate = float((wr_window > 0).mean())
        if win_rate < cfg.win_rate_floor:
            result.triggered.append("win_rate_floor")
            result.reasons["win_rate_floor"] = (
                f"win rate {win_rate:.2f} over last {wr_window.size} trades "
                f"< {cfg.win_rate_floor:.2f}"
            )

    # Rule 4: catastrophe (single trade)
    worst = float(arr.min())
    if worst < -abs(cfg.catastrophe_pct):
        result.triggered.append("catastrophe")
        result.reasons["catastrophe"] = (
            f"single-trade loss {worst*100:.1f}% exceeds {cfg.catastrophe_pct*100:.1f}%"
        )

    # Rule 5 (Phase M): deflated-Sharpe floor. Catches the case where
    # rolling Sharpe is OK but the result is unlikely to be statistically
    # real (low DSR ⇒ overfit to noise). Disabled when dsr_floor == 0.
    if cfg.dsr_floor > 0.0 and arr.size >= cfg.dsr_min_trades:
        # Lazy import: keeps kill_switch importable without scipy.
        from ..validation.deflated_sr import deflated_sharpe_ratio
        dsr_val = float(
            deflated_sharpe_ratio(arr, n_trials=cfg.dsr_n_trials).deflated_sharpe
        )
        if dsr_val < cfg.dsr_floor:
            result.triggered.append("dsr_floor")
            result.reasons["dsr_floor"] = (
                f"deflated Sharpe {dsr_val:.3f} < {cfg.dsr_floor:.3f} "
                f"on {arr.size} trades (n_trials={cfg.dsr_n_trials})"
            )

    return result


def from_cfg(cfg_dict: dict) -> KillSwitchConfig:
    """Build a KillSwitchConfig from the ``kill_switch`` block of default.yaml."""
    if not cfg_dict:
        return KillSwitchConfig()
    return KillSwitchConfig(
        enabled=bool(cfg_dict.get("enabled", True)),
        sharpe_floor=float(cfg_dict.get("sharpe_floor", 1.0)),
        sharpe_window=int(cfg_dict.get("sharpe_window", 60)),
        sharpe_duration_bars=int(cfg_dict.get("sharpe_duration_bars", 3)),
        max_drawdown=float(cfg_dict.get("max_drawdown", 0.05)),
        win_rate_floor=float(cfg_dict.get("win_rate_floor", 0.5)),
        win_rate_window=int(cfg_dict.get("win_rate_window", 100)),
        catastrophe_pct=float(cfg_dict.get("catastrophe_pct", 0.05)),
        dsr_floor=float(cfg_dict.get("dsr_floor", 0.0)),
        dsr_min_trades=int(cfg_dict.get("dsr_min_trades", 50)),
        dsr_n_trials=int(cfg_dict.get("dsr_n_trials", 36)),
    )
