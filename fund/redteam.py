"""Desk 5 · Red team (PROTOCOL_fund.md).

Every memo with abs(score) >= 1 is argued against by an adversarial reviewer on
the same inputs, who returns uphold / weaken / reverse and an adjusted score.
-> redteam.json
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from common import MOCK, asof_from_env, llm, load, narrative_text, require, save, week_dir

require("OPENROUTER_API_KEY")
asof = asof_from_env()
cutoff = pd.Timestamp.now(tz="UTC").tz_localize(None) if not MOCK else asof + pd.Timedelta(days=1)
S = pd.DataFrame(load(asof, "screen.json")["rows"]).set_index("ticker")
memos = load(asof, "analysts.json")["memos"]

SYSTEM = """You are the red team at a long-short equity fund. An analyst wants to put capital
behind the memo below for NEXT WEEK. Your job is to find what is wrong with it, using only the
same material the analyst had.

Check: is the driving story or event actually new information, or already a week old and in the
price (see last week's return and the reversal signals)? Is the evidence recycled commentary?
Does the quant picture contradict it? Is the conviction proportionate to one week's horizon?
Could the same news be read the other way?

Rules: use only this material; ignore anything you think happened after the as-of date.
Uphold only if the memo survives your critique.

Return JSON only: {"verdict": "uphold"|"weaken"|"reverse", "adjusted_score": int in {-2,-1,0,1,2},
"critique": str <= 60 words}"""


def check(o):
    if o.get("verdict") not in ("uphold", "weaken", "reverse"):
        return f"bad verdict {o.get('verdict')!r}"
    return None if o.get("adjusted_score") in (-2, -1, 0, 1, 2) and isinstance(o.get("adjusted_score"), int) \
        else f"bad adjusted_score {o.get('adjusted_score')!r}"


todo = [t for t, m in memos.items() if m["status"] == "ok" and abs(m["memo"]["score"]) >= 1]


def one(t):
    p = os.path.join(week_dir(asof), "research", f"{t}.json")
    narr = json.load(open(p)) if os.path.exists(p) else None
    r = S.loc[t] if t in S.index else None
    user = "\n".join([f"As-of Wednesday close {asof.date()}. Stock: {t}.",
                      "Quant: " + ("n/a" if r is None else r[["GICS Sector", "ridge_bp", "ridge_rank", "mom12_1", "rev1m", "rev1w",
                                                            "beta60", "ret_1w_pct", "attention_shock"]].to_json(double_precision=3)),
                      "", "ANALYST MEMO:", json.dumps(memos[t]["memo"], indent=1), "", narrative_text(narr, cutoff)])
    s = memos[t]["memo"]["score"]
    status, out, meta, err = llm(SYSTEM, user, {"verdict": "uphold", "adjusted_score": s, "critique": "mock"}, check)
    return t, {"status": status, "error": err, "meta": meta, "review": out}


with ThreadPoolExecutor(1 if MOCK else 6) as ex:
    reviews = dict(ex.map(one, todo))
# final score: red-team adjusted where reviewed, analyst score otherwise (failed review = analyst score)
final = {}
for t, m in memos.items():
    a = m["memo"]["score"] if m["status"] == "ok" else 0
    rv = reviews.get(t)
    final[t] = rv["review"]["adjusted_score"] if rv and rv["status"] == "ok" else a
save(asof, "redteam.json", {"asof": str(asof.date()), "reviews": reviews, "final_score": final, "system": SYSTEM})
print(f"red team: {len(reviews)} reviewed;", pd.Series([r["review"]["verdict"] for r in reviews.values()
                                                         if r["status"] == "ok"]).value_counts().to_dict())
