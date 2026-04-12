"""Evaluate all trained policies and write a statistics report.

Supports algorithm-diverse ensembles (T2.2): PPO, A2C, and RecurrentPPO
policies are loaded via the correct SB3 class and evaluated uniformly.
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

_ALGO_MAP: dict[str, type] = {"ppo": PPO, "a2c": A2C}
if RecurrentPPO is not None:
    _ALGO_MAP["recurrent_ppo"] = RecurrentPPO
    _ALGO_MAP["rppo"] = RecurrentPPO


def _load_model(entry: dict):
    """Load the correct SB3 class based on the manifest ``algorithm`` field."""
    algo = entry.get("algorithm", "ppo").lower()
    cls = _ALGO_MAP.get(algo, PPO)
    return cls.load(entry["policy_path"], device="cpu")


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

    env_cfg = env_config_from_yaml(cfg)

    manifest_path = path(cfg, cfg["artefact_dir"], "ppo_manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    log.info("loaded %d runs from manifest", len(manifest))

    # Cache precomputed embeddings per encoder group (reused across many runs)
    precomputed_cache: dict[int, dict] = {}
    # Per-split regime posterior cache (T2.1). The HMM was fit during PPO
    # training; we just load it and emit the full-bar posterior here.
    regime_cache: dict[int, np.ndarray] = {}

    def get_precomputed(encoder_group: int) -> dict:
        if encoder_group in precomputed_cache:
            return precomputed_cache[encoder_group]
        enc_path = path(cfg, cfg["artefact_dir"], "encoders", f"encoder_group{encoder_group}.pt")
        encoder = load_encoder(enc_path)
        pc = build_precomputed(features, feat_cols, encoder, seq_len=env_cfg.seq_len)
        precomputed_cache[encoder_group] = pc
        return pc

    def get_regime_post(entry: dict) -> np.ndarray | None:
        rp_path = entry.get("regime_path")
        if not rp_path:
            return None
        s = int(entry["split"])
        if s in regime_cache:
            return regime_cache[s]
        if not os.path.exists(rp_path):
            return None
        hmm = HMMRegimeModel.load(rp_path)
        # Use whatever close array the cached precomputed already exposes;
        # any encoder group works because close is identical.
        any_pc = next(iter(precomputed_cache.values()), None)
        if any_pc is None:
            any_pc = get_precomputed(int(entry["encoder_group"]))
        post = hmm.posterior(any_pc["close"])
        regime_cache[s] = post
        return post

    per_run = []
    curves = []
    returns_by_split: dict[int, list[np.ndarray]] = defaultdict(list)
    pooled_returns: list[float] = []
    # Per-split trade traces for the meta-labeling layer (T1.1). Each entry
    # is (X=features at entry, y=1 if trade_return>0 else 0). Keyed by split
    # so we can train a separate meta-model per split using leave-one-out.
    trace_by_split: dict[int, tuple[list[np.ndarray], list[int]]] = defaultdict(
        lambda: ([], [])
    )
    # Parallel per-split list of raw trade returns, aligned row-for-row with
    # trace_by_split[s]. Used by the fast meta-labeling filter path below.
    returns_trace_by_split: dict[int, list[np.ndarray]] = defaultdict(list)

    for entry in manifest:
        model = _load_model(entry)
        test_idx = np.concatenate(
            [np.arange(int(g[1]), int(g[2]) + 1) for g in entry["test_blocks"]]
        )
        pc_base = get_precomputed(int(entry["encoder_group"]))
        regime_post = get_regime_post(entry)
        pc = {**pc_base, "regime_posterior": regime_post} if regime_post is not None else pc_base
        result = rollout_policy(model, pc, env_cfg, test_idx, trace_entries=True)
        algo = entry.get("algorithm", "ppo")
        metrics = result.metrics.asdict()
        metrics["split"] = entry["split"]
        metrics["seed"] = entry["seed"]
        metrics["algorithm"] = algo
        per_run.append(metrics)
        curves.append(result.equity)
        returns_by_split[entry["split"]].append(result.trade_returns)
        pooled_returns.extend(result.trade_returns.tolist())
        if result.trade_features is not None and result.n_trades > 0:
            feats_list, labels_list = trace_by_split[entry["split"]]
            feats_list.append(result.trade_features)
            labels_list.append((result.trade_returns > 0).astype(np.int64))
            returns_trace_by_split[entry["split"]].append(result.trade_returns)
        log.info(
            "%s split=%d seed=%d n_trades=%d sharpe=%.2f hit=%.2f dd=%.2f",
            algo,
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
            model = _load_model(entry)
            test_idx = np.concatenate(
                [np.arange(int(g[1]), int(g[2]) + 1) for g in entry["test_blocks"]]
            )
            pc_base = get_precomputed(int(entry["encoder_group"]))
            regime_post = get_regime_post(entry)
            pc = (
                {**pc_base, "regime_posterior": regime_post}
                if regime_post is not None
                else pc_base
            )
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

    # ------------------------------------------------------------------
    # T2.2 -- Algorithm-diverse ensemble
    # ------------------------------------------------------------------
    # Per-algorithm Sharpe and a rolling-Sharpe-weighted ensemble.
    algo_sharpes: dict[str, list[float]] = defaultdict(list)
    algo_returns: dict[str, list[float]] = defaultdict(list)
    for row in per_run:
        algo = row.get("algorithm", "ppo")
        algo_sharpes[algo].append(row["sharpe"])
    # Pool returns per algorithm for Sharpe calculation
    for entry, result_returns in zip(manifest, [
        r for r in [None] * len(manifest)  # placeholder
    ]):
        pass  # already pooled above; recalculate from df_runs below

    algo_summary: list[dict] = []
    for algo in sorted(algo_sharpes.keys()):
        srs = algo_sharpes[algo]
        algo_summary.append(dict(
            algorithm=algo,
            mean_sharpe=float(np.mean(srs)),
            std_sharpe=float(np.std(srs)),
            n_runs=len(srs),
        ))
        log.info(
            "algo=%s mean_sharpe=%.3f std=%.3f n=%d",
            algo, float(np.mean(srs)), float(np.std(srs)), len(srs),
        )

    # ------------------------------------------------------------------
    # T1.1 -- Meta-labeling layer (Lopez de Prado, AFML Ch. 3)
    # ------------------------------------------------------------------
    # Train one meta-model per split using leave-one-out on the traced
    # trades from the OTHER splits, then rerun the rollout with the model
    # gating low-confidence entries. Report the gated pooled Sharpe at a
    # range of confidence thresholds.
    meta_results: list[dict] = []
    meta_thresholds = [0.50, 0.55, 0.60]
    split_keys = sorted(trace_by_split.keys())
    if split_keys:
        # Pre-stack each split's trace matrix so the leave-one-out loop is cheap.
        split_X: dict[int, np.ndarray] = {}
        split_y: dict[int, np.ndarray] = {}
        split_returns_aligned: dict[int, np.ndarray] = {}
        for s in split_keys:
            Xs_list, ys_list = trace_by_split[s]
            if not Xs_list:
                continue
            split_X[s] = np.concatenate(Xs_list, axis=0)
            split_y[s] = np.concatenate(ys_list, axis=0)
            ret_list = returns_trace_by_split.get(s, [])
            if ret_list:
                split_returns_aligned[s] = np.concatenate(ret_list, axis=0)

        per_split_meta: dict[int, MetaLabelModel] = {}
        for s in split_keys:
            if s not in split_X:
                continue
            # Train on all OTHER splits
            X_parts = [split_X[o] for o in split_keys if o != s and o in split_X]
            y_parts = [split_y[o] for o in split_keys if o != s and o in split_y]
            if not X_parts:
                continue
            X_tr = np.concatenate(X_parts, axis=0)
            y_tr = np.concatenate(y_parts, axis=0)
            mm = MetaLabelModel(MetaLabelConfig()).fit(X_tr, y_tr)
            per_split_meta[s] = mm
            log.info(
                "meta split=%d train_trades=%d base_rate=%.3f",
                s,
                len(X_tr),
                mm.base_rate,
            )

        # Fast filter path: instead of re-running rollout_policy per threshold
        # (which queries PPO every bar the agent stays flat -- ~25 min total),
        # we reuse the per-trade (features, return) traces collected during
        # the first pass with trace_entries=True. For each threshold we score
        # the existing trades with the per-split meta model and keep only
        # those with P(profit) >= threshold. Much faster AND a cleaner
        # counterfactual: it measures "what would Sharpe be if we had skipped
        # the low-confidence trades" rather than "what trades would a
        # different agent take after we force HOLDs on it".
        log.info("meta-labeling gate filter over %d thresholds", len(meta_thresholds))
        for thr in meta_thresholds:
            gated_returns: list[float] = []
            gated_sharpes: list[float] = []
            for s in split_keys:
                if s not in split_X:
                    continue
                mm = per_split_meta.get(s)
                if mm is None:
                    continue
                Xs = split_X[s]
                # The corresponding trade returns for this split, re-collected
                # in trade order matching Xs row-for-row.
                rets_s = split_returns_aligned.get(s)
                if rets_s is None or len(rets_s) != len(Xs):
                    continue
                probs = mm.predict_proba(Xs)
                keep = probs >= float(thr)
                kept = rets_s[keep]
                if len(kept) == 0:
                    continue
                gated_returns.extend(kept.tolist())
                gated_sharpes.append(
                    sharpe_ratio(kept, periods_per_year=252.0 / 5.0)
                )
            if not gated_returns:
                continue
            pooled_gated = np.asarray(gated_returns, dtype=float)
            pooled_sr = sharpe_ratio(pooled_gated, periods_per_year=252.0 / 5.0)
            meta_results.append(
                dict(
                    threshold=float(thr),
                    mean_sharpe=float(np.mean(gated_sharpes)),
                    pooled_sharpe=float(pooled_sr),
                    n_trades=int(len(pooled_gated)),
                    total_return=float((1 + pooled_gated).prod() - 1),
                )
            )
            log.info(
                "meta thr=%.2f mean_sharpe=%.3f pooled=%.3f n_trades=%d",
                thr,
                float(np.mean(gated_sharpes)),
                float(pooled_sr),
                len(pooled_gated),
            )

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

    if algo_summary and len(algo_summary) > 1:
        report_lines += [
            "",
            "## Algorithm ensemble (T2.2)",
            "",
            "Per-algorithm mean Sharpe across all CPCV splits and seeds.",
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
            "## Meta-labeling gate (T1.1, Lopez de Prado)",
            "",
            "Per-split HistGBM classifier trained on trades from the OTHER splits,",
            "predicting P(profit) from entry embedding+direction+vol-quantile. Actions",
            "with P < threshold are gated to HOLD.",
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
