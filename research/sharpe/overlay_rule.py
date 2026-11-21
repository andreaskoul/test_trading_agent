"""Item 2 of PREREG_CAPITAL.md: the overlay risk-budget rule, tabulated (no data fitting).
sigma_o = 1/2 * sigma_c * S_used / S_c;  S_used = max(0, 1/2 * L);  L = S_hat - 1.645 * sqrt((1 + S_hat^2/2) / years).
Gross g = sigma_o / sigma_unit, capped at 0.6. Inputs: RESULT_CAPITAL.json (core) and the B0 ledger (MASTER book)."""
import json, math, os
import numpy as np, pandas as pd
from scipy.optimize import brentq
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
cap = json.load(open(os.path.join(HERE, "RESULT_CAPITAL.json")))
core = cap["item1_a_1927_2026"]["M_R"]
S_c, sig_c = core["excess_sharpe"], core["vol_pct"] / 100
L = pd.read_csv(os.path.join(ROOT, ".cache", "capital", "weekly_b0_ledger.csv"))
book = 7 * L.book_net_return / L.days
sig_unit = float(book.std(ddof=1) * math.sqrt(52) / 0.6)        # MASTER book volatility per unit of gross
G = 0.6
def lower(s, y): return s - 1.645 * math.sqrt((1 + s * s / 2) / y)
def rule(s, y):
    Lb = lower(s, y); su = max(0.0, 0.5 * Lb); so = 0.5 * sig_c * su / S_c
    return {"S_hat": s, "years": y, "lower_95": Lb, "S_used": su, "overlay_vol_pct": 100 * so,
            "gross": min(G, so / sig_unit), "gross_uncapped": so / sig_unit}
su_full = 2 * S_c * sig_unit * G / sig_c
need = {y: brentq(lambda s: 0.5 * lower(s, y) - su_full, 0, 20) for y in (2, 6, 10)}
rows = {"F2 short-volume tilt (Sharpe derived from OOS t -1.88 over 6 years; no return series on file)": rule(1.88 / math.sqrt(6), 6),
        "Broad trees book, point in time, realistic cost model (R2)": rule(0.03, 498 / 52),
        "Broad trees book, point in time, 14 bp flat (R2)": rule(0.12, 498 / 52),
        "MASTER book, development 2013-2019": rule(-0.161, 7),
        "MASTER book, 2020-2025 walk-forward (reused)": rule(0.768, 6)}
out = {"core": {"S_c": S_c, "sigma_c_pct": 100 * sig_c, "source": "RESULT_CAPITAL item1_a M_R (1927-2026)"},
       "sigma_unit_pct_MASTER_book_per_unit_gross": 100 * sig_unit, "S_used_for_full_0.6": su_full,
       "S_hat_needed_for_full_0.6_by_years": need, "rows": rows}
json.dump(out, open(os.path.join(HERE, "RESULT_OVERLAY_RULE.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
