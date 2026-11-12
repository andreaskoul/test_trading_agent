"""python3 run.py name1 name2 ...  : score named configurations (each appended to RESULTS.jsonl)."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "3")
import sys
import time
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lib  # noqa: E402
import harness  # noqa: E402

lib.DISK = os.path.join(HERE, "cache")
H = lib.HORIZONS
mh = lambda kind, fs: [(kind, fs, h) for h in H]
C = {
    "1a_D_hgb_mh": (dict(specs=mh("hgb", "D")), "baseline: branch D boosted trees, D's 27 inputs, targets 3/5/10/20 sessions, rank average"),
    "1b_C_fmridge": (dict(specs=[("fm", "C", 5)]), "baseline: branch C Fama-MacBeth ridge, 24 characteristics + 8 state interactions"),
    "2_hgb_Cfeat": (dict(specs=[("hgb", "Ct", 5)]), "D's boosted trees on C's 24 characteristics + 2 market-state scalars, 5-session target"),
    "3_ew3_Cfeat": (dict(specs=[("hgb", "Ct", 5), ("fm", "C", 5), ("mlp", "C", 5)]), "rank average of trees + FM ridge + MLP on C's features, 5-session target"),
    "4_ew3_Cfeat_mh": (dict(specs=None, groups=[mh("hgb", "Ct"), mh("fm", "C"), mh("mlp", "C")]), "as 3 with each learner trained on 3/5/10/20-session targets (ranks averaged within learner, then across)"),
    "5_ew3_Cfeat_mh_panic": (dict(specs=None, groups=[mh("hgb", "Ct"), mh("fm", "C"), mh("mlp", "C")], panic=True), "4 + fixed panic overlay: in panic weeks the score is residualised on 12-1 momentum"),
    "6_hgbD_mh+fmC": (dict(specs=None, groups=[mh("hgb", "D"), [("fm", "C", 5)]]), "the two round-1 winners as they were: D trees multi-horizon + C FM ridge, equal weight"),
    "6p_hgbD_mh+fmC_panic": (dict(specs=None, groups=[mh("hgb", "D"), [("fm", "C", 5)]], panic=True), "6 + fixed panic overlay"),
    "7_hgbD_mh+fmC_mh": (dict(specs=None, groups=[mh("hgb", "D"), mh("fm", "C")]), "D trees multi-horizon + C FM ridge multi-horizon"),
    "7p_hgbD_mh+fmC_mh_panic": (dict(specs=None, groups=[mh("hgb", "D"), mh("fm", "C")], panic=True), "7 + fixed panic overlay"),
    "8_hgbD_mh+fmC_mh+mlpC_mh": (dict(specs=None, groups=[mh("hgb", "D"), mh("fm", "C"), mh("mlp", "C")]), "D trees (D inputs) + FM ridge + MLP (C inputs), all multi-horizon"),
    "8p_hgbD_mh+fmC_mh+mlpC_mh_panic": (dict(specs=None, groups=[mh("hgb", "D"), mh("fm", "C"), mh("mlp", "C")], panic=True), "8 + fixed panic overlay"),
    "1a_p_D_hgb_mh_panic": (dict(specs=mh("hgb", "D"), panic=True), "baseline 1a + fixed panic overlay"),
    "fm_mh": (dict(specs=mh("fm", "C")), "C FM ridge, multi-horizon"),
    "mlp_C": (dict(specs=[("mlp", "C", 5)]), "MLP on C's features, 5-session rank target"),
}

if __name__ == "__main__":
    D = harness.load()
    for name in sys.argv[1:]:
        kw, note = C[name]
        t0 = time.time()
        pred = harness.walk_forward(lib.combine(**kw), seeds=(0, 1, 2), D=D)
        r = harness.score(pred, name, os.path.join(HERE, "RESULTS.jsonl"), note=note + " | %.0fs" % (time.time() - t0), D=D)
        by = " ".join("%+.3f" % v for v in r["ic_by_year"].values())
        print("%-34s IC %+.4f t %+.2f | %s | pos %d/7 | dec %+.1f%%/y sh %+.2f | %.0fs" % (
            name, r["ic"], r["ic_t"], by, sum(v > 0 for v in r["ic_by_year"].values()), r["decile_net_pct_per_year"],
            r["decile_net_sharpe"], time.time() - t0), flush=True)
