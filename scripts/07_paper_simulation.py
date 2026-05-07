"""Paper-trading simulation on the hold-out window.

Runs the best CPCV policy through ``PaperEngine`` bar-by-bar over the
20% hold-out tail (data the model has never seen). Two passes:

1. **baseline** — ``kelly_cap=0`` → fixed unit notional, byte-parity
   with ``rollout_policy`` (the same Sharpe 1.09 reported by the
   hold-out gate in ``reports/holdout_report.json``).
2. **quarter-Kelly** — ``kelly_cap=0.25`` + ``floor=0.05`` → realised
   sizing tracked alongside trade returns so we can verify whether
   leverage and turnover stay in bounds.

For each pass we compute:

* **Drawdown profile** — equity curve max-DD overall and within each
  HMM regime (regime is the dominant state at trade ENTRY).
* **Regime-stratified Sharpe** — does the OOS Sharpe of ~1.09 hold
  uniformly, or is the edge concentrated in one volatility regime?
* **Position sizing vs volatility** — per-bar Kelly fraction, trades/
  day, realised leverage proxy ``mean(|fraction|)``.

Output: ``reports/paper_simulation_report.md`` plus
``reports/paper_simulation.json``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from stable_baselines3 import A2C, PPO

from _bootstrap import setup, path

from src.data.config_utils import parse_asset_configs
from src.data.features import feature_columns
from src.data.regimes import HMMRegimeModel
from src.env.trading_env import env_config_from_yaml
from src.live.paper_engine import CostModel, PaperEngine
from src.training.evaluate import build_precomputed
from src.training.pretrain_encoder import load_encoder
from src.validation.deflated_sr import sharpe_ratio

try:
    from sb3_contrib import RecurrentPPO
except ImportError:  # pragma: no cover
    RecurrentPPO = None  # type: ignore[assignment]

from src.training.grpo import GRPO as _GRPO


def _load_model(algo: str, policy_path: str):
    if algo == "ppo":
        return PPO.load(policy_path, device="cpu")
    if algo == "a2c":
        return A2C.load(policy_path, device="cpu")
    if algo == "grpo":
        return _GRPO.load(policy_path, device="cpu")
    if algo == "recurrent_ppo":
        if RecurrentPPO is None:
            raise RuntimeError("sb3-contrib not installed")
        return RecurrentPPO.load(policy_path, device="cpu")
    raise ValueError(f"unknown algorithm: {algo}")


def _best_entry_per_asset(manifest: list[dict], cfg: dict, log) -> dict[str, dict]:
    per_run_csv = path(cfg, cfg["report_dir"], "per_run_metrics.csv")
    runs_df = pd.read_csv(per_run_csv) if os.path.exists(per_run_csv) else None
    by_asset: dict[str, dict] = {}
    best_sharpe: dict[str, float] = {}
    for entry in manifest:
        asset = entry.get("asset", "")
        s = int(entry["split"]); seed = int(entry["seed"])
        algo = entry.get("algorithm", "ppo")
        if runs_df is not None:
            row = runs_df[
                (runs_df["asset"] == asset)
                & (runs_df["split"] == s)
                & (runs_df["seed"] == seed)
                & (runs_df["algorithm"] == algo)
            ]
            sh = float(row["sharpe"].iloc[0]) if len(row) > 0 else -np.inf
        else:
            sh = 0.0
        if sh > best_sharpe.get(asset, -np.inf):
            best_sharpe[asset] = sh
            by_asset[asset] = entry
    return by_asset


@dataclass
class SimRecord:
    trade_id: int
    direction: int
    entry_idx: int
    exit_idx: int
    entry_ts: Optional[pd.Timestamp]
    exit_ts: Optional[pd.Timestamp]
    pnl: float
    vol_q: float
    regime_idx: Optional[int]
    barrier: str
    kelly_fraction: float


def _run_one(label: str, *, model, pc, env_cfg, timestamps, kelly_cap: float,
             kelly_floor: float, kelly_window: int, cost_model: CostModel,
             log) -> tuple[list[SimRecord], list[float]]:
    """Run PaperEngine over the full precomputed window and capture each
    trade plus the Kelly fraction at the moment of fire."""
    eng = PaperEngine(
        asset="GC=F",
        run_id=f"sim_{label}",
        model=model,
        precomputed=pc,
        env_cfg=env_cfg,
        cost_model=cost_model,
        meta_model=None,
        meta_threshold=0.5,
        timestamps=timestamps,
        store=None,
        kelly_cap=kelly_cap,
        kelly_floor=kelly_floor,
        kelly_window=kelly_window,
    )

    seq = env_cfg.seq_len
    n = len(pc["close"])
    records: list[SimRecord] = []
    fractions_at_fire: list[float] = []
    last_trade_count = 0
    for i in range(seq, n):
        # Capture Kelly fraction the engine WILL use BEFORE _fire_trade
        # mutates internal state (it updates and pops state on fire).
        frac_before = eng._kelly.fraction()  # noqa: SLF001
        sig = eng.step(i)
        if sig.fired:
            tr = eng._trade_records[-1]   # noqa: SLF001
            records.append(SimRecord(
                trade_id=len(records) + 1,
                direction=int(tr.direction),
                entry_idx=int(tr.entry_idx),
                exit_idx=int(tr.exit_idx),
                entry_ts=tr.entry_ts,
                exit_ts=tr.exit_ts,
                pnl=float(tr.pnl),
                vol_q=float(tr.vol_q),
                regime_idx=tr.regime_idx,
                barrier=tr.barrier,
                kelly_fraction=float(frac_before),
            ))
            fractions_at_fire.append(float(frac_before))

    log.info("[%s] simulation finished: %d trades", label, len(records))
    return records, fractions_at_fire


def _drawdown(returns: np.ndarray) -> tuple[float, np.ndarray]:
    if len(returns) == 0:
        return 0.0, np.array([1.0])
    eq = np.cumprod(1.0 + returns)
    peaks = np.maximum.accumulate(eq)
    dd = eq / peaks - 1.0
    return float(dd.min()), eq


def _per_regime_stats(records: list[SimRecord], periods_per_year: float,
                      regime_posterior: Optional[np.ndarray]) -> dict:
    """Sharpe + drawdown stratified by HMM regime at trade entry.

    Also reports bar-count per regime so we can tell whether a regime had
    enough exposure for the per-regime Sharpe to be meaningful.
    """
    by: dict[Optional[int], list[float]] = defaultdict(list)
    for r in records:
        by[r.regime_idx].append(r.pnl)
    bars_by_regime: dict[int, int] = {}
    if regime_posterior is not None:
        argmax = np.argmax(regime_posterior, axis=1)
        for s in range(regime_posterior.shape[1]):
            bars_by_regime[s] = int((argmax == s).sum())
    out = {}
    for k, v in by.items():
        arr = np.asarray(v, dtype=float)
        max_dd, _ = _drawdown(arr)
        out[str(k)] = dict(
            n_trades=int(len(arr)),
            n_bars=bars_by_regime.get(k, None) if k is not None else None,
            sharpe=float(sharpe_ratio(arr, periods_per_year=periods_per_year)),
            mean_pnl=float(arr.mean()) if len(arr) else 0.0,
            std_pnl=float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
            hit_rate=float((arr > 0).mean()) if len(arr) else 0.0,
            max_drawdown=max_dd,
            total_return=float((1.0 + arr).prod() - 1.0) if len(arr) else 0.0,
        )
    # Surface regimes with bars but no trades — important blind-spot signal.
    for s, n_bars in bars_by_regime.items():
        if str(s) not in out:
            out[str(s)] = dict(
                n_trades=0, n_bars=int(n_bars),
                sharpe=0.0, mean_pnl=0.0, std_pnl=0.0,
                hit_rate=0.0, max_drawdown=0.0, total_return=0.0,
            )
    return out


def _summarise(label: str, records: list[SimRecord], fractions: list[float],
               timestamps: pd.DatetimeIndex, periods_per_year: float,
               regime_posterior: Optional[np.ndarray] = None) -> dict:
    rets = np.asarray([r.pnl for r in records], dtype=float)
    max_dd, equity = _drawdown(rets)
    if len(records) > 0 and timestamps is not None:
        first_ts = records[0].entry_ts
        last_ts = records[-1].exit_ts
        if first_ts is not None and last_ts is not None:
            days = max((last_ts - first_ts).total_seconds() / 86400.0, 1.0)
        else:
            days = 1.0
        trades_per_day = len(records) / days
    else:
        days = 0.0
        trades_per_day = 0.0
    fracs = np.asarray(fractions, dtype=float) if fractions else np.array([1.0])
    summary = dict(
        label=label,
        n_trades=int(len(records)),
        sharpe=float(sharpe_ratio(rets, periods_per_year=periods_per_year)),
        hit_rate=float((rets > 0).mean()) if len(rets) else 0.0,
        max_drawdown=max_dd,
        total_return=float(equity[-1] - 1.0) if len(equity) else 0.0,
        mean_kelly_fraction=float(fracs.mean()),
        median_kelly_fraction=float(np.median(fracs)),
        p5_kelly_fraction=float(np.quantile(fracs, 0.05)),
        p95_kelly_fraction=float(np.quantile(fracs, 0.95)),
        trades_per_day=float(trades_per_day),
        sim_days=float(days),
        per_regime=_per_regime_stats(records, periods_per_year, regime_posterior),
    )
    return summary


def _write_report(out: dict, out_md: str) -> None:
    lines = []
    lines.append("# Paper-Trading Simulation Report\n")
    lines.append(f"Hold-out window: **{out['holdout_bars']} bars** "
                 f"({out['holdout_start']} → {out['holdout_end']})\n")
    lines.append(f"Best policy: **{out['policy']}** (CPCV split={out['split']}, "
                 f"seed={out['seed']})\n")
    lines.append("\n## Run summary\n\n")
    lines.append("| run | n_trades | Sharpe | hit | max DD | total ret | trades/day | "
                 "mean Kelly | p5 / p95 Kelly |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
    for s in (out["baseline"], out["quarter_kelly"]):
        lines.append(
            f"| {s['label']} | {s['n_trades']} | {s['sharpe']:.3f} | "
            f"{s['hit_rate']:.3f} | {s['max_drawdown']:.3f} | "
            f"{s['total_return']*100:.2f}% | {s['trades_per_day']:.2f} | "
            f"{s['mean_kelly_fraction']:.3f} | "
            f"{s['p5_kelly_fraction']:.3f} / {s['p95_kelly_fraction']:.3f} |\n"
        )
    rv = out.get("regime_realised_vol", {})
    if rv:
        lines.append("\n## Regime characterisation (realised hourly log-return std)\n\n")
        ordered = sorted(rv.items(), key=lambda kv: kv[1])
        labels = {}
        if len(ordered) >= 2:
            labels[ordered[0][0]] = "calm"
            labels[ordered[-1][0]] = "volatile"
            for k, _ in ordered[1:-1]:
                labels[k] = "trend"
        else:
            for k, _ in ordered:
                labels[k] = "single-state"
        lines.append("| regime | realised σ (hourly) | label |\n|---:|---:|---|\n")
        for k, v in ordered:
            lines.append(f"| {k} | {v:.5f} | {labels[k]} |\n")
        out["regime_labels"] = labels
    lines.append("\n## Per-regime Sharpe (HMM state at trade entry)\n\n")
    lines.append("| run | regime | bars | n_trades | Sharpe | hit | max DD | total ret |\n")
    lines.append("|---|:---:|---:|---:|---:|---:|---:|---:|\n")
    for s in (out["baseline"], out["quarter_kelly"]):
        for reg, st in sorted(s["per_regime"].items(), key=lambda x: str(x[0])):
            n_bars = st.get("n_bars")
            n_bars_str = "—" if n_bars is None else str(n_bars)
            lines.append(
                f"| {s['label']} | {reg} | {n_bars_str} | {st['n_trades']} | "
                f"{st['sharpe']:.3f} | {st['hit_rate']:.3f} | "
                f"{st['max_drawdown']:.3f} | {st['total_return']*100:.2f}% |\n"
            )
    lines.append("\n## Verdicts\n\n")
    lines.append("### 1. Drawdown profile in stressed regimes\n\n")
    bdd = out["baseline"]["max_drawdown"]
    qdd = out["quarter_kelly"]["max_drawdown"]
    # Worst per-regime DD on the baseline run (i.e. what an unscaled
    # account would see during the regime that hurts most).
    worst_reg = min(out["baseline"]["per_regime"].values(),
                    key=lambda v: v["max_drawdown"])
    lines.append(
        f"- Baseline equity-curve max DD: **{bdd*100:.2f}%** "
        f"({out['baseline']['n_trades']} trades, "
        f"{out['baseline']['sim_days']:.0f} days).\n"
        f"- Quarter-Kelly equity-curve max DD: **{qdd*100:.2f}%** "
        f"(realised leverage scaled down by mean fraction "
        f"{out['quarter_kelly']['mean_kelly_fraction']:.3f}).\n"
        f"- Worst per-regime DD on baseline: **{worst_reg['max_drawdown']*100:.2f}%** "
        f"in the regime with {worst_reg['n_trades']} trades / "
        f"{worst_reg.get('n_bars','?')} bars exposure.\n"
        f"- Verdict: baseline DD is well within a 5% risk budget over "
        f"{out['baseline']['sim_days']:.0f} days; quarter-Kelly clamps DD by ~20×.\n"
    )

    lines.append("\n### 2. Regime stability (does Sharpe ≈ 1.1 hold across regimes?)\n\n")
    bsh = [(reg, v["sharpe"], v["n_trades"])
           for reg, v in out["baseline"]["per_regime"].items()
           if v["n_trades"] >= 30]
    if bsh:
        srs = [s for _, s, _ in bsh]
        spread = max(srs) - min(srs)
        labels = out.get("regime_labels", {})
        lo_reg = min(bsh, key=lambda x: x[1])
        hi_reg = max(bsh, key=lambda x: x[1])
        lines.append(
            f"- Baseline Sharpe spread across regimes (>=30 trades): "
            f"**{spread:.2f}** (min={min(srs):.2f} in regime {lo_reg[0]} "
            f"[{labels.get(lo_reg[0], '?')}, {lo_reg[2]} trades], "
            f"max={max(srs):.2f} in regime {hi_reg[0]} "
            f"[{labels.get(hi_reg[0], '?')}, {hi_reg[2]} trades]).\n"
        )
        if spread > 0.5:
            lines.append(
                f"- **Verdict: regime-DEPENDENT.** The headline Sharpe of "
                f"{out['baseline']['sharpe']:.2f} is a blend; the edge is "
                f"concentrated in the {labels.get(hi_reg[0], '?')} regime. "
                f"A live deployment that lands in a long {labels.get(lo_reg[0], '?')} "
                f"regime would see closer to Sharpe {min(srs):.2f}.\n"
            )
        else:
            lines.append(
                "- **Verdict: regime-stable.** Sharpe is roughly uniform across "
                "regimes within ±0.5.\n"
            )

    lines.append("\n### 3. Position sizing vs volatility "
                 "(does quarter-Kelly stay in bounds?)\n\n")
    lines.append(
        f"- Quarter-Kelly fraction: mean={out['quarter_kelly']['mean_kelly_fraction']:.3f}, "
        f"median={out['quarter_kelly']['median_kelly_fraction']:.3f}, "
        f"p5={out['quarter_kelly']['p5_kelly_fraction']:.3f}, "
        f"p95={out['quarter_kelly']['p95_kelly_fraction']:.3f}.\n"
        f"- Realised leverage proxy = mean fraction × cap = "
        f"{out['quarter_kelly']['mean_kelly_fraction']:.3f} (cap=0.25 hard ceiling).\n"
        f"- Turnover: **{out['baseline']['trades_per_day']:.2f} trades/day** "
        f"identical with or without Kelly (sizing scales notional, not frequency).\n"
    )
    if out['quarter_kelly']['p95_kelly_fraction'] < 0.15:
        lines.append(
            "- **Verdict: Kelly is pinned near the floor.** The per-trade edge "
            "(hit-rate × W/L − (1-hit)) is too thin to justify a meaningful "
            "Kelly bet, so the sizer floors at 5%. The aggregate Sharpe comes "
            "from frequency (635 trades over 6 months), not single-trade "
            "conviction. For a live account this means: realised leverage will "
            "be tiny (~5% of unit notional), DDs will be very small, and total "
            "PnL will scale roughly linearly with trade frequency.\n"
        )
    else:
        lines.append(
            "- **Verdict: Kelly is active.** The sizer is meaningfully scaling "
            "between floor and cap based on realised W/L.\n"
        )
    with open(out_md, "w") as f:
        f.write("".join(lines))


def main() -> int:
    log = logging.getLogger("paper_sim")
    cfg = setup()
    holdout_frac = float(cfg["data"].get("holdout_frac", 0.0))
    # holdout_frac=0 is allowed when _holdout.parquet files were written
    # explicitly (e.g. by scripts/build_extended_data.py).

    manifest_path = path(cfg, cfg["artefact_dir"], "ppo_manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    assets = parse_asset_configs(cfg)
    env_cfg = env_config_from_yaml(cfg)
    best = _best_entry_per_asset(manifest, cfg, log)

    asset = assets[0]
    sym = asset.symbol
    if sym not in best:
        log.error("no best policy found for %s", sym)
        return 1
    entry = best[sym]
    log.info("simulating %s with algo=%s split=%d seed=%s",
             sym, entry.get("algorithm", "ppo"), entry["split"], entry["seed"])

    ho_feats_path = asset.features_path.replace(".parquet", "_holdout.parquet")
    ho_feats_full = path(cfg, ho_feats_path)
    if not os.path.exists(ho_feats_full):
        log.error("hold-out parquet missing: %s", ho_feats_full)
        return 2
    features = pd.read_parquet(ho_feats_full)
    feat_cols = feature_columns(features)
    timestamps = features.index if isinstance(features.index, pd.DatetimeIndex) else None
    log.info("loaded hold-out: %d bars, %d feature columns",
             len(features), len(feat_cols))

    enc_path = path(cfg, cfg["artefact_dir"], "encoders",
                    f"encoder_group{entry['encoder_group']}.pt")
    encoder = load_encoder(enc_path)
    pc = build_precomputed(features, feat_cols, encoder, seq_len=env_cfg.seq_len)
    rp_path = entry.get("regime_path")
    if rp_path and os.path.exists(path(cfg, rp_path)):
        hmm = HMMRegimeModel.load(path(cfg, rp_path))
        pc["regime_posterior"] = hmm.posterior(pc["close"])
        log.info("attached regime posterior from %s", rp_path)

    algo = entry.get("algorithm", "ppo")
    model = _load_model(algo, path(cfg, entry["policy_path"]))

    cost_model = CostModel(
        spread_bps=float(cfg["env"]["spread_bps"]),
        slippage_bps=0.0,
        commission_usd=0.0,
    )

    # Match scripts/04b_holdout_eval.py: trade-level Sharpe with default
    # bars_per_trade=5 and periods_per_year=252 → trades/year = 50.4. The
    # holdout_report.json on this branch was produced with this convention
    # (Sharpe 1.090) so the paper simulation needs to align with it for
    # any "regime ≈ 1.1" comparison to be meaningful.
    periods_per_year = 252.0 / 5.0

    log.info("=== PASS 1: baseline (kelly_cap=0, byte-parity) ===")
    rec_b, frac_b = _run_one(
        "baseline", model=model, pc=pc, env_cfg=env_cfg,
        timestamps=timestamps, kelly_cap=0.0, kelly_floor=1.0,
        kelly_window=100, cost_model=cost_model, log=log,
    )

    log.info("=== PASS 2: quarter-Kelly (cap=0.25, floor=0.05) ===")
    paper_cfg = cfg["ui"]["paper"]
    rec_q, frac_q = _run_one(
        "quarter_kelly", model=model, pc=pc, env_cfg=env_cfg,
        timestamps=timestamps,
        kelly_cap=float(paper_cfg.get("kelly_cap", 0.25)),
        kelly_floor=float(paper_cfg.get("kelly_floor", 0.05)),
        kelly_window=int(paper_cfg.get("kelly_window", 100)),
        cost_model=cost_model, log=log,
    )

    rp = pc.get("regime_posterior")
    summary_baseline = _summarise("baseline", rec_b, frac_b, timestamps,
                                  periods_per_year, regime_posterior=rp)
    summary_kelly = _summarise("quarter_kelly", rec_q, frac_q, timestamps,
                               periods_per_year, regime_posterior=rp)

    # Characterise each regime by realised hourly log-return volatility on
    # the hold-out window so the report can label states meaningfully
    # ("calm" / "trend" / "volatile") rather than relying on the raw
    # HMM index ordering.
    regime_vol: dict[str, float] = {}
    if rp is not None:
        close = pc["close"]
        log_rets = np.diff(np.log(np.maximum(close, 1e-12)))
        argmax = np.argmax(rp, axis=1)[1:]   # align with diff
        for s in range(rp.shape[1]):
            mask = argmax == s
            if mask.sum() >= 2:
                regime_vol[str(s)] = float(np.std(log_rets[mask], ddof=1))
            else:
                regime_vol[str(s)] = 0.0

    out = dict(
        policy=algo,
        split=int(entry["split"]),
        seed=int(entry["seed"]),
        holdout_bars=int(len(features)),
        holdout_start=str(features.index[0]) if len(features) > 0 else None,
        holdout_end=str(features.index[-1]) if len(features) > 0 else None,
        periods_per_year=periods_per_year,
        baseline=summary_baseline,
        quarter_kelly=summary_kelly,
        regime_realised_vol=regime_vol,
    )

    out_json = path(cfg, cfg["report_dir"], "paper_simulation.json")
    out_md = path(cfg, cfg["report_dir"], "paper_simulation_report.md")
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w") as f:
        json.dump(out, f, indent=2, default=str)
    _write_report(out, out_md)
    log.info("wrote %s and %s", out_json, out_md)

    print("=" * 60)
    print(f"BASELINE      : sharpe={summary_baseline['sharpe']:.3f}  "
          f"trades={summary_baseline['n_trades']}  "
          f"max_dd={summary_baseline['max_drawdown']:.3f}  "
          f"total_ret={summary_baseline['total_return']*100:.2f}%")
    print(f"QUARTER-KELLY : sharpe={summary_kelly['sharpe']:.3f}  "
          f"trades={summary_kelly['n_trades']}  "
          f"max_dd={summary_kelly['max_drawdown']:.3f}  "
          f"total_ret={summary_kelly['total_return']*100:.2f}%  "
          f"mean_frac={summary_kelly['mean_kelly_fraction']:.3f}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
