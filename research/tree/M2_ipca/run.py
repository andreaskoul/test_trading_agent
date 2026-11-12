"""Run one M2 configuration: python3 run.py NAME chars freq K lam xnorm  (scores restricted and unrestricted)."""
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "3")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "3")
os.environ.setdefault("MKL_NUM_THREADS", "3")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import json
import numpy as np
from harness import load, walk_forward, score
import ipca

name, chars, freq, K, lam, xnorm = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5]), sys.argv[6] == "1"
K = K if K == "auto" else int(K)
D = load()
t0 = time.time()
fr, fu = ipca.make(chars, freq, K, lam=lam, xnorm=xnorm, log=os.path.join(HERE, "FITS.jsonl"), tag=name)
desc = f"IPCA chars={chars} freq={freq} K={K} (auto: inner holdout pred R2 over 1,3,5) lam={lam} xnorm={xnorm}"
out = {}
for lab, f in (("R", fr), ("U", fu)):
    pred = walk_forward(f, seeds=(0, 1, 2), D=D)
    np.save(os.path.join(HERE, f"pred_{name}_{lab}.npy"), pred.astype(np.float32))
    res = score(pred, f"{name}_{lab}", os.path.join(HERE, "RESULTS.jsonl"),
                note=desc + (" restricted (Gamma_a=0)" if lab == "R" else " unrestricted (alpha)"), D=D)
    out[lab] = res
    print(lab, json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in res.items() if k not in ("note", "at")}))
print("secs", round(time.time() - t0))
