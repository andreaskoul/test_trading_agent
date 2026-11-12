"""Round 2 of X3: (a) paired differences for the first three ridge configurations (not re-logged);
(b) staleness curve: the C32 expanding Fama-MacBeth model updated weekly but with a constant extra lag;
(c) exponential-weights mixing on the 32 columns, online and yearly."""
import os, sys, json, time, warnings
warnings.filterwarnings("ignore")
import numpy as np
import lib, harness
from run import CFG, LOG, W

D = harness.load()
def wic(pred):
    return np.concatenate([harness.weekly_ic(pred, D, harness.thursdays(D, y)) for y in harness.VAL_YEARS])
def paired(a, b, name):
    d = a - b; d = d[np.isfinite(d)]
    r = dict(name=name, diff=float(d.mean()), se=float(d.std(ddof=1) / np.sqrt(len(d))), weeks=int(len(d)))
    print("   paired %s: %+.4f (se %.4f, t %.2f)" % (name, r["diff"], r["se"], r["diff"] / r["se"]), flush=True)
    open(os.path.join(lib.HERE, "PAIRED.jsonl"), "a").write(json.dumps(r) + "\n")
def run(tag, note, log=True, **kw):
    pred = harness.walk_forward(lib.make(**kw), seeds=(0, 1, 2), D=D)
    if log:
        r = harness.score(pred, tag, LOG, note=note, D=D)
        print("%-34s ic %.4f t %.2f min_yr %.4f dec %.1f%%/yr  by_year %s" % (tag, r["ic"], r["ic_t"], r["min_year_ic"], r["decile_net_pct_per_year"],
              " ".join("%.3f" % v for v in r["ic_by_year"].values())), flush=True)
    return wic(pred)

for n in ("ridge_exp", "ridge_ew26", "ridge_ew104"):
    paired(run(n, "", log=False, online=True, **CFG[n]), run(n, "", log=False, online=False, **CFG[n]), n)

base = dict(kind="C32", mode="fm")
yr = run("", "", log=False, online=False, **base)
on0 = run("", "", log=False, online=True, **base)
for wk in (13, 26, 52, 104):
    ic = run("c32_fm_exp | online, extra lag %dw" % wk, "staleness diagnostic: cut = t-6-%d sessions; expanding Fama-MacBeth, 32 columns" % (wk * W), online=True, lag=wk * W, **base)
    paired(ic, on0, "c32_fm_exp lag%dw minus lag0 (online)" % wk)

for eta in (0.5,):
    h = dict(kind="C32", mode="hedge", eta=eta)
    a = run("c32_hedge | yearly", str(h) + " cut=train_end", online=False, **h)
    b = run("c32_hedge | online", str(h) + " cut=t-6", online=True, **h)
    paired(b, a, "c32_hedge")
