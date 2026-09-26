"""Exploratory: how much did the look-ahead in the old extended features buy?

Runs the pre-registered ridge rule on the old parquets (as committed on
main before the causal rebuild; macro closes on their own date and S&P
monthly averages for 2012-15) and on the rebuilt ones, same code path.
Also reports each macro column's same-horizon correlation with the gold
outcome, old vs new: a feature that 'knows' today's dollar or S&P close
should correlate with today's gold move far more than a lagged one.

    python scripts/13_leak_probe.py <old_commit>
"""

import io
import os
import subprocess
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]] + (sys.argv[1:] or ["1b424ff"])
old_ref = sys.argv[1]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import importlib.util
spec = importlib.util.spec_from_file_location("ladder", os.path.join(ROOT, "scripts/11_baseline_ladder.py"))


def old(path):
    b = subprocess.run(["git", "-C", ROOT, "show", f"{old_ref}:{path}"], capture_output=True, check=True).stdout
    return pd.read_parquet(io.BytesIO(b))


new_d = pd.read_parquet(os.path.join(ROOT, "data/processed/features_gc_extended.parquet"))
new_h = pd.read_parquet(os.path.join(ROOT, "data/processed/features_gc_extended_holdout.parquet"))
old_d = old("data/processed/features_gc_extended.parquet")
old_h = old("data/processed/features_gc_extended_holdout.parquet")
for o_, n_ in ((old_d, new_d), (old_h, new_h)):
    for k in ("open", "high", "low"):
        o_[k] = n_[k].reindex(o_.index)

# Load the ladder's helpers without running its main body.
src = open(os.path.join(ROOT, "scripts/11_baseline_ladder.py")).read().split("results, trades_out = [], {}")[0]
L = {"__file__": os.path.join(ROOT, "scripts/11_baseline_ladder.py")}
exec(compile(src, "ladder_helpers", "exec"), L)

rows = []
for tag, d, h in (("old (leaky)", old_d.dropna(), old_h.dropna()), ("new (causal)", new_d, new_h)):
    feats = L["feature_columns"](d)
    for H in (4, 26):
        nd, gd, exd, _ = L["outcomes"](d, H)
        nh, gh, exh, _ = L["outcomes"](h, H)
        ok = ~np.isnan(nd).any(1)
        folds = np.array_split(np.arange(len(d)), 8)
        sc = np.zeros(len(d))
        for f in folds:
            tr = np.where(((np.arange(len(d)) < f[0] - H - 32) | (np.arange(len(d)) > f[-1] + H + 32)) & ok)[0]
            sc[f], _ = L["fit_predict"]("ridge", d[feats].to_numpy()[tr], nd[tr], None, d[feats].to_numpy()[f], None, None)
        sh, _ = L["fit_predict"]("ridge", d[feats].to_numpy()[ok], nd[ok], None, h[feats].to_numpy(), None, None)
        for split, s_, g_, idx in (("dev_oof", sc, gd, d.index), ("holdout", sh, gh, h.index)):
            ic, t, _ = L["monthly_ic"](s_, g_[:, 0] - g_[:, 1], idx)
            rows.append(dict(data=tag, H=H, split=split, ridge_ic=ic, ic_t=t))
        # per-macro-column correlation with same-horizon long outcome (dev)
        for c in [c for c in feats if "_chg" in c]:
            m = ~np.isnan(gd[:, 0])
            rows.append(dict(data=tag, H=H, split="dev", column=c,
                             spearman_with_outcome=stats.spearmanr(d[c].to_numpy()[m], gd[m, 0])[0]))

R = pd.DataFrame(rows)
R.to_csv(os.path.join(ROOT, "reports/research/leak_probe.csv"), index=False)
pd.set_option("display.width", 200)
print(R[R.column.isna()].drop(columns=["column", "spearman_with_outcome"]).round(4).to_string())
print(R[R.column.notna() & (R.H == 4)].pivot_table(index="column", columns="data",
                                                     values="spearman_with_outcome").round(4))
