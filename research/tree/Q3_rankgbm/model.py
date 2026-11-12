"""Branch Q3_rankgbm best configuration: ens_ctrl_mh_huber (see REPORT.md).

    from model import fit_predict
    pred = harness.walk_forward(fit_predict, seeds=(0, 1, 2))      # development IC 0.0222

Equal-weight average of cross-sectional ranks of three tree models, each trained on the Thursdays <= train_end from
branch D's 25 inputs (D_ensembles/model.py, imported unchanged):
  1. the declared control: sklearn HistGradientBoosting, squared error on the 5-session rank target (D_ensembles/model.py);
  2. LightGBM, squared error on one multi-horizon target (rank of the mean rank of 3/5/10/20-session returns);
  3. LightGBM, Huber loss on the Gaussianised 5-session rank target.
Trees for 2 and 3 are chosen by rank IC on the last 104 training Thursdays (8-row gap), then refitted on all training rows.
Needs lightgbm (4.7.0 used).
"""
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "3")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import lib  # noqa: E402

MEMBERS = (None, dict(tgt="mh"), dict(obj="huber", tgt="gauss"))


def fit_predict(D, train_end, pred_rows, seed):
    ps = [lib.control(D, train_end, pred_rows, seed) if c is None else lib.fit_lgb(D, train_end, pred_rows, seed, c)
          for c in MEMBERS]
    with np.errstate(all="ignore"):
        return np.nanmean([lib.xrank(p) for p in ps], 0)


if __name__ == "__main__":
    import json
    H = lib.harness
    D = H.load()
    r = H.score(H.walk_forward(fit_predict, seeds=(0, 1, 2), D=D), "ens_ctrl_mh_huber (model.py re-run)", D=D)
    logged = [json.loads(l) for l in open(os.path.join(lib.HERE, "RESULTS.jsonl")) if '"ens_ctrl_mh_huber"' in l][-1]["ic"]
    print(json.dumps({"reproduced_ic": r["ic"], "logged_ic": logged, "match": abs(r["ic"] - logged) < 1e-9}))
