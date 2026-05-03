"""Phase R: smoke test for the multi-window backtest action.

Skips when the trained artefacts (manifest + encoders + features) are
absent, since this exercises the full end-to-end pipeline. When they're
available, runs scripts/08_backtest_windows.py with tiny inputs against
synthetic pre-training data and asserts the JSON + markdown reports are
well-formed.

Invoke explicitly::

    python tests/test_backtest_windows.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _has_artefacts() -> bool:
    return all(os.path.exists(os.path.join(ROOT, p)) for p in (
        "artefacts/ppo_manifest.json",
        "artefacts/encoders/encoder_group0.pt",
    ))


def _synthetic_pretraining_parquet(out_path: str, n_bars: int = 3000) -> None:
    """Fabricate a parquet that LOOKS like Stooq output: 60m bars
    spanning a range that doesn't overlap training (2023-07 → 2026-03)."""
    rng = np.random.default_rng(0)
    rets = 0.0002 + 0.01 * rng.standard_normal(n_bars)
    close = 1500 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({
        "open": close, "high": close * 1.001, "low": close * 0.999,
        "close": close,
        "volume": np.abs(rng.normal(1e5, 1e4, n_bars)).astype(np.int64),
    }, index=pd.date_range("2022-01-01", periods=n_bars, freq="h", tz="UTC"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_parquet(out_path)


def test_backtest_windows_smoke():
    if not _has_artefacts():
        print("SKIP test_backtest_windows_smoke: training artefacts missing")
        return

    with tempfile.TemporaryDirectory() as tmp:
        # Synthetic pre-training data in a tmp parquet (avoid clobbering
        # any real one already on disk).
        synth_parquet = os.path.join(tmp, "gold_pretraining_synth.parquet")
        _synthetic_pretraining_parquet(synth_parquet, n_bars=3000)

        out_dir = os.path.join(tmp, "reports", "backtest")
        env = {
            **os.environ,
            "TRADING_PROFILE": "aggressive",
            "PYTHONPATH": ROOT,
        }
        # Tiny inputs for speed: 3 windows × 200 bars × 50 bootstrap resamples.
        r = subprocess.run(
            [
                sys.executable, "scripts/08_backtest_windows.py",
                "--asset", "GC=F",
                "--n-windows", "3",
                "--window-bars", "200",
                "--bootstrap-resamples", "50",
                "--notional", "100000",
                "--seed", "7",
                "--data-path", synth_parquet,
                "--out-dir", out_dir,
                "--branch-tag", "smoke-test",
                "--commit-sha", "smoke0000",
            ],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=600,
        )
        print(r.stdout[-2000:] if r.stdout else "")
        print(r.stderr[-2000:] if r.stderr else "", file=sys.stderr)
        assert r.returncode == 0, f"exit {r.returncode}\n{r.stderr}"

        json_path = os.path.join(out_dir, "smoke0000.json")
        md_path = os.path.join(out_dir, "smoke0000.md")
        assert os.path.exists(json_path), f"missing {json_path}"
        assert os.path.exists(md_path), f"missing {md_path}"

        with open(json_path) as f:
            report = json.load(f)
        assert set(report.keys()) >= {"meta", "summary", "windows"}
        assert report["meta"]["n_windows"] == 3
        assert report["meta"]["notional"] == 100_000
        assert len(report["windows"]) == 3
        for w in report["windows"]:
            for k in ("n_trades", "sharpe", "total_pnl_usd",
                       "max_dd_usd", "boot_p", "dsr",
                       "window_start_ts", "window_end_ts"):
                assert k in w, f"window missing {k}: {w}"
            assert np.isfinite(w["total_pnl_usd"])

        for k in ("mean_pnl_usd", "median_pnl_usd", "pct_profitable_windows",
                   "mean_sharpe", "n_windows"):
            assert k in report["summary"]
        # Markdown should be non-trivial.
        with open(md_path) as f:
            md = f.read()
        assert "Aggregate" in md and "Per-window detail" in md


if __name__ == "__main__":
    try:
        test_backtest_windows_smoke()
        print("PASS test_backtest_windows_smoke")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"FAIL test_backtest_windows_smoke: {exc}")
        sys.exit(1)
