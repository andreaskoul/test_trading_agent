"""Desk 5 · Red team (PROTOCOL_fund.md).

Every memo with abs(score) >= 1 is argued against by an adversarial reviewer on
the same inputs, who upholds it or weakens it for a named flaw (Amendment 2: no reversals).
-> redteam.json
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from common import MOCK, PRICE_FACTS, asof_from_env, llm, load, narrative_text, require, save, week_dir

require("OPENROUTER_API_KEY")
asof = asof_from_env()
cutoff = pd.Timestamp.now(tz="UTC").tz_localize(None) if not MOCK else asof + pd.Timedelta(days=1)
S = pd.DataFrame(load(asof, "screen.json")["rows"]).set_index("ticker")
memos = load(asof, "analysts.json")["memos"]

SYSTEM = """You are the red team at a long-short equity fund. An analyst wants to put capital behind
the memo below for NEXT WEEK. You check it for specific errors, using only the material the
analyst had. You are a filter for mistakes, not a second opinion: a memo you merely disagree
with, or that you find "not certain enough", is upheld.

Weaken the memo ONLY if you can name one of these flaws, citing the evidence:
  factual   - the memo misstates a date, number or event in the material
  stale     - its driving event is more than 7 days before the as-of date and nothing newer supports it
  recycled  - its drivers are only opinion, price-target chatter or generic commentary
  contra    - a story or event in the material directly contradicts the thesis and the memo ignores it
  priced    - the recent return already exceeds any plausible reaction to the driving news
You cannot reverse a view: arguing the other side needs its own evidence, which is the analyst's job.
Weakening moves the score one step toward 0 (two steps only for a factual error that removes the
thesis entirely).

Rules: use only this material; ignore anything you think happened after the as-of date.

Return JSON only: {"verdict": "uphold"|"weaken", "flaw": null|"factual"|"stale"|"recycled"|"contra"|"priced",
"adjusted_score": int in {-2,-1,0,1,2}, "critique": str <= 60 words}"""


def check(o, score=None):
    v, f, a = o.get("verdict"), o.get("flaw"), o.get("adjusted_score")
    if v not in ("uphold", "weaken"):
        return f"bad verdict {v!r}"
    if not isinstance(a, int) or a not in (-2, -1, 0, 1, 2):
        return f"bad adjusted_score {a!r}"
    if v == "weaken" and f not in ("factual", "stale", "recycled", "contra", "priced"):
        return "weaken without a named flaw"
    if score is not None:
        if v == "uphold" and a != score:
            return "uphold must keep the score"
        if v == "weaken" and not (abs(a) < abs(score) and (a == 0 or (a > 0) == (score > 0))):
            return "weaken must move the score toward 0 without crossing it"
    return None


todo = [t for t, m in memos.items() if m["status"] == "ok" and abs(m["memo"]["score"]) >= 1]


def one(t):
    p = os.path.join(week_dir(asof), "research", f"{t}.json")
    narr = json.load(open(p)) if os.path.exists(p) else None
    r = S.loc[t] if t in S.index else None
    user = "\n".join([f"As-of Wednesday close {asof.date()}. Stock: {t}.",
                      "Price facts: " + ("n/a" if r is None else r[PRICE_FACTS].to_json(double_precision=2)),
                      "", "ANALYST MEMO:", json.dumps(memos[t]["memo"], indent=1), "", narrative_text(narr, cutoff)])
    s = memos[t]["memo"]["score"]
    status, out, meta, err = llm(SYSTEM, user, {"verdict": "uphold", "flaw": None, "adjusted_score": s, "critique": "mock"},
                                 lambda o: check(o, s))
    return t, {"status": status, "error": err, "meta": meta, "review": out}


with ThreadPoolExecutor(1 if MOCK else 6) as ex:
    reviews = dict(ex.map(one, todo))
# final score: red-team adjusted where reviewed, analyst score otherwise (failed review = analyst score)
final = {}
for t, m in memos.items():
    a = m["memo"]["score"] if m["status"] == "ok" else 0
    rv = reviews.get(t)
    final[t] = rv["review"]["adjusted_score"] if rv and rv["status"] == "ok" else a
ok_ = [r["review"] for r in reviews.values() if r["status"] == "ok"]
calib = {"reviewed": len(reviews), "ok": len(ok_),
         "uphold": sum(r["verdict"] == "uphold" for r in ok_), "weaken": sum(r["verdict"] == "weaken" for r in ok_),
         "flaws": pd.Series([r["flaw"] for r in ok_ if r["verdict"] == "weaken"]).value_counts().to_dict()}
save(asof, "redteam.json", {"asof": str(asof.date()), "reviews": reviews, "final_score": final, "calibration": calib,
                            "system": SYSTEM})
print("red team:", calib)
