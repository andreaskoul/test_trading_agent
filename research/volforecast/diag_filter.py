"""Development-only diagnostic: how often does the insanity filter bind, and is it why HAR under-forecasts the ETFs?
Panel truncated at the development end (no out-of-sample datum)."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data as DATA  # noqa: E402
import evaluate as EV  # noqa: E402
import models as M  # noqa: E402

cls = sys.argv[1] if len(sys.argv) > 1 else "etf"
P = EV.truncate(pd.read_parquet(os.path.join(DATA.CACHE, f"panel_{cls}.parquet")), EV.WINDOWS[cls]["dev"][1],
                EV.FE.HORIZONS_BY_CLASS[cls])
a, b = EV.WINDOWS[cls]["dev"]
orig = M._finish
log = {}


def make_finish(tag, filt):
    def f(fc_avg, yv, H, n, sy):
        mn, mx = M._window_range(yv, H)
        hi = np.isfinite(fc_avg) & (fc_avg > mx)
        lo = np.isfinite(fc_avg) & ((fc_avg < mn) | (fc_avg <= 0))
        log.setdefault(tag, []).append((hi.sum(), lo.sum(), np.isfinite(fc_avg).sum()))
        if filt:
            return orig(fc_avg, yv, H, n, sy)
        out = np.where(fc_avg <= 0, sy / np.maximum(n, 1), fc_avg)       # only the non-positive guard
        out[n < M.MINROWS] = np.nan
        return H * out
    return f


for H in EV.FE.HORIZONS_BY_CLASS[cls][1:3]:
    for filt in (True, False):
        M._finish = make_finish(f"H{H}_{'filter' if filt else 'nofilter'}", filt)
        rows = []
        for asset, g in P.groupby(level="asset", sort=False):
            g = g.droplevel("asset")
            for m in ("S3", "S4", "S5"):
                s = M.har_family(g, H, m)
                rows.append(pd.DataFrame({"asset": asset, "date": g.index, "m": m, "f": s.values,
                                          "y": g[f"y{H}"].values}))
        D = pd.concat(rows)
        D = D[(D["date"] >= a) & (D["date"] <= b) & np.isfinite(D["f"]) & np.isfinite(D["y"]) & (D["f"] > 0)]
        q = D["y"] / D["f"] - np.log(D["y"] / D["f"]) - 1
        D["q"] = q
        s = D.groupby("m").agg(qlike=("q", "mean"), real_fc=("y", "sum"))
        s["real_fc"] = D.groupby("m")["y"].sum() / D.groupby("m")["f"].sum()
        print(f"{cls} H={H} {'FILTER ON ' if filt else 'FILTER OFF'}:", s.round(3).to_dict("index"))
        bind = np.array(log[f"H{H}_{'filter' if filt else 'nofilter'}"]).sum(0)
        print(f"   above window max: {bind[0]} rows, below min / <= 0: {bind[1]} rows, of {bind[2]} forecasts")
        log.clear()
M._finish = orig
