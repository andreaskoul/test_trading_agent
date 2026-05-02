"""Autonomous pipeline orchestrator.

Runs the existing numbered scripts on a schedule so the system keeps
learning from new data without manual intervention:

  build_data  (01)   : only when new bars are available
  pretrain    (02)   : full retrain every `retrain_every_days`
  train_ppo   (03)   : same cadence
  evaluate    (04)   : every `evaluate_every_days` (reports stay fresh)
  finetune    (05)   : every `finetune_every_days` (small-lr refresh)

Usage:
    python scripts/99_auto.py                    # loop forever
    python scripts/99_auto.py --once             # run one iteration
    python scripts/99_auto.py --tick-seconds 60  # override poll interval

State lives in ``artefacts/auto_state.json`` so restarts pick up where
the last iteration left off.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone

from _bootstrap import path, setup


log = logging.getLogger("auto")


@dataclass
class AutoState:
    last_build: str = ""
    last_pretrain: str = ""
    last_train_ppo: str = ""
    last_evaluate: str = ""
    last_finetune: str = ""
    last_bar_count: int = 0
    halt: bool = False
    halt_reason: str = ""


def _load_state(state_path: str) -> AutoState:
    if not os.path.exists(state_path):
        return AutoState()
    with open(state_path) as f:
        raw = json.load(f)
    return AutoState(**raw)


def _save_state(state: AutoState, state_path: str) -> None:
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w") as f:
        json.dump(asdict(state), f, indent=2)


def _age_days(iso: str) -> float:
    if not iso:
        return float("inf")
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return float("inf")
    return (datetime.now(timezone.utc) - t).total_seconds() / 86400.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run(cmd: list[str], cwd: str) -> bool:
    log.info("$ %s", " ".join(cmd))
    try:
        # Propagate the parent environment so TRADING_PROFILE (and any other
        # caller-set vars) reach the sub-script. Without this the auto loop
        # silently runs the default profile even when launched as
        # `TRADING_PROFILE=aggressive python scripts/99_auto.py`.
        result = subprocess.run(cmd, cwd=cwd, env=os.environ.copy(), check=False)
        return result.returncode == 0
    except FileNotFoundError as e:
        log.error("command not found: %s", e)
        return False


def _count_bars(cfg: dict) -> int:
    """Sum bar counts across all configured assets. Skips missing files."""
    import pandas as pd

    total = 0
    for a in cfg.get("data", {}).get("assets", []):
        p = path(cfg, a["features_path"])
        if not os.path.exists(p):
            continue
        try:
            total += len(pd.read_parquet(p, columns=["close"]))
        except Exception:  # pragma: no cover
            pass
    return total


def _check_kill_switch(cfg: dict) -> tuple[bool, str]:
    """Load the paper-trade SQLite and check kill-switch rules. Safe to skip."""
    db_path = cfg.get("ui", {}).get("db_path", "artefacts/paper_trades.db")
    full = path(cfg, db_path) if not os.path.isabs(db_path) else db_path
    if not os.path.exists(full):
        return False, ""
    import sqlite3
    from src.live.kill_switch import evaluate, from_cfg

    try:
        with sqlite3.connect(full) as con:
            rows = con.execute("SELECT pnl FROM trades ORDER BY trade_id").fetchall()
    except sqlite3.Error as e:
        log.warning("kill-switch query failed: %s", e)
        return False, ""
    returns = [float(r[0]) for r in rows if r[0] is not None]
    if not returns:
        return False, ""
    ks_cfg = from_cfg(cfg.get("kill_switch", {}))
    res = evaluate(returns, ks_cfg)
    if res.halt:
        reason = "; ".join(f"{k}: {v}" for k, v in res.reasons.items())
        return True, reason
    return False, ""


def _iteration(cfg: dict, state: AutoState, *, dry_run: bool) -> AutoState:
    repo = cfg["__repo_root__"]
    auto_cfg = cfg.get("auto", {})
    ev_days = float(auto_cfg.get("evaluate_every_days", 1))
    ft_days = float(auto_cfg.get("finetune_every_days", 7))
    retrain_days = float(auto_cfg.get("retrain_every_days", 30))
    min_new_bars = int(auto_cfg.get("min_new_bars_before_retrain", 500))

    # 0) Kill-switch
    halted, reason = _check_kill_switch(cfg)
    if halted and not state.halt:
        log.warning("kill-switch triggered: %s", reason)
        state.halt = True
        state.halt_reason = reason
        return state
    if state.halt:
        log.info("halted (%s); skipping iteration. manually clear halt to resume.", state.halt_reason)
        return state

    # 1) Build data (cheap, always try)
    if not dry_run:
        ok = _run([sys.executable, "scripts/01_build_data.py"], cwd=repo)
        if ok:
            state.last_build = _now_iso()
    new_bar_count = _count_bars(cfg)
    bar_delta = new_bar_count - state.last_bar_count
    state.last_bar_count = new_bar_count
    log.info("bars total=%d (delta=%d since last iter)", new_bar_count, bar_delta)

    # 2) Full retrain path (pretrain + PPO)
    # Phase K: max_policy_age_days is a HARD upper bound. Once exceeded,
    # we override the min_new_bars gate and force a retrain so live
    # trading never runs on a stale policy.
    max_policy_age = float(auto_cfg.get("max_policy_age_days", 0.0))
    forced_by_age = (
        max_policy_age > 0.0
        and state.last_train_ppo != ""
        and _age_days(state.last_train_ppo) >= max_policy_age
    )
    retrain_due = (
        _age_days(state.last_train_ppo) >= retrain_days
        or state.last_train_ppo == ""
    )
    if forced_by_age:
        log.warning("policy age exceeds max_policy_age_days=%.1f (age=%.1fd); forcing retrain",
                    max_policy_age, _age_days(state.last_train_ppo))
    if retrain_due and (bar_delta >= min_new_bars or forced_by_age):
        log.info("full retrain due (age=%.1fd, new_bars=%d)",
                 _age_days(state.last_train_ppo), bar_delta)
        if not dry_run:
            if _run([sys.executable, "scripts/02_pretrain_encoder.py", "--fast"], cwd=repo):
                state.last_pretrain = _now_iso()
            if _run([sys.executable, "scripts/03_train_ppo.py", "--fast"], cwd=repo):
                state.last_train_ppo = _now_iso()
    elif retrain_due:
        log.info("retrain due but only %d new bars (<%d); skipping", bar_delta, min_new_bars)

    # 3) Evaluate
    if _age_days(state.last_evaluate) >= ev_days:
        if not dry_run and _run([sys.executable, "scripts/04_evaluate.py"], cwd=repo):
            state.last_evaluate = _now_iso()

    # 4) Finetune
    if _age_days(state.last_finetune) >= ft_days:
        if not dry_run and _run([sys.executable, "scripts/05_finetune.py"], cwd=repo):
            state.last_finetune = _now_iso()

    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="run one iteration and exit")
    parser.add_argument("--tick-seconds", type=float, default=3600.0,
                        help="seconds between iterations (default 1h)")
    parser.add_argument("--dry-run", action="store_true",
                        help="log decisions but don't invoke the sub-scripts")
    parser.add_argument("--clear-halt", action="store_true",
                        help="clear a prior kill-switch halt and resume")
    args = parser.parse_args()

    cfg = setup()
    state_path = path(cfg, cfg["artefact_dir"], "auto_state.json")
    state = _load_state(state_path)

    if args.clear_halt:
        if state.halt:
            log.info("clearing halt (was: %s)", state.halt_reason)
        state.halt = False
        state.halt_reason = ""
        _save_state(state, state_path)

    while True:
        try:
            state = _iteration(cfg, state, dry_run=args.dry_run)
            _save_state(state, state_path)
        except KeyboardInterrupt:
            log.info("interrupted; state saved, exiting")
            _save_state(state, state_path)
            return
        except Exception:  # pragma: no cover
            log.exception("iteration crashed; sleeping and retrying")
        if args.once:
            return
        log.info("sleeping %.0fs", args.tick_seconds)
        time.sleep(args.tick_seconds)


if __name__ == "__main__":
    main()
