import sys
sys.path.insert(0, "research/p8")
import h1 as H1, inference as I, pandas as pd
out = []
for seed in range(1, 6):
    P = H1.build(placebo_seed=seed)
    v = P[(P["t0"] >= "2022-01-01") & (P["t0"] <= "2025-12-31") & (P["universe"] == "sp400")]
    o = I.event_test(v["CAR"], v["S"], v["season"] + "|" + v["sector"], v["industry"], direction=-1, B=1999)
    out.append(o); print(f"placebo seed {seed}: n {o['n']}, beta {o['beta']:+.4f}, t {o['t']:+.2f}, p {o['p']:.4f}", flush=True)
