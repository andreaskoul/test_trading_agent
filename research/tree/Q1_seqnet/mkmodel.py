"""Write model.py: seq.py's code with the chosen configuration bound as fit_predict. Usage: python mkmodel.py <config>"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
name = sys.argv[1]
cfg = dict(json.load(open(os.path.join(HERE, "configs.json")))[name])
spec = cfg.pop("spec"); cfg.pop("seeds", None)
src = open(os.path.join(HERE, "seq.py")).read()
head = f'''"""Q1_seqnet best configuration ({name}), self-contained (numpy, pandas, torch; D_ensembles/model.py for the 27 inputs).

    from model import fit_predict        # fit_predict(D, train_end, pred_rows, seed) -> (len(pred_rows), n_names)

{spec}
CONFIG below is the configuration; the rest is the branch's code (seq.py), copied.
"""
CONFIG = {json.dumps(cfg)}
'''
body = src.split('"""', 2)[2]
open(os.path.join(HERE, "model.py"), "w").write(head + body + "\n\nfit_predict = make(**CONFIG)\n")
print("model.py written for", name)
