"""Run named Q3 configurations: python run.py name1 name2 ...  (skips anything already in STATE.json 'scored')."""
import json
import os
import sys
import time

os.environ["OMP_NUM_THREADS"] = "3"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import lib  # noqa: E402

H = lib.harness
STATE = os.path.join(HERE, "STATE.json")
RES = os.path.join(HERE, "RESULTS.jsonl")
PRED = os.path.join(lib.harness.ROOT, ".cache", "tree", "preds", "Q3_rankgbm")

R = "rank target"
CONFIGS = {
    "ref_control": (None, "declared control: D_ensembles/model.py unchanged (sklearn HGB, squared error on 5-session rank target)"),
    "lgb_l2": (dict(), "LightGBM gbdt, squared error on 5-session rank target, D hyperparameters (port check)"),
    "lgb_lambdarank_q5": (dict(obj="lambdarank", ngrades=5), "LightGBM lambdarank, query=Thursday, 5 quintile grades, linear gains, full truncation"),
    "lgb_lambdarank_q20": (dict(obj="lambdarank", ngrades=20), "lambdarank, 20 grades (ventiles), linear gains, full truncation"),
    "lgb_lambdarank_2side": (dict(obj="lambdarank", ngrades=5, two_side=True), "lambdarank q5 top model minus lambdarank q5 bottom model (reversed grades)"),
    "lgb_xendcg_q20": (dict(obj="rank_xendcg", ngrades=20), "LightGBM rank_xendcg listwise, 20 grades"),
    "lgb_ranknet": (dict(obj="ranknet", K=32, weighted=True), "sampled pairwise RankNet custom objective (32 partners/row, weight |dt|)"),
    "lgb_mono": (dict(mono=True), "lgb_l2 + monotone constraints on 11 momentum/reversal features (signs from training ICs)"),
    "lgb_dart": (dict(boosting="dart", lr=0.1, iters=(100, 200), extra=dict(drop_rate=0.1, skip_drop=0.5)), "DART boosting, lr 0.1, 100/200 trees"),
    "lgb_big": (dict(leaves=31, lr=0.02, min_data=1000, colsample=0.3, bagging=0.7, iters=(100, 200, 400, 800, 1200)), "deeper/larger: 31 leaves, lr .02, up to 1200 trees, colsample .3, bagging .7"),
    "lgb_gauss": (dict(tgt="gauss"), "lgb_l2 on Gaussianised rank target"),
    "lgb_mh": (dict(tgt="mh"), "lgb_l2 on one target = rank of mean rank of 3/5/10/20-session returns"),
    "lgb_win5": (dict(lo_years=5), "lgb_l2 trained on the last 5 years only"),
    "lgb_huber": (dict(obj="huber", tgt="gauss"), "Huber loss on Gaussianised rank"),
    "lgb_nan": (dict(feat="nan"), "lgb_l2 with missing features left NaN (LightGBM native missing handling) instead of NaN->0"),
    "lgb_rankZ": (dict(feat="rankZ"), "lgb_l2 with the five characteristics Z cross-sectionally ranked instead of clipped z-scores"),
    "ref_control_s10": (None, "ref_control re-scored with seeds 0-9 (seed-spread check)"),
    "lgb_mh_s10": (dict(tgt="mh"), "lgb_mh (best alternative) re-scored with seeds 0-9 (seed-spread check)"),
    "ens_ctrl_mh_huber": ("ens", "combination of winners: equal-weight cross-sectional rank average of ref_control, lgb_mh and lgb_huber, each refitted per (year, seed)"),
}


def _ens(D, te, rows, seed):
    ps = [lib.control(D, te, rows, seed), lib.fit_lgb(D, te, rows, seed, dict(tgt="mh")),
          lib.fit_lgb(D, te, rows, seed, dict(obj="huber", tgt="gauss"))]
    with np.errstate(all="ignore"):
        return np.nanmean([lib.xrank(p) for p in ps], 0)


def load_state():
    with open(STATE) as f:
        return json.load(f)


def save_state(st):
    st["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(STATE, "w") as f:
        json.dump(st, f, indent=1)


def results():
    return [json.loads(l) for l in open(RES) if l.strip()] if os.path.exists(RES) else []


def sync(st, note=None):
    """Make STATE.json agree with RESULTS.jsonl (the record), in the schema research/tree/state.py writes:
    scored = names; pending = planned names not yet scored; best = highest mean IC among configs positive >= 5/7."""
    R = results()
    names = [r["name"] for r in R]
    st["scored"] = names
    st["configurations_scored"] = len(R)
    planned = [p.split(":")[0] for p in st["plan"]]
    st["pending"] = [p for p in planned if p not in names]
    el = [r for r in R if sum(v > 0 for v in r["ic_by_year"].values()) >= 5]
    if el:
        b = max(el, key=lambda r: r["ic"])
        st["best"] = {k: b[k] for k in ("name", "ic", "ic_t", "decile_net_pct_per_year", "decile_net_sharpe")}
        st["best"]["rule"] = "highest development mean IC among configurations positive in >= 5 of 7 years"
    if note:
        st["notes"].append(note)
    if st.get("status") in (None, "not started", "in progress"):
        st["status"] = "running"
    return st


def register(name, spec):
    st = load_state()
    if not any(p.split(":")[0] == name for p in st["plan"]):
        st["plan"].append(f"{name}: {spec}")
    save_state(sync(st))


SEEDS = {"ref_control_s10": tuple(range(10)), "lgb_mh_s10": tuple(range(10))}   # name -> seeds tuple when not (0, 1, 2)


def fn_for(name):
    cfg = CONFIGS[name][0]
    if cfg is None:
        return lib.control
    if cfg == "ens":
        return _ens
    return lambda D, te, rows, seed: lib.fit_lgb(D, te, rows, seed, cfg)


def main(names, nxt=""):
    D = H.load()
    for name in names:
        st = load_state()
        if name in [r["name"] for r in results()]:
            print("skip", name)
            continue
        spec = CONFIGS[name][1]
        register(name, spec)
        t0 = time.time()
        pred = H.walk_forward(fn_for(name), seeds=SEEDS.get(name, (0, 1, 2)), D=D)
        el = time.time() - t0
        res = H.score(pred, name, RES, note=f"{spec} | {el:.0f}s", D=D)
        os.makedirs(PRED, exist_ok=True)
        np.save(os.path.join(PRED, name + ".npy"), pred.astype(np.float32))
        pos = sum(v > 0 for v in res["ic_by_year"].values())
        st = load_state()
        save_state(sync(st, f"scored {name} (IC {res['ic']:.4f}, t {res['ic_t']:.2f}, {pos}/7, {el:.0f}s); next: {nxt or 'see pending'}"))
        by = " ".join("%+.3f" % v for v in res["ic_by_year"].values())
        print("%-24s IC %+.4f t %+.2f | %s | pos %d/7 | dec %+.1f%%/y | %.0fs" % (
            name, res["ic"], res["ic_t"], by, pos, res["decile_net_pct_per_year"], el), flush=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--plan"]:            # register configurations in the plan without scoring them
        for n in sys.argv[2:]:
            register(n, CONFIGS[n][1])
    else:
        main(sys.argv[1:])
