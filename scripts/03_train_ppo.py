"""Train PPO policies across CPCV splits and seeds, per asset.

For Combinatorial Purged K-Fold with N groups and k test groups, a single
"backtest path" covers ALL bars - so we train one PPO per *split* (one
combination of k test groups), not per path. The 15 splits for N=6, k=2
can then be reassembled into 5 backtest paths at evaluation time by
concatenating their test blocks.

Multi-asset: uses the shared encoder (pretrained on concatenated features
from all assets) but trains independent per-asset PPO policies so each
instrument can specialise its entry/exit timing.
"""

from __future__ import annotations

import argparse
import json
import logging
import os

import numpy as np
import pandas as pd

from _bootstrap import setup, path

from src.data.config_utils import parse_asset_configs
from src.data.features import feature_columns
from src.data.regimes import HMMRegimeConfig, fit_or_load_regime
from src.env.trading_env import env_config_from_yaml
from src.models.precompute import precompute_embeddings
from src.training.pretrain_encoder import load_encoder
from src.training.train_ppo import PPORunConfig, train_ppo_run
from src.validation.cpcv import CombinatorialPurgedKFold, _group_bounds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="Reduce splits + seeds + steps")
    ap.add_argument("--max-splits", type=int, default=None)
    ap.add_argument("--max-seeds", type=int, default=None)
    args = ap.parse_args()

    log = logging.getLogger("train_ppo")
    cfg = setup()

    assets = parse_asset_configs(cfg)

    seeds = cfg["ppo"]["seeds"]
    total_steps = cfg["ppo"]["total_timesteps"]
    algorithms = cfg["ppo"].get("algorithms", ["ppo"])
    if args.fast:
        total_steps = max(8000, total_steps // 4)
        seeds = seeds[:3]
    if args.max_seeds is not None:
        seeds = seeds[: args.max_seeds]

    env_cfg = env_config_from_yaml(cfg)
    log.info(
        "reward_mode=%s return_scale=%.1f cost_lambda=%.2f dsr_eta=%.3f",
        env_cfg.reward_mode,
        env_cfg.reward_return_scale,
        env_cfg.reward_cost_lambda,
        env_cfg.reward_dsr_eta,
    )

    run_cfg = PPORunConfig(
        total_timesteps=total_steps,
        n_steps=cfg["ppo"]["n_steps"],
        batch_size=cfg["ppo"]["batch_size"],
        gae_lambda=cfg["ppo"]["gae_lambda"],
        gamma=cfg["ppo"]["gamma"],
        ent_coef=cfg["ppo"]["ent_coef"],
        clip_range=cfg["ppo"]["clip_range"],
        learning_rate=cfg["ppo"]["learning_rate"],
        curriculum=cfg["ppo"]["curriculum"],
    )

    regime_cfg = HMMRegimeConfig()
    encoders_dir = path(cfg, cfg["artefact_dir"], "encoders")
    policy_dir = path(cfg, cfg["artefact_dir"], "policies")
    regimes_dir = path(cfg, cfg["artefact_dir"], "regimes")
    os.makedirs(policy_dir, exist_ok=True)
    os.makedirs(regimes_dir, exist_ok=True)

    manifest: list[dict] = []

    for asset in assets:
        sym = asset.symbol
        # Sanitised tag for filenames (e.g. "GC=F" -> "gc_f")
        sym_tag = sym.lower().replace("=", "_").replace("/", "_")
        log.info("=== training policies for %s ===", sym)

        features = pd.read_parquet(path(cfg, asset.features_path))
        labels = pd.read_parquet(path(cfg, asset.labels_path))
        labels["t1"] = pd.to_datetime(labels["t1"], utc=True)
        feat_cols = feature_columns(features)
        t1_series = pd.Series(labels["t1"].values, index=features.index)

        cpcv = CombinatorialPurgedKFold(
            n_splits=cfg["cpcv"]["n_splits"],
            n_test_splits=cfg["cpcv"]["n_test_splits"],
            embargo_pct=cfg["cpcv"]["embargo_pct"],
        )
        splits = list(cpcv.split(t1_series))
        if args.fast:
            splits = splits[:6]
        if args.max_splits is not None:
            splits = splits[: args.max_splits]

        n = len(features)
        n_splits = cfg["cpcv"]["n_splits"]
        groups = _group_bounds(n, n_splits)

        feats_arr = features[feat_cols].to_numpy(dtype=np.float32)
        close_arr = features["close"].to_numpy(dtype=np.float64)
        atr_arr = features["atr"].to_numpy(dtype=np.float64)
        rv = pd.Series(atr_arr / close_arr).rolling(20, min_periods=1).mean()
        vol_quantile = rv.rank(pct=True).to_numpy()

        # Cache precomputed embeddings per encoder group for this asset
        precomputed_cache: dict[int, dict] = {}

        def get_precomputed(anchor_group: int) -> dict:
            if anchor_group in precomputed_cache:
                return precomputed_cache[anchor_group]
            encoder = load_encoder(os.path.join(encoders_dir, f"encoder_group{anchor_group}.pt"))
            emb = precompute_embeddings(encoder, feats_arr, seq_len=env_cfg.seq_len)
            pc = dict(close=close_arr, atr=atr_arr, embeddings=emb, vol_quantile=vol_quantile)
            precomputed_cache[anchor_group] = pc
            return pc

        log.info(
            "[%s] %d splits x %d algos x %d seeds = %d runs",
            sym, len(splits), len(algorithms), len(seeds),
            len(splits) * len(algorithms) * len(seeds),
        )

        for s_idx, split in enumerate(splits):
            anchor_group = int(split.test_groups[0])
            precomputed_base = get_precomputed(anchor_group)
            train_idx = split.train_idx
            test_idx = split.test_idx
            test_blocks = [[int(g), int(groups[g][0]), int(groups[g][1] - 1)] for g in split.test_groups]

            # Fit (or load cached) per-asset HMM
            regime_cache = os.path.join(regimes_dir, f"hmm_{sym_tag}_split{s_idx}.pkl")
            _, regime_post = fit_or_load_regime(
                close=precomputed_base["close"],
                train_idx=train_idx,
                cache_path=regime_cache,
                cfg=regime_cfg,
            )
            precomputed = {**precomputed_base, "regime_posterior": regime_post}

            log.info(
                "[%s] split %d: train=%d test=%d groups=%s encoder=group%d",
                sym, s_idx, len(train_idx), len(test_idx),
                list(split.test_groups), anchor_group,
            )

            encoder = load_encoder(os.path.join(encoders_dir, f"encoder_group{anchor_group}.pt"))

            for algo in algorithms:
                algo_cfg = PPORunConfig(
                    total_timesteps=total_steps,
                    n_steps=run_cfg.n_steps,
                    batch_size=run_cfg.batch_size,
                    gae_lambda=run_cfg.gae_lambda,
                    gamma=run_cfg.gamma,
                    ent_coef=run_cfg.ent_coef,
                    clip_range=run_cfg.clip_range,
                    learning_rate=run_cfg.learning_rate,
                    curriculum=run_cfg.curriculum,
                    algorithm=algo,
                )
                for seed in seeds:
                    tag = algo if algo != "ppo" else "ppo"
                    save_path = os.path.join(
                        policy_dir, f"{sym_tag}_{tag}_split{s_idx}_seed{seed}.zip"
                    )
                    if os.path.exists(save_path):
                        log.info("skipping %s %s split=%d seed=%d (already exists)", sym, algo, s_idx, seed)
                    else:
                        log.info("training %s %s split=%d seed=%d", sym, algo, s_idx, seed)
                        train_ppo_run(
                            features=features,
                            feature_cols=feat_cols,
                            env_cfg=env_cfg,
                            encoder=encoder,
                            train_idx=train_idx,
                            run_cfg=algo_cfg,
                            seed=seed,
                            save_path=save_path,
                            precomputed=precomputed,
                        )
                    manifest.append(
                        dict(
                            asset=sym,
                            split=int(s_idx),
                            test_groups=list(map(int, split.test_groups)),
                            seed=int(seed),
                            algorithm=algo,
                            encoder_group=anchor_group,
                            policy_path=save_path,
                            regime_path=regime_cache,
                            train_size=int(len(train_idx)),
                            test_size=int(len(test_idx)),
                            test_blocks=test_blocks,
                        )
                    )
                # Write manifest incrementally
                manifest_path = path(cfg, cfg["artefact_dir"], "ppo_manifest.json")
                with open(manifest_path, "w") as f:
                    json.dump(manifest, f, indent=2)

    log.info(
        "wrote manifest -> %s with %d runs across %d assets",
        path(cfg, cfg["artefact_dir"], "ppo_manifest.json"),
        len(manifest),
        len(assets),
    )


if __name__ == "__main__":
    main()
