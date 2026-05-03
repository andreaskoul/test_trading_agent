"""Multi-window backtest action (Phase R).

Replays the best-policy from the manifest over N independent random
6-month windows of pre-training market data. Reports per-window and
aggregate PnL on $100k notional.

Why: existing evaluators (04_evaluate.py, 04b_holdout_eval.py,
07_paper_simulation.py) all run on training or hold-out data the policy
has either trained on or been gated against. To honestly compare two
iterations of the agent we need a corpus the policy has *never seen*,
sliced into many windows so we get a distribution of PnL rather than a
single-point estimate.

Usage::

    # Local: use existing data/raw/gold_pretraining.parquet
    python scripts/08_backtest_windows.py

    # All knobs:
    python scripts/08_backtest_windows.py \\
        --n-windows 20 --window-bars 1100 \\
        --notional 100000 --seed 42 --asset GC=F \\
        --branch-tag main \\
        --commit-sha abcd1234

Outputs:
    reports/backtest/<sha>.json   (machine-readable)
    reports/backtest/<sha>.md     (markdown summary table)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import os
import sys

import numpy as np
import pandas as pd

from _bootstrap import path, setup

from src.data.config_utils import parse_asset_configs
from src.data.features import build_features, feature_columns
from src.env.trading_env import env_config_from_yaml
from src.training.evaluate import build_precomputed, rollout_policy
from src.training.pretrain_encoder import load_encoder
from src.validation.bootstrap import block_bootstrap_sharpe, bootstrap_pvalue_sharpe
from src.validation.deflated_sr import deflated_sharpe_ratio

try:
    from stable_baselines3 import PPO, A2C
except ImportError:    # pragma: no cover
    PPO = A2C = None    # type: ignore[assignment]

log = logging.getLogger("backtest_windows")

# ---------------------------------------------------------------------------
# Training-corpus ranges (hard-coded per Phase R audit; if you re-train,
# update these with the new manifest's date span).
# ---------------------------------------------------------------------------
TRAINING_RANGES = [
    ("2023-07-17T00:00Z", "2025-09-09T00:00Z"),    # CPCV training
    ("2025-09-09T00:00Z", "2026-03-24T00:00Z"),    # held-out tail (also OOS to policy
                                                    # but used as deployment gate, so excluded)
]


def _select_best_entry(manifest: list[dict], asset: str) -> dict:
    candidates = [e for e in manifest if e.get("asset") == asset]
    if not candidates:
        raise RuntimeError(f"no manifest entry for {asset}")
    candidates.sort(key=lambda e: float(e.get("sharpe", 0.0)), reverse=True)
    return candidates[0]


def _load_policy(cfg: dict, entry: dict):
    algo = entry.get("algorithm", "ppo").lower()
    cls = PPO if algo in ("ppo", "grpo") else A2C
    if cls is None:
        raise RuntimeError("stable_baselines3 not installed")
    p = entry["policy_path"]
    if not os.path.isabs(p):
        p = path(cfg, p)
    return cls.load(p, device="cpu")


def _filter_pretraining(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Drop bars that overlap the training or hold-out corpus."""
    keep = pd.Series(True, index=ohlcv.index)
    for start_iso, end_iso in TRAINING_RANGES:
        start = pd.Timestamp(start_iso)
        end = pd.Timestamp(end_iso)
        keep &= ~((ohlcv.index >= start) & (ohlcv.index < end))
    return ohlcv[keep]


def _sample_windows(
    n_bars_total: int, window_bars: int, n_windows: int, warmup_bars: int,
    seed: int,
) -> list[int]:
    """Sample N random window starts. Each starts where features stabilise
    (after ``warmup_bars``) and ends within bounds (``+ window_bars``)."""
    earliest = warmup_bars
    latest = n_bars_total - window_bars - 1
    if latest <= earliest:
        raise RuntimeError(
            f"corpus too short: {n_bars_total} bars; need at least "
            f"{warmup_bars + window_bars + 1}"
        )
    rng = np.random.default_rng(seed)
    return sorted(rng.integers(earliest, latest, size=n_windows).tolist())


