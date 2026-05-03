"""Side-by-side comparison of multiple backtest reports (Phase R).

Reads N JSON reports produced by ``scripts/08_backtest_windows.py`` and
prints / writes a markdown table comparing aggregate PnL, Sharpe, profit
rate and worst-case PnL across iterations.

Usage::

    # Compare two reports
    python scripts/compare_backtests.py reports/backtest/abc1234.json reports/backtest/def5678.json

    # Compare all reports on the backtest_history branch (after `git fetch`):
    git checkout backtest_history -- reports/backtest/
    python scripts/compare_backtests.py reports/backtest/*.json --out reports/backtest/compare.md

"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys


def _load(json_path: str) -> dict:
    with open(json_path) as f:
        return json.load(f)


def _row(report: dict) -> dict:
    meta = report.get("meta", {})
    summary = report.get("summary", {})
    return {
        "label": f"{meta.get('branch_tag', '?')}@{(meta.get('commit_sha') or '')[:8]}",
        "generated": meta.get("generated_at", ""),
        "n_windows": int(summary.get("n_windows", 0)),
        "mean_pnl_usd": float(summary.get("mean_pnl_usd", 0.0)),
        "median_pnl_usd": float(summary.get("median_pnl_usd", 0.0)),
        "min_pnl_usd": float(summary.get("min_pnl_usd", 0.0)),
        "max_pnl_usd": float(summary.get("max_pnl_usd", 0.0)),
        "pct_profitable": float(summary.get("pct_profitable_windows", 0.0)),
        "mean_sharpe": float(summary.get("mean_sharpe", 0.0)),
        "n_trades": int(summary.get("total_trades_across_windows", 0)),
    }


def _render(rows: list[dict]) -> str:
    if not rows:
        return "*(no reports to compare)*\n"
    # Sort newest first.
    rows = sorted(rows, key=lambda r: r["generated"], reverse=True)
    base = rows[-1]    # oldest = baseline for delta
    header = (
        "| iteration | generated | windows | mean PnL ($) | median PnL ($) | "
        "best ($) | worst ($) | profit % | mean Sharpe | trades | Δmean vs baseline |"
    )
    sep = "|---" * 11 + "|"
    out = [header, sep]
    for r in rows:
        delta = r["mean_pnl_usd"] - base["mean_pnl_usd"]
        delta_s = "—" if r["label"] == base["label"] else f"${delta:+,.2f}"
        out.append(
            f"| `{r['label']}` | {r['generated']} | {r['n_windows']} "
            f"| {r['mean_pnl_usd']:+,.2f} | {r['median_pnl_usd']:+,.2f} "
            f"| {r['max_pnl_usd']:+,.2f} | {r['min_pnl_usd']:+,.2f} "
            f"| {r['pct_profitable']:.0%} | {r['mean_sharpe']:+.3f} "
            f"| {r['n_trades']} | {delta_s} |"
        )
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+",
                        help="paths to backtest JSON reports (globs allowed)")
    parser.add_argument("--out", default="",
                        help="optional markdown output path; prints to stdout if absent")
    args = parser.parse_args()

    expanded: list[str] = []
    for p in args.paths:
        if any(c in p for c in "*?["):
            expanded.extend(sorted(glob.glob(p)))
        else:
            expanded.append(p)
    if not expanded:
        print("no JSON reports matched", file=sys.stderr)
        return 2

    rows: list[dict] = []
    for p in expanded:
        try:
            rows.append(_row(_load(p)))
        except Exception as exc:    # pragma: no cover - defensive
            print(f"skipped {p}: {exc}", file=sys.stderr)

    md = _render(rows)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as f:
            f.write("# Backtest comparison\n\n" + md)
        print(f"wrote {args.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
