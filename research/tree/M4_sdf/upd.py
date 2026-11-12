"""Update STATE.json: python3 upd.py "note" [best_name]"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = ["S01_C24_wk_l2", "S02_C24_wk_mv", "S03_X324_wk_l2", "S04_X324_wk_mv", "S05_C24_wk_en_raw", "S06_C24_wk_en_pc",
        "S07_X324_wk_en_raw", "S08_X324_wk_en_pc", "S09_C24_wk_pck", "S10_C24_d5_l2", "S11_X324_d5_l2", "S12_C24_d1_l2"]
p = os.path.join(HERE, "STATE.json")
s = json.load(open(p))
res = [json.loads(l) for l in open(os.path.join(HERE, "RESULTS.jsonl"))] if os.path.exists(os.path.join(HERE, "RESULTS.jsonl")) else []
s["scored"] = [r["name"] for r in res]
s["configurations_scored"] = len(res)
s["plan"] = PLAN
s["pending"] = [n for n in PLAN if n not in s["scored"]]
s["status"] = "in progress" if s["pending"] else "scored"
if res:
    b = max(res, key=lambda r: r["ic_t"]); s["best"] = {"name": b["name"], "ic": round(b["ic"], 4), "ic_t": round(b["ic_t"], 2)}
s["deliverables"]["model.py"] = os.path.exists(os.path.join(HERE, "model.py"))
s["deliverables"]["REPORT.md"] = os.path.exists(os.path.join(HERE, "REPORT.md"))
s["notes"].append(sys.argv[1])
s["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(s, open(p, "w"), indent=1)
