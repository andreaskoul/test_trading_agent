"""Score one named configuration: python3 run.py <name> [<name> ...]. Every run appends to RESULTS.jsonl."""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import harness
import models as M

CONFIGS = {
    "E01 ew ridge hl52": (M.ew_ridge(52), (0,), "ridge on rank-normalised y5, exponential weights, halflife 52 weeks"),
    "E02 rolling ridge 104w": (M.rolling_ridge(104), (0,), "ridge, last 104 weeks only"),
    "E03 interaction ridge": (M.interaction_ridge(), (0,), "coefficients linear in state (trend252, vol21, corr63), pooled ridge"),
    "E04 panic rule": (M.panic_rule(), (0,), "full-sample ridge; momentum coefficient zero when market 1y return<0 and vol21 in top third"),
    "E05 kernel ridge": (M.kernel_ridge(), (0,), "past weeks weighted by Gaussian similarity of (trend252, vol21, corr63), h=1"),
    "E06 exp weights": (M.exp_weights(), (0,), "Hedge over 10 signed single-characteristic experts, gain = weekly IC, frozen at train_end"),
    "E07 ic timing 52w": (M.ic_timing(52), (0,), "characteristic weights = trailing 52-week IC t-stat at train_end"),
    "E08 hypernet": (M.hypernet(), (0, 1, 2), "MLP 7 states -> 8 tanh -> 5 weights, weekly squared loss"),
    "E09 mixture of experts": (M.hypernet(experts=3), (0, 1, 2), "softmax gate over 3 weight vectors, 7 states"),
    "E10 static ridge control": (M.panic_rule(off=()), (0,), "CONTROL, no regime: full-sample ridge on rank-normalised y5 (same pipeline as E04 without the rule)"),
    "E11 panic rule ew52 base": (M.panic_rule(halflife=52), (0,), "E04 with exponentially weighted (halflife 52w) base ridge"),
    "E12 panic mom+52wh off": (M.panic_rule(off=(0, 4)), (0,), "E04, panic also zeroes the 52-week-high coefficient"),
    "E13 kernel ridge + panic": (M.kernel_ridge(panic_off=(0,)), (0,), "E05 with the E04 panic rule on top"),
    "E14 kernel h0.7 shrink0.3": (M.kernel_ridge(h=0.7, shrink=0.3), (0,), "E05 narrower kernel, 30% uniform weights"),
    "E15 panic rule vol median": (M.panic_rule(vol_q=0.5), (0,), "E04 with vol threshold at the train median instead of the top third"),
}


def run(name, D=None):
    fp, seeds, note = CONFIGS[name]
    t0 = time.time()
    pred = harness.walk_forward(fp, seeds=seeds, D=D)
    res = harness.score(pred, name, os.path.join(HERE, "RESULTS.jsonl"), note=note, D=D)
    by = " ".join(f"{v:+.3f}" for v in res["ic_by_year"].values())
    print(f"{name:28s} IC {res['ic']:+.4f} t {res['ic_t']:+.2f} | {by} | pos {sum(v > 0 for v in res['ic_by_year'].values())}/7"
          f" | net {res['decile_net_pct_per_year']:+.1f}%/y | {time.time() - t0:.0f}s", flush=True)
    return res


if __name__ == "__main__":
    D = harness.load()
    for n in sys.argv[1:] or list(CONFIGS):
        run(n, D)
