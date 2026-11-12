"""Before the holdout: each finalist's model.py must reproduce its logged development IC to 4 decimals."""
import importlib.util, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import harness as H
LOGGED = {"X1_8p": ("X1_combine", "8p_hgbD_mh+fmC_mh+mlpC_mh_panic"), "A_mse_rank": ("A_loss", "mse_rank"), "D_hgb_mh": ("D_ensembles", "hgb_multihorizon")}
f = sys.argv[1]
b, name = LOGGED[f]
want = next(json.loads(l) for l in open(os.path.join(os.path.dirname(HERE), b, "RESULTS.jsonl")) if json.loads(l)["name"] == name)
spec = importlib.util.spec_from_file_location("m", os.path.join(HERE, f, "model.py")); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
r = H.score(H.walk_forward(m.fit_predict, seeds=(0, 1, 2)), f + " (verify)")
ok = round(r["ic"], 4) == round(want["ic"], 4)
json.dump({"finalist": f, "logged_ic": want["ic"], "reproduced_ic": r["ic"], "ok": ok}, open(os.path.join(HERE, f, "VERIFY.json"), "w"), indent=1)
print(f, "logged", round(want["ic"], 5), "reproduced", round(r["ic"], 5), "OK" if ok else "MISMATCH")
