"""Fit and freeze the ridge forecasts the LLM is shown (PROTOCOL_llm.md).

Coefficients are fitted once on all weeks through 2026-03-31, using exactly
the Protocol 3/4 panels (cross-sectional z-scores of the base signals ->
next week's demeaned return), and stored in artefacts/llm/. They are never
refitted during the forward window.

    python scripts/llm/fit_frozen_ridge.py
"""

import json
import os

import numpy as np
from sklearn.linear_model import Ridge

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "artefacts", "llm")
os.makedirs(OUT, exist_ok=True)

for name, script, cut in (("stocks", "scripts/xs/stock_ladder.py", "def rank_weights"),
                          ("fx", "scripts/xs/fx_ladder.py", "# ------------------------------------------------------------------ portfolio machinery")):
    path = os.path.join(ROOT, script)
    src = open(path).read().split(cut)[0]
    src = src.replace("sc = ridge_scores(", "pass  # sc = ridge_scores(")      # skip the CV loop
    G = {"__file__": path}
    exec(compile(src.split("ridge = pd.DataFrame(")[0], script, "exec"), G)
    panel, BASE = G["panel"], list(G["BASE"])
    wk = panel.index.get_level_values(0)
    tr = panel[wk <= "2026-03-31"]
    m = Ridge(alpha=10.0).fit(tr[BASE], tr["y"])
    spec = {"features": BASE, "coef": m.coef_.tolist(), "intercept": float(m.intercept_), "alpha": 10.0,
            "fit_weeks": [str(wk.min().date()), "2026-03-31"], "n_obs": int(len(tr)),
            "input": "cross-sectional z-scores of the base signals (see PROTOCOL_fx.md / PROTOCOL_stocks.md)"}
    json.dump(spec, open(os.path.join(OUT, f"ridge_{name}.json"), "w"), indent=2)
    print(name, dict(zip(BASE, np.round(m.coef_ * 1e4, 2))), "bp per 1 sd", "n", len(tr))
