"""Run a batch of named configurations: python3 run.py <batch>. Every scored configuration is appended to RESULTS.jsonl."""
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "2")
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib
from lib import GROUPS as G
from harness import load, walk_forward, score

LOG = "research/tree/C_features/RESULTS.jsonl"
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

REVX = [("rev5", "mvol"), ("erev5", "mvol"), ("rev21", "mvol"), ("erev21", "mvol"), ("rev1", "mvol"), ("mom252", "mvol"),
        ("rev5", "mret"), ("mom252", "mret")]

BATCH = {
    "screen": [
        ("C01 rev group", dict(feats=G["rev"]), "screen: reversal 1/5/21, raw and hedged; ranks, pooled expanding ridge lam 0.1, all days"),
        ("C02 mom group", dict(feats=G["mom"]), "screen: momentum 63/126/252 skip 21, hedged and residual"),
        ("C03 risk group", dict(feats=G["risk"]), "screen: ivol, tvol, beta, skew, max21, vol change"),
        ("C04 52w-high + vol-scaled", dict(feats=G["hv"]), "screen: distance from 52w high, vol-scaled returns"),
        ("C05 all 24", dict(feats=G["all"]), "screen: all 24 characteristics"),
        ("C06 all 24 + market-state interactions", dict(feats=G["all"], inter=REVX), "screen: all + reversal/momentum x market vol/ret state"),
    ],
    "refine": [
        ("C07 rev + risk groups", dict(feats=G["rev"] + G["risk"]), "refine: the two best single groups together, 13 features"),
        ("C08 all 24 + all x market vol", dict(feats=G["all"], inter=[(f, "mvol") for f in G["all"]]), "refine: every characteristic interacted with market-vol state"),
        ("C09 C06 with z-scores", dict(feats=G["all"], inter=REVX, how="z"), "transform: winsorised z-scores instead of ranks"),
        ("C10 C06 with gaussianised ranks", dict(feats=G["all"], inter=REVX, how="gauss"), "transform: gaussianised ranks"),
        ("C11 C06 rolling 3y window", dict(feats=G["all"], inter=REVX, window="rolling", roll=756), "estimation: rolling 756 sessions"),
        ("C12 C06 exp-weighted hl 2y", dict(feats=G["all"], inter=REVX, window="ew", halflife=504), "estimation: exponential weights, half-life 504 sessions"),
        ("C13 C06 Fama-MacBeth", dict(feats=G["all"], inter=REVX, fm=True), "estimation: average of daily cross-sectional ridge slopes"),
        ("C14 C06 heavy shrinkage lam 3", dict(feats=G["all"], inter=REVX, lam=3.0), "estimation: ridge lam 3 x mean eigenvalue (vs 0.1)"),
        ("C15 C06 Thursdays only", dict(feats=G["all"], inter=REVX, thursdays_only=True), "estimation: non-overlapping Thursday rows only"),
    ],
}


def run(batch):
    D = load()
    for name, cfg, note in BATCH[batch]:
        t0 = time.time()
        fp = lib.make(**cfg)
        pred = walk_forward(fp, seeds=(0, 1, 2), D=D)
        res = score(pred, name, LOG, note=note, D=D)
        b = list(fp.cache.values())[-1]
        top = sorted(zip(lib.names(cfg["feats"], cfg.get("inter", ())), b), key=lambda z: -abs(z[1]))[:8]
        print("%-42s IC %.4f t %.2f  yrs %s  pos %d/7  net %.1f%%  (%.0fs)" % (
            name, res["ic"], res["ic_t"], " ".join("%+.3f" % v for v in res["ic_by_year"].values()),
            sum(v > 0 for v in res["ic_by_year"].values()), res["decile_net_pct_per_year"], time.time() - t0), flush=True)
        print("    last-fit coefs:", ", ".join("%s %+.4f" % z for z in top), flush=True)


if __name__ == "__main__":
    run(sys.argv[1])
