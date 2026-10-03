"""Amendment 6 · Shadow challengers C8 and C9 (fund/AMENDMENT6_PLAN.md). Never traded. -> shadow_info.json

C8, informed analysts: the champion analyst's own prompt for each covered name, unchanged, with
  * the MACRO BRIEF first (macro_desk.py; identical for every name, so providers can cache it),
  * the coverage reason (core 20 / nominated / rule slot),
  * the NEIGHBOURHOOD block after it (neighbours.py).
  Same schema, checks, model and temperature as the champion. No red team: C8 is compared with the
  `analyst` book, so the only difference between the two is the information.
C9, cross-sectional re-score: one call reads every ok C8 memo and the brief and re-scores each name
  -2..+2 relative to the others, using the full range. Book: C9 score x C8 confidence.
Degraded (as the champion): more than 25% of C8 memos failed -> no C8 or C9 book this week.
"""

import gzip
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from common import MOCK, asof_from_env, llm, load, news_cutoff, require, save, week_dir

require("OPENROUTER_API_KEY")
asof = asof_from_env()
wd = week_dir(asof)
A = load(asof, "analysts.json")
champ = {r["ticker"]: r["user"] for r in map(json.loads, gzip.open(os.path.join(wd, "prompts_analysts.jsonl.gz"), "rt"))}
idea = load(asof, "ideation.json")
macro = load(asof, "macro_brief.json") if os.path.exists(os.path.join(wd, "macro_brief.json")) else {}
nbr = (load(asof, "neighbours.json") if os.path.exists(os.path.join(wd, "neighbours.json")) else {}).get("names", {})
S = pd.DataFrame(load(asof, "screen.json")["rows"]).set_index("ticker")
SHARED = macro.get("brief") or "MACRO BRIEF: unavailable this week."
WHY = {"core": "one of the dashboard's core 20 firms", "nominated": "nominated by the ideation desk",
       "rule": "a rule slot (top/bottom of the quant ranking or the largest attention shocks)"}
SYSTEM = A["system"] + """

THIS VERSION gets two extra blocks. The MACRO BRIEF at the top is the same for every stock: use it to
judge whether this stock's news runs with or against what moves its sector or the market this week, and
whether a scheduled release falls inside the holding week. The NEIGHBOURHOOD block lists news of the
firms most often covered together with this one, the rest of its sub-industry, and its own SEC 8-K
filings: use it for news that reaches this firm through customers, suppliers and competitors, and for
material filings the articles may have missed. The rules above still apply: score 0 unless the news,
these blocks included, gives a dated reason specific to this firm."""
check = lambda o: None if o.get("score") in (-2, -1, 0, 1, 2) and isinstance(o.get("score"), int) \
    and isinstance(o.get("confidence"), (int, float)) and 0 <= o["confidence"] <= 1 else "bad memo"
END, PROMPTS = time.time() + 40 * 60, []


def one(t):
    if t not in champ:
        return t, {"status": "failed", "error": "no champion prompt", "meta": {}, "memo": None, "prompt_chars": 0}
    if time.time() > END:
        return t, {"status": "failed", "error": "desk time budget spent", "meta": {}, "memo": None, "prompt_chars": 0}
    why = "; ".join(WHY[k] for k in idea.get("why", {}).get(t, [])) or "n/a"
    user = "\n\n".join([SHARED, champ[t] + f"\nCoverage reason: {why}.",
                        (nbr.get(t) or {}).get("text") or "NEIGHBOURHOOD: unavailable this week."])
    PROMPTS.append({"ticker": t, "system": SYSTEM, "user": user})
    m0 = (A["memos"].get(t) or {}).get("memo") or {"score": 0, "confidence": 0.5}
    st, out, meta, err = llm(SYSTEM, user, {**m0, "thesis": "mock c8"}, check)
    print(f"c8 {t}: {st}" + (f" score {out['score']}" if out else f" ({err})"), flush=True)
    return t, {"status": st, "error": err, "meta": meta, "memo": out, "prompt_chars": len(user)}


with ThreadPoolExecutor(1 if MOCK else 6) as ex:
    c8 = dict(ex.map(one, idea["coverage"]))
ok = {t: v["memo"] for t, v in c8.items() if v["status"] == "ok"}
degraded = len(ok) < 0.75 * len(c8)

# ---- C9: re-score the whole cross-section in one call
c9 = {"status": "skipped", "error": "degraded C8" if degraded else None, "meta": {}, "scores": {}}
if not degraded and ok:
    SYS9 = """You are the cross-sectional analyst of a long-short equity fund. You get this week's analyst
memos for every covered stock (score -2..+2, confidence, thesis, drivers) and the macro brief. The fund
holds next week's relative winners long and relative losers short; market beta and sectors are hedged.
Re-score EVERY stock -2..+2 for its expected return next week RELATIVE TO THE OTHER STOCKS IN THIS LIST:
use the full range, give +-2 only to the strongest relative views, and 0 to names whose news is weak,
already priced, or common to many names in the list (a sector-wide or macro move is hedged away).
Use only this material. Return JSON only: {"scores": {"TICKER": int, ...}} with every ticker listed."""
    rows = [f"{t} | {S['GICS Sector'].get(t, 'n/a')} | score {m['score']} | conf {m['confidence']} | {m.get('thesis')} | "
            f"drivers: {'; '.join(map(str, m.get('drivers') or []))}" for t, m in ok.items()]
    u9 = SHARED + "\n\nMEMOS (ticker | sector | score | confidence | thesis | drivers):\n" + "\n".join(rows)
    chk9 = lambda o: None if isinstance(o.get("scores"), dict) and set(o["scores"]) == set(ok) and all(
        v in (-2, -1, 0, 1, 2) and isinstance(v, int) for v in o["scores"].values()) else "scores must cover every ticker, ints -2..2"
    st, out, meta, err = llm(SYS9, u9, {"scores": {t: m["score"] for t, m in ok.items()}}, chk9)
    c9 = {"status": st, "error": err, "meta": meta, "scores": (out or {}).get("scores", {}), "system": SYS9}
    PROMPTS.append({"ticker": "_c9", "system": SYS9, "user": u9})

metas = [v["meta"] for v in c8.values()] + [c9["meta"], macro.get("meta") or {}]
use = [m.get("usage") or {} for m in metas]
usage = {"calls": sum(bool(u) for u in use), "prompt_tokens": sum(u.get("prompt_tokens", 0) for u in use),
         "completion_tokens": sum(u.get("completion_tokens", 0) for u in use),
         "cached_tokens": sum((u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0 for u in use),
         "cost_usd": round(sum(u.get("cost", 0) or 0 for u in use), 4)}
with gzip.open(os.path.join(wd, "prompts_c8.jsonl.gz"), "wt") as fh:
    for r in PROMPTS:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
save(asof, "shadow_info.json", {"asof": str(asof.date()), "cutoff": str(news_cutoff(asof)), "system_c8": SYSTEM,
                                "brief_status": macro.get("status"), "c8": c8, "c9": c9, "degraded": degraded, "usage": usage})
print(f"c8: {len(ok)}/{len(c8)} ok{' (DEGRADED: no book)' if degraded else ''}; c9: {c9['status']}; "
      f"usage incl. macro desk {usage}")
