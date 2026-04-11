"""Evaluate all trained PPO policies and write a statistics report."""

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
from stable_baselines3 import PPO

from _bootstrap import setup, path

from src.data.features import feature_columns
from src.env.trading_env import EnvConfig
from src.training.evaluate import build_precomputed, rollout_policy, rollout_with_cost
from src.training.pretrain_encoder import load_encoder
from src.validation.bootstrap import block_bootstrap_sharpe, permutation_pvalue_sharpe
from src.validation.deflated_sr import deflated_sharpe_ratio, sharpe_ratio


def _write_report(report_path: str, lines: list[str]) -> None:
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(lines))


def _plot_sharpe_hist(values: np.ndarray, out_path: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(values, bins=12, color="steelblue", alpha=0.85, edgecolor="black")
    ax.axvline(0, color="k", lw=1)
    ax.axvline(float(np.mean(values)), color="red", lw=1.5, label=f"mean={np.mean(values):.2f}")
    ax.set_title("Sharpe distribution across CPCV runs")
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


def main() -> None:
    log = logging.getLogger("evaluate")
    cfg = setup()

    features = pd.read_parquet(path(cfg, cfg["data"]["features_path"]))
    feat_cols = feature_columns(features)

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
    log.info("loaded %d runs from manifest", len(manifest))

    # Cache precomputed embeddings per encoder group (reused across many runs)
    precomputed_cache: dict[int, dict] = {}

    def get_precomputed(encoder_group: int) -> dict:
        if encoder_group in precomputed_cache:
            return precomputed_cache[encoder_group]
        enc_path = path(cfg, cfg["artefact_dir"], "encoders", f"encoder_group{encoder_group}.pt")
        encoder = load_encoder(enc_path)
        pc = build_precomputed(features, feat_cols, encoder, seq_len=env_cfg.seq_len)
        precomputed_cache[encoder_group] = pc
        return pc

    per_run = []
    curves = []
    returns_by_split: dict[int, list[np.ndarray]] = defaultdict(list)
    pooled_returns: list[float] = []

    for entry in manifest:
        model = PPO.load(entry["policy_path"], device="cpu")
        test_idx = np.concatenate(
            [np.arange(int(g[1]), int(g[2]) + 1) for g in entry["test_blocks"]]
        )
        pc = get_precomputed(int(entry["encoder_group"]))
        result = rollout_policy(model, pc, env_cfg, test_idx)
        metrics = result.metrics.asdict()
        metrics["split"] = entry["split"]
        metrics["seed"] = entry["seed"]
        per_run.append(metrics)
        curves.append(result.equity)
        returns_by_split[entry["split"]].append(result.trade_returns)
        pooled_returns.extend(result.trade_returns.tolist())
        log.info(
            "split=%d seed=%d n_trades=%d sharpe=%.2f hit=%.2f dd=%.2f",
            entry["split"],
            entry["seed"],
            result.n_trades,
            metrics["sharpe"],
            metrics["hit_rate"],
            metrics["max_drawdown"],
        )

    df_runs = pd.DataFrame(per_run)
    df_runs.to_csv(path(cfg, cfg["report_dir"], "per_run_metrics.csv"), index=False)

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

    # Transaction cost sweep (re-run evaluation at each cost level)
    cost_means = []
    cost_details = []
    costs = cfg["evaluation"]["costs_bps"]
    for c in costs:
        run_sr = []
        for entry in manifest:
            model = PPO.load(entry["policy_path"], device="cpu")
            test_idx = np.concatenate(
                [np.arange(int(g[1]), int(g[2]) + 1) for g in entry["test_blocks"]]
            )
            pc = get_precomputed(int(entry["encoder_group"]))
            r = rollout_with_cost(model, pc, env_cfg, test_idx, c)
            run_sr.append(r.metrics.sharpe)
        cost_means.append(float(np.mean(run_sr)))
        cost_details.append(dict(cost_bps=c, sharpe_mean=float(np.mean(run_sr)), sharpe_std=float(np.std(run_sr))))
        log.info("cost %.1f bps -> mean sharpe=%.2f", c, np.mean(run_sr))

    # Seed ensemble (per split, pool trade-returns across seeds)
    ensemble_sharpes = []
    for _s_idx, arrs in sorted(returns_by_split.items()):
        if not arrs:
            continue
        pooled_split = np.concatenate(arrs)
        ensemble_sharpes.append(sharpe_ratio(pooled_split, periods_per_year=252.0 / 5.0))

    # Plots
    plot_dir = path(cfg, cfg["report_dir"])
    os.makedirs(plot_dir, exist_ok=True)
    _plot_sharpe_hist(sharpes, os.path.join(plot_dir, "sharpe_hist.png"))
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

    # Markdown report
    report_lines = [
        "# Evaluation Report",
        "",
        f"- Runs evaluated: **{len(df_runs)}**",
        f"- Pooled trades: **{len(pooled)}**",
        "",
        "## Sharpe distribution",
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
    report_lines += [
        "",
        "## Seed ensemble (pooled trades per split)",
        "",
        "| Split | Sharpe |",
        "|------:|-------:|",
    ]
    for i, s in enumerate(ensemble_sharpes):
        report_lines.append(f"| {i} | {s:+.3f} |")

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
                red_flags=red_flags,
            ),
            f,
            indent=2,
        )
    log.info("wrote report + summary to %s", cfg["report_dir"])


if __name__ == "__main__":
    main()
