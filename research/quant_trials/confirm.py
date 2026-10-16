"""Quant trials · Stage 2: the one confirmation read on 2022-2025 (plan: Stage 2; PREREG_quant_trials.md).

    python confirm.py            # refuses unless the pre-registration is committed AND pushed

For every frozen candidate it fits an expanding window refit per year (train 2016..Y-1 with an h-session
embargo, predict year Y, Y = 2022..2025), together with its price-only twin and its shuffled-text placebo, then
scores the pre-registered statistics. The candidate list is read from the JSON block in the pre-registration,
never from this file. Run it once.
"""

import json
import os
import re
import subprocess
import sys

import numpy as np
import pandas as pd
from scipy import stats

import features as F
import panel as P
import trials as T

ROOT = P.ROOT
PREREG = os.path.join(ROOT, "reports", "research", "PREREG_quant_trials.md")
OUT = os.path.join(P.REPORT, "CONFIRM.md")
YEARS = (2022, 2023, 2024, 2025)


def frozen():
    """Candidates + pass rules from the committed, pushed pre-registration."""
    rel = os.path.relpath(PREREG, ROOT)
    if not os.path.exists(PREREG):
        sys.exit("no pre-registration")
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=ROOT).returncode:
        sys.exit("pre-registration has uncommitted changes")
    sha = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", rel], cwd=ROOT, text=True).strip()
    if not sha or not subprocess.check_output(["git", "branch", "-r", "--contains", sha], cwd=ROOT, text=True).strip():
        sys.exit("pre-registration commit is not pushed")
    if os.path.exists(OUT):
        sys.exit("CONFIRM.md exists: the confirmation read has already been made")
    if "Owner sign-off:** _pending_" in open(PREREG).read():
        sys.exit("pre-registration not signed off by the owner")
    block = re.search(r"```json\n(.*?)\n```", open(PREREG).read(), re.S).group(1)
    return json.loads(block), sha


def weekly_net_spread(pred, r5, idx, cost_bp=5.0):
    """Weekly top-minus-bottom tercile portfolio (equal weights, +-1/k), held one week on the 5-session
    residual return from close(d+1); cost = cost_bp per unit of one-way turnover."""
    out, prev = [], None
    for d in idx:
        m = np.isfinite(pred[d]) & np.isfinite(r5[d])
        w = np.zeros(pred.shape[1])
        if m.sum() >= 10:
            q = pd.Series(pred[d][m]).rank(pct=True).values
            ix = np.where(m)[0]
            lo, hi = ix[q <= 1 / 3], ix[q > 2 / 3]
            if len(hi) and len(lo):                 # all-tied predictions (e.g. a stump-only GBRT week): no position
                w[hi], w[lo] = 1 / len(hi), -1 / len(lo)
        g = float(np.nansum(w * np.nan_to_num(r5[d])))
        c = 0.0 if prev is None else cost_bp * 1e-4 * np.abs(w - prev).sum()
        out.append(g - c)
        prev = w
    return np.array(out)


def main():
    spec, sha = frozen()
    p = F.Panel()
    tx = T.Text(p)
    grp = F.sector_ids(p.names)
    r5 = p.target(5)
    rows, tests = [], []
    for c in spec["candidates"]:
        h = c["h"]
        base = {k: v for k, v in c.items() if k not in ("id", "family")}
        cfgs = {"cand": {**base, "trial": "S2"}, "price": {**base, "arm": "none", "trial": "S2"},
                "placebo": {**base, "placebo": True, "trial": "S2"}}
        hashes = {}
        for role, cfg in cfgs.items():
            h_ = T.chash(cfg)
            if all(os.path.exists(os.path.join(T.PREDS, f"{h_}_{y_}.npy")) for y_ in YEARS):
                hashes[role] = h_                   # already fitted in this read: reuse, never refit
                continue
            hashes[role], _ = T.run_config(p, tx, cfg, YEARS, extra_info={"prereg": sha}, confirm=True)
        y = p.target(h)
        yn = F.neutralise(y, grp)
        per = {}
        for fy in YEARS:
            _, test = F.fold_index(p, fy, h)
            wk = F.thursdays(p, test)
            yy, yyn = y.copy(), yn.copy()
            yy[test[-1] + 1:] = np.nan
            yyn[test[-1] + 1:] = np.nan
            pr = {k: np.load(os.path.join(T.PREDS, f"{v}_{fy}.npy")) for k, v in hashes.items()}
            ic = {k: F.weekly_ic(v, yy, wk) for k, v in pr.items()}
            icn = {k: F.weekly_ic(F.neutralise(v, grp), yyn, wk) for k, v in pr.items()}
            per[fy] = {"d_price": ic["cand"] - ic["price"], "d_placebo": ic["cand"] - ic["placebo"],
                       "d_neutral": icn["cand"] - icn["price"], "ic": ic["cand"],
                       "net": weekly_net_spread(pr["cand"], r5, wk)}
        cat = lambda k, ys=YEARS: np.concatenate([per[y_][k] for y_ in ys])
        L = F.nw_lag(h)
        t_price = F.nw_t(cat("d_price"), L)
        row = {"id": c["id"], "family": c.get("family", "primary"), "h": h, "model": c["model"], "arm": c["arm"],
               "variant": c.get("variant", ""),
               "ic": np.nanmean(cat("ic")), "d_price": np.nanmean(cat("d_price")), "t_price": t_price,
               "p_one_sided": float(stats.norm.sf(t_price)),
               "d_2022": np.nanmean(per[2022]["d_price"]),
               "d_2022_23": np.nanmean(cat("d_price", (2022, 2023))),
               "d_2024_25": np.nanmean(cat("d_price", (2024, 2025))),
               "d_placebo": np.nanmean(cat("d_placebo")), "t_placebo": F.nw_t(cat("d_placebo"), L),
               "d_sector_neutral": np.nanmean(cat("d_neutral")), "t_sector_neutral": F.nw_t(cat("d_neutral"), L),
               "net_spread_bp_wk": np.nanmean(cat("net")) * 1e4,
               **{f"d_{y_}": np.nanmean(per[y_]["d_price"]) for y_ in YEARS}}
        rows.append(row)
    df = pd.DataFrame(rows)
    prim = df[df.family == "primary"].sort_values("p_one_sided")
    m = len(prim)
    holm, running = {}, 0.0
    for k, (i, r) in enumerate(prim.iterrows()):
        running = max(running, min(1.0, (m - k) * r.p_one_sided))
        holm[i] = running
    df["p_holm"] = pd.Series(holm)
    df["pass"] = ((df.p_holm < 0.05) & (df.d_2022_23 > 0) & (df.d_2024_25 > 0) & (df.d_2022 >= 0)
                  & (df.d_placebo > 0) & (df.net_spread_bp_wk > 0)).where(df.family == "primary")
    df["kind"] = np.where(df.d_sector_neutral > 0, "firm-level", "sector-rotation")
    df.to_csv(os.path.join(P.REPORT, "confirm.csv"), index=False)
    with open(OUT, "w") as f:
        f.write(f"# Quant trials · Stage 2 confirmation read (2022-2025)\n\nPre-registration commit `{sha}`. "
                "One read; rules as pre-registered.\n\n")
        f.write(df.round(4).to_markdown(index=False))
        f.write("\n")
    print(df.round(4).to_string())


if __name__ == "__main__":
    main()
