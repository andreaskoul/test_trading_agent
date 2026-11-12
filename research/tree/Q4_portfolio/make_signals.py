"""Produce the Q4 input signals once (development 2013-2019, harness.walk_forward). Usage: python make_signals.py trees|ipca"""
import importlib.util
import os
import sys

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[v] = "3"
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
sys.path.insert(0, TREE)
import harness  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(TREE)), ".cache", "tree", "preds", "Q4_portfolio")


def load_module(rel):
    p = os.path.join(os.path.dirname(os.path.dirname(TREE)), rel)
    spec = importlib.util.spec_from_file_location(os.path.basename(os.path.dirname(p)), p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


if __name__ == "__main__":
    which = sys.argv[1]
    path = {"trees": "research/tree/finalists/D_hgb_mh/model.py", "ipca": "research/tree/M2_ipca/model.py"}[which]
    D = harness.load()
    # IPCA is deterministic (seed unused), so one seed gives the same mean-of-ranks as three
    seeds = (0, 1, 2) if which == "trees" else (0,)
    pred = harness.walk_forward(load_module(path).fit_predict, seeds=seeds, D=D)
    np.save(os.path.join(OUT, f"sig_{which}.npy"), pred)
    print(which, harness.score(pred, which, D=D))
