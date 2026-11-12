"""Run one M4 configuration: python3 run.py NAME chars freq method [en_space]"""
import os
import sys
import time

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(v, "3")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import json
import numpy as np
from harness import load, walk_forward, score
import sdf

name, chars, freq, method = sys.argv[1:5]
space = sys.argv[5] if len(sys.argv) > 5 else "raw"
D = load()
t0 = time.time()
f = sdf.make(chars, freq, method, space, log=os.path.join(HERE, "FITS.jsonl"), tag=name)
pred = walk_forward(f, seeds=(0, 1, 2), D=D)
np.save(os.path.join(HERE, f"pred_{name}.npy"), pred.astype(np.float32))
desc = (f"KNS SDF chars={chars} freq={freq} method={method}" + (f" space={space}" if method == "en" else "")
        + "; F=Z'x/n with x standardised per period; gamma (and L1) by 3-fold contiguous CV of OOS pricing-error R2 in training")
res = score(pred, name, os.path.join(HERE, "RESULTS.jsonl"), note=desc, D=D)
print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in res.items() if k not in ("note", "at")}))
print("secs", round(time.time() - t0))
