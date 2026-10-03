"""Shadow analysts and the model canary (PROTOCOL_fund.md, Amendment 4). Never traded.

Runs after the champion's decisions are committed, so it can never delay or change them.
* C2 self-consistency: the champion analyst prompt, 5 samples at temperature 0.7; score = median,
  confidence = max(0, 1 - sd/2) of the 5 scores.
* C3 text-only, anonymised: the same narratives with the firm's name, ticker and match terms
  masked as "the company", no price facts and no ideation hypothesis; one sample, temperature 0.
* Canary: 20 frozen analyst prompts (the first live week's, first 20 tickers with an ok memo),
  re-scored every week at temperature 0. Agreement with the frozen scores is the evidence for
  whether the served model changed (Amendment 4 continuity rule).
-> shadow.json, canary/canary.json, canary/history.csv
"""

import gzip
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from common import MODE, STATE, asof_from_env, llm, load, news_cutoff, narrative_text, require, save, week_dir

require("OPENROUTER_API_KEY")
asof = asof_from_env()
wd = week_dir(asof)
END = time.time() + 60 * 60
A = load(asof, "analysts.json")
SYSTEM = A["system"]
prompts = {r["ticker"]: r["user"] for r in map(json.loads, gzip.open(os.path.join(wd, "prompts_analysts.jsonl.gz"), "rt"))}
firms = {f["ticker"]: f for f in load(asof, "research.json")["firms"]}
S = pd.DataFrame(load(asof, "screen.json")["rows"]).set_index("ticker")
check = lambda o: None if o.get("score") in (-2, -1, 0, 1, 2) and isinstance(o.get("score"), int) \
    and isinstance(o.get("confidence"), (int, float)) else "bad memo"
SYSTEM_C3 = SYSTEM + """

THIS VERSION: the company's name and ticker are masked as "the company" and you get NO price
facts and no ideation hypothesis. Judge only from the news: what happened and whether it changes
next week's relative return. Do not try to guess which company it is."""


def mask(t, text):
    terms = [re.escape(t)] + [x for x in [firms.get(t, {}).get("match")] if x]
    name = str(S.loc[t, "Security"]) if t in S.index else ""
    if name:
        terms.append(re.escape(re.sub(r"\s*\(.*?\)", "", name)))
    for pat in terms:
        try:
            text = re.sub(pat, "the company", text, flags=re.I)
        except re.error:
            pass
    return text


def c2(t):
    if time.time() > END:
        return t, None
    scores, confs = [], []
    for k in range(5):
        st, out, meta, err = llm(SYSTEM, prompts[t], check, temperature=0.7)
        if st == "ok":
            scores.append(out["score"]); confs.append(out["confidence"])
    if len(scores) < 3:
        return t, None
    return t, {"score": int(np.median(scores)), "confidence": float(max(0.0, 1 - np.std(scores) / 2)), "samples": scores}


def c3(t):
    if time.time() > END:
        return t, None
    p_ = os.path.join(wd, "research", f"{t}.json")
    narr = json.load(open(p_)) if os.path.exists(p_) else None
    user = f"As-of Wednesday close {asof.date()}. Stock: the company.\n\n" + mask(t, narrative_text(narr, news_cutoff(asof)))
    st, out, meta, err = llm(SYSTEM_C3, user, check)
    return t, ({"score": out["score"], "confidence": float(out["confidence"])} if st == "ok" else None)


names = sorted(prompts)
with ThreadPoolExecutor(6) as ex:
    r2 = dict(ex.map(c2, names))
    r3 = dict(ex.map(c3, names))
print(f"shadow: C2 {sum(v is not None for v in r2.values())}/{len(names)}, C3 {sum(v is not None for v in r3.values())}/{len(names)}")

# ---- canary
cdir = os.path.join(STATE, MODE, "canary")
os.makedirs(cdir, exist_ok=True)
cp = os.path.join(cdir, "canary.json")
ok_names = [t for t in names if A["memos"][t]["status"] == "ok"]
if not os.path.exists(cp) and len(ok_names) < 15:
    canary = {"created": False, "why": f"only {len(ok_names)} ok memos; the canary is frozen from a healthy week"}
    print(f"canary: not frozen ({canary['why']})")
elif not os.path.exists(cp):
    base = ok_names[:20]
    json.dump({"created_from": str(asof.date()), "system": SYSTEM,
               "items": [{"ticker": t, "user": prompts[t], "score": A["memos"][t]["memo"]["score"],
                          "confidence": A["memos"][t]["memo"]["confidence"]} for t in base]}, open(cp, "w"), indent=1)
    canary = {"created": True, "n": len(base)}
    print(f"canary: frozen {len(base)} prompts from {asof.date()}")
else:
    C = json.load(open(cp))
    def rescore(it):
        st, out, meta, err = llm(C["system"], it["user"], check)
        return it["ticker"], (out["score"] if st == "ok" else None), meta.get("provider")
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(rescore, C["items"]))
    ref = {it["ticker"]: it["score"] for it in C["items"]}
    got = [(ref[t], s) for t, s, _ in res if s is not None]
    canary = {"asof": str(asof.date()), "n": len(got), "exact": float(np.mean([a == b for a, b in got])) if got else None,
              "mean_abs_diff": float(np.mean([abs(a - b) for a, b in got])) if got else None,
              "providers": sorted({p for _, _, p in res if p})}
    hp = os.path.join(cdir, "history.csv")
    pd.concat([pd.read_csv(hp) if os.path.exists(hp) else pd.DataFrame(), pd.DataFrame([canary])]).to_csv(hp, index=False)
    print(f"canary: {canary}")

save(asof, "shadow.json", {"asof": str(asof.date()), "c2_selfconsistency": r2, "c3_textonly": r3, "canary": canary,
                           "system_c3": SYSTEM_C3})
