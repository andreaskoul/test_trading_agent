"""Finetune the best policy per asset and evaluate on a held-out window.

Supports PPO, A2C, and RecurrentPPO (T2.2). Multi-asset: selects the best
policy independently for each asset and produces a combined finetune report.
"""

from __future__ import annotations

import json
import logging
import os

import numpy as np
import pandas as pd
from stable_baselines3 import A2C, PPO

from _bootstrap import setup, path

from src.data.config_utils import parse_asset_configs
from src.data.features import feature_columns
from src.data.regimes import HMMRegimeModel
from src.env.trading_env import env_config_from_yaml
from src.training.evaluate import build_precomputed, rollout_policy
from src.training.finetune import FinetuneConfig, finetune_policy
from src.training.pretrain_encoder import load_encoder

try:
    from sb3_contrib import RecurrentPPO
except ImportError:  # pragma: no cover
    RecurrentPPO = None  # type: ignore[assignment]

from src.training.grpo import GRPO as _GRPO

_ALGO_MAP: dict[str, type] = {"ppo": PPO, "a2c": A2C, "grpo": _GRPO}
if RecurrentPPO is not None:
    _ALGO_MAP["recurrent_ppo"] = RecurrentPPO
    _ALGO_MAP["rppo"] = RecurrentPPO


def main() -> None:
    log = logging.getLogger("finetune")
    cfg = setup()

    assets = parse_asset_configs(cfg)
    env_cfg = env_config_from_yaml(cfg)

    manifest_path = path(cfg, cfg["artefact_dir"], "ppo_manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)

    per_run = pd.read_csv(path(cfg, cfg["report_dir"], "per_run_metrics.csv"))
    per_run["score"] = per_run["sharpe"] - 0.5 * per_run["max_drawdown"].abs() * 10

    # Backward compat: add default asset column if missing
    default_asset = assets[0].symbol if assets else "unknown"
    if "asset" not in per_run.columns:
        per_run["asset"] = default_asset
    for entry in manifest:
        if "asset" not in entry:
            entry["asset"] = default_asset

    ft_cfg = FinetuneConfig(
        timesteps=cfg["finetune"]["timesteps"],
        lr=cfg["finetune"]["lr"],
        ent_coef=cfg["finetune"]["ent_coef"],
    )

    report_lines = [
        "# Finetune Report",
        "",
    ]

    for asset in assets:
        sym = asset.symbol
        sym_tag = sym.lower().replace("=", "_").replace("/", "_")
        log.info("=== finetuning best policy for %s ===", sym)

        features = pd.read_parquet(path(cfg, asset.features_path))
        feat_cols = feature_columns(features)
        n = len(features)
        holdout_n = int(cfg["finetune"]["holdout_frac"] * n)
        train_idx = np.arange(0, n - holdout_n)
        holdout_idx = np.arange(n - holdout_n, n)

        # Find best run for this asset
        asset_runs = per_run[per_run["asset"] == sym]
        if asset_runs.empty:
            log.warning("no runs found for %s, skipping finetune", sym)
            continue
        best = asset_runs.sort_values("score", ascending=False).iloc[0]
        best_algo = best.get("algorithm", "ppo") if "algorithm" in best.index else "ppo"

        candidates = [
            m for m in manifest
            if m.get("asset") == sym
            and m["split"] == int(best["split"])
            and m["seed"] == int(best["seed"])
            and m.get("algorithm", "ppo") == best_algo
        ]
        if not candidates:
            candidates = [
                m for m in manifest
                if m.get("asset") == sym
                and m["split"] == int(best["split"])
                and m["seed"] == int(best["seed"])
            ]
        if not candidates:
            log.warning("no matching manifest entry for %s, skipping", sym)
            continue
        best_entry = candidates[0]
        best_algo = best_entry.get("algorithm", "ppo")
        log.info(
            "[%s] best run: algo=%s split=%d seed=%d sharpe=%.2f dd=%.2f",
            sym, best_algo, int(best["split"]), int(best["seed"]),
            best["sharpe"], best["max_drawdown"],
        )

        encoder_group = best_entry["encoder_group"]
        encoder_path = path(cfg, cfg["artefact_dir"], "encoders", f"encoder_group{encoder_group}.pt")
        encoder = load_encoder(encoder_path)

        # Re-attach HMM regime posterior
        regime_post = None
        rp_path = best_entry.get("regime_path")
        if rp_path and os.path.exists(rp_path):
            hmm = HMMRegimeModel.load(rp_path)
            close = features["close"].to_numpy(dtype=np.float64)
            regime_post = hmm.posterior(close)

        precomputed = build_precomputed(
            features, feat_cols, encoder,
            seq_len=env_cfg.seq_len,
            regime_posterior=regime_post,
        )

        out_path = path(cfg, cfg["artefact_dir"], "policies", f"{sym_tag}_{best_algo}_finetuned.zip")
        finetune_policy(
            precomputed=precomputed,
            env_cfg=env_cfg,
            train_idx=train_idx,
            base_policy_path=best_entry["policy_path"],
            cfg=ft_cfg,
            save_path=out_path,
            seed=int(best["seed"]),
            algorithm=best_algo,
        )

        algo_cls = _ALGO_MAP.get(best_algo, PPO)
        base_model = algo_cls.load(best_entry["policy_path"], device="cpu")
        before = rollout_policy(base_model, precomputed, env_cfg, holdout_idx)
        ft_model = algo_cls.load(out_path, device="cpu")
        after = rollout_policy(ft_model, precomputed, env_cfg, holdout_idx)

        report_lines += [
            f"## {sym}",
            "",
            f"- Base policy : algo={best_algo}, split={int(best['split'])}, seed={int(best['seed'])}",
            f"- Holdout window: last {holdout_n} bars",
            "",
            "| Metric | Before | After | Delta |",
            "|:--|---:|---:|---:|",
            f"| Trades | {before.n_trades} | {after.n_trades} | {after.n_trades - before.n_trades:+d} |",
            f"| Sharpe | {before.metrics.sharpe:+.3f} | {after.metrics.sharpe:+.3f} | {after.metrics.sharpe - before.metrics.sharpe:+.3f} |",
            f"| Sortino | {before.metrics.sortino:+.3f} | {after.metrics.sortino:+.3f} | {after.metrics.sortino - before.metrics.sortino:+.3f} |",
            f"| Max DD | {before.metrics.max_drawdown:+.3f} | {after.metrics.max_drawdown:+.3f} | {after.metrics.max_drawdown - before.metrics.max_drawdown:+.3f} |",
            f"| Hit rate | {before.metrics.hit_rate:.3f} | {after.metrics.hit_rate:.3f} | {after.metrics.hit_rate - before.metrics.hit_rate:+.3f} |",
            f"| Total return | {before.metrics.total_return:+.3f} | {after.metrics.total_return:+.3f} | {after.metrics.total_return - before.metrics.total_return:+.3f} |",
            "",
        ]
        log.info(
            "[%s] finetune: sharpe %.3f -> %.3f",
            sym, before.metrics.sharpe, after.metrics.sharpe,
        )

    report_path = path(cfg, cfg["report_dir"], "finetune_report.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    log.info("wrote %s", report_path)


if __name__ == "__main__":
    main()
