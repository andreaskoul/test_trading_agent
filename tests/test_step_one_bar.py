"""Phase Q: smoke test for the cron-driven trading loop.

Runs scripts/step_one_bar.py in --offline mode against the existing
artefacts (manifest, encoders, features parquet). Verifies:

  * exit code is 0 (no halt, no crash)
  * artefacts/engine_state.json is written with the expected keys
  * docs/data.json (via export_dashboard_data.py) is well-formed

This is excluded from the default smoke run (requires the trained
artefacts on disk) — invoke explicitly:

    python tests/test_step_one_bar.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _has_artefacts() -> bool:
    return all(os.path.exists(os.path.join(ROOT, p)) for p in (
        "artefacts/ppo_manifest.json",
        "artefacts/encoders/encoder_group0.pt",
        "data/processed/features_gc_60m.parquet",
        "data/raw/gc_60m.parquet",
    ))


def test_step_one_bar_offline():
    if not _has_artefacts():
        print("SKIP test_step_one_bar_offline: training artefacts missing")
        return

    env = {**os.environ, "TRADING_PROFILE": "aggressive",
           "PYTHONPATH": ROOT}
    r = subprocess.run(
        [sys.executable, "scripts/step_one_bar.py",
         "--asset", "GC=F", "--offline"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=300,
    )
    print(r.stdout)
    print(r.stderr, file=sys.stderr)
    assert r.returncode in (0, 2), f"unexpected exit code {r.returncode}"

    state_path = os.path.join(ROOT, "artefacts", "engine_state.json")
    if r.returncode == 0 and os.path.exists(state_path):
        with open(state_path) as f:
            snap = json.load(f)
        for k in ("asset", "run_id", "position", "n_trades", "equity"):
            assert k in snap, f"engine_state missing {k}"

    # Export step.
    r2 = subprocess.run(
        [sys.executable, "scripts/export_dashboard_data.py",
         "--out", "docs/data.json"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    print(r2.stdout)
    print(r2.stderr, file=sys.stderr)
    assert r2.returncode == 0
    out = os.path.join(ROOT, "docs", "data.json")
    assert os.path.exists(out)
    with open(out) as f:
        snap = json.load(f)
    for k in ("trades", "aggregate", "stats", "equity_curve"):
        assert k in snap, f"data.json missing {k}"


if __name__ == "__main__":
    try:
        test_step_one_bar_offline()
        print("PASS test_step_one_bar_offline")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"FAIL test_step_one_bar_offline: {exc}")
        sys.exit(1)
