"""Reproduction check of model.fit_predict (BEST), seeds 0-2; written to repro.json, not to RESULTS.jsonl."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import harness as H
import model
r = H.score(H.walk_forward(model.fit_predict, seeds=(0, 1, 2)), "repro moe_unif_d128 via model.fit_predict")
json.dump(r, open(os.path.join(HERE, "repro.json"), "w"), indent=1)
print(r["ic"])
