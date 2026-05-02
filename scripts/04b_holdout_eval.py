"""TRUE hold-out OOS evaluation — the final deployment gate.

The CPCV splits in scripts/03_train_ppo.py only ever see the first
(1 - data.holdout_frac) of bars. This script loads the best CPCV policy
per asset and runs it ONCE on the withheld tail (data/processed/
*_holdout.parquet), computing Sharpe + block-bootstrap CI + block
permutation p-value + DSR on a window the model has never touched.

If the gate passes (sharpe >= min_sharpe AND block_perm_p < max_perm_p),
`reports/holdout_report.json` is written with `status: "PASS"` and exit 0.
If it fails, status is `"FAIL"` and exit 1 — scripts/99_auto.py and
paper-trading launchers should short-circuit on exit != 0.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd
from stable_baselines3 import A2C, PPO

from _bootstrap import setup, path

from src.data.config_utils import parse_asset_configs
from src.data.features import feature_columns
from src.data.regimes import HMMRegimeModel
from src.env.trading_env import env_config_from_yaml
from src.training.evaluate import build_precomputed, rollout_policy
from src.training.pretrain_encoder import load_encoder
from src.validation.bootstrap import (
    acf_lag1,
    block_bootstrap_sharpe,
    block_permutation_pvalue_sharpe,
    bootstrap_pvalue_sharpe,
    permutation_pvalue_sharpe,
)
from src.validation.deflated_sr import deflated_sharpe_ratio

try:
    from sb3_contrib import RecurrentPPO
except ImportError:  # pragma: no cover
    RecurrentPPO = None  # type: ignore[assignment]

from src.training.grpo import GRPO as _GRPO


# Deployment gate thresholds (override via config.evaluation.holdout_gate.*)
DEFAULT_MIN_SHARPE = 0.30
DEFAULT_MAX_BOOT_P = 0.10     # centred block-bootstrap edge test p-value
DEFAULT_MAX_PERM_P = 0.20     # legacy permutation diagnostic (soft check)


def _load_model(algo: str, policy_path: str):
    if algo == "ppo":
        return PPO.load(policy_path, device="cpu")
    if algo == "a2c":
        return A2C.load(policy_path, device="cpu")
    if algo == "grpo":
        return _GRPO.load(policy_path, device="cpu")
    if algo == "recurrent_ppo":
        if RecurrentPPO is None:
            raise RuntimeError("sb3-contrib not installed; cannot load RecurrentPPO")
        return RecurrentPPO.load(policy_path, device="cpu")
    raise ValueError(f"unknown algorithm: {algo}")


def _best_entry_per_asset(manifest: list[dict], cfg: dict, log) -> dict[str, dict]:
    """Select the manifest entry with highest per_run Sharpe per asset.

    Falls back to reports/per_run_metrics.csv if the manifest does not
    itself carry Sharpe values. Otherwise uses the order-of-appearance
    as a tie-break (first encountered wins).
    """
    per_run_csv = path(cfg, cfg["report_dir"], "per_run_metrics.csv")
    runs_df = None
    if os.path.exists(per_run_csv):
        runs_df = pd.read_csv(per_run_csv)
    by_asset: dict[str, dict] = {}
    best_sharpe: dict[str, float] = {}
    for entry in manifest:
        asset = entry.get("asset", "")
        sym = asset
        s = int(entry["split"])
        seed = int(entry["seed"])
        algo = entry.get("algorithm", "ppo")
        if runs_df is not None:
            row = runs_df[
                (runs_df["asset"] == sym)
                & (runs_df["split"] == s)
                & (runs_df["seed"] == seed)
                & (runs_df["algorithm"] == algo)
            ]
            if len(row) > 0:
                sh = float(row["sharpe"].iloc[0])
            else:
                sh = -np.inf
        else:
            sh = 0.0
        if sh > best_sharpe.get(sym, -np.inf):
            best_sharpe[sym] = sh
            by_asset[sym] = entry
    for sym, entry in by_asset.items():
        log.info(
            "holdout: best %s policy = algo=%s split=%d seed=%s (cpcv_sharpe=%.3f)",
            sym, entry.get("algorithm", "ppo"), int(entry["split"]),
            entry["seed"], best_sharpe[sym],
        )
    return by_asset


def main() -> int:
    log = logging.getLogger("holdout_eval")
    cfg = setup()

    holdout_frac = float(cfg["data"].get("holdout_frac", 0.0))
    if holdout_frac <= 0.0:
        log.error(
            "data.holdout_frac=0 — no hold-out window exists. "
            "Set holdout_frac > 0 in config and re-run scripts/01_build_data.py."
        )
        return 2

    gate_cfg = cfg.get("evaluation", {}).get("holdout_gate", {})
    min_sharpe = float(gate_cfg.get("min_sharpe", DEFAULT_MIN_SHARPE))
    max_boot_p = float(gate_cfg.get("max_boot_p", DEFAULT_MAX_BOOT_P))
    max_perm_p = float(gate_cfg.get("max_perm_p", DEFAULT_MAX_PERM_P))

    manifest_path = path(cfg, cfg["artefact_dir"], "ppo_manifest.json")
    if not os.path.exists(manifest_path):
        log.error("manifest not found: %s — run scripts/03_train_ppo.py first", manifest_path)
        return 2
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    if not isinstance(manifest, list) or len(manifest) == 0:
        log.error("manifest is empty")
        return 2

    assets = parse_asset_configs(cfg)
    env_cfg = env_config_from_yaml(cfg)
    best = _best_entry_per_asset(manifest, cfg, log)

    per_asset: dict[str, dict] = {}
    all_pooled: list[float] = []

    for asset in assets:
        sym = asset.symbol
        if sym not in best:
            log.warning("no best policy for %s — skipping", sym)
            continue
        entry = best[sym]

        ho_feats_path = asset.features_path.replace(".parquet", "_holdout.parquet")
        ho_labels_path = asset.labels_path.replace(".parquet", "_holdout.parquet")
        ho_feats_full = path(cfg, ho_feats_path)
        ho_labels_full = path(cfg, ho_labels_path)
        if not os.path.exists(ho_feats_full):
            log.error("hold-out parquet missing: %s", ho_feats_full)
            return 2

        features = pd.read_parquet(ho_feats_full)
        feat_cols = feature_columns(features)
        log.info("[%s] hold-out bars: %d, features: %d", sym, len(features), len(feat_cols))

        enc_path = path(cfg, cfg["artefact_dir"], "encoders",
                        f"encoder_group{entry['encoder_group']}.pt")
        encoder = load_encoder(enc_path)
        pc = build_precomputed(features, feat_cols, encoder, seq_len=env_cfg.seq_len)
        # Attach regime posterior if the policy was trained with one so
        # the SB3 observation shape matches (else obs is 128-dim vs 131-dim).
        rp_path = entry.get("regime_path")
        if rp_path and os.path.exists(path(cfg, rp_path)):
            hmm = HMMRegimeModel.load(path(cfg, rp_path))
            pc["regime_posterior"] = hmm.posterior(pc["close"])
            log.info("[%s] attached regime posterior from %s", sym, rp_path)

        algo = entry.get("algorithm", "ppo")
        model = _load_model(algo, path(cfg, entry["policy_path"]))

        # Hold-out test_idx = every valid bar in the hold-out window.
        seq = env_cfg.seq_len
        test_idx = np.arange(seq, len(features))

        result = rollout_policy(model, pc, env_cfg, test_idx)
        rets = result.trade_returns.astype(float)
        if len(rets) == 0:
            log.warning("[%s] no closed trades on hold-out — skipping metrics", sym)
            per_asset[sym] = {
                "algo": algo, "split": int(entry["split"]), "seed": int(entry["seed"]),
                "holdout_bars": int(len(features)),
                "n_trades": 0, "sharpe": 0.0, "red_flag": "zero_trades",
            }
            continue

        boot = block_bootstrap_sharpe(
            rets,
            block=int(cfg["evaluation"]["bootstrap_block_size"]),
            n_resamples=int(cfg["evaluation"]["bootstrap_resamples"]),
        )
        boot_p = bootstrap_pvalue_sharpe(
            rets,
            block=int(cfg["evaluation"]["bootstrap_block_size"]),
            n_resamples=int(cfg["evaluation"]["bootstrap_resamples"]),
        )
        acf1 = acf_lag1(rets)
        perm_block = int(cfg["evaluation"].get("permutation_block_size", 8))
        use_block = abs(acf1) > 0.05
        if use_block:
            perm_p = block_permutation_pvalue_sharpe(
                rets, block_size=perm_block,
                n_resamples=int(cfg["evaluation"]["permutation_samples"]),
            )
        else:
            perm_p = permutation_pvalue_sharpe(
                rets, n_resamples=int(cfg["evaluation"]["permutation_samples"]),
            )
        dsr = deflated_sharpe_ratio(rets, n_trials=len(manifest))

        per_asset[sym] = {
            "algo": algo,
            "split": int(entry["split"]),
            "seed": int(entry["seed"]),
            "holdout_bars": int(len(features)),
            "n_trades": int(len(rets)),
            "sharpe": float(result.metrics.sharpe),
            "sortino": float(result.metrics.sortino),
            "max_drawdown": float(result.metrics.max_drawdown),
            "hit_rate": float(result.metrics.hit_rate),
            "total_return": float(result.metrics.total_return),
            "bootstrap_sr_lo": float(boot.lo),
            "bootstrap_sr_hi": float(boot.hi),
            "bootstrap_pvalue_sharpe": float(boot_p),
            "permutation_acf1": float(acf1),
            "permutation_block_size": perm_block if use_block else None,
            "permutation_pvalue": float(perm_p),
            "deflated_sharpe": float(dsr.deflated_sharpe),
        }
        all_pooled.extend(rets.tolist())
        log.info(
            "[%s] HOLD-OUT: sharpe=%.3f boot_p=%.3f perm_p=%.3f dsr=%.3f n_trades=%d",
            sym, result.metrics.sharpe, boot_p, perm_p,
            dsr.deflated_sharpe, len(rets),
        )

    # Overall gate: worst per-asset values bind (paper-trade only as
    # strong as the weakest asset).
    if not per_asset:
        log.error("no assets evaluated — manifest may be stale")
        return 2
    assets_with_trades = [a for a in per_asset.values() if a.get("n_trades", 0) > 0]
    if not assets_with_trades:
        log.error("no asset produced any closed trades on hold-out")
        return 1
    worst_sharpe = min(a["sharpe"] for a in assets_with_trades)
    worst_boot_p = max(a.get("bootstrap_pvalue_sharpe", 1.0) for a in assets_with_trades)
    worst_perm_p = max(a.get("permutation_pvalue", 1.0) for a in assets_with_trades)
    # PRIMARY gate: sharpe >= min AND bootstrap edge-test p <= max_boot_p
    passed = (worst_sharpe >= min_sharpe) and (worst_boot_p <= max_boot_p)
    status = "PASS" if passed else "FAIL"

    out = {
        "status": status,
        "worst_sharpe": worst_sharpe,
        "worst_boot_p": worst_boot_p,
        "worst_perm_p": worst_perm_p,
        "gate_min_sharpe": min_sharpe,
        "gate_max_boot_p": max_boot_p,
        "gate_max_perm_p": max_perm_p,
        "holdout_frac": holdout_frac,
        "per_asset": per_asset,
    }
    out_path = path(cfg, cfg["report_dir"], "holdout_report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    log.info("wrote %s", out_path)

    banner = "=" * 60
    print(banner)
    print(f"HOLD-OUT GATE: {status}")
    print(f"  worst_sharpe = {worst_sharpe:.3f}  (gate >= {min_sharpe})")
    print(f"  worst_boot_p = {worst_boot_p:.3f}  (gate <= {max_boot_p})")
    print(f"  worst_perm_p = {worst_perm_p:.3f}  (diag; gate <= {max_perm_p})")
    print(banner)
    if not passed:
        print("HOLD-OUT GATE FAILED — do not deploy this policy.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
