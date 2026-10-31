"""The entry-day "already priced in" log of the lifecycle book (fund/lifecycle.py trade). Pure: no I/O, no side
effects, so it can be tested on real cohort records without importing lifecycle.py (which runs a mode at import).

The constants are passed in by lifecycle.py (P_CAP, H_MIN, H8_MAX, STALE_AT: Amendment 8's), so they live in one place.
"""

import numpy as np
import pandas as pd


def entry_day_check(C, day, ret, k):
    """Logged only (2026-10-31, operational): for each name entering at this close, the residual move from the
    signal date's close to the decision price, and Amendment 8's "already priced in" fraction and horizon recomputed
    with it. The desk's p uses closes only to the as-of close, so a release after that close is invisible to it."""
    out = {}
    for c in C:
        if str(pd.Timestamp(c.get("entry_day")).date()) != str(day.date()):
            continue
        for t, v in (c.get("names") or {}).items():
            i = v.get("inputs") or {}
            if t not in ret or "SPY" not in ret or not i.get("M"):
                continue
            side = 1 if c["w"].get(t, 0) > 0 else -1
            ed = ret[t] - float(c.get("beta", {}).get(t, 1.0)) * ret["SPY"]
            p_e = float(np.clip(side * (float(i.get("car") or 0.0) + ed) / float(i["M"]), 0.0, k["P_CAP"]))
            raw = (float(i["B"]) * float(i["m"]) - float(v.get("news_age") or 0)) * (1 - 0.5 * min(p_e, 1.0))
            out[t] = {"side": side, "car_desk": i.get("car"), "car_entry_day": ed, "M": i.get("M"), "p_desk": i.get("p"),
                      "p_entry": p_e, "H_desk": v.get("H"), "H_a8_entry": int(min(max(round(raw), k["H_MIN"]), k["H8_MAX"])),
                      "stale_entry": bool(raw <= k["STALE_AT"]), "priced_in_entry": bool(p_e >= 1), "hard": i.get("hard")}
    return out
