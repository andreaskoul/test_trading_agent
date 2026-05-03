"""Phase S: smoke test for the historical data fetcher.

No network: uses the --source file path so we can verify the loader,
slicer, and parquet writer end-to-end without depending on Stooq or
yfinance reachability.

Invoke explicitly::

    python tests/test_fetch_historical_data.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _synthetic_parquet(out_path: str, n: int = 5000) -> None:
    """1h bars 2018-01-01 onwards — covers the requested 2016-01-01 start
    so slicing produces at least a non-empty intersection."""
    rng = np.random.default_rng(0)
    rets = 0.0002 + 0.01 * rng.standard_normal(n)
    close = 1500 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({
        "open": close, "high": close * 1.001, "low": close * 0.999,
        "close": close,
        "volume": np.abs(rng.normal(1e5, 1e4, n)).astype(np.int64),
    }, index=pd.date_range("2018-01-01", periods=n, freq="h", tz="UTC"))
    df.to_parquet(out_path)


def test_fetch_historical_file_source():
    """--source file should round-trip a parquet through the slicer."""
    with tempfile.TemporaryDirectory() as tmp:
        in_path = os.path.join(tmp, "synth.parquet")
        out_dir = os.path.join(tmp, "out")
        _synthetic_parquet(in_path, n=5000)

        env = {**os.environ, "PYTHONPATH": ROOT}
        r = subprocess.run(
            [
                sys.executable, "scripts/fetch_historical_data.py",
                "--asset", "GC=F",
                "--interval", "60m",
                "--start", "2018-06-01",
                "--end", "2018-09-01",
                "--source", "file",
                "--file-path", in_path,
                "--out-dir", out_dir,
                "--name-suffix", "_test",
                "--macros", "",
            ],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=60,
        )
        print(r.stdout[-1500:] if r.stdout else "")
        print(r.stderr[-1500:] if r.stderr else "", file=sys.stderr)
        assert r.returncode == 0, f"exit {r.returncode}\n{r.stderr}"

        produced = os.path.join(out_dir, "gcf_60m_test.parquet")
        assert os.path.exists(produced), f"missing {produced}"
        out_df = pd.read_parquet(produced)
        # Slicing should respect [start, end].
        assert out_df.index.min() >= pd.Timestamp("2018-06-01", tz="UTC")
        assert out_df.index.max() <= pd.Timestamp("2018-09-01", tz="UTC")
        assert len(out_df) > 0
        assert list(out_df.columns) == ["open", "high", "low", "close", "volume"]


if __name__ == "__main__":
    try:
        test_fetch_historical_file_source()
        print("PASS test_fetch_historical_file_source")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"FAIL test_fetch_historical_file_source: {exc}")
        sys.exit(1)
