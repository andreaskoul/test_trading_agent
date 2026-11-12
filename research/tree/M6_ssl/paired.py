"""Paired weekly IC difference (treatment - control) with Newey-West(4) t, from saved predictions; and harness.increment
for named configurations. python3 paired.py treat:ctrl [...] --inc name1 name2"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from harness import load, weekly_ic, thursdays, VAL_YEARS, increment  # noqa: E402

D = load()
rows = np.concatenate([thursdays(D, y) for y in VAL_YEARS])
P = lambda n: np.load(os.path.join(HERE, "pred_%s.npy" % n)).astype(np.float64)
args = sys.argv[1:]
inc = args[args.index("--inc") + 1:] if "--inc" in args else []
for pair in (args[:args.index("--inc")] if inc else args):
    a, b = pair.split(":")
    d = weekly_ic(P(a), D, rows) - weekly_ic(P(b), D, rows)
    d = d[np.isfinite(d)]
    n, dd = len(d), d - d.mean()
    v = dd @ dd / n
    for l in range(1, 5):
        v += 2 * (1 - l / 5) * (dd[l:] @ dd[:-l]) / n
    print("%s - %s: diff %.4f  NW t %.2f  weeks %d" % (a, b, d.mean(), d.mean() / np.sqrt(v / n), n))
for name in inc:
    r = increment(P(name), name, os.path.join(HERE, "INCREMENT.jsonl"), note="M6 increment over MASTER", D=D)
    print(name, {k: r[k] for k in ("ic", "base_ic", "increment", "increment_t", "years_increment_positive", "corr_with_base")})
