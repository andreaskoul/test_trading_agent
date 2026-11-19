"""Read-only reconciliation of *already published* H7 and Layer-4 summaries.

Does not load raw market data, run a strategy, inspect a new OOS sample,
modify any incumbent research result, or communicate with the broker.
"""
from __future__ import annotations

import json
import math
from pathlib import Path


def _num(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name}: expected finite numeric value")
    return float(value)


def _agree(a, b, name, atol=1e-9):
    a, b = _num(a, name), _num(b, name)
    if not math.isclose(a, b, rel_tol=0.0, abs_tol=atol):
        raise ValueError(f"{name}: incompatible previously published results: {a} != {b}")


def audit_reports(h7, decomposition, layer4):
    """Reconcile existing B0/H7 headline metrics without claiming NAV-row equality.

    Input dictionaries are JSON from H7_RESULT, H7_DECOMP, L4_exploit/RESULT.
    Checks establish *headline* equivalence only; per-position ledger still needs
    independently verified cash and per-period return streams.
    """
    a = h7["arms"]["H7a"]
    b = h7["arms"]["H7b"]
    d = decomposition["fund"]["by_year_pct_per_year"]["2026"]
    l = layer4["y2026_already_read_reported_not_tested"]["B0"]
    n = int(_num(l["weeks"], "L4 weeks"))
    if n != l["weeks"] or n <= 1:
        raise ValueError("invalid weeks")
    dates = list(l["period"])
    if len(dates) != 2 or dates[0] > dates[1]:
        raise ValueError("invalid period")
    for label, arm in (("H7a", a), ("H7b", b)):
        if list(arm["period"]) != dates:
            raise ValueError(f"{label}: period mismatch")
        for key in ("weeks",):
            _agree(arm[key], n, f"{label} {key}")
        _agree(arm["fund_alone"]["weeks"], n, f"{label} fund weeks")
        _agree(arm["fund_alone"]["pct_per_year"], d["total"], f"{label} arithmetic annual")
        _agree(arm["fund_alone"]["net_sharpe"], l["sharpe"], f"{label} raw return/vol")
        _agree(arm["fund_alone"]["worst_fall_pct"], l["worst_fall_pct"], f"{label} drawdown")
    _agree(d["weeks"], n, "decomposition weeks")
    _agree(d["master_book"], l["book_pct_per_year_arith"], "MASTER book annual arithmetic")
    _agree(d["book_sharpe"], l["book_sharpe"], "MASTER book raw ratio")
    arith = _num(d["total"], "arithmetic annual percentage")
    # Identity: raw annual Sharpe = annual arithmetic mean / annual volatility.
    _agree(arith, _num(l["sharpe"], "raw ratio") * _num(l["vol_pct"], "annual volatility"),
           "annual arithmetic = legacy ratio times volatility")
    cum = _num(l["pct_simple_2026"], "cumulative percent") / 100.0
    geo = _num(l["pct_per_year"], "annual geometric percent") / 100.0
    if cum <= -1 or geo <= -1 or (geo == 0 and cum != 0):
        raise ValueError("invalid compounding inputs")
    implied_days = None if geo == 0 else 365.25 * math.log1p(cum) / math.log1p(geo)
    if implied_days is not None and (not math.isfinite(implied_days) or implied_days <= 0):
        raise ValueError("invalid implied duration")
    last_rate = h7["fund_info"].get("rf_last_date")
    if not isinstance(last_rate, str):
        raise ValueError("risk-free last date missing")
    from datetime import date
    rf_age_days = (date.fromisoformat(dates[-1]) - date.fromisoformat(last_rate)).days
    if rf_age_days < 0:
        raise ValueError("risk-free series extends past reported last portfolio date")
    cap_nominal = 1.9  # Layer 4's reference CAP, not a hard B0 constraint.
    mean_gross = _num(l["mean_gross"], "mean gross")
    return {
        "period": dates,
        "weeks": n,
        "annual_arithmetic_percent": arith,
        "annual_geometric_percent": 100.0 * geo,
        "cumulative_simple_percent": 100.0 * cum,
        "difference_geometric_minus_arithmetic_pp": 100.0 * geo - arith,
        "legacy_return_to_vol_ratio": _num(l["sharpe"], "raw ratio"),
        "annual_volatility_percent": _num(l["vol_pct"], "volatility"),
        "master_book_arithmetic_percent": _num(d["master_book"], "book"),
        "implied_elapsed_days": implied_days,
        "rf_last_reported_date": last_rate,
        "rf_last_date_age_at_report_end_days": rf_age_days,
        "mean_gross_exposure": mean_gross,
        "mean_gross_minus_nominal_cap": mean_gross - cap_nominal,
        "audited_claim": "summary-level cross-reconciliation only; no cash-adjusted Sharpe or NAV-row audit",
    }


def audit_repository(root):
    root = Path(root)
    paths = (root / "research/tree/H7_RESULT.json",
             root / "research/tree/H7_DECOMP.json",
             root / "research/tree/L4_exploit/RESULT.json")
    with paths[0].open(encoding="utf-8") as f:
        h7 = json.load(f)
    with paths[1].open(encoding="utf-8") as f:
        decomp = json.load(f)
    with paths[2].open(encoding="utf-8") as f:
        layer4 = json.load(f)
    return audit_reports(h7, decomp, layer4)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    print(json.dumps(audit_repository(root), indent=2, allow_nan=False))
