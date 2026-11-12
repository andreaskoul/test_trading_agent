"""Configuration set 1: each characteristic alone (no fitting), harness.score, names prefixed single_."""
import json
import numpy as np
import pandas as pd
import lib
from lib import harness

D, R = lib.data(), lib.ranks()
rows = np.concatenate([harness.thursdays(D, y) for y in harness.VAL_YEARS])
out = []
for k in list(lib.CHARS) + ["prof", "logassets", "composite"]:
    name = "single_" + k
    import json as _j
    done = _j.load(open(lib.os.path.join(lib.HERE, "STATE.json")))["scored"]
    if name in done:
        continue
    s = lib.composite() if k == "composite" else R[k]
    p = np.full(D["y5"].shape, np.nan)
    p[rows] = s[rows]
    cov = float((np.isfinite(p[rows]) & D["elig"][rows]).sum() / D["elig"][rows].sum())
    cm = float(np.nanmean([pd.Series(p[t]).corr(pd.Series(R["master"][t]), method="spearman") for t in rows]))
    desc = lib.CHARS[k] if k in lib.CHARS else {"prof": "gpa where present else opa", "logassets": "log assets (size proxy, sign +)",
                             "composite": "equal-weight prof, accruals, agrowth, payout, sue; missing neutral"}[k]
    r = harness.score(p, name, lib.LOG, note=f"{desc}; coverage {cov:.2f} of eligible; corr with MASTER {cm:.3f}", D=D)
    out.append((name, r["ic"], r["ic_t"], r["min_year_ic"], r["decile_net_pct_per_year"], r["decile_net_sharpe"], cov, cm))
    print(out[-1], flush=True)
lib.update_state(None, "set 1 done: single_* references (score) for 12 characteristics + prof, logassets, composite; next: comp_blend70, comp_blend50",
                 ["comp_blend70", "comp_blend50", "fm_ridge", "hgb_blend", "dml_composite"])
