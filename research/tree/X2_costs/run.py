import os
os.environ["OMP_NUM_THREADS"] = "3"
import sys, time, json, warnings
import numpy as np
warnings.filterwarnings("ignore")
import lib, harness
HERE = os.path.dirname(os.path.abspath(__file__))
lib.CACHE_DIR = sys.argv[1]
os.makedirs(lib.CACHE_DIR, exist_ok=True)
D = harness.load()
A = lambda *hs: tuple(("all", h, w) for h, w in hs)
CONF = {
 "c1_base_mh":      (dict(members=A((3, 1), (5, 1), (10, 1), (20, 1))), "base reproduced: D's HGB, equal-weight ranks of 3/5/10/20-session targets"),
 "c1b_base_h5":     (dict(members=A((5, 1))), "D's HGB, 5-session target only"),
 "c2a_mh_ema_hl1":  (dict(members=A((3, 1), (5, 1), (10, 1), (20, 1)), hl=1), "base + EMA of ranks over past weeks, half-life 1 week, 12-week lookback"),
 "c2b_mh_ema_hl3":  (dict(members=A((3, 1), (5, 1), (10, 1), (20, 1)), hl=3), "base + EMA of ranks, half-life 3 weeks"),
 "c3_h10_h20":      (dict(members=A((10, 1), (20, 1))), "HGB on 10- and 20-session targets only"),
 "c4_blend_slow":   (dict(members=A((5, 1), (10, 2), (20, 3))), "blend 5/10/20-session models, weights 1:2:3"),
 "c5_nofast_mh":    (dict(members=tuple(("slow", h, 1) for h in (5, 10, 20))), "5/10/20-session models without e1, e5, r5, z5 (23 features)"),
 "c7_mh_ema1_band5": (dict(members=A((3, 1), (5, 1), (10, 1), (20, 1)), hl=1, b=0.05), "c2a + no-trade band: last week's decile members keep their place until their rank is 5 points inside the threshold"),
 "c8_h10h20_ema1":  (dict(members=A((10, 1), (20, 1)), hl=1), "c3 (10/20-session targets) + EMA half-life 1 week"),
 "c9_mh_ema_hl2":   (dict(members=A((3, 1), (5, 1), (10, 1), (20, 1)), hl=2), "base + EMA of ranks, half-life 2 weeks"),
 "c6_tc_target":    (dict(members=(("tc", 5, 1),)), "5-session target minus 10 bp when the first-stage score changed decile since last Thursday"),
}
EXTRA = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
for k, (kw, note) in EXTRA.items():
    kw["members"] = tuple(tuple(m) for m in kw["members"])
    CONF[k] = (kw, note)
for name in sys.argv[2].split(","):
    kw, note = CONF[name]
    t0 = time.time()
    pred = harness.walk_forward(lib.make(**kw), seeds=(0, 1, 2), D=D)
    r = harness.score(pred, name, None if os.environ.get("NOLOG") else os.path.join(HERE, "RESULTS.jsonl"), note=note, D=D)
    # diagnostics (not logged by the harness): gross spread and turnover, same definitions as harness.decile_net
    rows = np.concatenate([harness.thursdays(D, y) for y in harness.VAL_YEARS])
    c = harness.COST; harness.COST = 0.0; g = harness.decile_net(pred, D, rows); harness.COST = c
    n = harness.decile_net(pred, D, rows)
    by = r["ic_by_year"]
    print("%-18s IC %+.4f t %+.2f pos %d/7 | net %+.2f%%/y sh %+.2f | gross %+.2f%%/y cost %.2f%%/y turn %.0f%%/wk | %.0fs" % (
        name, r["ic"], r["ic_t"], sum(v > 0 for v in by.values()), r["decile_net_pct_per_year"], r["decile_net_sharpe"],
        52 * g.mean() * 100, 52 * (g.mean() - n.mean()) * 100, (g.mean() - n.mean()) / (2 * c) * 100, time.time() - t0), flush=True)