def _per_window_metrics(
    rets: np.ndarray, equity: np.ndarray, notional: float,
    block: int = 20, n_resamples: int = 500,
) -> dict:
    """Per-window stats. ``n_resamples`` lower than offline default to
    keep the 20-window run within Actions free-tier minutes."""
    n = int(len(rets))
    if n == 0:
        return {
            "n_trades": 0, "sharpe": 0.0, "total_return_frac": 0.0,
            "total_pnl_usd": 0.0, "max_dd_frac": 0.0, "max_dd_usd": 0.0,
            "hit_rate": 0.0, "boot_p": 1.0, "boot_lo": 0.0, "boot_hi": 0.0,
            "dsr": 0.5,
        }
    total_ret = float(equity[-1] - 1.0)
    peak = np.maximum.accumulate(equity)
    max_dd = float(((equity - peak) / peak).min())
    std = float(rets.std(ddof=1)) if n > 1 else 0.0
    sr = float(rets.mean() / std) if std > 1e-12 else 0.0

    if n >= block:
        ci = block_bootstrap_sharpe(rets, block=block, n_resamples=n_resamples)
        pval = bootstrap_pvalue_sharpe(rets, block=block, n_resamples=n_resamples)
    else:
        ci = type("CI", (), {"lo": 0.0, "hi": 0.0})()
        pval = 1.0

    dsr = float(deflated_sharpe_ratio(rets, n_trials=1).deflated_sharpe)

    return {
        "n_trades": n,
        "sharpe": sr,
        "total_return_frac": total_ret,
        "total_pnl_usd": notional * total_ret,
        "max_dd_frac": max_dd,
        "max_dd_usd": notional * max_dd,
        "hit_rate": float((rets > 0).mean()),
        "boot_p": float(pval),
        "boot_lo": float(ci.lo),
        "boot_hi": float(ci.hi),
        "dsr": dsr,
    }


def _aggregate(per_window: list[dict], notional: float) -> dict:
    pnls = np.array([w["total_pnl_usd"] for w in per_window], dtype=float)
    sharpes = np.array([w["sharpe"] for w in per_window], dtype=float)
    n_trades = int(np.sum([w["n_trades"] for w in per_window]))
    return {
        "n_windows": len(per_window),
        "mean_pnl_usd": float(pnls.mean()) if pnls.size else 0.0,
        "median_pnl_usd": float(np.median(pnls)) if pnls.size else 0.0,
        "std_pnl_usd": float(pnls.std(ddof=1)) if pnls.size > 1 else 0.0,
        "min_pnl_usd": float(pnls.min()) if pnls.size else 0.0,
        "max_pnl_usd": float(pnls.max()) if pnls.size else 0.0,
        "pct_profitable_windows": float((pnls > 0).mean()) if pnls.size else 0.0,
        "mean_sharpe": float(sharpes.mean()) if sharpes.size else 0.0,
        "total_trades_across_windows": n_trades,
    }


def _windows_overlap_pct(starts: list[int], window_bars: int) -> float:
    """Average pairwise % overlap of the sampled windows."""
    n = len(starts)
    if n < 2:
        return 0.0
    pcts = []
    for i in range(n):
        for j in range(i + 1, n):
            a_start, b_start = starts[i], starts[j]
            inter = max(0, min(a_start + window_bars, b_start + window_bars)
                        - max(a_start, b_start))
            pcts.append(inter / window_bars)
    return float(np.mean(pcts))


