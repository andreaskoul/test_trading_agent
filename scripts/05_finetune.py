"""Finetune the best PPO policy and evaluate on a held-out window."""

from __future__ import annotations

import json
import logging
import os

import numpy as np
import pandas as pd
from stable_baselines3 import PPO

from _bootstrap import setup, path

from src.data.features import feature_columns
from src.env.trading_env import EnvConfig
from src.training.evaluate import build_precomputed, rollout_policy
from src.training.finetune import FinetuneConfig, finetune_policy
from src.training.pretrain_encoder import load_encoder


def main() -> None:
    log = logging.getLogger("finetune")
    cfg = setup()

    features = pd.read_parquet(path(cfg, cfg["data"]["features_path"]))
    feat_cols = feature_columns(features)
    n = len(features)
    holdout_n = int(cfg["finetune"]["holdout_frac"] * n)
    train_idx = np.arange(0, n - holdout_n)
    holdout_idx = np.arange(n - holdout_n, n)

    env_cfg = EnvConfig(
        seq_len=cfg["env"]["seq_len"],
        rr_upper=cfg["triple_barrier"]["rr_upper"],
        rr_lower=cfg["triple_barrier"]["rr_lower"],
        horizon=cfg["triple_barrier"]["horizon"],
        spread_bps=cfg["env"]["spread_bps"],
        reward_tp=cfg["env"]["reward_tp"],
        reward_sl=cfg["env"]["reward_sl"],
    )

    manifest_path = path(cfg, cfg["artefact_dir"], "ppo_manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    per_run = pd.read_csv(path(cfg, cfg["report_dir"], "per_run_metrics.csv"))
    # deflated-friendly score: sharpe discounted by downside
    per_run["score"] = per_run["sharpe"] - 0.5 * per_run["max_drawdown"].abs() * 10
    best = per_run.sort_values("score", ascending=False).iloc[0]
    best_entry = [
        m for m in manifest if m["split"] == int(best["split"]) and m["seed"] == int(best["seed"])
    ][0]
    log.info(
        "best run: split=%d seed=%d sharpe=%.2f dd=%.2f",
        int(best["split"]),
        int(best["seed"]),
        best["sharpe"],
        best["max_drawdown"],
    )

    encoder_group = best_entry["encoder_group"]
    encoder_path = path(cfg, cfg["artefact_dir"], "encoders", f"encoder_group{encoder_group}.pt")
    encoder = load_encoder(encoder_path)

    precomputed = build_precomputed(features, feat_cols, encoder, seq_len=env_cfg.seq_len)

    ft_cfg = FinetuneConfig(
        timesteps=cfg["finetune"]["timesteps"],
        lr=cfg["finetune"]["lr"],
        ent_coef=cfg["finetune"]["ent_coef"],
    )
    out_path = path(cfg, cfg["artefact_dir"], "policies", "ppo_finetuned.zip")
    finetune_policy(
        precomputed=precomputed,
        env_cfg=env_cfg,
        train_idx=train_idx,
        base_policy_path=best_entry["policy_path"],
        cfg=ft_cfg,
        save_path=out_path,
        seed=int(best["seed"]),
    )

    base_model = PPO.load(best_entry["policy_path"], device="cpu")
    before = rollout_policy(base_model, precomputed, env_cfg, holdout_idx)
    ft_model = PPO.load(out_path, device="cpu")
    after = rollout_policy(ft_model, precomputed, env_cfg, holdout_idx)

    report = [
        "# Finetune Report",
        "",
        f"- Base policy : split={int(best['split'])}, seed={int(best['seed'])}",
        f"- Holdout window: last {holdout_n} bars (not seen during encoder pretrain or PPO training)",
        "",
        "## Held-out metrics",
        "",
        "| Metric | Before | After | Delta |",
        "|:--|---:|---:|---:|",
        f"| Trades | {before.n_trades} | {after.n_trades} | {after.n_trades - before.n_trades:+d} |",
        f"| Sharpe | {before.metrics.sharpe:+.3f} | {after.metrics.sharpe:+.3f} | {after.metrics.sharpe - before.metrics.sharpe:+.3f} |",
        f"| Sortino | {before.metrics.sortino:+.3f} | {after.metrics.sortino:+.3f} | {after.metrics.sortino - before.metrics.sortino:+.3f} |",
        f"| Max DD | {before.metrics.max_drawdown:+.3f} | {after.metrics.max_drawdown:+.3f} | {after.metrics.max_drawdown - before.metrics.max_drawdown:+.3f} |",
        f"| Hit rate | {before.metrics.hit_rate:.3f} | {after.metrics.hit_rate:.3f} | {after.metrics.hit_rate - before.metrics.hit_rate:+.3f} |",
        f"| Total return | {before.metrics.total_return:+.3f} | {after.metrics.total_return:+.3f} | {after.metrics.total_return - before.metrics.total_return:+.3f} |",
    ]
    report_path = path(cfg, cfg["report_dir"], "finetune_report.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(report))
    log.info("wrote %s", report_path)


if __name__ == "__main__":
    main()
