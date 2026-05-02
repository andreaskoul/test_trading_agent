"""Export the cockpit's persistent state to a static JSON snapshot for
GitHub Pages (Phase Q).

Each cron invocation writes ``docs/data.json`` containing everything the
static dashboard needs:

  * latest engine state (open position, equity, n_trades, last_ts)
  * recent closed trades (last 500)
  * per-algorithm aggregate PnL (re-bucketed via the manifest)
  * rolling Sharpe / DSR / bootstrap p-value via LiveStats
  * kill-switch halt marker (if any)

The dashboard is fully static (no Python runtime); fetches data.json on
load and re-fetches every 60 s. Updated each hour by the cron workflow.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

import numpy as np

from _bootstrap import setup, path

from src.live.paper_engine import TradeStore
from src.validation.live_stats import LiveStats

log = logging.getLogger("export_dashboard_data")


def _bucket_by_algorithm(rows: list[dict], manifest: list[dict]) -> dict:
    pnls: dict[str, list[float]] = {}
    for r in rows:
        rid = str(r.get("run_id", ""))
        algo = "unknown"
        try:
            mtag = next(p for p in rid.split("-") if p.startswith("m"))
            midx = int(mtag[1:])
            algo = str(manifest[midx].get("algorithm", "unknown")).lower()
        except (StopIteration, ValueError, IndexError):
            pass
        pnls.setdefault(algo, []).append(float(r["pnl"]))
    out = []
    for algo, pl in sorted(pnls.items()):
        arr = np.asarray(pl, dtype=float)
        equity = np.cumprod(1.0 + arr) if arr.size else np.array([1.0])
        peak = np.maximum.accumulate(equity)
        dd = float(((equity - peak) / peak).min()) if arr.size else 0.0
        std = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
        out.append({
            "key": algo,
            "n_trades": int(arr.size),
            "total_return": float(equity[-1] - 1.0) if arr.size else 0.0,
            "sharpe": float(arr.mean() / std) if std > 1e-12 else 0.0,
            "max_dd": dd,
            "hit_rate": float((arr > 0).mean()) if arr.size else 0.0,
        })
    return {"groups": out}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/data.json")
    args = parser.parse_args()

    cfg = setup()
    db_path = path(cfg, cfg.get("trade_db_path", "artefacts/paper_trades.db"))
    if not os.path.exists(db_path):
        log.warning("trade DB missing: %s", db_path)
        snapshot = {"trades": [], "aggregate": {"groups": [], "total": {}},
                    "stats": {}, "engine": None, "halt": None}
    else:
        store = TradeStore(db_path)
        rows = store.list_trades(limit=2000)
        agg = store.aggregate(group_by="asset")

        # Per-algorithm bucket via manifest.
        manifest_path = path(cfg, cfg["artefact_dir"], "ppo_manifest.json")
        manifest = []
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                manifest = json.load(f)
        algo_agg = _bucket_by_algorithm(rows, manifest)

        # Live-stats snapshot from accumulated returns.
        rets = np.array([float(r["pnl"]) for r in reversed(rows)],
                        dtype=float)         # chronological for stats
        ann = float(cfg.get("ui", {}).get("paper", {}).get("ann_factor", 252.0))
        ls = LiveStats(annualisation_factor=ann,
                       bootstrap_resamples=int(cfg.get("ui", {}).get("paper", {})
                                                  .get("stats_bootstrap_resamples", 500)),
                       bootstrap_block=int(cfg.get("evaluation", {})
                                              .get("permutation_block_size", 20)))
        stats = ls.compute(rets).to_dict()

        # Engine snapshot (open position) — written by step_one_bar.py.
        engine_state_path = path(cfg, "artefacts", "engine_state.json")
        engine = None
        if os.path.exists(engine_state_path):
            with open(engine_state_path) as f:
                engine = json.load(f)

        # Halt marker.
        halt_path = path(cfg, "artefacts", "kill_switch_halt.json")
        halt = None
        if os.path.exists(halt_path):
            with open(halt_path) as f:
                halt = json.load(f)

        # Equity curve from chronological pnls (last 1000 points).
        equity_curve = []
        if rets.size:
            eq = np.cumprod(1.0 + rets[-1000:])
            equity_curve = [float(x) for x in eq]

        snapshot = {
            "generated_at": cfg.get("__now__", ""),
            "trades": [
                {k: v for k, v in r.items()
                 if k not in ("entry_features_json", "embedding_json", "explanation")}
                for r in rows[:500]
            ],
            "aggregate": {"by_asset": agg, "by_algorithm": algo_agg},
            "stats": stats,
            "engine": engine,
            "halt": halt,
            "equity_curve": equity_curve,
        }

    out_path = path(cfg, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)
    log.info("wrote %s (%d trades, %d eq points)",
             out_path, len(snapshot.get("trades", [])),
             len(snapshot.get("equity_curve", [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
