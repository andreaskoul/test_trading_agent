"""Evaluate all trained policies and write a statistics report.

Supports multi-asset evaluation with per-asset and cross-asset pooled
metrics, cross-asset meta-labeling, and algorithm-diverse ensembles (T2.2).
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from stable_baselines3 import A2C, PPO

from _bootstrap import setup, path

from src.data.config_utils import parse_asset_configs
from src.data.features import feature_columns
from src.data.regimes import HMMRegimeModel
from src.env.trading_env import env_config_from_yaml
from src.models.meta_label import MetaLabelConfig, MetaLabelModel
from src.training.evaluate import build_precomputed, rollout_policy, rollout_with_cost
from src.training.pretrain_encoder import load_encoder
from src.validation.bootstrap import block_bootstrap_sharpe, permutation_pvalue_sharpe
from src.validation.deflated_sr import deflated_sharpe_ratio, sharpe_ratio

try:
    from sb3_contrib import RecurrentPPO
except ImportError:  # pragma: no cover
    RecurrentPPO = None  # type: ignore[assignment]

from src.training.grpo import GRPO as _GRPO

_ALGO_MAP: dict[str, type] = {"ppo": PPO, "a2c": A2C, "grpo": _GRPO}
if RecurrentPPO is not None:
    _ALGO_MAP["recurrent_ppo"] = RecurrentPPO
    _ALGO_MAP["rppo"] = RecurrentPPO


def _load_model(entry: dict):
    algo = entry.get("algorithm", "ppo").lower()
    cls = _ALGO_MAP.get(algo, PPO)
    return cls.load(entry["policy_path"], device="cpu")


def _write_report(report_path: str, lines: list[str]) -> None:
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(lines))


def _plot_sharpe_hist(values: np.ndarray, out_path: str, title_suffix: str = "") -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(values, bins=12, color="steelblue", alpha=0.85, edgecolor="black")
    ax.axvline(0, color="k", lw=1)
    ax.axvline(float(np.mean(values)), color="red", lw=1.5, label=f"mean={np.mean(values):.2f}")
    ax.set_title(f"Sharpe distribution{title_suffix}")
    ax.set_xlabel("Annualised Sharpe (trade-based)")
    ax.set_ylabel("Count")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def _plot_equity_curves(curves: list[np.ndarray], out_path: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    for eq in curves:
        ax.plot(eq, alpha=0.5, lw=1)
    ax.set_title("Equity curves (all CPCV runs)")
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Cumulative equity")
    ax.axhline(1, color="k", lw=0.5)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def _plot_cost_curve(costs: list[float], sr_means: list[float], out_path: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(costs, sr_means, marker="o", color="darkorange")
    ax.axhline(0, color="k", lw=0.5)
    ax.set_title("Mean Sharpe vs transaction cost (bps)")
    ax.set_xlabel("Spread (bps)")
    ax.set_ylabel("Mean Sharpe")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def _evaluate_entries(
    entries: list[dict],
    features_map: dict[str, pd.DataFrame],
    cfg: dict,
    env_cfg,
    log,
):
    """Run rollouts for a list of manifest entries.

    Returns per_run metrics, equity curves, pooled returns, and trade
    traces keyed by split (for meta-labeling).
    """
    # Cache precomputed embeddings per (asset, encoder_group)
    precomputed_cache: dict[tuple[str, int], dict] = {}
    regime_cache: dict[tuple[str, int], np.ndarray] = {}

    def get_precomputed(asset: str, encoder_group: int) -> dict:
        key = (asset, encoder_group)
        if key in precomputed_cache:
            return precomputed_cache[key]
        features = features_map[asset]
        feat_cols = feature_columns(features)
        enc_path = path(cfg, cfg["artefact_dir"], "encoders", f"encoder_group{encoder_group}.pt")
        encoder = load_encoder(enc_path)
        pc = build_precomputed(features, feat_cols, encoder, seq_len=env_cfg.seq_len)
        precomputed_cache[key] = pc
        return pc

    def get_regime_post(entry: dict) -> np.ndarray | None:
        rp_path = entry.get("regime_path")
        if not rp_path or not os.path.exists(rp_path):
            return None
        asset = entry.get("asset", "")
        s = int(entry["split"])
        key = (asset, s)
        if key in regime_cache:
            return regime_cache[key]
        hmm = HMMRegimeModel.load(rp_path)
        pc = get_precomputed(asset, int(entry["encoder_group"]))
        post = hmm.posterior(pc["close"])
        regime_cache[key] = post
        return post

    per_run = []
    curves = []
    returns_by_split: dict[tuple[str, int], list[np.ndarray]] = defaultdict(list)
    pooled_returns: list[float] = []
    trace_by_split: dict[tuple[str, int], tuple[list[np.ndarray], list[int]]] = defaultdict(
        lambda: ([], [])
    )
    returns_trace_by_split: dict[tuple[str, int], list[np.ndarray]] = defaultdict(list)

    for entry in entries:
        asset = entry.get("asset", "unknown")
        model = _load_model(entry)
        test_idx = np.concatenate(
            [np.arange(int(g[1]), int(g[2]) + 1) for g in entry["test_blocks"]]
        )
        pc_base = get_precomputed(asset, int(entry["encoder_group"]))
        regime_post = get_regime_post(entry)
        pc = {**pc_base, "regime_posterior": regime_post} if regime_post is not None else pc_base
        result = rollout_policy(model, pc, env_cfg, test_idx, trace_entries=True)
        algo = entry.get("algorithm", "ppo")
        metrics = result.metrics.asdict()
        metrics["split"] = entry["split"]
        metrics["seed"] = entry["seed"]
        metrics["algorithm"] = algo
        metrics["asset"] = asset
        per_run.append(metrics)
        curves.append(result.equity)
        split_key = (asset, entry["split"])
        returns_by_split[split_key].append(result.trade_returns)
        pooled_returns.extend(result.trade_returns.tolist())
        if result.trade_features is not None and result.n_trades > 0:
            feats_list, labels_list = trace_by_split[split_key]
            feats_list.append(result.trade_features)
            labels_list.append((result.trade_returns > 0).astype(np.int64))
            returns_trace_by_split[split_key].append(result.trade_returns)
        log.info(
            "%s %s split=%d seed=%d n_trades=%d sharpe=%.2f hit=%.2f dd=%.2f",
            asset, algo, entry["split"], entry["seed"],
            result.n_trades, metrics["sharpe"], metrics["hit_rate"],
            metrics["max_drawdown"],
        )

    return per_run, curves, returns_by_split, pooled_returns, trace_by_split, returns_trace_by_split


def _run_meta_labeling(
    trace_by_split, returns_trace_by_split, meta_thresholds, log,
):
    """Cross-asset meta-labeling: train on trades from ALL other splits (across
    all assets), test on each split. Returns list of threshold result dicts."""
    split_X: dict[tuple, np.ndarray] = {}
    split_y: dict[tuple, np.ndarray] = {}
    split_returns_aligned: dict[tuple, np.ndarray] = {}

    for key in trace_by_split:
        Xs_list, ys_list = trace_by_split[key]
        if not Xs_list:
            continue
        split_X[key] = np.concatenate(Xs_list, axis=0)
        split_y[key] = np.concatenate(ys_list, axis=0)
        ret_list = returns_trace_by_split.get(key, [])
        if ret_list:
            split_returns_aligned[key] = np.concatenate(ret_list, axis=0)

    split_keys = sorted(split_X.keys())
    if not split_keys:
        return []

    per_split_meta: dict[tuple, MetaLabelModel] = {}
    for key in split_keys:
        # Train on ALL other splits (cross-asset leave-one-out)
        X_parts = [split_X[o] for o in split_keys if o != key]
        y_parts = [split_y[o] for o in split_keys if o != key]
        if not X_parts:
            continue
        X_tr = np.concatenate(X_parts, axis=0)
        y_tr = np.concatenate(y_parts, axis=0)
        mm = MetaLabelModel(MetaLabelConfig()).fit(X_tr, y_tr)
        per_split_meta[key] = mm
        log.info(
            "meta split=%s train_trades=%d base_rate=%.3f",
            key, len(X_tr), mm.base_rate,
        )

    meta_results = []
    for thr in meta_thresholds:
        gated_returns: list[float] = []
        gated_sharpes: list[float] = []
        for key in split_keys:
            mm = per_split_meta.get(key)
            if mm is None:
                continue
            Xs = split_X[key]
            rets_s = split_returns_aligned.get(key)
            if rets_s is None or len(rets_s) != len(Xs):
                continue
            probs = mm.predict_proba(Xs)
            keep = probs >= float(thr)
            kept = rets_s[keep]
            if len(kept) == 0:
                continue
            gated_returns.extend(kept.tolist())
            gated_sharpes.append(sharpe_ratio(kept, periods_per_year=252.0 / 5.0))
        if not gated_returns:
            continue
        pooled_gated = np.asarray(gated_returns, dtype=float)
        pooled_sr = sharpe_ratio(pooled_gated, periods_per_year=252.0 / 5.0)
        meta_results.append(dict(
            threshold=float(thr),
            mean_sharpe=float(np.mean(gated_sharpes)),
            pooled_sharpe=float(pooled_sr),
            n_trades=int(len(pooled_gated)),
            total_return=float((1 + pooled_gated).prod() - 1),
        ))
        log.info(
            "meta thr=%.2f mean_sharpe=%.3f pooled=%.3f n_trades=%d",
            thr, float(np.mean(gated_sharpes)), float(pooled_sr), len(pooled_gated),
        )
    return meta_results


def main() -> None:
    log = logging.getLogger("evaluate")
    cfg = setup()

    assets = parse_asset_configs(cfg)
    env_cfg = env_config_from_yaml(cfg)

    manifest_path = path(cfg, cfg["artefact_dir"], "ppo_manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    log.info("loaded %d runs from manifest", len(manifest))

    # Load per-asset features
    features_map: dict[str, pd.DataFrame] = {}
    for asset in assets:
        features_map[asset.symbol] = pd.read_parquet(path(cfg, asset.features_path))

    # For backward compat: entries without "asset" field get first asset
    default_asset = assets[0].symbol if assets else "unknown"
    for entry in manifest:
        if "asset" not in entry:
            entry["asset"] = default_asset

    # Group manifest by asset
    asset_entries: dict[str, list[dict]] = defaultdict(list)
    for entry in manifest:
        asset_entries[entry["asset"]].append(entry)

    # Evaluate all entries
    per_run, curves, returns_by_split, pooled_returns, trace_by_split, returns_trace_by_split = (
        _evaluate_entries(manifest, features_map, cfg, env_cfg, log)
    )

    df_runs = pd.DataFrame(per_run)
    df_runs.to_csv(path(cfg, cfg["report_dir"], "per_run_metrics.csv"), index=False)

    # ------------------------------------------------------------------
    # Global pooled statistics
    # ------------------------------------------------------------------
    sharpes = df_runs["sharpe"].to_numpy()
    pooled = np.asarray(pooled_returns, dtype=float)

    dsr = deflated_sharpe_ratio(pooled, n_trials=len(df_runs))
    boot = block_bootstrap_sharpe(
        pooled,
        block=cfg["evaluation"]["bootstrap_block_size"],
        n_resamples=cfg["evaluation"]["bootstrap_resamples"],
    )
    perm_p = permutation_pvalue_sharpe(
        pooled, n_resamples=cfg["evaluation"]["permutation_samples"]
    )

    # Transaction cost sweep
    cost_means = []
    cost_details = []
    costs = cfg["evaluation"]["costs_bps"]
    for c in costs:
        run_sr = []
        for entry in manifest:
            asset = entry["asset"]
            model = _load_model(entry)
            test_idx = np.concatenate(
                [np.arange(int(g[1]), int(g[2]) + 1) for g in entry["test_blocks"]]
            )
            features = features_map[asset]
            feat_cols = feature_columns(features)
            enc_path = path(cfg, cfg["artefact_dir"], "encoders", f"encoder_group{entry['encoder_group']}.pt")
            encoder = load_encoder(enc_path)
            pc = build_precomputed(features, feat_cols, encoder, seq_len=env_cfg.seq_len)
            rp = entry.get("regime_path")
            if rp and os.path.exists(rp):
                hmm = HMMRegimeModel.load(rp)
                pc["regime_posterior"] = hmm.posterior(pc["close"])
            r = rollout_with_cost(model, pc, env_cfg, test_idx, c)
            run_sr.append(r.metrics.sharpe)
        cost_means.append(float(np.mean(run_sr)))
        cost_details.append(dict(cost_bps=c, sharpe_mean=float(np.mean(run_sr)), sharpe_std=float(np.std(run_sr))))
        log.info("cost %.1f bps -> mean sharpe=%.2f", c, np.mean(run_sr))

    # Seed ensemble (per asset+split, pool trade-returns across seeds)
    ensemble_sharpes_by_asset: dict[str, list[float]] = defaultdict(list)
    for (asset, s_idx), arrs in sorted(returns_by_split.items()):
        if not arrs:
            continue
        pooled_split = np.concatenate(arrs)
        ensemble_sharpes_by_asset[asset].append(sharpe_ratio(pooled_split, periods_per_year=252.0 / 5.0))

    # Algorithm ensemble (T2.2)
    algo_sharpes: dict[str, list[float]] = defaultdict(list)
    for row in per_run:
        algo = row.get("algorithm", "ppo")
        algo_sharpes[algo].append(row["sharpe"])

    algo_summary: list[dict] = []
    for algo in sorted(algo_sharpes.keys()):
        srs = algo_sharpes[algo]
        algo_summary.append(dict(
            algorithm=algo,
            mean_sharpe=float(np.mean(srs)),
            std_sharpe=float(np.std(srs)),
            n_runs=len(srs),
        ))

    # Cross-asset meta-labeling
    meta_thresholds = [0.50, 0.55, 0.60]
    meta_results = _run_meta_labeling(
        trace_by_split, returns_trace_by_split, meta_thresholds, log,
    )

    # Plots
    plot_dir = path(cfg, cfg["report_dir"])
    os.makedirs(plot_dir, exist_ok=True)
    _plot_sharpe_hist(sharpes, os.path.join(plot_dir, "sharpe_hist.png"), " (all assets)")
    _plot_equity_curves(curves, os.path.join(plot_dir, "equity_curves.png"))
    _plot_cost_curve(costs, cost_means, os.path.join(plot_dir, "cost_curve.png"))

    # Red-flag analysis
    red_flags = []
    if np.mean(sharpes) <= 0:
        red_flags.append("Mean Sharpe <= 0")
    if dsr.deflated_sharpe < 0.95:
        red_flags.append(f"DSR p-value > 0.05 (deflated={dsr.deflated_sharpe:.3f})")
    if perm_p > 0.10:
        red_flags.append(f"Permutation p-value > 0.10 (p={perm_p:.3f})")
    mean_mdd = float(np.mean(df_runs["max_drawdown"]))
    if mean_mdd < -0.25:
        red_flags.append(f"Mean max drawdown < -25% ({mean_mdd:.2%})")
    if costs and cost_means and cost_means[min(3, len(cost_means) - 1)] <= 0:
        red_flags.append("Edge collapses at >=5 bps transaction cost")

    # ------------------------------------------------------------------
    # Build Markdown report
    # ------------------------------------------------------------------
    unique_assets = sorted(df_runs["asset"].unique()) if "asset" in df_runs.columns else []
    report_lines = [
        "# Evaluation Report",
        "",
        f"- Runs evaluated: **{len(df_runs)}**",
        f"- Assets: **{', '.join(unique_assets) if unique_assets else 'n/a'}**",
        f"- Pooled trades: **{len(pooled)}**",
    ]

    # -- Per-asset sections --
    if len(unique_assets) > 1:
        for asset in unique_assets:
            asset_df = df_runs[df_runs["asset"] == asset]
            asset_sharpes = asset_df["sharpe"].to_numpy()
            report_lines += [
                "",
                f"## Per-asset: {asset}",
                "",
                f"- Runs: {len(asset_df)}",
                f"- Mean Sharpe: {np.mean(asset_sharpes):+.3f}",
                f"- Median Sharpe: {np.median(asset_sharpes):+.3f}",
                f"- Std: {np.std(asset_sharpes):.3f}",
            ]
            if asset in ensemble_sharpes_by_asset:
                report_lines += [
                    "",
                    "| Split | Sharpe |",
                    "|------:|-------:|",
                ]
                for i, s in enumerate(ensemble_sharpes_by_asset[asset]):
                    report_lines.append(f"| {i} | {s:+.3f} |")

    # -- Global pooled stats --
    report_lines += [
        "",
        "## Sharpe distribution (all assets pooled)",
        "",
        f"- mean   : {np.mean(sharpes):+.3f}",
        f"- median : {np.median(sharpes):+.3f}",
        f"- std    : {np.std(sharpes):.3f}",
        f"- p5     : {np.percentile(sharpes, 5):+.3f}",
        f"- p95    : {np.percentile(sharpes, 95):+.3f}",
        f"- min    : {np.min(sharpes):+.3f}",
        f"- max    : {np.max(sharpes):+.3f}",
        "",
        "## Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)",
        "",
        f"- Observed Sharpe (pooled)   : {dsr.sharpe:.3f}",
        f"- Trials                     : {dsr.n_trials}",
        f"- E[max SR] under null       : {dsr.expected_max_sr:.3f}",
        f"- PSR vs 0                   : {dsr.psr_vs_zero:.3f}",
        f"- **Deflated SR (P > null)** : **{dsr.deflated_sharpe:.3f}**",
        f"- Skewness                   : {dsr.skew:+.3f}",
        f"- Excess kurtosis            : {dsr.kurt_excess:+.3f}",
        f"- Min Track Record Length    : {dsr.min_trl if dsr.min_trl is not None else 'n/a'}",
        "",
        "## Bootstrap 95% CI (block bootstrap)",
        "",
        f"- Point Sharpe : {boot.point:.3f}",
        f"- 2.5% / 97.5% : [{boot.lo:.3f}, {boot.hi:.3f}]  ({boot.samples} resamples)",
        "",
        "## Monte Carlo permutation test",
        "",
        f"- One-sided p-value vs random shuffle: **{perm_p:.3f}** (lower = more evidence of sequential edge)",
        "",
        "## Transaction cost sensitivity",
        "",
        "| Cost (bps) | Mean Sharpe |",
        "|-----------:|-------------:|",
    ]
    for c, s in zip(costs, cost_means):
        report_lines.append(f"| {c:.1f} | {s:+.3f} |")

    # Seed ensemble (per asset)
    report_lines += [
        "",
        "## Seed ensemble (pooled trades per split)",
        "",
    ]
    for asset in unique_assets:
        if asset in ensemble_sharpes_by_asset:
            report_lines += [
                f"### {asset}",
                "",
                "| Split | Sharpe |",
                "|------:|-------:|",
            ]
            for i, s in enumerate(ensemble_sharpes_by_asset[asset]):
                report_lines.append(f"| {i} | {s:+.3f} |")
            report_lines.append("")

    if algo_summary and len(algo_summary) > 1:
        report_lines += [
            "## Algorithm ensemble (T2.2)",
            "",
            "Per-algorithm mean Sharpe across all CPCV splits, seeds, and assets.",
            "",
            "| Algorithm | Mean Sharpe | Std | Runs |",
            "|:----------|------------:|----:|-----:|",
        ]
        for a in algo_summary:
            report_lines.append(
                "| {algo} | {ms:+.3f} | {ss:.3f} | {nr} |".format(
                    algo=a["algorithm"],
                    ms=a["mean_sharpe"],
                    ss=a["std_sharpe"],
                    nr=a["n_runs"],
                )
            )

    if meta_results:
        report_lines += [
            "",
            "## Cross-asset meta-labeling gate (T1.1, Lopez de Prado)",
            "",
            "HistGBM classifier trained on trades from ALL other splits across ALL",
            "assets (cross-asset leave-one-out). Predicts P(profit) from entry",
            "embedding+direction+vol-quantile. Actions with P < threshold are gated.",
            "",
            "| Threshold | Mean Sharpe | Pooled Sharpe | Trades | Total Return |",
            "|----------:|------------:|--------------:|-------:|-------------:|",
        ]
        for mr in meta_results:
            report_lines.append(
                "| {thr:.2f} | {ms:+.3f} | {ps:+.3f} | {nt} | {tr:+.3f} |".format(
                    thr=mr["threshold"],
                    ms=mr["mean_sharpe"],
                    ps=mr["pooled_sharpe"],
                    nt=mr["n_trades"],
                    tr=mr["total_return"],
                )
            )

    report_lines += [
        "",
        "## Red flags",
        "",
    ]
    if not red_flags:
        report_lines.append("*None detected.*")
    else:
        for r in red_flags:
            report_lines.append(f"- {r}")

    report_lines += [
        "",
        "## Plots",
        "",
        "- ![Sharpe histogram](sharpe_hist.png)",
        "- ![Equity curves](equity_curves.png)",
        "- ![Transaction cost curve](cost_curve.png)",
    ]

    _write_report(path(cfg, cfg["report_dir"], "evaluation_report.md"), report_lines)

    with open(path(cfg, cfg["report_dir"], "evaluation_summary.json"), "w") as f:
        json.dump(
            dict(
                n_runs=len(df_runs),
                n_assets=len(unique_assets),
                assets=unique_assets,
                sharpe_mean=float(np.mean(sharpes)),
                sharpe_std=float(np.std(sharpes)),
                sharpe_p5=float(np.percentile(sharpes, 5)),
                sharpe_p95=float(np.percentile(sharpes, 95)),
                deflated_sharpe=dsr.deflated_sharpe,
                psr_vs_zero=dsr.psr_vs_zero,
                expected_max_sr=dsr.expected_max_sr,
                permutation_pvalue=perm_p,
                bootstrap_lo=boot.lo,
                bootstrap_hi=boot.hi,
                cost_sweep=cost_details,
                algo_ensemble=algo_summary,
                meta_gate=meta_results,
                red_flags=red_flags,
            ),
            f,
            indent=2,
        )
    log.info("wrote report + summary to %s", cfg["report_dir"])


if __name__ == "__main__":
    main()