def _write_markdown(
    out_path: str, summary: dict, per_window: list[dict], meta: dict,
) -> None:
    lines = [
        f"# Backtest report — {meta['branch_tag']} @ {meta['commit_sha'][:8]}",
        "",
        f"- Asset: **{meta['asset']}**",
        f"- Notional: **${meta['notional']:,.0f}**",
        f"- Windows: **{meta['n_windows']}** × **{meta['window_bars']}** bars (~6 months at 60m)",
        f"- Random seed: `{meta['seed']}`",
        f"- Mean window-overlap: **{meta['mean_overlap_pct']:.0%}**  *(if high: pre-training corpus is short — see plan caveats)*",
        f"- Generated: {meta['generated_at']}",
        "",
        "## Aggregate",
        "",
        f"| Metric | Value |",
        f"|---|---:|",
        f"| Mean PnL / window | **${summary['mean_pnl_usd']:+,.2f}** |",
        f"| Median PnL / window | ${summary['median_pnl_usd']:+,.2f} |",
        f"| Std PnL / window | ${summary['std_pnl_usd']:,.2f} |",
        f"| Worst window | ${summary['min_pnl_usd']:+,.2f} |",
        f"| Best window | ${summary['max_pnl_usd']:+,.2f} |",
        f"| Profitable windows | {summary['pct_profitable_windows']:.0%} |",
        f"| Mean per-window Sharpe | {summary['mean_sharpe']:+.3f} |",
        f"| Total trades (sum across windows) | {summary['total_trades_across_windows']} |",
        "",
        "## Per-window detail",
        "",
        "| # | window start | window end | trades | Sharpe | PnL ($) | DD ($) | hit | boot p | DSR |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for i, w in enumerate(per_window, start=1):
        lines.append(
            f"| {i} | {w['window_start_ts']} | {w['window_end_ts']} "
            f"| {w['n_trades']} | {w['sharpe']:+.3f} "
            f"| {w['total_pnl_usd']:+,.2f} | {w['max_dd_usd']:+,.2f} "
            f"| {w['hit_rate']:.2f} | {w['boot_p']:.4f} | {w['dsr']:.3f} |"
        )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", default="GC=F")
    parser.add_argument("--n-windows", type=int, default=20)
    parser.add_argument("--window-bars", type=int, default=1100,
                        help="~6 months at 60m bars including overnight gaps")
    parser.add_argument("--notional", type=float, default=100_000.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bootstrap-resamples", type=int, default=500,
                        help="lower than offline default to keep CI runtime bounded")
    parser.add_argument("--data-path", default="data/raw/gold_pretraining.parquet",
                        help="parquet of pre-training OHLCV")
    parser.add_argument("--out-dir", default="reports/backtest")
    parser.add_argument("--branch-tag", default=os.environ.get("GITHUB_REF_NAME", "local"))
    parser.add_argument("--commit-sha", default=os.environ.get("GITHUB_SHA", "local"))
    args = parser.parse_args()

    cfg = setup()

    # Asset config
    asset_cfgs = parse_asset_configs(cfg)
    asset = next((a for a in asset_cfgs if a.symbol == args.asset), None)
    if asset is None:
        log.error("asset %s not in config", args.asset)
        return 2

    # Load pre-training OHLCV.
    data_path = path(cfg, args.data_path)
    if not os.path.exists(data_path):
        log.error("pre-training data missing: %s", data_path)
        log.error("run: python scripts/fetch_pretraining_data.py")
        return 2
    ohlcv = pd.read_parquet(data_path)
    if ohlcv.index.tz is None:
        ohlcv.index = ohlcv.index.tz_localize("UTC")
    log.info("loaded %d bars from %s [%s -> %s]",
             len(ohlcv), data_path,
             ohlcv.index[0].isoformat(), ohlcv.index[-1].isoformat())

    # Drop training/hold-out overlap.
    n_before = len(ohlcv)
    ohlcv = _filter_pretraining(ohlcv)
    log.info("after filtering training/hold-out overlap: %d -> %d bars",
             n_before, len(ohlcv))

    # Compute features once on the full pre-training corpus; window-slice indices.
    warmup = int(cfg.get("features", {}).get("warmup_bars", 252))
    zscore = int(cfg.get("features", {}).get("zscore_window", 252))
    # Load cached macro parquets if present so feature columns match training.
    macro_data: dict = {}
    for sym in cfg.get("data", {}).get("macro_symbols", []) or []:
        m_path = path(cfg, "data/raw", f"macro_{sym.lstrip('^').replace('=','')}.parquet")
        if os.path.exists(m_path):
            macro_data[sym] = pd.read_parquet(m_path)
    feats = build_features(ohlcv, warmup_bars=warmup, zscore_window=zscore,
                           macro_data=macro_data or None)
    if len(feats) == 0:
        log.error("no features after warmup; need more bars (have %d, warmup=%d)",
                  len(ohlcv), warmup + zscore)
        return 2

    # Align to the canonical training feature column set so the encoder's
    # input dimension matches. Missing columns are filled with 0 (rare —
    # macro merge usually covers everything).
    train_feats_path = path(cfg, asset.features_path)
    if os.path.exists(train_feats_path):
        train_feats = pd.read_parquet(train_feats_path)
        canonical_cols = feature_columns(train_feats)
        for col in canonical_cols:
            if col not in feats.columns:
                feats[col] = 0.0
        # Keep close + atr (required by build_precomputed) and the canonical features.
        keep = list(dict.fromkeys(["close", "atr"] + canonical_cols))
        feats = feats[keep]
        log.info("features aligned to %d training cols", len(canonical_cols))
    log.info("features: %d rows × %d cols", len(feats), len(feature_columns(feats)))

    # Sample window starts (indices into feats, which is already past warmup).
    starts = _sample_windows(
        n_bars_total=len(feats), window_bars=args.window_bars,
        n_windows=args.n_windows, warmup_bars=0, seed=args.seed,
    )
    overlap_pct = _windows_overlap_pct(starts, args.window_bars)
    log.info("sampled %d window starts; mean pairwise overlap %.0f%%",
             len(starts), overlap_pct * 100)

    # Load policy + encoder once.
    manifest_path = path(cfg, cfg["artefact_dir"], "ppo_manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    entry = _select_best_entry(manifest, asset.symbol)
    enc_path = path(cfg, cfg["artefact_dir"], "encoders",
                    f"encoder_group{entry['encoder_group']}.pt")
    encoder = load_encoder(enc_path)
    model = _load_policy(cfg, entry)
    env_cfg = env_config_from_yaml(cfg)

    # Optional regime posterior — required when the policy was trained with
    # regime conditioning (obs shape includes appended regime probs).
    regime_post = None
    rp_rel = entry.get("regime_path") or "artefacts/regimes/hmm_gc_60m.pkl"
    rp_abs = path(cfg, rp_rel)
    if os.path.exists(rp_abs):
        try:
            from src.data.regimes import HMMRegimeModel
            hmm = HMMRegimeModel.load(rp_abs)
            close_arr = feats["close"].to_numpy(np.float64)
            regime_post = hmm.posterior(close_arr)
            log.info("regime posterior: shape %s", regime_post.shape)
        except ImportError as exc:
            log.warning("hmmlearn not installed; regime conditioning disabled (%s)", exc)
        except Exception as exc:
            log.warning("regime model load failed: %s", exc)

    # Build precomputed once over the full corpus; per-window slicing via test_idx.
    feat_cols = feature_columns(feats)
    pc = build_precomputed(feats, feat_cols, encoder, seq_len=env_cfg.seq_len,
                           regime_posterior=regime_post)

    # Per-window backtest.
    per_window: list[dict] = []
    for i, start in enumerate(starts, start=1):
        end = start + args.window_bars
        test_idx = np.arange(start, end, dtype=np.int64)
        log.info("[%d/%d] window bars %d..%d", i, len(starts), start, end)
        try:
            res = rollout_policy(model, pc, env_cfg, test_idx)
        except Exception as exc:
            log.warning("window %d/%d failed: %s", i, len(starts), exc)
            continue
        m = _per_window_metrics(
            res.trade_returns, res.equity, args.notional,
            n_resamples=args.bootstrap_resamples,
        )
        m["window_start_ts"] = str(feats.index[start])
        m["window_end_ts"] = str(feats.index[min(end - 1, len(feats) - 1)])
        per_window.append(m)

    if not per_window:
        log.error("no successful windows; aborting")
        return 2

    summary = _aggregate(per_window, args.notional)
    now_iso = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    meta = {
        "asset": args.asset, "notional": args.notional,
        "n_windows": len(per_window), "window_bars": args.window_bars,
        "seed": args.seed, "branch_tag": args.branch_tag,
        "commit_sha": args.commit_sha, "generated_at": now_iso,
        "mean_overlap_pct": overlap_pct,
    }
    out = {"meta": meta, "summary": summary, "windows": per_window}

    out_dir = path(cfg, args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    sha_short = (args.commit_sha or "local")[:12]
    json_path = os.path.join(out_dir, f"{sha_short}.json")
    md_path = os.path.join(out_dir, f"{sha_short}.md")

    with open(json_path, "w") as f:
        json.dump(out, f, indent=2)
    _write_markdown(md_path, summary, per_window, meta)

    log.info("wrote %s and %s", json_path, md_path)
    n_profit = int(summary["pct_profitable_windows"] * len(per_window))
    msg = (f"AGGREGATE: mean PnL = ${summary['mean_pnl_usd']:+,.2f} / window | "
           f"{n_profit}/{len(per_window)} profitable | "
           f"mean Sharpe {summary['mean_sharpe']:+.3f}")
    log.info(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
